"""
inspect_rasters.py
Inspect dimensions, CRS, nodata values, valid cell counts of all reference rasters.
"""
import sys
from pathlib import Path
from osgeo import gdal
import numpy as np

BASE = Path(r"D:\Research\SedInConnect_python")

files = [
    "dtmfel.tif",
    "sinked_dtm_p.tif",
    "sinked_dtm_sd8.tif",
    "sinked_dtm_ang.tif",
    "sinked_dtm_slp.tif",
    "sinked_dtm_sca.tif",
    "ref_sca_taudem.tif",
    "ic_test_30.tif",
    "ic_test_31_vfix.tif",
    "target.shp"
]

print(f"{'Raster/File':<25} | {'Shape (Y, X)':<15} | {'GeoTransform':<40} | {'NoData':<15} | {'Valid Cells':<12}")
print("-" * 115)

for fn in files:
    fp = BASE / fn
    if not fp.exists():
        print(f"{fn:<25} | NOT FOUND")
        continue
    if fn.endswith(".shp"):
        print(f"{fn:<25} | Vector Shapefile exists")
        continue

    ds = gdal.Open(str(fp))
    b = ds.GetRasterBand(1)
    arr = b.ReadAsArray()
    nd = b.GetNoDataValue()
    gt = ds.GetGeoTransform()
    gt_str = f"({gt[0]:.1f}, {gt[1]:.1f}, ..., {gt[3]:.1f}, {gt[5]:.1f})"
    
    if nd is not None:
        valid = ~((arr == nd) | np.isnan(arr) | (arr < -1e10))
    else:
        valid = ~np.isnan(arr)
    v_count = int(valid.sum())
    
    print(f"{fn:<25} | {str(arr.shape):<15} | {gt_str:<40} | {str(nd):<15} | {v_count:<12,}")

