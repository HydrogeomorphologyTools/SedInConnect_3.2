# SedInConnect — ArcGIS Pro Python Toolbox (`SedInConnect.pyt`)

Official **Python Toolbox (`.pyt`)** for calculating the **Index of Sediment Connectivity (IC)** (Cavalli et al., 2013; Borselli et al., 2008) directly in **ArcGIS Pro** and **ArcGIS Desktop**.

Developed at **CNR-IRPI Padova (Italy)** within the **MORPHEUS PRIN 2023-2026 Project**.

---

## 🌟 Key Features in ArcGIS Pro

* **Native Python Toolbox (`.pyt`):** Zero DLL compilation or separate installation required. Works seamlessly out of the box in ArcGIS Pro.
* **ModelBuilder & Geoprocessing Integration:** Fully compatible with ArcGIS Pro ModelBuilder, Batch Processing, and Python scripting (`arcpy`).
* **Complete Parameter Control:** Select DTM layers, target river lines/polygons, sink depressions, roughness window sizes, and export intermediate components ($D_{up}$, $D_{down}$, Roughness, Weight).
* **High Performance Engine:** Runs the pure native 64-bit Numba/NumPy computation pipeline with multithreaded acceleration.

---

## 📥 How to Load and Use in ArcGIS Pro

### 1. Add Toolbox to ArcGIS Pro Project
1. Open your project in **ArcGIS Pro**.
2. Open the **Catalog Pane** (View ➔ Catalog Pane).
3. Right-click **Toolboxes** ➔ **Add Toolbox**.
4. Browse to the `arcgis_toolbox/` folder and select **`SedInConnect.pyt`**.
5. The toolbox `SedInConnect 3.2` will appear under your Toolboxes list.

### 2. Run the Tool
1. Expand **`SedInConnect 3.2`** ➔ double-click **`Calculate Sediment Connectivity Index (IC)`**.
2. Select your **Input DTM** from the map layers dropdown.
3. *(Optional)* Select **Target Features** (streams, dams, reservoirs) or leave blank for catchment outlet calculation.
4. *(Optional)* Select **Sink Features** (internal retention basins).
5. Specify the **Output Connectivity Index (IC)** raster path (e.g. `C:/GIS/ic_output.tif`).
6. Click **Run**.

### 3. Using in Python Scripts (`arcpy`)

```python
import arcpy

# Import SedInConnect Python Toolbox
arcpy.ImportToolbox(r"C:/path/to/arcgis_toolbox/SedInConnect.pyt")

# Run calculation
arcpy.sedinconnect.CalculateSedimentConnectivity(
    in_dtm="dtmfel.tif",
    in_target="streams.shp",
    use_auto_weight=True,
    window_size=3,
    out_ic="ic_output.tif"
)
```

---

## 📚 Scientific References
1. **Cavalli, M., Trevisani, S., Comiti, F., & Marchi, L. (2013).** Geomorphometric assessment of spatial sediment connectivity in small Alpine catchments. *Geomorphology*, 188, 31-41. [doi:10.1016/j.geomorph.2012.05.007](https://doi.org/10.1016/j.geomorph.2012.05.007)
2. **Crema, S., & Cavalli, M. (2018).** SedInConnect: a stand-alone, free and open source tool for the assessment of sediment connectivity. *Computers & Geosciences*, 111, 39-45. [doi:10.1016/j.cageo.2017.10.009](https://doi.org/10.1016/j.cageo.2017.10.009)
