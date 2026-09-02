"""
Diagnostic: understand why 964 flat cells remain unresolved.
For each pdir=0 cell after setFlow2, report neighbor info.
"""
import numpy as np
import sys
sys.path.insert(0, r'D:\Research\SedInConnect_python\SedInConnect_3.1')
from osgeo import gdal
from collections import deque

# ---- replicate internals from d8flowdir.py ----
from sedinconnect.core.native.d8flowdir import (
    D8_OFFSETS, D8_DIST, _FACT, _SETFLOW2_ORDER, _bfs_distance
)

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

pdir = np.zeros((rows, cols), dtype=np.int8)
best_slope = np.full((rows, cols), -np.inf, dtype=np.float64)
center = pad[1:rows + 1, 1:cols + 1]

for d_idx in range(8):
    dr, dc = D8_OFFSETS[d_idx]
    dist = D8_DIST[d_idx] * cell_size
    r0 = 1 + dr; c0 = 1 + dc
    neigh = pad[r0:r0 + rows, c0:c0 + cols]
    valid = (~np.isnan(neigh)) & (~nodata_mask)
    slope = (center - neigh) / dist
    update = valid & (slope > best_slope)
    best_slope = np.where(update, slope, best_slope)
    pdir = np.where(update, np.int8(d_idx + 1), pdir).astype(np.int8)

flat_mask = (~nodata_mask) & (best_slope <= 0.0)
print(f"Initial flat cells: {int(np.sum(flat_mask))}")

# Compute incfall seeds
has_dir = (pdir > 0) & (~nodata_mask)
seeds_lower = []
for d_idx in range(8):
    dr, dc = int(D8_OFFSETS[d_idx, 0]), int(D8_OFFSETS[d_idx, 1])
    r0 = max(0, -dr); r1 = rows - max(0, dr)
    c0 = max(0, -dc); c1 = cols - max(0, dc)
    nr0, nr1 = r0 + dr, r1 + dr
    nc0, nc1 = c0 + dc, c1 + dc
    fc = flat_mask[r0:r1, c0:c1]
    cn = center[r0:r1, c0:c1]
    ne = center[nr0:nr1, nc0:nc1]
    hd = has_dir[nr0:nr1, nc0:nc1]
    seed = fc & hd & (~np.isnan(ne)) & (cn - ne >= -1e-9)
    seed = seed | (fc & (~np.isnan(ne)) & (ne < cn - 1e-9))
    for pos in np.argwhere(seed):
        r, c = int(pos[0]) + r0, int(pos[1]) + c0
        seeds_lower.append((r, c))

for d_idx in range(8):
    dr, dc = int(D8_OFFSETS[d_idx, 0]), int(D8_OFFSETS[d_idx, 1])
    ne_pad = pad[1 + dr:rows + 1 + dr, 1 + dc:cols + 1 + dc]
    seed = flat_mask & np.isnan(ne_pad)
    for pos in np.argwhere(seed):
        seeds_lower.append((int(pos[0]), int(pos[1])))

seeds_lower = list(set(seeds_lower))
dist_lower = _bfs_distance(seeds_lower, flat_mask, rows, cols)

seeds_higher = []
for d_idx in range(8):
    dr, dc = int(D8_OFFSETS[d_idx, 0]), int(D8_OFFSETS[d_idx, 1])
    r0 = max(0, -dr); r1 = rows - max(0, dr)
    c0 = max(0, -dc); c1 = cols - max(0, dc)
    nr0, nr1 = r0 + dr, r1 + dr
    nc0, nc1 = c0 + dc, c1 + dc
    fc = flat_mask[r0:r1, c0:c1]
    cn = center[r0:r1, c0:c1]
    ne = center[nr0:nr1, nc0:nc1]
    seed = fc & (~np.isnan(ne)) & (ne > cn + 1e-9)
    for pos in np.argwhere(seed):
        r, c = int(pos[0]) + r0, int(pos[1]) + c0
        seeds_higher.append((r, c))

seeds_higher = list(set(seeds_higher))
dist_higher = _bfs_distance(seeds_higher, flat_mask, rows, cols)
elev2 = dist_lower.astype(np.float64) - dist_higher.astype(np.float64)

# Analyze flat cells
flat_rows, flat_cols = np.where(flat_mask)
print(f"Total flat cells to resolve: {len(flat_rows)}")
print(f"dist_lower=0 cells: {int(np.sum(dist_lower[flat_mask] == 0))}")
print(f"dist_higher=0 cells: {int(np.sum(dist_higher[flat_mask] == 0))}")
print(f"both=0 cells: {int(np.sum((dist_lower[flat_mask] == 0) & (dist_higher[flat_mask] == 0)))}")

# Simulate setFlow2, track why cells fail
unresolved = []
reasons = {'no_valid_neighbor': 0, 'all_higher_nonflat': 0, 'zero_slope_flat': 0,
           'mixed': 0, 'isolated': 0}

for idx in range(len(flat_rows)):
    r, c = int(flat_rows[idx]), int(flat_cols[idx])
    elev_rc = center[r, c]
    elev2_rc = elev2[r, c]
    smax = 0.0
    best_d = -1

    has_nonflat_higher = False
    has_flat_neighbor = False

    for ii in range(8):
        d_idx = _SETFLOW2_ORDER[ii]
        dr, dc = int(D8_OFFSETS[d_idx, 0]), int(D8_OFFSETS[d_idx, 1])
        nr, nc = r + dr, c + dc
        if not (0 <= nr < rows and 0 <= nc < cols):
            continue
        if nodata_mask[nr, nc] or np.isnan(center[nr, nc]):
            continue
        if flat_mask[nr, nc]:
            has_flat_neighbor = True
            slope = _FACT[d_idx] * (elev2_rc - elev2[nr, nc])
            if slope > smax:
                smax = slope
                best_d = d_idx
        else:
            ed = elev_rc - center[nr, nc]
            if ed >= -1e-9:
                best_d = d_idx
                break
            else:
                has_nonflat_higher = True

    if best_d < 0:
        unresolved.append((r, c, elev_rc, elev2_rc, dist_lower[r,c], dist_higher[r,c], has_nonflat_higher, has_flat_neighbor))

print(f"\nUnresolved after setFlow2: {len(unresolved)}")

# Categorize
no_neighbors = sum(1 for x in unresolved if not x[6] and not x[7])
only_higher = sum(1 for x in unresolved if x[6] and not x[7])
flat_only = sum(1 for x in unresolved if not x[6] and x[7])
both = sum(1 for x in unresolved if x[6] and x[7])
print(f"  No valid neighbors at all: {no_neighbors}")
print(f"  Only non-flat (all higher): {only_higher}")
print(f"  Only flat neighbors (zero slope): {flat_only}")
print(f"  Both flat and higher nonflat: {both}")

# Print a sample
print("\nSample of unresolved cells (r, c, elev, elev2, dl, dh, nonflat_higher, flat_neigh):")
for x in unresolved[:20]:
    print(f"  r={x[0]:4d} c={x[1]:4d} elev={x[2]:.4f} elev2={x[3]:.1f} dl={x[4]:3d} dh={x[5]:3d} nf_hi={x[6]} fl={x[7]}")

# Check: are these cells all in connected components?
# and what are their neighbors' elev2?
print("\nDetailed neighbor info for first 5 unresolved:")
for x in unresolved[:5]:
    r, c = x[0], x[1]
    print(f"\nCell ({r},{c}) elev={x[2]:.4f} elev2={x[3]:.1f} dl={x[4]} dh={x[5]}")
    for ii in range(8):
        d_idx = _SETFLOW2_ORDER[ii]
        dr, dc = int(D8_OFFSETS[d_idx, 0]), int(D8_OFFSETS[d_idx, 1])
        nr, nc = r + dr, c + dc
        if 0 <= nr < rows and 0 <= nc < cols and not nodata_mask[nr, nc] and not np.isnan(center[nr, nc]):
            nf = flat_mask[nr, nc]
            print(f"  dir={d_idx+1} n=({nr},{nc}) elev={center[nr,nc]:.4f} flat={nf} pdir={pdir[nr,nc]} elev2={elev2[nr,nc]:.1f} dl={dist_lower[nr,nc]} dh={dist_higher[nr,nc]}")
