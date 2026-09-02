import sys
import os
import ctypes
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
        except: pass
        
        if self.log:
            try:
                self.log.write(message)
            except:
                pass

    def flush(self):
        try:
            self.terminal.flush()
        except: pass
        
        if self.log:
            try:
                self.log.flush()
            except:
                pass

def run_cli(args):
    """Run in command line mode"""
    print(f"CLI Mode: Initializing with DTM {args.dtm}")
    
    if args.params and os.path.exists(args.params):
        print(f"Loading parameters from {args.params}")
        params = ProcessingParams.load_from_file(Path(args.params))
    else:
        # Get cell size automatically if not provided
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
            window_size=args.window_size
        )

    processor = ConnectivityProcessor(print)
    try:
        processor.process(params)
        print("Success: Analysis completed.")
        return 0
    except Exception as e:
        print(f"Error: {e}")
        return 1

def main():
    parser = argparse.ArgumentParser(description='SedInConnect 3.0 - Sediment Connectivity Index')
    parser.add_argument('--dtm', type=str, help='Path to filled DTM raster')
    parser.add_argument('--output', type=str, help='Path to output IC raster')
    parser.add_argument('--cell-size', type=float, default=0.0, help='Cell size in meters')
    parser.add_argument('--weight', type=str, help='Path to weight raster')
    parser.add_argument('--target', type=str, help='Path to target shapefile')
    parser.add_argument('--sink', type=str, help='Path to sink shapefile')
    parser.add_argument('--auto-weight', action='store_true', help='Compute Cavalli weight automatically')
    parser.add_argument('--normalize', action='store_true', help='Normalize weight factor')
    parser.add_argument('--window-size', type=int, default=5, help='Moving window size for roughness')
    parser.add_argument('--save-components', action='store_true', help='Save D_up and D_down components')
    parser.add_argument('--params', type=str, help='Path to a JSON parameters file')
    parser.add_argument('--gui', action='store_true', default=None, help='Force GUI mode')
    
    # If no arguments (or only --gui), start GUI
    if len(sys.argv) == 1 or (len(sys.argv) == 2 and sys.argv[1] == '--gui'):
        start_gui = True
    else:
        # Check if we have the minimum required for CLI
        parsed_args = parser.parse_args()
        if parsed_args.gui:
            start_gui = True
        elif parsed_args.params or (parsed_args.dtm and parsed_args.output):
            start_gui = False
        else:
            parser.print_help()
            sys.exit(1)

    # Global GDAL setup
    gdal.AllRegister()
    gdal.UseExceptions()

    if start_gui:
        # Setup dual logging in a user-writable directory
        if getattr(sys, 'frozen', False):
            log_dir = os.path.join(os.environ.get('LOCALAPPDATA', os.path.expanduser('~')), 'SedInConnect')
            os.makedirs(log_dir, exist_ok=True)
            log_file = os.path.join(log_dir, "sedinconnect_debug.log")
        else:
            log_file = os.path.join(project_root, "sedinconnect_debug.log")
            
        try:
            logger = Logger(log_file)
            sys.stdout = logger
            # sys.stderr = logger
        except: pass

        from PyQt5 import QtWidgets, QtGui, QtCore
        from sedinconnect.gui.main_window import ModernConnectivityGUI
        
        if sys.platform == 'win32':
            try:
                myappid = 'sedin.connect.3.0'
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
            except Exception: pass

        try:
            QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling, True)
            QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps, True)
        except Exception: pass

        app = QtWidgets.QApplication(sys.argv)
        app.setStyle('Fusion')
        app.setFont(QtGui.QFont("Segoe UI", 10))

        window = ModernConnectivityGUI()
        window.show()
        sys.exit(app.exec_())
    else:
        sys.exit(run_cli(parser.parse_args()))

if __name__ == "__main__":
    multiprocessing.freeze_support()
    if getattr(sys, 'frozen', False):
        os.chdir(os.path.dirname(sys.executable))
    main()
