"""
test_dag_areadinf.py
Test topological in-degree DAG accumulation for AreaDinf on TauDEM angle grid.
"""
import sys
import numpy as np
from pathlib import Path
from osgeo import gdal
from collections import deque
import numba as nb

sys.path.insert(0, str(Path(__file__).parent))
from sedinconnect.core.native.areadinf import _compute_receivers_vectorised

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
def accumulate_dag_numba(rows, cols, cell_size, 
                         e1_row, e1_col, e2_row, e2_col,
                         p1, p2, valid_e1, valid_e2, has_flow,
                         nodata_mask, weight=None):
    # 1. Compute in-degrees
    indegree = np.zeros((rows, cols), dtype=np.int32)
    for r in range(rows):
        for c in range(cols):
            if has_flow[r, c]:
                if valid_e1[r, c]:
                    indegree[e1_row[r, c], e1_col[r, c]] += 1
                if valid_e2[r, c]:
                    indegree[e2_row[r, c], e2_col[r, c]] += 1

    # 2. Initialize SCA
    sca = np.zeros((rows, cols), dtype=np.float64)
    for r in range(rows):
        for c in range(cols):
            if not nodata_mask[r, c]:
                if weight is not None:
                    sca[r, c] = weight[r, c]
                else:
                    sca[r, c] = cell_size

    # 3. Queue for cells with in-degree 0
    # Preallocate queue
    max_q = rows * cols
    q_r = np.empty(max_q, dtype=np.int32)
    q_c = np.empty(max_q, dtype=np.int32)
    head = 0
    tail = 0

    for r in range(rows):
        for c in range(cols):
            if not nodata_mask[r, c] and indegree[r, c] == 0:
                q_r[tail] = r
                q_c[tail] = c
                tail += 1

    # 4. Topological traversal
    count = 0
    while head < tail:
        r = q_r[head]
        c = q_c[head]
        head += 1
        count += 1

        val = sca[r, c]
        if has_flow[r, c]:
            if valid_e1[r, c]:
                nr1 = e1_row[r, c]
                nc1 = e1_col[r, c]
                sca[nr1, nc1] += val * p1[r, c]
                indegree[nr1, nc1] -= 1
                if indegree[nr1, nc1] == 0:
                    q_r[tail] = nr1
                    q_c[tail] = nc1
                    tail += 1

            if valid_e2[r, c]:
                nr2 = e2_row[r, c]
                nc2 = e2_col[r, c]
                sca[nr2, nc2] += val * p2[r, c]
                indegree[nr2, nc2] -= 1
                if indegree[nr2, nc2] == 0:
                    q_r[tail] = nr2
                    q_c[tail] = nc2
                    tail += 1

    return sca, count, indegree

def main():
    print("Loading TauDEM ground truth ang and sca...", flush=True)
    ang_ref, ang_ref_nd, cell_size = load_raster(REF / "dtm_ang.tif")
    sca_ref, sca_ref_nd, _ = load_raster(REF / "dtm_sca.tif")
    
    rows, cols = ang_ref.shape
    nodata_mask = (ang_ref == ang_ref_nd) | np.isnan(ang_ref) | (ang_ref < -1e10) | (ang_ref < 0)
    
    (e1_row, e1_col, e2_row, e2_col, p2,
     valid_e1, valid_e2, has_flow) = _compute_receivers_vectorised(
        ang_ref, nodata_mask, rows, cols)
    p1 = 1.0 - p2

    print("Running DAG topological accumulation with numba...", flush=True)
    sca_dag, processed, remaining_indegree = accumulate_dag_numba(
        rows, cols, float(cell_size),
        e1_row, e1_col, e2_row, e2_col,
        p1, p2, valid_e1, valid_e2, has_flow,
        nodata_mask
    )

    print(f"Processed: {processed:,} cells. Remaining in-degree > 0: {(remaining_indegree > 0).sum():,}")

    ref_valid = ~((sca_ref == sca_ref_nd) | np.isnan(sca_ref) | (sca_ref < -1e10))
    nat_valid = ~nodata_mask
    both = ref_valid & nat_valid

    r_vals = sca_ref[both].astype(np.float64)
    n_vals = sca_dag[both].astype(np.float64)
    diff = np.abs(r_vals - n_vals)

    print(f"\n{'='*70}")
    print(f"  DAG ACCUMULATION vs TauDEM dtm_sca.tif")
    print(f"{'='*70}")
    print(f"  Max abs diff:       {diff.max():.6f}")
    print(f"  Mean abs diff:      {diff.mean():.6f}")
    print(f"  Exact match (0):    {100*(diff==0).mean():.6f}% ({int((diff==0).sum()):,} / {int(both.sum()):,})")
    print(f"  Within 0.001:       {100*(diff<=0.001).mean():.6f}%")
    print(f"  Within 0.01:        {100*(diff<=0.01).mean():.6f}%")
    print(f"  Within 0.1:         {100*(diff<=0.1).mean():.6f}%")

if __name__ == "__main__":
    main()
