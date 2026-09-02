import os
import sys
import subprocess
from pathlib import Path

def build():
    base_dir = Path(r"D:\Research\SedInConnect_python\SedInConnect_3.2")
    dist_dir = Path(r"D:\Research\SedInConnect_python\dist_3.2")
    build_dir = Path(r"D:\Research\SedInConnect_python\build_3.2")
    
    dist_dir.mkdir(parents=True, exist_ok=True)
    build_dir.mkdir(parents=True, exist_ok=True)

    spec_content = f"""# -*- mode: python ; coding: utf-8 -*-
import sys
from pathlib import Path

block_cipher = None

base_dir = Path(r"{base_dir}")

excludes = [
    "torch", "torchvision", "tensorflow", "cv2", "botocore", "boto3",
    "IPython", "jupyter", "tornado", "sphinx", "pytest",
    "pygame", "kornia", "cupy", "dash", "flask", "selenium", "open3d",
    "sklearn", "scikit-learn", "skimage", "scikit-image", "seaborn",
    "pandas", "pyarrow", "lxml", "openpyxl", "sqlalchemy", "sqlite3",
    "numba.cuda", "numba.cuda.*",
    "PyQt5.QtQuick", "PyQt5.QtQml", "PyQt5.QtNetwork", "PyQt5.QtWebEngine",
    "PyQt5.Qt3D", "PyQt5.QtBluetooth", "PyQt5.QtNfc", "PyQt5.QtPositioning",
    "PyQt5.QtSensors", "PyQt5.QtSerialPort", "PyQt5.QtSql", "PyQt5.QtTest",
    "PyQt5.QtXmlPatterns"
]

datas = [
    (str(base_dir / 'borselli_ic_EMS.png'), '.'),
    (str(base_dir / 'image.jpg'), '.'),
    (str(base_dir / 'logo.png'), '.'),
    (str(base_dir / 'logo2.ico'), '.'),
    (str(base_dir / 'logo2.png'), '.'),
    (str(base_dir / 'arrow_up.png'), '.'),
    (str(base_dir / 'arrow_down.png'), '.'),
    (str(base_dir / 'arrow_combo.png'), '.')
]

from PyInstaller.utils.hooks import collect_all, collect_submodules, collect_data_files

gdal_datas, gdal_binaries, gdal_hiddenimports = collect_all('osgeo')
numba_datas, numba_binaries, numba_hiddenimports = collect_all('numba')
llvmlite_datas, llvmlite_binaries, llvmlite_hiddenimports = collect_all('llvmlite')

numba_binaries = [b for b in numba_binaries if 'cuda' not in b[0].lower()]
numba_datas = [d for d in numba_datas if 'cuda' not in d[0].lower()]
numba_hiddenimports = [h for h in numba_hiddenimports if 'cuda' not in h.lower()]

datas += gdal_datas + numba_datas + llvmlite_datas

hiddenimports = [
    'PyQt5', 'PyQt5.QtCore', 'PyQt5.QtGui', 'PyQt5.QtWidgets',
    'osgeo._gdal', 'osgeo._gdal_array', 'osgeo.gdal', 'osgeo.ogr', 'osgeo.osr', 'osgeo.gdal_array',
    'matplotlib', 'matplotlib.pyplot', 'matplotlib.backends.backend_qt5agg',
    'PIL', 'PIL.Image',
    'scipy.signal', 'scipy.ndimage', 'scipy.spatial',
    'sedinconnect', 'sedinconnect.core.processor',
    'sedinconnect.core.hydrology', 'sedinconnect.core.weight',
    'sedinconnect.utils.raster', 'sedinconnect.utils.params',
    'sedinconnect.gui.main_window', 'sedinconnect.gui.dialogs',
    'numba', 'llvmlite'
] + gdal_hiddenimports + numba_hiddenimports + llvmlite_hiddenimports

a = Analysis(
    [str(base_dir / 'main.py')],
    pathex=[str(base_dir)],
    binaries=gdal_binaries + numba_binaries + llvmlite_binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={{}},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False
)

# Strip out broken / missing DLLs, external CUDA / Torch, and outdated PyQt5 VC runtime DLLs
filtered_binaries = []
bad_keywords = ['cuda', 'cudnn', 'cublas', 'cusparse', 'cufft', 'curand', 'nvrtc', 'torch', 'cutensor', 'nccl', 'nvjpeg', 'c10', 'tbbpool']
for name, path, typecode in a.binaries:
    name_l = name.lower()
    path_l = path.lower()
    if any(kw in name_l or kw in path_l for kw in bad_keywords):
        continue
    # Exclude outdated MSVC runtimes bundled inside PyQt5/Qt5/bin
    if 'pyqt5' in path_l and ('msvcp140' in name_l or 'vcruntime140' in name_l or 'vccorlib' in name_l):
        continue
    filtered_binaries.append((name, path, typecode))

# Bundle modern Visual C++ runtimes from System32 to avoid MSVCP ABI mismatch
sys32 = Path(r"C:\Windows\System32")
vc_dlls = ['msvcp140.dll', 'msvcp140_1.dll', 'msvcp140_2.dll', 'msvcp140_atomic_wait.dll', 'msvcp140_codecvt_ids.dll', 'vcruntime140.dll', 'vcruntime140_1.dll']
for dll_name in vc_dlls:
    p = sys32 / dll_name
    if p.exists():
        filtered_binaries.append((dll_name, str(p), 'BINARY'))

# Also ensure osgeo DLLs are present in the root directory for direct linkage
for src, dst in gdal_binaries:
    filtered_binaries.append((Path(src).name, src, 'BINARY'))

a.binaries = filtered_binaries

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='SedInConnect_3.2',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(base_dir / 'logo2.ico')
)
"""

    spec_path = build_dir / "SedInConnect_3.2_clean.spec"
    with open(spec_path, "w", encoding="utf-8") as f:
        f.write(spec_content)

    py_exe = r"C:\Users\STEFANOCREMA\AppData\Local\Programs\Python\Python312\python.exe"
    cmd = [
        py_exe, "-m", "PyInstaller",
        f"--distpath={dist_dir}",
        f"--workpath={build_dir}",
        "--clean",
        "--noconfirm",
        str(spec_path)
    ]

    print("Building clean, lightweight standalone executable...")
    res = subprocess.run(cmd, cwd=str(base_dir))
    if res.returncode == 0:
        exe_path = dist_dir / "SedInConnect_3.2.exe"
        size_mb = exe_path.stat().st_size / (1024*1024)
        print(f"SUCCESS! Output executable: {exe_path}")
        print(f"Final file size: {size_mb:.1f} MB")
    else:
        print(f"PyInstaller failed with code {res.returncode}")

if __name__ == "__main__":
    build()

