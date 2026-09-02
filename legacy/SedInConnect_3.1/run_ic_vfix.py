import numpy as np, sys
sys.path.insert(0, r'D:\Research\SedInConnect_python\SedInConnect_3.1')
from sedinconnect.core.processor import ConnectivityProcessor
from pathlib import Path
from osgeo import gdal

print("Starting IC pipeline test...")
p = ConnectivityProcessor(log_func=print)
p.compute_connectivity_targets(
    dtm_path=Path(r'D:\Research\SedInConnect_python\dtmfel.tif'),
    cell_size=30.0,
    target_path=Path(r'D:\Research\SedInConnect_python\target.shp'),
    weight_path=Path(r'D:\Research\SedInConnect_python\w.tif'),
    output_path=Path(r'D:\Research\SedInConnect_python\ic_test_31_vfix.tif'),
    save_components=False,
    sink_flag=0,
)

# Compare with reference
ref_path = r'D:\Research\SedInConnect_python\ic_test_30.tif'
nat_path = r'D:\Research\SedInConnect_python\ic_test_31_vfix.tif'

ds_ref = gdal.Open(ref_path)
ref = ds_ref.GetRasterBand(1).ReadAsArray().astype(np.float32)
ndv_ref = ds_ref.GetRasterBand(1).GetNoDataValue(); ds_ref = None
ds_nat = gdal.Open(nat_path)
nat = ds_nat.GetRasterBand(1).ReadAsArray().astype(np.float32)
ndv_nat = ds_nat.GetRasterBand(1).GetNoDataValue(); ds_nat = None

if ndv_ref is not None: ref[ref == ndv_ref] = np.nan
if ndv_nat is not None: nat[nat == ndv_nat] = np.nan

valid_ref = ~np.isnan(ref)
valid_nat = ~np.isnan(nat)
valid_both = valid_ref & valid_nat

print(f"\n=== IC Comparison ===")
print(f"Valid ref:  {int(np.sum(valid_ref))}")
print(f"Valid nat:  {int(np.sum(valid_nat))}")
print(f"Valid both: {int(np.sum(valid_both))}")
print(f"Missing (valid ref but not nat): {int(np.sum(valid_ref & ~valid_nat))}")
print(f"Extra (valid nat but not ref):   {int(np.sum(valid_nat & ~valid_ref))}")

if int(np.sum(valid_both)) > 0:
    diff = np.abs(ref[valid_both] - nat[valid_both])
    print(f"Max diff: {diff.max():.6f}")
    print(f"Mean diff: {diff.mean():.6f}")
    print(f"Within 0.001: {100*np.mean(diff < 0.001):.3f}%")
    print(f"Within 0.01:  {100*np.mean(diff < 0.01):.3f}%")
