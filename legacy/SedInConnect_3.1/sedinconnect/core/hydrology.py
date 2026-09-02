import numpy as np
import time
import math
import numba as nb

@nb.njit(fastmath=True)
def _propagate_d8_codes_nb(Fdir8, big_codes):
    ny, nx = Fdir8.shape
    # TauDEM directions: 1=E, 2=NE, 3=N, 4=NW, 5=W, 6=SW, 7=S, 8=SE
    # dy, dx relative to current cell (upstream neighbor)
    dy_arr = np.array([0, 1, 1, 1, 0, -1, -1, -1], dtype=nb.int32)
    dx_arr = np.array([-1, -1, 0, 1, 1, 1, 0, -1], dtype=nb.int32)
    dir_arr = np.array([1, 2, 3, 4, 5, 6, 7, 8], dtype=nb.int32)

    SK_m = big_codes.copy()
    max_q = nx * ny
    q_x = np.empty(max_q, dtype=nb.int32)
    q_y = np.empty(max_q, dtype=nb.int32)
    head = 0
    tail = 0

    # Seed queue from active cells
    for j in range(1, ny - 1):
        for i in range(1, nx - 1):
            if big_codes[j, i] > 0:
                q_x[tail] = i
                q_y[tail] = j
                tail += 1

    iterations = 0
    while head < tail:
        iterations += 1
        level_size = tail - head
        for _ in range(level_size):
            cx = q_x[head]
            cy = q_y[head]
            head += 1

            for k in range(8):
                uy = cy + dy_arr[k]
                ux = cx + dx_arr[k]
                if 0 <= uy < ny and 0 <= ux < nx:
                    if Fdir8[uy, ux] == dir_arr[k] and SK_m[uy, ux] == 0:
                        SK_m[uy, ux] = SK_m[cy, cx]
                        q_x[tail] = ux
                        q_y[tail] = uy
                        tail += 1

    return SK_m, iterations

def propagate_d8_codes(fdir8: np.ndarray, codes: np.ndarray, ndv_fdir: float = None, log_func=print) -> np.ndarray:
    """Propagate codes upstream using compiled D8 flow direction queue"""
    start_time = time.time()
    rows, cols = fdir8.shape
    Fdir8 = np.zeros((rows + 2, cols + 2), dtype=np.float32)
    Fdir8[1:-1, 1:-1] = fdir8
    Fdir8[(Fdir8 <= 0) | (Fdir8 > 8) | np.isnan(Fdir8)] = -9999
    if ndv_fdir is not None:
        Fdir8[Fdir8 == ndv_fdir] = -9999

    big_codes = np.zeros((rows + 2, cols + 2), dtype=np.float32)
    big_codes[1:-1, 1:-1] = codes

    SK_m, iterations = _propagate_d8_codes_nb(Fdir8, big_codes)
    elapsed = time.time() - start_time
    masked_count = np.count_nonzero(SK_m[1:-1, 1:-1] > 0)
    log_func(f"Watershed propagation completed in {elapsed:.3f}s ({iterations} iterations). Total masked pixels: {masked_count}")
    return SK_m[1:-1, 1:-1]


@nb.njit(fastmath=True)
def _compute_weighted_flow_length_nb(Fdir8, Wgt, cell_size):
    ny, nx = Fdir8.shape
    dy_arr = np.array([0, 1, 1, 1, 0, -1, -1, -1], dtype=nb.int32)
    dx_arr = np.array([-1, -1, 0, 1, 1, 1, 0, -1], dtype=nb.int32)
    dir_arr = np.array([1, 2, 3, 4, 5, 6, 7, 8], dtype=nb.int32)
    dist_arr = np.array([
        cell_size,
        cell_size * 1.4142135623730951,
        cell_size,
        cell_size * 1.4142135623730951,
        cell_size,
        cell_size * 1.4142135623730951,
        cell_size,
        cell_size * 1.4142135623730951
    ], dtype=nb.float64)

    W_Fl = np.full((ny, nx), -1.0, dtype=nb.float32)

    # Initial lists of active cells per direction
    max_q = nx * ny
    # We will use level queues
    q_x = np.empty(max_q, dtype=nb.int32)
    q_y = np.empty(max_q, dtype=nb.int32)
    tail = 0

    # Step 0: Outlets are inside the valid region [1..ny-2, 1..nx-2] where Fdir8 is NaN
    for j in range(1, ny - 1):
        for i in range(1, nx - 1):
            if np.isnan(Fdir8[j, i]):
                # Check for upstream cells pointing to this outlet
                for k in range(8):
                    uy = j + dy_arr[k]
                    ux = i + dx_arr[k]
                    if 0 <= uy < ny and 0 <= ux < nx:
                        if Fdir8[uy, ux] == dir_arr[k]:
                            W_Fl[j, i] = 0.0
                            # Push cell (j, i) to queue with direction index k
                            q_x[tail] = i
                            q_y[tail] = j
                            tail += 1
                            break

    # Count 1: Set immediate upstream cells to 0
    # Process level by level
    head = 0
    count = 1
    while head < tail:
        level_size = tail - head
        count += 1
        for _ in range(level_size):
            cx = q_x[head]
            cy = q_y[head]
            head += 1

            for k in range(8):
                uy = cy + dy_arr[k]
                ux = cx + dx_arr[k]
                if 0 <= uy < ny and 0 <= ux < nx:
                    if Fdir8[uy, ux] == dir_arr[k]:
                        if count == 2:
                            W_Fl[uy, ux] = 0.0
                        else:
                            dist = dist_arr[k]
                            w_avg = (Wgt[cy, cx] + Wgt[uy, ux]) * 0.5
                            new_val = W_Fl[cy, cx] + np.float32(dist * w_avg)
                            if W_Fl[uy, ux] < 0.0 or new_val < W_Fl[uy, ux]:
                                W_Fl[uy, ux] = new_val

                        q_x[tail] = ux
                        q_y[tail] = uy
                        tail += 1

    return W_Fl, count

def compute_weighted_flow_length(fdir8: np.ndarray, weight: np.ndarray,
                                 cell_size: float, log_func=print) -> np.ndarray:
    """Compute weighted flow length using compiled D8 Numba propagation"""
    start_time = time.time()

    # Pad arrays with 0 exactly like 3.0
    Fdir8 = np.zeros((fdir8.shape[0] + 2, fdir8.shape[1] + 2), dtype=np.float32)
    Fdir8[1:-1, 1:-1] = fdir8

    Wgt = np.zeros((weight.shape[0] + 2, weight.shape[1] + 2), dtype=np.float32)
    Wgt[1:-1, 1:-1] = weight

    # Directions: (0, -1, 1), (1, -1, 2), (1, 0, 3), (1, 1, 4), (0, 1, 5), (-1, 1, 6), (-1, 0, 7), (-1, -1, 8)
    W_Fl = np.full_like(Fdir8, -1.0)
    ND = np.where(np.isnan(Fdir8))
    Y = ND[0]
    X = ND[1]

    directions = [
        (0, -1, 1, cell_size),
        (1, -1, 2, cell_size * math.sqrt(2)),
        (1, 0, 3, cell_size),
        (1, 1, 4, cell_size * math.sqrt(2)),
        (0, 1, 5, cell_size),
        (-1, 1, 6, cell_size * math.sqrt(2)),
        (-1, 0, 7, cell_size),
        (-1, -1, 8, cell_size * math.sqrt(2))
    ]

    YC = [[] for _ in range(8)]
    XC = [[] for _ in range(8)]

    for idx, (dy, dx, direction, dist) in enumerate(directions):
        i = Fdir8[Y + dy, X + dx]
        D = np.where(i == direction)
        YC[idx].extend(Y[D])
        XC[idx].extend(X[D])
        if len(YC[idx]) > 0:
            W_Fl[YC[idx], XC[idx]] = 0

    count = 1
    while any(len(yc) > 0 for yc in YC):
        YY = []
        XX = []

        for idx, (dy, dx, direction, dist) in enumerate(directions):
            if len(YC[idx]) > 0:
                YYC = np.asarray(YC[idx])
                XXC = np.asarray(XC[idx])
                YYC_new = YYC + dy
                XXC_new = XXC + dx

                if count == 1:
                    W_Fl[YYC_new, XXC_new] = 0
                else:
                    W_Fl[YYC_new, XXC_new] = (W_Fl[YYC, XXC] +
                                              dist * ((Wgt[YYC, XXC] + Wgt[YYC_new, XXC_new]) / 2))

                YY.extend(YYC_new)
                XX.extend(XXC_new)

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
    return W_Fl[1:-1, 1:-1]
