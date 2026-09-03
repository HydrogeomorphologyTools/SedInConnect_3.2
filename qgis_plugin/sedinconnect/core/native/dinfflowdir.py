"""
dinfflowdir.py - 100% Exact Port of TauDEM 5.3.7 DinfFlowDir C++ Implementation.
"""
import numpy as np
try:
    import numba as nb
    HAVE_NUMBA = True
except ImportError:
    HAVE_NUMBA = False
    class _MockNumba:
        int8 = np.int8
        int16 = np.int16
        int32 = np.int32
        int64 = np.int64
        uint8 = np.uint8
        uint16 = np.uint16
        uint32 = np.uint32
        uint64 = np.uint64
        float32 = np.float32
        float64 = np.float64
        boolean = np.bool_
        
        @staticmethod
        def njit(*args, **kwargs):
            if len(args) == 1 and callable(args[0]):
                return args[0]
            def decorator(func):
                return func
            return decorator
            
        @staticmethod
        def jit(*args, **kwargs):
            if len(args) == 1 and callable(args[0]):
                return args[0]
            def decorator(func):
                return func
            return decorator
            
        prange = range
    nb = _MockNumba()



@nb.njit
def _vslope(e0, e1, e2, d1, d2, dd):
    s1 = 0.0
    s2 = 0.0
    if d1 != 0.0:
        s1 = (e0 - e1) / d1
    if d2 != 0.0:
        s2 = (e1 - e2) / d2

    if s2 == 0.0 and s1 == 0.0:
        a = 0.0
    else:
        a = np.arctan2(s2, s1)

    ad = np.arctan2(d2, d1)
    if a < 0.0:
        a = 0.0
        s = s1
    elif a > ad:
        a = ad
        s = (e0 - e2) / dd
    else:
        s = np.sqrt(s1 * s1 + s2 * s2)
    return s, a

@nb.njit
def _dont_cross_dinf(k, i, j, flow_dir):
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
def _set_pos_dir_dinf_nb(dem, dx, dy, nodata_val):
    ny, nx = dem.shape
    PI = 3.141592653589793
    MISSINGFLOAT = -1e38

    d1 = np.array([0, 1,  1,  0, -1, -1, -1, 0, 1], dtype=nb.int32)
    d2 = np.array([0, 0, -1, -1, -1,  0,  1, 1, 1], dtype=nb.int32)

    # In TauDEM SET2:
    # I1 is row offset, J1 is col offset
    # I2 is row offset, J2 is col offset
    ID1 = np.array([0, 1, 2, 2, 1, 1, 2, 2, 1], dtype=nb.int32)
    ID2 = np.array([0, 2, 1, 1, 2, 2, 1, 1, 2], dtype=nb.int32)
    I1 = np.array([0, 0, -1, -1, 0, 0, 1, 1, 0], dtype=nb.int32)
    I2 = np.array([0, -1, -1, -1, -1, 1, 1, 1, 1], dtype=nb.int32)
    J1 = np.array([0, 1, 0, 0, -1, -1, 0, 0, 1], dtype=nb.int32)
    J2 = np.array([0, 1, 1, -1, -1, -1, -1, 1, 1], dtype=nb.int32)
    ANGC = np.array([0.0, 0.0, 1.0, 1.0, 2.0, 2.0, 3.0, 3.0, 4.0], dtype=nb.float64)
    ANGF = np.array([0.0, 1.0, -1.0, 1.0, -1.0, 1.0, -1.0, 1.0, -1.0], dtype=nb.float64)

    DXX = np.array([0.0, dx, dy], dtype=nb.float64)
    DD = np.sqrt(dx * dx + dy * dy)

    flow_dir = np.full((ny, nx), MISSINGFLOAT, dtype=nb.float32)
    slope = np.full((ny, nx), -1.0, dtype=nb.float32)

    max_q = nx * ny
    q_x = np.empty(max_q, dtype=nb.int32)
    q_y = np.empty(max_q, dtype=nb.int32)
    q_tail = 0

    for j in range(ny):
        for i in range(nx):
            z = dem[j, i]
            if (i == 0 or i == nx - 1 or j == 0 or j == ny - 1 or
                z == nodata_val or np.isnan(z) or z < -1e30):
                continue

            con = 0
            for k in range(1, 9):
                in_x = i + d1[k]
                jn_y = j + d2[k]
                zn = dem[jn_y, in_x]
                if zn == nodata_val or np.isnan(zn) or zn < -1e30:
                    con = -1
                    break

            if con == -1:
                flow_dir[j, i] = MISSINGFLOAT
            else:
                flow_dir[j, i] = -1.0
                smax = 0.0
                kd = 0
                sk = np.zeros(9, dtype=nb.float64)
                angle_k = np.zeros(9, dtype=nb.float64)

                for k in range(1, 9):
                    a = np.float64(dem[j, i])
                    b = np.float64(dem[j + I1[k], i + J1[k]])
                    c = np.float64(dem[j + I2[k], i + J2[k]])
                    s_val, a_val = _vslope(a, b, c, DXX[ID1[k]], DXX[ID2[k]], DD)
                    sk[k] = s_val
                    angle_k[k] = a_val

                for k in range(1, 9):
                    if sk[k] > smax:
                        smax = sk[k]
                        kd = k

                if kd > 0:
                    ang_res = ANGC[kd] * (PI / 2.0) + ANGF[kd] * angle_k[kd]
                    flow_dir[j, i] = np.float32(ang_res)
                else:
                    q_x[q_tail] = i
                    q_y[q_tail] = j
                    q_tail += 1

                slope[j, i] = np.float32(smax)

    return flow_dir, slope, DXX, DD, q_x, q_y, q_tail

@nb.njit
def _resolve_flats_dinf_nb(dem, flow_dir, DXX, DD, q_x, q_y, q_tail, nodata_val):
    ny, nx = dem.shape
    PI = 3.141592653589793
    MISSINGFLOAT = -1e38

    d1 = np.array([0, 1,  1,  0, -1, -1, -1, 0, 1], dtype=nb.int32)
    d2 = np.array([0, 0, -1, -1, -1,  0,  1, 1, 1], dtype=nb.int32)

    ID1 = np.array([0, 1, 2, 2, 1, 1, 2, 2, 1], dtype=nb.int32)
    ID2 = np.array([0, 2, 1, 1, 2, 2, 1, 1, 2], dtype=nb.int32)
    I1 = np.array([0, 0, -1, -1, 0, 0, 1, 1, 0], dtype=nb.int32)
    I2 = np.array([0, -1, -1, -1, -1, 1, 1, 1, 1], dtype=nb.int32)
    J1 = np.array([0, 1, 0, 0, -1, -1, 0, 0, 1], dtype=nb.int32)
    J2 = np.array([0, 1, 1, -1, -1, -1, -1, 1, 1], dtype=nb.int32)
    ANGC = np.array([0.0, 0.0, 1.0, 1.0, 2.0, 2.0, 3.0, 3.0, 4.0], dtype=nb.float64)
    ANGF = np.array([0.0, 1.0, -1.0, 1.0, -1.0, 1.0, -1.0, 1.0, -1.0], dtype=nb.float64)

    total_num_flat = q_tail
    if total_num_flat == 0:
        return flow_dir

    elevDEM = dem.copy()
    flat_x = q_x[:total_num_flat].copy()
    flat_y = q_y[:total_num_flat].copy()

    while total_num_flat > 0:
        elev2 = np.ones((ny, nx), dtype=nb.int16)
        dn = np.zeros((ny, nx), dtype=nb.int16)
        s = np.zeros((ny, nx), dtype=nb.int16)

        nflat = total_num_flat

        # 1. incfall
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
                z = elevDEM[j, i]
                for k in range(1, 9):
                    in_x = i + d1[k]
                    jn_y = j + d2[k]
                    zn = elevDEM[jn_y, in_x]
                    elev_diff = z - zn
                    fdir_n = flow_dir[jn_y, in_x]

                    if elev_diff >= 0 and fdir_n >= 0.0:
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

        if num_inc_total > 0:
            for idx in range(nflat):
                i = flat_x[idx]
                j = flat_y[idx]

                do_nothing = False
                z = elevDEM[j, i]
                for k in range(1, 9):
                    in_x = i + d1[k]
                    jn_y = j + d2[k]
                    zn = elevDEM[jn_y, in_x]
                    elev_diff = z - zn
                    fdir_n = flow_dir[jn_y, in_x]

                    if elev_diff >= 0 and fdir_n >= 0.0:
                        do_nothing = True
                        break
                    elif elev_diff == 0:
                        e2n = elev2[jn_y, in_x]
                        if e2n >= 0 and e2n < st:
                            do_nothing = True
                            break

                if not do_nothing:
                    flow_dir[j, i] = MISSINGFLOAT

        # 2. incrise
        done = False
        num_inc_old = 0
        while not done:
            num_inc = 0
            for idx in range(nflat):
                i = flat_x[idx]
                j = flat_y[idx]

                z = elevDEM[j, i]
                for k in range(1, 9):
                    in_x = i + d1[k]
                    jn_y = j + d2[k]
                    zn = elevDEM[jn_y, in_x]
                    if z - zn < 0:
                        dn[j, i] = 1
                    if dn[jn_y, in_x] > 0 and s[jn_y, in_x] > 0:
                        dn[j, i] = 1

            for j in range(ny):
                for i in range(nx):
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

        # 3. SET2
        local_still_flat = 0
        new_q_tail = 0

        for idx in range(nflat):
            i = flat_x[idx]
            j = flat_y[idx]

            smax = 0.0
            kd = 0
            sk = np.zeros(9, dtype=nb.float64)
            angle_k = np.zeros(9, dtype=nb.float64)
            diag_out_found = False

            for k in range(1, 9):
                t1 = dn[j + I1[k], i + J1[k]]
                t2 = dn[j + I2[k], i + J2[k]]

                if t1 <= 0 and t2 <= 0:
                    a = np.float64(elevDEM[j, i])
                    b = np.float64(elevDEM[j + I1[k], i + J1[k]])
                    c = np.float64(elevDEM[j + I2[k], i + J2[k]])
                    s_val, a_val = _vslope(a, b, c, DXX[ID1[k]], DXX[ID2[k]], DD)
                    sk[k] = s_val
                    angle_k[k] = a_val
                    if s_val >= 0.0:
                        if b > a:
                            if not diag_out_found:
                                diag_out_found = True
                                kd = k
                        else:
                            kd = k
                            break

                elif t1 <= 0 and t2 > 0:
                    a = np.float64(elevDEM[j, i])
                    b = np.float64(elevDEM[j + I1[k], i + J1[k]])
                    if a >= b:
                        angle_k[k] = 0.0
                        sk[k] = 0.0
                        kd = k
                        break
                    a1 = np.float64(elev2[j, i])
                    c1 = np.float64(elev2[j + I2[k], i + J2[k]])
                    b1 = max(a1, c1)
                    s_val, a_val = _vslope(a1, b1, c1, DXX[ID1[k]], DXX[ID2[k]], DD)
                    sk[k] = s_val
                    angle_k[k] = a_val
                    if s_val > smax:
                        smax = s_val
                        kd = k

                elif t1 > 0 and t2 <= 0:
                    a = np.float64(elevDEM[j, i])
                    c = np.float64(elevDEM[j + I2[k], i + J2[k]])
                    if a >= c:
                        if not diag_out_found:
                            angle_k[k] = np.arctan2(DXX[ID2[k]], DXX[ID1[k]])
                            sk[k] = 0.0
                            kd = k
                            diag_out_found = True
                    else:
                        a1 = np.float64(elev2[j, i])
                        b1 = np.float64(elev2[j + I1[k], i + J1[k]])
                        c1 = max(a1, b1)
                        s_val, a_val = _vslope(a1, b1, c1, DXX[ID1[k]], DXX[ID2[k]], DD)
                        sk[k] = s_val
                        angle_k[k] = a_val
                        if s_val > smax:
                            smax = s_val
                            kd = k

                else:
                    a = np.float64(elev2[j, i])
                    b = np.float64(elev2[j + I1[k], i + J1[k]])
                    c = np.float64(elev2[j + I2[k], i + J2[k]])
                    s_val, a_val = _vslope(a, b, c, DXX[ID1[k]], DXX[ID2[k]], DD)
                    sk[k] = s_val
                    angle_k[k] = a_val
                    if s_val > smax:
                        smax = s_val
                        kd = k

            if flow_dir[j, i] != MISSINGFLOAT:
                flow_dir[j, i] = -1.0

            if kd > 0:
                ang_res = ANGC[kd] * (PI / 2.0) + ANGF[kd] * angle_k[kd]
                if ang_res >= 0.0:
                    flow_dir[j, i] = np.float32(ang_res)

            if flow_dir[j, i] < 0.0 and flow_dir[j, i] != MISSINGFLOAT:
                flat_x[new_q_tail] = i
                flat_y[new_q_tail] = j
                new_q_tail += 1
                local_still_flat += 1

        total_num_flat = local_still_flat
        if total_num_flat > 0:
            for j in range(ny):
                for i in range(nx):
                    elevDEM[j, i] = np.float32(elev2[j, i])

    return flow_dir

def compute_dinf_flowdir(dem: np.ndarray, cell_size: float,
                         nodata: float = -9999.0,
                         log_func=print):
    """
    100% TauDEM-compatible D-infinity flow direction and slope.
    """
    rows, cols = dem.shape
    log_func(f"Computing D-infinity flow direction ({rows}x{cols})...")

    dem_f32 = dem.astype(np.float32)
    ndv_f32 = np.float32(nodata) if nodata is not None else np.float32(-9999.0)

    flow_dir, slope, DXX, DD, q_x, q_y, q_tail = _set_pos_dir_dinf_nb(
        dem_f32, float(cell_size), float(cell_size), ndv_f32
    )

    n_flats = q_tail
    if n_flats > 0:
        log_func(f"  Resolving {n_flats} D-inf flat cells via TauDEM multi-pass...")
        flow_dir = _resolve_flats_dinf_nb(
            dem_f32, flow_dir, DXX, DD, q_x, q_y, q_tail, ndv_f32
        )

    ang_out = flow_dir.copy()
    ang_out[flow_dir < -1e30] = -1.0
    
    slp_out = slope.copy()
    slp_out[flow_dir < -1e30] = nodata

    remaining = int(np.sum((flow_dir < 0.0) & (flow_dir > -1e30)))
    log_func(f"  D-infinity complete. Flat/no-direction cells: {remaining}")

    return ang_out, slp_out
