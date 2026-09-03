"""
SedInConnect 3.2 - Sediment Connectivity Index (IC) Assessment Package
"""

__version__ = "3.2.0"
__author__ = "Stefano Crema, Marco Cavalli (CNR-IRPI)"

from pathlib import Path
from typing import Optional, Union

from .utils.params import ProcessingParams
from .core.processor import ConnectivityProcessor


def compute_ic(
    dtm: Union[str, Path],
    output: Union[str, Path],
    cell_size: Optional[float] = None,
    target: Optional[Union[str, Path]] = None,
    sink: Optional[Union[str, Path]] = None,
    auto_weight: bool = True,
    window_size: int = 3,
    custom_weight: Optional[Union[str, Path]] = None,
    normalize_weight: bool = False,
    fill_dtm: bool = False,
    save_components: bool = False,
    n_workers: Optional[int] = None,
    chunk_size: int = 1024,
    save_run_log: bool = True,
    log_func=print
) -> Path:
    """
    High-level Python API to compute the Index of Sediment Connectivity (IC).

    :param dtm: Path to input Digital Terrain Model (GeoTIFF)
    :param output: Path to output IC raster (GeoTIFF)
    :param cell_size: Pixel size in meters (extracted automatically from DTM if None)
    :param target: Path to target shapefile (streams, outlets, dams, etc.) [Optional]
    :param sink: Path to sink shapefile (depressions, retention ponds) [Optional]
    :param auto_weight: Use automatic Cavalli (2013) surface roughness weighting factor
    :param window_size: Moving window size for surface roughness (odd integer >= 3)
    :param custom_weight: Path to custom user weight raster (if auto_weight is False)
    :param normalize_weight: Log-normalize weight factor
    :param fill_dtm: Fill depressions via Priority-Flood algorithm before routing
    :param save_components: Save D_up, D_down, Roughness, and Weight rasters
    :param n_workers: Number of parallel CPU workers (default: auto)
    :param chunk_size: Chunk size in pixels for parallel tile processing
    :param save_run_log: Save execution record to sedinconnect_runs.log
    :param log_func: Callback function for progress logging
    :return: Path to computed IC raster
    """
    dtm_p = Path(dtm)
    out_p = Path(output)

    if cell_size is None or cell_size <= 0:
        from .utils.raster import LargeFileRasterReader
        with LargeFileRasterReader(dtm_p) as r:
            cell_size = abs(r.geotransform[1])

    params = ProcessingParams(
        dtm_path=dtm_p,
        cell_size=float(cell_size),
        output_path=out_p,
        weight_path=Path(custom_weight) if custom_weight else None,
        target_path=Path(target) if target else None,
        sink_path=Path(sink) if sink else None,
        use_cavalli_weight=auto_weight,
        normalize_weight=normalize_weight,
        save_components=save_components,
        window_size=int(window_size),
        fill_dtm=fill_dtm,
        n_workers=n_workers,
        chunk_size=chunk_size,
        show_preview=False,
        save_run_log=save_run_log
    )

    processor = ConnectivityProcessor(log_func=log_func)
    processor.process(params)
    return out_p
