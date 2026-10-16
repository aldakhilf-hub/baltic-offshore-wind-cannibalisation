"""
7.32_make_site_ranking.py -- Objective 4 test: does adding capture value change the
RANKING of candidate offshore development areas, 2025 / 2030 / 2040?

Candidate areas = the 10 offshore bidding-zone development areas (Finland excluded).
For each, the representative buildable site = the MEDIAN feasible cell (GWA capacity
factor, GEBCO depth, distance to shore). Two rankings per horizon:
  - COST only:      LCOE (resource + cost, the standard GIS metric, no value)
  - VALUE-adjusted: value-adjusted LCOE = LCOE / capture value (adds the value dimension)
The difference between the rankings IS the effect of the capture-value dimension.
Spearman(cost-rank, value-rank) per horizon measures how much it reorders things.

This step is the analysis + printout; figures follow once the result is verified.
"""
from pathlib import Path
import warnings
warnings.filterwarnings("ignore")
import numpy as np, pandas as pd, xarray as xr, geopandas as gpd
from scipy.spatial import cKDTree
from scipy.ndimage import distance_transform_edt
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "7_Thesis_Figures" / "results"
GEO = Path.home() / "pypsa-eur/resources/faisal-2023/regions_offshore_base_s_30.geojson"
GEBCO = (Path.home() / "pypsa-eur/data/gebco/archive/2014/GEBCO_2014_2D.nc")
ZONES = ["DE", "NL", "BE", "DK1", "FR", "PL", "EE", "LV", "LT", "DK2"]   # Finland excluded
NAME = {"DE": "German Bight", "NL": "Dutch North Sea", "BE": "Belgian", "DK1": "Danish North Sea",
        "FR": "French", "PL": "Polish Baltic", "EE": "Estonian", "LV": "Latvian",
        "LT": "Lithuanian", "DK2": "Danish Baltic (DK2)"}
WACC = 0.07


def capex(depth, dist):
    base = 1.85e6
    fixed = np.where(depth <= 60, 12e3 * np.maximum(depth - 25, 0),
                     12e3 * 35 + 1.00e6 + 6e3 * np.maximum(depth - 60, 0))
    return base + fixed + 10e3 * np.maximum(dist - 25, 0)


def capex_factor(year):
    inv = lambda y: 2505.0 - (2505.0 - 1916.0) * (y - 2020) / 30.0
    return inv(year) / inv(2025)


def crf_year(year):
    n = 27.0 + 3.0 * (year - 2020) / 30.0
    return WACC * (1 + WACC) ** n / ((1 + WACC) ** n - 1)


def annual_cost(depth, dist, year):
    return capex(depth, dist) * capex_factor(year) * crf_year(year) + (75e3 + 250.0 * dist)


def to_zone(n):
    return "DK1" if n.startswith("DK1") else "DK2" if n.startswith("DK2") else n[:2]


# ---- fields ----
cf = xr.open_dataarray(OUT / "gwa_cf_field.nc")
m = np.isnan(cf.values); d, (iy, ix) = distance_transform_edt(m, return_indices=True)
cf_grid = np.where(d <= 4, cf.values[iy, ix], np.nan)
LON, LAT = np.meshgrid(cf.x.values, cf.y.values)
geb = xr.open_dataset(GEBCO)["elevation"].sortby("lat").sortby("lon").interp(lat=cf.y, lon=cf.x).values
depth = np.where(geb < 0, -geb, np.nan); sea = geb < 0
dlat = 111.0 * abs(float(cf.y[1] - cf.y[0])); dlon = 111.0 * np.cos(np.deg2rad(55)) * abs(float(cf.x[1] - cf.x[0]))
dist_km = distance_transform_edt(sea, sampling=(dlat, dlon))
feasible = np.isfinite(cf_grid) & sea & (depth <= 1000) & (dist_km <= 200)

reg = gpd.read_file(GEO); reg["zone"] = reg["name"].map(to_zone)
reg = reg[reg.zone.isin(ZONES)].copy(); reg["geometry"] = reg.geometry.buffer(0)
cent = reg.dissolve("zone").geometry.representative_point()
zl = list(cent.index); zxy = np.array([[cent[z].x, cent[z].y] for z in zl])
_, idx = cKDTree(zxy).query(np.c_[LON.ravel(), LAT.ravel()])
zone_grid = np.array(zl, dtype=object)[idx].reshape(cf_grid.shape)

tbl = pd.read_csv(OUT / "value_map_table.csv"); tbl["horizon"] = tbl["horizon"].astype(str)

# ---- per-area representative (median feasible cell) ----
base = {}
for z in ZONES:
    msk = feasible & (zone_grid.astype(str) == z)
    if msk.sum() == 0:
        continue
    base[z] = dict(CF=float(np.nanmedian(cf_grid[msk])), depth=float(np.nanmedian(depth[msk])),
                   dist=float(np.nanmedian(dist_km[msk])), n_cells=int(msk.sum()))
B = pd.DataFrame(base).T

# ---- per horizon: LCOE (cost) and vLCOE (cost+value), then two rankings ----
rank_tables = {}
spear = {}
for hz in ["2025", "2030", "2040"]:
    cv = tbl[tbl.horizon == hz].set_index("zone").CV.to_dict()
    rows = []
    for z in B.index:
        ac = annual_cost(B.loc[z, "depth"], B.loc[z, "dist"], int(hz))
        lcoe = ac / (B.loc[z, "CF"] * 8760.0)
        c = cv.get(z, np.nan)
        rows.append(dict(zone=z, area=NAME[z], CF=round(B.loc[z, "CF"], 3),
                         depth=round(B.loc[z, "depth"]), dist=round(B.loc[z, "dist"]),
                         CV=round(c, 3), LCOE=round(lcoe, 1), vLCOE=round(lcoe / c, 1)))
    R = pd.DataFrame(rows).dropna(subset=["CV", "vLCOE"]).reset_index(drop=True)  # need a CV that horizon
    R["rank_cost"] = R.LCOE.rank().astype(int)            # lower LCOE = better
    R["rank_value"] = R.vLCOE.rank().astype(int)          # lower vLCOE = better
    R["move"] = R.rank_cost - R.rank_value                 # +ve = rises when value added
    rho = spearmanr(R.rank_cost, R.rank_value).correlation
    spear[hz] = rho
    rank_tables[hz] = R.sort_values("rank_value")
    print(f"\n===== {hz}  (Spearman cost-vs-value rank = {rho:.3f}) =====")
    print(rank_tables[hz][["area", "CF", "CV", "LCOE", "vLCOE", "rank_cost", "rank_value", "move"]].to_string(index=False))

print("\n=== OBJECTIVE-4 TEST: how much does capture value reorder the ranking? ===")
for hz in ["2025", "2030", "2040"]:
    R = rank_tables[hz]
    movers = R[R.move.abs() >= 2]
    print(f"  {hz}: rank correlation {spear[hz]:.2f}; sites moving >=2 places: "
          + (", ".join(f"{r.area} ({'+' if r.move>0 else ''}{r.move})" for _, r in movers.iterrows()) or "none"))

# save the merged ranking table
allr = pd.concat([rank_tables[h].assign(horizon=h) for h in ["2025", "2030", "2040"]])
allr.to_csv(OUT / "site_ranking.csv", index=False)
print(f"\nsaved site_ranking.csv ({len(allr)} rows)")

# ---- recommendation ----
print("\n=== RECOMMENDATION (top value-adjusted areas per horizon) ===")
for hz in ["2025", "2030", "2040"]:
    top = rank_tables[hz].head(3).area.tolist()
    print(f"  {hz}: " + " > ".join(top))

# ---------------- figure: the reorder (cost rank -> value rank) ----------------
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
DECK = ROOT / "10_Presentation" / "figures"
NS = {"DE", "NL", "BE", "DK1", "FR"}
fig, axes = plt.subplots(1, 3, figsize=(13.6, 6.6), sharey=True)
for ax, hz in zip(axes, ["2025", "2030", "2040"]):
    R = rank_tables[hz]
    for _, r in R.iterrows():
        col = "#2471a3" if r.zone in NS else "#c0392b"
        big = abs(r.move) >= 2
        ax.plot([0, 1], [r.rank_cost, r.rank_value], "-o", color=col,
                lw=2.8 if big else 1.2, ms=6 if big else 4, alpha=0.95 if big else 0.5, zorder=3 if big else 2)
        ax.text(1.05, r.rank_value, r.area + (f"  ({'+' if r.move>0 else ''}{r.move})" if big else ""),
                va="center", fontsize=8, color=col, fontweight="bold" if big else "normal")
    ax.set_xlim(-0.08, 1.75); ax.set_xticks([0, 1])
    ax.set_xticklabels(["rank by\ncost (LCOE)", "rank by\nvalue (vLCOE)"], fontsize=9.5)
    ax.set_title(f"{hz}\nrank agreement {spear[hz]:.2f}", fontsize=12, color="#111")
    ax.grid(axis="y", alpha=0.2)
    for s in ["top", "right", "bottom"]: ax.spines[s].set_visible(False)
axes[0].set_ylabel("rank   (1 = best site to build)", fontsize=10.5)
axes[0].invert_yaxis()
fig.suptitle("Candidate-area ranking by cost and by value-adjusted cost",
             fontsize=13.5, y=0.99, color="#111")
fig.tight_layout(rect=[0, 0, 1, 0.95])
fig.savefig(OUT / "fig_site_ranking.png", dpi=190)
plt.close(fig)
print("saved fig_site_ranking.png")

# ---------------- figure: the grid backing (areas ranked on the value field, 2040) ----------------
import matplotlib.patheffects as pe
import cartopy.crs as ccrs, cartopy.feature as cfeature
HALO = [pe.withStroke(linewidth=2.6, foreground="white")]
cv40 = tbl[tbl.horizon == "2040"].set_index("zone").CV.to_dict()
cvg = np.vectorize(lambda z: cv40.get(z, np.nan))(zone_grid)
lcoe40 = annual_cost(depth, dist_km, 2040) / (cf_grid * 8760.0)
vlcoe40 = np.where(feasible, lcoe40 / cvg, np.nan)         # value-adjusted LCOE field
R40 = rank_tables["2040"].set_index("zone")
fig = plt.figure(figsize=(8.2, 5.3))
ax = fig.add_axes([0.02, 0.15, 0.96, 0.72], projection=ccrs.PlateCarree())
ax.set_extent([-6, 30, 46.5, 63.5], crs=ccrs.PlateCarree())
mesh = ax.pcolormesh(cf.x.values, cf.y.values, np.ma.masked_invalid(vlcoe40), cmap="RdYlGn_r",
                     vmin=45, vmax=160, shading="auto", transform=ccrs.PlateCarree(), zorder=1, rasterized=True)
ax.add_feature(cfeature.LAND.with_scale("50m"), facecolor="#efece6", zorder=2)
ax.add_feature(cfeature.COASTLINE.with_scale("50m"), lw=0.4, edgecolor="#888", zorder=3)
ax.add_feature(cfeature.BORDERS.with_scale("50m"), lw=0.3, edgecolor="#c4c4c4", zorder=3)
for z in ZONES:
    if z not in R40.index:
        continue
    pt = cent[z]; rk = int(R40.loc[z, "rank_value"])
    col = "#1b4f72" if z in NS else "#7b241c"
    ax.scatter([pt.x], [pt.y], s=460, color="white", edgecolor=col, linewidth=2.2, zorder=5, transform=ccrs.PlateCarree())
    ax.text(pt.x, pt.y, str(rk), ha="center", va="center", fontsize=11, fontweight="bold", color=col, zorder=6, transform=ccrs.PlateCarree())
    ax.text(pt.x, pt.y - 0.55, NAME[z], ha="center", va="top", fontsize=7.4, color="#222", zorder=6,
            path_effects=HALO, transform=ccrs.PlateCarree())
cax = fig.add_axes([0.18, 0.075, 0.64, 0.028])
fig.colorbar(mesh, cax=cax, orientation="horizontal", extend="both").set_label(
    "Value-adjusted LCOE 2040  (EUR/MWh)", fontsize=9)
fig.suptitle("Candidate areas ranked on the value-adjusted cost field, 2040", fontsize=13.5, y=0.955, color="#111")
fig.savefig(OUT / "fig_site_ranking_map.png", dpi=185)
plt.close(fig)
print("saved fig_site_ranking_map.png")

# ================= MANY SITES + TWO METRICS =================
# ~40 candidate sites on a coarse grid over the feasible shelf; rank by BOTH
#   value-for-money  = value-adjusted LCOE  (lower better)
#   absolute money   = net value per MW     (higher better)
P25 = tbl[tbl.horizon == "2025"].set_index("zone").price_level.to_dict()
glon = np.arange(-5.0, 29.5, 1.25); glat = np.arange(47.0, 62.6, 0.78)
sites = []
for la in glat:
    iy = int(np.argmin(np.abs(cf.y.values - la)))
    for lo in glon:
        ix = int(np.argmin(np.abs(cf.x.values - lo)))
        if not feasible[iy, ix]:
            continue
        z = str(zone_grid[iy, ix])
        if z not in ZONES:
            continue
        sites.append(dict(lon=float(cf.x.values[ix]), lat=float(cf.y.values[iy]), zone=z,
                          CF=float(cf_grid[iy, ix]), depth=float(depth[iy, ix]), dist=float(dist_km[iy, ix])))
S = pd.DataFrame(sites)
print(f"\n=== {len(S)} candidate sites on the grid ({S.zone.value_counts().to_dict()}) ===")

reorder = {}
for hz in ["2025", "2030", "2040"]:
    cvm = tbl[tbl.horizon == hz].set_index("zone").CV.to_dict()
    S[f"cv_{hz}"] = S.zone.map(cvm)
    ac = annual_cost(S.depth.values, S.dist.values, int(hz))
    lcoe = ac / (S.CF.values * 8760.0)
    S[f"lcoe_{hz}"] = lcoe
    S[f"vlcoe_{hz}"] = lcoe / S[f"cv_{hz}"]
    price = S.zone.map(P25)
    S[f"nv_{hz}"] = (S.CF.values * 8760.0 * S[f"cv_{hz}"] * price - ac) / 1000.0   # k EUR/MW/yr
    valid = S.dropna(subset=[f"vlcoe_{hz}"])
    rho_v = spearmanr(valid[f"lcoe_{hz}"].rank(), valid[f"vlcoe_{hz}"].rank()).correlation
    rho_n = spearmanr(valid[f"lcoe_{hz}"].rank(), (-valid[f"nv_{hz}"]).rank()).correlation
    reorder[hz] = (rho_v, rho_n)
S.to_csv(OUT / "site_ranking_grid.csv", index=False)
print("reorder vs cost-only ranking (Spearman; 1.0 = no change):")
for hz in ["2025", "2030", "2040"]:
    print(f"  {hz}: value-adjusted LCOE {reorder[hz][0]:.2f}   net value {reorder[hz][1]:.2f}")

# ---- two-metric map (2040), coloured by rank-percentile so the two views' winners stand out ----
fig, axes = plt.subplots(1, 2, figsize=(13.8, 4.7), subplot_kw={"projection": ccrs.PlateCarree()})
panels = [("vlcoe_2040", "Value-adjusted LCOE", True),
          ("nv_2040", "Net value per MW", False)]
for ax, (col, ttl, low_better) in zip(axes, panels):
    ax.set_extent([-6, 30, 46.5, 63.5], crs=ccrs.PlateCarree())
    ax.add_feature(cfeature.OCEAN.with_scale("50m"), facecolor="#eef3f7")
    ax.add_feature(cfeature.LAND.with_scale("50m"), facecolor="#efece6")
    ax.add_feature(cfeature.COASTLINE.with_scale("50m"), lw=0.4, edgecolor="#999")
    pct = S[col].rank(pct=True)
    score = (1.0 - pct) if low_better else pct          # 1 = best site under this metric
    sc = ax.scatter(S.lon, S.lat, c=score * 100, cmap="RdYlGn", vmin=0, vmax=100, s=62,
                    edgecolor="#333", linewidth=0.4, zorder=5, transform=ccrs.PlateCarree())
    top = S.nsmallest(5, col) if low_better else S.nlargest(5, col)
    for r, (_, s) in enumerate(top.iterrows(), 1):
        ax.scatter([s.lon], [s.lat], s=150, facecolor="none", edgecolor="black", linewidth=1.4, zorder=6, transform=ccrs.PlateCarree())
        ax.text(s.lon, s.lat - 0.5, str(r), ha="center", va="top", fontsize=8.5, fontweight="bold",
                color="black", zorder=7, transform=ccrs.PlateCarree())
    ax.set_title(ttl, fontsize=11.5, color="#111")
    cb = fig.colorbar(sc, ax=ax, orientation="horizontal", pad=0.03, fraction=0.045)
    cb.set_label("site rank percentile  (100 = best)", fontsize=8.5)
fig.suptitle(f"Ranking of {len(S)} candidate sites under the two metrics, 2040",
             fontsize=13, y=0.97, color="#111")
fig.subplots_adjust(top=0.88, bottom=0.03, left=0.02, right=0.98, wspace=0.06)
fig.savefig(OUT / "fig_site_ranking_2metric.png", dpi=180, bbox_inches="tight")
plt.close(fig)
print("saved fig_site_ranking_2metric.png")
