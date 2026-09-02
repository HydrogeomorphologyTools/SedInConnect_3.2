"""
Compare flat_mask between old D8 code (no OOB) and new code (OOB fix).
Find cells that are in new flat_mask but NOT in old flat_mask.
"""
import numpy as np
import sys
sys.path.insert(0, r'D:\Research\SedInConnect_python\SedInConnect_3.1')
from osgeo import gdal
from sedinconnect.core.native.d8flowdir import D8_OFFSETS, D8_DIST

dtm_path = r'D:\Research\SedInConnect_python\dtmfel.tif'
ds = gdal.Open(dtm_path)
band = ds.GetRasterBand(1)
dem = band.ReadAsArray().astype(np.float32)
nodata = band.GetNoDataValue()
cell_size = ds.GetGeoTransform()[1]
ds = None

rows, cols = dem.shape
nodata_mask = np.isnan(dem)
if nodata is not None and not (isinstance(nodata, float) and np.isnan(nodata)):
    nodata_mask = nodata_mask | (dem.astype(np.float32) == np.float32(nodata))

dem_nan = dem.astype(np.float64).copy()
dem_nan[nodata_mask] = np.nan
pad = np.pad(dem_nan, 1, mode='constant', constant_values=np.nan)
center = pad[1:rows + 1, 1:cols + 1]

# --- OLD code ---
best_slope_old = np.full((rows, cols), -np.inf, dtype=np.float64)
pdir_old = np.zeros((rows, cols), dtype=np.int8)
for d_idx in range(8):
    dr, dc = int(D8_OFFSETS[d_idx, 0]), int(D8_OFFSETS[d_idx, 1])
    dist = D8_DIST[d_idx] * cell_size
    r0 = 1 + dr; c0 = 1 + dc
    neigh = pad[r0:r0 + rows, c0:c0 + cols]
    valid = (~np.isnan(neigh)) & (~nodata_mask)
    slope = (center - neigh) / dist
    update = valid & (slope > best_slope_old)
    best_slope_old = np.where(update, slope, best_slope_old)
    pdir_old = np.where(update, np.int8(d_idx + 1), pdir_old).astype(np.int8)
flat_old = (~nodata_mask) & (best_slope_old <= 0.0)
print(f"OLD flat count: {int(np.sum(flat_old))}")

# --- NEW code (OOB fix) ---
_OOB_SLOPE = 1e-10
best_slope_new = np.full((rows, cols), -np.inf, dtype=np.float64)
pdir_new = np.zeros((rows, cols), dtype=np.int8)
for d_idx in range(8):
    dr, dc = int(D8_OFFSETS[d_idx, 0]), int(D8_OFFSETS[d_idx, 1])
    dist = D8_DIST[d_idx] * cell_size
    r0 = 1 + dr; c0 = 1 + dc
    neigh = pad[r0:r0 + rows, c0:c0 + cols]
    oob = np.zeros((rows, cols), dtype=bool)
    if dr < 0: oob[: -dr, :] = True
    elif dr > 0: oob[rows - dr :, :] = True
    if dc < 0: oob[:, : -dc] = True
    elif dc > 0: oob[:, cols - dc :] = True
    valid_inbounds = (~np.isnan(neigh)) & (~nodata_mask)
    valid_oob = oob & (~nodata_mask)
    slope_cmp = np.where(valid_inbounds, (center - neigh) / dist,
                         np.where(valid_oob, _OOB_SLOPE, -np.inf))
    slope_sd8 = np.where(valid_inbounds, (center - neigh) / dist, 0.0)
    valid = valid_inbounds | valid_oob
    update = valid & (slope_cmp > best_slope_new)
    best_slope_new = np.where(update, slope_cmp, best_slope_new)
    pdir_new = np.where(update, np.int8(d_idx + 1), pdir_new).astype(np.int8)

flat_new = (~nodata_mask) & (best_slope_new <= 0.0)
print(f"NEW flat count: {int(np.sum(flat_new))}")

# Find cells that entered flat_mask in new but not old
new_only = flat_new & ~flat_old
old_only = flat_old & ~flat_new
print(f"New only (in new flat but not old): {int(np.sum(new_only))}")
print(f"Old only (in old flat but not new): {int(np.sum(old_only))}")

# Print info about cells in new_only
new_only_rows, new_only_cols = np.where(new_only)
print(f"\nSample of cells NEW to flat_mask (r, c, old_bs, new_bs, old_pdir, new_pdir):")
for i in range(min(20, len(new_only_rows))):
    r, c = int(new_only_rows[i]), int(new_only_cols[i])
    print(f"  ({r:4d},{c:4d}) old_bs={best_slope_old[r,c]:.6f} new_bs={best_slope_new[r,c]:.6f} old_pdir={pdir_old[r,c]} new_pdir={pdir_new[r,c]}")
