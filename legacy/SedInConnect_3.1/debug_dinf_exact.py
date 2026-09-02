"""
debug_dinf_exact.py
Find and debug any cell difference between native D-inf and TauDEM dtm_ang.tif.
"""
import sys
import numpy as np
from pathlib import Path
from osgeo import gdal

sys.path.insert(0, str(Path(__file__).parent))
from sedinconnect.core.native.dinfflowdir import compute_dinf_flowdir

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

def main():
    dem_arr, dem_nd, cell_size = load_raster(BASE / "dtmfel.tif")
    ang_ref, ang_ref_nd, _ = load_raster(REF / "dtm_ang.tif")

    ang_nat, slp_nat = compute_dinf_flowdir(dem_arr, cell_size, nodata=dem_nd)

    ref_valid = ~((ang_ref == ang_ref_nd) | np.isnan(ang_ref) | (ang_ref < -1e10) | (ang_ref < 0))
    nat_valid = ang_nat >= 0
    both = ref_valid & nat_valid

    r_vals = ang_ref[both].astype(np.float64)
    n_vals = ang_nat[both].astype(np.float64)
    diff = np.abs(r_vals - n_vals)
    diff = np.minimum(diff, 2.0 * np.pi - diff)

    diff_idx = np.where(diff > 0.0001)
    diff_count = len(diff_idx[0])

    print(f"\n{'='*70}")
    print(f"  D-INF ANGLE COMPARISON")
    print(f"{'='*70}")
    print(f"  Ref valid: {int(ref_valid.sum()):,}  Nat valid: {int(nat_valid.sum()):,}")
    print(f"  Exact match (diff == 0): {100*(diff == 0).mean():.6f}% ({int((diff == 0).sum()):,} / {int(both.sum()):,})")
    print(f"  Within 0.001 rad:        {100*(diff <= 0.001).mean():.6f}%")
    print(f"  Differences > 0.0001 rad: {diff_count}")

    if diff_count > 0:
        both_rows, both_cols = np.where(both)
        for idx in range(min(10, diff_count)):
            i_pos = diff_idx[0][idx]
            r = both_rows[i_pos]
            c = both_cols[i_pos]
            print(f"  Cell (row={r}, col={c}): ref={ang_ref[r, c]:.6f}, nat={ang_nat[r, c]:.6f}, diff={diff[i_pos]:.6f}")

if __name__ == "__main__":
    main()
