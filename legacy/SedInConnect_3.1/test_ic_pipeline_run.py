
import numpy as np, sys
sys.path.insert(0, r'D:\Research\SedInConnect_python\SedInConnect_3.1')
from sedinconnect.core.processor import SedInConnectProcessor
from pathlib import Path

p = SedInConnectProcessor(log_func=print)
p.compute_connectivity_targets(
    dtm_path=Path(r'D:\Research\SedInConnect_python\dtmfel.tif'),
    cell_size=30.0,
    target_path=Path(r'D:\Research\SedInConnect_python\target.shp'),
    weight_path=Path(r'D:\Research\SedInConnect_python\w.tif'),
    output_path=Path(r'D:\Research\SedInConnect_python\ic_test_31_vfix.tif'),
    save_components=False,
    sink_flag=0,
)
print("Done")
