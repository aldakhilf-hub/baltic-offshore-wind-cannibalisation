"""
7.28_make_vlcoe_interconnection.py — how much does interconnection lower the
value-adjusted LCOE? Ties the vLCOE novelty to the grid-reversal / Baltic result.

vLCOE = LCOE / capture value. Interconnection raises capture value (the grid bracket),
so it LOWERS vLCOE. We compute the 2040 vLCOE with the grid FROZEN vs OPTIMALLY
EXPANDED, using per-zone capture value read straight from the solved networks. The
offshore LCOE is identical in both (the grid cost is a separate system investment);
only the capture value, and therefore the break-even price, changes.

Output: fig_vlcoe_grid_2040.png (frozen vs optimal, 2 panels) + vlcoe_grid_summary.csv
"""
import importlib.util, warnings
from pathlib import Path
import numpy as np, pandas as pd, xarray as xr, geopandas as gpd
from scipy.spatial import cKDTree
from scipy.ndimage import distance_transform_edt
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import cartopy.feature as cfeature
warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "7_Thesis_Figures" / "results"
DECK = ROOT / "10_Presentation" / "figures"
GEO = Path.home() / "pypsa-eur/resources/faisal-2023/regions_offshore_base_s_30.geojson"
GEBCO = (Path.home() / "pypsa-eur/data/gebco/archive/2014/GEBCO_2014_2D.nc")
FROZEN = Path.home() / "pypsa-eur/results/scenarios_tyndp_v3/2040-NT-balticBaseline.nc"
VOPT = Path.home() / "pypsa-eur/results/scenarios_tyndp_v3_vopt/2040-NT-balticBaseline.nc"
ZONES = ["DE", "NL", "BE", "DK1", "FR", "PL", "EE", "LV", "LT", "FI", "DK2"]
NS = ["DE", "NL", "BE", "DK1", "FR"]; BAL = ["PL", "EE", "LV", "LT", "FI", "DK2"]
EXTENT = [-6, 30, 46.5, 63.5]; WACC = 0.07; REF = 70.0

spec = importlib.util.spec_from_file_location("sur", ROOT / "1_PyPSA_Model/scripts/1.13_surrogate_runs.py")
sur = importlib.util.module_from_spec(spec); spec.loader.exec_module(sur)
import pypsa


def per_zone_cv(path):
    n = pypsa.Network(path)
    out = {}
    for z in ZONES:
        r = sur.offshore_capture(n, z)
        if r.get("energy_GWh", 0) > 0 and pd.notna(r.get("CV_raw")):
            out[z] = float(r["CV_raw"])
    return out


cv_frozen, cv_opt = per_zone_cv(FROZEN), per_zone_cv(VOPT)
print("per-zone CV 2040 (frozen -> optimal):")
for z in ZONES:
    if z in cv_frozen and z in cv_opt:
        print(f"  {z:4s} {cv_frozen[z]:.2f} -> {cv_opt[z]:.2f}")


def capex(depth, dist):
    base = 1.85e6
    fixed = np.where(depth <= 60, 12e3 * np.maximum(depth - 25, 0),
                     12e3 * 35 + 1.00e6 + 6e3 * np.maximum(depth - 60, 0))
    return base + fixed + 10e3 * np.maximum(dist - 25, 0)


def annual_cost_2040(depth, dist):
    fac = (2505 - (2505 - 1916) * 20 / 30) / (2505 - (2505 - 1916) * 5 / 30)   # 2040 vs 2025 learning
    n = 27 + 3 * 20 / 30; crf = WACC * (1 + WACC) ** n / ((1 + WACC) ** n - 1)
    return capex(depth, dist) * fac * crf + (75e3 + 250.0 * dist)


def to_zone(name):
    return "DK1" if name.startswith("DK1") else "DK2" if name.startswith("DK2") else name[:2]


cf = xr.open_dataarray(OUT / "gwa_cf_field.nc")
_m = np.isnan(cf.values); _d, (_iy, _ix) = distance_transform_edt(_m, return_indices=True)
cf_grid = np.where(_d <= 4, cf.values[_iy, _ix], np.nan)
LON, LAT = np.meshgrid(cf.x.values, cf.y.values)
geb = xr.open_dataset(GEBCO)["elevation"].sortby("lat").sortby("lon").interp(lat=cf.y, lon=cf.x).values
depth = np.where(geb < 0, -geb, np.nan); sea = geb < 0
dlat = 111 * abs(float(cf.y[1] - cf.y[0])); dlon = 111 * np.cos(np.deg2rad(55)) * abs(float(cf.x[1] - cf.x[0]))
dist_km = distance_transform_edt(sea, sampling=(dlat, dlon))
feasible = np.isfinite(cf_grid) & sea & (depth <= 1000) & (dist_km <= 200)
lcoe = annual_cost_2040(depth, dist_km) / (cf_grid * 8760.0)

reg = gpd.read_file(GEO); reg["zone"] = reg["name"].map(to_zone)
reg = reg[reg.zone.isin(ZONES)].copy(); reg["geometry"] = reg.geometry.buffer(0)
cent = reg.dissolve("zone").geometry.representative_point()
zl = list(cent.index); zxy = np.array([[cent[z].x, cent[z].y] for z in zl])
_, idx = cKDTree(zxy).query(np.c_[LON.ravel(), LAT.ravel()])
zone_grid = np.array(zl, dtype=object)[idx].reshape(cf_grid.shape)


def vlcoe(cvmap):
    cvg = np.vectorize(lambda z: cvmap.get(z, np.nan))(zone_grid)
    return np.where(feasible, lcoe / cvg, np.nan)


vf, vo = vlcoe(cv_frozen), vlcoe(cv_opt)
fig, axes = plt.subplots(1, 2, figsize=(13.4, 7.4), subplot_kw={"projection": ccrs.PlateCarree()})
for ax, v, ttl in [(axes[0], vf, "Frozen grid (today's)"), (axes[1], vo, "Optimal grid expansion")]:
    ax.set_extent(EXTENT, crs=ccrs.PlateCarree())
    mesh = ax.pcolormesh(cf.x.values, cf.y.values, np.ma.masked_invalid(v), cmap="RdYlGn_r",
                         vmin=45, vmax=160, shading="auto", transform=ccrs.PlateCarree(), zorder=1, rasterized=True)
    ax.contour(cf.x.values, cf.y.values, np.ma.masked_invalid(v), levels=[REF], colors="black",
               linewidths=1.0, linestyles="--", transform=ccrs.PlateCarree(), zorder=4)
    ax.add_feature(cfeature.LAND.with_scale("50m"), facecolor="#efece6", zorder=2)
    ax.add_feature(cfeature.COASTLINE.with_scale("50m"), lw=0.4, edgecolor="#888", zorder=3)
    ax.add_feature(cfeature.BORDERS.with_scale("50m"), lw=0.3, edgecolor="#c4c4c4", zorder=3)
    ax.set_title(ttl, fontsize=12.5, color="#111")
cax = fig.add_axes([0.3, 0.07, 0.4, 0.02])
fig.colorbar(mesh, cax=cax, orientation="horizontal", extend="both").set_label(
    "Value-adjusted LCOE  (EUR/MWh; dashed contour at 70)", fontsize=9)
fig.suptitle("Value-adjusted LCOE in 2040 under the frozen and optimal grids",
             fontsize=13.5, y=0.97, color="#111")
fig.subplots_adjust(left=0.01, right=0.99, top=0.90, bottom=0.12, wspace=0.04)
fig.savefig(OUT / "fig_vlcoe_grid_2040.png", dpi=190)
plt.close(fig)

# quantify by basin
def basin_med(v, zs):
    mask = feasible & np.isin(zone_grid.astype(str), zs)
    return float(np.nanmedian(np.where(mask, v, np.nan)))
rows = []
GROUPS = [("Core North Sea (DE,NL,BE)", ["DE", "NL", "BE"]),
          ("Enclosed Baltic (PL,EE,LV,LT)", ["PL", "EE", "LV", "LT"]),
          ("Danish transit (DK1,DK2)", ["DK1", "DK2"])]
for nm, zs in GROUPS:
    rows.append(dict(group=nm, vlcoe_frozen=round(basin_med(vf, zs), 0), vlcoe_optimal=round(basin_med(vo, zs), 0),
                     reduction=round(basin_med(vf, zs) - basin_med(vo, zs), 0)))
T = pd.DataFrame(rows); T.to_csv(OUT / "vlcoe_grid_summary.csv", index=False)
print(T.to_string(index=False))
print(f"competitive (<{REF:.0f}) frozen {np.nansum(vf < REF) / feasible.sum() * 100:.0f}% "
      f"-> optimal {np.nansum(vo < REF) / feasible.sum() * 100:.0f}%")
print("saved fig_vlcoe_grid_2040.png")
