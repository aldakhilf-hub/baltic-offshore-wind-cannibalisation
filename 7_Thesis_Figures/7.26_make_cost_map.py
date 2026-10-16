"""
7.26_make_cost_map.py — the offshore-wind COST map: levelised cost of energy
(LCOE, EUR/MWh) by location, 2025 / 2030 / 2040, with technology learning.

LCOE = annualised cost(depth, distance, year) / (capacity factor x 8760)

Same cost model as 7.25 (DEA learning trajectory; CAPEX rises with depth, distance,
and a floating premium > 60 m). Low LCOE (green) = cheap to build = windy, shallow,
near shore; high LCOE (red) = deep / far / low-wind. The whole field dims (gets
cheaper) toward 2040 as costs fall.

Output -> results/fig_cost_lcoe_{2025,2030,2040}.png + 10_Presentation/figures/
"""
from pathlib import Path
import warnings
warnings.filterwarnings("ignore")
import numpy as np
import xarray as xr
from scipy.ndimage import distance_transform_edt
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import cartopy.feature as cfeature

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "7_Thesis_Figures" / "results"
DECK = ROOT / "10_Presentation" / "figures"
GEBCO = (Path.home() / "pypsa-eur/data/gebco/archive/2014/GEBCO_2014_2D.nc")
EXTENT = [-6, 30, 46.5, 63.5]
WACC = 0.07


def capex(depth, dist):
    base = 1.85e6
    fixed = np.where(depth <= 60, 12e3 * np.maximum(depth - 25, 0),
                     12e3 * 35 + 1.00e6 + 6e3 * np.maximum(depth - 60, 0))
    grid = 10e3 * np.maximum(dist - 25, 0)
    return base + fixed + grid


def capex_factor(year):
    inv = lambda y: 2505.0 - (2505.0 - 1916.0) * (y - 2020) / 30.0
    return inv(year) / inv(2025)


def crf_year(year):
    n = 27.0 + (30.0 - 27.0) * (year - 2020) / 30.0
    return WACC * (1 + WACC) ** n / ((1 + WACC) ** n - 1)


def annual_cost(depth, dist, year):
    return capex(depth, dist) * capex_factor(year) * crf_year(year) + (75e3 + 250.0 * dist)


# grids
cf = xr.open_dataarray(OUT / "gwa_cf_field.nc")
_m = np.isnan(cf.values); _d, (_iy, _ix) = distance_transform_edt(_m, return_indices=True)
cf_grid = np.where(_d <= 4, cf.values[_iy, _ix], np.nan)
geb = xr.open_dataset(GEBCO)["elevation"].sortby("lat").sortby("lon").interp(lat=cf.y, lon=cf.x).values
depth = np.where(geb < 0, -geb, np.nan); sea = geb < 0
dlat = 111.0 * abs(float(cf.y[1] - cf.y[0]))
dlon = 111.0 * np.cos(np.deg2rad(55)) * abs(float(cf.x[1] - cf.x[0]))
dist_km = distance_transform_edt(sea, sampling=(dlat, dlon))
feasible = np.isfinite(cf_grid) & sea & (depth <= 1000) & (dist_km <= 200)

TITLES = {"2025": "2025  ·  today", "2030": "2030", "2040": "2040  ·  with technology learning"}
for hz in ["2025", "2030", "2040"]:
    lcoe = annual_cost(depth, dist_km, int(hz)) / (cf_grid * 8760.0)   # EUR/MWh
    lcoe = np.where(feasible, lcoe, np.nan)
    fig = plt.figure(figsize=(7.6, 5.0))
    ax = fig.add_axes([0.02, 0.155, 0.96, 0.70], projection=ccrs.PlateCarree())
    ax.set_extent(EXTENT, crs=ccrs.PlateCarree())
    mesh = ax.pcolormesh(cf.x.values, cf.y.values, np.ma.masked_invalid(lcoe),
                         cmap="RdYlGn_r", vmin=40, vmax=140, shading="auto",
                         transform=ccrs.PlateCarree(), zorder=1, rasterized=True)
    ax.add_feature(cfeature.LAND.with_scale("50m"), facecolor="#efece6", zorder=2)
    ax.add_feature(cfeature.COASTLINE.with_scale("50m"), lw=0.4, edgecolor="#888", zorder=3)
    ax.add_feature(cfeature.BORDERS.with_scale("50m"), lw=0.3, edgecolor="#c4c4c4", zorder=3)
    cax = fig.add_axes([0.18, 0.085, 0.64, 0.030])
    fig.colorbar(mesh, cax=cax, orientation="horizontal", extend="both").set_label(
        "Levelised cost of energy  (EUR/MWh)", fontsize=9.5)
    fig.suptitle(f"Levelised cost of energy, {hz}", fontsize=13.5, y=0.96, color="#111")
    fig.savefig(OUT / f"fig_cost_lcoe_{hz}.png", dpi=190)
    plt.close(fig)
    print(f"saved fig_cost_lcoe_{hz}.png  median LCOE {np.nanmedian(lcoe):.0f} EUR/MWh  "
          f"min {np.nanmin(lcoe):.0f}")
