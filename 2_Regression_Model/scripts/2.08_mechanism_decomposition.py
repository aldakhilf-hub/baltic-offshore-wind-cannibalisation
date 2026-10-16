"""
08_mechanism_decomposition.py

The thesis's committed Gap-3 contribution: decompose WHY offshore-wind capture
value varies, into the explicit market parameters (Paul's 7 features) -- the
"parameterised" alternative to zone fixed effects. Two deliverables:

  1. SHAP decomposition of the XGBoost model (Paul's actual method): how much of
     the capture-value variation each market parameter explains, and in which
     direction -- the mechanism story.
  2. An analytical (closed-form) polynomial model: recursive feature elimination
     over the degree-2 feature products, then a linear fit -> an interpretable,
     extrapolatable equation (Paul Sec 4.3.3).

Reuses 06's data + model definitions (no duplication). Trains on operational
farm-months only.

Outputs to results/:
  shap_importance.csv              mean|SHAP| per feature + % of total
  fig_shap_beeswarm.png            direction + magnitude per feature
  fig_shap_bar.png                 ranked mean|SHAP|
  fig_shap_dependence_penetration.png   the cannibalisation mechanism
  analytical_polynomial.txt        the closed-form CV equation + R²

Usage:  python 08_mechanism_decomposition.py
"""
import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import shap
from sklearn.preprocessing import PolynomialFeatures, StandardScaler
from sklearn.feature_selection import RFE
from sklearn.linear_model import LinearRegression
from sklearn.metrics import r2_score

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RESULTS = ROOT / "results" / "02_capture_value_mechanism_SHAP"
RESULTS.mkdir(parents=True, exist_ok=True)

# reuse 2.06's FEATURES / load_operational / make_models (filename isn't importable)
_spec = importlib.util.spec_from_file_location("fit06", HERE / "2.06_fit_regression.py")
fit06 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fit06)
FEATURES = fit06.FEATURES
SHORT = [fit06.SHORT[f] for f in FEATURES]


def main():
    df = fit06.load_training_panel()
    X, y = df[FEATURES].reset_index(drop=True), df["CV"].values
    Xlab = X.copy(); Xlab.columns = SHORT

    # ---- 1. SHAP decomposition (XGBoost) --------------------------------
    model = fit06.make_models()["XGBoost"].fit(X, y)
    sv = shap.TreeExplainer(model).shap_values(X)
    mean_abs = np.abs(sv).mean(axis=0)
    imp = (pd.DataFrame({"feature": SHORT, "mean_abs_shap": mean_abs,
                         "pct_of_total": 100 * mean_abs / mean_abs.sum()})
           .sort_values("pct_of_total", ascending=False).reset_index(drop=True))
    imp.round(4).to_csv(RESULTS / "shap_importance.csv", index=False)
    print("\n=== SHAP mechanism decomposition (% of explained CV variation) ===")
    print(imp.round(2).to_string(index=False))

    # ranked bar
    shap.summary_plot(sv, Xlab, plot_type="bar", show=False, max_display=7)
    plt.title("Mechanism decomposition: mean |SHAP| per parameter")
    plt.tight_layout(); plt.savefig(RESULTS / "fig_shap_bar.png", dpi=200); plt.close()
    # dependence for penetration (the cannibalisation mechanism)
    shap.dependence_plot("VRE_MarketShare", sv, Xlab, show=False)
    plt.tight_layout(); plt.savefig(RESULTS / "fig_shap_dependence_penetration.png", dpi=200); plt.close()

    # ---- 1b. the mechanism in three roles (the cannibalisation story) -------
    # Carbon/gas set HOW FAR prices fall when wind sells; correlation-with-wind
    # and penetration set HOW CROWDED the selling hours are; the rest is market
    # structure (demand timing, export, storage). Directions are reported in the
    # text: crowding/penetration/carbon lower CV (robust); interconnection's
    # in-sample sign is confounded with penetration, so no arrows are drawn here.
    share = dict(zip(imp.feature, imp.pct_of_total))
    nice = {"Corr_VRE": "Corr. with system wind", "VRE_MarketShare": "Penetration",
            "Carbon_Price": "Carbon price", "Gas_Price": "Gas price",
            "Corr_Load": "Corr. with demand", "Interconnection_Index": "Interconnection",
            "Flexibility_Index": "Flexibility"}
    roles = [("How crowded the selling hours are", ["Corr_VRE", "VRE_MarketShare"], "#c0392b"),
             ("How far prices fall when wind sells", ["Carbon_Price", "Gas_Price"], "#e67e22"),
             ("Market structure (demand, export, storage)",
              ["Corr_Load", "Interconnection_Index", "Flexibility_Index"], "#2471a3")]
    items = []
    for title, feats, color in roles:
        items.append(("H", title, color, sum(share[f] for f in feats)))
        for f in sorted(feats, key=lambda x: -share[x]):
            items.append(("B", f, color, None))
    n = len(items)
    fig, ax = plt.subplots(figsize=(9.8, 5.6))
    yt, yl = [], []
    for i, it in enumerate(items):
        yv = n - i
        if it[0] == "H":
            ax.text(0.0, yv, it[1], fontsize=11, fontweight="bold", color=it[2], va="center")
            ax.text(33.8, yv, f"{it[3]:.0f}%", fontsize=11, fontweight="bold", color=it[2],
                    ha="right", va="center")
        else:
            f, color = it[1], it[2]
            ax.barh(yv, share[f], color=color, edgecolor="white", height=0.7)
            ax.text(share[f] + 0.4, yv, f"{share[f]:.1f}%", va="center", fontsize=9.5)
            yt.append(yv); yl.append(nice[f])
    ax.set_yticks(yt); ax.set_yticklabels(yl, fontsize=10)
    ax.set_xlim(0, 34); ax.set_ylim(0.3, n + 0.9)
    ax.set_xlabel("Share of explained capture-value variation (SHAP, %)")
    ax.set_title("What sets capture value, grouped by mechanism role", fontsize=12)
    ax.grid(axis="x", alpha=0.3)
    fig.tight_layout(); fig.savefig(RESULTS / "fig_shap_mechanism.png", dpi=200); plt.close()

    # ---- 2. Analytical (closed-form) polynomial -------------------------
    scaler = StandardScaler().fit(X)
    Xs = scaler.transform(X)
    poly = PolynomialFeatures(2, include_bias=False)
    Xp = poly.fit_transform(Xs)
    terms = list(poly.get_feature_names_out(SHORT))
    k = 7
    rfe = RFE(LinearRegression(), n_features_to_select=k).fit(Xp, y)
    sel = rfe.support_
    lin = LinearRegression().fit(Xp[:, sel], y)
    r2 = r2_score(y, lin.predict(Xp[:, sel]))
    sel_terms = [t for t, s in zip(terms, sel) if s]

    lines = [
        "ANALYTICAL CAPTURE-VALUE MODEL (closed form, standardised features)",
        f"  in-sample R2 = {r2:.3f}  ({k} RFE-selected degree-2 terms)",
        "  features standardised: z = (x - mean) / std  (means/stds below)",
        "",
        f"  CV = {lin.intercept_:.4f}",
    ]
    for t, c in sorted(zip(sel_terms, lin.coef_), key=lambda kv: -abs(kv[1])):
        lines.append(f"       {c:+.4f} * {t}")
    lines += ["", "  standardisation (mean, std) per raw feature:"]
    for f, mu, sd in zip(SHORT, scaler.mean_, scaler.scale_):
        lines.append(f"       {f:24s} mean={mu:12.4f}  std={sd:12.4f}")
    (RESULTS / "analytical_polynomial.txt").write_text("\n".join(lines))
    print("\n=== analytical polynomial (closed form) ===")
    print("\n".join(lines[:6 + k]))

    print(f"\nSaved -> {RESULTS}/ (shap_importance.csv, 3 figures, analytical_polynomial.txt)")


if __name__ == "__main__":
    main()
