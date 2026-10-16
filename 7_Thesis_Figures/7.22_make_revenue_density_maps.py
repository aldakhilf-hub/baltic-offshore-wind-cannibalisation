"""
7.22_make_revenue_density_maps.py — granular (~25 km) revenue-density heat maps,
2025 / 2030 / 2040. The superposition:

    revenue density at a cell = (cell capacity factor, fixed wind resource)
                              x (its bidding zone's captured price, that year)

Layer 1 (fixed): wind_cf_field.nc from 7.21 (ERA5/atlite ~25 km).
Layer 2 (per zone, per year): captured price = capture value x average price, from
the central projection (value_map_table.csv). The granular texture is the same in
all three maps (the wind resource); the zones dim as their captured price falls.

Capture value itself is a zone-uniform price quantity, so the meaningful granular
field is REVENUE, not capture value.

Output -> results/fig_revenue_density_{2025,2030,2040}.png + 10_Presentation/figures/
"""
from pathlib import Path
import warnings
warnings.filterwarnings("ignore")
import numpy as np
import pandas as pd
import xarray as xr
import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import cartopy.feature as cfeature

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "7_Thesis_Figures" / "results"
DECK = ROOT / "10_Presentation" / "figures"
GEO = Path.home() / "pypsa-eur/resources/faisal-2023/regions_offshore_base_s_30.geojson"
ZONES = ["DE", "NL", "BE", "DK1", "FR", "PL", "EE", "LV", "LT", "FI", "DK2"]
EXTENT = [-6, 30, 46.5, 63.5]


def to_zone(name):
    if name.startswith("DK1"): return "DK1"
    if name.startswith("DK2"): return "DK2"
    return name[:2]


# Layer 1: the capacity-factor field
cf = xr.open_dataarray(OUT / "wind_cf_field.nc")
LON, LAT = np.meshgrid(cf.x.values, cf.y.values)

# assign every grid cell to a bidding zone via the offshore region polygons
reg = gpd.read_file(GEO)
reg["zone"] = reg["name"].map(to_zone)
reg = reg[reg.zone.isin(ZONES)].copy()
reg["geometry"] = reg.geometry.buffer(0)
# assign every cell to its NEAREST modelled zone (fills the seas continuously; land is
# hidden by the land overlay). Cells too far from any modelled zone are left blank.
from scipy.spatial import cKDTree
cent = reg.dissolve("zone").geometry.representative_point()
zlist = list(cent.index)
zxy = np.array([[cent[z].x, cent[z].y] for z in zlist])
dist, idx = cKDTree(zxy).query(np.c_[LON.ravel(), LAT.ravel()])
zone_flat = np.array(zlist, dtype=object)[idx]
zone_flat[dist > 4.0] = np.nan           # >~350 km from any modelled zone -> blank
zone_grid = zone_flat.reshape(cf.shape)
cf_grid = cf.values

# Layer 2: captured price per zone per year (k EUR/MWh path -> revenue density)
tbl = pd.read_csv(OUT / "value_map_table.csv")
tbl["horizon"] = tbl["horizon"].astype(str)


P25 = tbl[tbl.horizon == "2025"].set_index("zone").price_level.to_dict()  # today's zone prices (no future artifact)


def revenue_grid(hz):
    # captured price = capture value(year) x TODAY's zone price level, so the only thing that
    # changes over time is the capture-value erosion (the future surrogate prices carry a Polish
    # scarcity artifact, so they are not used here).
    cv = tbl[tbl.horizon == hz].set_index("zone").CV.to_dict()
    cap_price = np.vectorize(
        lambda z: cv.get(z, np.nan) * P25.get(z, np.nan) if isinstance(z, str) else np.nan)(zone_grid)
    return cf_grid * 8760.0 * cap_price / 1000.0  # k EUR/MW/yr


VMAX = float(np.nanmax([np.nanmax(revenue_grid(h)) for h in ("2025", "2030", "2040")]))
TITLES = {"2025": "2025  ·  today", "2030": "2030  ·  build-out underway", "2040": "2040  ·  full build-out"}

for hz in ["2025", "2030", "2040"]:
    rev = revenue_grid(hz)
    fig = plt.figure(figsize=(7.6, 8.2))
    ax = fig.add_axes([0.02, 0.08, 0.96, 0.86], projection=ccrs.PlateCarree())
    ax.set_extent(EXTENT, crs=ccrs.PlateCarree())
    ax.add_feature(cfeature.LAND.with_scale("50m"), facecolor="#efece6", zorder=2)
    ax.add_feature(cfeature.COASTLINE.with_scale("50m"), lw=0.4, edgecolor="#888", zorder=3)
    ax.add_feature(cfeature.BORDERS.with_scale("50m"), lw=0.3, edgecolor="#c4c4c4", zorder=3)
    mesh = ax.pcolormesh(cf.x.values, cf.y.values, np.ma.masked_invalid(rev),
                         cmap="RdYlGn", vmin=0, vmax=VMAX, shading="gouraud",
                         transform=ccrs.PlateCarree(), zorder=1)
    cax = fig.add_axes([0.18, 0.045, 0.64, 0.022])
    fig.colorbar(mesh, cax=cax, orientation="horizontal").set_label(
        "Offshore-wind revenue density  (thousand EUR per MW per year)", fontsize=9.5)
    fig.suptitle(TITLES[hz], fontsize=15, fontweight="bold", y=0.965)
    fig.text(0.5, 0.925, "capacity factor (~25 km) x capture value x today's zone price  ·  "
             "the wind resource is fixed; zones dim as capture value erodes",
             ha="center", fontsize=9.0, color="#555")
    for d in (OUT, DECK):
        fig.savefig(d / f"fig_revenue_density_{hz}.png", dpi=185)
    plt.close(fig)
    print(f"saved fig_revenue_density_{hz}.png  (max {np.nanmax(rev):.0f} k EUR/MW/yr)")
