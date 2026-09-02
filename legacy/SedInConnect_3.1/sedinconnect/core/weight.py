import numpy as np
import time
from pathlib import Path
from multiprocessing import Pool, cpu_count
from scipy import signal
from osgeo import gdal
from sedinconnect.utils.raster import LargeFileRasterReader, save_raster

def _process_chunk_roughness_global(args):
    """
    Highly optimized roughness computation using 2D convolution.
    Replicates the logic in the verified monolithic version.
    """
    chunk_data, window_size, nodata_value = args

    # Local imports for worker processes
    import numpy as np
    from scipy import signal

    i_ar = chunk_data.astype(np.float64)
    rows, cols = i_ar.shape
    tipo = i_ar.dtype

    if nodata_value is not None:
        i_ar[i_ar == nodata_value] = np.nan

    size_filter = int(window_size)
    ker = np.ones((size_filter, size_filter))

    i_ar_p = np.ones((rows, cols), dtype=tipo)
    i_ar_p[np.isnan(i_ar)] = 0

    i_ar_d = np.zeros((rows, cols), dtype=tipo)
    valid_mask = ~np.isnan(i_ar)
    i_ar_d[valid_mask] = i_ar[valid_mask]

    # Fast moving standard deviation using convolution
    d_num_el = signal.convolve2d(i_ar_p, ker, 'same')
    d_num_el[np.isnan(i_ar)] = np.nan

    e_sum = signal.convolve2d(i_ar_d, ker, 'same')
    e_sum[np.isnan(i_ar)] = np.nan

    m = e_sum / d_num_el

    dtm_r = i_ar.copy()
    dtm_r[valid_mask] -= m[valid_mask]
    dtm_r[np.isnan(i_ar)] = 0

    e_r = signal.convolve2d(dtm_r, ker, 'same')
    e_r[np.isnan(i_ar)] = np.nan
    m_r = e_r / d_num_el

    dtm_r_sq = dtm_r * dtm_r
    e_r_sq = signal.convolve2d(dtm_r_sq, ker, 'same')
    e_r_sq[np.isnan(i_ar)] = np.nan

    m_r_sq = e_r_sq / d_num_el
    mrsq = np.power(m_r, 2)

    # Standard deviation formula: sqrt(E[X^2] - E[X]^2)
    ri = np.sqrt(np.maximum(0, m_r_sq - mrsq))
    ri[np.isnan(i_ar)] = np.nan

    return ri

class WeightCalculator:
    """Computes roughness and weighting factors using parallel processing"""
    
    def __init__(self, log_func=print):
        self.log = log_func

    def compute(self, dtm_path: Path, window_size: int,
                weight_out: Path, roughness_out: Path,
                normalize: bool = False, sink_flag: int = 0) -> Path:
        """Compute Cavalli weighting factor with optimized parallel processing"""
        start_time = time.time()
        chunk_size = 1024
        
        try:
            n_workers = max(1, cpu_count() - 4)
        except:
            n_workers = 8

        self.log(f"Computing roughness (PARALLEL: {n_workers} workers, chunks: {chunk_size}x{chunk_size})...")

        # Open DTM
        ds = gdal.Open(str(dtm_path))
        if ds is None:
            raise ValueError(f"Could not open {dtm_path}")

        cols = ds.RasterXSize
        rows = ds.RasterYSize
        band = ds.GetRasterBand(1)
        nodata = band.GetNoDataValue()
        geotransform = ds.GetGeoTransform()
        projection = ds.GetProjection()

        self.log(f"DTM: {cols} x {rows} pixels")

        # Create output raster for roughness
        driver = gdal.GetDriverByName('GTiff')
        ri_ds = driver.Create(str(roughness_out), cols, rows, 1, gdal.GDT_Float32,
                              options=['COMPRESS=LZW', 'TILED=YES', 'BIGTIFF=YES'])
        ri_ds.SetGeoTransform(geotransform)
        ri_ds.SetProjection(projection)
        ri_band = ri_ds.GetRasterBand(1)
        if nodata is not None:
            ri_band.SetNoDataValue(nodata)

        # Prepare chunks
        overlap = window_size
        n_chunks_y = int(np.ceil(rows / chunk_size))
        n_chunks_x = int(np.ceil(cols / chunk_size))
        total_chunks = n_chunks_y * n_chunks_x

        self.log(f"Processing {total_chunks} chunks...")

        chunk_args = []
        chunk_positions = []

        for i in range(n_chunks_y):
            for j in range(n_chunks_x):
                y_start = max(0, i * chunk_size - overlap)
                y_end = min(rows, (i + 1) * chunk_size + overlap)
                x_start = max(0, j * chunk_size - overlap)
                x_end = min(cols, (j + 1) * chunk_size + overlap)

                y_core_start = i * chunk_size
                y_core_end = min(rows, (i + 1) * chunk_size)
                x_core_start = j * chunk_size
                x_core_end = min(cols, (j + 1) * chunk_size)

                chunk_positions.append({
                    'y_start': y_start, 'y_end': y_end,
                    'x_start': x_start, 'x_end': x_end,
                    'y_core_start': y_core_start, 'y_core_end': y_core_end,
                    'x_core_start': x_core_start, 'x_core_end': x_core_end
                })

                chunk = band.ReadAsArray(x_start, y_start, x_end - x_start, y_end - y_start)
                chunk_args.append((chunk, window_size, nodata))

        # Process chunks in parallel
        max_ri_global = -np.inf
        results = []

        with Pool(processes=n_workers) as pool:
            for idx, ri_chunk in enumerate(pool.imap(_process_chunk_roughness_global, chunk_args)):
                results.append(ri_chunk)

                valid_ri = ri_chunk[~np.isnan(ri_chunk)]
                if len(valid_ri) > 0:
                    chunk_max = valid_ri.max()
                    if chunk_max > max_ri_global:
                        max_ri_global = chunk_max

                if (idx + 1) % max(1, total_chunks // 10) == 0 or (idx + 1) == total_chunks:
                    progress = ((idx + 1) / total_chunks) * 100
                    self.log(f"Progress: {progress:5.1f}% ({idx + 1}/{total_chunks})")

        if max_ri_global == -np.inf:
            max_ri_global = 1.0
            
        self.log(f"Max RI: {max_ri_global:.6f}")

        # Write results
        self.log("Writing roughness to disk...")
        for ri_chunk, pos in zip(results, chunk_positions):
            y_offset = pos['y_core_start'] - pos['y_start']
            y_size = pos['y_core_end'] - pos['y_core_start']
            x_offset = pos['x_core_start'] - pos['x_start']
            x_size = pos['x_core_end'] - pos['x_core_start']

            core_chunk = ri_chunk[y_offset:y_offset + y_size, x_offset:x_offset + x_size]

            if nodata is not None:
                core_chunk_write = core_chunk.copy()
                core_chunk_write[np.isnan(core_chunk)] = nodata
            else:
                core_chunk_write = core_chunk

            ri_band.WriteArray(core_chunk_write, pos['x_core_start'], pos['y_core_start'])

        ri_band.FlushCache()
        ri_band.ComputeStatistics(False)
        
        # Release handles
        ri_band = None
        ri_ds = None
        
        self.log("[OK] Roughness saved")

        # Handle sinks
        if sink_flag == 1:
            self.log("Applying sink masking to roughness...")
            sk_dtm_path = dtm_path.parent / "sinked_dtm.tif"
            with LargeFileRasterReader(sk_dtm_path) as sk_reader:
                sk_dtm_ar = sk_reader.read_array()
                sk_ndv = sk_reader.nodata
            
            ds_tmp = gdal.Open(str(roughness_out))
            ri_ar = ds_tmp.GetRasterBand(1).ReadAsArray()
            ri_ar[(sk_dtm_ar == -9999) | (sk_dtm_ar == sk_ndv) | np.isnan(sk_dtm_ar)] = np.nan
            ds_tmp = None 
            
            save_raster(ri_ar, roughness_out, geotransform, projection)

            # Recalculate max_ri_global after sink masking, matching SedInConnect 2.3
            valid_masked = ri_ar[~np.isnan(ri_ar)]
            if len(valid_masked) > 0:
                max_ri_global = float(valid_masked.max())
            self.log(f"Max RI (after sink masking): {max_ri_global:.6f}")

        # Compute weighting factor
        self.log("Computing weighting factor...")
        
        ri_ds = gdal.Open(str(roughness_out))
        ri_band = ri_ds.GetRasterBand(1)
        
        w_ds = driver.Create(str(weight_out), cols, rows, 1, gdal.GDT_Float32,
                             options=['COMPRESS=LZW', 'TILED=YES', 'BIGTIFF=YES'])
        w_ds.SetGeoTransform(geotransform)
        w_ds.SetProjection(projection)
        w_band = w_ds.GetRasterBand(1)
        if nodata is not None:
            w_band.SetNoDataValue(nodata)

        # Process weight in chunks
        for i in range(0, rows, chunk_size):
            chunk_rows = min(chunk_size, rows - i)
            for j in range(0, cols, chunk_size):
                chunk_cols = min(chunk_size, cols - j)
                ri_chunk = ri_band.ReadAsArray(j, i, chunk_cols, chunk_rows)
                if nodata is not None:
                    mask_nodata = (ri_chunk == nodata)
                    ri_chunk = ri_chunk.astype(np.float64)
                    ri_chunk[mask_nodata] = np.nan
                w_chunk = 1.0 - (ri_chunk / max_ri_global)
                w_chunk[~np.isnan(w_chunk) & (w_chunk < 0.001)] = 0.001
                if nodata is not None:
                    w_chunk[mask_nodata] = nodata
                w_band.WriteArray(w_chunk, j, i)

        # Normalization
        if normalize:
            self.log("Normalizing (Trevisani & Cavalli, 2016)...")
            Ri_full = ri_band.ReadAsArray()
            if nodata is not None:
                Ri_full = Ri_full.astype(np.float64)
                Ri_full[Ri_full == nodata] = np.nan
            Ri_full[Ri_full < 0.001] = 0.001
            min_r = np.nanmin(Ri_full)
            max_r = np.nanmax(Ri_full)
            weig_fac = 1.0 - ((np.log(Ri_full) - np.log(min_r)) / (np.log(max_r) - np.log(min_r)))
            weig_fac[weig_fac < 0.001] = 0.001
            if nodata is not None:
                weig_fac[np.isnan(Ri_full)] = nodata
            for i in range(0, rows, chunk_size):
                chunk_rows = min(chunk_size, rows - i)
                for j in range(0, cols, chunk_size):
                    chunk_cols = min(chunk_size, cols - j)
                    w_chunk_norm = weig_fac[i:i + chunk_rows, j:j + chunk_cols]
                    w_band.WriteArray(w_chunk_norm, j, i)

        w_band.FlushCache()
        w_band.ComputeStatistics(False)
        
        ri_ds = None
        w_ds = None
        self.log("[OK] Weight saved")
        
        elapsed = time.time() - start_time
        self.log(f"Roughness computed in {elapsed:.1f}s ({elapsed / 60:.1f}min)")
        return weight_out
