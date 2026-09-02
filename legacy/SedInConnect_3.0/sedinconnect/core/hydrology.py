import numpy as np
import time
import math

def propagate_d8_codes(fdir8: np.ndarray, codes: np.ndarray, ndv_fdir: float = None, log_func=print) -> np.ndarray:
    """Propagate codes upstream using D8 flow direction"""
    num_sinks = np.count_nonzero(codes > 0)
    log_func(f"Starting propagation for {num_sinks} sink points...")
    
    if num_sinks == 0:
        log_func("Warning: No sink points found in rasterized sink file!")
        return np.zeros_like(fdir8)

    # Pad arrays
    rows, cols = fdir8.shape
    Fdir8 = np.zeros((rows + 2, cols + 2), dtype=np.float32)
    Fdir8[1:-1, 1:-1] = fdir8
    if ndv_fdir is not None:
        Fdir8[Fdir8 == ndv_fdir] = -9999

    big_codes = np.zeros((rows + 2, cols + 2), dtype=np.float32)
    big_codes[1:-1, 1:-1] = codes

    # Initialize with sink codes to include sinks themselves
    SK_m = big_codes.copy()

    # Initial active cells are the sinks
    Y, X = np.where(big_codes > 0)
    
    # TauDEM directions: 1=E, 2=NE, 3=N, 4=NW, 5=W, 6=SW, 7=S, 8=SE
    # Center is at (y, x). Neighbor relative to center (dy, dx)
    directions = [
        (0, -1, 1),  # West neighbor drains East
        (1, -1, 2),  # SW neighbor drains NE
        (1, 0, 3),   # South neighbor drains North
        (1, 1, 4),   # SE neighbor drains NW
        (0, 1, 5),   # East neighbor drains West
        (-1, 1, 6),  # NE neighbor drains SW
        (-1, 0, 7),  # North neighbor drains South
        (-1, -1, 8)  # NW neighbor drains SE
    ]

    count = 0
    total_pixels = rows * cols
    
    while len(Y) > 0:
        count += 1
        new_y = []
        new_x = []
        
        for dy, dx, target_dir in directions:
            # Potential upstream neighbors
            uy = Y + dy
            ux = X + dx
            
            # Bounds check
            mask = (uy >= 0) & (uy < rows + 2) & (ux >= 0) & (ux < cols + 2)
            if not np.any(mask): continue
            
            uy_m, ux_m = uy[mask], ux[mask]
            cy_m, cx_m = Y[mask], X[mask]
            
            # Check if neighbor drains into current cell
            drains_in = (Fdir8[uy_m, ux_m] == target_dir)
            # Check if neighbor is NOT already masked
            not_masked = (SK_m[uy_m, ux_m] == 0)
            
            valid = drains_in & not_masked
            
            if np.any(valid):
                # Propagate basin code from current cell to upstream neighbor
                SK_m[uy_m[valid], ux_m[valid]] = SK_m[cy_m[valid], cx_m[valid]]
                new_y.extend(uy_m[valid])
                new_x.extend(ux_m[valid])
        
        # Update active cells for next iteration (de-duplicated)
        if new_y:
            combined = np.array(new_y, dtype=np.int64) * (cols + 2) + np.array(new_x, dtype=np.int64)
            _, indices = np.unique(combined, return_index=True)
            Y = np.array(new_y)[indices]
            X = np.array(new_x)[indices]
        else:
            break

        if count % 100 == 0:
            log_func(f"  Propagation iteration {count} (tracking {len(Y)} active cells)...")
        
        if count > total_pixels:
            log_func("Warning: Propagation safety limit reached!")
            break

    masked_count = np.count_nonzero(SK_m > 0)
    log_func(f"Watershed propagation completed in {count} iterations. Total masked pixels: {masked_count}")

    return SK_m[1:-1, 1:-1]


def compute_weighted_flow_length(fdir8: np.ndarray, weight: np.ndarray,
                                 cell_size: float, log_func=print) -> np.ndarray:
    """Compute weighted flow length using D8"""
    start_time = time.time()

    # Pad arrays
    Fdir8 = np.zeros((fdir8.shape[0] + 2, fdir8.shape[1] + 2), dtype=np.float32)
    Fdir8[1:-1, 1:-1] = fdir8

    Wgt = np.zeros((weight.shape[0] + 2, weight.shape[1] + 2), dtype=np.float32)
    Wgt[1:-1, 1:-1] = weight

    W_Fl = np.full_like(Fdir8, -1.0)

    # Find outlets (NoData cells)
    ND = np.where(np.isnan(Fdir8))
    Y = ND[0]
    X = ND[1]

    # Initialize lists for each direction
    YC = [[] for _ in range(8)]
    XC = [[] for _ in range(8)]

    # D8 directions and their upstream offsets
    directions = [
        (0, -1, 1, cell_size),  # West to East
        (1, -1, 2, cell_size * math.sqrt(2)),  # SW to NE
        (1, 0, 3, cell_size),  # South to North
        (1, 1, 4, cell_size * math.sqrt(2)),  # SE to NW
        (0, 1, 5, cell_size),  # East to West
        (-1, 1, 6, cell_size * math.sqrt(2)),  # NE to SW
        (-1, 0, 7, cell_size),  # North to South
        (-1, -1, 8, cell_size * math.sqrt(2))  # NW to SE
    ]

    # Find cells draining to outlets
    for idx, (dy, dx, direction, dist) in enumerate(directions):
        i = Fdir8[Y + dy, X + dx]
        D = np.where(i == direction)
        YC[idx].extend(Y[D])
        XC[idx].extend(X[D])
        if len(YC[idx]) > 0:
            W_Fl[YC[idx], XC[idx]] = 0

    # Propagate upstream
    count = 1
    while any(len(yc) > 0 for yc in YC):
        YY = []
        XX = []

        for idx, (dy, dx, direction, dist) in enumerate(directions):
            if len(YC[idx]) > 0:
                YYC = np.asarray(YC[idx])
                XXC = np.asarray(XC[idx])

                # Move upstream
                YYC_new = YYC + dy
                XXC_new = XXC + dx

                if count == 1:
                    W_Fl[YYC_new, XXC_new] = 0
                else:
                    # Weighted flow length
                    W_Fl[YYC_new, XXC_new] = (W_Fl[YYC, XXC] +
                                              dist * ((Wgt[YYC, XXC] + Wgt[YYC_new, XXC_new]) / 2))

                YY.extend(YYC_new)
                XX.extend(XXC_new)

        # Find next cells
        YY = np.asarray(YY) if len(YY) > 0 else np.array([])
        XX = np.asarray(XX) if len(XX) > 0 else np.array([])

        YC = [[] for _ in range(8)]
        XC = [[] for _ in range(8)]

        if len(YY) > 0:
            for idx, (dy, dx, direction, dist) in enumerate(directions):
                i = Fdir8[YY + dy, XX + dx]
                D = np.where(i == direction)
                YC[idx] = YY[D].tolist()
                XC[idx] = XX[D].tolist()

        count += 1

    elapsed = time.time() - start_time
    log_func(f"Weighted flow length calculated in {elapsed:.2f} seconds with {count} iterations")

    # Remove padding
    return W_Fl[1:-1, 1:-1]
