"""
2.14_analytical_projection.py  --  Paul-style forecast as a THIRD cross-check.

The gradient-boosting regression abstains from the future (a tree flat-lines
beyond its training range). Paul's answer was to forecast not with his tree but
with his ANALYTICAL equation, a closed form that can be evaluated outside the
training range. This thesis has the same equation (per-basin, script 2.12), so we
can do exactly what Paul did: feed the equation the projected TYNDP inputs and
read off capture value, then ask whether it agrees with the PyPSA projection.

Inputs reuse the 2.07 TYNDP construction, with two Baltic-specific corrections the
thesis's own mechanism demands and which Jacquet's frozen-feature assumption omits
(his basins do not enclose): the wind-correlation converges to the built-out Baltic
analogue as the zone builds out (space-for-time, measured 0.60 -> 0.81), and the
interconnection UTILISATION declines as VRE outgrows a fixed grid. Freezing these,
as the first cut did, leaves the forecast implausibly flat. Even with them the
analytical still over-shoots PyPSA at 2040 (it cannot produce the convex price
collapse a linear penalty has no term for), which is exactly why the headline is
left to PyPSA. This is a corroboration cross-check, not a headline.

Output -> results/07_analytical_per_basin/analytical_projection.csv + figure.
Run:  ~/miniforge3-arm64/envs/pypsa-eur-arm64/bin/python 2.14_analytical_projection.py
      (or the pypsa-eur env; needs xgboost only via the 2.07 import)
"""
import importlib.util
from pathlib import Path
import numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OUT = ROOT / "results" / "07_analytical_per_basin"
PYPSA = Path(__file__).resolve().parents[2] / "1_PyPSA_Model/results/projections_v3"

def _load(name, fname):
    spec = importlib.util.spec_from_file_location(name, HERE / fname)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m

p7 = _load("proj07", "2.07_project_capture_values.py")   # helpers + TYNDP tables (no __main__ run)
FEAT = p7.FEATURES

# per-basin analytical constants (fitted in 2.12)
con = pd.read_csv(OUT / "analytical_constants.csv")
def consts(basin):
    s = con[con.fit == basin].set_index("constant").value
    return [float(s[k]) for k in ["alpha", "delta", "gamma", "B", "C"]]

def analytical_cv(c, X):
    alpha, delta, gamma, B, C = c
    diff = X.feature_1_Corr_VRE.values - X.feature_2_Corr_Load.values
    modwf = np.sign(diff) * np.abs(diff) ** alpha
    modbzn = np.maximum(X.feature_7_Interconnection_Index.values + X.feature_6_Flexibility_Index.values, 1e-6) ** delta
    fuel = np.maximum(0.202 * X.feature_5_Carbon_Price.values + X.feature_4_Gas_Price.values, 1e-6) ** gamma
    return 1.0 - B * (modwf / modbzn) * X.feature_3_VRE_MarketShare.values - C * modwf * fuel

# ---- replicate 2.07's projected feature construction, per planned farm --------
sites = pd.read_csv(ROOT / "data/wind_farms_strandA.csv", comment="#")
status = sites.set_index("name").status.to_dict()
feat = pd.read_csv(ROOT / "data/features_strandA/features_monthly.csv")
feat["status"] = feat.farm.map(status)
proj = feat[feat.status.isin(["planned", "under_construction"])].copy()
recent = proj[proj.year.isin(p7.RECENT_YEARS)]

# Space-for-time correlation target. Holding the wind-correlation features flat
# (Jacquet's assumption, fine for his non-enclosing basins) contradicts THIS
# thesis's central measured mechanism: an enclosed-Baltic zone's farm-vs-system
# correlation RISES as it builds out. The already-built-out Baltic zones (DK2,
# SE4) sit at corr_VRE ~0.81 today against the under-built ~0.60, so a building-
# out Baltic zone is projected to converge to that built-out analogue by 2040
# (full buildout), linearly from 2024. The North Sea stays flat: it is already
# built out yet spatially diverse (~0.47), so its correlation does not climb.
BO_CORR_VRE = float(feat[feat.bidding_zone.isin(["DK_2", "SE_4"])].feature_1_Corr_VRE.mean())
print(f"space-for-time target corr_VRE (built-out Baltic DK2/SE4): {BO_CORR_VRE:.3f}\n")

rows = []
for farm, g in recent.groupby("farm"):
    country, basin = g.country.iloc[0], g.basin.iloc[0]
    if basin not in ("NS", "Baltic"):
        continue
    mon = g.groupby("month").agg(
        corr_vre=("feature_1_Corr_VRE", "mean"),
        corr_load=("feature_2_Corr_Load", "mean"),
        share=("feature_3_VRE_MarketShare", "mean")).reindex(range(1, 13))
    ic_recent = g[g.year == p7.ANCHOR_YEAR].feature_7_Interconnection_Index.mean()
    if pd.isna(ic_recent):
        ic_recent = g.feature_7_Interconnection_Index.mean()
    base2024 = p7.our_2024_vre(country) or {"solar": 0, "onwind": 0, "offwind": 0}
    vre2024 = sum(base2024.values()); phs2024 = p7.our_2024_phs(country)
    for traj in p7.TRAJECTORIES:
        for year in p7.HORIZONS:
            vre_fut = p7.tyndp_vrecap(country, year, traj, base2024)
            cap_scale = vre_fut / vre2024 if vre2024 > 0 else np.nan
            pen_scale = cap_scale / p7.demand_growth(country, year)
            flex_fut = ((p7.tyndp_battery_power(country, year, traj) + phs2024) / vre_fut
                        if vre_fut > 0 else np.nan)
            gas = float(p7.PRICES.loc[year, "gas_eurMWh"]); co2 = float(p7.PRICES.loc[year, "co2_eurton"])
            # Stop freezing the features the thesis's mechanism says must move as
            # the enclosed basin builds out:
            #  (i) wind-correlation converges to the built-out Baltic analogue
            #      (space-for-time), raising the cannibalisation pattern penalty;
            #  (ii) interconnection UTILISATION declines as VRE outgrows a fixed
            #       grid (ic / cap_scale), weakening the buffer (Efthymiadou's
            #       forward IC/VRE logic; the same conservative bound as 2.07).
            frac = (year - p7.ANCHOR_YEAR) / (2040 - p7.ANCHOR_YEAR)
            if basin == "Baltic":
                corr_vre_proj = np.minimum(
                    mon.corr_vre.values + frac * (BO_CORR_VRE - mon.corr_vre.values),
                    BO_CORR_VRE)
                corr_vre_proj = np.maximum(corr_vre_proj, mon.corr_vre.values)  # only raise
            else:
                corr_vre_proj = mon.corr_vre.values
            ic_proj = ic_recent / cap_scale if (pd.notna(cap_scale) and cap_scale > 0) else ic_recent
            X = pd.DataFrame({
                "feature_1_Corr_VRE": corr_vre_proj,
                "feature_2_Corr_Load": mon.corr_load.values,
                "feature_3_VRE_MarketShare": mon.share.values * pen_scale,
                "feature_4_Gas_Price": gas, "feature_5_Carbon_Price": co2,
                "feature_6_Flexibility_Index": flex_fut,
                "feature_7_Interconnection_Index": ic_proj,
            })[FEAT].dropna()
            if not len(X):
                continue
            cv = float(np.clip(analytical_cv(consts(basin), X), 0.0, 1.1).mean())
            rows.append({"farm": farm, "basin": basin, "trajectory": traj,
                         "horizon": year, "cv_analytical": cv})

ap = pd.DataFrame(rows)
summary = ap.groupby(["basin", "trajectory", "horizon"]).cv_analytical.mean().round(3).reset_index()
summary.to_csv(OUT / "analytical_projection.csv", index=False)
print("=== analytical (Paul-style) projection, basin mean ===")
print(summary.to_string(index=False))

# ---- PyPSA comparison (raw engine) -------------------------------------------
bal = pd.read_csv(PYPSA / "baltic_capture_value_corrected.csv")
pj = pd.read_csv(PYPSA / "projected_capture_values.csv")
NS = {"DE", "NL", "BE", "DK1", "FR"}
def ns_pypsa(scn):
    s = pj[(pj.scenario == scn) & (pj.zone.isin(NS))]
    return float((s.energy_GWh * s.CV).sum() / s.energy_GWh.sum())
pypsa = {
    ("Baltic", 2030): bal[(bal.year == 2030) & (bal.buildout == "baseline")].CV_raw.iloc[0],
    ("Baltic", 2040): bal[(bal.year == 2040) & (bal.buildout == "baseline")].CV_raw.iloc[0],
    ("NS", 2030): ns_pypsa("2030-NT-balticBaseline"),
    ("NS", 2040): ns_pypsa("2040-NT-balticBaseline"),
}
today = {"NS": 0.879, "Baltic": 0.883}

print("\n=== analytical vs PyPSA (BEST / NT-baseline), raw ===")
for basin in ["NS", "Baltic"]:
    a30 = summary[(summary.basin==basin)&(summary.trajectory=="BEST")&(summary.horizon==2030)].cv_analytical
    a40 = summary[(summary.basin==basin)&(summary.trajectory=="BEST")&(summary.horizon==2040)].cv_analytical
    a30 = float(a30.iloc[0]) if len(a30) else float("nan")
    a40 = float(a40.iloc[0]) if len(a40) else float("nan")
    print(f"  {basin:6s}  today {today[basin]:.2f}  |  2030  ana {a30:.2f}  pypsa {pypsa[(basin,2030)]:.2f}"
          f"  |  2040  ana {a40:.2f}  pypsa {pypsa[(basin,2040)]:.2f}")

# ---- figure ------------------------------------------------------------------
fig, ax = plt.subplots(figsize=(8.6, 5.2))
xs = [0, 1, 2]; xl = ["today", "2030", "2040"]
col = {"NS": "#2E6E9E", "Baltic": "#E67E22"}
for basin in ["NS", "Baltic"]:
    a = [today[basin],
         summary[(summary.basin==basin)&(summary.trajectory=="BEST")&(summary.horizon==2030)].cv_analytical.iloc[0],
         summary[(summary.basin==basin)&(summary.trajectory=="BEST")&(summary.horizon==2040)].cv_analytical.iloc[0]]
    p = [today[basin], pypsa[(basin,2030)], pypsa[(basin,2040)]]
    ax.plot(xs, a, "o--", color=col[basin], lw=2, ms=9, alpha=0.9,
            label=f"{basin}: analytical")
    ax.plot(xs, p, "s-", color=col[basin], lw=2.4, ms=9,
            label=f"{basin}: PyPSA (system model)")
ax.set_xticks(xs); ax.set_xticklabels(xl, fontsize=11)
ax.set_ylabel("Capture value (raw)", fontsize=11); ax.set_ylim(0.3, 1.0)
ax.set_title("Analytical form and PyPSA, basin capture value to 2040",
             fontsize=11.5, color="#111")
ax.legend(fontsize=9, ncol=2, loc="lower left")
for s in ["top","right"]: ax.spines[s].set_visible(False)
ax.grid(alpha=0.25)
fig.tight_layout(); fig.savefig(OUT / "fig_analytical_projection.png", dpi=200)
print(f"\nSaved -> {OUT}/analytical_projection.csv + fig_analytical_projection.png")
