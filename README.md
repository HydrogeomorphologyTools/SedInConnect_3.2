# SedInConnect 3.2

**Stand-alone Tool for the Assessment of Sediment Connectivity**

Developed by **Stefano Crema** and **Marco Cavalli**  
*CNR-IRPI (National Research Council - Research Institute for Geo-Hydrological Protection), Padova, Italy*  
*Framework:* **MORPHEUS Project** (*GeoMORPHomEtry throUgh Scales for a resilient landscape*)  
*License:* GNU General Public License v2 (GPLv2)

---

## 🚀 Overview

**SedInConnect 3.2** is a stand-alone, open-source software for computing the **Index of Connectivity (IC)** (Cavalli et al., 2013; Borselli et al., 2008). It evaluates the potential sediment transfer pathways and the degree of linkage between sediment sources (hillslopes) and downstream targets (river networks, detention basins, roads, or catchment outlets).

Version **3.2** represents a milestone release featuring a **100% native Python/Numba computational core**, eliminating any external dependencies on TauDEM or MS-MPI while maintaining **exact numerical consistency** with reference hydrogeomorphometric models.

---

## ✨ What's New in Version 3.2

* **⚡ 100% Native High-Performance Core:** Complete Python/Numba vectorized algorithms for D8 and D-infinity flow routing (\infty$, Tarboton, 1997), flat area resolution (Garbrecht & Martz, 1997), and weighted downslope distance transforms ({down}$).
* **🔄 Chunk-Invariant Processing:** Tile-based spatial chunking (1024, 2048, 4096 px) enables processing of massive LiDAR grids (100M+ cells) on standard workstations with strict **bitwise mathematical invariance** across chunk sizes.
* **💻 Multi-Core Parallel Acceleration:** Configurable CPU worker processes (--workers) for high-throughput spatial convolution and surface roughness calculation.
* **🎨 Modern User Interface:** Enhanced PyQt5 interface with high-DPI vector icons, streamlined input fields, friendly validation alerts, and responsive progress reporting.
* **📊 Interactive Results Visualizer:** Built-in preview dialog featuring the continuous IC map, frequency distribution histogram, descriptive statistics (mean, median, standard deviation), and export tools for publication-ready figures (PNG/PDF).
* **💾 Diagnostic Component Export:** Dedicated options to export intermediate rasters ({up}$, {down}$, Cavalli Roughness $, and Weight factor $).
* **🗂️ Preserved Legacy Code:** Codebases for **v3.0** and **v3.1** are preserved under the [legacy/](legacy/) directory for historical reproducibility.

---

## 📐 Mathematical Formulation

The Index of Connectivity ($) is defined as:

\\text{IC} = \\log_{10} \\left( \\frac{D_{up}}{D_{down}} \\right)

### 1. Upslope Component ({up}$)
Quantifies the potential for sediment delivery driven by upslope contributing area ($), average upslope slope gradient ($\\overline{S}$), and average surface impedance ($\\overline{W}$):
D_{up} = \\overline{W} \\cdot \\overline{S} \\cdot \\sqrt{A}

### 2. Downslope Component ({down}$)
Quantifies the travel path resistance of sediment moving from the cell along the flow path to the designated target or outlet:
D_{down} = \\sum_{i} \\frac{d_i}{W_i \\cdot S_i}
where $ is the length of cell $ along the flow path, $ is the local surface weighting factor, and $ is the local slope gradient (clamped to a minimum of .005$ to avoid division by zero).

### 3. Surface Weighting Factor ($)
When calculated automatically (**Cavalli et al., 2013**), the surface roughness index ($) is computed as the standard deviation of residual elevation in a moving window ( \\times N$, default 5):
RI = \\text{std}(DTM - \\mu_{local})
W = 1.0 - \\left( \\frac{RI}{RI_{max}} \\right) \\quad \\text{with } W \\ge 0.001

Optional logarithmic normalization (**Trevisani & Cavalli, 2016**):
W_{norm} = 1.0 - \\left[ \\frac{\\ln(RI) - \\ln(RI_{min})}{\\ln(RI_{max}) - \\ln(RI_{min})} \\right]

---

## 📥 Standalone Executable (Windows)

For Windows users who do not wish to install Python, pre-compiled standalone executables are available on the **[Releases Page](../../releases)**:

1. Download **SedInConnect_3.2.exe** from the latest Release.
2. Double-click the executable to launch the GUI (no installation required).

---

## 🛠️ Installation from Source

### Prerequisites
* Python 3.9+ (Python 3.10, 3.11, or 3.12 recommended)
* GDAL (via conda or pre-built wheels)

### Setup
`ash
# Clone the repository
git clone https://github.com/HydrogeomorphologyTools/SedInConnect_3.2.git
cd SedInConnect_3.2

# Install dependencies
pip install -r requirements.txt
`

---

## 🖥️ Usage

### Graphical User Interface (GUI)
Launch the graphical interface:
`ash
python main.py
`

### Command Line Interface (CLI)
SedInConnect can be executed in batch mode via CLI:
`ash
# Basic run with automatic Cavalli roughness weight
python main.py --dtm path/to/dtm_filled.tif --cellsize 2.5 --output path/to/ic.tif --auto-weight

# Full run with targets, sinks, parallel workers, and chunk size
python main.py --dtm path/to/dtm_filled.tif \\
               --cellsize 2.5 \\
               --output path/to/ic.tif \\
               --target path/to/streams.shp \\
               --sink path/to/sinks.shp \\
               --auto-weight \\
               --normalize \\
               --window-size 5 \\
               --save-components \\
               --workers 8 \\
               --chunk-size 1024
`

#### CLI Arguments Summary
| Argument | Description |
| :--- | :--- |
| --dtm <path> | Path to hydrologically conditioned input DTM (GeoTIFF) |
| --cellsize <float> | Raster cell resolution in meters |
| --output <path> | Destination path for output IC GeoTIFF |
| --target <path> | Optional ESRI Shapefile (.shp) of target areas/channels |
| --sink <path> | Optional ESRI Shapefile (.shp) of sink/reservoir areas |
| --weight <path> | Path to custom weighting factor raster (GeoTIFF) |
| --auto-weight | Automatically compute weight from surface roughness |
| --normalize | Apply logarithmic normalization to roughness |
| --window-size <int> | Moving window size for roughness (odd integer $\\ge 3$, default 5) |
| --save-components | Export {up}$ and {down}$ component rasters |
| --workers <int> | Number of parallel CPU workers for spatial convolution |
| --chunk-size <int> | Processing tile size in pixels (e.g. 1024, 2048, 4096) |
| --fill-dtm | Automatically run Priority-Flood depression filling |

---

## 📂 Repository Structure

`
SedInConnect_3.2/
├── main.py                      # Application entry point (GUI & CLI)
├── sedinconnect/                # Native SedInConnect 3.2 core package
│   ├── core/                    # Computational hydrology, weight, processor
│   │   └── native/              # Numba-accelerated D8, D-inf, and distance routing
│   ├── gui/                     # PyQt5 interface, widgets, and preview dialog
│   └── utils/                   # Raster I/O, geoprocessing, parameters
├── legacy/                      # Historical legacy releases
│   ├── SedInConnect_3.0/        # Legacy v3.0 codebase
│   └── SedInConnect_3.1/        # Legacy v3.1 codebase
├── requirements.txt             # Python dependencies
└── README.md                    # Documentation
`

---

## 📚 References & Citations

If you use **SedInConnect** in your research, please cite:

* **Cavalli, M., Trevisani, S., Comiti, F., & Marchi, L. (2013).** Geomorphometric assessment of spatial sediment connectivity in small Alpine catchments. *Geomorphology*, 188, 31-41. [doi:10.1016/j.geomorph.2012.05.007](https://doi.org/10.1016/j.geomorph.2012.05.007)
* **Crema, S., & Cavalli, M. (2018).** SedInConnect: a stand-alone, free and open source tool for the assessment of sediment connectivity. *Computers & Geosciences*, 111, 39-45. [doi:10.1016/j.cageo.2017.10.009](https://doi.org/10.1016/j.cageo.2017.10.009)
* **Borselli, L., Cassi, P., & Torri, D. (2008).** Prolegomena to sediment connectivity: Thinking with the flow. *Catena*, 75(3), 268-277. [doi:10.1016/j.catena.2008.07.006](https://doi.org/10.1016/j.catena.2008.07.006)
* **Trevisani, S., & Cavalli, M. (2016).** Topography-based flow-direction modeling: how much does spatial resolution matter? *Earth Surface Processes and Landforms*, 41(5), 658-670. [doi:10.1002/esp.3854](https://doi.org/10.1002/esp.3854)
