# SedInConnect — QGIS Plugin & Processing Toolbox (v3.2.0)

Official **QGIS Plugin and Processing Toolbox Provider** for stand-alone and native Sediment Connectivity Index (IC) assessment in river catchments.

Developed at **CNR-IRPI Padova (Italy)** within the **MORPHEUS PRIN 2023-2026 Project**.

---

## 🌟 Key Features in QGIS

* **Dual Integration:**
  1. **Dedicated GUI Dialog:** Easily select input DTM, Target, and Sink layers from active QGIS map layers, configure moving window sizes, and preview results with interactive histograms.
  2. **QGIS Processing Toolbox:** Fully integrated native algorithm under `Processing Toolbox ➔ SedInConnect ➔ Calculate Sediment Connectivity Index (IC)`. Supports **batch processing** across multiple catchments and seamless integration into the **QGIS Graphical Modeler**.
* **ArcGIS-Style Cold-to-Hot Stretched Colormap:** Automatically styles the output $IC$ layer upon completion:
  * 🔵 **Deep Lapislazuli Blue (`#0F2D6E`):** Low Connectivity / Deposition zones
  * 🟡 **Yellow / Orange:** Transitional connectivity
  * 🔴 **Vibrant Red (`#DC1414`):** High Connectivity / Fast delivery paths
* **Zero External Dependencies:** Powered by pure native Python/Numba algorithms (no TauDEM or external C++ binary installation required).
* **Automatic Dependency Installer:** Automatically verifies and installs required scientific libraries (`numba`, `numpy`, `scipy`, `matplotlib`) into the QGIS Python environment upon startup.

---

## 📥 Installation

### Method A: Install from ZIP Archive (Recommended)

1. Download the pre-built plugin archive: [`SedInConnect_QGIS_Plugin_v3.2.0.zip`](SedInConnect_QGIS_Plugin_v3.2.0.zip).
2. Open **QGIS** (version 3.0 or later).
3. In the top menu, navigate to: **Plugins** ➔ **Manage and Install Plugins...**
4. Select the **Install from ZIP** tab on the left sidebar.
5. Browse and select `SedInConnect_QGIS_Plugin_v3.2.0.zip`, then click **Install Plugin**.
6. The plugin will automatically appear in your **Raster toolbar**, **Plugins menu**, and **Processing Toolbox**.

### Method B: Manual Installation (Development / Git Clone)

Copy the `qgis_plugin` folder into your QGIS active profile plugins directory:
* **Windows:** `C:\Users\<YourUsername>\AppData\Roaming\QGIS\QGIS3\profiles\default\python\plugins\sedinconnect_qgis_plugin`
* **macOS:** `~/Library/Application Support/QGIS/QGIS3/profiles/default/python/plugins/sedinconnect_qgis_plugin`
* **Linux:** `~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/sedinconnect_qgis_plugin`

---

## 🚀 How to Use

### 1. Using the Dedicated GUI Dialog
* Click the **SedInConnect icon** on the Raster Toolbar, or go to **Raster ➔ SedInConnect**.
* Select your **DTM Raster Layer** from the dropdown menu.
* *(Optional)* Select a **Target Layer** (stream network lines/polygons, lake outlets, dams). If omitted, connectivity to the catchment outlet is calculated automatically.
* *(Optional)* Select a **Sink Layer** (depressions, retention ponds).
* Set the **Roughness Window Size** (default: `3x3` pixels).
* Check *"Automatically add output IC layer to QGIS canvas with ArcGIS Cold-to-Hot colormap"*.
* Specify the output `.tif` destination path and click **Run Calculation**.

### 2. Using the Processing Toolbox & Graphical Modeler
* Open the **Processing Toolbox** (`Ctrl + Alt + T` or click the gear icon ⚙️).
* Expand **SedInConnect** ➔ **Sediment Connectivity** ➔ double-click **Calculate Sediment Connectivity Index (IC)**.
* Right-click the algorithm to run in **Batch Mode** across multiple catchment datasets.

---

## 📚 Scientific References
1. **Cavalli, M., Trevisani, S., Comiti, F., & Marchi, L. (2013).** Geomorphometric assessment of spatial sediment connectivity in small Alpine catchments. *Geomorphology*, 188, 31-41. [doi:10.1016/j.geomorph.2012.05.007](https://doi.org/10.1016/j.geomorph.2012.05.007)
2. **Crema, S., & Cavalli, M. (2018).** SedInConnect: a stand-alone, free and open source tool for the assessment of sediment connectivity. *Computers & Geosciences*, 111, 39-45. [doi:10.1016/j.cageo.2017.10.009](https://doi.org/10.1016/j.cageo.2017.10.009)
