"""
7.29_robustness_vlcoe.py — robustness of the value-adjusted-LCOE headline.

Headline 1: vLCOE RISES 2025 -> 2040 (cannibalisation overruns cost learning).
Headline 2: the rise is robust to cost level (WACC, CAPEX, depth/distance), because the
cost level cancels in the ratio vLCOE(2040)/vLCOE(2025) = learning_factor x CV(2025)/CV(2040).
Only an implausibly fast learning rate could flip it; we find the break-even rate.

Outputs: a sensitivity table (WACC x CAPEX x learning) + fig_vlcoe_robustness.png
"""
from pathlib import Path
import warnings
warnings.filterwarnings("ignore")
import numpy as np, pandas as pd, xarray as xr, geopandas as gpd
from scipy.spatial import cKDTree
from scipy.ndimage import distance_transform_edt
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "7_Thesis_Figures" / "results"
DECK = ROOT / "10_Presentation" / "figures"
GEO = Path.home() / "pypsa-eur/resources/faisal-2023/regions_offshore_base_s_30.geojson"
GEBCO = (Path.home() / "pypsa-eur/data/gebco/archive/2014/GEBCO_2014_2D.nc")
ZONES = ["DE", "NL", "BE", "DK1", "FR", "PL", "EE", "LV", "LT", "FI", "DK2"]
REF = 70.0


def to_zone(n):
    return "DK1" if n.startswith("DK1") else "DK2" if n.startswith("DK2") else n[:2]


# grids
cf = xr.open_dataarray(OUT / "gwa_cf_field.nc")
_m = np.isnan(cf.values); _d, (_iy, _ix) = distance_transform_edt(_m, return_indices=True)
cf_grid = np.where(_d <= 4, cf.values[_iy, _ix], np.nan)
LON, LAT = np.meshgrid(cf.x.values, cf.y.values)
geb = xr.open_dataset(GEBCO)["elevation"].sortby("lat").sortby("lon").interp(lat=cf.y, lon=cf.x).values
depth = np.where(geb < 0, -geb, np.nan); sea = geb < 0
dlat = 111 * abs(float(cf.y[1] - cf.y[0])); dlon = 111 * np.cos(np.deg2rad(55)) * abs(float(cf.x[1] - cf.x[0]))
dist_km = distance_transform_edt(sea, sampling=(dlat, dlon))
feasible = np.isfinite(cf_grid) & sea & (depth <= 1000) & (dist_km <= 200)

reg = gpd.read_file(GEO); reg["zone"] = reg["name"].map(to_zone)
reg = reg[reg.zone.isin(ZONES)].copy(); reg["geometry"] = reg.geometry.buffer(0)
cent = reg.dissolve("zone").geometry.representative_point()
zl = list(cent.index); zxy = np.array([[cent[z].x, cent[z].y] for z in zl])
_, idx = cKDTree(zxy).query(np.c_[LON.ravel(), LAT.ravel()])
zone_grid = np.array(zl, dtype=object)[idx].reshape(cf_grid.shape)
tbl = pd.read_csv(OUT / "value_map_table.csv"); tbl["horizon"] = tbl["horizon"].astype(str)


def cv_grid(hz):
    d = tbl[tbl.horizon == hz].set_index("zone").CV.to_dict()
    return np.vectorize(lambda z: d.get(z, np.nan))(zone_grid)


CV25, CV40 = cv_grid("2025"), cv_grid("2040")


def capex(depth, dist, scale):
    base = 1.85e6 * scale
    fixed = np.where(depth <= 60, 12e3 * scale * np.maximum(depth - 25, 0),
                     (12e3 * 35 + 1.00e6) * scale + 6e3 * scale * np.maximum(depth - 60, 0))
    return base + 10e3 * scale * np.maximum(dist - 25, 0) + fixed


def vlcoe_median(year, wacc, scale, learn40, cvg):
    # learn40 = fractional CAPEX decline by 2040 (vs 2025); linear from 2025
    fac = 1.0 - learn40 * (year - 2025) / 15.0
    n = 27.0 + 3.0 * (year - 2020) / 30.0
    crf = wacc * (1 + wacc) ** n / ((1 + wacc) ** n - 1)
    ac = capex(depth, dist_km, scale) * fac * crf + (75e3 + 250.0 * dist_km)
    v = np.where(feasible, (ac / (cf_grid * 8760.0)) / cvg, np.nan)
    return float(np.nanmedian(v)), float(np.nansum(v < REF) / feasible.sum() * 100)


# ---- sensitivity table ----
rows = []
for wacc in (0.05, 0.07, 0.09):
    for scale in (0.8, 1.0, 1.2):
        for learn in (0.05, 0.12, 0.25):
            v25, c25 = vlcoe_median(2025, wacc, scale, learn, CV25)
            v40, c40 = vlcoe_median(2040, wacc, scale, learn, CV40)
            rows.append(dict(WACC=wacc, capex_scale=scale, learning_2040=learn,
                             vlcoe25=round(v25), vlcoe40=round(v40),
                             rises=v40 > v25, comp25=round(c25), comp40=round(c40)))
S = pd.DataFrame(rows); S.to_csv(OUT / "vlcoe_robustness.csv", index=False)
print(f"vLCOE RISES (2040>2025) in {S.rises.sum()}/{len(S)} of all WACC x CAPEX x learning cases")
print(S.groupby("learning_2040").agg(vlcoe25=("vlcoe25", "median"), vlcoe40=("vlcoe40", "median"),
                                     rises=("rises", "all")).to_string())

# ---- break-even learning rate: how fast must costs fall to stop vLCOE rising? ----
cvr = float(np.nanmedian(np.where(feasible, CV40, np.nan)) / np.nanmedian(np.where(feasible, CV25, np.nan)))
breakeven = 1.0 - cvr   # cost must fall by this fraction for vLCOE to merely hold
learns = np.linspace(0, 0.6, 121)
ratio = [vlcoe_median(2040, 0.07, 1.0, L, CV40)[0] / vlcoe_median(2025, 0.07, 1.0, L, CV25)[0] for L in learns]

fig, ax = plt.subplots(figsize=(9, 5.6))
ax.plot(learns * 100, ratio, color="#1b4f72", lw=2.6)
ax.axhline(1.0, color="#888", ls="--", lw=1)
ax.axvspan(0, breakeven * 100, color="#fdedec", alpha=0.6)
ax.axvspan(breakeven * 100, 60, color="#eafaf1", alpha=0.6)
ax.axvline(12, color="#c0392b", ls=":", lw=1.8)
ax.text(12, ax.get_ylim()[1] * 0.96, " DEA projection (12%)", color="#c0392b", fontsize=9, va="top")
ax.text(breakeven * 100, 1.02, f" break-even {breakeven*100:.0f}%", fontsize=9, color="#1e7d34")
ax.text(4, max(ratio) * 0.55, "vLCOE rises", fontsize=10, color="#922b21")
ax.text(45, 0.85, "vLCOE falls", fontsize=10, color="#1e7d34", ha="center")
ax.set_xlabel("Offshore CAPEX decline by 2040 (%)", fontsize=11)
ax.set_ylabel("value-adjusted LCOE  2040 / 2025", fontsize=11)
ax.set_title("Ratio of 2040 to 2025 value-adjusted LCOE against the assumed\n"
             "CAPEX decline", fontsize=12.5, color="#111")
ax.grid(alpha=0.3)
fig.tight_layout()
fig.savefig(OUT / "fig_vlcoe_robustness.png", dpi=190)
print(f"break-even learning rate {breakeven*100:.0f}% (CV ratio 2040/2025 = {cvr:.2f}); DEA is 12%")
print("saved fig_vlcoe_robustness.png")
