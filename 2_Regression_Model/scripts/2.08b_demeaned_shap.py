"""
2.08b_demeaned_shap.py  --  W6 fix: isolate the CROSS-SECTIONAL mechanism.

The in-sample SHAP (2.08) is computed on a panel dominated by the 2021-22 fuel
crisis: a large share of capture-value variation is a common TIME signal shared
by every zone. Carbon and gas are Europe-wide monthly prices (identical across
zones within a month), so their in-sample SHAP share is, by construction, a time
artefact: it cannot reflect farm-to-farm cannibalisation skill.

This script reports three SHAP rankings on the same 7 features:
  1. in-sample        (reproduces 2.08)
  2. ex-2022          (drop the crisis year)
  3. cross-sectional  (within-month de-meaning: x_im - mean_m(x_.m); removes the
                       common time signal, leaving only farm-to-farm variation)

and a variance decomposition showing how much of each feature is cross-sectional.

Outputs to results/02_capture_value_mechanism_SHAP/:
  shap_demeaned_comparison.csv
  fig_shap_demeaned.png
Run with the arm64 env (xgboost + shap):
  ~/miniforge3-arm64/envs/pypsa-eur-arm64/bin/python 2.08b_demeaned_shap.py
"""
import importlib.util
from pathlib import Path
import numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
import shap

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RESULTS = ROOT / "results" / "02_capture_value_mechanism_SHAP"

_spec = importlib.util.spec_from_file_location("fit06", HERE / "2.06_fit_regression.py")
fit06 = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(fit06)
FEATURES, SHORT, TARGET = fit06.FEATURES, [fit06.SHORT[f] for f in fit06.FEATURES], "CV"

def shap_shares(X, y):
    model = fit06.make_models()["XGBoost"].fit(X, y)
    sv = shap.TreeExplainer(model).shap_values(X)
    ma = np.abs(sv).mean(axis=0)
    return pd.Series(100 * ma / ma.sum(), index=SHORT)

def main():
    df = fit06.load_training_panel().reset_index(drop=True)
    print(f"panel: {len(df)} rows, {df.bidding_zone.nunique()} zones, "
          f"{df.groupby(['year','month']).ngroups} months")

    # ---- variance decomposition: how much of each feature is cross-sectional ----
    g = df.groupby(["year", "month"])
    rows = []
    for f in FEATURES:
        within = g[f].transform(lambda s: s - s.mean())     # cross-sectional part
        between = df[f] - within                             # time part
        tot = df[f].var()
        rows.append({"feature": fit06.SHORT[f],
                     "cross_sectional_var_pct": 100 * within.var() / tot if tot else 0,
                     "time_var_pct": 100 * between.var() / tot if tot else 0})
    vdec = pd.DataFrame(rows)
    print("\n=== how much of each feature varies across zones vs over time ===")
    print(vdec.round(1).to_string(index=False))

    # ---- three SHAP rankings ----
    base = shap_shares(df[FEATURES], df[TARGET].values)
    d22 = df[df.year != 2022]
    ex = shap_shares(d22[FEATURES].reset_index(drop=True), d22[TARGET].values)
    dem = df.copy()
    cols = FEATURES + [TARGET]
    dem[cols] = g[cols].transform(lambda s: s - s.mean())   # within-month de-mean
    cs = shap_shares(dem[FEATURES].reset_index(drop=True), dem[TARGET].values)

    comp = pd.DataFrame({"in_sample": base, "ex_2022": ex, "cross_sectional": cs})
    comp = comp.sort_values("in_sample", ascending=False).round(1)
    comp.to_csv(RESULTS / "shap_demeaned_comparison.csv")
    print("\n=== SHAP share (% of explained variation) under three panels ===")
    print(comp.to_string())

    # ---- figure: cross-sectional ranking first, in-sample as comparison ----
    order = comp.sort_values("cross_sectional", ascending=True).index.tolist()
    y = np.arange(len(order))
    fig, ax = plt.subplots(figsize=(9.4, 5.6))
    h = 0.38
    ax.barh(y + h/2, comp.loc[order, "cross_sectional"], height=h, color="#C0392B",
            label="cross-sectional (time signal removed)")
    ax.barh(y - h/2, comp.loc[order, "in_sample"], height=h, color="#C5CDD6",
            label="in-sample (crisis-laden)")
    for yi, f in zip(y, order):
        ax.text(comp.loc[f, "cross_sectional"] + 0.4, yi + h/2, f"{comp.loc[f,'cross_sectional']:.0f}",
                va="center", fontsize=8.5, color="#C0392B")
        ax.text(comp.loc[f, "in_sample"] + 0.4, yi - h/2, f"{comp.loc[f,'in_sample']:.0f}",
                va="center", fontsize=8.5, color="#5a6675")
    NICE = {"Carbon_Price": "Carbon price", "Gas_Price": "Gas price",
            "Corr_VRE": "Crowding (corr. with VRE)", "Corr_Load": "Correlation with demand",
            "VRE_MarketShare": "VRE market share", "Flexibility_Index": "Flexibility (storage)",
            "Interconnection_Index": "Interconnection"}
    ax.set_yticks(y); ax.set_yticklabels([NICE.get(f, f) for f in order], fontsize=10)
    ax.set_xlabel("Share of explained capture-value variation (SHAP, %)", fontsize=10.5)
    ax.set_title("SHAP shares before and after removing the common time signal",
                 fontsize=12, color="#111")
    ax.legend(fontsize=9.5, loc="lower right")
    for s in ["top", "right"]: ax.spines[s].set_visible(False)
    ax.grid(axis="x", alpha=0.3)
    fig.tight_layout(); fig.savefig(RESULTS / "fig_shap_demeaned.png", dpi=200); plt.close()
    print(f"\nSaved -> {RESULTS}/shap_demeaned_comparison.csv + fig_shap_demeaned.png")

if __name__ == "__main__":
    main()
