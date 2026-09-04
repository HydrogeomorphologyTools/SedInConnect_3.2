# -*- coding: utf-8 -*-
"""
Build standalone macOS SedInConnect.app and SedInConnect.dmg
Contains all dependencies: GDAL, Numba, NumPy, SciPy, Matplotlib, PyQt5.
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

repo_root = Path(__file__).resolve().parent
os.chdir(repo_root)

print("=== Building SedInConnect for macOS ===")

# Locate icon
icon_path = repo_root / "sedinconnect" / "assets" / "logo2.ico"
if not icon_path.exists():
    icon_path = repo_root / "python_package" / "sedinconnect" / "assets" / "logo2.ico"

# Build PyInstaller command
cmd = [
    sys.executable, "-m", "PyInstaller",
    "--noconfirm",
    "--windowed",
    "--name", "SedInConnect",
    "--add-data", f"{repo_root / 'sedinconnect' / 'assets'}:sedinconnect/assets",
    "--hidden-import", "osgeo",
    "--hidden-import", "osgeo.gdal",
    "--hidden-import", "osgeo.gdal_array",
    "--hidden-import", "osgeo.osr",
    "--hidden-import", "osgeo.ogr",
    "--hidden-import", "numba",
    "--hidden-import", "scipy",
    "--hidden-import", "scipy.ndimage",
    "--hidden-import", "matplotlib",
    "--hidden-import", "PyQt5",
    "--collect-all", "osgeo",
    "--collect-all", "numba",
    "--collect-all", "sedinconnect",
    str(repo_root / "sedinconnect" / "main.py")
]

if icon_path.exists():
    cmd.extend(["--icon", str(icon_path)])

print("Running PyInstaller:", " ".join(cmd))
subprocess.check_call(cmd)

app_path = repo_root / "dist" / "SedInConnect.app"
dmg_out = repo_root / "dist" / "SedInConnect_3.2_macOS.dmg"

if not app_path.exists():
    print("Error: SedInConnect.app was not created!")
    sys.exit(1)

print(f"Successfully created: {app_path}")

# Create DMG if on macOS
if sys.platform == "darwin":
    print("Creating macOS DMG installer image...")
    # Try using create-dmg if installed, otherwise hdiutil
    if shutil.which("create-dmg"):
        subprocess.run([
            "create-dmg",
            "--volname", "SedInConnect 3.2",
            "--window-pos", "200", "120",
            "--window-size", "600", "400",
            "--icon-size", "100",
            "--icon", "SedInConnect.app", "150", "190",
            "--hide-extension", "SedInConnect.app",
            "--app-drop-link", "450", "185",
            str(dmg_out),
            str(app_path)
        ])
    else:
        subprocess.run([
            "hdiutil", "create",
            "-volname", "SedInConnect 3.2",
            "-srcfolder", str(app_path),
            "-ov", "-format", "UDZO",
            str(dmg_out)
        ])

    if dmg_out.exists():
        print(f"🎉 Successfully created macOS installer: {dmg_out}")
