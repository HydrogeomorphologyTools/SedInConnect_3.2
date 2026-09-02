"""
generate_taudem_ground_truth.py
Run TauDEM CLI on dtmfel.tif to generate exact ground-truth reference rasters.
"""
import subprocess
import os
from pathlib import Path
from osgeo import gdal

BASE = Path(r"D:\Research\SedInConnect_python")
OUT_DIR = BASE / "taudem_ref"
OUT_DIR.mkdir(exist_ok=True)

dtm = BASE / "dtmfel.tif"
p_ref = OUT_DIR / "dtm_p.tif"
sd8_ref = OUT_DIR / "dtm_sd8.tif"
ang_ref = OUT_DIR / "dtm_ang.tif"
slp_ref = OUT_DIR / "dtm_slp.tif"
sca_ref = OUT_DIR / "dtm_sca.tif"

print("1. Running TauDEM D8FlowDir...")
cmd_d8 = f'mpiexec -n 4 "C:\\Program Files\\TauDEM\\TauDEM5Exe\\D8FlowDir.exe" -fel "{dtm}" -p "{p_ref}" -sd8 "{sd8_ref}"'
subprocess.run(cmd_d8, shell=True, check=True)

print("2. Running TauDEM DinfFlowDir...")
cmd_dinf = f'mpiexec -n 4 "C:\\Program Files\\TauDEM\\TauDEM5Exe\\DinfFlowDir.exe" -fel "{dtm}" -ang "{ang_ref}" -slp "{slp_ref}"'
subprocess.run(cmd_dinf, shell=True, check=True)

print("3. Running TauDEM AreaDinf (unweighted SCA)...")
cmd_sca = f'mpiexec -n 4 "C:\\Program Files\\TauDEM\\TauDEM5Exe\\AreaDinf.exe" -ang "{ang_ref}" -sca "{sca_ref}" -nc'
subprocess.run(cmd_sca, shell=True, check=True)

print("TauDEM ground truth generated successfully in:", OUT_DIR)
