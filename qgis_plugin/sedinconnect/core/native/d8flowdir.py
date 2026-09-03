"""
d8flowdir.py - 100% Exact Port of TauDEM 5.3.7 D8FlowDir C++ Implementation.
"""
import numpy as np
import numba as nb

# TauDEM 1-based direction constants
# 1=E, 2=NE, 3=N, 4=NW, 5=W, 6=SW, 7=S, 8=SE
# d1 = x offset (col), d2 = y offset (row, negative = North = row-1)
# d1[9] = { 0, 1,  1,  0, -1, -1, -1, 0, 1 };
# d2[9] = { 0, 0, -1, -1, -1,  0,  1, 1, 1 };

@nb.njit
def _dont_cross(k, i, j, flow_dir):
    # i is col (x), j is row (y)
    d1 = np.array([0, 1,  1,  0, -1, -1, -1, 0, 1], dtype=nb.int32)
    d2 = np.array([0, 0, -1, -1, -1,  0,  1, 1, 1], dtype=nb.int32)
    ans = 0
    if k == 2:
        n1, c1, n2, c2 = 1, 4, 3, 8
        in1, jn1 = i + d1[n1], j + d2[n1]
        in2, jn2 = i + d1[n2], j + d2[n2]
        if flow_dir[jn1, in1] == c1 or flow_dir[jn2, in2] == c2:
            ans = 1
    elif k == 4:
        n1, c1, n2, c2 = 3, 6, 5, 2
        in1, jn1 = i + d1[n1], j + d2[n1]
        in2, jn2 = i + d1[n2], j + d2[n2]
        if flow_dir[jn1, in1] == c1 or flow_dir[jn2, in2] == c2:
            ans = 1
    elif k == 6:
        n1, c1, n2, c2 = 7, 4, 5, 8
        in1, jn1 = i + d1[n1], j + d2[n1]
        in2, jn2 = i + d1[n2], j + d2[n2]
        if flow_dir[jn1, in1] == c1 or flow_dir[jn2, in2] == c2:
            ans = 1
    elif k == 8:
        n1, c1, n2, c2 = 1, 6, 7, 2
        in1, jn1 = i + d1[n1], j + d2[n1]
        in2, jn2 = i + d1[n2], j + d2[n2]
        if flow_dir[jn1, in1] == c1 or flow_dir[jn2, in2] == c2:
            ans = 1
    return ans

@nb.njit
def _set_pos_dir_d8_nb(dem, dx, dy, nodata_val):
    ny, nx = dem.shape
    d1 = np.array([0, 1,  1,  0, -1, -1, -1, 0, 1], dtype=nb.int32)
    d2 = np.array([0, 0, -1, -1, -1,  0,  1, 1, 1], dtype=nb.int32)
    
    # Precalculate fact[k] = 1.0 / sqrt(d1[k]*d1[k]*dx*dx + d2[k]*d2[k]*dy*dy)
    fact = np.zeros(9, dtype=nb.float64)
    for k in range(1, 9):
        fact[k] = 1.0 / np.sqrt(d1[k] * d1[k] * dx * dx + d2[k] * d2[k] * dy * dy)

    flow_dir = np.full((ny, nx), -32768, dtype=nb.int16)
    slope = np.full((ny, nx), -1.0, dtype=nb.float32)

    # Queue of flat cells
    max_q = nx * ny
    q_x = np.empty(max_q, dtype=nb.int32)
    q_y = np.empty(max_q, dtype=nb.int32)
    q_tail = 0

    for j in range(ny):
        for i in range(nx):
            # Border check (i==0, i==nx-1, j==0, j==ny-1) or nodata
            z = dem[j, i]
            if (i == 0 or i == nx - 1 or j == 0 or j == ny - 1 or
                z == nodata_val or np.isnan(z) or z < -1e30):
                continue

            # Contamination check: if any of the 8 neighbors is nodata -> contaminated
            con = 0
            for k in range(1, 9):
                in_x = i + d1[k]
                jn_y = j + d2[k]
                zn = dem[jn_y, in_x]
                if zn == nodata_val or np.isnan(zn) or zn < -1e30:
                    con = -1
                    break

            if con == -1:
                flow_dir[j, i] = -32768
            else:
                flow_dir[j, i] = 0
                smax = 0.0
                best_k = 0
                for k in (1, 3, 5, 7):
                    in_x = i + d1[k]
                    jn_y = j + d2[k]
                    zn = dem[jn_y, in_x]
                    drop = z - zn
                    slp = drop * fact[k]
                    if slp > smax:
                        smax = slp
                        best_k = k

                for k in (2, 4, 6, 8):
                    in_x = i + d1[k]
                    jn_y = j + d2[k]
                    zn = dem[jn_y, in_x]
                    drop = z - zn
                    slp = drop * fact[k]
                    if slp > smax and _dont_cross(k, i, j, flow_dir) == 0:
                        smax = slp
                        best_k = k

                if best_k > 0:
                    flow_dir[j, i] = best_k
                else:
                    # Flat cell
                    q_x[q_tail] = i
                    q_y[q_tail] = j
                    q_tail += 1

    return flow_dir, slope, fact, q_x, q_y, q_tail

@nb.njit
def _resolve_flats_d8_nb(dem, flow_dir, fact, q_x, q_y, q_tail, nodata_val):
    ny, nx = dem.shape
    d1 = np.array([0, 1,  1,  0, -1, -1, -1, 0, 1], dtype=nb.int32)
    d2 = np.array([0, 0, -1, -1, -1,  0,  1, 1, 1], dtype=nb.int32)
    order = np.array([1, 3, 5, 7, 2, 4, 6, 8], dtype=nb.int32)

    total_num_flat = q_tail
    if total_num_flat == 0:
        return flow_dir

    last_num_flat = total_num_flat
    
    # Working dem array for multi-pass iterations
    elev_dem = dem.copy()
    flat_x = q_x[:total_num_flat].copy()
    flat_y = q_y[:total_num_flat].copy()

    while total_num_flat > 0:
        elev2 = np.ones((ny, nx), dtype=nb.int16)
        dn = np.zeros((ny, nx), dtype=nb.int16)
        s = np.zeros((ny, nx), dtype=nb.int16)

        nflat = total_num_flat

        # 1. incfall - drain toward lower ground
        num_inc_old = -1
        st = 1
        num_inc_total = 0

        while num_inc_total != num_inc_old:
            num_inc = 0
            num_inc_old = num_inc_total
            for idx in range(nflat):
                i = flat_x[idx]
                j = flat_y[idx]

                do_nothing = False
                z = elev_dem[j, i]
                for k in range(1, 9):
                    if _dont_cross(k, i, j, flow_dir) == 0:
                        in_x = i + d1[k]
                        jn_y = j + d2[k]
                        zn = elev_dem[jn_y, in_x]
                        elev_diff = z - zn
                        fdir_n = flow_dir[jn_y, in_x]

                        if elev_diff >= 0 and fdir_n > 0 and fdir_n < 9:
                            do_nothing = True
                            break
                        elif elev_diff == 0:
                            e2n = elev2[jn_y, in_x]
                            if e2n >= 0 and e2n < st:
                                do_nothing = True
                                break

                if not do_nothing:
                    elev2[j, i] += 1
                    num_inc += 1

            num_inc_total = num_inc
            st += 1

        # Check for unresolvable pits
        if num_inc_total > 0:
            for idx in range(nflat):
                i = flat_x[idx]
                j = flat_y[idx]

                do_nothing = False
                z = elev_dem[j, i]
                for k in range(1, 9):
                    if _dont_cross(k, i, j, flow_dir) == 0:
                        in_x = i + d1[k]
                        jn_y = j + d2[k]
                        zn = elev_dem[jn_y, in_x]
                        elev_diff = z - zn
                        fdir_n = flow_dir[jn_y, in_x]

                        if elev_diff >= 0 and fdir_n > 0 and fdir_n < 9:
                            do_nothing = True
                            break
                        elif elev_diff == 0:
                            e2n = elev2[jn_y, in_x]
                            if e2n >= 0 and e2n < st:
                                do_nothing = True
                                break

                if not do_nothing:
                    flow_dir[j, i] = -32768

        # 2. incrise - drain away from higher ground
        done = False
        num_inc_old = 0
        while not done:
            num_inc = 0
            for idx in range(nflat):
                i = flat_x[idx]
                j = flat_y[idx]

                z = elev_dem[j, i]
                for k in range(1, 9):
                    in_x = i + d1[k]
                    jn_y = j + d2[k]
                    zn = elev_dem[jn_y, in_x]
                    if z - zn < 0:
                        dn[j, i] = 1
                    if dn[jn_y, in_x] > 0 and s[jn_y, in_x] > 0:
                        dn[j, i] = 1

            for idx in range(nflat):
                i = flat_x[idx]
                j = flat_y[idx]
                if dn[j, i] > 0:
                    s[j, i] += 1
                    num_inc += 1

            if num_inc == num_inc_old:
                done = True
            num_inc_old = num_inc

        for idx in range(nflat):
            i = flat_x[idx]
            j = flat_y[idx]
            elev2[j, i] += s[j, i]

        # 3. setFlow2: assign directions
        local_still_flat = 0
        new_q_tail = 0

        for idx in range(nflat):
            i = flat_x[idx]
            j = flat_y[idx]

            smax = 0.0
            z = elev_dem[j, i]
            e2_val = elev2[j, i]

            for ii in range(8):
                k = order[ii]
                in_x = i + d1[k]
                jn_y = j + d2[k]
                
                if dn[jn_y, in_x] > 0:
                    # In flat
                    slp = fact[k] * (e2_val - elev2[jn_y, in_x])
                    if slp > smax:
                        flow_dir[j, i] = k
                        smax = slp
                else:
                    # Neighbor is not in flat
                    ed = z - elev_dem[jn_y, in_x]
                    if ed >= 0:
                        flow_dir[j, i] = k
                        break

            if flow_dir[j, i] == 0:
                flat_x[new_q_tail] = i
                flat_y[new_q_tail] = j
                new_q_tail += 1
                local_still_flat += 1

        total_num_flat = local_still_flat
        if total_num_flat >= last_num_flat:
            break
        last_num_flat = total_num_flat

        if total_num_flat > 0:
            elev_dem = elev2.astype(np.float32)

    return flow_dir

@nb.njit
def _calc_slope_d8_nb(dem, flow_dir, fact, nodata_val):
    ny, nx = dem.shape
    d1 = np.array([0, 1,  1,  0, -1, -1, -1, 0, 1], dtype=nb.int32)
    d2 = np.array([0, 0, -1, -1, -1,  0,  1, 1, 1], dtype=nb.int32)
    slope = np.full((ny, nx), -1.0, dtype=nb.float32)

    for j in range(ny):
        for i in range(nx):
            fdir = flow_dir[j, i]
            if (i == 0 or i == nx - 1 or j == 0 or j == ny - 1 or
                fdir <= 0 or fdir > 8):
                slope[j, i] = -1.0
            else:
                in_x = i + d1[fdir]
                jn_y = j + d2[fdir]
                elev_diff = dem[j, i] - dem[jn_y, in_x]
                slope[j, i] = np.float32(elev_diff * fact[fdir])

    return slope

def compute_d8_flowdir(dem: np.ndarray, cell_size: float,
                       nodata: float = -9999.0,
                       log_func=print):
    """
    100% TauDEM-compatible D8 flow direction and slope.
    """
    rows, cols = dem.shape
    log_func(f"Computing D8 flow direction ({rows}x{cols})...")

    dem_f32 = dem.astype(np.float32)
    ndv_f32 = np.float32(nodata) if nodata is not None else np.float32(-9999.0)

    flow_dir, _, fact, q_x, q_y, q_tail = _set_pos_dir_d8_nb(
        dem_f32, float(cell_size), float(cell_size), ndv_f32
    )

    n_flats = q_tail
    if n_flats > 0:
        log_func(f"  Resolving {n_flats} flat/pit cells...")
        flow_dir = _resolve_flats_d8_nb(
            dem_f32, flow_dir, fact, q_x, q_y, q_tail, ndv_f32
        )

    sd8 = _calc_slope_d8_nb(dem_f32, flow_dir, fact, ndv_f32)

    # TauDEM convention:
    # flow_dir: -32768 for nodata, 1..8 for valid directions, 0 for unresolved flats
    # sd8: -1.0 for nodata / flat
    pdir_out = flow_dir.astype(np.float32)
    pdir_out[flow_dir == -32768] = -1.0
    
    sd8_out = sd8.copy()
    sd8_out[flow_dir == -32768] = nodata

    remaining = int(np.sum(flow_dir == 0))
    log_func(f"  D8 complete. Flat cells remaining: {remaining}")

    return pdir_out, sd8_out
