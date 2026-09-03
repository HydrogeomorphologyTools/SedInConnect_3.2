import os
import sys
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Optional
try:
    from qgis.PyQt import QtWidgets, QtCore, QtGui
except ImportError:
    try:
        from PyQt5 import QtWidgets, QtCore, QtGui
    except ImportError:
        from PyQt6 import QtWidgets, QtCore, QtGui
try:
    from qgis.PyQt.QtWidgets import
except ImportError:
    try:
        from PyQt5.QtWidgets import
    except ImportError:
        from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QLabel, QLineEdit, QPushButton, QFileDialog, 
                             QProgressBar, QTextEdit, QFrame, QCheckBox, 
                             QSpinBox, QComboBox, QGroupBox, QMessageBox, QSplitter,
                             QScrollArea, QGridLayout, QApplication)
try:
    from qgis.PyQt.QtCore import
except ImportError:
    try:
        from PyQt5.QtCore import
    except ImportError:
        from PyQt6.QtCore import Qt, QThread, pyqtSignal
try:
    from qgis.PyQt.QtGui import
except ImportError:
    try:
        from PyQt5.QtGui import
    except ImportError:
        from PyQt6.QtGui import QFont, QPixmap, QPalette, QBrush, QTextCursor

from sedinconnect.core.processor import ConnectivityProcessor
from sedinconnect.utils.params import ProcessingParams
from sedinconnect.gui.dialogs import ResultPreviewDialog
from sedinconnect.utils.telemetry import track_app_launch

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev, package, and PyInstaller """
    try:
        if getattr(sys, 'frozen', False):
            base_path = Path(sys._MEIPASS)
            p = base_path / relative_path
            if p.exists():
                return p
            p_asset = base_path / "sedinconnect" / "assets" / relative_path
            if p_asset.exists():
                return p_asset

        # Package assets directory (sedinconnect/assets/)
        pkg_asset = Path(__file__).resolve().parent.parent / "assets" / relative_path
        if pkg_asset.exists():
            return pkg_asset

        # Development root directory (2 levels up from sedinconnect/gui/)
        base_path = Path(__file__).resolve().parent.parent.parent
        res_path = base_path / relative_path
        if res_path.exists():
            return res_path
    except Exception:
        pass
    local_path = Path(relative_path)
    if local_path.exists():
        return local_path
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
        self.processor._user_log = self.console_output.emit

    def run(self):
        try:
            self.processor.process(self.params)
            self.finished.emit(True, "Analysis completed successfully!")
        except Exception as e:
            import traceback
            error_msg = f"Error: {str(e)}\n\n{traceback.format_exc()}"
            self.finished.emit(False, error_msg)

class ModernConnectivityGUI(QMainWindow):
    """Modern PyQt5 GUI for SedInConnect 3.1 matching 3.0 visual design"""

    def __init__(self, processor_class=ConnectivityProcessor):
        super().__init__()
        try:
            track_app_launch("GUI")
        except Exception:
            pass
        self.processor = processor_class()
        self.worker_thread = None
        self.init_ui()

    def init_ui(self):
        """Initialize UI matching the final verified layout"""
        self.setWindowTitle("SedInConnect 3.2 - Sediment Connectivity Tool")
        self.setGeometry(100, 100, 1400, 900)
        self.setMinimumSize(1000, 700)

        # Set window icon
        logo2_path = resource_path("logo2.png")
        if not logo2_path.exists():
            logo2_path = resource_path("logo2.ico")
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

        title = QLabel("SedInConnect 3.2")
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

        # 3. Console Pane (Right) with translucent dark glass effect
        console_widget = QWidget()
        console_widget.setStyleSheet("background-color: rgba(30, 30, 30, 185); border-radius: 10px; border: 1px solid rgba(255, 255, 255, 40);")
        console_pane_layout = QVBoxLayout(console_widget)
        
        console_title = QLabel("Processing Console")
        console_title.setStyleSheet("color: white; font-weight: bold; font-size: 14px; margin-top: 5px; background: transparent; border: none;")
        console_title.setAlignment(Qt.AlignCenter)
        console_pane_layout.addWidget(console_title)

        self.console = QTextEdit()
        self.console.setReadOnly(True)
        self.console.setFont(QFont("Courier", 9))
        self.console.setLineWrapMode(QTextEdit.NoWrap)
        self.console.setStyleSheet("""
            QTextEdit {
                background-color: rgba(20, 20, 20, 190);
                color: #e0e0e0;
                border: 1px solid rgba(255, 255, 255, 30);
                border-radius: 5px;
                padding: 4px;
            }
        """)
        console_pane_layout.addWidget(self.console)
        
        main_layout.addWidget(console_widget, stretch=2)

        self.statusBar().showMessage("Ready to process")

        # Initial message
        self.append_console("""
###############################################################################
SedInConnect 3.2 - Sediment Connectivity Index Tool
Copyright (C) 2014-2026 CNR-IRPI, Padova (Italy)
Licensed under GNU GPL v2

Based on: Cavalli et al., 2013 - Geomorphology
Developed within the MORPHEUS PRIN 2023-2026 Project framework
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
            "<b>MORPHEUS PRIN 2023-2026 Project</b><br>"
            "<i>GeoMORPHomEtry throUgh Scales for a resilient landscape</i><br><br>"
            "Understanding sediment dynamics and connectivity through geomorphometric "
            "techniques at multiple spatial and temporal scales.<br><br>"
            "<i>SedInConnect 3.2</i> represents a major advancement in connectivity analysis with native Python algorithms."
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

        version_label = QLabel("<b>Version 3.2 (2026)</b><br>Stefano Crema<br>Marco Cavalli")
        version_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(version_label)
        return sidebar

    def _add_logo_placeholder(self, layout):
        l = QLabel("MORPHEUS\nPRIN 2023-2026")
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
        self.weight_button = QPushButton("Browse...")
        self.weight_button.setStyleSheet(button_style)
        self.weight_button.clicked.connect(lambda: self.browse_file(self.weight_input, "GeoTIFF (*.tif)"))
        layout.addWidget(self.weight_button, 1, 2)

        # Row 2: Cell size, Workers, Chunk size
        row2_widget = QWidget()
        row2_layout = QHBoxLayout(row2_widget)
        row2_layout.setContentsMargins(0, 0, 0, 0)
        row2_layout.setSpacing(10)

        row2_layout.addWidget(QLabel("Cell size (m):"))
        self.cell_size_input = QLineEdit("2.5")
        self.cell_size_input.setMaximumWidth(70)
        self.cell_size_input.setToolTip("DTM cell resolution in meters")
        row2_layout.addWidget(self.cell_size_input)

        row2_layout.addSpacing(15)

        row2_layout.addWidget(QLabel("CPU Workers:"))
        self.workers_spin = QSpinBox()
        max_cpus = os.cpu_count() or 8
        self.workers_spin.setRange(1, max_cpus)
        self.workers_spin.setValue(max(1, max_cpus - 4))
        self.workers_spin.setMinimumWidth(65)
        self.workers_spin.setMaximumWidth(75)
        self.workers_spin.setToolTip(f"Number of parallel CPU worker processes for Roughness/Weight (1 - {max_cpus})")
        row2_layout.addWidget(self.workers_spin)

        row2_layout.addSpacing(15)

        row2_layout.addWidget(QLabel("Chunk size (px):"))
        self.chunk_size_combo = QComboBox()
        self.chunk_size_combo.setEditable(True)
        for cs in [256, 512, 1024, 2048, 4096, 8192]:
            self.chunk_size_combo.addItem(str(cs))
        self.chunk_size_combo.setCurrentText("1024")
        self.chunk_size_combo.setMinimumWidth(95)
        self.chunk_size_combo.setMaximumWidth(105)
        self.chunk_size_combo.setToolTip("Block size in pixels for Roughness and Weight computation (default 1024)")
        row2_layout.addWidget(self.chunk_size_combo)

        row2_layout.addStretch()
        layout.addWidget(row2_widget, 2, 0, 1, 3)
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
        # Row 0: Targets
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

        # Row 1: Sinks
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

        # Row 2: Auto weight
        self.auto_weight_cb = QCheckBox("Compute W automatically (Cavalli et al., 2013)")
        self.auto_weight_cb.stateChanged.connect(self.toggle_auto_weight)
        layout.addWidget(self.auto_weight_cb, 2, 0, 1, 3)

        # Row 3: Normalize & Window size
        self.normalize_cb = QCheckBox("Normalize W")
        self.normalize_cb.setEnabled(False)
        layout.addWidget(self.normalize_cb, 3, 0, 1, 2)

        layout.addWidget(QLabel("Window size:"), 3, 2)
        self.window_size_input = QLineEdit("5")
        self.window_size_input.setMaximumWidth(60)
        self.window_size_input.setEnabled(False)
        layout.addWidget(self.window_size_input, 3, 3)

        # Row 4: Save components master checkbox
        self.save_components_cb = QCheckBox("Save upslope (D_up) and downslope (D_down) components")
        self.save_components_cb.stateChanged.connect(self.toggle_save_components)
        layout.addWidget(self.save_components_cb, 4, 0, 1, 3)

        # Row 5 & 6: D_up and D_down custom paths
        layout.addWidget(QLabel("  D_up raster:"), 5, 0)
        self.dup_output_input = QLineEdit()
        self.dup_output_input.setPlaceholderText("Optional: custom location for D_up (*.tif)")
        self.dup_output_input.setEnabled(False)
        layout.addWidget(self.dup_output_input, 5, 1)
        self.dup_output_button = QPushButton("Browse...")
        self.dup_output_button.setEnabled(False)
        self.dup_output_button.setStyleSheet(button_style)
        self.dup_output_button.clicked.connect(lambda: self.browse_save_file(self.dup_output_input, "GeoTIFF (*.tif)"))
        layout.addWidget(self.dup_output_button, 5, 2)

        layout.addWidget(QLabel("  D_down raster:"), 6, 0)
        self.ddown_output_input = QLineEdit()
        self.ddown_output_input.setPlaceholderText("Optional: custom location for D_down (*.tif)")
        self.ddown_output_input.setEnabled(False)
        layout.addWidget(self.ddown_output_input, 6, 1)
        self.ddown_output_button = QPushButton("Browse...")
        self.ddown_output_button.setEnabled(False)
        self.ddown_output_button.setStyleSheet(button_style)
        self.ddown_output_button.clicked.connect(lambda: self.browse_save_file(self.ddown_output_input, "GeoTIFF (*.tif)"))
        layout.addWidget(self.ddown_output_button, 6, 2)

        # Row 7: Pit fill
        self.fill_dtm_cb = QCheckBox("Fill DTM depressions (Priority-Flood pit removal before flow routing)")
        layout.addWidget(self.fill_dtm_cb, 7, 0, 1, 3)

        # Row 8: Show Preview Checkbox (Default TRUE)
        self.show_preview_cb = QCheckBox("Show results preview (map & distribution charts)")
        self.show_preview_cb.setChecked(True)
        layout.addWidget(self.show_preview_cb, 8, 0, 1, 3)

        # Row 9: Save Run Log Checkbox (Default TRUE)
        self.save_run_log_cb = QCheckBox("Save execution run log (sedinconnect_runs.log)")
        self.save_run_log_cb.setChecked(True)
        layout.addWidget(self.save_run_log_cb, 9, 0, 1, 3)

        return group

    def create_output_group(self) -> QGroupBox:
        group = QGroupBox("Output Files")
        group.setStyleSheet("QGroupBox { font-weight: bold; color: #2E7D32; border: 1px solid #ccc; margin-top: 10px; padding-top: 15px; }")
        layout = QGridLayout(group)
        button_style = """
            QPushButton { padding: 8px 16px; background-color: #2196F3; color: white; border: 2px solid #2196F3; border-radius: 4px; font-weight: bold; }
            QPushButton:hover { background-color: #1976D2; }
            QPushButton:disabled { background-color: #cccccc; color: #666; border: 2px solid #999; }
        """

        # Row 0: IC raster
        layout.addWidget(QLabel("Connectivity Index:"), 0, 0)
        self.output_input = QLineEdit()
        self.output_input.setPlaceholderText("Select output location for IC raster (*.tif)")
        layout.addWidget(self.output_input, 0, 1)
        output_button = QPushButton("Browse...")
        output_button.setStyleSheet(button_style)
        output_button.clicked.connect(lambda: self.browse_save_file(self.output_input, "GeoTIFF (*.tif)"))
        layout.addWidget(output_button, 0, 2)

        # Row 1: Roughness raster (optional)
        layout.addWidget(QLabel("Roughness raster:"), 1, 0)
        self.roughness_output_input = QLineEdit()
        self.roughness_output_input.setPlaceholderText("Save roughness raster (*.tif) — optional, requires auto-W")
        self.roughness_output_input.setEnabled(False)
        layout.addWidget(self.roughness_output_input, 1, 1)
        self.roughness_output_button = QPushButton("Browse...")
        self.roughness_output_button.setEnabled(False)
        self.roughness_output_button.setStyleSheet(button_style)
        self.roughness_output_button.clicked.connect(lambda: self.browse_save_file(self.roughness_output_input, "GeoTIFF (*.tif)"))
        layout.addWidget(self.roughness_output_button, 1, 2)

        # Row 2: Weight factor (W) raster (optional)
        layout.addWidget(QLabel("Weight factor (W):"), 2, 0)
        self.weight_output_input = QLineEdit()
        self.weight_output_input.setPlaceholderText("Save W raster (*.tif) — optional, requires auto-W")
        self.weight_output_input.setEnabled(False)
        layout.addWidget(self.weight_output_input, 2, 1)
        self.weight_output_button = QPushButton("Browse...")
        self.weight_output_button.setEnabled(False)
        self.weight_output_button.setStyleSheet(button_style)
        self.weight_output_button.clicked.connect(lambda: self.browse_save_file(self.weight_output_input, "GeoTIFF (*.tif)"))
        layout.addWidget(self.weight_output_button, 2, 2)

        return group

    def set_modern_style(self):
        arrow_up = str(resource_path('arrow_up.png')).replace('\\', '/')
        arrow_down = str(resource_path('arrow_down.png')).replace('\\', '/')
        arrow_combo = str(resource_path('arrow_combo.png')).replace('\\', '/')

        self.setStyleSheet(f"""
            QMainWindow {{ background-color: #f5f5f5; }}
            QGroupBox {{ font-weight: bold; border: 2px solid #ccc; border-radius: 5px; margin-top: 10px; padding-top: 10px; background-color: rgba(255, 255, 255, 200); }}
            QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 5px; }}
            QLineEdit {{ padding: 8px; border: 1px solid #ccc; border-radius: 4px; background-color: white; color: #222; font-size: 13px; }}
            QLineEdit:focus {{ border: 2px solid #4CAF50; }}
            
            QSpinBox {{
                padding: 4px 6px;
                padding-right: 22px;
                border: 1px solid #ccc;
                border-radius: 4px;
                background-color: #ffffff;
                color: #222;
                font-size: 13px;
                min-height: 24px;
            }}
            QSpinBox:focus {{ border: 2px solid #4CAF50; }}
            QSpinBox::up-button {{
                subcontrol-origin: border;
                subcontrol-position: top right;
                width: 20px;
                height: 14px;
                border-left: 1px solid #ccc;
                border-bottom: 1px solid #ccc;
                background-color: #f5f5f5;
                border-top-right-radius: 4px;
            }}
            QSpinBox::up-button:hover {{ background-color: #e0e0e0; }}
            QSpinBox::up-arrow {{
                image: url("{arrow_up}");
                width: 10px;
                height: 10px;
            }}
            QSpinBox::down-button {{
                subcontrol-origin: border;
                subcontrol-position: bottom right;
                width: 20px;
                height: 14px;
                border-left: 1px solid #ccc;
                background-color: #f5f5f5;
                border-bottom-right-radius: 4px;
            }}
            QSpinBox::down-button:hover {{ background-color: #e0e0e0; }}
            QSpinBox::down-arrow {{
                image: url("{arrow_down}");
                width: 10px;
                height: 10px;
            }}

            QComboBox {{
                padding: 4px 6px;
                padding-right: 24px;
                border: 1px solid #ccc;
                border-radius: 4px;
                background-color: #ffffff;
                color: #222;
                font-size: 13px;
                min-height: 24px;
            }}
            QComboBox:focus {{ border: 2px solid #4CAF50; }}
            QComboBox::drop-down {{
                subcontrol-origin: border;
                subcontrol-position: top right;
                width: 22px;
                border-left: 1px solid #ccc;
                background-color: #f5f5f5;
                border-top-right-radius: 4px;
                border-bottom-right-radius: 4px;
            }}
            QComboBox::drop-down:hover {{ background-color: #e0e0e0; }}
            QComboBox::down-arrow {{
                image: url("{arrow_combo}");
                width: 12px;
                height: 12px;
            }}
            QComboBox QAbstractItemView {{
                background-color: #ffffff;
                color: #222222;
                border: 1px solid #bbb;
                selection-background-color: #4CAF50;
                selection-color: #ffffff;
                padding: 4px;
            }}
            QComboBox QAbstractItemView::item {{
                min-height: 24px;
                padding: 4px;
                background-color: #ffffff;
                color: #222222;
            }}
            QComboBox QAbstractItemView::item:hover {{
                background-color: #E8F5E9;
                color: #1B5E20;
            }}
            QComboBox QAbstractItemView::item:selected {{
                background-color: #4CAF50;
                color: #ffffff;
            }}

            QCheckBox {{ spacing: 8px; }}
            QCheckBox::indicator {{ width: 18px; height: 18px; border: 1px solid #999; background-color: white; border-radius: 2px; }}
            QCheckBox::indicator:hover {{ border: 1px solid #4CAF50; }}
            QCheckBox::indicator:checked {{ background-color: #4CAF50; border: 1px solid #2E7D32; }}
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
                except Exception: pass

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

    def toggle_save_components(self, state):
        enabled = state == Qt.Checked
        if hasattr(self, 'dup_output_input'):
            self.dup_output_input.setEnabled(enabled)
            self.dup_output_button.setEnabled(enabled)
            self.ddown_output_input.setEnabled(enabled)
            self.ddown_output_button.setEnabled(enabled)

    def toggle_auto_weight(self, state):
        enabled = state == Qt.Checked
        self.weight_input.setEnabled(not enabled)
        if hasattr(self, 'weight_button'):
            self.weight_button.setEnabled(not enabled)
        self.normalize_cb.setEnabled(enabled)
        self.window_size_input.setEnabled(enabled)
        if hasattr(self, 'roughness_output_input'):
            self.roughness_output_input.setEnabled(enabled)
            self.roughness_output_button.setEnabled(enabled)
            self.weight_output_input.setEnabled(enabled)
            self.weight_output_button.setEnabled(enabled)
        
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
        cs = abs(gt[1])
        ds = None
        return cs

    def validate_inputs(self) -> Optional[ProcessingParams]:
        # 1. DTM Validation
        dtm_text = self.dtm_input.text().strip()
        if not dtm_text:
            QMessageBox.warning(
                self, "Missing DTM File",
                "Please select an input DTM raster file (*.tif) using the 'Browse...' button."
            )
            return None
        dtm_p = Path(dtm_text)
        if not dtm_p.exists():
            QMessageBox.warning(
                self, "Invalid DTM File",
                f"The specified DTM file was not found on disk:\n{dtm_text}\n\nPlease check the path or browse for the file."
            )
            return None

        # 2. Output Validation
        out_text = self.output_input.text().strip()
        if not out_text:
            QMessageBox.warning(
                self, "Missing Output Path",
                "Please specify the output location for the Connectivity Index (IC) raster (*.tif) using the 'Browse...' button."
            )
            return None

        # 3. Cell Size Validation
        try:
            cell_size = float(self.cell_size_input.text().strip())
            if cell_size <= 0:
                raise ValueError()
        except ValueError:
            QMessageBox.warning(
                self, "Invalid Cell Size",
                "Cell size must be a positive number in meters (e.g. 2.5)."
            )
            return None

        # 4. Target Areas Validation
        target_p = None
        if self.use_targets_cb.isChecked():
            target_text = self.target_input.text().strip()
            if not target_text:
                QMessageBox.warning(
                    self, "Missing Target Shapefile",
                    "You selected 'Use target areas', but no target shapefile (*.shp) was specified.\n\n"
                    "Please click the 'Browse...' button next to Target to select your shapefile, or uncheck the option."
                )
                return None
            target_p = Path(target_text)
            if not target_p.exists():
                QMessageBox.warning(
                    self, "Invalid Target File",
                    f"The specified target shapefile was not found on disk:\n{target_text}\n\nPlease check the path or select the file."
                )
                return None

        # 5. Sink Areas Validation
        sink_p = None
        if self.use_sinks_cb.isChecked():
            sink_text = self.sink_input.text().strip()
            if not sink_text:
                QMessageBox.warning(
                    self, "Missing Sink Shapefile",
                    "You selected 'Use sink areas', but no sink shapefile (*.shp) was specified.\n\n"
                    "Please click the 'Browse...' button next to Sink to select your shapefile, or uncheck the option."
                )
                return None
            sink_p = Path(sink_text)
            if not sink_p.exists():
                QMessageBox.warning(
                    self, "Invalid Sink File",
                    f"The specified sink shapefile was not found on disk:\n{sink_text}\n\nPlease check the path or select the file."
                )
                return None

        # 6. Weighting Factor Validation
        use_auto_w = self.auto_weight_cb.isChecked()
        weight_p = None
        if not use_auto_w:
            weight_text = self.weight_input.text().strip()
            if not weight_text:
                QMessageBox.warning(
                    self, "Missing Weight Raster",
                    "Automatic weight computation is disabled, but no custom weight raster (*.tif) was provided.\n\n"
                    "Please click 'Browse...' to select your weight raster, or check 'Compute W automatically'."
                )
                return None
            weight_p = Path(weight_text)
            if not weight_p.exists():
                QMessageBox.warning(
                    self, "Invalid Weight File",
                    f"The specified weight raster was not found on disk:\n{weight_text}\n\nPlease check the path or select the file."
                )
                return None
        else:
            if self.weight_input.text().strip():
                weight_p = Path(self.weight_input.text().strip())

        # 7. Moving Window Size Validation
        window_size = 5
        if use_auto_w:
            try:
                window_size = int(self.window_size_input.text().strip())
                if window_size < 3:
                    raise ValueError()
            except ValueError:
                QMessageBox.warning(
                    self, "Invalid Window Size",
                    "Moving window size for roughness must be an integer >= 3 (e.g. 5, 15, 25)."
                )
                return None

        # 8. Performance Parameters
        try:
            n_workers = int(self.workers_spin.value())
        except Exception:
            n_workers = None

        try:
            chunk_size = int(self.chunk_size_combo.currentText().strip())
            if chunk_size < 64:
                chunk_size = 1024
        except Exception:
            chunk_size = 1024

        params = ProcessingParams(
            dtm_path=dtm_p,
            cell_size=cell_size,
            output_path=Path(out_text),
            weight_path=weight_p,
            target_path=target_p,
            sink_path=sink_p,
            use_cavalli_weight=use_auto_w,
            normalize_weight=self.normalize_cb.isChecked(),
            save_components=self.save_components_cb.isChecked(),
            window_size=window_size,
            roughness_path=Path(self.roughness_output_input.text().strip()) if (hasattr(self, 'roughness_output_input') and self.roughness_output_input.text().strip()) else None,
            weight_output_path=Path(self.weight_output_input.text().strip()) if (hasattr(self, 'weight_output_input') and self.weight_output_input.text().strip()) else None,
            d_up_path=Path(self.dup_output_input.text().strip()) if (hasattr(self, 'dup_output_input') and self.dup_output_input.text().strip()) else None,
            d_down_path=Path(self.ddown_output_input.text().strip()) if (hasattr(self, 'ddown_output_input') and self.ddown_output_input.text().strip()) else None,
            show_preview=self.show_preview_cb.isChecked() if hasattr(self, 'show_preview_cb') else True,
            fill_dtm=self.fill_dtm_cb.isChecked() if hasattr(self, 'fill_dtm_cb') else False,
            n_workers=n_workers,
            chunk_size=chunk_size,
            save_run_log=self.save_run_log_cb.isChecked() if hasattr(self, 'save_run_log_cb') else True
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
                if hasattr(self, 'roughness_output_input'):
                    if p.roughness_path:
                        self.roughness_output_input.setText(str(p.roughness_path))
                    if p.weight_output_path:
                        self.weight_output_input.setText(str(p.weight_output_path))
                if hasattr(self, 'dup_output_input'):
                    if p.d_up_path:
                        self.dup_output_input.setText(str(p.d_up_path))
                    if p.d_down_path:
                        self.ddown_output_input.setText(str(p.d_down_path))
                if hasattr(self, 'show_preview_cb'):
                    self.show_preview_cb.setChecked(getattr(p, 'show_preview', True))
                if hasattr(self, 'fill_dtm_cb'):
                    self.fill_dtm_cb.setChecked(getattr(p, 'fill_dtm', False))
                if hasattr(self, 'workers_spin') and getattr(p, 'n_workers', None) is not None:
                    self.workers_spin.setValue(int(p.n_workers))
                if hasattr(self, 'chunk_size_combo') and getattr(p, 'chunk_size', None) is not None:
                    self.chunk_size_combo.setCurrentText(str(p.chunk_size))
                if hasattr(self, 'save_run_log_cb'):
                    self.save_run_log_cb.setChecked(getattr(p, 'save_run_log', True))
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
            if hasattr(self, 'show_preview_cb') and self.show_preview_cb.isChecked():
                try:
                    preview = ResultPreviewDialog(Path(self.output_input.text()), self)
                    preview.exec_()
                except Exception as e:
                    self.append_console(f"Preview error: {e}")
        else:
            QMessageBox.critical(self, "Error", message)

    def show_help(self):
        help_dialog = QtWidgets.QDialog(self)
        help_dialog.setWindowTitle("SedInConnect 3.2 - Help & Documentation")
        help_dialog.setMinimumSize(950, 750)
        help_dialog.resize(1050, 850)
        main_layout = QVBoxLayout(help_dialog)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(20, 20, 20, 20)
        content_layout.setSpacing(12)

        help_label = QLabel()
        help_label.setWordWrap(True)
        help_label.setTextFormat(Qt.RichText)
        help_label.setOpenExternalLinks(True)
        
        help_text_1 = """
<div style="font-family: 'Segoe UI', Arial, sans-serif; color: #2b2b2b; line-height: 1.5;">
<h1 style="color: #1976D2; margin-bottom: 2px;">SedInConnect 3.2</h1>
<h3 style="color: #555; margin-top: 0px; font-weight: normal;"><b>Stand-alone Tool for the Assessment of Sediment Connectivity</b></h3>
<p style="font-size: 11pt; color: #666; margin-bottom: 15px;">
<b>Version:</b> 3.2 (2026) &nbsp;|&nbsp; 
<b>Authors:</b> Stefano Crema and Marco Cavalli &nbsp;|&nbsp; 
<b>Affiliation:</b> CNR-IRPI (National Research Council - Research Institute for Geo-Hydrological Protection), Padova, Italy<br>
<b>Framework:</b> Developed within the <i>MORPHEUS PRIN 2023-2026 Project</i> (GeoMORPHomEtry throUgh Scales for a resilient landscape).
</p>
<hr style="border: 0; height: 1px; background: #ccc; margin: 15px 0;">

<h2 style="color: #2E7D32; border-bottom: 2px solid #2E7D32; padding-bottom: 4px;">1. Theoretical Background</h2>
<p style="font-size: 11pt;">
<b>Sediment connectivity</b> describes the degree of linkage that facilitates the transfer of sediment through a catchment, 
from sediment source areas (hillslopes, gullies, cliffs) to downstream targets (channel network, retention basins, infrastructures, or the catchment outlet).
</p>
<p style="font-size: 11pt;">
SedInConnect implements the geomorphometric <b>Index of Connectivity (IC)</b> proposed by <b>Borselli et al. (2008)</b> and 
adapted for mountain environments and high-resolution Digital Terrain Models (DTMs) by <b>Cavalli et al. (2013)</b>.
</p>

<div style="background-color: #f8f9fa; border-left: 5px solid #2196F3; padding: 12px 16px; margin: 12px 0; border-radius: 4px;">
<h3 style="margin-top: 0; color: #1565C0;">Mathematical Formulation of IC</h3>
<p style="font-size: 12pt; margin: 5px 0;"><b>IC = log<sub>10</sub> ( D<sub>up</sub> / D<sub>down</sub> )</b></p>
<p style="margin: 4px 0; font-size: 10.5pt;">where:</p>
<ul style="margin: 4px 0; font-size: 10.5pt;">
  <li><b>D<sub>up</sub> (Upslope Component):</b> Represents the potential for sediment routing driven by the upslope contributing area, local gradient, and surface properties:<br>
  <span style="font-size: 11pt; color: #0D47A1;"><b>D<sub>up</sub> = W̄ · S̄ · √A</b></span><br>
  where <i>A</i> is the upslope contributing area (m²), <i>S̄</i> is the average slope gradient of the upslope area (m/m), and <i>W̄</i> is the average weighting factor (impedance/roughness).
  </li>
  <li style="margin-top: 8px;"><b>D<sub>down</sub> (Downslope Component):</b> Represents the travel path resistance of sediment moving from the cell along the flow path to the target or outlet:<br>
  <span style="font-size: 11pt; color: #0D47A1;"><b>D<sub>down</sub> = ∑ ( d<sub>i</sub> / ( W<sub>i</sub> · S<sub>i</sub> ) )</b></span><br>
  where <i>d<sub>i</sub></i> is the length of the flow path along cell <i>i</i> (m), <i>W<sub>i</sub></i> is the local weighting factor, and <i>S<sub>i</sub></i> is the local slope gradient (clamped to a minimum of 0.005 to avoid division by zero).
  </li>
</ul>
</div>
<p style="font-size: 10.5pt; color: #444;">
<i>IC</i> is dimensionless and ranges in theory from -∞ to +∞, with typical values from -10 (low connectivity, decoupled areas) to +5 (high connectivity, intense coupling with the target).
</p>
</div>
        """
        help_label.setText(help_text_1)
        content_layout.addWidget(help_label)

        # Diagram
        diagram_path = resource_path("borselli_ic_EMS.png")
        if diagram_path.exists():
            diagram_label = QLabel()
            pixmap = QtGui.QPixmap(str(diagram_path))
            diagram_label.setPixmap(pixmap.scaledToWidth(520, Qt.SmoothTransformation))
            diagram_label.setAlignment(Qt.AlignCenter)
            diagram_label.setStyleSheet("margin: 10px 0; padding: 5px; background: white; border: 1px solid #ddd; border-radius: 6px;")
            content_layout.addWidget(diagram_label)

        help_label2 = QLabel()
        help_label2.setWordWrap(True)
        help_label2.setTextFormat(Qt.RichText)
        help_label2.setOpenExternalLinks(True)
        
        help_text_2 = """
<div style="font-family: 'Segoe UI', Arial, sans-serif; color: #2b2b2b; line-height: 1.5;">

<h2 style="color: #2E7D32; border-bottom: 2px solid #2E7D32; padding-bottom: 4px; margin-top: 20px;">2. Inputs & Parameter Description</h2>

<table style="width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 10.5pt;">
  <tr style="background-color: #e8f5e9;">
    <th style="border: 1px solid #c8e6c9; padding: 10px; text-align: left; width: 25%;">Parameter / Option</th>
    <th style="border: 1px solid #c8e6c9; padding: 10px; text-align: left;">Description & Implementation Details</th>
  </tr>
  <tr>
    <td style="border: 1px solid #ddd; padding: 10px; vertical-align: top;"><b>DTM (filled)</b><br><span style="color: #c62828; font-size: 9pt;">[Mandatory]</span></td>
    <td style="border: 1px solid #ddd; padding: 10px;">
      Input Digital Terrain Model in GeoTIFF format (<code>*.tif</code>).<br>
      • <b>Coordinate Reference System:</b> Must be in a <b>projected coordinate system</b> (e.g., UTM) with planar units in meters (X, Y, and Z).<br>
      • <b>Pit-filling:</b> The DTM should be hydrologically conditioned (sink-filled) to ensure continuous drainage routing. If raw DTM has sinks, enable <i>Fill DTM depressions</i>.
    </td>
  </tr>
  <tr style="background-color: #fafafa;">
    <td style="border: 1px solid #ddd; padding: 10px; vertical-align: top;"><b>Cell size (m)</b><br><span style="color: #c62828; font-size: 9pt;">[Mandatory]</span></td>
    <td style="border: 1px solid #ddd; padding: 10px;">
      Spatial resolution of the raster cell in meters. Automatically extracted from the DTM GeoTransform metadata when the file is selected, or can be manually verified.
    </td>
  </tr>
  <tr>
    <td style="border: 1px solid #ddd; padding: 10px; vertical-align: top;"><b>Weight raster (W)</b><br><span style="color: #555; font-size: 9pt;">[Custom / Automatic]</span></td>
    <td style="border: 1px solid #ddd; padding: 10px;">
      Represents the surface impedance to sediment movement (values between 0.001 and 1.0):<br>
      • <b>Custom Weight:</b> User-provided raster representing land-use impedance (e.g., C-factor from USLE/RUSLE, Manning's roughness, or vegetative cover).<br>
      • <b>Automatic Cavalli Weight:</b> Computed directly from high-resolution topography using surface roughness as a proxy for surface impedance.
    </td>
  </tr>
  <tr style="background-color: #fafafa;">
    <td style="border: 1px solid #ddd; padding: 10px; vertical-align: top;"><b>Compute W automatically<br>(Cavalli et al., 2013)</b></td>
    <td style="border: 1px solid #ddd; padding: 10px;">
      When checked, surface roughness is calculated as the standard deviation of residual elevation: <b>RI = std(DTM - μ<sub>local</sub>)</b> in a moving window.<br>
      The weighting factor is derived as: <b>W = 1.0 - (RI / RI<sub>max</sub>)</b>, with a minimum threshold clamped at 0.001 (smooth terrain has high W ≈ 1, rough terrain has low W ≈ 0.001).
    </td>
  </tr>
  <tr>
    <td style="border: 1px solid #ddd; padding: 10px; vertical-align: top;"><b>Normalize W<br>(Trevisani & Cavalli, 2016)</b></td>
    <td style="border: 1px solid #ddd; padding: 10px;">
      Applies a logarithmic transformation to the roughness index: <br>
      <b>W<sub>norm</sub> = 1.0 - [ ( ln(RI) - ln(RI<sub>min</sub>) ) / ( ln(RI<sub>max</sub>) - ln(RI<sub>min</sub>) ) ]</b><br>
      Reduces right-skewness and compression in high-relief mountainous catchments, producing a more balanced distribution of weighting values.
    </td>
  </tr>
  <tr style="background-color: #fafafa;">
    <td style="border: 1px solid #ddd; padding: 10px; vertical-align: top;"><b>Window size</b></td>
    <td style="border: 1px solid #ddd; padding: 10px;">
      Size in pixels of the moving square window (<i>N × N</i>, default 5) for roughness calculation. Must be an odd integer ≥ 3.<br>
      <i>Guidance:</i> A 5×5 window on a 2.5 m DTM corresponds to a 12.5 m spatial support, optimal for micro-topographic roughness without blurring morphological slope breaks.
    </td>
  </tr>
  <tr>
    <td style="border: 1px solid #ddd; padding: 10px; vertical-align: top;"><b>CPU Workers</b></td>
    <td style="border: 1px solid #ddd; padding: 10px;">
      Number of parallel CPU worker processes allocated to multi-core convolution and spatial chunk processing. Defaults to <code>CPU cores - 4</code> (or 1 on low-core systems) to keep the OS responsive.
    </td>
  </tr>
  <tr style="background-color: #fafafa;">
    <td style="border: 1px solid #ddd; padding: 10px; vertical-align: top;"><b>Chunk size (px)</b></td>
    <td style="border: 1px solid #ddd; padding: 10px;">
      Dimension in pixels of the memory tiles (e.g. 256, 512, 1024, 2048, 4096 px) processed concurrently. Multi-threading spatial chunking ensures seamless processing of massive rasters without RAM exhaustion, with bitwise numerical invariance across all chunk sizes.
    </td>
  </tr>
</table>

<h2 style="color: #2E7D32; border-bottom: 2px solid #2E7D32; padding-bottom: 4px; margin-top: 25px;">3. Target, Sink and Analysis Options</h2>

<table style="width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 10.5pt;">
  <tr style="background-color: #e8f5e9;">
    <th style="border: 1px solid #c8e6c9; padding: 10px; text-align: left; width: 28%;">Option</th>
    <th style="border: 1px solid #c8e6c9; padding: 10px; text-align: left;">Description</th>
  </tr>
  <tr>
    <td style="border: 1px solid #ddd; padding: 10px; vertical-align: top;"><b>Use target areas</b></td>
    <td style="border: 1px solid #ddd; padding: 10px;">
      When checked, connectivity is assessed specifically with respect to user-defined <b>targets</b> provided as an ESRI Shapefile (<code>*.shp</code>, polygons or polylines):<br>
      • <b>Examples:</b> Main stream channel network, reservoir rim, retention basin, road network, or specific property boundaries.<br>
      • <b>Default (unchecked):</b> Connectivity is computed towards the <b>catchment outlet</b> (all boundary drainage exit points).
    </td>
  </tr>
  <tr style="background-color: #fafafa;">
    <td style="border: 1px solid #ddd; padding: 10px; vertical-align: top;"><b>Use sink areas</b></td>
    <td style="border: 1px solid #ddd; padding: 10px;">
      When checked, user-defined <b>sinks</b> provided as an ESRI Shapefile (<code>*.shp</code>) act as absolute sediment traps (e.g. natural lakes, wetlands, karst sinkholes, quarries, debris retention basins):<br>
      • Areas draining into a sink are disconnected from the downstream target, terminating the flow path and correctly mapping landscape disconnection.
    </td>
  </tr>
  <tr>
    <td style="border: 1px solid #ddd; padding: 10px; vertical-align: top;"><b>Save upslope (D_up) and<br>downslope (D_down) components</b></td>
    <td style="border: 1px solid #ddd; padding: 10px;">
      When checked, enables the export of the two intermediate component rasters that form the IC ratio:<br>
      • <b>D_up raster (*.tif):</b> The numerator representing upslope sediment delivery potential (<i>D<sub>up</sub> = W̄ · S̄ · √A</i>).<br>
      • <b>D_down raster (*.tif):</b> The denominator representing travel path impedance to the target/outlet (<i>D<sub>down</sub> = ∑ d<sub>i</sub> / (W<sub>i</sub> · S<sub>i</sub>)</i>).<br>
      • <b>Custom paths:</b> Activates dedicated browse fields to specify custom output file paths. If left blank, they are automatically saved alongside the output IC raster.
    </td>
  </tr>
  <tr style="background-color: #fafafa;">
    <td style="border: 1px solid #ddd; padding: 10px; vertical-align: top;"><b>Save execution run log</b></td>
    <td style="border: 1px solid #ddd; padding: 10px;">
      Appends a detailed, timestamped record of the execution parameters, input rasters, elapsed runtime, and status to <code>sedinconnect_runs.log</code> in the output directory.
    </td>
  </tr>
  <tr>
    <td style="border: 1px solid #ddd; padding: 10px; vertical-align: top;"><b>Fill DTM depressions</b></td>
    <td style="border: 1px solid #ddd; padding: 10px;">
      Runs a high-performance Priority-Flood algorithm to automatically resolve spurious elevation depressions and pits before calculating flow directions.
    </td>
  </tr>
</table>

<h2 style="color: #2E7D32; border-bottom: 2px solid #2E7D32; padding-bottom: 4px; margin-top: 25px;">4. Outputs & Diagnostic Rasters</h2>

<table style="width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 10.5pt;">
  <tr style="background-color: #e8f5e9;">
    <th style="border: 1px solid #c8e6c9; padding: 10px; text-align: left; width: 28%;">Output File / Tool</th>
    <th style="border: 1px solid #c8e6c9; padding: 10px; text-align: left;">Details</th>
  </tr>
  <tr>
    <td style="border: 1px solid #ddd; padding: 10px; vertical-align: top;"><b>Connectivity Index (IC)</b><br><span style="color: #1976D2; font-size: 9pt;">[Main Output *.tif]</span></td>
    <td style="border: 1px solid #ddd; padding: 10px;">
      GeoTIFF raster containing the continuous logarithmic Index of Connectivity. Higher values (green) indicate higher connectivity to the target; lower values (red) indicate decoupled landscape units.
    </td>
  </tr>
  <tr style="background-color: #fafafa;">
    <td style="border: 1px solid #ddd; padding: 10px; vertical-align: top;"><b>D_up raster</b><br><span style="color: #555; font-size: 9pt;">[Optional Diagnostic *.tif]</span></td>
    <td style="border: 1px solid #ddd; padding: 10px;">
      Upslope potential component in meters. Useful to analyze contributing drainage areas and upslope morphological drive independently from flow paths.
    </td>
  </tr>
  <tr>
    <td style="border: 1px solid #ddd; padding: 10px; vertical-align: top;"><b>D_down raster</b><br><span style="color: #555; font-size: 9pt;">[Optional Diagnostic *.tif]</span></td>
    <td style="border: 1px solid #ddd; padding: 10px;">
      Weighted downslope flow path length in meters. Represents the cumulative impedance distance to the target or outlet.
    </td>
  </tr>
  <tr style="background-color: #fafafa;">
    <td style="border: 1px solid #ddd; padding: 10px; vertical-align: top;"><b>Roughness raster</b><br><span style="color: #555; font-size: 9pt;">[Optional Diagnostic *.tif]</span></td>
    <td style="border: 1px solid #ddd; padding: 10px;">
      Standard deviation of residual elevation (<i>RI</i>) in meters computed in the moving window. Can be exported when <i>Compute W automatically</i> is enabled.
    </td>
  </tr>
  <tr>
    <td style="border: 1px solid #ddd; padding: 10px; vertical-align: top;"><b>Weight factor (W) raster</b><br><span style="color: #555; font-size: 9pt;">[Optional Diagnostic *.tif]</span></td>
    <td style="border: 1px solid #ddd; padding: 10px;">
      Normalized surface weighting factor raster (values in range [0.001, 1.0]). Represents the surface impedance field used in <i>D<sub>up</sub></i> and <i>D<sub>down</sub></i>.
    </td>
  </tr>
  <tr style="background-color: #fafafa;">
    <td style="border: 1px solid #ddd; padding: 10px; vertical-align: top;"><b>Interactive Preview & Stats</b></td>
    <td style="border: 1px solid #ddd; padding: 10px;">
      Built-in visualizer that opens upon completion, showing the spatial map of IC, the frequency distribution histogram, descriptive statistics (mean, median, std, min, max), and export tools to save publication-ready figures.
    </td>
  </tr>
  <tr>
    <td style="border: 1px solid #ddd; padding: 10px; vertical-align: top;"><b>Run History Log</b><br><span style="color: #555; font-size: 9pt;">[sedinconnect_runs.log]</span></td>
    <td style="border: 1px solid #ddd; padding: 10px;">
      Persistent log file automatically updated with timestamps, paths, window sizes, and execution logs for full scientific reproducibility.
    </td>
  </tr>
</table>

<h2 style="color: #2E7D32; border-bottom: 2px solid #2E7D32; padding-bottom: 4px; margin-top: 25px;">5. Key Scientific References</h2>
<ul style="font-size: 10pt; line-height: 1.6; color: #333;">
  <li><b>Cavalli, M., Trevisani, S., Comiti, F., Marchi, L. (2013).</b> Geomorphometric assessment of spatial sediment connectivity in small Alpine catchments. <i>Geomorphology</i>, 188, 31-41. <a href="https://doi.org/10.1016/j.geomorph.2012.05.007">doi:10.1016/j.geomorph.2012.05.007</a></li>
  <li><b>Borselli, L., Cassi, P., Torri, D. (2008).</b> Prolegomena to sediment connectivity: Thinking with the flow. <i>Catena</i>, 75(3), 268-277. <a href="https://doi.org/10.1016/j.catena.2008.07.006">doi:10.1016/j.catena.2008.07.006</a></li>
  <li><b>Crema, S., Cavalli, M. (2018).</b> SedInConnect: a stand-alone, free and open source tool for the assessment of sediment connectivity. <i>Computers & Geosciences</i>, 111, 39-45. <a href="https://doi.org/10.1016/j.cageo.2017.10.009">doi:10.1016/j.cageo.2017.10.009</a></li>
  <li><b>Trevisani, S., Cavalli, M. (2016).</b> Topography-based flow-direction modeling: how much does spatial resolution matter? <i>Earth Surface Processes and Landforms</i>, 41(5), 658-670. <a href="https://doi.org/10.1002/esp.3854">doi:10.1002/esp.3854</a></li>
  <li><b>Tarboton, D. G. (1997).</b> A new method for the determination of flow directions and upslope areas in grid digital elevation models. <i>Water Resources Research</i>, 33(2), 309-319.</li>
  <li><b>Garbrecht, J., Martz, L. W. (1997).</b> The assignment of drainage direction over flat surfaces in raster digital elevation models. <i>Journal of Hydrology</i>, 193(1-4), 204-213.</li>
</ul>

<hr style="border: 0; height: 1px; background: #ccc; margin: 20px 0;">
<p style="text-align: center; color: #777; font-size: 9.5pt; line-height: 1.5;">
<b>SedInConnect 3.2</b> — Licensed under GNU General Public License v2 (GPLv2)<br>
CNR-IRPI Padova (Italy) &nbsp;|&nbsp; MORPHEUS PRIN 2023-2026 Project<br>
<span style="font-size: 8.5pt; color: #888; font-style: italic;">
This software transmits non-identifiable, anonymous usage statistics (such as application launches, general analysis parameters, and execution runtime) via secure HTTPS solely to monitor international scientific adoption and support research project reporting. No personal information, usernames, IP addresses, file paths, or dataset contents are ever collected.
</span>
</p>
</div>
        """
        help_label2.setText(help_text_2)
        content_layout.addWidget(help_label2)
        scroll.setWidget(content_widget)
        main_layout.addWidget(scroll)
        close_btn = QPushButton("Close")
        close_btn.setStyleSheet("padding: 8px 24px; background-color: #4CAF50; color: white; font-weight: bold; border-radius: 4px; font-size: 11pt;")
        close_btn.clicked.connect(help_dialog.accept)
        main_layout.addWidget(close_btn, alignment=Qt.AlignCenter)
        help_dialog.exec_()

    def resizeEvent(self, event):
        if hasattr(self, '_bg_pixmap'):
            central_widget = self.centralWidget()
            palette = central_widget.palette()
            scaled_pixmap = self._bg_pixmap.scaled(self.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            palette.setBrush(QPalette.Window, QBrush(scaled_pixmap))
            central_widget.setPalette(palette)
        super().resizeEvent(event)
