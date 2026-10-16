"""
06_fit_regression.py

W4 fit: the Paul-Jacquet-style capture-value regression for Strand A.

Target : monthly capture value CV (per farm-month).
Features: Paul's 7 system-level variables (Sec 3.3) ->
    1 Corr_VRE  2 Corr_Load  3 VRE_MarketShare  4 Gas_Price
    5 Carbon_Price  6 Flexibility_Index  7 Interconnection_Index

Models (Paul used XGBoost as primary, validated with plain KFold; his projections
do not use the fitted model at all but extrapolate a seasonal/linear trend, see
0_README/Paul's Model/"L - Seasonal decomposition and projection creation.ipynb"):
    - XGBoost          (primary; Paul reports R^2 = 0.84)
    - Polynomial deg-2 (Ridge-stabilised; extrapolatable backup)
    - Linear OLS       (Lina-style control)
    - RandomForest     (completes Paul's algorithm comparison)
    - SVR (RBF)        (ditto; see make_models())

Trained ONLY on operational farms (Paul's design). Planned / under-construction
farms are the projection set (script 07, later), not training data.

Evaluation:
    A. GroupKFold(5) grouped by FARM  -> honest generalisation to unseen farms
       (+ a per-fold R2 spread, and an ex-2022 variant mirroring Paul's
        2022 gas-spike robustness check)
    A3. Leave-one-year-out (LOYO): fit on every other year, predict the held-out
        year. Both Jacquet and Efthymiadou report a multi-year temporal suite;
        LOYO separates "cannot forecast any year" from "cannot cross 2021-22".
    B. NS-train  -> Baltic-test   <-- the core thesis question (basin transfer)
    C. Baltic-train -> NS-test    (symmetric companion)
    Every split also reports signed forecast bias (mean pred - actual), the
    diagnostic the over-statement story needs.

Outputs to results/:
    regression_metrics.csv          all models x all splits (R2 / RMSE / MAE / bias)
    loyo_by_year.csv                leave-one-year-out R2 per held-out year
    feature_importance.csv          XGBoost gain + permutation importance
    xgb_operational.json            trained XGBoost (for the 07 projection step)
    fig_pred_vs_actual_ns_to_baltic.png
    fig_feature_importance.png

Usage:  python 06_fit_regression.py
"""
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from sklearn.model_selection import GroupKFold, KFold, cross_val_predict, cross_val_score
from sklearn.metrics import r2_score, mean_squared_error, mean_absolute_error
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler, PolynomialFeatures
from sklearn.linear_model import Ridge, LinearRegression
from sklearn.ensemble import RandomForestRegressor
from sklearn.svm import SVR
from sklearn.inspection import permutation_importance
import xgboost as xgb

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "results" / "01_model_fit_and_validation"
RESULTS.mkdir(parents=True, exist_ok=True)

FEATURES = [
    "feature_1_Corr_VRE", "feature_2_Corr_Load", "feature_3_VRE_MarketShare",
    "feature_4_Gas_Price", "feature_5_Carbon_Price",
    "feature_6_Flexibility_Index", "feature_7_Interconnection_Index",
]
SHORT = {f: f.split("_", 2)[-1] for f in FEATURES}   # tidy labels for plots
TARGET = "CV"


def make_models():
    """Fresh, unfitted model dict (so each split trains from scratch)."""
    return {
        "XGBoost": xgb.XGBRegressor(
            n_estimators=400, max_depth=4, learning_rate=0.05,
            subsample=0.8, colsample_bytree=0.8, reg_lambda=1.0,
            objective="reg:squarederror", random_state=0, n_jobs=-1),
        "Polynomial(d2)": Pipeline([
            ("scale", StandardScaler()),
            ("poly", PolynomialFeatures(degree=2, include_bias=False)),
            ("ridge", Ridge(alpha=1.0))]),
        "Linear(OLS)": Pipeline([
            ("scale", StandardScaler()),
            ("lin", LinearRegression())]),
        # RandomForest + SVR complete Paul's 6-algorithm comparison table
        "RandomForest": RandomForestRegressor(
            n_estimators=300, max_depth=8, random_state=0, n_jobs=-1),
        "SVR": Pipeline([
            ("scale", StandardScaler()),
            ("svr", SVR(kernel="rbf", C=1.0, epsilon=0.01))]),
    }


def metrics(y_true, y_pred):
    y_true, y_pred = np.asarray(y_true), np.asarray(y_pred)
    return {
        "R2": r2_score(y_true, y_pred),
        "RMSE": float(np.sqrt(mean_squared_error(y_true, y_pred))),
        "MAE": mean_absolute_error(y_true, y_pred),
        # signed forecast bias: >0 means the model predicts capture value too high
        "bias": float(np.mean(y_pred - y_true)),
        "n_test": int(len(y_true)),
    }


def load_training_panel(statuses=("operational", "planned", "under_construction")):
    """The training panel: one row per bidding-zone market observation, i.e. a
    virtual offshore farm at a representative site in each zone, described by the
    seven features and labelled with its monthly capture value (VWF generation x
    observed zonal price).

    Capture value is a property of a zone's prices sampled by a validated
    generation profile, so a zone with observed day-ahead prices is a valid
    observation whether or not an offshore farm operates there: it measures what a
    standard offshore farm at that location would have earned given the zone's
    realised prices. Operational farms (real metered generation) are the
    validation subset; planned and under-construction sites add the five enclosed
    Baltic zones with no operational offshore yet (PL, FI, EE, LV, LT), widening
    the Baltic base from eight farms (four of them German-priced) to fifteen across
    seven enclosed zones. This is strictly more grounded than the 2030/2040
    projection, which applies the same pipeline to unobserved future conditions."""
    sites = pd.read_csv(ROOT / "data/wind_farms_strandA.csv", comment="#")
    status = sites.set_index("name").status.to_dict()
    df = pd.read_csv(ROOT / "data/features_strandA/features_monthly.csv")
    df["status"] = df.farm.map(status)
    df = df[df.status.isin(statuses)].copy()
    df = df.dropna(subset=FEATURES + [TARGET])
    n0 = len(df)
    df = df[(df[TARGET] > 0) & (df[TARGET] < 2)].copy()
    print(f"Training panel: {len(df)} zone-market months ({n0 - len(df)} dropped on CV sanity)")
    for b in ["NS", "Baltic"]:
        s = df[df.basin == b]
        print(f"  {b}: {s.farm.nunique()} sites / {len(s)} months, "
              f"zones {sorted(s.bidding_zone.unique())}")
    return df


def load_operational():
    """The validation subset: operational farms only (real metered generation)."""
    return load_training_panel(statuses=("operational",))


def main():
    df = load_training_panel()
    X, y = df[FEATURES], df[TARGET].values
    groups, basin = df.farm.values, df.basin.values
    rows = []

    # ---- A. GroupKFold(farm) out-of-fold ---------------------------------
    gkf = GroupKFold(n_splits=5)
    ns_to_baltic_pred = None
    oof_xgb = None
    for name, model in make_models().items():
        yhat = cross_val_predict(model, X, y, cv=gkf, groups=groups)
        if name == "XGBoost":
            oof_xgb = yhat
        rows.append({"split": "GroupKFold(farm)", "model": name, **metrics(y, yhat)})

    # per-fold spread of the headline grouped-CV R2 -- stability of the 0.686,
    # the one obvious examiner question about a single pooled out-of-fold number
    gk_scores = cross_val_score(make_models()["XGBoost"], X, y, cv=gkf,
                                groups=groups, scoring="r2")
    print(f"GroupKFold(farm) XGBoost per-fold R2: {np.round(gk_scores, 3).tolist()} "
          f"(mean {gk_scores.mean():.3f} +/- {gk_scores.std():.3f}, "
          f"range [{gk_scores.min():.3f}, {gk_scores.max():.3f}])")

    # ex-2022 robustness (XGBoost only) -- Paul dropped 2022 (gas spike)
    m = df.year != 2022
    yhat22 = cross_val_predict(make_models()["XGBoost"], X[m], y[m],
                               cv=gkf, groups=groups[m])
    rows.append({"split": "GroupKFold(farm), ex-2022", "model": "XGBoost",
                 **metrics(y[m], yhat22)})

    # ---- A2. Paul's protocols, for like-for-like comparison --------------
    # Random K-fold: Paul's metric (leaks farm identity -> optimistic, ~his 0.84).
    # Time-split: train<=2022 / test 2023-24 -> tests TIME generalisation, which
    # is what a projection needs. Negative R2 here = the model does NOT forecast
    # future years on its own (-> PyPSA carries projections).
    rkf = KFold(n_splits=5, shuffle=True, random_state=0)
    for name, model in make_models().items():
        yhat = cross_val_predict(model, X, y, cv=rkf)
        rows.append({"split": "RandomKFold (Paul protocol)", "model": name, **metrics(y, yhat)})
    tr, te = (df.year <= 2022).values, (df.year >= 2023).values
    if te.sum() > 10:
        xgb_t = make_models()["XGBoost"].fit(X[tr], y[tr])
        rows.append({"split": "TimeSplit (train<=2022, test 23-24)", "model": "XGBoost",
                     **metrics(y[te], xgb_t.predict(X[te]))})

    # ---- A3. Leave-one-year-out (LOYO): the strict out-of-time test ------
    # Both predecessors report a three-protocol temporal suite. The single
    # train<=2022 split above conflates two failures: "cannot forecast any
    # year" and "cannot cross the 2021-22 fuel-crisis regime break". LOYO fits
    # on every OTHER year and predicts the held-out one, so a per-year R2 that
    # is negative everywhere strengthens the hand-off to PyPSA, while a failure
    # only across 2022 would localise it to the regime break.
    loyo_rows = []
    for yr in sorted(df.year.unique()):
        tr_y, te_y = (df.year != yr).values, (df.year == yr).values
        if te_y.sum() < 10:
            continue
        m_y = make_models()["XGBoost"].fit(X[tr_y], y[tr_y])
        loyo_rows.append({"year": int(yr), **metrics(y[te_y], m_y.predict(X[te_y]))})
    loyo = pd.DataFrame(loyo_rows)
    loyo.to_csv(RESULTS / "loyo_by_year.csv", index=False)
    rows.append({"split": "LOYO (mean over held-out years)", "model": "XGBoost",
                 "R2": float(loyo.R2.mean()), "RMSE": float(loyo.RMSE.mean()),
                 "MAE": float(loyo.MAE.mean()), "bias": float(loyo.bias.mean()),
                 "n_test": int(loyo.n_test.sum())})

    # ---- B / C. basin transfer ------------------------------------------
    for tr_basin, te_basin in [("NS", "Baltic"), ("Baltic", "NS")]:
        tr, te = basin == tr_basin, basin == te_basin
        for name, model in make_models().items():
            model.fit(X[tr], y[tr])
            yhat = model.predict(X[te])
            rows.append({"split": f"{tr_basin}->{te_basin}", "model": name,
                         **metrics(y[te], yhat)})
            if name == "XGBoost" and tr_basin == "NS":
                ns_to_baltic_pred = (y[te], yhat, df.loc[te, "farm"].values)

    metrics_df = pd.DataFrame(rows)[["split", "model", "R2", "RMSE", "MAE", "bias", "n_test"]]
    metrics_df.to_csv(RESULTS / "regression_metrics.csv", index=False)
    print("\n=== regression metrics ===")
    print(metrics_df.round(3).to_string(index=False))
    print("\n=== leave-one-year-out (XGBoost, strict: predict the held-out year) ===")
    print(loyo.round(3).to_string(index=False))
    print(f"  per-year R2 range [{loyo.R2.min():.3f}, {loyo.R2.max():.3f}], "
          f"mean {loyo.R2.mean():.3f}  (all years out-of-time)")

    # ---- out-of-fold predictions (the honest validation artifact) --------
    # Each farm-month is predicted by an XGBoost that never saw that farm
    # (GroupKFold). 3.01 uses these for the validation triangle's regression
    # column — audit fix: the triangle previously used in-sample values,
    # overstating the independence of the three estimates.
    oof = df[["farm", "country", "bidding_zone", "basin", "year", "month"]].copy()
    oof["CV_actual"] = y
    oof["CV_pred_oof"] = oof_xgb
    oof.to_csv(RESULTS / "oof_predictions_groupkfold.csv", index=False)
    print(f"Saved out-of-fold predictions -> {RESULTS / 'oof_predictions_groupkfold.csv'}")

    # ---- the expanded Baltic, validated out-of-fold ----------------------
    # The model never trained on the zone's site; how well does it predict each
    # enclosed Baltic zone's capture value? The breadth answer to "is it just DK2?"
    enc = oof[(oof.basin == "Baltic") & (oof.bidding_zone != "DE_LU")].copy()
    per_zone = (enc.groupby("bidding_zone")
                .apply(lambda g: pd.Series({
                    "CV_observed": g.CV_actual.mean(), "CV_oof": g.CV_pred_oof.mean(),
                    "abs_err": (g.CV_pred_oof - g.CV_actual).abs().mean(),
                    # signed: >0 means the regression also over-states here, i.e.
                    # whether it co-signs or qualifies PyPSA's congestion bias
                    "signed_err": (g.CV_pred_oof - g.CV_actual).mean(),
                    "n_months": len(g)}), include_groups=False)
                .round(3).reset_index())
    per_zone.to_csv(RESULTS / "enclosed_baltic_oof.csv", index=False)
    print("\n=== enclosed Baltic zones, predicted out-of-fold (model blind to each) ===")
    print(per_zone.to_string(index=False))

    # operational-only baseline, for the panel-expansion before/after
    op = load_operational()
    r2_op = r2_score(op[TARGET].values,
                     cross_val_predict(make_models()["XGBoost"], op[FEATURES],
                                       op[TARGET].values, cv=GroupKFold(5),
                                       groups=op.farm.values))
    print(f"\nLeave-farm-out R2: operational-only {r2_op:.3f}  ->  full panel "
          f"{r2_score(y, oof_xgb):.3f}")

    # ---- feature importance (XGBoost on all operational data) -----------
    xgb_full = make_models()["XGBoost"].fit(X, y)
    xgb_full.save_model(RESULTS / "xgb_operational.json")
    gain = xgb_full.get_booster().get_score(importance_type="gain")
    perm = permutation_importance(xgb_full, X, y, n_repeats=20,
                                  random_state=0, n_jobs=-1)
    imp = pd.DataFrame({
        "feature": [SHORT[f] for f in FEATURES],
        "xgb_gain": [gain.get(f, 0.0) for f in FEATURES],
        "perm_importance": perm.importances_mean,
        "perm_std": perm.importances_std,
    }).sort_values("perm_importance", ascending=False)
    imp.to_csv(RESULTS / "feature_importance.csv", index=False)
    print("\n=== feature importance (XGBoost) ===")
    print(imp.round(4).to_string(index=False))

    # ---- figures ---------------------------------------------------------
    # 1. NS -> Baltic predicted vs actual
    yt, yp, _ = ns_to_baltic_pred
    r2 = r2_score(yt, yp)
    fig, ax = plt.subplots(figsize=(5, 5))
    ax.scatter(yt, yp, s=10, alpha=0.4, color="#1f6f8b")
    lim = [min(yt.min(), yp.min()) - 0.02, max(yt.max(), yp.max()) + 0.02]
    ax.plot(lim, lim, "k--", lw=1)
    ax.set(xlim=lim, ylim=lim, xlabel="Observed CV (Baltic)",
           ylabel="Predicted CV (NS-trained XGBoost)",
           title=f"NS-train -> Baltic-test\nR2 = {r2:.3f}, n = {len(yt)}")
    fig.tight_layout(); fig.savefig(RESULTS / "fig_pred_vs_actual_ns_to_baltic.png", dpi=140)

    # 2. feature importance bar (permutation)
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.barh(imp.feature[::-1], imp.perm_importance[::-1],
            xerr=imp.perm_std[::-1], color="#c06c3e")
    ax.set(xlabel="Permutation importance (Δ R²)",
           title="Paul-feature importance (XGBoost, operational farms)")
    fig.tight_layout(); fig.savefig(RESULTS / "fig_feature_importance.png", dpi=140)

    print(f"\nSaved -> {RESULTS}/  (metrics, importance, xgb_operational.json, 2 figures)")


if __name__ == "__main__":
    main()
