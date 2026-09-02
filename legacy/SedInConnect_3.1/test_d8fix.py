import numpy as np
import sys
sys.path.insert(0, r'D:\Research\SedInConnect_python\SedInConnect_3.1')
from osgeo import gdal
from sedinconnect.core.native.d8flowdir import compute_d8_flowdir

dtm_path = r'D:\Research\SedInConnect_python\dtmfel.tif'
ds = gdal.Open(dtm_path)
band = ds.GetRasterBand(1)
dem = band.ReadAsArray().astype(np.float32)
nodata = band.GetNoDataValue()
cell_size = ds.GetGeoTransform()[1]
ds = None

pdir, sd8 = compute_d8_flowdir(dem, cell_size, nodata)
nodata_mask = (pdir == -1)
flat_mask = (pdir == 0) & (~nodata_mask)
print(f'pdir=0 count: {int(np.sum(flat_mask))}')
print(f'pdir valid (1-8): {int(np.sum((pdir >= 1) & (pdir <= 8)))}')
print(f'pdir=-1 (nodata): {int(np.sum(nodata_mask))}')
