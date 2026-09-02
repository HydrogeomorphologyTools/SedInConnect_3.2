"""
test_full_pipeline_31.py
Run full SedInConnect 3.1 target connectivity with correct cell_size=2.5 and compare with ic_test_30.tif.
"""
import sys
import numpy as np
from pathlib import Path
from osgeo import gdal

sys.path.insert(0, str(Path(__file__).parent))
from sedinconnect.core.processor import ConnectivityProcessor

BASE = Path(r"D:\Research\SedInConnect_python")

def load_raster(path):
    ds = gdal.Open(str(path))
    b = ds.GetRasterBand(1)
    arr = b.ReadAsArray()
    nd = b.GetNoDataValue()
    gt = ds.GetGeoTransform()
    cell_size = abs(gt[1])
    return arr, nd, cell_size

def main():
    dtm = BASE / "dtmfel.tif"
    target = BASE / "target.shp"
    weight = BASE / "w.tif"
    out_31 = BASE / "ic_test_31_final.tif"
    ref_30 = BASE / "ic_test_30.tif"

    print("--- Running Full SedInConnect 3.1 Pipeline (cell_size=2.5) ---", flush=True)
    p = ConnectivityProcessor(log_func=print)
    p.compute_connectivity_targets(
        dtm_path=dtm,
        cell_size=2.5,
        target_path=target,
        weight_path=weight,
        output_path=out_31,
        save_components=True,
        sink_flag=0
    )

    print("\n--- Comparing ic_test_31_final.tif vs ic_test_30.tif ---", flush=True)
    ic_ref, nd_ref, _ = load_raster(ref_30)
    ic_31, nd_31, _ = load_raster(out_31)

    ref_valid = ~((ic_ref == nd_ref) | np.isnan(ic_ref) | (ic_ref < -1e10))
    nat_valid = ~((ic_31 == nd_31) | np.isnan(ic_31) | (ic_31 < -1e10))
    both = ref_valid & nat_valid

    r_vals = ic_ref[both].astype(np.float64)
    n_vals = ic_31[both].astype(np.float64)
    diff = np.abs(r_vals - n_vals)

    print(f"{'='*70}")
    print(f"  FULL IC CONNECTIVITY BENCHMARK (3.1 Native vs 3.0 TauDEM)")
    print(f"{'='*70}")
    print(f"  Ref valid cells (3.0):   {int(ref_valid.sum()):,}")
    print(f"  Native valid cells (3.1): {int(nat_valid.sum()):,}")
    print(f"  Both valid cells:        {int(both.sum()):,}")
    print(f"  Missing cells in 3.1:    {int((ref_valid & ~nat_valid).sum()):,}")
    print(f"  Extra cells in 3.1:      {int((nat_valid & ~ref_valid).sum()):,}")
    print(f"  Max abs diff:            {diff.max():.6f}")
    print(f"  Mean abs diff:           {diff.mean():.6f}")
    print(f"  Exact match (0 diff):    {100*(diff == 0).mean():.6f}% ({int((diff == 0).sum()):,} / {int(both.sum()):,})")
    print(f"  Within 0.0001:           {100*(diff <= 0.0001).mean():.6f}%")
    print(f"  Within 0.001:            {100*(diff <= 0.001).mean():.6f}%")
    print(f"  Within 0.01:             {100*(diff <= 0.01).mean():.6f}%")
    print(f"  Within 0.1:              {100*(diff <= 0.1).mean():.6f}%")

if __name__ == "__main__":
    main()
