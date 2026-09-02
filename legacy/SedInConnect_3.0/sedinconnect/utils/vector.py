import numpy as np
from pathlib import Path
from osgeo import gdal, ogr

def rasterize_vector(vector_path: Path, output_path: Path,
                     reference_raster: Path, attribute: str, log_func=print):
    """Rasterize vector with attribute, with fallback to burn value if attribute missing or empty"""
    ref_ds = gdal.Open(str(reference_raster))
    vector_ds = ogr.Open(str(vector_path))
    if vector_ds is None:
        raise RuntimeError(f"Could not open vector file: {vector_path}")
        
    layer = vector_ds.GetLayer()
    layer_defn = layer.GetLayerDefn()
    field_names = [layer_defn.GetFieldDefn(i).GetName() for i in range(layer_defn.GetFieldCount())]

    driver = gdal.GetDriverByName('GTiff')
    target_ds = driver.Create(str(output_path), ref_ds.RasterXSize,
                              ref_ds.RasterYSize, 1, gdal.GDT_Float32)
    target_ds.SetGeoTransform(ref_ds.GetGeoTransform())
    target_ds.SetProjection(ref_ds.GetProjection())
    
    # Initialize with 0
    band = target_ds.GetRasterBand(1)
    band.Fill(0)

    use_burn = True
    if attribute in field_names:
        log_func(f"Rasterizing using attribute '{attribute}'...")
        gdal.RasterizeLayer(target_ds, [1], layer, options=[f"ATTRIBUTE={attribute}", "ALL_TOUCHED=TRUE"])
        
        # Check if we actually got any data
        ar = band.ReadAsArray()
        if np.any(ar > 0):
            use_burn = False
        else:
            log_func(f"Warning: Attribute '{attribute}' produced empty raster. Falling back to burn value 1.")

    if use_burn:
        log_func(f"Rasterizing using burn value 1 (ALL_TOUCHED=TRUE)...")
        gdal.RasterizeLayer(target_ds, [1], layer, burn_values=[1], options=["ALL_TOUCHED=TRUE"])

    if band is not None:
        band.FlushCache()
        band = None
    if target_ds is not None:
        target_ds.FlushCache()
        target_ds = None
    vector_ds = None
    ref_ds = None

def rasterize_vector_burn(vector_path: Path, output_path: Path,
                          reference_raster: Path):
    """Rasterize vector with burn value"""
    ref_ds = gdal.Open(str(reference_raster))
    vector_ds = ogr.Open(str(vector_path))
    if vector_ds is None:
        raise RuntimeError(f"Could not open vector file: {vector_path}")
        
    layer = vector_ds.GetLayer()

    driver = gdal.GetDriverByName('GTiff')
    target_ds = driver.Create(str(output_path), ref_ds.RasterXSize,
                              ref_ds.RasterYSize, 1, gdal.GDT_Float32)
    target_ds.SetGeoTransform(ref_ds.GetGeoTransform())
    target_ds.SetProjection(ref_ds.GetProjection())
    band = target_ds.GetRasterBand(1)
    band.SetNoDataValue(-9999)

    # Center point / touched approach for targets
    gdal.RasterizeLayer(target_ds, [1], layer, burn_values=[10], options=["ALL_TOUCHED=TRUE"])

    band.FlushCache()
    band = None
    target_ds.FlushCache()
    target_ds = None
    vector_ds = None
    ref_ds = None
