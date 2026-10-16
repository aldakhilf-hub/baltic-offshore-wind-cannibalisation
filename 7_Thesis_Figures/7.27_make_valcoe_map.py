"""
7.27_make_valcoe_map.py — the novel metric: VALUE-ADJUSTED LCOE (vLCOE), 2025 /
2030 / 2040. Folds capture value into the cost of energy.

    vLCOE (EUR/MWh) = LCOE(depth, distance, year) / capture value(zone, year)

This is the average wholesale price a site needs to break even, once cannibalisation
is accounted for (it follows from capture_price >= LCOE, i.e. P*CV >= LCOE -> P >=
LCOE/CV). Standard LCOE asks 'cost per MWh produced'; vLCOE asks 'cost per MWh of
VALUE delivered'. As the buildout erodes capture value, vLCOE rises even while the
raw LCOE falls with technology learning, the cannibalisation undoing the learning.

The dashed contour marks a reference wholesale price (~70 EUR/MWh): inside it the
site is merchant-competitive, outside it needs revenue support.

Output -> results/fig_vlcoe_{2025,2030,2040}.png + 10_Presentation/figures/ + vlcoe_summary.csv
"""
from pathlib import Path
import warnings
warnings.filterwarnings("ignore")
import numpy as np
import pandas as pd
import xarray as xr
import geopandas as gpd
from scipy.spatial import cKDTree
from scipy.ndimage import distance_transform_edt
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import cartopy.feature as cfeature

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "7_Thesis_Figures" / "results"
DECK = ROOT / "10_Presentation" / "figures"
GEO = Path.home() / "pypsa-eur/resources/faisal-2023/regions_offshore_base_s_30.geojson"
GEBCO = (Path.home() / "pypsa-eur/data/gebco/archive/2014/GEBCO_2014_2D.nc")
ZONES = ["DE", "NL", "BE", "DK1", "FR", "PL", "EE", "LV", "LT", "FI", "DK2"]
EXTENT = [-6, 30, 46.5, 63.5]
WACC = 0.07
REF_PRICE = 70.0   # reference merchant wholesale price (EUR/MWh) for the competitiveness contour


def capex(depth, dist):
    base = 1.85e6
    fixed = np.where(depth <= 60, 12e3 * np.maximum(depth - 25, 0),
                     12e3 * 35 + 1.00e6 + 6e3 * np.maximum(depth - 60, 0))
    return base + fixed + 10e3 * np.maximum(dist - 25, 0)


def capex_factor(year):
    inv = lambda y: 2505.0 - (2505.0 - 1916.0) * (y - 2020) / 30.0
    return inv(year) / inv(2025)


def crf_year(year):
    n = 27.0 + (30.0 - 27.0) * (year - 2020) / 30.0
    return WACC * (1 + WACC) ** n / ((1 + WACC) ** n - 1)


def annual_cost(depth, dist, year):
    return capex(depth, dist) * capex_factor(year) * crf_year(year) + (75e3 + 250.0 * dist)


def to_zone(name):
    if name.startswith("DK1"): return "DK1"
    if name.startswith("DK2"): return "DK2"
    return name[:2]


# grids
cf = xr.open_dataarray(OUT / "gwa_cf_field.nc")
_m = np.isnan(cf.values); _d, (_iy, _ix) = distance_transform_edt(_m, return_indices=True)
cf_grid = np.where(_d <= 4, cf.values[_iy, _ix], np.nan)
LON, LAT = np.meshgrid(cf.x.values, cf.y.values)
geb = xr.open_dataset(GEBCO)["elevation"].sortby("lat").sortby("lon").interp(lat=cf.y, lon=cf.x).values
depth = np.where(geb < 0, -geb, np.nan); sea = geb < 0
dlat = 111.0 * abs(float(cf.y[1] - cf.y[0]))
dlon = 111.0 * np.cos(np.deg2rad(55)) * abs(float(cf.x[1] - cf.x[0]))
dist_km = distance_transform_edt(sea, sampling=(dlat, dlon))
feasible = np.isfinite(cf_grid) & sea & (depth <= 1000) & (dist_km <= 200)

# nearest-zone capture value
reg = gpd.read_file(GEO); reg["zone"] = reg["name"].map(to_zone)
reg = reg[reg.zone.isin(ZONES)].copy(); reg["geometry"] = reg.geometry.buffer(0)
cent = reg.dissolve("zone").geometry.representative_point()
zlist = list(cent.index); zxy = np.array([[cent[z].x, cent[z].y] for z in zlist])
_, idx = cKDTree(zxy).query(np.c_[LON.ravel(), LAT.ravel()])
zone_grid = np.array(zlist, dtype=object)[idx].reshape(cf_grid.shape)
tbl = pd.read_csv(OUT / "value_map_table.csv"); tbl["horizon"] = tbl["horizon"].astype(str)

TITLES = {"2025": "2025  ·  today", "2030": "2030", "2040": "2040  ·  full build-out"}
rows = []
for hz in ["2025", "2030", "2040"]:
    lcoe = annual_cost(depth, dist_km, int(hz)) / (cf_grid * 8760.0)
    cv = tbl[tbl.horizon == hz].set_index("zone").CV.to_dict()
    cvg = np.vectorize(lambda z: cv.get(z, np.nan))(zone_grid)
    vlcoe = np.where(feasible, lcoe / cvg, np.nan)
    fig = plt.figure(figsize=(7.6, 5.0))
    ax = fig.add_axes([0.02, 0.155, 0.96, 0.70], projection=ccrs.PlateCarree())
    ax.set_extent(EXTENT, crs=ccrs.PlateCarree())
    mesh = ax.pcolormesh(cf.x.values, cf.y.values, np.ma.masked_invalid(vlcoe),
                         cmap="RdYlGn_r", vmin=45, vmax=160, shading="auto",
                         transform=ccrs.PlateCarree(), zorder=1, rasterized=True)
    try:    # competitiveness contour at the reference price
        ax.contour(cf.x.values, cf.y.values, np.ma.masked_invalid(vlcoe), levels=[REF_PRICE],
                   colors="black", linewidths=1.1, linestyles="--",
                   transform=ccrs.PlateCarree(), zorder=4)
    except Exception:
        pass
    ax.add_feature(cfeature.LAND.with_scale("50m"), facecolor="#efece6", zorder=2)
    ax.add_feature(cfeature.COASTLINE.with_scale("50m"), lw=0.4, edgecolor="#888", zorder=3)
    ax.add_feature(cfeature.BORDERS.with_scale("50m"), lw=0.3, edgecolor="#c4c4c4", zorder=3)
    cax = fig.add_axes([0.18, 0.085, 0.64, 0.030])
    fig.colorbar(mesh, cax=cax, orientation="horizontal", extend="both").set_label(
        f"Value-adjusted LCOE = LCOE / capture value   (EUR/MWh; dashed contour at {REF_PRICE:.0f})", fontsize=9)
    fig.suptitle(f"Value-adjusted LCOE, {hz}", fontsize=13.5, y=0.96, color="#111")
    fig.savefig(OUT / f"fig_vlcoe_{hz}.png", dpi=190)
    plt.close(fig)
    comp = np.nansum(vlcoe < REF_PRICE) / np.sum(feasible) * 100
    rows.append(dict(year=hz, competitive_area_pct=round(comp, 1),
                     median_vlcoe=round(float(np.nanmedian(vlcoe)), 1),
                     min_vlcoe=round(float(np.nanmin(vlcoe)), 1)))
    print(f"saved fig_vlcoe_{hz}.png  competitive(<{REF_PRICE:.0f}) {comp:.0f}%  median {np.nanmedian(vlcoe):.0f} EUR/MWh")
pd.DataFrame(rows).to_csv(OUT / "vlcoe_summary.csv", index=False)
