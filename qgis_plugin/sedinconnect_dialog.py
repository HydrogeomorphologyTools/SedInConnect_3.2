# -*- coding: utf-8 -*-
"""
Dedicated PyQt Dialog for SedInConnect in QGIS.
Features QGIS MapLayer combo boxes, live progress, ArcGIS Cold-to-Hot Stretched colormap styling,
and interactive results preview window. Cross-platform Qt5/Qt6 compatible.

Developed at CNR-IRPI Padova within the MORPHEUS PRIN 2023-2026 Project.
[TESTING / PREVIEW VERSION]
"""

import os
import sys
import threading
import numpy as np
from pathlib import Path

try:
    from qgis.PyQt import QtCore, QtGui, QtWidgets
    from qgis.PyQt.QtCore import Qt, pyqtSignal, QObject
    from qgis.PyQt.QtGui import QIcon, QFont, QColor, QPixmap
    from qgis.PyQt.QtWidgets import (
        QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox,
        QLabel, QPushButton, QCheckBox, QSpinBox, QComboBox,
        QProgressBar, QTextEdit, QFileDialog, QMessageBox, QWidget, QFrame
    )
except ImportError:
    try:
        from PyQt5 import QtCore, QtGui, QtWidgets
        from PyQt5.QtCore import Qt, pyqtSignal, QObject
        from PyQt5.QtGui import QIcon, QFont, QColor, QPixmap
        from PyQt5.QtWidgets import (
            QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox,
            QLabel, QPushButton, QCheckBox, QSpinBox, QComboBox,
            QProgressBar, QTextEdit, QFileDialog, QMessageBox, QWidget, QFrame
        )
    except ImportError:
        from PyQt6 import QtCore, QtGui, QtWidgets
        from PyQt6.QtCore import Qt, pyqtSignal, QObject
        from PyQt6.QtGui import QIcon, QFont, QColor, QPixmap
        from PyQt6.QtWidgets import (
            QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox,
            QLabel, QPushButton, QCheckBox, QSpinBox, QComboBox,
            QProgressBar, QTextEdit, QFileDialog, QMessageBox, QWidget, QFrame
        )

# Safe enum resolution across Qt5 and Qt6
Qt_AlignCenter = getattr(Qt, "AlignCenter", None)
if Qt_AlignCenter is None:
    Qt_AlignCenter = getattr(Qt.AlignmentFlag, "AlignCenter")

from qgis.core import (
    QgsProject, QgsMapLayerProxyModel, QgsRasterLayer,
    QgsRasterShader, QgsColorRampShader, QgsSingleBandPseudoColorRenderer,
    QgsRasterBandStats
)
from qgis.gui import QgsMapLayerComboBox, QgsFileWidget

# Proxy filter enums
Filter_Raster = getattr(QgsMapLayerProxyModel, "RasterLayer", None)
if Filter_Raster is None:
    Filter_Raster = getattr(getattr(QgsMapLayerProxyModel, "Filter", None), "RasterLayer", 1)

Filter_Vector = getattr(QgsMapLayerProxyModel, "VectorLayer", None)
if Filter_Vector is None:
    Filter_Vector = getattr(getattr(QgsMapLayerProxyModel, "Filter", None), "VectorLayer", 2)

Filter_Polygon = getattr(QgsMapLayerProxyModel, "PolygonLayer", None)
if Filter_Polygon is None:
    Filter_Polygon = getattr(getattr(QgsMapLayerProxyModel, "Filter", None), "PolygonLayer", 16)

# FileWidget storage mode
SaveFile_Mode = getattr(QgsFileWidget, "SaveFile", None)
if SaveFile_Mode is None:
    SaveFile_Mode = getattr(getattr(QgsFileWidget, "StorageMode", None), "SaveFile", 0)

# ColorRamp type
Ramp_Interpolated = getattr(QgsColorRampShader, "Interpolated", None)
if Ramp_Interpolated is None:
    Ramp_Interpolated = getattr(getattr(QgsColorRampShader, "Type", None), "Interpolated", 0)

from .sedinconnect.utils.params import ProcessingParams
from .sedinconnect.core.processor import ConnectivityProcessor
from .sedinconnect.gui.dialogs import ResultPreviewDialog
from .sedinconnect.utils.telemetry import track_app_launch


def apply_arcgis_ic_colormap(layer: QgsRasterLayer):
    """
    Apply a rich ArcGIS-style Cold-to-Hot colormap with enhanced warm reds:
    - Low Connectivity: Lapislazuli Blue (#0F2D6E) -> Sky Blue (#0284C7)
    - Median Connectivity: Emerald Green (#10B981) -> Golden Yellow (#FACC15)
    - High Connectivity: Rich Orange (#F97316) -> Fiery Red (#EF4444) -> Deep Crimson (#881337)
    """
    try:
        if not layer.isValid():
            return

        provider = layer.dataProvider()
        stats = provider.bandStatistics(1, QgsRasterBandStats.Min | QgsRasterBandStats.Max | QgsRasterBandStats.Mean | QgsRasterBandStats.StdDev)
        min_val = stats.minValue
        max_val = stats.maxValue
        mean_val = stats.mean
        std_val = stats.stdDev

        if np.isnan(min_val) or np.isnan(max_val) or min_val >= max_val:
            min_val = -10.0
            max_val = 5.0
            mean_val = -2.5
            std_val = 2.0

        # Contrast stretch: 2 standard deviations around mean, clamped to min/max
        s_min = max(min_val, mean_val - 2.2 * std_val)
        s_max = min(max_val, mean_val + 2.2 * std_val)
        val_range = s_max - s_min

        # 7-stop rich warm spectrum with vibrant reds
        items = [
            QgsColorRampShader.ColorRampItem(min_val, QColor(15, 45, 110), f"{min_val:.2f} (Low IC)"),
            QgsColorRampShader.ColorRampItem(s_min + 0.15 * val_range, QColor(2, 132, 199), f"{s_min + 0.15 * val_range:.2f}"),
            QgsColorRampShader.ColorRampItem(s_min + 0.35 * val_range, QColor(16, 185, 129), f"{s_min + 0.35 * val_range:.2f}"),
            QgsColorRampShader.ColorRampItem(s_min + 0.50 * val_range, QColor(250, 204, 21), f"{s_min + 0.50 * val_range:.2f}"),
            QgsColorRampShader.ColorRampItem(s_min + 0.65 * val_range, QColor(249, 115, 22), f"{s_min + 0.65 * val_range:.2f}"),
            QgsColorRampShader.ColorRampItem(s_min + 0.82 * val_range, QColor(239, 68, 68), f"{s_min + 0.82 * val_range:.2f}"),
            QgsColorRampShader.ColorRampItem(max_val, QColor(136, 19, 55), f"{max_val:.2f} (High IC)")
        ]

        shader = QgsRasterShader()
        ramp = QgsColorRampShader()
        ramp.setColorRampType(Ramp_Interpolated)
        ramp.setColorRampItemList(items)
        shader.setRasterShaderFunction(ramp)

        renderer = QgsSingleBandPseudoColorRenderer(layer.dataProvider(), 1, shader)
        layer.setRenderer(renderer)
        layer.triggerRepaint()
    except Exception as e:
        print(f"Warning applying colormap: {e}")


class WorkerSignals(QObject):
    log = pyqtSignal(str)
    finished = pyqtSignal(bool, str)


class SedInConnectDialog(QDialog):

    def __init__(self, iface, parent=None):
        super().__init__(parent)
        self.iface = iface
        self.setWindowTitle("SedInConnect 3.2 — Sediment Connectivity Assessment [TESTING RELEASE]")
        self.resize(820, 780)

        icon_path = os.path.join(os.path.dirname(__file__), 'icon.png')
        if not os.path.exists(icon_path):
            icon_path = os.path.join(os.path.dirname(__file__), 'logo2.png')
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        try:
            track_app_launch('QGIS_Plugin')
        except Exception:
            pass
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)

        # Header Box with Logo and Project Information
        header_frame = QFrame()
        header_frame.setStyleSheet("background-color: #F8F9FA; border: 1px solid #DEE2E6; border-radius: 6px; padding: 6px;")
        h_layout = QHBoxLayout(header_frame)

        # Logo image
        logo_label = QLabel()
        logo_path = os.path.join(os.path.dirname(__file__), 'icon.png')
        if not os.path.exists(logo_path):
            logo_path = os.path.join(os.path.dirname(__file__), 'logo2.png')
        if os.path.exists(logo_path):
            pix = QPixmap(logo_path).scaled(56, 56, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            logo_label.setPixmap(pix)
        h_layout.addWidget(logo_label)

        # Title & Disclaimer text
        title_text = QLabel(
            "<h3 style='margin:0; color:#1B5E20;'>SedInConnect 3.2 — Sediment Connectivity Tool</h3>"
            "<p style='margin:2px 0 0 0; font-size:9pt; color:#495057;'>"
            "Stand-alone Sediment Connectivity Assessment in River Catchments<br>"
            "<b>CNR-IRPI Padova</b> | <b>MORPHEUS PRIN 2023-2026 Project</b> (Prot. 2022JEFZRM)<br>"
            "<span style='color:#D32F2F; font-weight:bold;'>[TESTING / PREVIEW VERSION — Feedback Welcome]</span>"
            "</p>"
        )
        title_text.setAlignment(Qt.AlignVCenter)
        h_layout.addWidget(title_text, stretch=1)
        main_layout.addWidget(header_frame)

        # Group 1: Inputs
        grp_inputs = QGroupBox("1. Input Spatial Layers")
        g_layout = QGridLayout(grp_inputs)

        g_layout.addWidget(QLabel("<b>Digital Terrain Model (DTM):</b>"), 0, 0)
        self.dtm_combo = QgsMapLayerComboBox()
        self.dtm_combo.setFilters(Filter_Raster)
        self.dtm_combo.setToolTip("Select the input elevation raster (raw or pit-filled DTM).")
        g_layout.addWidget(self.dtm_combo, 0, 1)

        g_layout.addWidget(QLabel("Target Layer (Streams/Outlets) [Optional]:"), 1, 0)
        self.target_combo = QgsMapLayerComboBox()
        self.target_combo.setFilters(Filter_Vector)
        self.target_combo.setAllowEmptyLayer(True)
        self.target_combo.setToolTip("Optional stream network lines or lake/reservoir polygons. If blank, connectivity to catchment outlet is calculated.")
        g_layout.addWidget(self.target_combo, 1, 1)

        g_layout.addWidget(QLabel("Sink Layer (Depressions) [Optional]:"), 2, 0)
        self.sink_combo = QgsMapLayerComboBox()
        self.sink_combo.setFilters(Filter_Polygon)
        self.sink_combo.setAllowEmptyLayer(True)
        self.sink_combo.setToolTip("Optional polygon features representing retention basins, quarries, or natural depressions.")
        g_layout.addWidget(self.sink_combo, 2, 1)

        main_layout.addWidget(grp_inputs)

        # Group 2: Parameters
        grp_params = QGroupBox("2. Analysis Parameters & Weighting Factor")
        p_layout = QGridLayout(grp_params)

        self.auto_weight_cb = QCheckBox("Automatic Cavalli (2013) Surface Roughness Weight Factor")
        self.auto_weight_cb.setChecked(True)
        self.auto_weight_cb.setToolTip("Computes impedance weight W automatically as 1 - (RI / RI_max) using moving standard deviation of residual topography.")
        self.auto_weight_cb.toggled.connect(self.toggle_weight_mode)
        p_layout.addWidget(self.auto_weight_cb, 0, 0, 1, 2)

        p_layout.addWidget(QLabel("Roughness Window Size:"), 1, 0)
        self.window_combo = QComboBox()
        for w in [3, 5, 7, 9, 11, 13, 15, 17, 19, 21, 23, 25, 27, 29, 31, 33, 35]:
            self.window_combo.addItem(f"{w}x{w} pixels (window={w})", w)
        self.window_combo.setToolTip("Moving window kernel size for surface roughness computation.")
        p_layout.addWidget(self.window_combo, 1, 1)

        self.normalize_cb = QCheckBox("Log-normalize Weight (Recommended for window size > 5)")
        self.normalize_cb.setChecked(False)
        self.normalize_cb.setToolTip("Applies natural logarithmic transformation to reduce skewness in large moving windows.")
        p_layout.addWidget(self.normalize_cb, 2, 0, 1, 2)

        self.fill_pits_cb = QCheckBox("Fill DTM depressions (Priority-Flood Pit Removal)")
        self.fill_pits_cb.setChecked(False)
        self.fill_pits_cb.setToolTip("Removes digital elevation pits using Priority-Flood algorithm before routing.")
        p_layout.addWidget(self.fill_pits_cb, 3, 0, 1, 2)

        self.save_comp_cb = QCheckBox("Save intermediate components (D_up, D_down, Roughness, Weight)")
        self.save_comp_cb.setChecked(False)
        self.save_comp_cb.setToolTip("Exports intermediate calculation GeoTIFF files into the same directory as the output IC.")
        p_layout.addWidget(self.save_comp_cb, 4, 0, 1, 2)

        self.auto_load_cb = QCheckBox("Automatically add output IC layer to QGIS canvas with ArcGIS Cold-to-Hot colormap")
        self.auto_load_cb.setChecked(True)
        p_layout.addWidget(self.auto_load_cb, 5, 0, 1, 2)

        self.show_preview_cb = QCheckBox("Show interactive results preview dialog (histogram & statistics)")
        self.show_preview_cb.setChecked(True)
        p_layout.addWidget(self.show_preview_cb, 6, 0, 1, 2)

        main_layout.addWidget(grp_params)

        # Group 3: Output Destination
        grp_out = QGroupBox("3. Output Destination")
        o_layout = QHBoxLayout(grp_out)
        self.out_file_widget = QgsFileWidget()
        self.out_file_widget.setStorageMode(SaveFile_Mode)
        self.out_file_widget.setFilter("GeoTIFF (*.tif *.TIF)")
        self.out_file_widget.setToolTip("Select the output GeoTIFF file destination for the Index of Connectivity (IC).")
        o_layout.addWidget(self.out_file_widget)
        main_layout.addWidget(grp_out)

        # Progress and Log
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(False)
        main_layout.addWidget(self.progress_bar)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(120)
        self.log_text.setFont(QFont("Consolas", 9))
        main_layout.addWidget(self.log_text)

        # Action Buttons & References
        btn_layout = QHBoxLayout()
        self.btn_run = QPushButton("Run Calculation")
        self.btn_run.setStyleSheet("background-color: #2E7D32; color: white; font-weight: bold; padding: 8px 24px; font-size: 11pt; border-radius: 4px;")
        self.btn_run.clicked.connect(self.start_processing)
        btn_layout.addWidget(self.btn_run)

        self.btn_close = QPushButton("Close")
        self.btn_close.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_close)
        main_layout.addLayout(btn_layout)

    def toggle_weight_mode(self, checked):
        self.window_combo.setEnabled(checked)
        self.normalize_cb.setEnabled(checked)

    def start_processing(self):
        dtm_layer = self.dtm_combo.currentLayer()
        if not dtm_layer or not dtm_layer.isValid():
            QMessageBox.warning(self, "Input Error", "Please select a valid DTM raster layer from your project.")
            return

        out_path_str = self.out_file_widget.filePath().strip()
        if not out_path_str:
            QMessageBox.warning(self, "Output Error", "Please specify an output path for the Connectivity Index raster (.tif).")
            return

        dtm_path = Path(dtm_layer.source())
        cell_size = float(dtm_layer.rasterUnitsPerPixelX())

        target_layer = self.target_combo.currentLayer()
        target_path = Path(target_layer.source()) if (target_layer and target_layer.isValid()) else None

        sink_layer = self.sink_combo.currentLayer()
        sink_path = Path(sink_layer.source()) if (sink_layer and sink_layer.isValid()) else None

        out_path = Path(out_path_str)
        window_size = int(self.window_combo.currentData())

        params = ProcessingParams(
            dtm_path=dtm_path,
            cell_size=cell_size,
            output_path=out_path,
            target_path=target_path,
            sink_path=sink_path,
            use_cavalli_weight=self.auto_weight_cb.isChecked(),
            normalize_weight=self.normalize_cb.isChecked(),
            window_size=window_size,
            fill_dtm=self.fill_pits_cb.isChecked(),
            save_components=self.save_comp_cb.isChecked(),
            save_run_log=True,
            show_preview=False
        )

        self.btn_run.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.log_text.clear()

        self.signals = WorkerSignals()
        self.signals.log.connect(self.on_log)
        self.signals.finished.connect(self.on_finished)

        def worker():
            try:
                proc = ConnectivityProcessor(log_func=lambda m: self.signals.log.emit(str(m)))
                proc.process(params)
                self.signals.finished.emit(True, str(out_path))
            except Exception as e:
                self.signals.finished.emit(False, str(e))

        t = threading.Thread(target=worker, daemon=True)
        t.start()

    def on_log(self, msg):
        self.log_text.append(msg)
        self.log_text.verticalScrollBar().setValue(self.log_text.verticalScrollBar().maximum())

    def on_finished(self, success, result):
        self.btn_run.setEnabled(True)
        self.progress_bar.setVisible(False)
        if success:
            out_p = Path(result)
            if self.auto_load_cb.isChecked() and out_p.exists():
                layer = QgsRasterLayer(str(out_p), out_p.stem)
                if layer.isValid():
                    apply_arcgis_ic_colormap(layer)
                    QgsProject.instance().addMapLayer(layer)
                    if self.iface:
                        self.iface.mapCanvas().refresh()

            if self.show_preview_cb.isChecked() and out_p.exists():
                preview = ResultPreviewDialog(out_p, parent=self)
                preview.exec_()
            else:
                QMessageBox.information(self, "Success", "SedInConnect processing completed successfully!")
        else:
            QMessageBox.critical(self, "Error", f"Processing failed:\n{result}")
