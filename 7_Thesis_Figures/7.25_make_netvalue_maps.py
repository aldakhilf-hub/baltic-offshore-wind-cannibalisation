"""
7.25_make_netvalue_maps.py — the 'where is it worth building' map: net annual value
of offshore wind per MW, 2025 / 2030 / 2040.

    net value (EUR/MW/yr) = revenue density - annualised cost

revenue density = GWA capacity factor x capture value(year) x today's zone price (7.24).
annualised cost = CAPEX(depth, distance) x CRF + OPEX(distance), a transparent stylised
offshore cost model: CAPEX rises with water depth (GEBCO) and distance to shore, with a
floating-foundation premium beyond 60 m. WACC 7%, 27-yr life (CRF 0.083).

Green = profitable, red = uneconomic. The insight: the profitable area SHRINKS from 2025
to 2040 as cannibalisation erodes revenue, deep/far water falls below the line first.

Output -> results/fig_netvalue_{2025,2030,2040}.png + 10_Presentation/figures/ + netvalue_summary.csv
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
ZONES = ["DE", "NL", "BE", "DK1", "FR", "PL", "EE", "LV", "LT", "DK2"]  # Finland excluded (nuclear outlier)
EXTENT = [-6, 30, 46.5, 63.5]

# ---- stylised offshore cost model (EUR/MW) ----
WACC, LIFE = 0.07, 27
CRF = WACC * (1 + WACC) ** LIFE / ((1 + WACC) ** LIFE - 1)   # ~0.083


def capex(depth, dist):
    base = 1.85e6                                   # modern turbine + array + shallow/near baseline
    fixed = np.where(depth <= 60, 12e3 * np.maximum(depth - 25, 0),
                     12e3 * 35 + 1.00e6 + 6e3 * np.maximum(depth - 60, 0))  # floating > 60 m
    grid = 10e3 * np.maximum(dist - 25, 0)          # export cable beyond 25 km
    return base + fixed + grid


def capex_factor(year):
    # DEA technology-learning trajectory for offshore wind investment (2505 -> 1916 EUR/kW,
    # 2020 -> 2050), normalised to 2025: costs fall ~12% by 2040.
    inv = lambda y: 2505.0 - (2505.0 - 1916.0) * (y - 2020) / 30.0
    return inv(year) / inv(2025)


def crf_year(year):
    n = 27.0 + (30.0 - 27.0) * (year - 2020) / 30.0          # DEA fixed-offshore lifetime 27 -> 30
    return WACC * (1 + WACC) ** n / ((1 + WACC) ** n - 1)


def annual_cost(depth, dist, year):
    # CAPEX scaled by the DEA learning trajectory (cheaper over time) + OPEX
    return capex(depth, dist) * capex_factor(year) * crf_year(year) + (75e3 + 250.0 * dist)


def to_zone(name):
    if name.startswith("DK1"): return "DK1"
    if name.startswith("DK2"): return "DK2"
    return name[:2]


# ---- grids: GWA capacity factor (reference grid), GEBCO depth, distance to shore ----
cf = xr.open_dataarray(OUT / "gwa_cf_field.nc")
m = np.isnan(cf.values); d, (iy, ix) = distance_transform_edt(m, return_indices=True)
cf_grid = np.where(d <= 4, cf.values[iy, ix], np.nan)          # seam-filled resource
LON, LAT = np.meshgrid(cf.x.values, cf.y.values)

geb = xr.open_dataset(GEBCO)["elevation"]
geb = geb.sortby("lat").sortby("lon").interp(lat=cf.y, lon=cf.x)   # onto the GWA grid
elev = geb.values
depth = np.where(elev < 0, -elev, np.nan)                      # m below sea level
sea = (elev < 0)
dlat = 111.0 * abs(float(cf.y[1] - cf.y[0]))                   # km per cell (lat)
dlon = 111.0 * np.cos(np.deg2rad(55)) * abs(float(cf.x[1] - cf.x[0]))
dist_km = distance_transform_edt(sea, sampling=(dlat, dlon))   # distance from sea cell to nearest land

# feasible offshore: has resource, sea, depth <= 1000 m, within 200 km of shore
feasible = np.isfinite(cf_grid) & sea & (depth <= 1000) & (dist_km <= 200)

# nearest modelled zone per cell (value tint)
reg = gpd.read_file(GEO); reg["zone"] = reg["name"].map(to_zone)
reg = reg[reg.zone.isin(ZONES)].copy(); reg["geometry"] = reg.geometry.buffer(0)
cent = reg.dissolve("zone").geometry.representative_point()
zlist = list(cent.index); zxy = np.array([[cent[z].x, cent[z].y] for z in zlist])
_, idx = cKDTree(zxy).query(np.c_[LON.ravel(), LAT.ravel()])
zone_grid = np.array(zlist, dtype=object)[idx].reshape(cf_grid.shape)

tbl = pd.read_csv(OUT / "value_map_table.csv"); tbl["horizon"] = tbl["horizon"].astype(str)
P25 = tbl[tbl.horizon == "2025"].set_index("zone").price_level.to_dict()


def netvalue(hz):
    cost = annual_cost(depth, dist_km, int(hz))       # year-specific cost (learning curve)
    cv = tbl[tbl.horizon == hz].set_index("zone").CV.to_dict()
    cap_price = np.vectorize(lambda z: cv.get(z, np.nan) * P25.get(z, np.nan))(zone_grid)
    revenue = cf_grid * 8760.0 * cap_price            # EUR/MW/yr
    nv = (revenue - cost) / 1000.0                    # k EUR/MW/yr
    return np.where(feasible, nv, np.nan)


TITLES = {"2025": "2025  ·  today", "2030": "2030  ·  build-out underway", "2040": "2040  ·  full build-out"}
rows = []
for hz in ["2025", "2030", "2040"]:
    nv = netvalue(hz)
    prof = np.nansum(nv > 0) / np.sum(feasible) * 100        # profitable share of the buildable shelf
    fig = plt.figure(figsize=(7.6, 5.0))
    ax = fig.add_axes([0.02, 0.155, 0.96, 0.70], projection=ccrs.PlateCarree())
    ax.set_extent(EXTENT, crs=ccrs.PlateCarree())
    mesh = ax.pcolormesh(cf.x.values, cf.y.values, np.ma.masked_invalid(nv),
                         cmap="RdYlGn", vmin=-200, vmax=200, shading="auto",
                         transform=ccrs.PlateCarree(), zorder=1, rasterized=True)
    # break-even line: the build / don't-build threshold an investor reads first
    try:
        ax.contour(cf.x.values, cf.y.values, np.ma.masked_invalid(nv), levels=[0],
                   colors="black", linewidths=1.2, transform=ccrs.PlateCarree(), zorder=4)
    except Exception:
        pass
    ax.add_feature(cfeature.LAND.with_scale("50m"), facecolor="#efece6", zorder=2)
    ax.add_feature(cfeature.COASTLINE.with_scale("50m"), lw=0.4, edgecolor="#888", zorder=3)
    ax.add_feature(cfeature.BORDERS.with_scale("50m"), lw=0.3, edgecolor="#c4c4c4", zorder=3)
    cax = fig.add_axes([0.18, 0.085, 0.64, 0.030])
    cb = fig.colorbar(mesh, cax=cax, orientation="horizontal", extend="both")
    cb.set_label("Net value per MW  (thousand EUR/MW/yr; black line = break-even)", fontsize=9)
    fig.suptitle(f"Net value per MW, {hz}", fontsize=13.5, y=0.96, color="#111")
    fig.savefig(OUT / f"fig_netvalue_{hz}.png", dpi=190)
    plt.close(fig)
    rows.append(dict(year=hz, profitable_area_pct=round(prof, 1),
                     median_netvalue_k=round(float(np.nanmedian(nv)), 1),
                     max_netvalue_k=round(float(np.nanmax(nv)), 1)))
    print(f"saved fig_netvalue_{hz}.png  profitable area {prof:.0f}%  median {np.nanmedian(nv):.0f} k EUR/MW/yr")
pd.DataFrame(rows).to_csv(OUT / "netvalue_summary.csv", index=False)
print("CRF", round(CRF, 4))
