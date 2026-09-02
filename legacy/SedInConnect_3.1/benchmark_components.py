"""
benchmark_components.py
Test each component of SedInConnect 3.1 against TauDEM reference datasets.
"""
import sys
import os
import numpy as np
from pathlib import Path
from osgeo import gdal

# Add SedInConnect 3.1 to path
sys.path.insert(0, str(Path(__file__).parent))

from sedinconnect.core.native.d8flowdir import compute_d8_flowdir
from sedinconnect.core.native.dinfflowdir import compute_dinf_flowdir
from sedinconnect.core.native.areadinf import accumulate_dinf, build_dinf_topology

BASE = Path(r"D:\Research\SedInConnect_python")

def load_raster(path):
    ds = gdal.Open(str(path))
    if ds is None:
        raise FileNotFoundError(f"Could not open {path}")
    b = ds.GetRasterBand(1)
    arr = b.ReadAsArray()
    nd = b.GetNoDataValue()
    gt = ds.GetGeoTransform()
    cell_size = abs(gt[1])
    return arr, nd, cell_size

def compare(name, ref, native, ref_nodata=None, native_nodata=None, tol=1e-4):
    print(f"\n{'='*70}")
    print(f"  BENCHMARK: {name}")
    print(f"{'='*70}")

    if ref_nodata is not None:
        ref_valid = ~((ref == ref_nodata) | np.isnan(ref) | (ref < -1e10))
    else:
        ref_valid = ~np.isnan(ref)

    if native_nodata is not None:
        nat_valid = ~((native == native_nodata) | np.isnan(native) | (native < -1e10))
    else:
        nat_valid = ~np.isnan(native)

    both = ref_valid & nat_valid
    ref_count = int(ref_valid.sum())
    nat_count = int(nat_valid.sum())
    both_count = int(both.sum())

    print(f"  Ref valid cells:    {ref_count:,}")
    print(f"  Native valid cells: {nat_count:,}")
    print(f"  Both valid cells:   {both_count:,}")
    print(f"  Missing (in ref not nat): {int((ref_valid & ~nat_valid).sum()):,}")
    print(f"  Extra (in nat not ref):   {int((nat_valid & ~ref_valid).sum()):,}")

    if both_count == 0:
        print("  ERROR: No cells to compare!")
        return

    diff = np.abs(ref[both].astype(np.float64) - native[both].astype(np.float64))
    max_d = float(diff.max())
    mean_d = float(diff.mean())
    exact = float((diff == 0).mean()) * 100
    within_tol = float((diff <= tol).mean()) * 100
    within_1e2 = float((diff <= 1e-2).mean()) * 100
    within_1e1 = float((diff <= 0.1).mean()) * 100

    print(f"  Max abs diff:     {max_d:.6f}")
    print(f"  Mean abs diff:    {mean_d:.6f}")
    print(f"  Exact match (0):  {exact:.4f}% ({int((diff == 0).sum()):,} / {both_count:,})")
    print(f"  Within tol ({tol}): {within_tol:.4f}% ({int((diff <= tol).sum()):,} / {both_count:,})")
    print(f"  Within 0.01:      {within_1e2:.4f}%")
    print(f"  Within 0.1:       {within_1e1:.4f}%")
    sys.stdout.flush()

def main():
    print("Loading DEM (dtmfel.tif)...", flush=True)
    dem_arr, dem_nd, cell_size = load_raster(BASE / "dtmfel.tif")
    dem = dem_arr.astype(np.float32)
    ndv_val = float(dem_nd) if dem_nd is not None else -9999.0

    # 1. D8 FlowDir & Slope
    print("\n--- Testing D8 Flow Direction & Slope ---", flush=True)
    pdir_nat, sd8_nat = compute_d8_flowdir(dem, cell_size, nodata=ndv_val, log_func=print)
    p_ref, p_ref_nd, _ = load_raster(BASE / "sinked_dtm_p.tif")
    sd8_ref, sd8_ref_nd, _ = load_raster(BASE / "sinked_dtm_sd8.tif")

    compare("D8 Flow Direction (sinked_dtm_p.tif)", p_ref, pdir_nat, ref_nodata=p_ref_nd, native_nodata=-1.0, tol=0.5)
    compare("D8 Slope (sinked_dtm_sd8.tif)", sd8_ref, sd8_nat, ref_nodata=sd8_ref_nd, native_nodata=ndv_val, tol=1e-4)

    # 2. D-infinity FlowDir & Slope
    print("\n--- Testing D-infinity Flow Direction & Slope ---", flush=True)
    ang_nat, slp_nat = compute_dinf_flowdir(dem, cell_size, nodata=ndv_val, log_func=print)
    ang_ref, ang_ref_nd, _ = load_raster(BASE / "sinked_dtm_ang.tif")
    slp_ref, slp_ref_nd, _ = load_raster(BASE / "sinked_dtm_slp.tif")

    compare("D-inf Angle (sinked_dtm_ang.tif)", ang_ref, ang_nat, ref_nodata=ang_ref_nd, native_nodata=-1.0, tol=1e-3)
    compare("D-inf Slope (sinked_dtm_slp.tif)", slp_ref, slp_nat, ref_nodata=slp_ref_nd, native_nodata=ndv_val, tol=1e-4)

if __name__ == "__main__":
    main()
