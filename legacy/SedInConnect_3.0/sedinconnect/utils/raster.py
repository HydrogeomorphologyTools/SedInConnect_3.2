import os
import numpy as np
from pathlib import Path
from osgeo import gdal

class LargeFileRasterReader:
    """Efficient raster reading for large files"""

    def __init__(self, filepath: Path):
        self.filepath = filepath
        self.dataset = gdal.Open(str(filepath))
        if self.dataset is None:
            raise ValueError(f"Could not open raster: {filepath}")

        self.band = self.dataset.GetRasterBand(1)
        self.cols = self.dataset.RasterXSize
        self.rows = self.dataset.RasterYSize
        self.geotransform = self.dataset.GetGeoTransform()
        self.projection = self.dataset.GetProjection()
        self.nodata = self.band.GetNoDataValue()

    def read_array(self) -> np.ndarray:
        """Read full array"""
        return self.band.ReadAsArray().astype(np.float32)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.dataset = None


def save_raster(array: np.ndarray, output_path: Path,
                geotransform: tuple, projection: str, nodata: float = -9999):
    """Save array as GeoTIFF with better error handling"""
    try:
        driver = gdal.GetDriverByName('GTiff')
        options = ['COMPRESS=LZW', 'BIGTIFF=YES', 'TILED=YES']

        output_path_str = str(output_path)
        if os.path.exists(output_path_str):
            try:
                os.remove(output_path_str)
            except Exception as e:
                # If we can't remove it, driver.Create will likely fail or try to overwrite
                pass

        dataset = driver.Create(output_path_str, array.shape[1], array.shape[0],
                                1, gdal.GDT_Float32, options=options)

        if dataset is None:
            raise RuntimeError(f"GDAL failed to create output file: {output_path_str}. "
                               f"Check if it's open in another program or if you have write permissions.")

        dataset.SetGeoTransform(geotransform)
        dataset.SetProjection(projection)
        band = dataset.GetRasterBand(1)
        band.SetNoDataValue(nodata)
        band.WriteArray(array)
        band.ComputeStatistics(False)
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
