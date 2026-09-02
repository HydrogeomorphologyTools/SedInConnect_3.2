"""
Find which pdir=0 cells are actually blocking 374k cells from getting D_down.
Strategy: run D_down BFS, check which pdir=0 cells block the most paths.
Also compare with TauDEM ref_p.tif to see what TauDEM gives for those cells.
"""
import numpy as np
import sys, math
sys.path.insert(0, r'D:\Research\SedInConnect_python\SedInConnect_3.1')
from osgeo import gdal
from collections import deque

# Load DEM
dtm_path = r'D:\Research\SedInConnect_python\dtmfel.tif'
ds = gdal.Open(dtm_path)
band = ds.GetRasterBand(1)
dem = band.ReadAsArray().astype(np.float32)
nodata = band.GetNoDataValue()
cell_size = ds.GetGeoTransform()[1]
ds = None

# Compute native D8
from sedinconnect.core.native.d8flowdir import compute_d8_flowdir
pdir, sd8 = compute_d8_flowdir(dem, cell_size, nodata)

# Load TauDEM ref D8
ref_path = r'D:\Research\SedInConnect_python\ref_p.tif'
ds = gdal.Open(ref_path)
ref_pdir = ds.GetRasterBand(1).ReadAsArray().astype(np.float32)
ds = None

rows, cols = pdir.shape
nodata_mask = (pdir == -1)

# Cells where TauDEM valid (1-8) but native pdir=0
taudem_valid = (ref_pdir >= 1) & (ref_pdir <= 8)
native_zero = (pdir == 0)
conflict = taudem_valid & native_zero
print(f"TauDEM valid, native pdir=0: {int(np.sum(conflict))}")

# Show sample TauDEM pdir for conflicting cells
rows_c, cols_c = np.where(conflict)
print(f"\nSample of conflicting cells (r, c, taudem_pdir, native_pdir=0):")
for i in range(min(20, len(rows_c))):
    r, c = int(rows_c[i]), int(cols_c[i])
    print(f"  ({r:4d},{c:4d}) taudem_pdir={int(ref_pdir[r,c])}")

# Now find which pdir=0 cells are in D_down flow paths
# Load targets
tgt_path = r'D:\Research\SedInConnect_python\targets.tif'
try:
    ds = gdal.Open(tgt_path)
    tgt = ds.GetRasterBand(1).ReadAsArray()
    ds = None
except:
    print("No targets.tif found, using -1000 from p_tg.tif")
    tgt = None

# Build D8 neighbor lookup for flow-following
D8_OFFSETS = np.array([[0,1],[-1,1],[-1,0],[-1,-1],[0,-1],[1,-1],[1,0],[1,1]])

# For each pdir=0 cell, compute its upstream catchment using backward BFS on D8
# (find all cells that flow through this pdir=0 cell)
print("\n--- Analyzing upstream catchments of pdir=0 cells ---")

# Build forward flow: for each cell, its downstream cell (following pdir)
# Build backward flow: for each cell, list of upstream cells

# Build upstream_map: cell -> list of cells draining into it
# For efficiency, use vectorized approach

# Create padded pdir array
pdir_flat = pdir.astype(np.float32)
pdir_flat[pdir_flat == 0] = -9999
pdir_flat[pdir_flat == -1] = -9999

# For each cell, find downstream cell
# downstream[r,c] = (r+dr, c+dc) following pdir[r,c]
# Build upstream list using forward pass

# For the pdir=0 cells that block D_down, we need:
# 1. Count of upstream cells that flow through each pdir=0 cell
# Let's do a simple approach: for each pdir=0 cell, BFS upstream

# First, build map: (r,c) -> upstream cells
upstream = [[[] for _ in range(cols)] for _ in range(rows)]
for r in range(rows):
    for c in range(cols):
        p = int(pdir[r, c])
        if p < 1 or p > 8:
            continue
        dr, dc = int(D8_OFFSETS[p-1, 0]), int(D8_OFFSETS[p-1, 1])
        nr, nc = r + dr, c + dc
        if 0 <= nr < rows and 0 <= nc < cols:
            upstream[nr][nc].append((r, c))

print("Built upstream map.")

# For each pdir=0 cell, count upstream cells
zero_cells = np.argwhere(native_zero)
print(f"Total pdir=0 cells: {len(zero_cells)}")

# Count upstream catchment for each pdir=0 cell
catchment_sizes = []
for pos in zero_cells:
    r, c = int(pos[0]), int(pos[1])
    # BFS upstream
    visited = set()
    q = deque([(r, c)])
    while q:
        cr, cc = q.popleft()
        for ur, uc in upstream[cr][cc]:
            if (ur, uc) not in visited:
                visited.add((ur, uc))
                q.append((ur, uc))
    catchment_sizes.append((len(visited), r, c))

catchment_sizes.sort(reverse=True)
total_blocked = sum(s for s, r, c in catchment_sizes if s > 0)
# Note: this double-counts cells that flow through multiple pdir=0 cells

print(f"\nTop 20 pdir=0 cells by upstream catchment:")
for size, r, c in catchment_sizes[:20]:
    tpdir = int(ref_pdir[r, c])
    print(f"  ({r:4d},{c:4d}) catchment={size:6d} taudem_pdir={tpdir}")

print(f"\nCells with catchment > 0: {sum(1 for s, r, c in catchment_sizes if s > 0)}")
print(f"Cells with catchment > 100: {sum(1 for s, r, c in catchment_sizes if s > 100)}")
