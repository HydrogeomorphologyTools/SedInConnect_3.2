import os
import shutil
import numpy as np
from pathlib import Path

from sedinconnect.utils.raster import LargeFileRasterReader, save_raster
from sedinconnect.utils.vector import rasterize_vector, rasterize_vector_burn
from sedinconnect.utils.params import ProcessingParams
from sedinconnect.core.taudem import TauDEMRunner
from sedinconnect.core.hydrology import propagate_d8_codes, compute_weighted_flow_length
from sedinconnect.core.weight import WeightCalculator

class ConnectivityProcessor:
    """Orchestrates the connectivity computation workflow"""
    
    def __init__(self, log_func=print):
        self.log = log_func
        self.taudem = TauDEMRunner(log_func)
        self.weight_calc = WeightCalculator(log_func)

    def process(self, params: ProcessingParams):
        """Execute processing based on parameters"""
        self.log("Starting process...")

        # 0. Filter DTM (values < 0 or > 9000 to NoData)
        self.log("Filtering DTM (masking values < 0 or > 9000)...")
        filtered_dtm_path = self.filter_dtm(params.dtm_path)
        if filtered_dtm_path:
            params.original_dtm_path = params.dtm_path
            params.dtm_path = filtered_dtm_path

        # 1. Handle Sinks
        sink_flag = 0
        if params.sink_path:
            self.log("Sinks detected, starting extraction...")
            self.process_sinks(params.dtm_path, params.sink_path)
            # Update DTM path to sinked version
            # If we already filtered, original_dtm_path is already set
            if params.original_dtm_path is None:
                params.original_dtm_path = params.dtm_path
            params.dtm_path = params.dtm_path.parent / "sinked_dtm.tif"
            sink_flag = 1

        try:
            # 2. Handle Weight
            if params.use_cavalli_weight:
                self.log("Computing Cavalli weighting factor...")
                weight_out = params.dtm_path.parent / "weight.tif"
                roughness_out = params.dtm_path.parent / "roughness.tif"
                params.weight_path = self.weight_calc.compute(
                    params.dtm_path, params.window_size,
                    weight_out, roughness_out,
                    params.normalize_weight, sink_flag
                )
                params.roughness_path = roughness_out
                params.weight_output_path = weight_out

            # 3. Compute Connectivity
            if params.target_path:
                self.log("Computing connectivity to TARGETS...")
                self.compute_connectivity_targets(
                    params.dtm_path, params.cell_size,
                    params.target_path, params.weight_path,
                    params.output_path, params.save_components,
                    sink_flag
                )
            else:
                self.log("Computing connectivity to OUTLET...")
                self.compute_connectivity_outlet(
                    params.dtm_path, params.cell_size,
                    params.weight_path, params.output_path,
                    params.save_components, sink_flag
                )

            self.log("Processing successfully completed!")
        finally:
            # Cleanup filtered DTM if it was created
            if filtered_dtm_path and filtered_dtm_path.exists():
                try:
                    os.remove(filtered_dtm_path)
                    self.log("Cleaned up filtered DTM.")
                except Exception as e:
                    self.log(f"Warning: Could not remove filtered DTM: {e}")
            
            # Restore original DTM path in params if it was changed
            if params.original_dtm_path:
                params.dtm_path = params.original_dtm_path

    def filter_dtm(self, dtm_path: Path) -> Path:
        """Set values < 0 and > 9000 to NoData and save to a temporary file"""
        # Ensure we have a Path object
        dtm_path = Path(dtm_path)
        with LargeFileRasterReader(dtm_path) as reader:
            tif_ar = reader.read_array()
            geotransform = reader.geotransform
            projection = reader.projection
            ndv_dtm = reader.nodata

        # Define output NoData value
        mask_nodata = ndv_dtm if (ndv_dtm is not None and not np.isnan(ndv_dtm)) else -9999
        
        # Identify existing NoData pixels (to preserve them)
        if ndv_dtm is not None:
            if np.isnan(ndv_dtm):
                existing_nodata = np.isnan(tif_ar)
            else:
                # Use a small tolerance for float comparison if not NaN
                existing_nodata = np.isclose(tif_ar, ndv_dtm, atol=1e-10)
        else:
            existing_nodata = np.zeros_like(tif_ar, dtype=bool)

        # Identify pixels to filter (outside [0, 9000]) that are NOT already NoData
        to_filter = ((tif_ar < 0) | (tif_ar > 9000)) & ~existing_nodata
        
        if np.any(to_filter):
            num_filtered = np.sum(to_filter)
            self.log(f"Found {num_filtered} pixels outside range [0, 9000]. Setting to NoData.")
            
            # Apply mask: existing NoData + newly filtered
            tif_ar[existing_nodata | to_filter] = mask_nodata
            
            out_path = dtm_path.parent / "filtered_dtm.tif"
            self.log(f"Saving filtered DTM to: {out_path}")
            save_raster(tif_ar, out_path, geotransform, projection, mask_nodata)
            return out_path
        else:
            self.log("No new pixels found outside range [0, 9000].")
            return None

    def process_sinks(self, dtm_path: Path, sink_path: Path):
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

        # Compute D8 flow direction
        self.log("Computing D8 flow direction...")
        p_file = str(dtm_path)[:-4] + "p.tif"
        sd8_file = str(dtm_path)[:-4] + "sd8.tif"
        self.taudem.run('D8Flowdir', f'-p {p_file} -sd8 {sd8_file} -fel {dtm_path}')

        # Compute Dinf flow direction
        self.log("Computing Dinf flow direction...")
        ang_file = str(dtm_path)[:-4] + "ang.tif"
        slp_file = str(dtm_path)[:-4] + "slp.tif"
        self.taudem.run('DinfFlowdir', f'-ang {ang_file} -slp {slp_file} -fel {dtm_path}')

        # Load flow direction (RAW for propagation)
        with LargeFileRasterReader(Path(p_file)) as fdir_reader:
            tif_fdir8_ar = fdir_reader.read_array()
            ndv_fdir8 = fdir_reader.nodata

        # Load slope D8
        with LargeFileRasterReader(Path(sd8_file)) as sd8_reader:
            tif_sd8_ar = sd8_reader.read_array()

        # Load Dinf
        with LargeFileRasterReader(Path(ang_file)) as ang_reader:
            tif_dirinf_ar = ang_reader.read_array()

        self.log("Computing sink watersheds extraction...")

        # Propagate sink codes
        SK_m = propagate_d8_codes(tif_fdir8_ar, sink_ar, ndv_fdir8, self.log)

        # Mask DTM where sinks exist
        mask_nodata = ndv_dtm if ndv_dtm is not None else -9999
        tif_ar[SK_m > 0] = mask_nodata

        # Mask flow directions
        tif_fdir8_ar[SK_m > 0] = -9999
        tif_sd8_ar[SK_m > 0] = -9999
        tif_dirinf_ar[SK_m > 0] = -9999

        # Save outputs
        self.log("Saving sinked rasters...")
        save_raster(tif_ar, dir_path / "sinked_dtm.tif", geotransform, projection, mask_nodata)
        save_raster(tif_fdir8_ar, dir_path / "sinked_fdir8.tif", geotransform, projection, -9999)
        save_raster(tif_sd8_ar, dir_path / "sinked_sd8.tif", geotransform, projection, -9999)
        save_raster(tif_dirinf_ar, dir_path / "sinked_dirinf.tif", geotransform, projection, -9999)

        # Cleanup
        os.remove(sink_raster)
        os.remove(ang_file)
        os.remove(slp_file)

        self.log("Sinks computation concluded successfully!")

    def compute_connectivity_outlet(self, dtm_path: Path, cell_size: float,
                                    weight_path: Path, output_path: Path,
                                    save_components: bool, sink_flag: int):
        """Compute connectivity to outlet"""
        dir_path = dtm_path.parent
        filename = str(dtm_path)

        with LargeFileRasterReader(dtm_path) as reader:
            tif_ar = reader.read_array()
            geotransform = reader.geotransform
            projection = reader.projection
            ndv_dtm = reader.nodata

        if ndv_dtm is not None:
            tif_ar[tif_ar == ndv_dtm] = np.nan
        else:
            ndv_dtm = -9999

        if sink_flag == 0:
            self.log("Computing D8 flow direction...")
            p_file = filename[:-4] + "p.tif"
            sd8_file = filename[:-4] + "sd8.tif"
            self.taudem.run('D8Flowdir', f'-p {p_file} -sd8 {sd8_file} -fel {dtm_path}')

            self.log("Computing Dinf flow direction...")
            ang_file = filename[:-4] + "ang.tif"
            slp_file = filename[:-4] + "slp.tif"
            self.taudem.run('DinfFlowdir', f'-ang {ang_file} -slp {slp_file} -fel {dtm_path}')
            os.remove(slp_file)
        else:
            p_file = filename[:-4] + "p.tif"
            sd8_file = filename[:-4] + "sd8.tif"
            ang_file = filename[:-4] + "ang.tif"
            shutil.copy2(dir_path / "sinked_fdir8.tif", p_file)
            shutil.copy2(dir_path / "sinked_sd8.tif", sd8_file)
            shutil.copy2(dir_path / "sinked_dirinf.tif", ang_file)

        with LargeFileRasterReader(Path(p_file)) as fdir_reader:
            tif_fdir8_ar = fdir_reader.read_array()
            ndv_fdir8 = fdir_reader.nodata

        with LargeFileRasterReader(Path(sd8_file)) as sd8_reader:
            tif_sd8_ar = sd8_reader.read_array()

        if ndv_fdir8 is not None:
            tif_fdir8_ar[tif_fdir8_ar == ndv_fdir8] = np.nan

        tif_sd8_ar[(tif_sd8_ar >= 0) & (tif_sd8_ar < 0.005)] = 0.005
        tif_sd8_ar[tif_sd8_ar > 1] = 1
        
        s_file = filename[:-4] + "s.tif"
        save_raster(tif_sd8_ar, Path(s_file), geotransform, projection)

        with LargeFileRasterReader(weight_path) as weight_reader:
            tif_wgt_ar = weight_reader.read_array()

        self.log("Computing downslope component (weighted flow length)...")
        Ws_1 = 1.0 / (tif_wgt_ar * tif_sd8_ar)
        D_down_ar = compute_weighted_flow_length(tif_fdir8_ar, Ws_1, cell_size, self.log)
        D_down_ar[D_down_ar == 0] = 1

        self.log("Computing Dinf flow accumulation...")
        sca_file = filename[:-4] + "sca.tif"
        self.taudem.run('AreaDinf', f'-ang {ang_file} -sca {sca_file} -nc')

        accW_file = str(dir_path / "accW.tif")
        self.taudem.run('AreaDinf', f'-ang {ang_file} -sca {accW_file} -wg {weight_path} -nc')

        accS_file = str(dir_path / "accS.tif")
        self.taudem.run('AreaDinf', f'-ang {ang_file} -sca {accS_file} -wg {s_file} -nc')

        with LargeFileRasterReader(Path(sca_file)) as sca_reader:
            tif_sca_ar = sca_reader.read_array()
        with LargeFileRasterReader(Path(accW_file)) as accW_reader:
            acc_W_ar = accW_reader.read_array()
        with LargeFileRasterReader(Path(accS_file)) as accS_reader:
            acc_S_ar = accS_reader.read_array()

        acc_final_ar = tif_sca_ar / cell_size
        C_mean_ar = (acc_W_ar + tif_wgt_ar) / acc_final_ar
        S_mean_ar = (acc_S_ar + tif_sd8_ar) / acc_final_ar
        cell_area = cell_size ** 2
        D_up_ar = C_mean_ar * S_mean_ar * np.sqrt(acc_final_ar * cell_area)

        self.log("Computing connectivity index...")
        ic_ar = np.log10(D_up_ar / D_down_ar)

        self.log("Saving connectivity index...")
        save_raster(ic_ar, output_path, geotransform, projection)

        if save_components:
            self.log("Saving upslope and downslope components...")
            save_raster(D_up_ar, dir_path / "D_up.tif", geotransform, projection)
            save_raster(D_down_ar, dir_path / "D_down.tif", geotransform, projection)

        # Cleanup
        temp_files = [p_file, sd8_file, ang_file, sca_file, accW_file, accS_file, s_file]
        for f in temp_files:
            if Path(f).exists():
                try: os.remove(f)
                except: pass

        if sink_flag == 1:
            for f in ["sinked_dtm.tif", "sinked_fdir8.tif", "sinked_sd8.tif", "sinked_dirinf.tif"]:
                try: os.remove(dir_path / f)
                except: pass

    def compute_connectivity_targets(self, dtm_path: Path, cell_size: float,
                                     target_path: Path, weight_path: Path,
                                     output_path: Path, save_components: bool,
                                     sink_flag: int):
        """Compute connectivity to targets (strictly following v2.3 logic)"""

        dir_path = dtm_path.parent
        filename = str(dtm_path)

        with LargeFileRasterReader(dtm_path) as reader:
            tif_ar = reader.read_array()
            geotransform = reader.geotransform
            projection = reader.projection
            ndv_dtm = reader.nodata

        if ndv_dtm is not None:
            tif_ar[tif_ar == ndv_dtm] = np.nan
        else:
            ndv_dtm = -9999

        self.log("Rasterizing target shapefile...")
        target_raster = dir_path / "targets.tif"
        rasterize_vector_burn(target_path, target_raster, dtm_path)

        with LargeFileRasterReader(target_raster) as target_reader:
            target_ar = target_reader.read_array()

        if sink_flag == 0:
            self.log("Computing D8 flow direction...")
            p_file_orig = filename[:-4] + "p.tif"
            sd8_file_orig = filename[:-4] + "sd8.tif"
            for f in [p_file_orig, sd8_file_orig]:
                if Path(f).exists(): os.remove(f)
            self.taudem.run('D8Flowdir', f'-p {p_file_orig} -sd8 {sd8_file_orig} -fel {dtm_path}')

            self.log("Computing Dinf flow direction...")
            angt_file = filename[:-4] + "angt.tif"
            slp_file = filename[:-4] + "slp.tif"
            if Path(angt_file).exists(): os.remove(angt_file)
            self.taudem.run('DinfFlowdir', f'-ang {angt_file} -slp {slp_file} -fel {dtm_path}')
            if Path(slp_file).exists(): os.remove(slp_file)
        else:
            p_file_orig = filename[:-4] + "p.tif" 
            sd8_file_orig = filename[:-4] + "sd8.tif"
            angt_file = filename[:-4] + "angt.tif"
            shutil.copy2(dir_path / "sinked_fdir8.tif", p_file_orig)
            shutil.copy2(dir_path / "sinked_sd8.tif", sd8_file_orig)
            shutil.copy2(dir_path / "sinked_dirinf.tif", angt_file)

        p_file = filename[:-4] + "p_tg.tif"
        with LargeFileRasterReader(Path(p_file_orig)) as fdir_reader:
            tif_fdir8_ar = fdir_reader.read_array()
            ndv_fdir8 = fdir_reader.nodata

        tif_fdir8_ar_prop = tif_fdir8_ar.copy()
        tif_fdir8_ar_prop[target_ar == 10] = -1000
        
        tif_fdir8_ar_taudem = tif_fdir8_ar.copy()
        tif_fdir8_ar_taudem[target_ar == 10] = -1000
        if ndv_fdir8 is not None:
            tif_fdir8_ar_taudem[tif_fdir8_ar_taudem == ndv_fdir8] = -9999
        save_raster(tif_fdir8_ar_taudem, Path(p_file), geotransform, projection, -9999)

        ang_file = filename[:-4] + "ang.tif"
        with LargeFileRasterReader(Path(angt_file)) as angt_reader:
            tif_fdirinf_ar = angt_reader.read_array()
            ndv_ang = angt_reader.nodata

        tif_fdirinf_ar_taudem = tif_fdirinf_ar.copy()
        tif_fdirinf_ar_taudem[target_ar == 10] = -1000
        if ndv_ang is not None:
            tif_fdirinf_ar_taudem[tif_fdirinf_ar_taudem == ndv_ang] = -9999
        save_raster(tif_fdirinf_ar_taudem, Path(ang_file), geotransform, projection, -9999)

        with LargeFileRasterReader(Path(sd8_file_orig)) as sd8_reader:
            tif_sd8_ar = sd8_reader.read_array()
        tif_sd8_ar[(tif_sd8_ar >= 0) & (tif_sd8_ar < 0.005)] = 0.005
        tif_sd8_ar[tif_sd8_ar > 1] = 1
        tif_sd8_ar[tif_sd8_ar < 0] = -1
        s_file = filename[:-4] + "s.tif"
        save_raster(tif_sd8_ar, Path(s_file), geotransform, projection)

        with LargeFileRasterReader(weight_path) as weight_reader:
            tif_wgt_ar = weight_reader.read_array()

        self.log("Computing downslope component to targets...")
        Ws_1 = 1.0 / (tif_wgt_ar * tif_sd8_ar)
        
        tif_fdir8_ar_for_prop = np.full_like(tif_fdir8_ar_prop, -9999.0)
        mask_valid = (tif_fdir8_ar_prop >= 1) & (tif_fdir8_ar_prop <= 8)
        tif_fdir8_ar_for_prop[mask_valid] = tif_fdir8_ar_prop[mask_valid]
        tif_fdir8_ar_for_prop[tif_fdir8_ar_prop == -1000] = np.nan
        
        D_down_ar = compute_weighted_flow_length(tif_fdir8_ar_for_prop, Ws_1, cell_size, self.log)
        D_down_ar[D_down_ar == 0] = 1
        D_down_ar[D_down_ar < 0] = np.nan
        D_down_ar[target_ar == 10] = np.nan 

        self.log("Computing upslope component...")
        sca_file = filename[:-4] + "sca.tif"
        self.taudem.run('AreaDinf', f'-ang {ang_file} -sca {sca_file} -nc')
        accW_file = str(dir_path / "accW.tif")
        self.taudem.run('AreaDinf', f'-ang {ang_file} -sca {accW_file} -wg {weight_path} -nc')
        accS_file = str(dir_path / "accS.tif")
        self.taudem.run('AreaDinf', f'-ang {ang_file} -sca {accS_file} -wg {s_file} -nc')

        with LargeFileRasterReader(Path(sca_file)) as sca_reader:
            tif_sca_ar = sca_reader.read_array()
        with LargeFileRasterReader(Path(accW_file)) as accW_reader:
            acc_W_ar = accW_reader.read_array()
        with LargeFileRasterReader(Path(accS_file)) as accS_reader:
            acc_S_ar = accS_reader.read_array()

        acc_final_ar = tif_sca_ar / cell_size
        C_mean_ar = (acc_W_ar + tif_wgt_ar) / acc_final_ar
        S_mean_ar = (acc_S_ar + tif_sd8_ar) / acc_final_ar

        const_ar = np.full_like(tif_ar, -1.0)
        const_ar[~np.isnan(tif_ar)] = cell_size
        in_pos_cos = np.where(const_ar >= 0)
        const_ar[in_pos_cos] = (const_ar[in_pos_cos]) ** 2
        cell_area = const_ar

        D_up_ar = C_mean_ar * S_mean_ar * np.sqrt(acc_final_ar * cell_area)
        D_up_ar[target_ar == 10] = np.nan

        self.log("Computing connectivity index to targets...")
        ic_ar = np.log10(D_up_ar / D_down_ar)

        self.log("Saving connectivity index...")
        save_raster(ic_ar, output_path, geotransform, projection, -9999)

        if save_components:
            self.log("Saving upslope and downslope components...")
            save_raster(D_up_ar, dir_path / "D_up.tif", geotransform, projection)
            save_raster(D_down_ar, dir_path / "D_down.tif", geotransform, projection)

        self.log("Cleaning up temporary files...")
        temp_files = [p_file, s_file, ang_file, angt_file, sca_file, accW_file, accS_file, 
                     target_raster, filename[:-4]+"ad8.tif", filename[:-4]+"p.tif", filename[:-4]+"sd8.tif"]
        for f in temp_files:
            if Path(f).exists():
                try: os.remove(f)
                except: pass

        if sink_flag == 1:
            for f in ["sinked_dtm.tif", "sinked_fdir8.tif", "sinked_sd8.tif", "sinked_dirinf.tif"]:
                try: os.remove(dir_path / f)
                except: pass
