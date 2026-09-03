import os
import numpy as np
from pathlib import Path

try:
    from qgis.PyQt import QtWidgets, QtCore, QtGui
    from qgis.PyQt.QtWidgets import (QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
                                     QMessageBox, QWidget, QFileDialog)
    from qgis.PyQt.QtCore import Qt
except ImportError:
    try:
        from PyQt5 import QtWidgets, QtCore, QtGui
        from PyQt5.QtWidgets import (QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
                                     QMessageBox, QWidget, QFileDialog)
        from PyQt5.QtCore import Qt
    except ImportError:
        from PyQt6 import QtWidgets, QtCore, QtGui
        from PyQt6.QtWidgets import (QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
                                     QMessageBox, QWidget, QFileDialog)
        from PyQt6.QtCore import Qt

from sedinconnect.utils.raster import LargeFileRasterReader

# Cross-version enum
Qt_AlignCenter = getattr(Qt, "AlignCenter", None) or getattr(getattr(Qt, "AlignmentFlag", None), "AlignCenter", None)
Qt_Horizontal = getattr(Qt, "Horizontal", None) or getattr(getattr(Qt, "Orientation", None), "Horizontal", None)


class ResultPreviewDialog(QtWidgets.QDialog):
    """Dialog to preview IC results with map and statistics matching v3.0 style"""

    def __init__(self, ic_raster_path: Path, parent=None):
        super().__init__(parent)
        self.ic_path = Path(ic_raster_path)
        self.setWindowTitle("SedInConnect Results Preview")
        self.setMinimumSize(1200, 700)
        self.resize(1400, 800)

        # Load raster data
        try:
            with LargeFileRasterReader(self.ic_path) as reader:
                raw_data = reader.read_array()
                self.geotransform = reader.geotransform
                ndv = reader.nodata

            self.ic_data = raw_data.astype(np.float64)
            invalid_mask = np.isnan(self.ic_data) | np.isinf(self.ic_data) | (self.ic_data < -1e10)
            if ndv is not None:
                invalid_mask |= np.isclose(self.ic_data, ndv)
            invalid_mask |= (self.ic_data <= -9990.0)

            self.ic_data[invalid_mask] = np.nan
            self.ic_data_valid = self.ic_data[~invalid_mask]

            if len(self.ic_data_valid) == 0:
                raise ValueError("No valid data in IC raster")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load IC raster:\n{str(e)}")
            self.reject()
            return

        self.init_ui()

    def init_ui(self):
        """Initialize the UI with delayed matplotlib imports"""
        from matplotlib.figure import Figure
        from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas

        main_layout = QHBoxLayout(self)

        # Left panel: Info & Statistics
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_panel.setMaximumWidth(400)

        # File info
        info_label = QLabel(f"<b>File:</b> {self.ic_path.name}")
        left_layout.addWidget(info_label)

        # Statistics
        stats_group = QtWidgets.QGroupBox("Raster Statistics")
        stats_layout = QVBoxLayout(stats_group)

        mean_val = float(np.mean(self.ic_data_valid))
        std_val = float(np.std(self.ic_data_valid))
        median_val = float(np.median(self.ic_data_valid))
        min_val = float(np.min(self.ic_data_valid))
        max_val = float(np.max(self.ic_data_valid))
        valid_count = len(self.ic_data_valid)

        stats_text = (
            f"<b>Valid Pixels:</b> {valid_count:,}<br>"
            f"<b>Mean:</b> {mean_val:.4f}<br>"
            f"<b>Std Dev:</b> {std_val:.4f}<br>"
            f"<b>Median:</b> {median_val:.4f}<br>"
            f"<b>Min:</b> {min_val:.4f}<br>"
            f"<b>Max:</b> {max_val:.4f}"
        )
        stats_label = QLabel(stats_text)
        stats_layout.addWidget(stats_label)
        left_layout.addWidget(stats_group)

        # Histogram Figure
        hist_fig = Figure(figsize=(4, 3), dpi=100)
        hist_canvas = FigureCanvas(hist_fig)
        ax_hist = hist_fig.add_subplot(111)
        ax_hist.hist(self.ic_data_valid, bins=50, color='#1E88E5', edgecolor='black', alpha=0.7)
        ax_hist.set_title("IC Distribution", fontsize=10)
        ax_hist.set_xlabel("Connectivity Index (IC)", fontsize=8)
        ax_hist.set_ylabel("Frequency", fontsize=8)
        ax_hist.grid(True, linestyle='--', alpha=0.5)
        hist_fig.tight_layout()
        left_layout.addWidget(hist_canvas)

        left_layout.addStretch()

        btn_close = QPushButton("Close")
        btn_close.clicked.connect(self.accept)
        left_layout.addWidget(btn_close)

        main_layout.addWidget(left_panel)

        # Right panel: Map Display
        map_fig = Figure(figsize=(8, 7), dpi=100)
        map_canvas = FigureCanvas(map_fig)
        ax_map = map_fig.add_subplot(111)

        # Custom cold-to-hot colormap
        im = ax_map.imshow(self.ic_data, cmap='jet', vmin=min_val, vmax=max_val)
        map_fig.colorbar(im, ax=ax_map, label="Sediment Connectivity Index (IC)")
        ax_map.set_title(f"SedInConnect IC Map — {self.ic_path.name}")
        ax_map.axis('off')
        map_fig.tight_layout()

        main_layout.addWidget(map_canvas, stretch=1)
