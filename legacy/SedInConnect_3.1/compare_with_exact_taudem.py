"""
compare_with_exact_taudem.py
Detailed comparison of SedInConnect 3.1 native routines against exact TauDEM ground truth on dtmfel.tif.
"""
import sys
import numpy as np
from pathlib import Path
from osgeo import gdal

sys.path.insert(0, str(Path(__file__).parent))

from sedinconnect.core.native.d8flowdir import compute_d8_flowdir
from sedinconnect.core.native.dinfflowdir import compute_dinf_flowdir
from sedinconnect.core.native.areadinf import accumulate_dinf, build_dinf_topology

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

def compare(name, ref, native, ref_nodata=None, native_nodata=None, tol=1e-4, is_angle=False):
    print(f"\n{'='*70}")
    print(f"  BENCHMARK vs TauDEM Ground Truth: {name}")
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

    r_vals = ref[both].astype(np.float64)
    n_vals = native[both].astype(np.float64)

    if is_angle:
        # Wrap angle differences in [0, 2pi)
        diff = np.abs(r_vals - n_vals)
        diff = np.minimum(diff, 2.0 * np.pi - diff)
    else:
        diff = np.abs(r_vals - n_vals)

    max_d = float(diff.max())
    mean_d = float(diff.mean())
    exact = float((diff == 0).mean()) * 100
    within_tol = float((diff <= tol).mean()) * 100
    within_1e2 = float((diff <= 1e-2).mean()) * 100
    within_1e1 = float((diff <= 0.1).mean()) * 100

    print(f"  Max abs diff:       {max_d:.6f}")
    print(f"  Mean abs diff:      {mean_d:.6f}")
    print(f"  Exact match (0):    {exact:.6f}% ({int((diff == 0).sum()):,} / {both_count:,})")
    print(f"  Within tol ({tol}): {within_tol:.6f}% ({int((diff <= tol).sum()):,} / {both_count:,})")
    print(f"  Within 0.01:        {within_1e2:.6f}%")
    print(f"  Within 0.1:         {within_1e1:.6f}%")
    sys.stdout.flush()
    return diff, both, ref_valid, nat_valid

def main():
    print("Loading DEM (dtmfel.tif)...", flush=True)
    dem_arr, dem_nd, cell_size = load_raster(BASE / "dtmfel.tif")
    dem = dem_arr.astype(np.float32)
    ndv_val = float(dem_nd) if dem_nd is not None else -9999.0

    # 1. D8 FlowDir & Slope
    print("\n--- 1. D8 FlowDir & Slope ---", flush=True)
    p_ref, p_ref_nd, _ = load_raster(REF / "dtm_p.tif")
    sd8_ref, sd8_ref_nd, _ = load_raster(REF / "dtm_sd8.tif")
    
    pdir_nat, sd8_nat = compute_d8_flowdir(dem, cell_size, nodata=ndv_val, log_func=print)
    
    compare("D8 Flow Direction (dtm_p.tif)", p_ref, pdir_nat, ref_nodata=p_ref_nd, native_nodata=-1.0, tol=0.5)
    compare("D8 Slope (dtm_sd8.tif)", sd8_ref, sd8_nat, ref_nodata=sd8_ref_nd, native_nodata=ndv_val, tol=1e-4)

    # 2. D-infinity FlowDir & Slope
    print("\n--- 2. D-infinity FlowDir & Slope ---", flush=True)
    ang_ref, ang_ref_nd, _ = load_raster(REF / "dtm_ang.tif")
    slp_ref, slp_ref_nd, _ = load_raster(REF / "dtm_slp.tif")
    
    ang_nat, slp_nat = compute_dinf_flowdir(dem, cell_size, nodata=ndv_val, log_func=print)
    
    compare("D-inf Angle (dtm_ang.tif)", ang_ref, ang_nat, ref_nodata=ang_ref_nd, native_nodata=-1.0, tol=1e-3, is_angle=True)
    compare("D-inf Slope (dtm_slp.tif)", slp_ref, slp_nat, ref_nodata=slp_ref_nd, native_nodata=ndv_val, tol=1e-4)

    # 3. D-infinity Area Accumulation (SCA)
    print("\n--- 3. D-infinity SCA (using TauDEM ang vs native ang) ---", flush=True)
    sca_ref, sca_ref_nd, _ = load_raster(REF / "dtm_sca.tif")
    
    # 3a: Accumulate on TauDEM ang to isolate areadinf.py from dinfflowdir.py
    print("Testing areadinf.py on EXACT TauDEM angle input...")
    ang_ref_clean = ang_ref.copy()
    ang_ref_clean[ang_ref == ang_ref_nd] = -1.0
    ang_ref_clean[ang_ref_clean < -1e10] = -1.0
    
    topo_ref = build_dinf_topology(ang_ref_clean, nodata_ang=-1.0, dem=dem, log_func=print)
    sca_from_taudem_ang = accumulate_dinf(ang_ref_clean, cell_size, nodata_ang=-1.0, topology=topo_ref, log_func=print)
    
    compare("AreaDinf SCA (on TauDEM ang input)", sca_ref, sca_from_taudem_ang, ref_nodata=sca_ref_nd, native_nodata=-9999.0, tol=1e-2)

    # 3b: Accumulate on Native ang (full native pipeline)
    print("\nTesting areadinf.py on NATIVE angle input...")
    topo_nat = build_dinf_topology(ang_nat, nodata_ang=-1.0, dem=dem, log_func=print)
    sca_from_nat_ang = accumulate_dinf(ang_nat, cell_size, nodata_ang=-1.0, topology=topo_nat, log_func=print)
    
    compare("AreaDinf SCA (on Native ang input)", sca_ref, sca_from_nat_ang, ref_nodata=sca_ref_nd, native_nodata=-9999.0, tol=1e-2)

if __name__ == "__main__":
    main()
