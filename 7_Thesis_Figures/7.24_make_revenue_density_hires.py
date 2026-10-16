"""
7.24_make_revenue_density_hires.py — the 'full smooth sea' granular revenue-density
maps, 2025 / 2030 / 2040, on the high-resolution Global Wind Atlas field (~2 km,
full North Sea + Baltic coverage) from 7.23.

revenue density = capacity factor (GWA, fixed) x capture value(year) x today's zone price.
Every sea point is tinted by its nearest modelled bidding zone's value; the GWA field's
own coverage (the 13 countries' EEZs) defines the sea, so no extra masking is needed.

Output -> results/fig_revenue_density_hires_{2025,2030,2040}.png + 10_Presentation/figures/
"""
from pathlib import Path
import warnings
warnings.filterwarnings("ignore")
import numpy as np
import pandas as pd
import xarray as xr
import geopandas as gpd
from scipy.spatial import cKDTree
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


cf = xr.open_dataarray(OUT / "gwa_cf_field.nc")
LON, LAT = np.meshgrid(cf.x.values, cf.y.values)
cf_grid = cf.values
# fill the thin nodata seams between country EEZ tiles (within ~4 cells of data),
# leaving the open ocean beyond the modelled area masked
from scipy.ndimage import distance_transform_edt
_m = np.isnan(cf_grid)
_d, (_iy, _ix) = distance_transform_edt(_m, return_indices=True)
cf_grid = np.where(_d <= 4, cf_grid[_iy, _ix], np.nan)

# nearest modelled zone per cell (for the value tint)
reg = gpd.read_file(GEO); reg["zone"] = reg["name"].map(to_zone)
reg = reg[reg.zone.isin(ZONES)].copy(); reg["geometry"] = reg.geometry.buffer(0)
cent = reg.dissolve("zone").geometry.representative_point()
zlist = list(cent.index); zxy = np.array([[cent[z].x, cent[z].y] for z in zlist])
_, idx = cKDTree(zxy).query(np.c_[LON.ravel(), LAT.ravel()])
zone_grid = np.array(zlist, dtype=object)[idx].reshape(cf_grid.shape)

tbl = pd.read_csv(OUT / "value_map_table.csv"); tbl["horizon"] = tbl["horizon"].astype(str)
P25 = tbl[tbl.horizon == "2025"].set_index("zone").price_level.to_dict()


def revenue(hz):
    cv = tbl[tbl.horizon == hz].set_index("zone").CV.to_dict()
    cap_price = np.vectorize(lambda z: cv.get(z, np.nan) * P25.get(z, np.nan))(zone_grid)
    return cf_grid * 8760.0 * cap_price / 1000.0   # k EUR/MW/yr


VMAX = float(np.nanmax([np.nanmax(revenue(h)) for h in ("2025", "2030", "2040")]))
TITLES = {"2025": "Revenue density, 2025", "2030": "Revenue density, 2030", "2040": "Revenue density, 2040"}

for hz in ["2025", "2030", "2040"]:
    rev = revenue(hz)
    fig = plt.figure(figsize=(7.6, 5.0))
    ax = fig.add_axes([0.02, 0.155, 0.96, 0.70], projection=ccrs.PlateCarree())
    ax.set_extent(EXTENT, crs=ccrs.PlateCarree())
    mesh = ax.pcolormesh(cf.x.values, cf.y.values, np.ma.masked_invalid(rev),
                         cmap="RdYlGn", vmin=0, vmax=VMAX, shading="auto",
                         transform=ccrs.PlateCarree(), zorder=1, rasterized=True)
    ax.add_feature(cfeature.LAND.with_scale("50m"), facecolor="#efece6", zorder=2)
    ax.add_feature(cfeature.COASTLINE.with_scale("50m"), lw=0.4, edgecolor="#888", zorder=3)
    ax.add_feature(cfeature.BORDERS.with_scale("50m"), lw=0.3, edgecolor="#c4c4c4", zorder=3)
    cax = fig.add_axes([0.18, 0.085, 0.64, 0.030])
    fig.colorbar(mesh, cax=cax, orientation="horizontal").set_label(
        "Offshore-wind revenue density  (thousand EUR per MW per year)", fontsize=9.5)
    fig.suptitle(TITLES[hz], fontsize=13.5, y=0.96, color="#111")
    fig.savefig(OUT / f"fig_revenue_density_hires_{hz}.png", dpi=190)
    plt.close(fig)
    print(f"saved fig_revenue_density_hires_{hz}.png  (max {np.nanmax(rev):.0f} k EUR/MW/yr)")
