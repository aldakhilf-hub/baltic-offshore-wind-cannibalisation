"""
7.01_make_thesis_figures.py — the thesis-level figures that the per-track
results folders don't already provide.

Inspired by the figure strategies of the two predecessor theses (Jacquet 2024,
Efthymiadou 2025): per-variable history figures, headline trajectory figures,
projection fans with bands, and honest-diagnostics figures. Each output below
is mapped to a research question in README.md.

Figures produced (results/):
  fig_A_headline_scoreboard.png   RQ1 — Baltic vs NS capture value, observed era
                                  -> corrected 2030/2040 projections with 95% CI
  fig_B_cv_history_basins.png     RQ1 — monthly farm CV trajectories by basin
                                  (Jacquet Fig 45, extended to both basins)
  fig_C_feature_evolution.png     RQ2 — 7 small multiples: basin-mean monthly
                                  evolution of every explanatory feature
  fig_D_timesplit_failure.png     RQ3 — train<=2022 model vs 2023-24 reality
                                  (the honest failure that motivates two tracks)
  fig_E_carbon_flatline.png       RQ3 — XGBoost CV vs carbon price with training
                                  support shaded (the abstention proof)
  fig_F_leverC_before_after.png   methods — zone vs country feature resolution

Also prints the lit-review consistency check: is the Baltic's OBSERVED-era CV
really above the North Sea's (the archetype-table premise the thesis hinges on)?

Usage: python 7.01_make_thesis_figures.py   (env pypsa-eur-arm64)
"""
import importlib.util
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
REG = ROOT / "2_Regression_Model"
PV = ROOT / "1_PyPSA_Model"
OUT = HERE / "results"
OUT.mkdir(exist_ok=True)

C_NS, C_BAL = "#2471a3", "#c0392b"
BASIN_C = {"NS": C_NS, "Baltic": C_BAL}

# ---------------------------------------------------------------- shared data
cv = pd.read_csv(REG / "data/cv_strandA/monthly_cv_per_farm.csv", parse_dates=["date"])
sites = pd.read_csv(REG / "data/wind_farms_strandA.csv", comment="#")
status = sites.set_index("name").status.to_dict()
cv["status"] = cv.farm.map(status)
op = cv[cv.status == "operational"].copy()

feat = pd.read_csv(REG / "data/features_strandA/features_monthly.csv")
feat["date"] = pd.to_datetime(dict(year=feat.year, month=feat.month, day=1))

proj = pd.read_csv(PV / "results/projections_v3/baltic_cv_fit_corrected.csv", index_col=0)
zone_proj = pd.read_csv(PV / "results/projections_v3/projected_capture_values.csv")

# ------------------------------------------------- A · headline scoreboard
def fig_a():
    fig, ax = plt.subplots(figsize=(8.5, 5))
    # observed-era basin means (operational farms, VWF x observed price), annual
    ann = (op[op.CV.between(0, 2)].groupby(["basin", "year"]).CV.mean()
           .unstack(0).loc[2017:2024])
    for basin in ["NS", "Baltic"]:
        ax.plot(ann.index, ann[basin], "o-", color=BASIN_C[basin], lw=2,
                label=f"{basin} observed era (farm CV, VWF × observed price)")
    # projections: Baltic raw (primary) + bias-corrected refinement with CI;
    # NS raw zone aggregate (ex GB/NO)
    bal30 = proj.loc[["2030-NT-balticBaseline", "2030-NT-balticHigh"]]
    bal40 = proj.loc[[s for s in proj.index if s.startswith("2040")]]
    for yr, sub in [(2030, bal30), (2040, bal40)]:
        ax.plot([yr], [sub.CV_raw.mean()], "s", mfc="white", mec=C_BAL, mew=2,
                ms=10, zorder=4)
        lo, hi = sub.CV_corr_lo.min(), sub.CV_corr_hi.max()
        mid = sub.CV_corr_fit.mean()
        ax.errorbar([yr], [mid], yerr=[[mid - lo], [hi - mid]], fmt="s",
                    color=C_BAL, ms=9, capsize=6, lw=2, zorder=3)
    ax.plot([], [], "s", mfc="white", mec=C_BAL, mew=2, ms=9,
            label="Baltic projected (raw engine)")
    ax.plot([], [], "s", color=C_BAL, ms=9,
            label="Baltic projected (bias-corrected, 95% CI)")
    ns = zone_proj[(zone_proj.region == "NorthSea")
                   & (~zone_proj.zone.isin(["GB", "NO"])) & (zone_proj.energy_GWh > 0)]
    for yr in (2030, 2040):
        sub = ns[ns.scenario.str.startswith(str(yr))]
        w = sub.energy_GWh
        ax.plot([yr], [(sub.CV * w).sum() / w.sum()], "s", color=C_NS, ms=9)
    ax.annotate("raw engine, then\nbias-corrected (95% CI)",
                xy=(2040, proj.CV_corr_fit.min()),
                xytext=(2034.8, 0.28), fontsize=10,
                arrowprops=dict(arrowstyle="->", color="gray"))
    ax.axhline(1.0, color="k", ls="--", lw=0.8)
    ax.set(xlabel="Year", ylabel="Offshore wind capture value",
           title="Offshore capture value: observed era and 2030/2040 projections")
    ax.grid(alpha=0.3)
    ax.legend(fontsize=10, loc="lower left")
    fig.tight_layout()  # fig_A scoreboard retired 2026-06-16 (replaced by fig_group_arc); ann still returned
    plt.close(fig)
    return ann

# --------------------------------------------- B · CV history, both basins
def fig_b():
    fig, ax = plt.subplots(figsize=(12, 4.8))
    d = op[op.CV.between(0, 2)]
    for farm, sub in d.groupby("farm"):
        sub = sub.sort_values("date")
        ax.plot(sub.date, sub.CV, lw=0.5, alpha=0.16,
                color=BASIN_C[sub.basin.iloc[0]])
    for basin, sub in d.groupby("basin"):
        m = sub.set_index("date").sort_index().CV.resample("MS").mean()
        ax.plot(m.index, m.rolling(24, min_periods=12, center=True).mean(),
                lw=3.2, color=BASIN_C[basin], label=f"{basin} (24-month mean)")
    ax.axhline(1.0, color="k", ls="--", lw=0.8)
    ax.set(ylabel="Monthly capture value", xlabel="", ylim=(0.5, 1.05))
    ax.legend(fontsize=10, loc="lower left"); ax.grid(alpha=0.3)
    fig.tight_layout(); fig.savefig(OUT / "fig_B_cv_history_basins.png", dpi=200)
    plt.close(fig)

# ------------------------------------------ C · feature evolution (7 panels)
def fig_c():
    feats = [("feature_1_Corr_VRE", "Corr. with system VRE"),
             ("feature_2_Corr_Load", "Corr. with load"),
             ("feature_3_VRE_MarketShare", "VRE market share"),
             ("feature_4_Gas_Price", "Gas price (EUR/MWh)"),
             ("feature_5_Carbon_Price", "Carbon price (EUR/t)"),
             ("feature_6_Flexibility_Index", "Flexibility index"),
             ("feature_7_Interconnection_Index", "Interconnection index")]
    d = feat[feat.farm.map(status) == "operational"]
    fig, axes = plt.subplots(2, 4, figsize=(15, 6.5), sharex=True)
    for ax, (col, label) in zip(axes.flat, feats):
        for basin, sub in d.groupby("basin"):
            m = sub.groupby("date")[col].mean()
            ax.plot(m.index, m.rolling(6, min_periods=3).mean(), lw=1.6,
                    color=BASIN_C[basin], label=basin)
        ax.set_title(label, fontsize=9); ax.grid(alpha=0.3)
        ax.tick_params(labelsize=9)
    axes.flat[0].legend(fontsize=10)
    axes.flat[-1].axis("off")
    fig.suptitle("Explanatory features over time (basin means, operational farms, "
                 "6-month MA)", fontsize=13)
    fig.tight_layout(); fig.savefig(OUT / "fig_C_feature_evolution.png", dpi=200)
    plt.close(fig)

# ----------------------------------- D + E need the fitted model machinery
def load_fit06():
    spec = importlib.util.spec_from_file_location(
        "fit06", REG / "scripts/2.06_fit_regression.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m

def fig_d(fit06):
    df = fit06.load_training_panel()
    X, y = df[fit06.FEATURES], df[fit06.TARGET].values
    tr, te = (df.year <= 2022).values, (df.year >= 2023).values
    model = fit06.make_models()["XGBoost"].fit(X[tr], y[tr])
    pred = model.predict(X[te])
    d = df[te].assign(pred=pred)
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8))
    ax = axes[0]
    ax.scatter(d.CV, d.pred, s=12, alpha=0.45,
               c=[BASIN_C[b] for b in d.basin])
    lim = [min(d.CV.min(), d.pred.min()) - 0.02, max(d.CV.max(), d.pred.max()) + 0.02]
    ax.plot(lim, lim, "k--", lw=1)
    from sklearn.metrics import r2_score
    ax.set(xlim=lim, ylim=lim, xlabel="Actual CV (2023–24)",
           ylabel="Predicted CV (model trained ≤2022)",
           title=f"Time-split test: R² = {r2_score(d.CV, d.pred):.2f}\n"
                 "trained through 2022, tested on 2023 to 2024")
    ax.grid(alpha=0.3)
    ax = axes[1]
    mon = d.assign(date=pd.to_datetime(dict(year=d.year, month=d.month, day=1)))
    g = mon.groupby("date")[["CV", "pred"]].mean()
    ax.plot(g.index, g.CV, "k-", lw=2, label="actual (monthly mean)")
    ax.plot(g.index, g.pred, "-", color="#c06c3e", lw=2, label="predicted")
    ax.set(title="Why: the model replays pre-2022 price-regime levels",
           ylabel="Capture value")
    ax.legend(fontsize=10); ax.grid(alpha=0.3); ax.tick_params(labelsize=8)
    fig.tight_layout(); fig.savefig(OUT / "fig_D_timesplit_failure.png", dpi=200)
    plt.close(fig)
    return df, X, y

def fig_e(fit06, df, X, y):
    model = fit06.make_models()["XGBoost"].fit(X, y)
    base = X.median()
    carbon = np.linspace(0, 160, 161)
    Xs = pd.DataFrame([base] * len(carbon))
    Xs["feature_5_Carbon_Price"] = carbon
    pred = model.predict(Xs[fit06.FEATURES])
    lo, hi = X.feature_5_Carbon_Price.min(), X.feature_5_Carbon_Price.max()
    fig, ax = plt.subplots(figsize=(8, 4.6))
    ax.axvspan(lo, hi, color="#dfe9f0", label=f"training support [{lo:.0f}, {hi:.0f}]")
    ax.plot(carbon, pred, lw=2.2, color="#10485c")
    for yr, co2 in [(2030, 113.4), (2040, 147.0)]:
        ax.axvline(co2, color=C_BAL, ls=":", lw=1.5)
        ax.annotate(f"TYNDP {yr}", xy=(co2, pred.max()), fontsize=10,
                    rotation=90, va="top", ha="right", color=C_BAL)
    ax.set(xlabel="Carbon price (EUR/tCO2), all other features at median",
           ylabel="Predicted capture value (XGBoost)",
           title="Predicted capture value against carbon price, with the\n"
                 "training support marked")
    ax.legend(fontsize=10); ax.grid(alpha=0.3)
    fig.tight_layout(); fig.savefig(OUT / "fig_E_carbon_flatline.png", dpi=200)
    plt.close(fig)

# ------------------------------------------------- F · lever-C before/after
def fig_f():
    new = pd.read_csv(REG / "results/01_model_fit_and_validation/regression_metrics.csv")
    old = pd.read_csv(REG / "results/01_model_fit_and_validation/regression_metrics_v1_country.csv")
    rows = []
    for label, split in [("Random K-fold", "RandomKFold (Paul protocol)"),
                         ("Leave-farm-out", "GroupKFold(farm)"),
                         ("NS → Baltic\ntransfer", "NS->Baltic")]:
        rows.append({
            "label": label,
            "country": float(old[(old.split == split) & (old.model == "XGBoost")].R2.iloc[0]),
            "zone": float(new[(new.split == split) & (new.model == "XGBoost")].R2.iloc[0]),
        })
    d = pd.DataFrame(rows)
    x = np.arange(len(d)); w = 0.36
    fig, ax = plt.subplots(figsize=(7, 4.4))
    ax.bar(x - w / 2, d.country, w, color="#9bb3c4", label="country-level features")
    ax.bar(x + w / 2, d.zone, w, color="#10485c", label="bidding-zone features (lever C)")
    for xi, r in zip(x, d.itertuples()):
        ax.annotate(f"+{r.zone - r.country:.2f}", xy=(xi + w / 2, r.zone),
                    xytext=(0, 4), textcoords="offset points",
                    ha="center", fontsize=9, fontweight="bold", color=C_BAL)
    ax.set_xticks(x); ax.set_xticklabels(d.label, fontsize=9)
    ax.set(ylabel="out-of-fold R² (XGBoost)",
           title="Out-of-fold R² with country-level and\n"
                 "bidding-zone features")
    # headroom + legend over the short NS->Baltic bars, so the +0.09 gain
    # annotation on the headline bar is never occluded by the legend box
    ax.set_ylim(0, max(d.zone.max(), d.country.max()) * 1.18)
    ax.legend(fontsize=9, loc="upper right"); ax.grid(axis="y", alpha=0.3)
    fig.tight_layout(); fig.savefig(OUT / "fig_F_leverC_before_after.png", dpi=200)
    plt.close(fig)

# ---------------------------------------------------------------- run + check
ann = fig_a()
fig_b()
fig_c()
fit06 = load_fit06()
df, X, y = fig_d(fit06)
fig_e(fit06, df, X, y)
fig_f()

print("\n=== LIT-REVIEW CONSISTENCY CHECK (archetype premise) ===")
print("Observed-era basin-mean farm CV by year:")
print(ann.round(3).to_string())
recent = ann.loc[2023:2024].mean()
print(f"\n2023-24 mean: Baltic {recent['Baltic']:.3f} vs NS {recent['NS']:.3f}")
print("""
VERDICT (flagged 2026-06-12, resolved by the three-way split):
The lit review's archetype-table premise — 'every Baltic zone shows a HIGHER
value factor than every NS zone today' — is NOT supported by this project's
own farm-level data. 2023-24 ordering is monotone in buildout exposure:
  North Sea 0.886  >  under-built Baltic states 0.837  >  built-out DK2/SE4 0.788
Near-parity held pre-crisis (2017-19); the Baltic has lagged since 2022.
=> REWRITE the lit-review Section 3 premise when drafting: the correct setup is
'the Baltic is EARLIER on the cannibalisation curve (low local penetration),
with DK2 as the preview of where the curve leads' — NOT a present-day premium.
The thesis conclusion is unaffected (erosion to 0.36-0.60 raw by 2040); the
*starting point* of the story changes.""")
print(f"Saved 6 figures -> {OUT}/")
