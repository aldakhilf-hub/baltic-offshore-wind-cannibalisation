"""
7.30_optimal_grid_maps.py — capture-value heat maps on the OPTIMAL grid (both basins,
fair comparison), 2025/2030/2040 + the Baltic interconnection cost-benefit.

Supervisor asks: frozen grid is unrealistic; allow both basins the optimal grid; is
there an amount of interconnection that makes the Baltic worthwhile?

Capture value per zone read from the solved vopt (optimal-grid) networks; present (2025)
is observed. Same offshore-region choropleth as 7.18.
Output -> results/fig_heatmap_opt_{2025,2030,2040}.png + optimal_cv_table.csv
"""
import importlib.util, warnings
from pathlib import Path
import numpy as np, pandas as pd, geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patheffects as pe
import cartopy.crs as ccrs, cartopy.feature as cfeature
warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "7_Thesis_Figures" / "results"
DECK = ROOT / "10_Presentation" / "figures"
GEO = Path.home() / "pypsa-eur/resources/faisal-2023/regions_offshore_base_s_30.geojson"
VOPT = Path.home() / "pypsa-eur/results/scenarios_tyndp_v3_vopt"
FROZEN = Path.home() / "pypsa-eur/results/scenarios_tyndp_v3"
ZONES = ["DE", "NL", "BE", "DK1", "FR", "PL", "EE", "LV", "LT", "DK2"]  # Finland excluded (nuclear outlier)
BAL = ["PL", "EE", "LV", "LT", "DK2"]
CMAP, VMIN, VMAX = plt.cm.RdYlGn, 0.20, 0.95
EXTENT = [-6, 30, 46.5, 63.5]; HALO = [pe.withStroke(linewidth=2.4, foreground="white")]
ANCHOR = {"DE": (6.6, 54.0), "NL": (4.0, 52.6), "BE": (2.4, 51.2), "DK1": (7.4, 56.7),
          "DK2": (12.6, 54.7), "FR": (-3.0, 47.3)}
spec = importlib.util.spec_from_file_location("sur", ROOT / "1_PyPSA_Model/scripts/1.13_surrogate_runs.py")
sur = importlib.util.module_from_spec(spec); spec.loader.exec_module(sur)
import pypsa


def per_zone(path):
    n = pypsa.Network(path); out = {}
    for z in ZONES:
        r = sur.offshore_capture(n, z)
        if r.get("energy_GWh", 0) > 0 and pd.notna(r.get("CV_raw")):
            out[z] = (float(r["CV_raw"]), float(r["energy_GWh"]))
    return out


opt30, opt40 = per_zone(VOPT / "2030-NT-balticBaseline.nc"), per_zone(VOPT / "2040-NT-balticBaseline.nc")
fr40 = per_zone(FROZEN / "2040-NT-balticBaseline.nc")
pres = pd.read_csv(OUT / "value_map_table.csv"); pres["horizon"] = pres.horizon.astype(str)
cv25 = pres[pres.horizon == "2025"].set_index("zone").CV.to_dict()
CVMAP = {"2025": cv25, "2030": {z: v[0] for z, v in opt30.items()}, "2040": {z: v[0] for z, v in opt40.items()}}

# ---- Baltic interconnection cost-benefit (frozen -> optimal, 2040) ----
def ewt(d, zs):
    num = sum(d[z][0] * d[z][1] for z in zs if z in d); den = sum(d[z][1] for z in zs if z in d)
    return num / den, den
cvf, en = ewt(fr40, BAL); cvo, _ = ewt(opt40, BAL)
P = 60.0   # representative 2040 Baltic wholesale price EUR/MWh
uplift = (cvo - cvf) * P * en * 1e3 / 1e9   # GWh*1e3=MWh; EUR -> billion
print(f"Baltic 2040: CV {cvf:.2f} (frozen) -> {cvo:.2f} (optimal); offshore energy {en/1e3:.0f} TWh")
print(f"Captured-revenue uplift from interconnection: ~EUR {uplift:.1f} bn/yr (vs ~2.2 bn/yr for ALL new lines)")

# ---- choropleth (offshore regions) ----
reg = gpd.read_file(GEO); reg["zone"] = reg["name"].map(lambda n: "DK1" if n.startswith("DK1") else "DK2" if n.startswith("DK2") else n[:2])
zones = reg[reg.zone.isin(ZONES)].copy(); zones["geometry"] = zones.geometry.buffer(0)
zones = zones.dissolve("zone")
TITLES = {"2025": "2025  ·  today", "2030": "2030  ·  with grid build-out", "2040": "2040  ·  with grid build-out"}
for hz in ["2025", "2030", "2040"]:
    cvm = CVMAP[hz]
    fig = plt.figure(figsize=(7.6, 5.0)); ax = fig.add_axes([0.02, 0.155, 0.96, 0.70], projection=ccrs.PlateCarree())
    ax.set_extent(EXTENT, crs=ccrs.PlateCarree())
    ax.add_feature(cfeature.OCEAN.with_scale("50m"), facecolor="#eaf2f8")
    ax.add_feature(cfeature.LAND.with_scale("50m"), facecolor="#efece6")
    ax.add_feature(cfeature.COASTLINE.with_scale("50m"), lw=0.4, edgecolor="#888")
    for z, row in zones.iterrows():
        cv = cvm.get(z, np.nan)
        face = CMAP((cv - VMIN) / (VMAX - VMIN)) if pd.notna(cv) else "#cfcfcf"
        ax.add_geometries([row.geometry], ccrs.PlateCarree(), facecolor=face, edgecolor="#2c3e50", linewidth=0.7, alpha=0.92, zorder=4)
        if pd.notna(cv):
            pt = row.geometry.representative_point(); lx, ly = ANCHOR.get(z, (pt.x, pt.y))
            ax.annotate(f"{z} {cv:.2f}", (lx, ly), ha="center", va="center", fontsize=8.6, fontweight="bold", color="#111", zorder=6, path_effects=HALO, transform=ccrs.PlateCarree())
    sm = plt.cm.ScalarMappable(cmap=CMAP, norm=plt.Normalize(VMIN, VMAX))
    cax = fig.add_axes([0.18, 0.085, 0.64, 0.030]); fig.colorbar(sm, cax=cax, orientation="horizontal").set_label("Offshore-wind capture value (optimal grid)", fontsize=10)
    fig.suptitle(f"Capture value on the optimal grid, {hz}", fontsize=13.5, y=0.96, color="#111")
    fig.savefig(OUT / f"fig_heatmap_opt_{hz}.png", dpi=185)
    plt.close(fig)
    print(f"saved fig_heatmap_opt_{hz}.png")
pd.DataFrame([{"zone": z, "cv2025": cv25.get(z), "cv2030_opt": CVMAP['2030'].get(z), "cv2040_opt": CVMAP['2040'].get(z)} for z in ZONES]).to_csv(OUT / "optimal_cv_table.csv", index=False)
