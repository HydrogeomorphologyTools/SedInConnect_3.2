# SedInConnect — Python Package & Programmatic API (v3.2.0)

Official Python distribution of **SedInConnect**, providing high-performance, stand-alone, and scriptable Sediment Connectivity Index (IC) calculations for spatial data science workflows.

Developed at **CNR-IRPI Padova (Italy)** within the **MORPHEUS PRIN 2023-2026 Project**.

---

## 📦 Installation

### From PyPI (Standard):
```bash
pip install sedinconnect
```

### Directly from GitHub:
```bash
pip install git+https://github.com/HydrogeomorphologyTools/SedInConnect_3.2.git#subdirectory=python_package
```

### Local Development Mode:
```bash
git clone https://github.com/HydrogeomorphologyTools/SedInConnect_3.2.git
cd SedInConnect_3.2/python_package
pip install -e .
```

---

## 🐍 Python API Usage

### 1. One-Liner High-Level API (`compute_ic`)

```python
import sedinconnect as sic

# Calculate Index of Connectivity in a single line
output_ic = sic.compute_ic(
    dtm="data/dtmfel.tif",
    output="results/ic_target.tif",
    target="data/target.shp",         # Optional target shapefile
    sink="data/sinks.shp",            # Optional sinks shapefile
    auto_weight=True,                 # Automatic Cavalli (2013) roughness weighting
    window_size=3,                    # Moving window size (3, 5, 7, ...)
    fill_dtm=False,                   # Priority-Flood pit filling
    save_components=False,            # Save D_up and D_down rasters
    save_run_log=True                 # Write structured execution log
)

print(f"Calculated IC saved to: {output_ic}")
```

### 2. Object-Oriented Processor API (`ConnectivityProcessor`)

```python
from pathlib import Path
from sedinconnect.core.processor import ConnectivityProcessor
from sedinconnect.utils.params import ProcessingParams

# Custom logger callback
def my_logger(msg):
    print(f"[SedInConnect Log] {msg}")

params = ProcessingParams(
    dtm_path=Path("data/dtmfel.tif"),
    cell_size=2.5,
    output_path=Path("results/ic_custom.tif"),
    target_path=Path("data/target.shp"),
    use_cavalli_weight=True,
    window_size=5,
    normalize_weight=True,
    n_workers=8,
    chunk_size=1024
)

processor = ConnectivityProcessor(log_func=my_logger)
processor.process(params)
```

---

## 🖥️ Command Line Interface (CLI)

When installed via pip, the global command `sedinconnect` is automatically registered:

```bash
# Launch GUI
sedinconnect

# Headless CLI Execution
sedinconnect --dtm "dtm.tif" --cell-size 2.5 --output "ic.tif" --target "streams.shp" --auto-weight --window-size 3

# Display full help
sedinconnect --help
```

---

## 📚 Scientific References
* **Cavalli et al. (2013)**, *Geomorphology*, 188, 31-41. [doi:10.1016/j.geomorph.2012.05.007](https://doi.org/10.1016/j.geomorph.2012.05.007)
* **Borselli et al. (2008)**, *Catena*, 75(3), 268-277. [doi:10.1016/j.catena.2008.07.006](https://doi.org/10.1016/j.catena.2008.07.006)
* **Crema & Cavalli (2018)**, *Computers & Geosciences*, 111, 39-45. [doi:10.1016/j.cageo.2017.10.009](https://doi.org/10.1016/j.cageo.2017.10.009)
