"""
main2.py – SedInConnect 3.0 variant that adds the ability to save
the roughness raster and the weight-factor (W) raster to user-specified
GeoTIFF paths, both from the GUI and from the command line.

All existing behaviour (parallel processing, etc.) is left untouched.
Only additions:
  CLI : --save-roughness / --save-weight
  GUI : two extra "Browse…" rows in the Output group (enabled only when
        "Compute W automatically" is checked).
"""

import sys
import os
import ctypes
import dataclasses
import shutil
import multiprocessing
import argparse
from pathlib import Path
from osgeo import gdal

# Add project root to sys.path
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from sedinconnect.utils.params import ProcessingParams
from sedinconnect.core.processor import ConnectivityProcessor


# ---------------------------------------------------------------------------
# Logger (unchanged from main.py)
# ---------------------------------------------------------------------------
class Logger(object):
    def __init__(self, filename):
        self.terminal = sys.stdout
        try:
            self.log = open(filename, "w", buffering=1, encoding="utf-8")
        except Exception as e:
            print(f"Warning: Could not open log file {filename}: {e}")
            self.log = None

    def write(self, message):
        try:
            self.terminal.write(message)
        except:
            pass
        if self.log:
            try:
                self.log.write(message)
            except:
                pass

    def flush(self):
        try:
            self.terminal.flush()
        except:
            pass
        if self.log:
            try:
                self.log.flush()
            except:
                pass


# ---------------------------------------------------------------------------
# Extended processor: after process() copy files to user-specified paths
# ---------------------------------------------------------------------------
class ConnectivityProcessor2(ConnectivityProcessor):
    """
    Thin subclass: if the caller pre-set params.roughness_path or
    params.weight_output_path, those desired destinations are saved before
    the base process() overwrites them with the default locations.
    After processing the files are copied (if paths differ).
    """

    def process(self, params: ProcessingParams):
        # Capture user-desired output paths before base class overwrites them
        user_roughness = params.roughness_path
        user_weight_out = params.weight_output_path

        # Run the original workflow
        super().process(params)

        # After processing: params.roughness_path / weight_output_path now
        # point to the default locations inside the DTM folder.
        # Move (not copy) to user-specified locations when they differ,
        # so no duplicate files are left behind.
        if (user_roughness
                and params.roughness_path
                and Path(user_roughness) != Path(params.roughness_path)):
            shutil.move(str(params.roughness_path), str(user_roughness))
            params.roughness_path = Path(user_roughness)
            self.log(f"Roughness raster saved to: {user_roughness}")

        if (user_weight_out
                and params.weight_output_path
                and Path(user_weight_out) != Path(params.weight_output_path)):
            shutil.move(str(params.weight_output_path), str(user_weight_out))
            params.weight_output_path = Path(user_weight_out)
            self.log(f"Weight factor (W) raster saved to: {user_weight_out}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def run_cli(args):
    """Run in command line mode (extended with --save-roughness / --save-weight)"""
    print(f"CLI Mode: Initializing with DTM {args.dtm}")

    if args.params and os.path.exists(args.params):
        print(f"Loading parameters from {args.params}")
        params = ProcessingParams.load_from_file(Path(args.params))
        # CLI flags override JSON values when explicitly provided
        if args.save_roughness:
            params.roughness_path = Path(args.save_roughness)
        if args.save_weight:
            params.weight_output_path = Path(args.save_weight)
    else:
        cell_size = args.cell_size
        if cell_size <= 0:
            ds = gdal.Open(args.dtm)
            gt = ds.GetGeoTransform()
            cell_size = abs(gt[1])
            ds = None

        params = ProcessingParams(
            dtm_path=Path(args.dtm),
            cell_size=cell_size,
            output_path=Path(args.output),
            weight_path=Path(args.weight) if args.weight else None,
            target_path=Path(args.target) if args.target else None,
            sink_path=Path(args.sink) if args.sink else None,
            use_cavalli_weight=args.auto_weight,
            normalize_weight=args.normalize,
            save_components=args.save_components,
            window_size=args.window_size,
            roughness_path=Path(args.save_roughness) if args.save_roughness else None,
            weight_output_path=Path(args.save_weight) if args.save_weight else None,
        )

    processor = ConnectivityProcessor2(print)
    try:
        processor.process(params)
        print("Success: Analysis completed.")
        return 0
    except Exception as e:
        print(f"Error: {e}")
        return 1


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description='SedInConnect 3.0 (variant) - Sediment Connectivity Index'
    )
    parser.add_argument('--dtm', type=str, help='Path to filled DTM raster')
    parser.add_argument('--output', type=str, help='Path to output IC raster')
    parser.add_argument('--cell-size', type=float, default=0.0, help='Cell size in meters')
    parser.add_argument('--weight', type=str, help='Path to weight raster')
    parser.add_argument('--target', type=str, help='Path to target shapefile')
    parser.add_argument('--sink', type=str, help='Path to sink shapefile')
    parser.add_argument('--auto-weight', action='store_true',
                        help='Compute Cavalli weight automatically')
    parser.add_argument('--normalize', action='store_true', help='Normalize weight factor')
    parser.add_argument('--window-size', type=int, default=5,
                        help='Moving window size for roughness')
    parser.add_argument('--save-components', action='store_true',
                        help='Save D_up and D_down components')
    parser.add_argument('--params', type=str, help='Path to a JSON parameters file')
    parser.add_argument('--gui', action='store_true', default=None, help='Force GUI mode')
    # ── NEW ──────────────────────────────────────────────────────────────────
    parser.add_argument('--save-roughness', type=str, metavar='PATH',
                        help='Save roughness raster to PATH (*.tif). '
                             'Requires --auto-weight.')
    parser.add_argument('--save-weight', type=str, metavar='PATH',
                        help='Save weight-factor (W) raster to PATH (*.tif). '
                             'Requires --auto-weight.')
    # ─────────────────────────────────────────────────────────────────────────

    if len(sys.argv) == 1 or (len(sys.argv) == 2 and sys.argv[1] == '--gui'):
        start_gui = True
    else:
        parsed_args = parser.parse_args()
        if parsed_args.gui:
            start_gui = True
        elif parsed_args.params or (parsed_args.dtm and parsed_args.output):
            start_gui = False
        else:
            parser.print_help()
            sys.exit(1)

    gdal.AllRegister()
    gdal.UseExceptions()

    if start_gui:
        if getattr(sys, 'frozen', False):
            log_dir = os.path.join(
                os.environ.get('LOCALAPPDATA', os.path.expanduser('~')),
                'SedInConnect'
            )
            os.makedirs(log_dir, exist_ok=True)
            log_file = os.path.join(log_dir, "sedinconnect_debug.log")
        else:
            log_file = os.path.join(project_root, "sedinconnect_debug.log")
        try:
            logger = Logger(log_file)
            sys.stdout = logger
        except:
            pass

        from PyQt5 import QtWidgets, QtGui, QtCore
        from PyQt5.QtWidgets import (
            QLabel, QLineEdit, QPushButton, QFileDialog,
            QGroupBox, QGridLayout, QMessageBox
        )
        from PyQt5.QtCore import Qt
        from sedinconnect.gui.main_window import ModernConnectivityGUI, ProcessingThread

        # ------------------------------------------------------------------ #
        # Fix: propagate the GUI log signal to TauDEM runner + weight calc,  #
        # so their output appears in the black console pane.                  #
        # In the base ProcessingThread only processor.log is updated;         #
        # processor.taudem.log and processor.weight_calc.log still point to  #
        # print(), so TauDEM lines never reach the GUI.                       #
        # ------------------------------------------------------------------ #
        class ProcessingThread2(ProcessingThread):
            def __init__(self, params, processor):
                super().__init__(params, processor)
                # console_output signal is now wired; propagate to sub-components
                self.processor.taudem.log = self.console_output.emit
                self.processor.weight_calc.log = self.console_output.emit

        if sys.platform == 'win32':
            try:
                myappid = 'sedin.connect.3.0'
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
            except Exception:
                pass

        try:
            QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling, True)
            QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps, True)
        except Exception:
            pass

        # ------------------------------------------------------------------ #
        # Extended GUI: adds roughness + weight-output rows in the Output     #
        # group, enabled only when "Compute W automatically" is checked.      #
        # ------------------------------------------------------------------ #
        class ModernConnectivityGUI2(ModernConnectivityGUI):

            BROWSE_BTN_STYLE = """
                QPushButton {
                    padding: 8px 16px;
                    background-color: #2196F3;
                    color: white;
                    border: 2px solid #2196F3;
                    border-radius: 4px;
                    font-weight: bold;
                }
                QPushButton:hover { background-color: #1976D2; }
                QPushButton:disabled {
                    background-color: #cccccc;
                    color: #666;
                    border: 2px solid #999;
                }
            """

            def __init__(self):
                super().__init__()
                # Replace the base processor with the extended one
                self.processor = ConnectivityProcessor2()

            # ── Output group: add roughness + weight rows ─────────────────
            def create_output_group(self) -> QGroupBox:
                group = super().create_output_group()   # row 0: IC raster
                layout = group.layout()                 # QGridLayout

                # Row 1 – Roughness raster
                layout.addWidget(QLabel("Roughness raster:"), 1, 0)
                self.roughness_output_input = QLineEdit()
                self.roughness_output_input.setPlaceholderText(
                    "Save roughness raster (*.tif) — optional, requires auto-W"
                )
                self.roughness_output_input.setEnabled(False)
                layout.addWidget(self.roughness_output_input, 1, 1)
                self.roughness_output_button = QPushButton("Browse...")
                self.roughness_output_button.setEnabled(False)
                self.roughness_output_button.setStyleSheet(self.BROWSE_BTN_STYLE)
                self.roughness_output_button.clicked.connect(
                    lambda: self.browse_save_file(
                        self.roughness_output_input, "GeoTIFF (*.tif)"
                    )
                )
                layout.addWidget(self.roughness_output_button, 1, 2)

                # Row 2 – Weight factor (W) raster
                layout.addWidget(QLabel("Weight factor (W):"), 2, 0)
                self.weight_output_input = QLineEdit()
                self.weight_output_input.setPlaceholderText(
                    "Save W raster (*.tif) — optional, requires auto-W"
                )
                self.weight_output_input.setEnabled(False)
                layout.addWidget(self.weight_output_input, 2, 1)
                self.weight_output_button = QPushButton("Browse...")
                self.weight_output_button.setEnabled(False)
                self.weight_output_button.setStyleSheet(self.BROWSE_BTN_STYLE)
                self.weight_output_button.clicked.connect(
                    lambda: self.browse_save_file(
                        self.weight_output_input, "GeoTIFF (*.tif)"
                    )
                )
                layout.addWidget(self.weight_output_button, 2, 2)

                return group

            # ── Enable / disable new fields together with auto-weight ─────
            def toggle_auto_weight(self, state):
                super().toggle_auto_weight(state)
                enabled = (state == Qt.Checked)
                # The widgets may not exist yet when toggle fires during init
                if hasattr(self, 'roughness_output_input'):
                    self.roughness_output_input.setEnabled(enabled)
                    self.roughness_output_button.setEnabled(enabled)
                    self.weight_output_input.setEnabled(enabled)
                    self.weight_output_button.setEnabled(enabled)

            # ── validate_inputs: add new paths on top of parent result ────
            def validate_inputs(self):
                params = super().validate_inputs()
                if params is None:
                    return None
                roughness_path = (
                    Path(self.roughness_output_input.text())
                    if self.roughness_output_input.text() else None
                )
                weight_output_path = (
                    Path(self.weight_output_input.text())
                    if self.weight_output_input.text() else None
                )
                return dataclasses.replace(
                    params,
                    roughness_path=roughness_path,
                    weight_output_path=weight_output_path,
                )

            # ── run_analysis: use ProcessingThread2 for full console output ─
            def run_analysis(self):
                params = self.validate_inputs()
                if not params:
                    return
                self.run_button.setEnabled(False)
                self.progress_bar.setValue(0)
                self.console.clear()
                self.worker_thread = ProcessingThread2(params, self.processor)
                self.worker_thread.console_output.connect(self.append_console)
                self.worker_thread.finished.connect(self.processing_finished)
                self.worker_thread.start()

            # ── load_parameters: also restore new fields ──────────────────
            def load_parameters(self):
                filename, _ = QFileDialog.getOpenFileName(
                    self, "Load Parameters", "", "JSON Files (*.json)"
                )
                if not filename:
                    return
                try:
                    p = ProcessingParams.load_from_file(Path(filename))
                    self.dtm_input.setText(str(p.dtm_path))
                    self.cell_size_input.setText(str(p.cell_size))
                    self.output_input.setText(str(p.output_path))
                    self.auto_weight_cb.setChecked(p.use_cavalli_weight)
                    if p.weight_path:
                        self.weight_input.setText(str(p.weight_path))
                    if p.target_path:
                        self.use_targets_cb.setChecked(True)
                        self.target_input.setText(str(p.target_path))
                    if p.sink_path:
                        self.use_sinks_cb.setChecked(True)
                        self.sink_input.setText(str(p.sink_path))
                    self.save_components_cb.setChecked(p.save_components)
                    self.window_size_input.setText(str(p.window_size))
                    self.normalize_cb.setChecked(p.normalize_weight)
                    # New fields
                    if p.roughness_path:
                        self.roughness_output_input.setText(str(p.roughness_path))
                    if p.weight_output_path:
                        self.weight_output_input.setText(str(p.weight_output_path))
                    QMessageBox.information(self, "Success", "Parameters loaded!")
                except Exception as e:
                    QMessageBox.critical(self, "Error", str(e))

        # ------------------------------------------------------------------ #

        app = QtWidgets.QApplication(sys.argv)
        app.setStyle('Fusion')
        app.setFont(QtGui.QFont("Segoe UI", 10))

        window = ModernConnectivityGUI2()
        window.show()
        sys.exit(app.exec_())
    else:
        sys.exit(run_cli(parser.parse_args()))


if __name__ == "__main__":
    multiprocessing.freeze_support()
    if getattr(sys, 'frozen', False):
        os.chdir(os.path.dirname(sys.executable))
    main()
