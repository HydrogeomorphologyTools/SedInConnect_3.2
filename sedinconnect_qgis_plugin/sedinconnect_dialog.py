# -*- coding: utf-8 -*-
"""
Dedicated PyQt5 Dialog for SedInConnect in QGIS.
Features QGIS MapLayer combo boxes, live progress, ArcGIS Cold-to-Hot Stretched colormap styling,
and interactive results preview window.
"""

import os
import sys
import threading
import numpy as np
from pathlib import Path

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox,
    QLabel, QPushButton, QCheckBox, QSpinBox, QComboBox,
    QProgressBar, QTextEdit, QFileDialog, QMessageBox, QWidget
)
from PyQt5.QtCore import Qt, pyqtSignal, QObject
from PyQt5.QtGui import QIcon, QFont, QColor

from qgis.core import (
    QgsProject, QgsMapLayerProxyModel, QgsRasterLayer,
    QgsRasterShader, QgsColorRampShader, QgsSingleBandPseudoColorRenderer,
    QgsRasterBandStats
)
from qgis.gui import QgsMapLayerComboBox, QgsFileWidget

from .sedinconnect.utils.params import ProcessingParams
from .sedinconnect.core.processor import ConnectivityProcessor
from .sedinconnect.gui.dialogs import ResultPreviewDialog
from .sedinconnect.utils.telemetry import track_app_launch


def apply_arcgis_ic_colormap(layer: QgsRasterLayer):
    """
    Apply an ArcGIS-style Stretched Cold-to-Hot colormap to the IC raster:
    - Minimum / Negative values (Low Connectivity): Deep Lapislazuli Blue (#0D2B66 / #1E40AF)
    - Transitional values: Cyan (#06B6D4) -> Lime Yellow (#EAB308) -> Vivid Orange (#EA580C)
    - Maximum / Positive values (High Connectivity): Vibrant Red (#DC2626)
    """
    try:
        if not layer.isValid():
            return

        provider = layer.dataProvider()
        stats = provider.bandStatistics(1, QgsRasterBandStats.Min | QgsRasterBandStats.Max)
        min_val = stats.minValue
        max_val = stats.maxValue

        if np.isnan(min_val) or np.isnan(max_val) or min_val >= max_val:
            min_val = -10.0
            max_val = 5.0

        val_range = max_val - min_val

        # 5-stop smooth interpolated gradient (Cold to Hot)
        items = [
            QgsColorRampShader.ColorRampItem(
                min_val,
                QColor(15, 45, 110),  # Deep Lapislazuli Blue
                f"{min_val:.2f} (Low IC)"
            ),
            QgsColorRampShader.ColorRampItem(
                min_val + 0.25 * val_range,
                QColor(0, 180, 220),  # Cyan
                f"{min_val + 0.25 * val_range:.2f}"
            ),
            QgsColorRampShader.ColorRampItem(
                min_val + 0.50 * val_range,
                QColor(255, 230, 40),  # Bright Yellow
                f"{min_val + 0.50 * val_range:.2f}"
            ),
            QgsColorRampShader.ColorRampItem(
                min_val + 0.75 * val_range,
                QColor(245, 120, 20),  # Vibrant Orange
                f"{min_val + 0.75 * val_range:.2f}"
            ),
            QgsColorRampShader.ColorRampItem(
                max_val,
                QColor(220, 20, 20),  # Vibrant Red
                f"{max_val:.2f} (High IC)"
            )
        ]

        shader = QgsRasterShader()
        ramp = QgsColorRampShader()
        ramp.setColorRampType(QgsColorRampShader.Interpolated)
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
        self.setWindowTitle("SedInConnect 3.2 — Sediment Connectivity Assessment")
        self.resize(780, 720)

        icon_path = os.path.join(os.path.dirname(__file__), 'icon.ico')
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        try:
            track_app_launch('QGIS_Plugin')
        except Exception:
            pass
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)

        # Title Header
        header = QLabel("<h2>SedInConnect 3.2</h2><p style='color: #444;'>Stand-alone Sediment Connectivity Assessment (MORPHEUS PRIN 2023-2026)</p>")
        header.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(header)

        # Group 1: Inputs
        grp_inputs = QGroupBox("Inputs & Spatial Layers")
        g_layout = QGridLayout(grp_inputs)

        g_layout.addWidget(QLabel("DTM Raster Layer:"), 0, 0)
        self.dtm_combo = QgsMapLayerComboBox()
        self.dtm_combo.setFilters(QgsMapLayerProxyModel.RasterLayer)
        g_layout.addWidget(self.dtm_combo, 0, 1)

        g_layout.addWidget(QLabel("Target Layer (Streams/Outlets) [Optional]:"), 1, 0)
        self.target_combo = QgsMapLayerComboBox()
        self.target_combo.setFilters(QgsMapLayerProxyModel.VectorLayer)
        self.target_combo.setAllowEmptyLayer(True)
        g_layout.addWidget(self.target_combo, 1, 1)

        g_layout.addWidget(QLabel("Sink Layer (Depressions) [Optional]:"), 2, 0)
        self.sink_combo = QgsMapLayerComboBox()
        self.sink_combo.setFilters(QgsMapLayerProxyModel.PolygonLayer)
        self.sink_combo.setAllowEmptyLayer(True)
        g_layout.addWidget(self.sink_combo, 2, 1)

        main_layout.addWidget(grp_inputs)

        # Group 2: Parameters
        grp_params = QGroupBox("Analysis Parameters")
        p_layout = QGridLayout(grp_params)

        self.auto_weight_cb = QCheckBox("Automatic Cavalli (2013) Surface Roughness Weight Factor")
        self.auto_weight_cb.setChecked(True)
        p_layout.addWidget(self.auto_weight_cb, 0, 0, 1, 2)

        p_layout.addWidget(QLabel("Roughness Window Size (px):"), 1, 0)
        self.window_spin = QSpinBox()
        self.window_spin.setRange(3, 35)
        self.window_spin.setSingleStep(2)
        self.window_spin.setValue(3)
        p_layout.addWidget(self.window_spin, 1, 1)

        self.normalize_cb = QCheckBox("Log-normalize Weight (Recommended for window size > 5)")
        self.normalize_cb.setChecked(False)
        p_layout.addWidget(self.normalize_cb, 2, 0, 1, 2)

        self.fill_pits_cb = QCheckBox("Fill DTM depressions (Priority-Flood Pit Removal)")
        self.fill_pits_cb.setChecked(False)
        p_layout.addWidget(self.fill_pits_cb, 3, 0, 1, 2)

        self.save_comp_cb = QCheckBox("Save intermediate components (D_up, D_down, Roughness, Weight)")
        self.save_comp_cb.setChecked(False)
        p_layout.addWidget(self.save_comp_cb, 4, 0, 1, 2)

        self.auto_load_cb = QCheckBox("Automatically add output IC layer to QGIS canvas with ArcGIS Cold-to-Hot colormap")
        self.auto_load_cb.setChecked(True)
        p_layout.addWidget(self.auto_load_cb, 5, 0, 1, 2)

        self.show_preview_cb = QCheckBox("Show interactive results preview dialog (histogram & statistics)")
        self.show_preview_cb.setChecked(True)
        p_layout.addWidget(self.show_preview_cb, 6, 0, 1, 2)

        main_layout.addWidget(grp_params)

        # Group 3: Output Destination
        grp_out = QGroupBox("Output File")
        o_layout = QHBoxLayout(grp_out)
        self.out_file_widget = QgsFileWidget()
        self.out_file_widget.setStorageMode(QgsFileWidget.SaveFile)
        self.out_file_widget.setFilter("GeoTIFF (*.tif *.TIF)")
        o_layout.addWidget(self.out_file_widget)
        main_layout.addWidget(grp_out)

        # Progress and Log
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(False)
        main_layout.addWidget(self.progress_bar)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(130)
        self.log_text.setFont(QFont("Consolas", 9))
        main_layout.addWidget(self.log_text)

        # Action Buttons
        btn_layout = QHBoxLayout()
        self.btn_run = QPushButton("Run Calculation")
        self.btn_run.setStyleSheet("background-color: #2E7D32; color: white; font-weight: bold; padding: 8px 24px; font-size: 11pt; border-radius: 4px;")
        self.btn_run.clicked.connect(self.start_processing)
        btn_layout.addWidget(self.btn_run)

        self.btn_close = QPushButton("Close")
        self.btn_close.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_close)
        main_layout.addLayout(btn_layout)

    def start_processing(self):
        dtm_layer = self.dtm_combo.currentLayer()
        if not dtm_layer or not dtm_layer.isValid():
            QMessageBox.warning(self, "Input Error", "Please select a valid DTM raster layer.")
            return

        out_path_str = self.out_file_widget.filePath().strip()
        if not out_path_str:
            QMessageBox.warning(self, "Output Error", "Please specify an output path for the Connectivity Index raster.")
            return

        dtm_path = Path(dtm_layer.source())
        cell_size = float(dtm_layer.rasterUnitsPerPixelX())

        target_layer = self.target_combo.currentLayer()
        target_path = Path(target_layer.source()) if (target_layer and target_layer.isValid()) else None

        sink_layer = self.sink_combo.currentLayer()
        sink_path = Path(sink_layer.source()) if (sink_layer and sink_layer.isValid()) else None

        out_path = Path(out_path_str)

        params = ProcessingParams(
            dtm_path=dtm_path,
            cell_size=cell_size,
            output_path=out_path,
            target_path=target_path,
            sink_path=sink_path,
            use_cavalli_weight=self.auto_weight_cb.isChecked(),
            normalize_weight=self.normalize_cb.isChecked(),
            window_size=self.window_spin.value(),
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
