import os
import numpy as np
from pathlib import Path
from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtWidgets import (QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
                             QMessageBox, QWidget, QFileDialog)
from PyQt5.QtCore import Qt

from sedinconnect.utils.raster import LargeFileRasterReader

class ResultPreviewDialog(QtWidgets.QDialog):
    """Dialog to preview IC results with map and statistics"""

    def __init__(self, ic_raster_path: Path, parent=None):
        super().__init__(parent)
        self.ic_path = ic_raster_path
        self.setWindowTitle("SedInConnect Results Preview")
        self.setMinimumSize(1400, 800)
        self.resize(1600, 900)

        # Load raster data
        try:
            with LargeFileRasterReader(ic_raster_path) as reader:
                self.ic_data = reader.read_array()
                self.geotransform = reader.geotransform

            # Mask nodata
            self.ic_data_valid = self.ic_data[~np.isnan(self.ic_data)]

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
        from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar

        layout = QVBoxLayout(self)

        # Title
        title = QLabel(f"<h2>Connectivity Index Results</h2><p><i>{self.ic_path.name}</i></p>")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # Create horizontal splitter
        splitter = QtWidgets.QSplitter(Qt.Horizontal)

        # Left panel: IC Map
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        self.map_figure = Figure(figsize=(8, 10), facecolor='white')
        self.map_canvas = FigureCanvas(self.map_figure)
        self.map_toolbar = NavigationToolbar(self.map_canvas, self)
        left_layout.addWidget(QLabel("<b>Index of Connectivity (IC) Map</b>"))
        left_layout.addWidget(self.map_toolbar)
        left_layout.addWidget(self.map_canvas)
        self.plot_ic_map()
        splitter.addWidget(left_widget)

        # Right panel: Statistics
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        self.hist_figure = Figure(figsize=(6, 9), facecolor='white')
        self.hist_canvas = FigureCanvas(self.hist_figure)
        right_layout.addWidget(QLabel("<b>IC Distribution & Statistics</b>"))
        right_layout.addWidget(self.hist_canvas)
        self.plot_histogram_and_stats()
        splitter.addWidget(right_widget)

        splitter.setSizes([960, 640])
        layout.addWidget(splitter)

        # Close buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.export_btn = QPushButton("Export Figures...")
        self.export_btn.clicked.connect(self.export_figures)
        self.export_btn.setStyleSheet("background-color: #FF9800; color: white; font-weight: bold; padding: 8px;")
        button_layout.addWidget(self.export_btn)
        
        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self.accept)
        self.close_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold; padding: 8px;")
        button_layout.addWidget(self.close_btn)
        
        layout.addLayout(button_layout)

    def plot_ic_map(self):
        """Plot the IC map"""
        ax = self.map_figure.add_subplot(111)
        # Plot with inverted RdYlGn colormap (green = high connectivity, red = low)
        ic_masked = np.ma.masked_invalid(self.ic_data)
        im = ax.imshow(ic_masked, cmap='RdYlGn_r', aspect='equal', interpolation='nearest')
        
        cbar = self.map_figure.colorbar(im, ax=ax, orientation='vertical', pad=0.02, shrink=0.8)
        cbar.set_label('IC Value (log10)', fontsize=11, fontweight='bold')
        ax.set_title('Index of Connectivity', fontsize=13, fontweight='bold', pad=10)
        ax.axis('off')
        self.map_figure.tight_layout()
        self.map_canvas.draw()

    def plot_histogram_and_stats(self):
        """Plot histogram and compute statistics"""
        ic_valid = self.ic_data_valid
        mean_val = np.mean(ic_valid)
        median_val = np.median(ic_valid)
        
        ax = self.hist_figure.add_subplot(111)
        ax.hist(ic_valid, bins=50, color='steelblue', edgecolor='black', alpha=0.7)
        
        ax.axvline(mean_val, color='red', linestyle='--', label=f'Mean: {mean_val:.3f}')
        ax.axvline(median_val, color='green', linestyle='--', label=f'Median: {median_val:.3f}')
        
        ax.set_xlabel('IC Value (log10)', fontsize=12, fontweight='bold')
        ax.set_ylabel('Frequency', fontsize=12, fontweight='bold')
        ax.set_title('Distribution of IC Values', fontsize=13, fontweight='bold', pad=15)
        ax.legend()
        ax.grid(True, alpha=0.3, linestyle='--')
        self.hist_figure.tight_layout()
        self.hist_canvas.draw()

    def export_figures(self):
        """Export the figures as image files"""
        directory = QFileDialog.getExistingDirectory(self, "Select Export Directory")
        if not directory:
            return
        dir_path = Path(directory)
        try:
            self.map_figure.savefig(dir_path / f"{self.ic_path.stem}_map.png", dpi=300, bbox_inches='tight')
            self.hist_figure.savefig(dir_path / f"{self.ic_path.stem}_histogram.png", dpi=300, bbox_inches='tight')
            QMessageBox.information(self, "Export Successful", f"Figures exported to:\n{dir_path}")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to export figures:\n{str(e)}")
