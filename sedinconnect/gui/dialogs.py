# -*- coding: utf-8 -*-
import os
import numpy as np
from pathlib import Path

try:
    from qgis.PyQt import QtWidgets, QtCore, QtGui
    from qgis.PyQt.QtWidgets import (QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
                                     QMessageBox, QWidget, QFileDialog, QGroupBox)
    from qgis.PyQt.QtCore import Qt
except ImportError:
    try:
        from PyQt5 import QtWidgets, QtCore, QtGui
        from PyQt5.QtWidgets import (QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
                                     QMessageBox, QWidget, QFileDialog, QGroupBox)
        from PyQt5.QtCore import Qt
    except ImportError:
        from PyQt6 import QtWidgets, QtCore, QtGui
        from PyQt6.QtWidgets import (QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
                                     QMessageBox, QWidget, QFileDialog, QGroupBox)
        from PyQt6.QtCore import Qt

from sedinconnect.utils.raster import LargeFileRasterReader

# Cross-version enum
Qt_AlignCenter = getattr(Qt, "AlignCenter", None) or getattr(getattr(Qt, "AlignmentFlag", None), "AlignCenter", None)


class ResultPreviewDialog(QtWidgets.QDialog):
    """Dialog to preview IC results with map and statistics with rich warm spectrum."""

    def __init__(self, ic_raster_path: Path, parent=None):
        super().__init__(parent)
        self.ic_path = Path(ic_raster_path)
        self.setWindowTitle("SedInConnect 3.2 — Results Preview & Statistics")
        self.setMinimumSize(1100, 680)
        self.resize(1300, 750)

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
        """Initialize the UI with universal Matplotlib Qt canvas."""
        from matplotlib.figure import Figure
        from matplotlib.colors import LinearSegmentedColormap

        # Safe cross-version Qt canvas
        try:
            from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
        except ImportError:
            try:
                from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
            except ImportError:
                from matplotlib.backends.backend_qt6agg import FigureCanvasQTAgg as FigureCanvas

        main_layout = QHBoxLayout(self)

        # Left panel: Info & Statistics
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_panel.setMaximumWidth(380)

        # File info
        info_label = QLabel(f"<b>Output File:</b> {self.ic_path.name}")
        info_label.setWordWrap(True)
        left_layout.addWidget(info_label)

        # Statistics Box
        stats_group = QGroupBox("Raster Statistics")
        stats_layout = QVBoxLayout(stats_group)

        mean_val = float(np.mean(self.ic_data_valid))
        std_val = float(np.std(self.ic_data_valid))
        median_val = float(np.median(self.ic_data_valid))
        min_val = float(np.min(self.ic_data_valid))
        max_val = float(np.max(self.ic_data_valid))
        p2_val = float(np.percentile(self.ic_data_valid, 2))
        p98_val = float(np.percentile(self.ic_data_valid, 98))
        valid_count = len(self.ic_data_valid)

        stats_text = (
            f"<b>Valid Pixels:</b> {valid_count:,}<br>"
            f"<b>Mean IC:</b> {mean_val:.3f}<br>"
            f"<b>Std Dev:</b> {std_val:.3f}<br>"
            f"<b>Median IC:</b> {median_val:.3f}<br>"
            f"<b>Min / Max:</b> {min_val:.2f} / {max_val:.2f}<br>"
            f"<b>2% - 98% Range:</b> [{p2_val:.2f}, {p98_val:.2f}]"
        )
        stats_label = QLabel(stats_text)
        stats_layout.addWidget(stats_label)
        left_layout.addWidget(stats_group)

        # Histogram Figure
        hist_fig = Figure(figsize=(4, 2.8), dpi=100)
        hist_fig.patch.set_facecolor('#F8F9FA')
        hist_canvas = FigureCanvas(hist_fig)
        ax_hist = hist_fig.add_subplot(111)
        ax_hist.hist(self.ic_data_valid, bins=50, color='#EA580C', edgecolor='#9A3412', alpha=0.85)
        ax_hist.axvline(median_val, color='#1E40AF', linestyle='--', linewidth=1.5, label=f'Median ({median_val:.2f})')
        ax_hist.set_title("IC Frequency Distribution", fontsize=9, fontweight='bold')
        ax_hist.set_xlabel("Connectivity Index (IC)", fontsize=8)
        ax_hist.set_ylabel("Pixel Count", fontsize=8)
        ax_hist.legend(fontsize=7)
        ax_hist.grid(True, linestyle=':', alpha=0.6)
        hist_fig.tight_layout()
        left_layout.addWidget(hist_canvas)

        left_layout.addStretch()

        btn_close = QPushButton("Close Preview")
        btn_close.setStyleSheet("background-color: #2E7D32; color: white; font-weight: bold; padding: 6px 16px; border-radius: 4px;")
        btn_close.clicked.connect(self.accept)
        left_layout.addWidget(btn_close)

        main_layout.addWidget(left_panel)

        # Right panel: Map Display with Rich Red Spectrum
        # Colors: Deep Blue -> Sky Blue -> Lime Green -> Warm Yellow -> Coral Orange -> Fiery Red -> Dark Crimson
        cdict = [
            (0.00, '#0F2D6E'),  # Lapislazuli Blue (lowest)
            (0.20, '#0284C7'),  # Ocean Blue
            (0.35, '#10B981'),  # Lime Green
            (0.50, '#FACC15'),  # Bright Yellow
            (0.65, '#F97316'),  # Vibrant Orange
            (0.80, '#EF4444'),  # Fiery Red
            (1.00, '#881337'),  # Deep Crimson (highest)
        ]
        cmap_ic = LinearSegmentedColormap.from_list('ic_rich_red', [c[1] for c in cdict], N=256)

        map_fig = Figure(figsize=(8, 7), dpi=100)
        map_fig.patch.set_facecolor('#FFFFFF')
        map_canvas = FigureCanvas(map_fig)
        ax_map = map_fig.add_subplot(111)

        # Use 1.5% - 98.5% percentile stretch for rich visual contrast with vibrant reds
        vmin = max(min_val, p2_val)
        vmax = min(max_val, p98_val)

        im = ax_map.imshow(self.ic_data, cmap=cmap_ic, vmin=vmin, vmax=vmax, interpolation='bilinear')
        cbar = map_fig.colorbar(im, ax=ax_map, fraction=0.035, pad=0.04)
        cbar.set_label("Sediment Connectivity Index (IC) — High (Red) to Low (Blue)", fontsize=8)
        ax_map.set_title(f"SedInConnect IC Map — {self.ic_path.name}", fontsize=11, fontweight='bold', pad=10)
        ax_map.axis('off')
        map_fig.tight_layout()

        main_layout.addWidget(map_canvas, stretch=1)
