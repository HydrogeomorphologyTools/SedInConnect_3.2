import os
import sys
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Optional
from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QLabel, QLineEdit, QPushButton, QFileDialog, 
                             QProgressBar, QTextEdit, QFrame, QCheckBox, 
                             QSpinBox, QGroupBox, QMessageBox, QSplitter,
                             QScrollArea, QGridLayout, QApplication)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QPixmap, QPalette, QBrush, QTextCursor

from sedinconnect.core.processor import ConnectivityProcessor
from sedinconnect.utils.params import ProcessingParams
from sedinconnect.gui.dialogs import ResultPreviewDialog

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        if getattr(sys, 'frozen', False):
            base_path = Path(sys._MEIPASS)
        else:
            # Root is 2 levels up from sedinconnect/gui/
            base_path = Path(__file__).parent.parent.parent
            
        res_path = base_path / relative_path
        if res_path.exists():
            return res_path
    except:
        pass
    return Path(relative_path)

class ProcessingThread(QThread):
    """Thread for running long processing tasks without freezing GUI"""
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(bool, str)
    console_output = pyqtSignal(str)

    def __init__(self, params: ProcessingParams, processor: ConnectivityProcessor):
        super().__init__()
        self.params = params
        self.processor = processor
        self.processor.log = self.console_output.emit

    def run(self):
        try:
            self.processor.process(self.params)
            self.finished.emit(True, "Analysis completed successfully!")
        except Exception as e:
            import traceback
            error_msg = f"Error: {str(e)}\n\n{traceback.format_exc()}"
            self.finished.emit(False, error_msg)

class ModernConnectivityGUI(QMainWindow):
    """Modern PyQt5 GUI for SedInConnect 3.0"""

    def __init__(self):
        super().__init__()
        self.processor = ConnectivityProcessor()
        self.worker_thread = None
        self.init_ui()

    def init_ui(self):
        """Initialize UI matching the final verified layout"""
        self.setWindowTitle("SedInConnect 3.0 - Sediment Connectivity Tool")
        self.setGeometry(100, 100, 1400, 900)
        self.setMinimumSize(1000, 700)

        # Set window icon
        logo2_path = resource_path("logo2.png")
        if logo2_path.exists():
            self.setWindowIcon(QtGui.QIcon(str(logo2_path)))

        # Main central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Background image handling
        bg_image_path = resource_path("image.jpg")
        if bg_image_path.exists():
            palette = QPalette()
            pixmap = QPixmap(str(bg_image_path))
            self._bg_pixmap = pixmap
            scaled_pixmap = pixmap.scaled(self.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            palette.setBrush(QPalette.Window, QBrush(scaled_pixmap))
            central_widget.setAutoFillBackground(True)
            central_widget.setPalette(palette)
        else:
            central_widget.setStyleSheet("background-color: #f5f5f5;")

        self.set_modern_style()

        # MASTER HORIZONTAL LAYOUT
        main_layout = QHBoxLayout(central_widget)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(15, 15, 15, 15)

        # 1. Sidebar (Left)
        sidebar = self.create_sidebar()
        main_layout.addWidget(sidebar)

        # 2. Main Content (Center)
        content_widget = QWidget()
        content_widget.setStyleSheet("background-color: rgba(255, 255, 255, 200); border-radius: 10px;")
        content_layout = QVBoxLayout(content_widget)
        content_layout.setSpacing(10)
        content_layout.setContentsMargins(15, 15, 15, 15)

        title = QLabel("SedInConnect 3.0")
        title.setFont(QFont("Arial", 24, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        content_layout.addWidget(title)

        subtitle = QLabel("Sediment Connectivity Index Calculation (Cavalli et al., 2013)")
        subtitle.setFont(QFont("Arial", 11))
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet("color: #666; margin-bottom: 10px;")
        content_layout.addWidget(subtitle)

        # Scrollable area for controls
        controls_scroll = QScrollArea()
        controls_scroll.setWidgetResizable(True)
        controls_scroll.setFrameShape(QFrame.NoFrame)
        controls_scroll.setStyleSheet("background: transparent;")
        
        controls_container = QWidget()
        controls_container.setStyleSheet("background: transparent;")
        controls_layout = QVBoxLayout(controls_container)
        controls_layout.setContentsMargins(0, 0, 0, 0)

        input_group = self.create_input_group()
        controls_layout.addWidget(input_group)

        options_group = self.create_options_group()
        controls_layout.addWidget(options_group)

        output_group = self.create_output_group()
        controls_layout.addWidget(output_group)
        
        controls_layout.addStretch()
        controls_scroll.setWidget(controls_container)
        content_layout.addWidget(controls_scroll)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 2px solid #ccc;
                border-radius: 5px;
                text-align: center;
                height: 25px;
            }
            QProgressBar::chunk {
                background-color: #4CAF50;
            }
        """)
        content_layout.addWidget(self.progress_bar)

        # Status area
        self.status_label = QTextEdit()
        self.status_label.setReadOnly(True)
        self.status_label.setMaximumHeight(50)
        self.status_label.setMinimumHeight(50)
        self.status_label.setLineWrapMode(QTextEdit.NoWrap)
        self.status_label.setStyleSheet("""
            QTextEdit {
                color: #666; 
                font-style: italic; 
                background-color: rgba(245, 245, 245, 200);
                border: 1px solid #ccc;
                border-radius: 3px;
                padding: 5px;
            }
        """)
        self.status_label.setText("Ready")
        content_layout.addWidget(self.status_label)

        # Action Buttons
        button_layout = QHBoxLayout()
        load_params_button = QPushButton("Load Parameters")
        load_params_button.setMinimumHeight(40)
        load_params_button.setMinimumWidth(130)
        load_params_button.clicked.connect(self.load_parameters)
        load_params_button.setStyleSheet("""
            QPushButton { background-color: #FF9800; color: white; font-weight: bold; border-radius: 5px; padding: 8px; }
            QPushButton:hover { background-color: #F57C00; }
        """)
        
        save_params_button = QPushButton("Save Parameters")
        save_params_button.setMinimumHeight(40)
        save_params_button.setMinimumWidth(130)
        save_params_button.clicked.connect(self.save_parameters)
        save_params_button.setStyleSheet("""
            QPushButton { background-color: #9C27B0; color: white; font-weight: bold; border-radius: 5px; padding: 8px; }
            QPushButton:hover { background-color: #7B1FA2; }
        """)
        
        self.run_button = QPushButton("Run Analysis")
        self.run_button.setMinimumHeight(40)
        self.run_button.setMinimumWidth(140)
        self.run_button.clicked.connect(self.run_analysis)
        self.run_button.setStyleSheet("""
            QPushButton { background-color: #4CAF50; color: white; font-weight: bold; border-radius: 5px; padding: 8px; }
            QPushButton:hover { background-color: #45a049; }
        """)

        quit_button = QPushButton("Quit")
        quit_button.setMinimumHeight(40)
        quit_button.setMinimumWidth(100)
        quit_button.clicked.connect(self.close)
        quit_button.setStyleSheet("""
            QPushButton { background-color: #f44336; color: white; font-weight: bold; border-radius: 5px; padding: 8px; }
            QPushButton:hover { background-color: #da190b; }
        """)

        button_layout.addWidget(load_params_button)
        button_layout.addWidget(save_params_button)
        button_layout.addStretch()
        button_layout.addWidget(self.run_button)
        button_layout.addWidget(quit_button)
        content_layout.addLayout(button_layout)

        main_layout.addWidget(content_widget, stretch=3)

        # 3. Console Pane (Right)
        console_widget = QWidget()
        console_widget.setStyleSheet("background-color: rgba(30, 30, 30, 220); border-radius: 10px;")
        console_pane_layout = QVBoxLayout(console_widget)
        
        console_title = QLabel("Processing Console")
        console_title.setStyleSheet("color: white; font-weight: bold; font-size: 14px; margin-top: 5px;")
        console_title.setAlignment(Qt.AlignCenter)
        console_pane_layout.addWidget(console_title)

        self.console = QTextEdit()
        self.console.setReadOnly(True)
        self.console.setFont(QFont("Courier", 9))
        self.console.setLineWrapMode(QTextEdit.NoWrap)
        self.console.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                border: 1px solid #3e3e3e;
            }
        """)
        console_pane_layout.addWidget(self.console)
        
        main_layout.addWidget(console_widget, stretch=2)

        self.statusBar().showMessage("Ready to process")

        # Initial message
        self.append_console("""
###############################################################################
SedInConnect 3.0 - Sediment Connectivity Index Tool
Copyright (C) 2014-2025 CNR-IRPI, Padova (Italy)
Licensed under GNU GPL v2

Based on: Cavalli et al., 2013 - Geomorphology
Developed within the MORPHEUS Project framework
###############################################################################

Ready to start processing...
        """)

    def create_sidebar(self) -> QWidget:
        """Create sidebar with project logo and info"""
        sidebar = QWidget()
        sidebar.setMinimumWidth(250)
        sidebar.setMaximumWidth(250)
        sidebar.setStyleSheet("""
            QWidget {
                background-color: rgba(255, 255, 255, 180);
                border-radius: 10px;
                padding: 5px;
            }
        """)

        layout = QVBoxLayout(sidebar)
        layout.setSpacing(15)
        layout.setContentsMargins(10, 10, 10, 10)

        logo_path = resource_path("logo.png")
        if logo_path.exists():
            logo_label = QLabel()
            pixmap = QtGui.QPixmap(str(logo_path))
            scaled_pixmap = pixmap.scaled(311, 203, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            logo_label.setPixmap(scaled_pixmap)
            logo_label.setAlignment(Qt.AlignCenter)
            layout.addWidget(logo_label)
        else:
            self._add_logo_placeholder(layout)

        description_scroll = QScrollArea()
        description_scroll.setWidgetResizable(True)
        description_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        description = QLabel(
            "<b>MORPHEUS Project</b><br>"
            "<i>GeoMORPHomEtry throUgh Scales for a resilient landscape</i><br><br>"
            "Understanding sediment dynamics and connectivity through geomorphometric "
            "techniques at multiple spatial and temporal scales.<br><br>"
            "<i>SedInConnect 3.0</i> represents a major advancement in connectivity analysis."
        )
        description.setWordWrap(True)
        description.setFont(QFont("Arial", 9))
        description.setStyleSheet("""
            QLabel {
                color: #222;
                padding: 10px;
                background-color: rgba(240, 240, 240, 160);
                border-radius: 5px;
            }
        """)
        description_scroll.setWidget(description)
        layout.addWidget(description_scroll)

        cnr_label = QLabel("<b>CNR-IRPI</b><br>Padova, Italy")
        cnr_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(cnr_label)

        logo2_path = resource_path("logo2.png")
        if logo2_path.exists():
            logo2_label = QLabel()
            pixmap2 = QtGui.QPixmap(str(logo2_path)).scaled(276, 120, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            logo2_label.setPixmap(pixmap2)
            logo2_label.setAlignment(Qt.AlignCenter)
            layout.addWidget(logo2_label)

        help_button = QPushButton("? Help & Documentation")
        help_button.setMinimumHeight(40)
        help_button.clicked.connect(self.show_help)
        help_button.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                font-size: 12px;
                font-weight: bold;
                border-radius: 5px;
                border: 2px solid #2196F3;
                padding: 8px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
        """)
        layout.addWidget(help_button)
        layout.addStretch()

        version_label = QLabel("<b>Version 3.0 (2025)</b><br>Stefano Crema<br>Marco Cavalli")
        version_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(version_label)
        return sidebar

    def _add_logo_placeholder(self, layout):
        l = QLabel("MORPHEUS\nProject")
        l.setFont(QFont("Arial", 18, QFont.Bold))
        l.setAlignment(Qt.AlignCenter)
        l.setStyleSheet("color: #2196F3; padding: 20px;")
        layout.addWidget(l)

    def create_input_group(self) -> QGroupBox:
        group = QGroupBox("Input Files")
        group.setStyleSheet("QGroupBox { font-weight: bold; color: #2E7D32; border: 1px solid #ccc; margin-top: 10px; padding-top: 15px; }")
        layout = QGridLayout(group)
        button_style = """
            QPushButton { padding: 8px 16px; background-color: #2196F3; color: white; border: 2px solid #2196F3; border-radius: 4px; font-weight: bold; }
            QPushButton:hover { background-color: #1976D2; }
        """
        layout.addWidget(QLabel("DTM (filled):"), 0, 0)
        self.dtm_input = QLineEdit()
        self.dtm_input.setPlaceholderText("Select filled DTM raster (*.tif)")
        layout.addWidget(self.dtm_input, 0, 1)
        dtm_button = QPushButton("Browse...")
        dtm_button.setStyleSheet(button_style)
        dtm_button.clicked.connect(lambda: self.browse_file(self.dtm_input, "GeoTIFF (*.tif)"))
        layout.addWidget(dtm_button, 0, 2)

        layout.addWidget(QLabel("Weight raster:"), 1, 0)
        self.weight_input = QLineEdit()
        self.weight_input.setPlaceholderText("Select weight raster or use automatic computation")
        layout.addWidget(self.weight_input, 1, 1)
        weight_button = QPushButton("Browse...")
        weight_button.setStyleSheet(button_style)
        weight_button.clicked.connect(lambda: self.browse_file(self.weight_input, "GeoTIFF (*.tif)"))
        layout.addWidget(weight_button, 1, 2)

        layout.addWidget(QLabel("Cell size (m):"), 2, 0)
        self.cell_size_input = QLineEdit("2.5")
        self.cell_size_input.setMaximumWidth(100)
        layout.addWidget(self.cell_size_input, 2, 1, 1, 2)
        return group

    def create_options_group(self) -> QGroupBox:
        group = QGroupBox("Options")
        group.setStyleSheet("QGroupBox { font-weight: bold; color: #2E7D32; border: 1px solid #ccc; margin-top: 10px; padding-top: 15px; }")
        layout = QGridLayout(group)
        button_style = """
            QPushButton { padding: 8px 16px; background-color: #2196F3; color: white; border: 2px solid #2196F3; border-radius: 4px; font-weight: bold; }
            QPushButton:hover { background-color: #1976D2; }
            QPushButton:disabled { background-color: #cccccc; color: #666; border: 2px solid #999; }
        """
        self.use_targets_cb = QCheckBox("Use target areas")
        self.use_targets_cb.stateChanged.connect(self.toggle_targets)
        layout.addWidget(self.use_targets_cb, 0, 0)
        self.target_input = QLineEdit()
        self.target_input.setPlaceholderText("Select target shapefile (*.shp)")
        self.target_input.setEnabled(False)
        layout.addWidget(self.target_input, 0, 1)
        self.target_button = QPushButton("Browse...")
        self.target_button.setEnabled(False)
        self.target_button.setStyleSheet(button_style)
        self.target_button.clicked.connect(lambda: self.browse_file(self.target_input, "Shapefile (*.shp)"))
        layout.addWidget(self.target_button, 0, 2)

        self.use_sinks_cb = QCheckBox("Use sink areas")
        self.use_sinks_cb.stateChanged.connect(self.toggle_sinks)
        layout.addWidget(self.use_sinks_cb, 1, 0)
        self.sink_input = QLineEdit()
        self.sink_input.setPlaceholderText("Select sink shapefile (*.shp)")
        self.sink_input.setEnabled(False)
        layout.addWidget(self.sink_input, 1, 1)
        self.sink_button = QPushButton("Browse...")
        self.sink_button.setEnabled(False)
        self.sink_button.setStyleSheet(button_style)
        self.sink_button.clicked.connect(lambda: self.browse_file(self.sink_input, "Shapefile (*.shp)"))
        layout.addWidget(self.sink_button, 1, 2)

        self.auto_weight_cb = QCheckBox("Compute W automatically (Cavalli et al., 2013)")
        self.auto_weight_cb.stateChanged.connect(self.toggle_auto_weight)
        layout.addWidget(self.auto_weight_cb, 2, 0, 1, 3)

        self.normalize_cb = QCheckBox("Normalize W")
        self.normalize_cb.setEnabled(False)
        layout.addWidget(self.normalize_cb, 3, 0, 1, 2)

        layout.addWidget(QLabel("Window size:"), 3, 2)
        self.window_size_input = QLineEdit("5")
        self.window_size_input.setMaximumWidth(60)
        self.window_size_input.setEnabled(False)
        layout.addWidget(self.window_size_input, 3, 3)

        self.save_components_cb = QCheckBox("Save upslope/downslope components")
        layout.addWidget(self.save_components_cb, 4, 0, 1, 3)
        return group

    def create_output_group(self) -> QGroupBox:
        group = QGroupBox("Output")
        group.setStyleSheet("QGroupBox { font-weight: bold; color: #2E7D32; border: 1px solid #ccc; margin-top: 10px; padding-top: 15px; }")
        layout = QGridLayout(group)
        layout.addWidget(QLabel("Connectivity Index:"), 0, 0)
        self.output_input = QLineEdit()
        self.output_input.setPlaceholderText("Select output location for IC raster")
        layout.addWidget(self.output_input, 0, 1)
        output_button = QPushButton("Browse...")
        output_button.setStyleSheet("""
            QPushButton { padding: 8px 16px; background-color: #2196F3; color: white; border: 2px solid #2196F3; border-radius: 4px; font-weight: bold; }
            QPushButton:hover { background-color: #1976D2; }
        """)
        output_button.clicked.connect(lambda: self.browse_save_file(self.output_input, "GeoTIFF (*.tif)"))
        layout.addWidget(output_button, 0, 2)
        return group

    def set_modern_style(self):
        self.setStyleSheet("""
            QMainWindow { background-color: #f5f5f5; }
            QGroupBox { font-weight: bold; border: 2px solid #ccc; border-radius: 5px; margin-top: 10px; padding-top: 10px; background-color: rgba(255, 255, 255, 200); }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }
            QLineEdit { padding: 8px; border: 1px solid #ccc; border-radius: 4px; background-color: white; }
            QLineEdit:focus { border: 2px solid #4CAF50; }
            QCheckBox { spacing: 8px; }
            QCheckBox::indicator { width: 18px; height: 18px; border: 1px solid #999; background-color: white; border-radius: 2px; }
            QCheckBox::indicator:hover { border: 1px solid #4CAF50; }
            QCheckBox::indicator:checked { background-color: #4CAF50; border: 1px solid #2E7D32; }
        """)

    def append_console(self, text: str):
        self.console.append(text)
        self.console.moveCursor(QTextCursor.End)
        QApplication.processEvents()

    def browse_file(self, line_edit: QLineEdit, filter_str: str):
        filename, _ = QFileDialog.getOpenFileName(self, "Select File", "", filter_str)
        if filename:
            line_edit.setText(filename)
            if line_edit == self.dtm_input:
                try: self.cell_size_input.setText(str(self._get_cell_size(filename)))
                except: pass

    def browse_save_file(self, line_edit: QLineEdit, filter_str: str):
        filename, _ = QFileDialog.getSaveFileName(self, "Save File", "", filter_str)
        if filename: line_edit.setText(filename)

    def toggle_targets(self, state):
        enabled = state == Qt.Checked
        self.target_input.setEnabled(enabled)
        self.target_button.setEnabled(enabled)

    def toggle_sinks(self, state):
        enabled = state == Qt.Checked
        self.sink_input.setEnabled(enabled)
        self.sink_button.setEnabled(enabled)

    def toggle_auto_weight(self, state):
        enabled = state == Qt.Checked
        self.weight_input.setEnabled(not enabled)
        self.normalize_cb.setEnabled(enabled)
        self.window_size_input.setEnabled(enabled)
        
        if enabled:
            msg = QMessageBox(self)
            msg.setIcon(QMessageBox.Warning)
            msg.setWindowTitle("⚠️ Beware: The Curse of Counterintuitiveness!")
            msg.setText("<b>Wait! Are you sure about that window size?</b>")
            msg.setInformativeText(
                "Roughness and slope behavior can be quite mischievous at larger cell sizes. "
                "Choosing the wrong moving window dimension might lead to results more confusing than "
                "a map with no legend!<br><br>"
                "<i>Remember: With great resolution comes great responsibility (and potentially weird roughness behavior).</i>"
            )
            msg.setStandardButtons(QMessageBox.Ok)
            msg.exec_()

    def _get_cell_size(self, dtm_path):
        from osgeo import gdal
        ds = gdal.Open(str(dtm_path))
        gt = ds.GetGeoTransform()
        return abs(gt[1])

    def validate_inputs(self) -> Optional[ProcessingParams]:
        if not self.dtm_input.text():
            QMessageBox.warning(self, "Missing Input", "Please select a DTM file")
            return None
        if not self.output_input.text():
            QMessageBox.warning(self, "Missing Output", "Please specify output location")
            return None
        try: cell_size = float(self.cell_size_input.text())
        except ValueError:
            QMessageBox.warning(self, "Invalid Input", "Cell size must be a number")
            return None
        params = ProcessingParams(
            dtm_path=Path(self.dtm_input.text()),
            cell_size=cell_size,
            output_path=Path(self.output_input.text()),
            weight_path=Path(self.weight_input.text()) if self.weight_input.text() else None,
            target_path=Path(self.target_input.text()) if self.use_targets_cb.isChecked() else None,
            sink_path=Path(self.sink_input.text()) if self.use_sinks_cb.isChecked() else None,
            use_cavalli_weight=self.auto_weight_cb.isChecked(),
            normalize_weight=self.normalize_cb.isChecked(),
            save_components=self.save_components_cb.isChecked(),
            window_size=int(self.window_size_input.text()) if self.auto_weight_cb.isChecked() else 5
        )
        return params

    def save_parameters(self):
        params = self.validate_inputs()
        if not params: return
        filename, _ = QFileDialog.getSaveFileName(self, "Save Parameters", "", "JSON Files (*.json)")
        if filename:
            try:
                params.save_to_file(Path(filename))
                QMessageBox.information(self, "Success", f"Parameters saved to:\n{filename}")
            except Exception as e: QMessageBox.critical(self, "Error", str(e))

    def load_parameters(self):
        filename, _ = QFileDialog.getOpenFileName(self, "Load Parameters", "", "JSON Files (*.json)")
        if filename:
            try:
                p = ProcessingParams.load_from_file(Path(filename))
                self.dtm_input.setText(str(p.dtm_path))
                self.cell_size_input.setText(str(p.cell_size))
                self.output_input.setText(str(p.output_path))
                self.auto_weight_cb.setChecked(p.use_cavalli_weight)
                if p.weight_path: self.weight_input.setText(str(p.weight_path))
                if p.target_path: 
                    self.use_targets_cb.setChecked(True)
                    self.target_input.setText(str(p.target_path))
                if p.sink_path:
                    self.use_sinks_cb.setChecked(True)
                    self.sink_input.setText(str(p.sink_path))
                self.save_components_cb.setChecked(p.save_components)
                self.window_size_input.setText(str(p.window_size))
                self.normalize_cb.setChecked(p.normalize_weight)
                QMessageBox.information(self, "Success", "Parameters loaded!")
            except Exception as e: QMessageBox.critical(self, "Error", str(e))

    def run_analysis(self):
        params = self.validate_inputs()
        if not params: return
        self.run_button.setEnabled(False)
        self.progress_bar.setValue(0)
        self.console.clear()
        self.worker_thread = ProcessingThread(params, self.processor)
        self.worker_thread.console_output.connect(self.append_console)
        self.worker_thread.finished.connect(self.processing_finished)
        self.worker_thread.start()

    def processing_finished(self, success: bool, message: str):
        self.run_button.setEnabled(True)
        if success:
            QMessageBox.information(self, "Success", message)
            self.progress_bar.setValue(100)
            try:
                preview = ResultPreviewDialog(Path(self.output_input.text()), self)
                preview.exec_()
            except: pass
        else: QMessageBox.critical(self, "Error", message)

    def show_help(self):
        help_dialog = QtWidgets.QDialog(self)
        help_dialog.setWindowTitle("SedInConnect 3.0 - Help & Documentation")
        help_dialog.setMinimumSize(900, 700)
        help_dialog.resize(1000, 800)
        main_layout = QVBoxLayout(help_dialog)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        help_label = QLabel()
        help_label.setWordWrap(True)
        help_label.setTextFormat(Qt.RichText)
        help_label.setOpenExternalLinks(True)
        
        help_text = """
<h2 style="color: #2196F3;">SedInConnect 3.0 - User Guide</h2>
<p><b>Version 3.0 (2025)</b><br>
<b>Authors:</b> Stefano Crema and Marco Cavalli<br>
CNR-IRPI, Padova, Italy</p>
<hr>
<h3 style="color: #4CAF50;">What is Sediment Connectivity?</h3>
<p><b>Sediment connectivity</b> describes the potential for sediment transfer through a landscape, 
from source areas (hillslopes) to targets (channels, outlets, or specific areas of interest).</p>
<p>The <b>Index of Connectivity (IC)</b> (Cavalli et al., 2013) is a geomorphometric index that 
quantifies this connectivity.</p>
        """
        help_label.setText(help_text)
        content_layout.addWidget(help_label)
        
        diagram_path = resource_path("borselli_ic_EMS.png")
        if diagram_path.exists():
            diagram_label = QLabel()
            diagram_label.setPixmap(QtGui.QPixmap(str(diagram_path)).scaledToWidth(425, Qt.SmoothTransformation))
            diagram_label.setAlignment(Qt.AlignCenter)
            content_layout.addWidget(diagram_label)

        help_label2 = QLabel()
        help_label2.setWordWrap(True)
        help_label2.setTextFormat(Qt.RichText)
        help_label2.setText("""
<hr><h3 style="color: #4CAF50;">How to Use SedInConnect 3.0</h3>
<p><b>1. Required Inputs:</b> Pit-filled DTM and cell size.</p>
<p><b>2. Weighting Factor:</b> Manual raster or automatic from roughness.</p>
<p><b>3. Optional Features:</b> Target areas and Sink areas.</p>
<hr><h3 style="color: #4CAF50;">References</h3>
<p>Cavalli et al. (2013). Geomorphology, 188, 31-41.</p>
<p>Crema & Cavalli (2018). Computers & Geosciences, 111, 39-45.</p>
        """)
        content_layout.addWidget(help_label2)
        scroll.setWidget(content_widget)
        main_layout.addWidget(scroll)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(help_dialog.accept)
        main_layout.addWidget(close_btn)
        help_dialog.exec_()

    def resizeEvent(self, event):
        if hasattr(self, '_bg_pixmap'):
            central_widget = self.centralWidget()
            palette = central_widget.palette()
            scaled_pixmap = self._bg_pixmap.scaled(self.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            palette.setBrush(QPalette.Window, QBrush(scaled_pixmap))
            central_widget.setPalette(palette)
        super().resizeEvent(event)
