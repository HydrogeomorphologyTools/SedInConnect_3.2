import os
import subprocess
import threading
import queue
from pathlib import Path

class TauDEMRunner:
    """Helper to run TauDEM commands"""
    
    def __init__(self, log_func=print):
        self.log = log_func
        # TauDEM installation path
        self.taudem_path = Path(r"C:\Program Files\TauDEM\TauDEM5Exe")
        # Microsoft MPI path
        self.mpiexec_path = Path(r"C:\Program Files\Microsoft MPI\Bin\mpiexec.exe")
        
        # PRIORITY 1: Standalone GDAL installations (what TauDEM prefers)
        self.standalone_gdal_paths = [
            r"C:\Program Files\GDAL",
            r"C:\GDAL\bin",
            r"C:\GDAL",
        ]

        # PRIORITY 2: QGIS GDAL (fallback)
        qgis_base_paths = [
            r"C:\Program Files\QGIS 3.34.11",
            r"C:\PROGRA~1\QGIS33~1.11",
            r"C:\Program Files\QGIS 3.38",
            r"C:\OSGeo4W64",
        ]

        self.qgis_paths = []
        for base_path in qgis_base_paths:
            if Path(base_path).exists():
                self.qgis_paths.extend([
                    os.path.join(base_path, "apps", "qgis-ltr", "bin"),
                    os.path.join(base_path, "bin"),
                    os.path.join(base_path, "apps", "Qt5", "bin"),
                    os.path.join(base_path, "apps", "qt5", "bin"),
                ])
                break

    def run(self, command: str, args: str):
        """Run TauDEM command with output capture"""
        # TauDEM command mapping
        command_map = {
            'D8Flowdir': 'D8FlowDir.exe',
            'DinfFlowdir': 'DinfFlowDir.exe',
            'AreaDinf': 'AreaDinf.exe'
        }

        # Get the correct executable name
        exe_name = command_map.get(command, f"{command}.exe")
        exe_path = self.taudem_path / exe_name

        if not exe_path.exists():
            raise RuntimeError(f"TauDEM executable not found: {exe_path}")

        if not self.mpiexec_path.exists():
            raise RuntimeError(f"mpiexec not found: {self.mpiexec_path}")

        # Prepare environment
        env = os.environ.copy()
        existing_path = env.get('PATH', '')

        # Build new PATH: Standalone GDAL first, then TauDEM exe, then QGIS (fallback)
        new_paths = []
        for gdal_path in self.standalone_gdal_paths:
            if Path(gdal_path).exists():
                new_paths.append(gdal_path)

        new_paths.append(str(self.taudem_path))

        for qgis_path in self.qgis_paths:
            if Path(qgis_path).exists():
                new_paths.append(qgis_path)

        if new_paths:
            env['PATH'] = ';'.join(new_paths) + ';' + existing_path
            # self.log(f"PATH priority order: {' -> '.join(new_paths[:3])}...")

        # Build command
        cmd = f'"{self.mpiexec_path}" -n 1 "{exe_path}" {args}'
        self.log(f"Running: {cmd}")

        process = subprocess.Popen(
            cmd,
            shell=True,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
            bufsize=1
        )

        def enqueue_output(stream, queue, stream_name):
            try:
                for line in iter(stream.readline, ''):
                    if line:
                        queue.put((stream_name, line))
                stream.close()
            except Exception:
                pass

        output_queue = queue.Queue()
        stdout_thread = threading.Thread(target=enqueue_output, args=(process.stdout, output_queue, 'stdout'), daemon=True)
        stderr_thread = threading.Thread(target=enqueue_output, args=(process.stderr, output_queue, 'stderr'), daemon=True)
        stdout_thread.start()
        stderr_thread.start()

        while process.poll() is None or not output_queue.empty():
            try:
                stream_name, line = output_queue.get(timeout=0.1)
                line = line.rstrip()
                if line:
                    if stream_name == 'stdout':
                        self.log(f"  {line}")
                    else:
                        self.log(f"  [stderr] {line}")
            except queue.Empty:
                continue

        if process.returncode != 0:
            raise RuntimeError(f"TauDEM {command} failed with exit code {process.returncode}")
