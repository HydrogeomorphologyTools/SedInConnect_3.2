"""
test_d8_exact.py
"""
import sys
import numpy as np
from pathlib import Path
from osgeo import gdal

sys.path.insert(0, str(Path(__file__).parent))
from sedinconnect.core.native.d8flowdir import compute_d8_flowdir

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
    p_ref, p_ref_nd, _ = load_raster(REF / "dtm_p.tif")
    sd8_ref, sd8_ref_nd, _ = load_raster(REF / "dtm_sd8.tif")

    pdir_nat, sd8_nat = compute_d8_flowdir(dem_arr, cell_size, nodata=dem_nd)

    ref_valid = ~((p_ref == p_ref_nd) | np.isnan(p_ref) | (p_ref < -1e10))
    nat_valid = pdir_nat > 0
    both = ref_valid & nat_valid

    diff_p = np.abs(p_ref[both] - pdir_nat[both])
    print(f"\n{'='*70}")
    print(f"  D8 FlowDir EXACT MATCH RESULTS")
    print(f"{'='*70}")
    print(f"  Ref valid cells:    {int(ref_valid.sum()):,}")
    print(f"  Native valid cells: {int(nat_valid.sum()):,}")
    print(f"  Both valid cells:   {int(both.sum()):,}")
    print(f"  Exact match:        {100*(diff_p == 0).mean():.6f}% ({int((diff_p == 0).sum()):,} / {int(both.sum()):,})")
    print(f"  Diffs > 0:          {int((diff_p > 0).sum()):,}")

    diff_s = np.abs(sd8_ref[both] - sd8_nat[both])
    print(f"\n{'='*70}")
    print(f"  D8 Slope EXACT MATCH RESULTS")
    print(f"{'='*70}")
    print(f"  Max abs diff:       {diff_s.max():.6f}")
    print(f"  Mean abs diff:      {diff_s.mean():.6f}")
    print(f"  Within 1e-4:        {100*(diff_s <= 1e-4).mean():.6f}%")

if __name__ == "__main__":
    main()
