import sys
import os
import numpy as np
from pathlib import Path
from osgeo import gdal, gdal_array

def _debug_log(msg):
    try:
        log_file = os.path.join(os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(__file__), "startup.log")
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"  [RasterReader] {msg}\n")
    except Exception as e:
        print(f"DEBUG_LOG ERROR: {e}")

class LargeFileRasterReader:
    """Efficient raster reading for large files"""

    def __init__(self, filepath: Path):
        self.filepath = Path(filepath)
        path_str = str(self.filepath)
        _debug_log(f"1. gdal.Open on {path_str}")
        self.dataset = gdal.Open(path_str)
        if self.dataset is None:
            _debug_log(f"1. ERROR: dataset is None for {path_str}")
            raise ValueError(f"Could not open raster: {path_str}")

        _debug_log("2. GetRasterBand(1)")
        self.band = self.dataset.GetRasterBand(1)
        _debug_log("3. RasterXSize/RasterYSize")
        self.cols = self.dataset.RasterXSize
        self.rows = self.dataset.RasterYSize
        _debug_log("4. GetGeoTransform")
        self.geotransform = self.dataset.GetGeoTransform()
        _debug_log("5. GetProjection")
        self.projection = self.dataset.GetProjection()
        _debug_log("6. GetNoDataValue")
        self.nodata = self.band.GetNoDataValue()
        _debug_log("7. __init__ done")

    def read_array(self) -> np.ndarray:
        """Read full array"""
        _debug_log("read_array: calling band.ReadAsArray")
        arr = self.band.ReadAsArray()
        _debug_log(f"read_array: got array of shape {arr.shape}, dtype={arr.dtype}")
        return arr.astype(np.float32)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.band = None
        self.dataset = None


def save_raster(array: np.ndarray, output_path: Path,
                geotransform: tuple, projection: str, nodata: float = -9999):
    """Save array as GeoTIFF with better error handling"""
    try:
        driver = gdal.GetDriverByName('GTiff')
        options = ['COMPRESS=LZW', 'BIGTIFF=YES', 'TILED=YES']

        dataset = driver.Create(str(output_path), array.shape[1], array.shape[0],
                                1, gdal.GDT_Float32, options=options)

        if dataset is None:
            raise RuntimeError(f"Failed to create output file: {output_path}")

        dataset.SetGeoTransform(geotransform)
        dataset.SetProjection(projection)
        band = dataset.GetRasterBand(1)
        band.SetNoDataValue(nodata)
        band.WriteArray(array)
        band.FlushCache()
        band = None
        dataset.FlushCache()
        dataset = None

    except PermissionError as e:
        raise RuntimeError(
            f"Permission denied writing to '{output_path}'. "
            f"The file may be open in another program (GIS, Excel, etc.). "
            f"Please close it and try again."
        ) from e
    except OSError as e:
        if "Permission denied" in str(e) or "being used by another process" in str(e):
            raise RuntimeError(
                f"Cannot write to '{output_path}' - file is locked or in use by another program. "
                f"Please close the file in any GIS or other applications and try again."
            ) from e
        else:
            raise RuntimeError(f"File system error writing to '{output_path}': {str(e)}") from e
    except Exception as e:
        raise RuntimeError(f"Error saving raster to '{output_path}': {str(e)}") from e
