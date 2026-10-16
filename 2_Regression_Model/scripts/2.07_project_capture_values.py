"""
07_project_capture_values.py

W5 projection: apply the trained XGBoost capture-value model
(results/xgb_operational.json, from script 06) to TYNDP 2030/2040 conditions
for the PROJECTION-SET farms (planned + under-construction).

Method -- per planned farm, build 12 monthly feature vectors per horizon and
average the predicted CV:

  weather-driven features (held at the farm's recent monthly shape, 2023-2024):
    feature_1 Corr_VRE      -- structural to the site's wind profile
    feature_2 Corr_Load     -- structural

  system features (projected to the horizon, same monthly shape, new level):
    feature_3 VRE_MarketShare  = recent monthly share x penetration-scale,
        where penetration-scale = (TYNDP VRE capacity_future / our installed
        VRE_2024) / demand-growth. Anchored on OBSERVED 2024 penetration and
        scaled by capacity growth -- avoids absolute-CF assumptions and uses
        the TYNDP arm that is fully covered for 2030+2040.
    feature_4 Gas_Price        = TYNDP scenario gas price (annual)
    feature_5 Carbon_Price     = TYNDP scenario CO2 price (annual)
    feature_6 Flexibility_Index = (TYNDP battery power + held PHS_2024) / VRE_future
    feature_7 Interconnection_Index = held at the farm's recent (2024) value
        (TYNDP NTC not parsed; structural grid feature). Since VRE grows, the
        true IC/VRE ratio would FALL, so holding it is mildly OPTIMISTIC for CV.
        A conservative-bound sensitivity (pred_CV_*_icdecl) lets utilisation
        fall with VRE growth (ic_recent / cap_scale), following Efthymiadou's
        forward IC/VRE logic; it bites the linear/poly extrapolation while the
        tree out-of-range rows are unaffected.

Models -- XGBoost CANNOT extrapolate (tree leaves clamp beyond the training
range), so for high-penetration Baltic farms it flatlines at an optimistic
~0.86. We therefore project with THREE models and report the spread:
  - XGBoost        interpolation-bounded -> optimistic UPPER bound out-of-range
  - Linear (OLS)   smooth monotonic extrapolation -> primary extrapolation est.
  - Polynomial d2  Paul's extrapolatable backup (can over-shoot at extreme pen.)
Each projected farm is flagged `in_range` — ALL 7 features within the training
envelope, not just VRE share (audit fix 2026-06-11: TYNDP carbon prices of
113-147 EUR/t lie 25-62% beyond the training maximum of 91 EUR/t, and carbon
is the model's TOP SHAP feature, yet those rows were flagged in-range under
the old VRE-share-only check). `out_of_range_features` names the offenders.
A `joint_in_hull` flag adds the strictly stronger test (Jacquet's convex-hull /
Delaunay idea, generalised to 7-D point-in-hull membership): the per-feature box
passes joint excursions the convex hull rejects, since the hull is a SUBSET of
the box, so a row can sit in every 1-D span yet outside the joint support.
A carbon-clamped sensitivity column (pred_CV_xgb_carbonclamp: carbon clipped
to the training max) quantifies how much of each prediction rides on the
carbon extrapolation. In-range farms: trust XGBoost. Out-of-range (most
Baltic 2040, penetration > 0.83 up to 2.4 for export hubs): quote the
[linear, xgb] range and defer to the PyPSA track -- this is the central
limitation of the empirical regression and exactly why PyPSA is the second
pillar.

Scenarios: capacity trajectory BEST (central NT) primary + HIGH (high-RES)
sensitivity; demand scenario DE (Distributed Energy). Horizons 2030, 2040.

TYNDP gaps handled: demand has 2040 not 2030 (ramped linearly from 2024);
GB demand absent (growth fallback 1.15); missing country x tech capacity cells
held at the 2024 installed level.

Inputs:
  data/features_strandA/features_monthly.csv     (recent feature shape)
  data/wind_farms_strandA.csv                    (status, country, basin)
  data/entsoe_strandA/installed_capacity/        (our 2024 VRE + PHS anchors)
  data/tyndp/parsed_{capacity,demand,prices,batteries}.csv
  ../results... no -> results/xgb_operational.json   (trained model)

Output:
  results/projected_capture_values.csv     per farm x horizon x trajectory
  results/projection_summary.csv           basin x horizon x trajectory means

Usage:  python 07_project_capture_values.py
"""
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb
from scipy.spatial import ConvexHull, QhullError
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler, PolynomialFeatures
from sklearn.linear_model import Ridge, LinearRegression

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "results" / "03_projection_2030_2040"
RESULTS.mkdir(parents=True, exist_ok=True)
TY = ROOT / "data" / "tyndp"
CAP_DIR = ROOT / "data" / "entsoe_strandA" / "installed_capacity"

FEATURES = [
    "feature_1_Corr_VRE", "feature_2_Corr_Load", "feature_3_VRE_MarketShare",
    "feature_4_Gas_Price", "feature_5_Carbon_Price",
    "feature_6_Flexibility_Index", "feature_7_Interconnection_Index",
]
ANCHOR_YEAR = 2024
RECENT_YEARS = [2023, 2024]
HORIZONS = [2030, 2040]
TRAJECTORIES = ["BEST", "HIGH"]
DEMAND_SCENARIO = "DE"

# ---- TYNDP tables ---------------------------------------------------------
CAP = pd.read_csv(TY / "parsed_capacity.csv")
DEM = pd.read_csv(TY / "parsed_demand.csv")
PRICES = pd.read_csv(TY / "parsed_prices.csv").set_index("year")
BAT = pd.read_csv(TY / "parsed_batteries.csv")


def our_installed(country):
    f = CAP_DIR / f"{country}.csv"
    return pd.read_csv(f, index_col=0) if f.exists() else None


def our_2024_vre(country):
    df = our_installed(country)
    if df is None or ANCHOR_YEAR not in df.index:
        return None
    row = df.loc[ANCHOR_YEAR]
    return {t: float(row.get(col, 0.0) or 0.0) for t, col in
            [("solar", "Solar"), ("onwind", "Wind Onshore"), ("offwind", "Wind Offshore")]}


def our_2024_phs(country):
    df = our_installed(country)
    if df is None or ANCHOR_YEAR not in df.index:
        return 0.0
    row = df.loc[ANCHOR_YEAR]
    return float(sum(row[c] for c in df.columns
                     if "Pumped Storage" in c and pd.notna(row[c])))


def tyndp_vrecap(country, year, traj, base2024):
    """Future VRE capacity (MW): TYNDP per tech where present, else held at the
    country's 2024 installed level for that tech."""
    sub = CAP[(CAP.country == country) & (CAP.trajectory == traj) & (CAP.year == year)]
    techs = dict(zip(sub.tech, sub.MW))
    total = 0.0
    for t in ["solar", "onwind", "offwind"]:
        v = techs.get(t)
        total += float(v) if (v is not None and pd.notna(v)) else base2024.get(t, 0.0)
    return total


def tyndp_battery_power(country, year, traj):
    sub = BAT[(BAT.country == country) & (BAT.trajectory == traj) & (BAT.year == year)]
    return float(sub.power_MW.iloc[0]) if len(sub) else 0.0


def demand_growth(country, year):
    """Demand level relative to 2024 (~2019). DE scenario 2040 vs REF 2019;
    2030 ramped linearly; fallback 1.15 if a country lacks demand data."""
    ref = DEM[(DEM.country == country) & (DEM.scenario == "REF") & (DEM.year == 2019)]
    fut = DEM[(DEM.country == country) & (DEM.scenario == DEMAND_SCENARIO) & (DEM.year == 2040)]
    if len(ref) and len(fut) and ref.demand_TWh.iloc[0] > 0:
        g2040 = float(fut.demand_TWh.iloc[0]) / float(ref.demand_TWh.iloc[0])
    else:
        g2040 = 1.15
    if year >= 2040:
        return g2040
    return 1.0 + (g2040 - 1.0) * (year - ANCHOR_YEAR) / (2040 - ANCHOR_YEAR)


def fit_models(op):
    """Fit the three projection models on operational farm-months."""
    X, y = op[FEATURES], op["CV"].values
    xgbm = xgb.XGBRegressor(
        n_estimators=400, max_depth=4, learning_rate=0.05, subsample=0.8,
        colsample_bytree=0.8, reg_lambda=1.0, objective="reg:squarederror",
        random_state=0, n_jobs=-1).fit(X, y)
    poly = Pipeline([("scale", StandardScaler()),
                     ("poly", PolynomialFeatures(2, include_bias=False)),
                     ("ridge", Ridge(alpha=1.0))]).fit(X, y)
    lin = Pipeline([("scale", StandardScaler()),
                    ("lin", LinearRegression())]).fit(X, y)
    return {"xgb": xgbm, "linear": lin, "poly": poly}


def main():
    sites = pd.read_csv(ROOT / "data/wind_farms_strandA.csv", comment="#")
    status = sites.set_index("name").status.to_dict()
    feat = pd.read_csv(ROOT / "data/features_strandA/features_monthly.csv")
    feat["status"] = feat.farm.map(status)

    op = feat[(feat.status == "operational")].dropna(subset=FEATURES + ["CV"])
    op = op[(op.CV > 0) & (op.CV < 2)]
    models = fit_models(op)
    # training envelope for EVERY feature (in_range checks all of them)
    env_lo, env_hi = op[FEATURES].min(), op[FEATURES].max()
    share_lo, share_hi = env_lo.feature_3_VRE_MarketShare, env_hi.feature_3_VRE_MarketShare
    carbon_hi = env_hi.feature_5_Carbon_Price

    # joint-support test: the per-feature box is the axis-aligned bounding box of
    # the training cloud, hence a necessary-not-sufficient condition. The convex
    # hull is a subset of that box, so 7-D point-in-hull membership is a strictly
    # stronger (more conservative) extrapolation guard -- Jacquet's convex-hull /
    # Delaunay diagnostic, here via the hull's half-space inequalities so it scales
    # to 7-D without a Delaunay triangulation.
    _sc = StandardScaler().fit(op[FEATURES].to_numpy())
    try:
        _eq = ConvexHull(_sc.transform(op[FEATURES].to_numpy())).equations

        def in_hull(fv_series):
            p = _sc.transform(fv_series[FEATURES].to_numpy().reshape(1, -1))[0]
            return 1.0 if np.all(_eq[:, :-1] @ p + _eq[:, -1] <= 1e-9) else 0.0
    except QhullError:
        def in_hull(fv_series):   # degenerate hull -> no extra information
            return np.nan
    print(f"Trained on {len(op)} operational rows; training VRE-share span "
          f"[{share_lo:.2f}, {share_hi:.2f}]; carbon span "
          f"[{env_lo.feature_5_Carbon_Price:.1f}, {carbon_hi:.1f}] EUR/t\n")

    proj = feat[feat.status.isin(["planned", "under_construction"])].copy()

    # recent monthly shape (2023-2024 mean) + recent annual anchors, per farm
    recent = proj[proj.year.isin(RECENT_YEARS)]
    rows = []
    for farm, g in recent.groupby("farm"):
        country, basin = g.country.iloc[0], g.basin.iloc[0]
        mon = g.groupby("month").agg(
            corr_vre=("feature_1_Corr_VRE", "mean"),
            corr_load=("feature_2_Corr_Load", "mean"),
            share=("feature_3_VRE_MarketShare", "mean")).reindex(range(1, 13))
        share_recent_annual = mon.share.mean()
        ic_recent = g[g.year == ANCHOR_YEAR].feature_7_Interconnection_Index.mean()
        if pd.isna(ic_recent):
            ic_recent = g.feature_7_Interconnection_Index.mean()
        base2024 = our_2024_vre(country) or {"solar": 0, "onwind": 0, "offwind": 0}
        vre2024 = sum(base2024.values())
        phs2024 = our_2024_phs(country)

        for traj in TRAJECTORIES:
            for year in HORIZONS:
                vre_fut = tyndp_vrecap(country, year, traj, base2024)
                cap_scale = vre_fut / vre2024 if vre2024 > 0 else np.nan
                pen_scale = cap_scale / demand_growth(country, year)
                flex_fut = ((tyndp_battery_power(country, year, traj) + phs2024) / vre_fut
                            if vre_fut > 0 else np.nan)
                gas, co2 = float(PRICES.loc[year, "gas_eurMWh"]), float(PRICES.loc[year, "co2_eurton"])

                share_proj = mon.share.values * pen_scale
                X = pd.DataFrame({
                    "feature_1_Corr_VRE": mon.corr_vre.values,
                    "feature_2_Corr_Load": mon.corr_load.values,
                    "feature_3_VRE_MarketShare": share_proj,
                    "feature_4_Gas_Price": gas,
                    "feature_5_Carbon_Price": co2,
                    "feature_6_Flexibility_Index": flex_fut,
                    "feature_7_Interconnection_Index": ic_recent,
                })[FEATURES].dropna()
                # predict with each model, average over months, clip to physical CV
                preds = {}
                for mname, mdl in models.items():
                    p = float(np.clip(mdl.predict(X), 0.0, 1.1).mean()) if len(X) else np.nan
                    preds[f"pred_CV_{mname}"] = round(p, 3)
                # interconnection-decline sensitivity: let realised utilisation
                # fall with VRE growth (ic / cap_scale), the conservative bound on
                # the flat hold. Tree out-of-range rows are unaffected; this bites
                # the linear/poly extrapolation in the high-penetration Baltic.
                if len(X) and pd.notna(cap_scale) and cap_scale > 0:
                    Xd = X.copy()
                    Xd["feature_7_Interconnection_Index"] = max(ic_recent / cap_scale, 0.0)
                    for mname, mdl in models.items():
                        preds[f"pred_CV_{mname}_icdecl"] = round(
                            float(np.clip(mdl.predict(Xd), 0.0, 1.1).mean()), 3)
                else:
                    for mname in models:
                        preds[f"pred_CV_{mname}_icdecl"] = np.nan
                # carbon-clamped sensitivity: same vector, carbon clipped to the
                # training max — isolates how much rides on carbon extrapolation
                if len(X):
                    Xc = X.copy()
                    Xc["feature_5_Carbon_Price"] = min(co2, carbon_hi)
                    preds["pred_CV_xgb_carbonclamp"] = round(
                        float(np.clip(models["xgb"].predict(Xc), 0.0, 1.1).mean()), 3)
                else:
                    preds["pred_CV_xgb_carbonclamp"] = np.nan
                # in_range: EVERY feature's annual value inside the training
                # envelope (annual mean for the monthly-shaped features)
                ann_share = share_recent_annual * pen_scale
                fv = X.mean()
                fv["feature_3_VRE_MarketShare"] = ann_share
                oor = [f.split("_", 2)[-1] for f in FEATURES
                       if not (env_lo[f] <= fv[f] <= env_hi[f])]
                rows.append({
                    "farm": farm, "country": country, "basin": basin,
                    "status": status.get(farm), "horizon": year, "trajectory": traj,
                    **preds,
                    "in_range": len(oor) == 0,
                    "in_range_vre_only": bool(share_lo <= ann_share <= share_hi),
                    "joint_in_hull": in_hull(fv) if len(X) else np.nan,
                    "out_of_range_features": ";".join(oor),
                    "pen_scale": round(pen_scale, 2),
                    "VRE_share_proj": round(ann_share, 3),
                    "flex_proj": round(flex_fut, 3) if pd.notna(flex_fut) else np.nan,
                    "gas": round(gas, 1), "co2": round(co2, 1),
                })

    out = pd.DataFrame(rows)
    out.to_csv(RESULTS / "projected_capture_values.csv", index=False)

    pcols = ["pred_CV_xgb", "pred_CV_linear", "pred_CV_poly", "pred_CV_xgb_carbonclamp",
             "pred_CV_linear_icdecl", "pred_CV_poly_icdecl"]
    summary = (out.groupby(["trajectory", "horizon", "basin"])[pcols + ["in_range", "joint_in_hull"]]
                  .mean().round(3).reset_index())
    summary.to_csv(RESULTS / "projection_summary.csv", index=False)

    print(f"Projected {out.farm.nunique()} farms x {len(HORIZONS)} horizons x "
          f"{len(TRAJECTORIES)} trajectories = {len(out)} rows")
    print(f"In training range (ALL features): {out.in_range.sum()}/{len(out)}; "
          f"VRE-share-only (old check): {out.in_range_vre_only.sum()}/{len(out)}; "
          f"in 7-D convex hull (stronger): {int(np.nansum(out.joint_in_hull))}/{len(out)}")
    n_carbon = out.out_of_range_features.str.contains("Carbon", na=False).sum()
    print(f"Rows extrapolating on CARBON (top SHAP feature): {n_carbon}/{len(out)} — "
          f"see pred_CV_xgb_carbonclamp for the clamped sensitivity\n")
    print("=== per-farm projected CV, BEST trajectory  [xgb | linear | poly] ===")
    b = out[out.trajectory == "BEST"].sort_values(["basin", "farm", "horizon"])
    for _, r in b.iterrows():
        flag = "" if r.in_range else "  <-- OUT OF RANGE (extrapolation)"
        print(f"  {r.basin:6s} {r.farm:30s} {r.horizon}  "
              f"{r.pred_CV_xgb:.3f} | {r.pred_CV_linear:.3f} | {r.pred_CV_poly:.3f}"
              f"  (pen={r.VRE_share_proj:.2f}){flag}")
    print("\n=== basin-mean projected CV (BEST) ===")
    print(summary[summary.trajectory == "BEST"]
          .pivot_table(index="horizon", columns="basin", values=pcols).round(3).to_string())
    print(f"\nSaved -> {RESULTS}/projected_capture_values.csv + projection_summary.csv")


if __name__ == "__main__":
    main()
