import os
import sys
import shutil
import time
import numpy as np
from pathlib import Path
from typing import Optional, List

from sedinconnect.utils.params import ProcessingParams
from sedinconnect.utils.raster import LargeFileRasterReader, save_raster
from sedinconnect.utils.vector import rasterize_vector, rasterize_vector_burn
from sedinconnect.utils.telemetry import track_analysis_run
from sedinconnect.core.weight import WeightCalculator
from sedinconnect.core.hydrology import propagate_d8_codes, compute_weighted_flow_length
from sedinconnect.core.native.pitfill import fill_dem
from sedinconnect.core.native.d8flowdir import compute_d8_flowdir
from sedinconnect.core.native.dinfflowdir import compute_dinf_flowdir
from sedinconnect.core.native.areadinf import accumulate_dinf_multi

# Target raster burn value matching TauDEM/SedInConnect standard
TARGET_BURN_VALUE = 10
TARGET_MASK_CODE = -1000.0


class ConnectivityProcessor:
    """
    Core engine for sediment connectivity index (IC) calculation.
    """

    def __init__(self, log_func=print):
        self._user_log = log_func
        self.log_history: List[str] = []
        self.weight_calc = WeightCalculator(self.log)

    def log(self, msg):
        self.log_history.append(str(msg))
        if self._user_log:
            try:
                self._user_log(msg)
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def process(self, params: ProcessingParams):
        """Execute processing based on parameters"""
        self.log_history.clear()
        t_start = time.time()
        status = "COMPLETED"
        error_detail = None
        filtered_dtm_path = None

        try:
            self.log("Starting process...")

            # 0. Filter DTM (values < 0 or > 9000 to NoData)
            self.log("Filtering DTM (masking values < 0 or > 9000)...")
            filtered_dtm_path = self.filter_dtm(params.dtm_path)
            if filtered_dtm_path:
                params.original_dtm_path = params.dtm_path
                params.dtm_path = filtered_dtm_path

            # 1. Optional pit filling
            if params.fill_dtm:
                self.log("Filling DTM depressions (pit removal)...")
                with LargeFileRasterReader(params.dtm_path) as reader:
                    dem_arr = reader.read_array()
                    geotransform = reader.geotransform
                    projection = reader.projection
                    ndv = reader.nodata if reader.nodata is not None else -9999.0
                filled_arr = fill_dem(dem_arr, nodata=ndv, log_func=self.log)
                filled_path = params.dtm_path.parent / f"{params.dtm_path.stem}_filled.tif"
                save_raster(filled_arr, filled_path, geotransform, projection, ndv)
                params.dtm_path = filled_path
                self.log(f"  Filled DTM saved to: {filled_path}")

            # 2. Handle Sinks
            sink_flag = 0
            if params.sink_path:
                self.log("Sinks detected, starting extraction...")
                self.process_sinks(params.dtm_path, params.sink_path, params.cell_size)
                if params.original_dtm_path is None:
                    params.original_dtm_path = params.dtm_path
                params.dtm_path = params.dtm_path.parent / "sinked_dtm.tif"
                sink_flag = 1

            # 3. Handle Weight
            if params.use_cavalli_weight:
                self.log("Computing Cavalli weighting factor...")
                weight_out = Path(params.weight_output_path) if params.weight_output_path else (params.dtm_path.parent / "weight.tif")
                roughness_out = Path(params.roughness_path) if params.roughness_path else (params.dtm_path.parent / "roughness.tif")
                params.weight_path = self.weight_calc.compute(
                    params.dtm_path, params.window_size,
                    weight_out, roughness_out,
                    params.normalize_weight, sink_flag,
                    n_workers=getattr(params, 'n_workers', None),
                    chunk_size=getattr(params, 'chunk_size', 1024)
                )
                params.roughness_path = roughness_out
                params.weight_output_path = weight_out

            # 4. Compute Connectivity
            if params.target_path:
                self.log("Computing connectivity to TARGETS...")
                self.compute_connectivity_targets(
                    params.dtm_path, params.cell_size,
                    params.target_path, params.weight_path,
                    params.output_path, params.save_components,
                    sink_flag, params
                )
            else:
                self.log("Computing connectivity to OUTLET...")
                self.compute_connectivity_outlet(
                    params.dtm_path, params.cell_size,
                    params.weight_path, params.output_path,
                    params.save_components, sink_flag, params
                )

            self.log("Processing successfully completed!")
        except Exception as e:
            status = "FAILED"
            import traceback
            error_detail = traceback.format_exc()
            raise e
        finally:
            elapsed = time.time() - t_start
            self._write_run_log(params, t_start, elapsed, status, error_detail)
            try:
                track_analysis_run(
                    mode="GUI" if getattr(params, 'show_preview', True) else "CLI",
                    target_mode="targets" if params.target_path else "outlet",
                    weight_mode="cavalli_auto" if params.use_cavalli_weight else "custom",
                    window_size=getattr(params, 'window_size', 5),
                    fill_dtm=getattr(params, 'fill_dtm', False),
                    duration_s=elapsed,
                    status=status.lower()
                )
            except Exception:
                pass
            if filtered_dtm_path and filtered_dtm_path.exists():
                try:
                    filtered_dtm_path.unlink(missing_ok=True)
                    self.log("Cleaned up filtered DTM.")
                except Exception as e:
                    self.log(f"Warning: Could not remove filtered DTM: {e}")
            if params.original_dtm_path:
                params.dtm_path = params.original_dtm_path

    def _write_run_log(self, params: ProcessingParams, start_time: float, elapsed: float, status: str, error_msg: Optional[str] = None):
        """Append a structured execution record to sedinconnect_runs.log in application dir and output dir"""
        if not getattr(params, 'save_run_log', True):
            return
        try:
            target_dirs = []

            # 1. Application directory (where exe or script is located)
            if getattr(sys, 'frozen', False):
                app_dir = Path(sys.executable).parent
            else:
                app_dir = Path(__file__).resolve().parent.parent.parent
            if app_dir.exists():
                target_dirs.append(app_dir)

            # 2. Output raster directory (if different from app_dir)
            if params.output_path:
                try:
                    out_dir = Path(params.output_path).parent
                    if out_dir.exists() and out_dir not in target_dirs:
                        target_dirs.append(out_dir)
                except Exception:
                    pass

            now_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(start_time))
            entry_text = (
                "=" * 80 + "\n"
                f"[RUN LOG ENTRY] - {now_str}\n"
                f"Software:        SedInConnect 3.2 (Morpheus PRIN 2023-2026 Project)\n"
                f"Execution State: {status} (Elapsed Time: {elapsed:.2f} s)\n"
                "\n--- INPUTS & PARAMETERS ---\n"
                f"DTM Raster:      {params.dtm_path}\n"
                f"Cell Size:       {params.cell_size} m\n"
                f"Target Feature:  {params.target_path if params.target_path else 'None (Catchment Outlet Mode)'}\n"
                f"Sink Feature:    {params.sink_path if params.sink_path else 'None'}\n"
                f"Weight Option:   {'Automatic Cavalli (2013) Roughness' if params.use_cavalli_weight else f'Custom Raster ({params.weight_path})'}\n"
                f"Window Size:     {params.window_size}x{params.window_size} px\n"
                f"Log-Normalize W: {params.normalize_weight}\n"
                f"Fill DTM Pits:   {params.fill_dtm}\n"
                f"CPU Workers:     {params.n_workers if params.n_workers else 'Auto'}\n"
                f"Chunk Size:      {params.chunk_size} px\n"
                "\n--- OUTPUTS ---\n"
                f"Connectivity IC: {params.output_path}\n"
            )
            if params.roughness_path: entry_text += f"Roughness RI:    {params.roughness_path}\n"
            if params.weight_output_path: entry_text += f"Weight Factor W: {params.weight_output_path}\n"
            if params.d_up_path: entry_text += f"D_up Raster:     {params.d_up_path}\n"
            if params.d_down_path: entry_text += f"D_down Raster:   {params.d_down_path}\n"
            if error_msg:
                entry_text += f"\n--- ERROR DETAILS ---\n{error_msg}\n"
            entry_text += "\n--- EXECUTION LOG ---\n"
            for line in self.log_history:
                entry_text += f"  {line}\n"
            entry_text += "=" * 80 + "\n\n"

            for t_dir in target_dirs:
                try:
                    log_file = t_dir / "sedinconnect_runs.log"
                    with open(log_file, "a", encoding="utf-8") as f:
                        f.write(entry_text)
                except Exception:
                    pass
        except Exception:
            pass

    def filter_dtm(self, dtm_path: Path) -> Optional[Path]:
        """Set values < 0 and > 9000 to NoData and save to a temporary file"""
        dtm_path = Path(dtm_path)
        self.log(f"filter_dtm: opening raster {dtm_path}...")
        with LargeFileRasterReader(dtm_path) as reader:
            tif_ar = reader.read_array()
            geotransform = reader.geotransform
            projection = reader.projection
            ndv_dtm = reader.nodata
        self.log(f"filter_dtm: read array shape {tif_ar.shape}, nodata={ndv_dtm}")

        mask_nodata = ndv_dtm if (ndv_dtm is not None and not np.isnan(ndv_dtm)) else -9999
        if ndv_dtm is not None and not np.isnan(ndv_dtm):
            existing_nodata = np.isnan(tif_ar) | np.isclose(tif_ar, ndv_dtm, atol=1e-10)
        else:
            existing_nodata = np.isnan(tif_ar)

        with np.errstate(invalid='ignore'):
            to_filter = ((tif_ar < 0) | (tif_ar > 9000)) & ~existing_nodata
        if np.any(to_filter):
            num_filtered = np.sum(to_filter)
            self.log(f"Found {num_filtered} pixels outside range [0, 9000]. Setting to NoData.")
            tif_ar[existing_nodata | to_filter] = mask_nodata
            out_path = dtm_path.parent / "filtered_dtm.tif"
            self.log(f"Saving filtered DTM to: {out_path}")
            save_raster(tif_ar, out_path, geotransform, projection, mask_nodata)
            return out_path
        else:
            self.log("No new pixels found outside range [0, 9000].")
            return None

    # ------------------------------------------------------------------
    # Sink processing
    # ------------------------------------------------------------------

    def process_sinks(self, dtm_path: Path, sink_path: Path, cell_size: float = 1.0):
        """Process sink watersheds"""
        self.log("Opening DTM for sinks processing...")

        with LargeFileRasterReader(dtm_path) as reader:
            tif_ar = reader.read_array()
            geotransform = reader.geotransform
            projection = reader.projection
            ndv_dtm = reader.nodata

        dir_path = dtm_path.parent

        # Rasterize sinks
        self.log("Rasterizing sink shapefile...")
        sink_raster = dir_path / "sinks.tif"
        rasterize_vector(sink_path, sink_raster, dtm_path, "sink_id", self.log)

        with LargeFileRasterReader(sink_raster) as sink_reader:
            sink_ar = sink_reader.read_array()

        # Compute D8 flow direction (native)
        self.log("Computing D8 flow direction (native)...")
        ndv_val = float(ndv_dtm) if ndv_dtm is not None else -9999.0
        tif_fdir8_ar, tif_sd8_ar = compute_d8_flowdir(
            tif_ar, cell_size=cell_size, nodata=ndv_val, log_func=self.log)

        # Compute Dinf flow direction (native)
        self.log("Computing D-infinity flow direction (native)...")
        tif_dirinf_ar, _ = compute_dinf_flowdir(
            tif_ar, cell_size=cell_size, nodata=ndv_val, log_func=self.log)

        self.log("Computing sink watersheds extraction...")

        # Propagate sink codes
        SK_m = propagate_d8_codes(tif_fdir8_ar, sink_ar, ndv_fdir=-9999.0, log_func=self.log)

        # Mask DTM where sinks exist
        mask_nodata = ndv_dtm if ndv_dtm is not None else -9999
        tif_ar[SK_m > 0] = mask_nodata
        tif_fdir8_ar[SK_m > 0] = -9999
        tif_sd8_ar[SK_m > 0] = -9999
        tif_dirinf_ar[SK_m > 0] = -9999

        # Save outputs
        self.log("Saving sinked rasters...")
        save_raster(tif_ar, dir_path / "sinked_dtm.tif",
                    geotransform, projection, mask_nodata)
        save_raster(tif_fdir8_ar, dir_path / "sinked_fdir8.tif",
                    geotransform, projection, -9999)
        save_raster(tif_sd8_ar, dir_path / "sinked_sd8.tif",
                    geotransform, projection, -9999)
        save_raster(tif_dirinf_ar, dir_path / "sinked_dirinf.tif",
                    geotransform, projection, -9999)

        # Cleanup
        if sink_raster.exists():
            sink_raster.unlink(missing_ok=True)
        self.log("Sinks computation concluded successfully!")

    # ------------------------------------------------------------------
    # Unified Connectivity Engine (shared between Outlet & Targets)
    # ------------------------------------------------------------------

    def _compute_connectivity_core(self, dtm_path: Path, cell_size: float,
                                  weight_path: Path, output_path: Path,
                                  save_components: bool, sink_flag: int,
                                  target_path: Optional[Path] = None,
                                  params: Optional[ProcessingParams] = None):
        """
        Unified computation of sediment connectivity index (IC).
        Handles both Outlet and Target modes cleanly with zero code duplication.
        """
        dir_path = dtm_path.parent
        stem = dtm_path.stem

        with LargeFileRasterReader(dtm_path) as reader:
            tif_ar = reader.read_array()
            geotransform = reader.geotransform
            projection = reader.projection
            ndv_dtm = reader.nodata

        if ndv_dtm is not None:
            tif_ar[tif_ar == ndv_dtm] = np.nan
        else:
            ndv_dtm = -9999

        ndv_val = float(ndv_dtm)
        temp_files: List[Path] = []

        # Target rasterization if applicable
        target_ar = None
        target_raster = None
        if target_path:
            self.log("Rasterizing target shapefile...")
            target_raster = dir_path / "targets.tif"
            rasterize_vector_burn(target_path, target_raster, dtm_path)
            temp_files.append(target_raster)
            with LargeFileRasterReader(target_raster) as target_reader:
                target_ar = target_reader.read_array()

        # Step 1: Flow directions (D8 & Dinf)
        if sink_flag == 0:
            self.log("Computing D8 flow direction (native)...")
            tif_fdir8_ar, tif_sd8_ar = compute_d8_flowdir(
                tif_ar, cell_size=cell_size, nodata=ndv_val, log_func=self.log)

            p_file = dir_path / f"{stem}p.tif"
            sd8_file = dir_path / f"{stem}sd8.tif"
            save_raster(tif_fdir8_ar, p_file, geotransform, projection)
            save_raster(tif_sd8_ar, sd8_file, geotransform, projection)
            temp_files.extend([p_file, sd8_file])

            self.log("Computing D-infinity flow direction (native)...")
            tif_dirinf_ar, _ = compute_dinf_flowdir(
                tif_ar, cell_size=cell_size, nodata=ndv_val, log_func=self.log)

            ang_suffix = "angt.tif" if target_path else "ang.tif"
            ang_file = dir_path / f"{stem}{ang_suffix}"
            save_raster(tif_dirinf_ar, ang_file, geotransform, projection, nodata=-1.0)
            temp_files.append(ang_file)
        else:
            p_file = dir_path / f"{stem}p.tif"
            sd8_file = dir_path / f"{stem}sd8.tif"
            ang_suffix = "angt.tif" if target_path else "ang.tif"
            ang_file = dir_path / f"{stem}{ang_suffix}"
            shutil.copy2(dir_path / "sinked_fdir8.tif", p_file)
            shutil.copy2(dir_path / "sinked_sd8.tif", sd8_file)
            shutil.copy2(dir_path / "sinked_dirinf.tif", ang_file)
            temp_files.extend([p_file, sd8_file, ang_file])

            with LargeFileRasterReader(p_file) as fdir_reader:
                tif_fdir8_ar = fdir_reader.read_array()
            with LargeFileRasterReader(sd8_file) as sd8_reader:
                tif_sd8_ar = sd8_reader.read_array()
            with LargeFileRasterReader(ang_file) as ang_reader:
                tif_dirinf_ar = ang_reader.read_array()

        # Step 2: Target masking if applicable
        tif_dirinf_for_acc = tif_dirinf_ar.copy()
        if target_ar is not None:
            is_target = (target_ar == TARGET_BURN_VALUE)
            # Mask D8
            tif_fdir8_ar = tif_fdir8_ar.copy()
            tif_fdir8_ar[is_target] = TARGET_MASK_CODE
            p_tg_file = dir_path / f"{stem}p_tg.tif"
            save_raster(tif_fdir8_ar, p_tg_file, geotransform, projection, -9999)
            temp_files.append(p_tg_file)

            # Mask Dinf
            tif_dirinf_for_acc[is_target] = TARGET_MASK_CODE
            ang_tg_file = dir_path / f"{stem}ang.tif"
            save_raster(tif_dirinf_for_acc, ang_tg_file, geotransform, projection, -9999)
            temp_files.append(ang_tg_file)

        # Flow direction for propagation:
        # In Outlet mode: all boundary/non-valid cells are outlets (np.nan)
        # In Target mode: ONLY target cells are outlets (np.nan), non-target boundaries are -9999
        if target_path:
            tif_fdir8_for_prop = np.full_like(tif_fdir8_ar, -9999.0)
            mask_valid = (tif_fdir8_ar >= 1) & (tif_fdir8_ar <= 8)
            tif_fdir8_for_prop[mask_valid] = tif_fdir8_ar[mask_valid]
            tif_fdir8_for_prop[tif_fdir8_ar == TARGET_MASK_CODE] = np.nan
        else:
            tif_fdir8_for_prop = np.full_like(tif_fdir8_ar, np.nan)
            mask_valid = (tif_fdir8_ar >= 1) & (tif_fdir8_ar <= 8)
            tif_fdir8_for_prop[mask_valid] = tif_fdir8_ar[mask_valid]

        # Step 3: Clamp slope to [0.005, 1.0]
        tif_sd8_ar_clamped = tif_sd8_ar.copy()
        tif_sd8_ar_clamped[(tif_sd8_ar_clamped >= 0) & (tif_sd8_ar_clamped < 0.005)] = 0.005
        tif_sd8_ar_clamped[tif_sd8_ar_clamped > 1] = 1.0
        if target_path:
            tif_sd8_ar_clamped[tif_sd8_ar_clamped < 0] = -1.0

        s_file = dir_path / f"{stem}s.tif"
        save_raster(tif_sd8_ar_clamped, s_file, geotransform, projection)
        temp_files.append(s_file)

        # Read weight raster
        with LargeFileRasterReader(weight_path) as weight_reader:
            tif_wgt_ar = weight_reader.read_array()

        # Step 4: Downslope component (weighted flow length)
        msg_down = "Computing downslope component to targets..." if target_path else "Computing downslope component (weighted flow length)..."
        self.log(msg_down)
        Ws_1 = 1.0 / (tif_wgt_ar * tif_sd8_ar_clamped)
        D_down_ar = compute_weighted_flow_length(tif_fdir8_for_prop, Ws_1, cell_size, self.log)
        D_down_ar[D_down_ar == 0] = 1.0
        if target_path:
            D_down_ar[D_down_ar < 0] = np.nan
            if target_ar is not None:
                D_down_ar[target_ar == TARGET_BURN_VALUE] = np.nan

        # Step 5: Upslope component (AreaDinf single-pass multi-tensor)
        msg_up = "Computing upslope component (AreaDinf native unified pass)..." if target_path else "Computing D-infinity flow accumulation (native unified pass)..."
        self.log(msg_up)
        tif_sca_ar, acc_W_ar, acc_S_ar = accumulate_dinf_multi(
            tif_dirinf_for_acc, cell_size=cell_size,
            weight=tif_wgt_ar, slope=tif_sd8_ar_clamped,
            nodata_ang=-1.0, nodata_weight=-9999.0, log_func=self.log
        )

        # Save intermediate area rasters
        sca_file = dir_path / f"{stem}sca.tif"
        accW_file = dir_path / "accW.tif"
        accS_file = dir_path / "accS.tif"
        save_raster(tif_sca_ar, sca_file, geotransform, projection)
        save_raster(acc_W_ar, accW_file, geotransform, projection)
        save_raster(acc_S_ar, accS_file, geotransform, projection)
        temp_files.extend([sca_file, accW_file, accS_file])

        # Step 6: Compute IC
        with np.errstate(divide='ignore', invalid='ignore'):
            acc_final_ar = np.where(tif_sca_ar > 0, tif_sca_ar / cell_size, np.nan)
            C_mean_ar = (acc_W_ar + tif_wgt_ar) / acc_final_ar
            S_mean_ar = (acc_S_ar + tif_sd8_ar_clamped) / acc_final_ar
            cell_area = float(cell_size) ** 2
            D_up_ar = C_mean_ar * S_mean_ar * np.sqrt(np.maximum(acc_final_ar * cell_area, 0.0))

            if target_ar is not None:
                D_up_ar[target_ar == TARGET_BURN_VALUE] = np.nan

            msg_ic = "Computing connectivity index to targets..." if target_path else "Computing connectivity index..."
            self.log(msg_ic)
            ic_ar = np.log10(D_up_ar / D_down_ar)
            ic_ar[np.isnan(tif_ar) | np.isinf(ic_ar)] = np.nan

        # Save Connectivity Index
        self.log("Saving connectivity index...")
        save_raster(ic_ar, output_path, geotransform, projection, -9999)

        # Optional: Save components
        if save_components:
            self.log("Saving upslope and downslope components...")
            dup_out = Path(params.d_up_path) if (params and params.d_up_path) else (dir_path / "D_up.tif")
            ddown_out = Path(params.d_down_path) if (params and params.d_down_path) else (dir_path / "D_down.tif")
            save_raster(D_up_ar, dup_out, geotransform, projection, -9999)
            save_raster(D_down_ar, ddown_out, geotransform, projection, -9999)

        # Cleanup temporary files
        self.log("Cleaning up temporary files...")
        for f in temp_files:
            try:
                f.unlink(missing_ok=True)
            except Exception as e:
                self.log(f"Warning: Could not remove temporary file {f}: {e}")

        if sink_flag == 1:
            for fname in ["sinked_dtm.tif", "sinked_fdir8.tif",
                          "sinked_sd8.tif", "sinked_dirinf.tif"]:
                try:
                    (dir_path / fname).unlink(missing_ok=True)
                except Exception:
                    pass

    # ------------------------------------------------------------------
    # Outlet connectivity
    # ------------------------------------------------------------------

    def compute_connectivity_outlet(self, dtm_path: Path, cell_size: float,
                                    weight_path: Path, output_path: Path,
                                    save_components: bool, sink_flag: int,
                                    params: Optional[ProcessingParams] = None):
        """Compute connectivity to outlet"""
        self._compute_connectivity_core(
            dtm_path=dtm_path, cell_size=cell_size,
            weight_path=weight_path, output_path=output_path,
            save_components=save_components, sink_flag=sink_flag,
            target_path=None, params=params
        )

    # ------------------------------------------------------------------
    # Target connectivity
    # ------------------------------------------------------------------

    def compute_connectivity_targets(self, dtm_path: Path, cell_size: float,
                                     target_path: Path, weight_path: Path,
                                     output_path: Path, save_components: bool,
                                     sink_flag: int,
                                     params: Optional[ProcessingParams] = None):
        """Compute connectivity to targets (strictly following v2.3 / v3.0 logic)"""
        self._compute_connectivity_core(
            dtm_path=dtm_path, cell_size=cell_size,
            weight_path=weight_path, output_path=output_path,
            save_components=save_components, sink_flag=sink_flag,
            target_path=target_path, params=params
        )

