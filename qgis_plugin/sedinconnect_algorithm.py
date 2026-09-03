# -*- coding: utf-8 -*-
"""
QGIS Processing Algorithm for SedInConnect 3.2.
Executes the native Numba/NumPy 100% bit-exact sediment connectivity pipeline.
"""

import os
import sys
import time
from pathlib import Path

_p_dir = str(Path(__file__).resolve().parent)
if _p_dir not in sys.path:
    sys.path.insert(0, _p_dir)

from qgis.core import (
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingParameterRasterLayer,
    QgsProcessingParameterVectorLayer,
    QgsProcessingParameterBoolean,
    QgsProcessingParameterNumber,
    QgsProcessingParameterRasterDestination,
    QgsProcessingOutputRasterLayer,
    QgsProcessingException
)
try:
    from qgis.PyQt.QtGui import QIcon
except ImportError:
    try:
        from PyQt5.QtGui import QIcon
    except ImportError:
        from PyQt6.QtGui import QIcon

from .sedinconnect.utils.params import ProcessingParams
from .sedinconnect.core.processor import ConnectivityProcessor
from .sedinconnect.utils.raster import LargeFileRasterReader
from .sedinconnect.utils.telemetry import track_app_launch


class SedInConnectAlgorithm(QgsProcessingAlgorithm):
    INPUT_DTM = 'INPUT_DTM'
    INPUT_TARGET = 'INPUT_TARGET'
    INPUT_SINK = 'INPUT_SINK'
    USE_AUTO_WEIGHT = 'USE_AUTO_WEIGHT'
    INPUT_WEIGHT = 'INPUT_WEIGHT'
    WINDOW_SIZE = 'WINDOW_SIZE'
    NORMALIZE_WEIGHT = 'NORMALIZE_WEIGHT'
    FILL_DTM = 'FILL_DTM'
    SAVE_COMPONENTS = 'SAVE_COMPONENTS'
    OUTPUT_IC = 'OUTPUT_IC'
    OUTPUT_ROUGHNESS = 'OUTPUT_ROUGHNESS'
    OUTPUT_WEIGHT = 'OUTPUT_WEIGHT'
    OUTPUT_DUP = 'OUTPUT_DUP'
    OUTPUT_DDOWN = 'OUTPUT_DDOWN'

    def name(self):
        return 'sedinconnect_ic'

    def displayName(self):
        return 'Calculate Sediment Connectivity Index (IC)'

    def group(self):
        return 'Sediment Connectivity'

    def groupId(self):
        return 'sediment_connectivity'

    def shortHelpString(self):
        return (
            """<h3>SedInConnect 3.2 — Stand-alone Sediment Connectivity Assessment</h3>
            <p>Calculates the <b>Index of Connectivity (IC)</b> (Cavalli et al., 2013; Borselli et al., 2008) 
            using high-performance native Python/Numba algorithms.</p>
            <p><b>Features:</b></p>
            <ul>
              <li>Pure native D8 and D-Infinity flow direction calculation</li>
              <li>Multi-pass flat area drainage resolution (Garbrecht & Martz, 1997)</li>
              <li>Surface roughness weighting factor calculation (3x3 up to 35x35)</li>
              <li>Target-based (streams, gullies, dams) and catchment outlet modes</li>
              <li>Sink and depression extraction support</li>
            </ul>
            <p><b>MORPHEUS PRIN 2023-2026 Project</b> | CNR-IRPI Padova</p>"""
        )

    def icon(self):
        icon_path = os.path.join(os.path.dirname(__file__), 'icon.png')
        if os.path.exists(icon_path):
            return QIcon(icon_path)
        return super().icon()

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterRasterLayer(
                self.INPUT_DTM, 'Input Digital Terrain Model (DTM)'
            )
        )
        self.addParameter(
            QgsProcessingParameterVectorLayer(
                self.INPUT_TARGET, 'Target Features (Streams, Sinks, Reservoirs) [Optional]',
                [QgsProcessing.TypeVectorAnyGeometry],
                optional=True
            )
        )
        self.addParameter(
            QgsProcessingParameterVectorLayer(
                self.INPUT_SINK, 'Sink Features (Depressions, Retention Basins) [Optional]',
                [QgsProcessing.TypeVectorPolygon],
                optional=True
            )
        )
        self.addParameter(
            QgsProcessingParameterBoolean(
                self.USE_AUTO_WEIGHT, 'Compute Automatic Weighting Factor (Cavalli Roughness)',
                defaultValue=True
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.WINDOW_SIZE, 'Roughness Window Size (pixels, odd integer 3..35)',
                type=QgsProcessingParameterNumber.Integer,
                defaultValue=3,
                minValue=3,
                maxValue=35
            )
        )
        self.addParameter(
            QgsProcessingParameterBoolean(
                self.NORMALIZE_WEIGHT, 'Log-Normalize Weighting Factor (Recommended for window size > 5)',
                defaultValue=False
            )
        )
        self.addParameter(
            QgsProcessingParameterRasterLayer(
                self.INPUT_WEIGHT, 'Custom User Weight Raster [Optional, if auto-weight disabled]',
                optional=True
            )
        )
        self.addParameter(
            QgsProcessingParameterBoolean(
                self.FILL_DTM, 'Fill DTM Depressions (Priority-Flood Pit Removal)',
                defaultValue=False
            )
        )
        self.addParameter(
            QgsProcessingParameterBoolean(
                self.SAVE_COMPONENTS, 'Save Intermediate Components (D_up, D_down, Roughness, Weight)',
                defaultValue=False
            )
        )

        # Outputs
        self.addParameter(
            QgsProcessingParameterRasterDestination(
                self.OUTPUT_IC, 'Output Connectivity Index (IC)'
            )
        )
        self.addParameter(
            QgsProcessingParameterRasterDestination(
                self.OUTPUT_ROUGHNESS, 'Output Surface Roughness Raster [Optional]',
                optional=True
            )
        )
        self.addParameter(
            QgsProcessingParameterRasterDestination(
                self.OUTPUT_WEIGHT, 'Output Weight Factor Raster [Optional]',
                optional=True
            )
        )
        self.addParameter(
            QgsProcessingParameterRasterDestination(
                self.OUTPUT_DUP, 'Output Upslope Component (D_up) [Optional]',
                optional=True
            )
        )
        self.addParameter(
            QgsProcessingParameterRasterDestination(
                self.OUTPUT_DDOWN, 'Output Downslope Component (D_down) [Optional]',
                optional=True
            )
        )

    def processAlgorithm(self, parameters, context, feedback):
        try:
            track_app_launch('QGIS_Processing')
        except Exception:
            pass
        dtm_layer = self.parameterAsRasterLayer(parameters, self.INPUT_DTM, context)
        if not dtm_layer or not dtm_layer.isValid():
            raise QgsProcessingException('Invalid input DTM layer provided.')

        dtm_path = Path(dtm_layer.source())
        if not dtm_path.exists():
            raise QgsProcessingException(f'DTM source file not found on disk: {dtm_path}')

        cell_size = float(dtm_layer.rasterUnitsPerPixelX())
        if cell_size <= 0:
            with LargeFileRasterReader(dtm_path) as r:
                cell_size = abs(r.geotransform[1])

        target_layer = self.parameterAsVectorLayer(parameters, self.INPUT_TARGET, context)
        target_path = Path(target_layer.source()) if (target_layer and target_layer.isValid()) else None

        sink_layer = self.parameterAsVectorLayer(parameters, self.INPUT_SINK, context)
        sink_path = Path(sink_layer.source()) if (sink_layer and sink_layer.isValid()) else None

        use_auto_weight = self.parameterAsBool(parameters, self.USE_AUTO_WEIGHT, context)
        window_size = self.parameterAsInt(parameters, self.WINDOW_SIZE, context)
        normalize_weight = self.parameterAsBool(parameters, self.NORMALIZE_WEIGHT, context)
        fill_dtm = self.parameterAsBool(parameters, self.FILL_DTM, context)
        save_components = self.parameterAsBool(parameters, self.SAVE_COMPONENTS, context)

        weight_layer = self.parameterAsRasterLayer(parameters, self.INPUT_WEIGHT, context)
        weight_path = Path(weight_layer.source()) if (weight_layer and weight_layer.isValid()) else None

        out_ic = Path(self.parameterAsOutputLayer(parameters, self.OUTPUT_IC, context))
        out_roughness = Path(self.parameterAsOutputLayer(parameters, self.OUTPUT_ROUGHNESS, context)) if parameters.get(self.OUTPUT_ROUGHNESS) else None
        out_weight = Path(self.parameterAsOutputLayer(parameters, self.OUTPUT_WEIGHT, context)) if parameters.get(self.OUTPUT_WEIGHT) else None
        out_dup = Path(self.parameterAsOutputLayer(parameters, self.OUTPUT_DUP, context)) if parameters.get(self.OUTPUT_DUP) else None
        out_ddown = Path(self.parameterAsOutputLayer(parameters, self.OUTPUT_DDOWN, context)) if parameters.get(self.OUTPUT_DDOWN) else None

        if not use_auto_weight and not weight_path:
            raise QgsProcessingException('Automatic weighting factor is disabled, but no custom weight raster was provided.')

        params = ProcessingParams(
            dtm_path=dtm_path,
            cell_size=cell_size,
            output_path=out_ic,
            weight_path=weight_path,
            target_path=target_path,
            sink_path=sink_path,
            use_cavalli_weight=use_auto_weight,
            normalize_weight=normalize_weight,
            save_components=save_components or bool(out_dup or out_ddown or out_roughness or out_weight),
            window_size=window_size,
            roughness_path=out_roughness,
            weight_output_path=out_weight,
            d_up_path=out_dup,
            d_down_path=out_ddown,
            fill_dtm=fill_dtm,
            show_preview=False,
            save_run_log=True
        )

        def log_to_feedback(msg):
            feedback.pushInfo(str(msg))

        processor = ConnectivityProcessor(log_func=log_to_feedback)
        feedback.setProgressText("Processing Sediment Connectivity (Native Numba Pipeline)...")
        
        try:
            processor.process(params)
        except Exception as e:
            raise QgsProcessingException(f"Processing error: {e}")

        results = {self.OUTPUT_IC: str(out_ic)}
        if out_roughness and out_roughness.exists():
            results[self.OUTPUT_ROUGHNESS] = str(out_roughness)
        if out_weight and out_weight.exists():
            results[self.OUTPUT_WEIGHT] = str(out_weight)
        if out_dup and out_dup.exists():
            results[self.OUTPUT_DUP] = str(out_dup)
        if out_ddown and out_ddown.exists():
            results[self.OUTPUT_DDOWN] = str(out_ddown)

        return results

    def createInstance(self):
        return SedInConnectAlgorithm()
