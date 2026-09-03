# 🗺️ SedInConnect 3.2 — ArcGIS Pro Python Toolbox (.pyt)

Official Python Toolbox for **ArcGIS Pro** (2.8+ / 3.0 / 3.1 / 3.2 / 3.3+).

> [!NOTE]
> **Beta Testing Phase (Preview):** This ArcGIS Pro Python Toolbox is currently released as a testing and preview feature. Feedback, bug reports, and suggestions are warmly welcomed!

---

## 🚀 Quick Start in ArcGIS Pro

1. Open **ArcGIS Pro** and load your project.
2. In the **Catalog Pane** (*View ➔ Catalog Pane*):
   * Expand **Project** ➔ Right-click **Toolboxes** ➔ Click **Add Toolbox**.
   * Browse to this folder and select **`SedInConnect.pyt`**.
3. Under *Toolboxes ➔ SedInConnect 3.2*, double-click:
   👉 **`Calculate Sediment Connectivity Index (IC)`**.

---

## ⚡ High-Speed Acceleration: Installing Numba in ArcGIS Pro

ArcGIS Pro comes with standard Python without Numba pre-installed. While SedInConnect includes a built-in pure NumPy fallback to prevent errors, **installing Numba unlocks full 10x–20x calculation speedups** (processing 15+ million pixels in seconds rather than minutes).

### Step-by-Step Installation (Takes 1 Minute):

1. Close ArcGIS Pro.
2. In the Windows Start Menu, search and open:  
   👉 **Python Command Prompt** *(located in the ArcGIS folder)*.
3. Run the command matching your ArcGIS Pro version:

#### For ArcGIS Pro 2.9, 3.0, 3.1, 3.2 (NumPy 1.x):
```cmd
pip install --user "numpy<2" "numba>=0.56"
```

#### For ArcGIS Pro 3.3+ (NumPy 2.x):
```cmd
pip install --user numba
```

#### Alternative: Via ArcGIS Pro GUI:
1. Open ArcGIS Pro ➔ Click **Settings** (bottom left) ➔ **Package Manager**.
2. If your default environment is active, search for `numba` and click **Install**.

---

## 🌟 Supported Features in ArcGIS Pro
* **Table of Contents (TOC) Map Layers:** Directly select layers from your active map.
* **File Geodatabase (.gdb):** Native support for reading and writing directly into ESRI `.gdb` feature classes and raster datasets.
* **Multi-threaded Roughness:** Configurable chunk sizes (`512` to `4096` px) and parallel CPU worker count.
* **All Calculation Modalities:** Target features, sink polygons, log-normalized weights, and Pit-filling.

---

## 📚 Scientific Reference & Acknowledgements
* Cavalli, M., Trevisani, S., Comiti, F., & Marchi, L. (2013). *Geomorphology*, 188, 31-41.
* Borselli, L., Cassi, P., & Torri, D. (2008). *Catena*, 75(3), 268-277.
* **CNR-IRPI Padova** — Developed within **MORPHEUS PRIN 2023-2026** (Prot. 2022JEFZRM).
