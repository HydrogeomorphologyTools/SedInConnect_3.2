"""
pitfill.py - Priority-Flood depression filling algorithm.
Equivalent to TauDEM PitRemove.

Reference: Wang & Liu (2006); Barnes, Lehman & Mulla (2014)
"""

import numpy as np
import heapq


def priority_flood_fill(dem: np.ndarray, nodata: float = -9999.0) -> np.ndarray:
    """
    Fill pits/depressions using the Priority-Flood algorithm.
    Equivalent to ArcGIS Fill / TauDEM PitRemove.

    Seed cells are all valid-data cells that lie on the grid border
    OR are adjacent to at least one NoData cell.  This ensures that
    NoData acts as a natural drainage boundary and only true interior
    depressions are filled.

    Reference: Wang & Liu (2006), Barnes et al. (2014)

    Parameters
    ----------
    dem : np.ndarray (float32 or float64)
        Digital elevation model array.
    nodata : float
        NoData value in the DEM.

    Returns
    -------
    filled : np.ndarray, same shape as dem, dtype float32
        Filled DEM with depressions removed.
    """
    rows, cols = dem.shape
    filled = dem.astype(np.float64).copy()
    visited = np.zeros((rows, cols), dtype=bool)

    heap = []

    # 8-connected neighbor offsets
    NEIGHBORS = [(-1, -1), (-1, 0), (-1, 1),
                 (0, -1),           (0, 1),
                 (1, -1),  (1, 0),  (1, 1)]

    # Build NoData mask once (NaN or sentinel value)
    nodata_mask = np.isnan(filled) | (filled == nodata)

    # Seed the heap with all valid cells on the grid border
    # OR adjacent to at least one NoData cell.
    for r in range(rows):
        for c in range(cols):
            if nodata_mask[r, c] or visited[r, c]:
                continue
            is_border = (r == 0 or r == rows - 1 or c == 0 or c == cols - 1)
            is_nodata_adj = False
            if not is_border:
                for dr, dc in NEIGHBORS:
                    nr, nc = r + dr, c + dc
                    if 0 <= nr < rows and 0 <= nc < cols and nodata_mask[nr, nc]:
                        is_nodata_adj = True
                        break
            if is_border or is_nodata_adj:
                heapq.heappush(heap, (filled[r, c], r, c))
                visited[r, c] = True

    # Priority flood: process cells in ascending elevation order
    while heap:
        elev, r, c = heapq.heappop(heap)
        for dr, dc in NEIGHBORS:
            nr, nc = r + dr, c + dc
            if 0 <= nr < rows and 0 <= nc < cols and not visited[nr, nc]:
                visited[nr, nc] = True
                if nodata_mask[nr, nc]:
                    continue  # skip NoData cells
                if filled[nr, nc] < elev:
                    filled[nr, nc] = elev  # fill the depression
                heapq.heappush(heap, (filled[nr, nc], nr, nc))

    return filled.astype(np.float32)


def fill_dem(dem_array: np.ndarray, nodata: float = -9999.0,
             log_func=print) -> np.ndarray:
    """
    Fill DTM depressions. Returns filled array.

    Parameters
    ----------
    dem_array : np.ndarray
        Input DEM array.
    nodata : float
        NoData sentinel value.
    log_func : callable
        Logging function (default: print).

    Returns
    -------
    filled : np.ndarray float32
    """
    log_func("Filling DTM depressions (Priority-Flood algorithm)...")
    n_nodata = int(np.sum((dem_array == nodata) | np.isnan(dem_array)))
    log_func(f"  Input: {dem_array.shape[0]}x{dem_array.shape[1]} cells, "
             f"{n_nodata} nodata")

    filled = priority_flood_fill(dem_array, nodata)

    # Count cells that were actually raised (filled)
    valid_mask = (dem_array != nodata) & ~np.isnan(dem_array)
    n_filled = int(np.sum((filled > dem_array.astype(np.float32)) & valid_mask))
    log_func(f"  Filled {n_filled} depression cells")
    return filled
