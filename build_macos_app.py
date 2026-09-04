# -*- coding: utf-8 -*-
"""
Build standalone macOS SedInConnect.app and SedInConnect.dmg
Using pre-compiled Conda/Micromamba binaries (GDAL, PROJ, Numba, NumPy, SciPy, Matplotlib, PyQt5).
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

repo_root = Path(__file__).resolve().parent
os.chdir(repo_root)

print("=== Building SedInConnect for macOS ===")

# Detect entry point and assets
main_script = repo_root / "python_package" / "sedinconnect" / "main.py"
if not main_script.exists():
    main_script = repo_root / "sedinconnect" / "main.py"

assets_dir = repo_root / "python_package" / "sedinconnect" / "assets"
if not assets_dir.exists():
    assets_dir = repo_root / "sedinconnect" / "assets"

icon_path = assets_dir / "logo2.ico"

print(f"Main script path: {main_script}")
print(f"Assets directory: {assets_dir}")

if not main_script.exists():
    print(f"Error: {main_script} does not exist!")
    sys.exit(1)

# Detect GDAL and PROJ data directories (Conda prefix or system)
conda_prefix = os.environ.get("CONDA_PREFIX", "")
gdal_data_dir = ""
proj_lib_dir = ""

if conda_prefix:
    p_gdal = Path(conda_prefix) / "share" / "gdal"
    p_proj = Path(conda_prefix) / "share" / "proj"
    if p_gdal.exists():
        gdal_data_dir = str(p_gdal)
        print(f"Found Conda GDAL Data: {gdal_data_dir}")
    if p_proj.exists():
        proj_lib_dir = str(p_proj)
        print(f"Found Conda PROJ Data: {proj_lib_dir}")

if not gdal_data_dir:
    try:
        gdal_data_dir = subprocess.check_output(["gdal-config", "--datadir"]).decode().strip()
    except Exception:
        pass

if not proj_lib_dir:
    try:
        brew_prefix = subprocess.check_output(["brew", "--prefix"]).decode().strip()
        candidate = Path(brew_prefix) / "share" / "proj"
        if candidate.exists():
            proj_lib_dir = str(candidate)
    except Exception:
        pass

# Runtime hook for embedded paths
hook_code = """
import os
import sys
from pathlib import Path

if getattr(sys, 'frozen', False):
    bundle_dir = Path(sys._MEIPASS)
    gdal_d = bundle_dir / 'gdal_data'
    proj_d = bundle_dir / 'proj_data'
    if gdal_d.exists():
        os.environ['GDAL_DATA'] = str(gdal_d)
    if proj_d.exists():
        os.environ['PROJ_LIB'] = str(proj_d)
        os.environ['PROJ_DATA'] = str(proj_d)
"""
hook_file = repo_root / "runtime_hook_gdal.py"
hook_file.write_text(hook_code, encoding="utf-8")

# Build PyInstaller command (Options first, script path last)
cmd = [
    sys.executable, "-m", "PyInstaller",
    "--noconfirm",
    "--windowed",
    "--name", "SedInConnect",
    "--runtime-hook", str(hook_file),
    "--add-data", f"{assets_dir}:sedinconnect/assets",
    "--hidden-import", "osgeo",
    "--hidden-import", "osgeo.gdal",
    "--hidden-import", "osgeo.gdal_array",
    "--hidden-import", "osgeo.osr",
    "--hidden-import", "osgeo.ogr",
    "--hidden-import", "numba",
    "--hidden-import", "scipy",
    "--hidden-import", "scipy.ndimage",
    "--hidden-import", "matplotlib",
    "--hidden-import", "matplotlib.backends.backend_qtagg",
    "--hidden-import", "matplotlib.backends.backend_qt5agg",
    "--hidden-import", "PyQt5",
    "--collect-all", "osgeo",
    "--collect-all", "numba",
    "--collect-all", "sedinconnect",
]

if gdal_data_dir and Path(gdal_data_dir).exists():
    cmd.extend(["--add-data", f"{gdal_data_dir}:gdal_data"])

if proj_lib_dir and Path(proj_lib_dir).exists():
    cmd.extend(["--add-data", f"{proj_lib_dir}:proj_data"])

if icon_path.exists():
    cmd.extend(["--icon", str(icon_path)])

# Script path must be the last argument
cmd.append(str(main_script))

print("Running PyInstaller...")
subprocess.check_call(cmd)

app_path = repo_root / "dist" / "SedInConnect.app"
dmg_out = repo_root / "dist" / "SedInConnect_3.2_macOS.dmg"

if not app_path.exists():
    print("Error: SedInConnect.app was not created!")
    sys.exit(1)

print(f"Successfully created: {app_path}")

# Create DMG with Applications symlink
if sys.platform == "darwin":
    print("Creating macOS DMG installer image...")
    dmg_temp_dir = repo_root / "dist" / "dmg_root"
    if dmg_temp_dir.exists():
        shutil.rmtree(dmg_temp_dir)
    dmg_temp_dir.mkdir(parents=True, exist_ok=True)

    shutil.copytree(app_path, dmg_temp_dir / "SedInConnect.app")

    try:
        os.symlink("/Applications", str(dmg_temp_dir / "Applications"))
    except Exception as e:
        print(f"Symlink warning: {e}")

    subprocess.run([
        "hdiutil", "create",
        "-volname", "SedInConnect 3.2",
        "-srcfolder", str(dmg_temp_dir),
        "-ov", "-format", "UDZO",
        str(dmg_out)
    ], check=True)

    if dmg_out.exists():
        print(f"🎉 Successfully created macOS installer: {dmg_out}")
