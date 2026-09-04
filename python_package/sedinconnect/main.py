import sys
import os

# Configure Numba for standalone frozen execution
os.environ['NUMBA_THREADING_LAYER'] = 'workqueue'
os.environ['NUMBA_DISABLE_INTEL_SVML'] = '1'
os.environ['NUMBA_CACHE_DIR'] = os.path.join(os.environ.get('LOCALAPPDATA', os.path.expanduser('~')), 'numba_cache')
os.environ['PROJ_NETWORK'] = 'OFF'

if getattr(sys, 'frozen', False):
    bundle_dir = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
    # Register all DLL directories for Windows Python 3.8+
    for subdir in ['', 'osgeo', 'numpy.libs', 'scipy.libs', 'PyQt5\\Qt5\\bin', 'llvmlite\\binding', 'numba']:
        d = os.path.join(bundle_dir, subdir)
        if os.path.isdir(d):
            try:
                os.add_dll_directory(d)
            except Exception:
                pass

    gdal_data = os.path.join(bundle_dir, 'osgeo', 'data', 'gdal')
    proj_data = os.path.join(bundle_dir, 'osgeo', 'data', 'proj')
    if os.path.exists(gdal_data):
        os.environ['GDAL_DATA'] = gdal_data
    if os.path.exists(proj_data):
        os.environ['PROJ_LIB'] = proj_data
        os.environ['PROJ_DATA'] = proj_data

import ctypes
import multiprocessing
import argparse
from pathlib import Path

from osgeo import gdal, ogr, osr, gdal_array

gdal.UseExceptions()
gdal.SetConfigOption('PROJ_NETWORK', 'OFF')
if getattr(sys, 'frozen', False):
    bundle_dir = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
    gdal_data = os.path.join(bundle_dir, 'osgeo', 'data', 'gdal')
    proj_data = os.path.join(bundle_dir, 'osgeo', 'data', 'proj')
    if os.path.exists(gdal_data):
        gdal.SetConfigOption('GDAL_DATA', gdal_data)
    if os.path.exists(proj_data):
        gdal.SetConfigOption('PROJ_LIB', proj_data)
        gdal.SetConfigOption('PROJ_DATA', proj_data)
gdal.AllRegister()

# Add project root to sys.path
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# If launched without console arguments in GUI mode, hide console window on Windows
if sys.platform == 'win32':
    if getattr(sys, 'frozen', False) and len(sys.argv) <= 1:
        try:
            hwnd = ctypes.windll.kernel32.GetConsoleWindow()
            if hwnd:
                ctypes.windll.user32.ShowWindow(hwnd, 0)
        except Exception:
            pass

from sedinconnect.utils.params import ProcessingParams
from sedinconnect.core.processor import ConnectivityProcessor

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
        except Exception:
            pass
        if self.log:
            try:
                self.log.write(message)
            except Exception:
                pass

    def flush(self):
        try:
            self.terminal.flush()
        except Exception:
            pass
        if self.log:
            try:
                self.log.flush()
            except Exception:
                pass

from sedinconnect.utils.telemetry import track_app_launch

def run_cli(args):
    """Run in command line mode"""
    try:
        track_app_launch("CLI")
    except Exception:
        pass
    print(f"SedInConnect 3.2 CLI: DTM = {args.dtm}")
    
    if args.params and os.path.exists(args.params):
        print(f"Loading parameters from {args.params}")
        params = ProcessingParams.load_from_file(Path(args.params))
        if args.fill_dtm:
            params.fill_dtm = True
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
            use_cavalli_weight=args.auto_weight or (args.weight is None),
            normalize_weight=args.normalize,
            save_components=args.save_components,
            window_size=args.window_size,
            roughness_path=Path(args.save_roughness) if args.save_roughness else None,
            weight_output_path=Path(args.save_weight) if args.save_weight else None,
            d_up_path=Path(args.d_up) if args.d_up else None,
            d_down_path=Path(args.d_down) if args.d_down else None,
            fill_dtm=args.fill_dtm,
            n_workers=args.workers if hasattr(args, 'workers') else None,
            chunk_size=args.chunk_size if hasattr(args, 'chunk_size') and args.chunk_size else 1024,
            save_run_log=not args.no_run_log if hasattr(args, 'no_run_log') else True
        )

    def cli_logger(msg):
        print(msg)

    processor = ConnectivityProcessor(cli_logger)
    try:
        cli_logger("Starting processor.process...")
        processor.process(params)
        cli_logger("Success: Analysis completed.")
        return 0
    except Exception as e:
        import traceback
        cli_logger(f"Error: {e}\n{traceback.format_exc()}")
        return 1

def main():
    parser = argparse.ArgumentParser(
        description='SedInConnect 3.2 - Sediment Connectivity Index (native Python, no TauDEM)'
    )
    parser.add_argument('--dtm', type=str, help='Path to DTM raster')
    parser.add_argument('--output', type=str, help='Path to output IC raster')
    parser.add_argument('--cell-size', type=float, default=0.0, help='Cell size in metres')
    parser.add_argument('--weight', type=str, help='Path to weight raster')
    parser.add_argument('--target', type=str, help='Path to target shapefile')
    parser.add_argument('--sink', type=str, help='Path to sink shapefile')
    parser.add_argument('--auto-weight', action='store_true', help='Compute Cavalli weight automatically')
    parser.add_argument('--normalize', action='store_true', help='Normalize weight factor')
    parser.add_argument('--window-size', type=int, default=5, help='Moving window size for roughness')
    parser.add_argument('--workers', type=int, default=None, help='Number of parallel CPU worker processes')
    parser.add_argument('--chunk-size', type=int, default=1024, help='Block size in pixels for Roughness/Weight calculation')
    parser.add_argument('--save-components', action='store_true', help='Save D_up and D_down components')
    parser.add_argument('--d-up', type=str, metavar='PATH', help='Custom path for D_up raster (*.tif)')
    parser.add_argument('--d-down', type=str, metavar='PATH', help='Custom path for D_down raster (*.tif)')
    parser.add_argument('--save-roughness', type=str, metavar='PATH',
                        help='Save roughness raster to PATH (*.tif). Requires --auto-weight.')
    parser.add_argument('--save-weight', type=str, metavar='PATH',
                        help='Save weight-factor (W) raster to PATH (*.tif). Requires --auto-weight.')
    parser.add_argument('--params', type=str, help='Path to a JSON parameters file')
    parser.add_argument('--no-run-log', action='store_true',
                        help='Disable appending execution record to sedinconnect_runs.log')
    parser.add_argument('--gui', action='store_true', default=None, help='Force GUI mode')
    parser.add_argument('--fill-dtm', action='store_true',
                        help='Fill DTM depressions (Priority-Flood algorithm) before computing flow directions.')

    # If no arguments (or only --gui), start GUI
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
        except Exception:
            pass

        from PyQt5 import QtWidgets, QtGui, QtCore
        from sedinconnect.gui.main_window import ModernConnectivityGUI

        try:
            track_app_launch("GUI")
        except Exception:
            pass

        if sys.platform == 'win32':
            try:
                myappid = 'sedin.connect.3.2'
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
            except Exception:
                pass

        try:
            QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling, True)
            QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps, True)
        except Exception:
            pass

        app = QtWidgets.QApplication(sys.argv)
        app.setStyle('Fusion')
        app.setFont(QtGui.QFont("Segoe UI", 10))

        window = ModernConnectivityGUI()
        window.show()
        return app.exec_()
    else:
        return run_cli(parser.parse_args())

if __name__ == "__main__":
    multiprocessing.freeze_support()
    try:
        ret = main()
    except SystemExit as e:
        ret = e.code if isinstance(e.code, int) else 0
    except Exception as e:
        import traceback
        traceback.print_exc()
        ret = 1
    sys.stdout.flush()
    sys.stderr.flush()
    sys.exit(ret if isinstance(ret, int) else 0)

