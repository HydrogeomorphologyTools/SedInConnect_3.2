# -*- coding: utf-8 -*-
"""
SedInConnect 3.2 — ArcGIS Pro Python Toolbox (.pyt)
Provides native high-performance Sediment Connectivity Index (IC) assessment in ArcGIS Pro.
Developed at CNR-IRPI Padova (Italy) within the MORPHEUS PRIN 2023-2026 Project.
"""

import os
import sys
import time
from pathlib import Path

# Add toolbox directory to sys.path
_tb_dir = str(Path(__file__).resolve().parent)
if _tb_dir not in sys.path:
    sys.path.insert(0, _tb_dir)

try:
    import arcpy
except ImportError:
    pass

from sedinconnect.utils.params import ProcessingParams
from sedinconnect.core.processor import ConnectivityProcessor
from sedinconnect.utils.telemetry import track_app_launch, track_analysis_run


class Toolbox(object):
    def __init__(self):
        self.label = "SedInConnect 3.2"
        self.alias = "sedinconnect"
        self.tools = [CalculateSedimentConnectivity]


class CalculateSedimentConnectivity(object):
    def __init__(self):
        self.label = "Calculate Sediment Connectivity Index (IC)"
        self.description = (
            "Calculates the Index of Connectivity (IC) (Cavalli et al., 2013; Borselli et al., 2008) "
            "using high-performance native Python/Numba algorithms."
        )
        self.canRunInBackground = True

    def getParameterInfo(self):
        """Define parameter definitions for ArcGIS Pro geoprocessing tool."""

        # Param 0: DTM Raster (Required)
        p_dtm = arcpy.Parameter(
            displayName="Input Digital Terrain Model (DTM)",
            name="in_dtm",
            datatype="GPRasterLayer",
            parameterType="Required",
            direction="Input"
        )

        # Param 1: Target Features (Optional)
        p_target = arcpy.Parameter(
            displayName="Target Features (Streams, Sinks, Reservoirs) [Optional]",
            name="in_target",
            datatype="GPFeatureLayer",
            parameterType="Optional",
            direction="Input"
        )

        # Param 2: Sink Features (Optional)
        p_sink = arcpy.Parameter(
            displayName="Sink Features (Depressions, Retention Basins) [Optional]",
            name="in_sink",
            datatype="GPFeatureLayer",
            parameterType="Optional",
            direction="Input"
        )

        # Param 3: Automatic Cavalli Roughness Weight (Boolean)
        p_auto_weight = arcpy.Parameter(
            displayName="Compute Automatic Weighting Factor (Cavalli Roughness)",
            name="use_auto_weight",
            datatype="GPBoolean",
            parameterType="Optional",
            direction="Input"
        )
        p_auto_weight.value = True

        # Param 4: Window Size (Long, 3..35)
        p_window_size = arcpy.Parameter(
            displayName="Roughness Window Size (pixels, odd integer 3..35)",
            name="window_size",
            datatype="GPLong",
            parameterType="Optional",
            direction="Input"
        )
        p_window_size.value = 3

        # Param 5: Normalize Weight (Boolean)
        p_normalize = arcpy.Parameter(
            displayName="Log-Normalize Weighting Factor (Recommended for window size > 5)",
            name="normalize_weight",
            datatype="GPBoolean",
            parameterType="Optional",
            direction="Input"
        )
        p_normalize.value = False

        # Param 6: Custom User Weight Raster (Optional)
        p_custom_weight = arcpy.Parameter(
            displayName="Custom User Weight Raster [Optional, if auto-weight disabled]",
            name="in_custom_weight",
            datatype="GPRasterLayer",
            parameterType="Optional",
            direction="Input"
        )

        # Param 7: Fill DTM Depressions (Boolean)
        p_fill_dtm = arcpy.Parameter(
            displayName="Fill DTM Depressions (Priority-Flood Pit Removal)",
            name="fill_dtm",
            datatype="GPBoolean",
            parameterType="Optional",
            direction="Input"
        )
        p_fill_dtm.value = False

        # Param 8: Save Intermediate Components (Boolean)
        p_save_comp = arcpy.Parameter(
            displayName="Save Intermediate Components (D_up, D_down, Roughness, Weight)",
            name="save_components",
            datatype="GPBoolean",
            parameterType="Optional",
            direction="Input"
        )
        p_save_comp.value = False

        # Param 9: Output IC Raster (Required)
        p_out_ic = arcpy.Parameter(
            displayName="Output Connectivity Index (IC)",
            name="out_ic",
            datatype="DERasterDataset",
            parameterType="Required",
            direction="Output"
        )

        # Param 10: Output Roughness Raster (Optional)
        p_out_roughness = arcpy.Parameter(
            displayName="Output Surface Roughness Raster [Optional]",
            name="out_roughness",
            datatype="DERasterDataset",
            parameterType="Optional",
            direction="Output"
        )

        # Param 11: Output Weight Raster (Optional)
        p_out_weight = arcpy.Parameter(
            displayName="Output Weight Factor Raster [Optional]",
            name="out_weight",
            datatype="DERasterDataset",
            parameterType="Optional",
            direction="Output"
        )

        # Param 12: Output D_up Raster (Optional)
        p_out_dup = arcpy.Parameter(
            displayName="Output Upslope Component (D_up) [Optional]",
            name="out_dup",
            datatype="DERasterDataset",
            parameterType="Optional",
            direction="Output"
        )

        # Param 13: Output D_down Raster (Optional)
        p_out_ddown = arcpy.Parameter(
            displayName="Output Downslope Component (D_down) [Optional]",
            name="out_ddown",
            datatype="DERasterDataset",
            parameterType="Optional",
            direction="Output"
        )

        return [
            p_dtm, p_target, p_sink, p_auto_weight, p_window_size,
            p_normalize, p_custom_weight, p_fill_dtm, p_save_comp,
            p_out_ic, p_out_roughness, p_out_weight, p_out_dup, p_out_ddown
        ]

    def isLicensed(self):
        """Allow tool to execute."""
        return True

    def updateParameters(self, parameters):
        """Update GUI parameter visibility."""
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
                parameters[4].setErrorMessage("Window size must be an odd integer between 3 and 35.")
        return

    def execute(self, parameters, messages):
        """Execute the sediment connectivity calculation in ArcGIS Pro."""
        try:
            track_app_launch("ArcGIS_Pro")
        except Exception:
            pass

        # 1. Parse Input Parameters
        dtm_val = parameters[0].valueAsText
        target_val = parameters[1].valueAsText
        sink_val = parameters[2].valueAsText
        use_auto_weight = bool(parameters[3].value)
        window_size = int(parameters[4].value) if parameters[4].value else 3
        normalize_weight = bool(parameters[5].value)
        custom_weight_val = parameters[6].valueAsText
        fill_dtm = bool(parameters[7].value)
        save_components = bool(parameters[8].value)

        out_ic_val = parameters[9].valueAsText
        out_roughness_val = parameters[10].valueAsText
        out_weight_val = parameters[11].valueAsText
        out_dup_val = parameters[12].valueAsText
        out_ddown_val = parameters[13].valueAsText

        # Convert to Path objects
        dtm_path = Path(dtm_val)
        out_ic_path = Path(out_ic_val)
        target_path = Path(target_val) if target_val else None
        sink_path = Path(sink_val) if sink_val else None
        weight_path = Path(custom_weight_val) if (custom_weight_val and not use_auto_weight) else None

        out_roughness_path = Path(out_roughness_val) if out_roughness_val else None
        out_weight_path = Path(out_weight_val) if out_weight_val else None
        out_dup_path = Path(out_dup_val) if out_dup_val else None
        out_ddown_path = Path(out_ddown_val) if out_ddown_val else None

        # Determine cell size via arcpy raster describe if possible
        try:
            desc = arcpy.Describe(dtm_val)
            cell_size = float(desc.meanCellWidth)
        except Exception:
            cell_size = 0.0

        messages.addMessage("------------------------------------------------------------")
        messages.addMessage("SedInConnect 3.2 — Stand-alone Sediment Connectivity Assessment")
        messages.addMessage("MORPHEUS PRIN 2023-2026 Project | CNR-IRPI Padova (Italy)")
        messages.addMessage("------------------------------------------------------------")
        messages.addMessage(f"Input DTM: {dtm_path}")
        messages.addMessage(f"Output IC: {out_ic_path}")
        if target_path:
            messages.addMessage(f"Target Features: {target_path}")
        if sink_path:
            messages.addMessage(f"Sink Features: {sink_path}")
        messages.addMessage(f"Roughness Window Size: {window_size}x{window_size} px")

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
            save_run_log=True
        )

        def log_to_arcgis(msg):
            messages.addMessage(str(msg))

        processor = ConnectivityProcessor(log_func=log_to_arcgis)
        processor.process(params)

        messages.addMessage("------------------------------------------------------------")
        messages.addMessage(f"Calculation successfully completed! Output saved to:\n{out_ic_path}")
        messages.addMessage("------------------------------------------------------------")
