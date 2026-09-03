# -*- coding: utf-8 -*-
"""
SedInConnect 3.2 — ArcGIS Pro Python Toolbox (.pyt)
Stand-alone Sediment Connectivity Assessment in River Catchments.

Developed at:
CNR-IRPI Padova (National Research Council - Research Institute for Geo-Hydrological Protection)
Within the research activities of:
MORPHEUS - GeoMORPHomEtry throUgh Scales for a resilient landscape (PRIN 2022 / 2023-2026, Prot. 2022JEFZRM)
Funded by European Union - NextGenerationEU, MUR and Italia Domani (PNRR).

[TESTING / PREVIEW VERSION]
"""

import os
import sys
import time
import tempfile
from pathlib import Path

# Add toolbox directory to sys.path
try:
    _tb_dir = str(Path(__file__).resolve().parent)
except Exception:
    _tb_dir = os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else os.getcwd()

if _tb_dir not in sys.path:
    sys.path.insert(0, _tb_dir)
_pkg_sub = str(Path(_tb_dir) / "sedinconnect")
if _pkg_sub not in sys.path:
    sys.path.insert(0, _pkg_sub)

try:
    import arcpy
except ImportError:
    pass

from sedinconnect.utils.params import ProcessingParams
from sedinconnect.core.processor import ConnectivityProcessor
from sedinconnect.utils.telemetry import track_app_launch, track_analysis_run


def resolve_layer_or_gdb_raster(val_text, temp_dir):
    """Resolve ArcGIS layer, GDB raster, or disk path to a valid GeoTIFF on disk."""
    if not val_text:
        return None
    try:
        desc = arcpy.Describe(val_text)
        cat_path = getattr(desc, "catalogPath", val_text)
    except Exception:
        cat_path = val_text

    p = Path(cat_path)
    if p.exists() and p.is_file() and p.suffix.lower() in [".tif", ".tiff", ".img", ".asc"]:
        return p

    # If inside GDB or map layer, copy to temporary TIFF
    temp_tif = temp_dir / f"dtm_temp_{int(time.time())}.tif"
    arcpy.management.CopyRaster(val_text, str(temp_tif))
    return temp_tif


def resolve_layer_or_gdb_vector(val_text, temp_dir, prefix="target"):
    """Resolve ArcGIS layer, GDB feature class, or disk path to a valid shapefile."""
    if not val_text:
        return None
    try:
        desc = arcpy.Describe(val_text)
        cat_path = getattr(desc, "catalogPath", val_text)
    except Exception:
        cat_path = val_text

    p = Path(cat_path)
    if p.exists() and p.is_file() and p.suffix.lower() == ".shp":
        return p

    # If inside GDB or map layer, export to temporary Shapefile
    temp_shp = temp_dir / f"{prefix}_{int(time.time())}.shp"
    arcpy.management.CopyFeatures(val_text, str(temp_shp))
    return temp_shp


def resolve_raster_output(out_text, temp_dir, prefix="ic_out"):
    """If output destination is inside a GDB, write to temp GeoTIFF first, then import."""
    if not out_text:
        return None, False, None
    p = Path(out_text)
    if ".gdb" in str(p).lower() or not p.suffix:
        temp_out = temp_dir / f"{prefix}_{int(time.time())}.tif"
        return temp_out, True, out_text
    return p, False, out_text



def get_arcgis_numba_help_message():
    """Detect numpy/arcgis version and provide the exact command."""
    import numpy as np
    np_v = getattr(np, "__version__", "1.20")
    if np_v.startswith("2."):
        cmd = 'pip install --user numba'
    else:
        cmd = 'pip install --user "numpy<2" "numba>=0.56"'
    return (
        "\n------------------------------------------------------------\n"
        "⚠️ [PERFORMANCE NOTICE] 'numba' JIT compiler is not installed in your ArcGIS Pro environment.\n"
        "   SedInConnect is running in pure NumPy fallback mode (calculations are 100% exact but slower).\n\n"
        "   To achieve full 10x-20x JIT acceleration, open 'Python Command Prompt' (in Windows Start menu) and run:\n"
        f"   {cmd}\n"
        "------------------------------------------------------------"
    )


class Toolbox(object):
    def __init__(self):
        self.label = "SedInConnect 3.2"
        self.alias = "sedinconnect"
        self.description = (
            "SedInConnect 3.2: Stand-alone Sediment Connectivity Assessment Tool. "
            "MORPHEUS PRIN 2023-2026 Project (CNR-IRPI Padova). [TESTING / PREVIEW]"
        )
        self.tools = [CalculateSedimentConnectivity]


class CalculateSedimentConnectivity(object):
    def __init__(self):
        self.label = "Calculate Sediment Connectivity Index (IC)"
        self.description = (
            "Calculates the Index of Sediment Connectivity (IC) (Cavalli et al., 2013; Borselli et al., 2008) "
            "using high-performance native 64-bit Python/Numba algorithms.\n\n"
            "Developed at CNR-IRPI Padova within the MORPHEUS PRIN 2023-2026 project.\n"
            "Note: This tool is currently in Testing/Preview phase."
        )
        self.canRunInBackground = True

    def getParameterInfo(self):
        """Define parameter definitions organized in clear categories for ArcGIS Pro."""

        # -----------------------------------------------------------
        # CATEGORY 1: Input Datasets
        # -----------------------------------------------------------
        p_dtm = arcpy.Parameter(
            displayName="Input Digital Terrain Model (DTM)",
            name="in_dtm",
            datatype="GPRasterLayer",
            parameterType="Required",
            direction="Input",
            category="1. Input Datasets"
        )
        p_dtm.description = "Elevation raster layer or dataset (GeoTIFF or Geodatabase Raster)."

        p_target = arcpy.Parameter(
            displayName="Target Features (Streams, Lakes, Outlets) [Optional]",
            name="in_target",
            datatype="GPFeatureLayer",
            parameterType="Optional",
            direction="Input",
            category="1. Input Datasets"
        )
        p_target.description = (
            "Vector features representing targets of connectivity (e.g. stream lines, lake/reservoir polygon, "
            "catchment outlet point). If omitted, connectivity to the catchment outlet is calculated automatically."
        )

        p_sink = arcpy.Parameter(
            displayName="Sink Features (Depressions, Retention Basins) [Optional]",
            name="in_sink",
            datatype="GPFeatureLayer",
            parameterType="Optional",
            direction="Input",
            category="1. Input Datasets"
        )
        p_sink.description = (
            "Polygon features representing internal sinks, retention basins, or mining pits where "
            "sediment transport is intercepted."
        )

        # -----------------------------------------------------------
        # CATEGORY 2: Weighting Factor & Roughness
        # -----------------------------------------------------------
        p_auto_weight = arcpy.Parameter(
            displayName="Compute Automatic Weighting Factor (Cavalli Roughness)",
            name="use_auto_weight",
            datatype="GPBoolean",
            parameterType="Optional",
            direction="Input",
            category="2. Weighting Factor & Roughness"
        )
        p_auto_weight.description = (
            "If checked, calculates the impedance weight factor (W) automatically from high-resolution DTM "
            "surface roughness (moving standard deviation of residual topography, Cavalli et al., 2013)."
        )
        p_auto_weight.value = True

        p_window_size = arcpy.Parameter(
            displayName="Roughness Window Size (pixels)",
            name="window_size",
            datatype="GPLong",
            parameterType="Optional",
            direction="Input",
            category="2. Weighting Factor & Roughness"
        )
        p_window_size.description = (
            "Moving window kernel size in pixels for standard deviation of residual topography. "
            "Default: 3 (representing 3x3 pixels)."
        )
        p_window_size.filter.type = "ValueList"
        p_window_size.filter.list = [3, 5, 7, 9, 11, 13, 15, 17, 19, 21, 23, 25, 27, 29, 31, 33, 35]
        p_window_size.value = 3

        p_normalize = arcpy.Parameter(
            displayName="Log-Normalize Weighting Factor",
            name="normalize_weight",
            datatype="GPBoolean",
            parameterType="Optional",
            direction="Input",
            category="2. Weighting Factor & Roughness"
        )
        p_normalize.description = (
            "Applies natural logarithmic normalization to the Cavalli roughness weight factor. "
            "Recommended when using larger window sizes (window size > 5)."
        )
        p_normalize.value = False

        p_custom_weight = arcpy.Parameter(
            displayName="Custom User Weight Raster [Optional]",
            name="in_custom_weight",
            datatype="GPRasterLayer",
            parameterType="Optional",
            direction="Input",
            category="2. Weighting Factor & Roughness"
        )
        p_custom_weight.description = (
            "Custom impedance/weight raster (e.g. Manning roughness, C-factor). "
            "Used only when Automatic Weighting Factor is unchecked."
        )

        # -----------------------------------------------------------
        # CATEGORY 3: Pre-processing & Conditioning
        # -----------------------------------------------------------
        p_fill_dtm = arcpy.Parameter(
            displayName="Fill DTM Depressions (Priority-Flood Pit Removal)",
            name="fill_dtm",
            datatype="GPBoolean",
            parameterType="Optional",
            direction="Input",
            category="3. Pre-processing & Conditioning"
        )
        p_fill_dtm.description = (
            "Executes native Priority-Flood depression filling on the DTM prior to flow routing."
        )
        p_fill_dtm.value = False

        # -----------------------------------------------------------
        # CATEGORY 4: Primary & Intermediate Outputs
        # -----------------------------------------------------------
        p_out_ic = arcpy.Parameter(
            displayName="Output Connectivity Index (IC) Raster",
            name="out_ic",
            datatype="DERasterDataset",
            parameterType="Required",
            direction="Output",
            category="4. Output Datasets"
        )
        p_out_ic.description = "Primary output raster of the dimensionless Index of Connectivity (IC)."

        p_save_comp = arcpy.Parameter(
            displayName="Save Intermediate Components (D_up, D_down, Roughness, Weight)",
            name="save_components",
            datatype="GPBoolean",
            parameterType="Optional",
            direction="Input",
            category="4. Output Datasets"
        )
        p_save_comp.description = (
            "If enabled, also exports intermediate calculation rasters (Upslope Component D_up, "
            "Downslope Component D_down, Surface Roughness RI, and Weight Factor W)."
        )
        p_save_comp.value = False

        p_out_roughness = arcpy.Parameter(
            displayName="Output Surface Roughness Raster [Optional]",
            name="out_roughness",
            datatype="DERasterDataset",
            parameterType="Optional",
            direction="Output",
            category="4. Output Datasets"
        )
        p_out_roughness.description = "Output raster for surface roughness index (RI)."

        p_out_weight = arcpy.Parameter(
            displayName="Output Weight Factor Raster [Optional]",
            name="out_weight",
            datatype="DERasterDataset",
            parameterType="Optional",
            direction="Output",
            category="4. Output Datasets"
        )
        p_out_weight.description = "Output raster for the computed weight factor (W)."

        p_out_dup = arcpy.Parameter(
            displayName="Output Upslope Component (D_up) [Optional]",
            name="out_dup",
            datatype="DERasterDataset",
            parameterType="Optional",
            direction="Output",
            category="4. Output Datasets"
        )
        p_out_dup.description = "Output raster for upslope sediment potential component (D_up)."

        p_out_ddown = arcpy.Parameter(
            displayName="Output Downslope Component (D_down) [Optional]",
            name="out_ddown",
            datatype="DERasterDataset",
            parameterType="Optional",
            direction="Output",
            category="4. Output Datasets"
        )
        p_out_ddown.description = "Output raster for downslope flow path length component (D_down)."

        # -----------------------------------------------------------
        # CATEGORY 5: Advanced Performance Options
        # -----------------------------------------------------------
        p_chunk_size = arcpy.Parameter(
            displayName="Parallel Processing Chunk Size (pixels)",
            name="chunk_size",
            datatype="GPLong",
            parameterType="Optional",
            direction="Input",
            category="5. Advanced Performance Options"
        )
        p_chunk_size.filter.type = "ValueList"
        p_chunk_size.filter.list = [512, 1024, 2048, 4096]
        p_chunk_size.value = 1024
        p_chunk_size.description = "Tiling block size for multi-threaded surface roughness computation."

        p_workers = arcpy.Parameter(
            displayName="CPU Parallel Workers (0 = Auto)",
            name="n_workers",
            datatype="GPLong",
            parameterType="Optional",
            direction="Input",
            category="5. Advanced Performance Options"
        )
        p_workers.filter.type = "ValueList"
        p_workers.filter.list = [0, 2, 4, 8, 12, 16, 24, 32]
        p_workers.value = 0
        p_workers.description = "Number of parallel CPU worker threads (0 automatically detects available cores)."

        return [
            p_dtm, p_target, p_sink,
            p_auto_weight, p_window_size, p_normalize, p_custom_weight,
            p_fill_dtm,
            p_out_ic, p_save_comp, p_out_roughness, p_out_weight, p_out_dup, p_out_ddown,
            p_chunk_size, p_workers
        ]

    def isLicensed(self):
        """Allow tool to execute."""
        return True

    def updateParameters(self, parameters):
        """Dynamically enable or disable controls based on user choices."""
        use_auto = parameters[3].value
        if use_auto:
            parameters[4].enabled = True
            parameters[5].enabled = True
            parameters[6].enabled = False
        else:
            parameters[4].enabled = False
            parameters[5].enabled = False
            parameters[6].enabled = True
        return

    def updateMessages(self, parameters):
        """Validate parameter inputs."""
        window_size = parameters[4].value
        if window_size is not None:
            if window_size < 3 or window_size > 35 or (window_size % 2 == 0):
                parameters[4].setErrorMessage("Window size must be an odd integer between 3 and 35 (e.g., 3, 5, 7, 9...).")
        return

    def execute(self, parameters, messages):
        """Execute the sediment connectivity calculation in ArcGIS Pro."""
        try:
            track_app_launch("ArcGIS_Pro")
        except Exception:
            pass

        temp_workspace = Path(tempfile.mkdtemp(prefix="sedinconnect_arcgis_"))

        # 1. Parse Input Parameters
        dtm_val = parameters[0].valueAsText
        target_val = parameters[1].valueAsText
        sink_val = parameters[2].valueAsText
        use_auto_weight = bool(parameters[3].value)
        window_size = int(parameters[4].value) if parameters[4].value else 3
        normalize_weight = bool(parameters[5].value)
        custom_weight_val = parameters[6].valueAsText
        fill_dtm = bool(parameters[7].value)
        out_ic_val = parameters[8].valueAsText
        save_components = bool(parameters[9].value)

        out_roughness_val = parameters[10].valueAsText
        out_weight_val = parameters[11].valueAsText
        out_dup_val = parameters[12].valueAsText
        out_ddown_val = parameters[13].valueAsText

        chunk_size = int(parameters[14].value) if parameters[14].value else 1024
        n_workers = int(parameters[15].value) if parameters[15].value and int(parameters[15].value) > 0 else None

        # 2. Resolve Layers / Geodatabase Feature Classes
        messages.addMessage("Resolving input spatial layers and coordinate systems...")
        dtm_path = resolve_layer_or_gdb_raster(dtm_val, temp_workspace)
        target_path = resolve_layer_or_gdb_vector(target_val, temp_workspace, prefix="target") if target_val else None
        sink_path = resolve_layer_or_gdb_vector(sink_val, temp_workspace, prefix="sink") if sink_val else None
        weight_path = resolve_layer_or_gdb_raster(custom_weight_val, temp_workspace) if (custom_weight_val and not use_auto_weight) else None

        # 3. Resolve Output Rasters
        out_ic_path, ic_is_gdb, ic_final = resolve_raster_output(out_ic_val, temp_workspace, "ic")
        out_roughness_path, r_is_gdb, r_final = resolve_raster_output(out_roughness_val, temp_workspace, "roughness") if out_roughness_val else (None, False, None)
        out_weight_path, w_is_gdb, w_final = resolve_raster_output(out_weight_val, temp_workspace, "weight") if out_weight_val else (None, False, None)
        out_dup_path, dup_is_gdb, dup_final = resolve_raster_output(out_dup_val, temp_workspace, "dup") if out_dup_val else (None, False, None)
        out_ddown_path, ddown_is_gdb, ddown_final = resolve_raster_output(out_ddown_val, temp_workspace, "ddown") if out_ddown_val else (None, False, None)

        # Determine cell size via arcpy raster describe if possible
        try:
            desc = arcpy.Describe(dtm_val)
            cell_size = float(desc.meanCellWidth)
        except Exception:
            cell_size = 0.0

        messages.addMessage("============================================================")
        messages.addMessage("SedInConnect 3.2 — Stand-alone Sediment Connectivity Tool")
        messages.addMessage("CNR-IRPI Padova | MORPHEUS PRIN 2023-2026 Project")
        messages.addMessage("Status: [PREVIEW / TESTING RELEASE]")
        messages.addMessage("============================================================")
        messages.addMessage(f"Input DTM:        {dtm_path}")
        messages.addMessage(f"Output IC:       {out_ic_val}")
        if target_path:
            messages.addMessage(f"Target Features: {target_path}")
        if sink_path:
            messages.addMessage(f"Sink Features:   {sink_path}")
        messages.addMessage(f"Roughness Window: {window_size}x{window_size} pixels")
        messages.addMessage(f"Normalized W:    {normalize_weight}")
        messages.addMessage(f"Fill Pits:       {fill_dtm}")
        messages.addMessage(f"Chunk Size:      {chunk_size}x{chunk_size} px")
        messages.addMessage("------------------------------------------------------------")

        params = ProcessingParams(
            dtm_path=dtm_path,
            cell_size=cell_size,
            output_path=out_ic_path,
            target_path=target_path,
            sink_path=sink_path,
            use_cavalli_weight=use_auto_weight,
            weight_path=weight_path,
            normalize_weight=normalize_weight,
            save_components=save_components or bool(out_dup_path or out_ddown_path or out_roughness_path or out_weight_path),
            window_size=window_size,
            roughness_path=out_roughness_path,
            weight_output_path=out_weight_path,
            d_up_path=out_dup_path,
            d_down_path=out_ddown_path,
            fill_dtm=fill_dtm,
            show_preview=False,
            save_run_log=True,
            chunk_size=chunk_size,
            n_workers=n_workers
        )

        def log_to_arcgis(msg):
            messages.addMessage(str(msg))

        try:
            import numba
        except ImportError:
            messages.addWarning(get_arcgis_numba_help_message())

        processor = ConnectivityProcessor(log_func=log_to_arcgis)
        processor.process(params)

        # 4. If outputs are inside Geodatabase, copy them over
        if ic_is_gdb and out_ic_path.exists():
            messages.addMessage(f"Importing IC raster into Geodatabase: {ic_final}...")
            arcpy.management.CopyRaster(str(out_ic_path), ic_final)

        if r_is_gdb and out_roughness_path and out_roughness_path.exists():
            arcpy.management.CopyRaster(str(out_roughness_path), r_final)

        if w_is_gdb and out_weight_path and out_weight_path.exists():
            arcpy.management.CopyRaster(str(out_weight_path), w_final)

        if dup_is_gdb and out_dup_path and out_dup_path.exists():
            arcpy.management.CopyRaster(str(out_dup_path), dup_final)

        if ddown_is_gdb and out_ddown_path and ddown_path.exists():
            arcpy.management.CopyRaster(str(out_ddown_path), ddown_final)

        messages.addMessage("============================================================")
        messages.addMessage("SedInConnect IC calculation finished successfully!")
        messages.addMessage(f"Result file: {out_ic_val}")
        messages.addMessage("============================================================")
