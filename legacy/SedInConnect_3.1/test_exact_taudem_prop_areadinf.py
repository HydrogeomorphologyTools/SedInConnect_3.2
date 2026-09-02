"""
test_exact_taudem_prop_areadinf.py
Exact port of TauDEM C++ prop and areadinf algorithm.
"""
import sys
import numpy as np
from pathlib import Path
from osgeo import gdal
import numba as nb

BASE = Path(r"D:\Research\SedInConnect_python")
REF = BASE / "taudem_ref"

def load_raster(path):
    ds = gdal.Open(str(path))
    b = ds.GetRasterBand(1)
    arr = b.ReadAsArray()
    nd = b.GetNoDataValue()
    gt = ds.GetGeoTransform()
    cell_size = abs(gt[1])
    return arr, nd, cell_size

@nb.njit
def prop_taudem(a, k, dx1, dy1):
    # k in 1..8 (TauDEM 1-based indexing)
    # d1 = {0, 1, 1, 0, -1, -1, -1, 0, 1}
    # d2 = {0, 0, -1, -1, -1, 0, 1, 1, 1}
    PI = 3.141592653589793
    a0 = -np.arctan2(dy1, dx1)
    aref = np.array([
        a0,
        0.0,
        -a0,
        0.5 * PI,
        PI - (-a0),
        PI,
        PI + (-a0),
        1.5 * PI,
        2.0 * PI - (-a0),
        2.0 * PI
    ], dtype=nb.float64)

    if k <= 0:
        k = k + 8
    
    if k == 1 and a > PI:
        a = a - 2.0 * PI

    p = 0.0
    if a > aref[k - 1] and a < aref[k + 1]:
        if a > aref[k]:
            p = (aref[k + 1] - a) / (aref[k + 1] - aref[k])
        else:
            p = (a - aref[k - 1]) / (aref[k] - aref[k - 1])

    if p < 1e-5:
        return -1.0
    else:
        return p

@nb.njit
def accumulate_taudem_exact(ang_grid, nodata_ang, dx1, dy1, weight_grid=None):
    ny, nx = ang_grid.shape
    d1 = np.array([0, 1,  1,  0, -1, -1, -1, 0, 1], dtype=nb.int32)
    d2 = np.array([0, 0, -1, -1, -1,  0,  1, 1, 1], dtype=nb.int32)

    # 1. Initialize neighbor count
    neighbor = np.full((ny, nx), -32768, dtype=nb.int16)
    areadinf = np.full((ny, nx), -1.0, dtype=nb.float32)

    # Queue
    max_q = nx * ny
    q_x = np.empty(max_q, dtype=nb.int32)
    q_y = np.empty(max_q, dtype=nb.int32)
    head = 0
    tail = 0

    for j in range(ny):
        for i in range(nx):
            a_val = ang_grid[j, i]
            # Valid flow direction if not nodata and >= 0
            if not (a_val <= nodata_ang or np.isnan(a_val) or a_val < 0.0):
                neighbor[j, i] = 0
                for k in range(1, 9):
                    in_x = i + d1[k]
                    jn_y = j + d2[k]
                    if 0 <= in_x < nx and 0 <= jn_y < ny:
                        a_n = ang_grid[jn_y, in_x]
                        if not (a_n <= nodata_ang or np.isnan(a_n) or a_n < 0.0):
                            p = prop_taudem(a_n, (k + 4) % 8, dx1, dy1)
                            if p > 0.0:
                                neighbor[j, i] += 1
                
                if neighbor[j, i] == 0:
                    q_x[tail] = i
                    q_y[tail] = j
                    tail += 1

    # 2. Main propagation loop
    processed = 0
    while head < tail:
        i = q_x[head]
        j = q_y[head]
        head += 1
        processed += 1

        # FLOW ALGEBRA EXPRESSION EVALUATION
        areares = 0.0
        for k in range(1, 9):
            in_x = i + d1[k]
            jn_y = j + d2[k]
            if 0 <= in_x < nx and 0 <= jn_y < ny:
                a_n = ang_grid[jn_y, in_x]
                if not (a_n <= nodata_ang or np.isnan(a_n) or a_n < 0.0):
                    p = prop_taudem(a_n, (k + 4) % 8, dx1, dy1)
                    if p > 0.0:
                        if areadinf[jn_y, in_x] >= 0.0:
                            areares += p * areadinf[jn_y, in_x]

        # Local inputs
        if weight_grid is not None:
            areares += weight_grid[j, i]
        else:
            areares += dx1

        areadinf[j, i] = areares

        # Decrement neighbor dependence of downslope cell
        a_val = ang_grid[j, i]
        for k in range(1, 9):
            p = prop_taudem(a_val, k, dx1, dy1)
            if p > 0.0:
                in_x = i + d1[k]
                jn_y = j + d2[k]
                if 0 <= in_x < nx and 0 <= jn_y < ny:
                    neighbor[jn_y, in_x] -= 1
                    if neighbor[jn_y, in_x] == 0:
                        q_x[tail] = in_x
                        q_y[tail] = jn_y
                        tail += 1

    return areadinf, processed, neighbor

def main():
    print("Loading TauDEM ground truth ang and sca...", flush=True)
    ang_ref, ang_ref_nd, cell_size = load_raster(REF / "dtm_ang.tif")
    sca_ref, sca_ref_nd, _ = load_raster(REF / "dtm_sca.tif")
    
    print("Running exact TauDEM AreaDinf logic...", flush=True)
    sca_calc, processed, neighbor = accumulate_taudem_exact(
        ang_ref, -1.0, float(cell_size), float(cell_size)
    )

    print(f"Processed: {processed:,} cells. Remaining neighbor count > 0: {(neighbor > 0).sum():,}")

    ref_valid = ~((sca_ref == sca_ref_nd) | np.isnan(sca_ref) | (sca_ref < -1e10))
    nat_valid = sca_calc >= 0.0
    both = ref_valid & nat_valid

    r_vals = sca_ref[both].astype(np.float64)
    n_vals = sca_calc[both].astype(np.float64)
    diff = np.abs(r_vals - n_vals)

    print(f"\n{'='*70}")
    print(f"  EXACT TauDEM AreaDinf vs dtm_sca.tif")
    print(f"{'='*70}")
    print(f"  Ref valid cells:    {int(ref_valid.sum()):,}")
    print(f"  Native valid cells: {int(nat_valid.sum()):,}")
    print(f"  Both valid cells:   {int(both.sum()):,}")
    print(f"  Max abs diff:       {diff.max():.6f}")
    print(f"  Mean abs diff:      {diff.mean():.6f}")
    print(f"  Exact match (0):    {100*(diff==0).mean():.6f}% ({int((diff==0).sum()):,} / {int(both.sum()):,})")
    print(f"  Within 0.0001:      {100*(diff<=0.0001).mean():.6f}%")
    print(f"  Within 0.001:       {100*(diff<=0.001).mean():.6f}%")
    print(f"  Within 0.01:        {100*(diff<=0.01).mean():.6f}%")

if __name__ == "__main__":
    main()
