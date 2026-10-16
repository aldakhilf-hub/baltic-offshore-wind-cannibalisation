"""
7.18_make_value_heatmaps.py — proper choropleth HEAT MAPS of offshore-wind capture
value, three separate maps for 2025 / 2030 / 2040 (supervisor, 2026-06-22:
"a proper heat map, three separate maps").

Each bidding zone's OFFSHORE sea area (PyPSA-Eur regions_offshore, 30-cluster) is
shaded by its capture value on the central NT-balticBaseline scenario. Present
(2025) is observed; 2030/2040 are the PyPSA projection. Shared colour scale so the
three maps read like-for-like.

Output -> results/fig_heatmap_{2025,2030,2040}.png + 10_Presentation/figures/
"""
from pathlib import Path
import warnings
warnings.filterwarnings("ignore")
import numpy as np
import pandas as pd
import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patheffects as pe
import cartopy.crs as ccrs
import cartopy.feature as cfeature

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "7_Thesis_Figures" / "results"
DECK = ROOT / "10_Presentation" / "figures"
GEO = Path.home() / "pypsa-eur/resources/faisal-2023/regions_offshore_base_s_30.geojson"

ZONES = ["DE", "NL", "BE", "DK1", "FR", "PL", "EE", "LV", "LT", "DK2"]  # Finland excluded (nuclear outlier, set aside)
CMAP, VMIN, VMAX = plt.cm.RdYlGn, 0.20, 0.95
EXTENT = [-6, 30, 46.5, 63.5]
HALO = [pe.withStroke(linewidth=2.4, foreground="white")]
# fixed, spread label anchors for the crowded North Sea cluster (others auto)
ANCHOR = {"DE": (6.3, 54.3), "NL": (3.5, 52.4), "BE": (2.2, 51.1), "DK1": (7.0, 57.4),
          "DK2": (13.0, 55.6), "FR": (-3.3, 47.1), "PL": (18.2, 54.6)}


def to_zone(name):
    if name.startswith("DK1"):
        return "DK1"
    if name.startswith("DK2"):
        return "DK2"
    return name[:2]


# offshore regions -> dissolve to zones
reg = gpd.read_file(GEO)
reg["zone"] = reg["name"].map(to_zone)
reg["geometry"] = reg.geometry.buffer(0)
zones = reg[reg.zone.isin(ZONES)].dissolve("zone")

# per-zone capture value per horizon (central scenario; from 7.14 output)
tbl = pd.read_csv(OUT / "value_map_table.csv")
tbl["horizon"] = tbl["horizon"].astype(str)

TITLES = {"2025": "Capture value by bidding zone, 2025",
          "2030": "Capture value by bidding zone, 2030",
          "2040": "Capture value by bidding zone, 2040"}

for hz in ["2025", "2030", "2040"]:
    cvmap = tbl[tbl.horizon == hz].set_index("zone").CV.to_dict()
    capmap = tbl[tbl.horizon == hz].set_index("zone").capacity_MW.to_dict()
    fig = plt.figure(figsize=(7.6, 5.0))
    ax = fig.add_axes([0.02, 0.155, 0.96, 0.70], projection=ccrs.PlateCarree())
    ax.set_extent(EXTENT, crs=ccrs.PlateCarree())
    ax.add_feature(cfeature.OCEAN.with_scale("50m"), facecolor="#eaf2f8")
    ax.add_feature(cfeature.LAND.with_scale("50m"), facecolor="#efece6")
    ax.add_feature(cfeature.COASTLINE.with_scale("50m"), lw=0.4, edgecolor="#888")
    ax.add_feature(cfeature.BORDERS.with_scale("50m"), lw=0.3, edgecolor="#c4c4c4")

    for zone, row in zones.iterrows():
        cv = cvmap.get(zone, np.nan)
        face = CMAP((cv - VMIN) / (VMAX - VMIN)) if pd.notna(cv) else "#cfcfcf"
        ax.add_geometries([row.geometry], ccrs.PlateCarree(), facecolor=face,
                          edgecolor="#2c3e50", linewidth=0.7, alpha=0.92, zorder=4)
        pt = row.geometry.representative_point()
        if pd.notna(cv):
            lx, ly = ANCHOR.get(zone, (pt.x, pt.y))
            ax.annotate(f"{zone}  {cv:.2f}", (lx, ly), ha="center", va="center", fontsize=8.0,
                        fontweight="bold", color="#111", zorder=6, path_effects=HALO,
                        transform=ccrs.PlateCarree())

    ax.text(0.5, 61.9, "NORTH SEA", fontsize=8, color="#2471a3", fontweight="bold",
            style="italic", ha="center", transform=ccrs.PlateCarree(), zorder=5, path_effects=HALO)
    ax.text(24.5, 61.0, "BALTIC SEA", fontsize=8, color="#c0392b", fontweight="bold",
            style="italic", ha="center", transform=ccrs.PlateCarree(), zorder=5, path_effects=HALO)

    sm = plt.cm.ScalarMappable(cmap=CMAP, norm=plt.Normalize(VMIN, VMAX))
    cax = fig.add_axes([0.18, 0.085, 0.64, 0.030])
    fig.colorbar(sm, cax=cax, orientation="horizontal").set_label(
        "Offshore-wind capture value", fontsize=10)
    fig.suptitle(TITLES[hz], fontsize=13.5, y=0.96, color="#111")
    fig.savefig(OUT / f"fig_heatmap_{hz}.png", dpi=185)
    plt.close(fig)
    print(f"saved fig_heatmap_{hz}.png  (zones coloured: {sum(pd.notna(cvmap.get(z, np.nan)) for z in ZONES)})")
