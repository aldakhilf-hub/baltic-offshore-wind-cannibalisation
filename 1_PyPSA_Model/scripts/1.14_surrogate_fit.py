"""
1.14_surrogate_fit.py  ·  TRACK 1 — Surrogate emulator, step 3 of 4

Train the XGBoost surrogate that emulates the validated PyPSA model: given the
8 inputs (+ zone, year) it predicts per-zone offshore capture value and mean
wholesale price in milliseconds, instead of a ~2 min (3-hourly) Gurobi solve.

Training data = run_outputs.csv from 1.13 (harvested ~20 full-res canonical/gas-
shock runs + ~50 freshly-solved 3-hourly LHS runs), long format, one row per
(run_id, zone).

Features (all MEASURED from the solved network, so harvested and solved rows are
consistent):
  gas, co2, dem_mult         the knobs as set
  realized_{baltic_off,ns_off,solar,batt,h2}   realized GW (potential-bounded)
  year                       2030 / 2040
  zone                       one-hot (DE, NL, ... PL, FI, EE, LV, LT, DK1, DK2)

Targets (one XGBoost regressor each):
  CV     = CV_corr   (Baltic = DK2-bias-corrected; NS = raw, where PyPSA is
                      validated accurate — the correction is applied BEFORE
                      training, per the design decision)
  price  = mean_price (zone annual mean wholesale price)

Validation = GROUPED by run_id (GroupKFold). All zones of one PyPSA run share a
fold, so the model is always tested on scenarios it has never seen — this is the
leak-safe analogue of "held-out scenario" and the honest measure of surrogate
skill. We also report a polynomial-regression baseline (Paul-style) and the
anchor check: how well held-out predictions reproduce the 5 canonical scenarios.

Outputs (../results/surrogate/):
  surrogate_cv.json / surrogate_price.json   trained boosters
  surrogate_metrics.csv                       R2 / MAE (overall + per zone)
  surrogate_anchor_check.csv                  predicted vs actual at canonical scenarios
  fig_surrogate_fit.png                        predicted vs actual scatter
  fig_shap_cv.png                              SHAP importance for the CV model

Usage:
  python 1.14_surrogate_fit.py
"""
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import GroupKFold

RES = Path(__file__).resolve().parent.parent / "results" / "surrogate"
LONG = RES / "run_outputs.csv"

INPUTS = ["gas", "co2", "dem_mult",
          "realized_baltic_off", "realized_ns_off", "realized_solar",
          "realized_batt", "realized_h2", "year"]
XGB_PARAMS = dict(n_estimators=400, max_depth=4, learning_rate=0.05,
                  subsample=0.85, colsample_bytree=0.85, reg_lambda=1.0,
                  min_child_weight=3, objective="reg:squarederror")
ANCHORS = ["2030-NT-balticBaseline", "2030-NT-balticHigh", "2040-NT-balticBaseline",
           "2040-NT-balticHigh", "2040-DE-balticHigh", "2040-GA-balticHigh"]


def build_xy(df, target):
    """Feature matrix (8 inputs + year + one-hot zone) and target, dropping NaNs."""
    d = df.dropna(subset=[target]).copy()
    zone_oh = pd.get_dummies(d["zone"], prefix="zone")
    X = pd.concat([d[INPUTS].reset_index(drop=True),
                   zone_oh.reset_index(drop=True)], axis=1).astype(float)
    y = d[target].reset_index(drop=True).astype(float)
    groups = d["run_id"].reset_index(drop=True)
    return X, y, groups, d.reset_index(drop=True)


def grouped_cv(X, y, groups, n_splits=5):
    """Out-of-fold predictions with GroupKFold (no run_id in both train & test)."""
    ng = groups.nunique()
    n_splits = min(n_splits, ng)
    oof = np.full(len(y), np.nan)
    gkf = GroupKFold(n_splits=n_splits)
    for tr, te in gkf.split(X, y, groups):
        m = xgb.XGBRegressor(**XGB_PARAMS)
        m.fit(X.iloc[tr], y.iloc[tr])
        oof[te] = m.predict(X.iloc[te])
    return oof


def poly_baseline_cv(X, y, groups, n_splits=5):
    """Degree-2 polynomial (ridge) baseline on the numeric inputs only."""
    from sklearn.linear_model import Ridge
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import PolynomialFeatures, StandardScaler
    n_splits = min(n_splits, groups.nunique())
    oof = np.full(len(y), np.nan)
    Xn = X[[c for c in INPUTS]]
    for tr, te in GroupKFold(n_splits=n_splits).split(Xn, y, groups):
        pipe = make_pipeline(StandardScaler(), PolynomialFeatures(2),
                             Ridge(alpha=1.0))
        pipe.fit(Xn.iloc[tr], y.iloc[tr])
        oof[te] = pipe.predict(Xn.iloc[te])
    return oof


def fit_and_eval(df, target, label):
    X, y, groups, d = build_xy(df, target)
    print(f"\n=== {label}  (target={target}, n={len(y)}, runs={groups.nunique()}) ===")
    oof = grouped_cv(X, y, groups)
    poly = poly_baseline_cv(X, y, groups)
    mask = ~np.isnan(oof)
    r2 = r2_score(y[mask], oof[mask]); mae = mean_absolute_error(y[mask], oof[mask])
    r2p = r2_score(y[mask], poly[mask])
    print(f"  XGBoost  grouped-CV R²={r2:.3f}  MAE={mae:.3f}")
    print(f"  Poly(2)  grouped-CV R²={r2p:.3f}   (complexity baseline)")

    # per-zone R²
    d = d.assign(pred=oof)
    per_zone = (d.dropna(subset=["pred"]).groupby("zone")
                .apply(lambda g: r2_score(g[target], g.pred) if len(g) > 3 else np.nan)
                .rename("R2").reset_index())
    per_zone["target"] = target

    # final model on all data (for downstream use in 1.15)
    model = xgb.XGBRegressor(**XGB_PARAMS).fit(X, y)

    metrics = dict(target=target, label=label, n=len(y), runs=int(groups.nunique()),
                   xgb_R2=r2, xgb_MAE=mae, poly_R2=r2p)
    return model, X, y, d.assign(pred=oof), per_zone, metrics


def main():
    if not LONG.exists():
        raise SystemExit(f"missing {LONG} -- run 1.13 first (harvest + solve).")
    df = pd.read_csv(LONG)
    print(f"Loaded {len(df)} (run_id, zone) rows from {df.run_id.nunique()} runs "
          f"({df[df.kind=='harvest'].run_id.nunique()} harvested + "
          f"{df[df.kind!='harvest'].run_id.nunique()} solved).")

    # Baltic bias correction for the training target, parsed from the CANONICAL
    # 1.09 fit (fit_metadata.txt) exactly as 1.18 does — single source of truth,
    # no hardcoded constants (2026-06-12 fix: previously baked-in stale values
    # A=-0.005, B=0.399, clamp 0.38 from a pre-canonical fit). Clamping bounds
    # the correction to the validated penetration range against the extreme
    # export-hub penetrations (>100%) the LHS explores; CV floored at 0. North
    # Sea stays raw (PyPSA validated accurate there). This is the training target.
    import re
    meta = (RES.parent / "projections_v3" / "fit_metadata.txt").read_text()
    A, B = map(float, re.search(
        r"bias = ([+-][0-9.]+) \+ \+?([0-9.]+) \* pen", meta).groups())
    PEN_VALID_MAX = float(re.search(r"penetration clamp: ([0-9.]+)", meta).group(1))
    print(f"  bias fit from fit_metadata.txt: bias = {A:+.4f} + {B:.4f}*pen, "
          f"clamp {PEN_VALID_MAX:.3f}")
    is_baltic = df.region == "Baltic"
    bias_clamped = A + B * df.penetration.clip(upper=PEN_VALID_MAX)
    n_extrap = int((is_baltic & (df.penetration > PEN_VALID_MAX)).sum())
    df["CV_corr"] = df.CV_raw.where(~is_baltic, df.CV_raw - bias_clamped).clip(lower=0.0)
    print(f"  Bias correction: clamped penetration at {PEN_VALID_MAX:.0%} "
          f"({n_extrap} Baltic rows beyond validation range), CV floored at 0.")

    cv_model, Xcv, ycv, cv_oof, cv_pz, cv_m = fit_and_eval(df, "CV_corr", "Capture value")
    pr_model, Xpr, ypr, pr_oof, pr_pz, pr_m = fit_and_eval(df, "mean_price", "Wholesale price")

    # ----- persist models + metrics -----
    cv_model.save_model(RES / "surrogate_cv.json")
    pr_model.save_model(RES / "surrogate_price.json")
    pd.DataFrame([cv_m, pr_m]).to_csv(RES / "surrogate_metrics.csv", index=False)
    pd.concat([cv_pz, pr_pz]).to_csv(RES / "surrogate_metrics_per_zone.csv", index=False)
    print(f"\nSaved models + metrics -> {RES}")

    # ----- anchor check: out-of-fold predictions at the canonical scenarios -----
    anc = cv_oof[cv_oof.run_id.isin(ANCHORS)].copy()
    if len(anc):
        anc_summary = (anc.groupby(["run_id"])
                       .apply(lambda g: pd.Series({
                           "CV_actual_balticmean": g[g.region == "Baltic"].CV_corr.mean(),
                           "CV_pred_balticmean": g[g.region == "Baltic"].pred.mean()}))
                       .reset_index())
        anc_summary["abs_err"] = (anc_summary.CV_pred_balticmean
                                  - anc_summary.CV_actual_balticmean).abs()
        anc_summary.to_csv(RES / "surrogate_anchor_check.csv", index=False)
        print("\nAnchor check (held-out CV prediction vs actual, Baltic-mean):")
        print(anc_summary.round(3).to_string(index=False))

    # ----- fit scatter -----
    fig, ax = plt.subplots(1, 2, figsize=(12, 5))
    for a, oof, name in [(ax[0], cv_oof, "Capture value (CV_corr)"),
                         (ax[1], pr_oof, "Mean price (€/MWh)")]:
        tgt = "CV_corr" if "value" in name else "mean_price"
        good = oof.dropna(subset=["pred"])
        a.scatter(good[tgt], good.pred, s=14, alpha=0.5,
                  c=(good.region == "Baltic").map({True: "indianred", False: "steelblue"}))
        lim = [good[tgt].min(), good[tgt].max()]
        a.plot(lim, lim, "k--", lw=1)
        a.set_xlabel(f"PyPSA actual — {name}"); a.set_ylabel("Surrogate (out-of-fold)")
        a.set_title(name); a.grid(alpha=0.3)
    fig.suptitle("Surrogate vs PyPSA (grouped out-of-fold; red=Baltic, blue=North Sea)")
    plt.tight_layout(); plt.savefig(RES / "fig_surrogate_fit.png", dpi=130); plt.close()
    print(f"Saved fit figure -> {RES/'fig_surrogate_fit.png'}")

    # ----- SHAP on the CV model -----
    try:
        import shap
        expl = shap.TreeExplainer(cv_model)
        sv = expl.shap_values(Xcv)
        plt.figure()
        shap.summary_plot(sv, Xcv, show=False, max_display=12)
        plt.tight_layout(); plt.savefig(RES / "fig_shap_cv.png", dpi=130); plt.close()
        imp = (pd.DataFrame({"feature": Xcv.columns,
                             "mean_abs_shap": np.abs(sv).mean(0)})
               .sort_values("mean_abs_shap", ascending=False))
        imp.to_csv(RES / "surrogate_shap_importance.csv", index=False)
        print(f"Saved SHAP -> {RES/'fig_shap_cv.png'}")
        print("\nTop CV drivers (mean |SHAP|):")
        print(imp.head(8).to_string(index=False))
    except Exception as e:
        print(f"(SHAP skipped: {type(e).__name__}: {e})")


if __name__ == "__main__":
    main()
