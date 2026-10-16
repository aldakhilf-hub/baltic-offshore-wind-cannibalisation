"""
3.02_model_skill_comparison.py

Tests H3c: judged on identical targets neither model has seen, do the two models
carry different KINDS of error?

THE FAIRNESS PROBLEM. The regression model is fitted to the observed record; the
system model never sees it. Scoring the regression in sample is therefore rigged
in its favour. The fix is to score the regression only where the target was held
out of training, so both models predict something neither used.

MATCHED PANEL. Zone-months for the four zones the record can arbitrate, in the
three years the system model is solved for (2019, 2023, 2024). DK2 is excluded
from scoring on a stated model-class criterion: its price formation depends on
unit commitment and must-run operation, which a linear program without unit
commitment cannot represent (264 observed negative-price hours in 2023 against
the system model's zero). It is retained in the regression's training data and
reported as a sensitivity.

TEST 1  matched out-of-sample skill
        regression: leave-one-zone-out and leave-one-year-out refits
        system model: every prediction is out of sample by construction
        MAE / RMSE / bias, plus skill against the CV = 1 null, plus a paired
        test with zone-clustered bootstrap

TEST 2  Theil decomposition of mean squared error into
            bias      (mean(pred) - mean(obs))^2
            variance  (sd(pred) - sd(obs))^2
            covariance 2 (1 - r) sd(pred) sd(obs)
        which is the decomposition of predictive ability: systematic offset,
        failure to match spread, imperfect correlation.

DIAGNOSTIC (not used in the thesis; kept for reference only): regime transfer
        across the 2022 energy crisis. Written to regime_transfer.csv. Dropped
        from the write-up 2026-08-09 as confusing rather than clarifying.

Output -> results/04_skill_comparison/*.csv  and  fig_model_skill.png
"""
import warnings, sys
from pathlib import Path
import numpy as np, pandas as pd, pypsa, xgboost as xgb
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "3_Comparison/results/04_skill_comparison"
OUT.mkdir(parents=True, exist_ok=True)
FIGD = ROOT / "7_Thesis_Figures/results"
NETS = {y: Path.home() / f"pypsa-eur/results/faisal-{y}/networks/base_s_30_elec_.nc"
        for y in (2019, 2023, 2024)}

FEATURES = ["feature_1_Corr_VRE", "feature_2_Corr_Load", "feature_3_VRE_MarketShare",
            "feature_4_Gas_Price", "feature_5_Carbon_Price",
            "feature_6_Flexibility_Index", "feature_7_Interconnection_Index"]
TARGET = "CV"
YEARS = [2019, 2023, 2024]
SCORE_ZONES = ["DE_LU", "NL", "BE", "DK1"]           # DK2 excluded, see docstring
OUTLIER = "DK2"
PYPSA_ZONE = {"DE_LU": "DE", "NL": "NL", "BE": "BE", "DK1": "DK1"}
OFFSHORE = ["offwind-ac", "offwind-dc", "offwind-float", "offwind"]


def model():
    return xgb.XGBRegressor(n_estimators=400, max_depth=4, learning_rate=0.05,
                            subsample=0.8, colsample_bytree=0.8, reg_lambda=1.0,
                            objective="reg:squarederror", random_state=0, n_jobs=-1)


# ---------------------------------------------------------------- panel
sites = pd.read_csv(ROOT / "2_Regression_Model/data/wind_farms_strandA.csv", comment="#")
status = sites.set_index("name").status.to_dict()
df = pd.read_csv(ROOT / "2_Regression_Model/data/features_strandA/features_monthly.csv")
df["status"] = df.farm.map(status)
df = df[df.status.isin(["operational", "planned", "under_construction"])].copy()
df = df.dropna(subset=FEATURES + [TARGET])
df = df[(df[TARGET] > 0) & (df[TARGET] < 2)].copy()

gen = pd.read_csv(ROOT / "2_Regression_Model/data/cv_strandA/monthly_cv_per_farm.csv")
df = df.merge(gen[["farm", "year", "month", "gen_MWh_norm"]],
              on=["farm", "year", "month"], how="left")
df["gen_MWh_norm"] = df.gen_MWh_norm.fillna(0.0)
print(f"training panel {len(df)} farm-months, {df.farm.nunique()} sites, "
      f"{df.bidding_zone.nunique()} zones, {df.year.min()}-{df.year.max()}")

X, y = df[FEATURES], df[TARGET].values

# ---------------------------------------------------------------- regression, held out
pred = {}
# leave-one-zone-out: the model has never seen that market
p = np.full(len(df), np.nan)
for z in df.bidding_zone.unique():
    m = (df.bidding_zone == z).values
    if m.sum() == 0 or (~m).sum() == 0:
        continue
    p[m] = model().fit(X[~m], y[~m]).predict(X[m])
pred["Regression, zone held out"] = p
# leave-one-year-out: the model has never seen that year
p = np.full(len(df), np.nan)
for yr in sorted(df.year.unique()):
    m = (df.year == yr).values
    p[m] = model().fit(X[~m], y[~m]).predict(X[m])
pred["Regression, year held out"] = p

for k, v in pred.items():
    df[k] = v

# ---------------------------------------------------------------- system model
def sys_monthly_cv(year):
    n = pypsa.Network(NETS[year])
    snap = pd.DatetimeIndex(n.snapshots)
    g, prices = n.generators, n.buses_t.marginal_price
    rows = []
    for zf, zp in PYPSA_ZONE.items():
        buses = [b for b in n.buses.index if b.split()[0].startswith(zp)
                 and not b.split()[0].startswith("DK2")]
        ids = [i for i in g[(g.bus.isin(buses)) & (g.carrier.isin(OFFSHORE))].index
               if i in n.generators_t.p.columns]
        pb = [b for b in buses if b in prices.columns]
        if not ids or not pb:
            continue
        G = n.generators_t.p[ids].sum(axis=1).values
        P = prices[pb].mean(axis=1).values
        t = pd.DataFrame({"g": G, "p": P}, index=snap)
        for mth, s in t.groupby(t.index.month):
            if s.g.sum() <= 0:
                continue
            rows.append(dict(bidding_zone=zf, year=year, month=mth,
                             CV_system=(s.g * s.p).sum() / s.g.sum() / s.p.mean()))
    return pd.DataFrame(rows)


SYS = pd.concat([sys_monthly_cv(yr) for yr in YEARS], ignore_index=True)
print(f"system model zone-months: {len(SYS)}")

# ---------------------------------------------------------------- zone-month panel
assert set(SCORE_ZONES + [OUTLIER]) <= set(df.bidding_zone.unique()), \
    f"zone code mismatch: panel has {sorted(df.bidding_zone.unique())}"
sub = df[df.bidding_zone.isin(SCORE_ZONES + [OUTLIER]) & df.year.isin(YEARS)].copy()
sub["w"] = sub.gen_MWh_norm.where(sub.gen_MWh_norm > 0, 1.0)


def wmean(s, w):
    return float((s * w).sum() / w.sum())


agg = []
for (z, yr, mth), s in sub.groupby(["bidding_zone", "year", "month"]):
    row = dict(bidding_zone=z, year=yr, month=mth,
               CV_observed=wmean(s[TARGET], s.w))
    for k in pred:
        row[k] = wmean(s[k], s.w)
    agg.append(row)
A = pd.DataFrame(agg).merge(SYS, on=["bidding_zone", "year", "month"], how="left")
A = A.rename(columns={"CV_system": "System model"})
A.to_csv(OUT / "zone_month_panel.csv", index=False)

MODELS = list(pred) + ["System model"]
head = A[A.bidding_zone.isin(SCORE_ZONES)].dropna(subset=MODELS + ["CV_observed"])
assert set(head.bidding_zone) == set(SCORE_ZONES), \
    f"lost zones in merge: expected {SCORE_ZONES}, scored {sorted(set(head.bidding_zone))}"
print(f"\nscored zone-months (DK2 excluded): {len(head)}  "
      f"zones {sorted(head.bidding_zone.unique())}  years {sorted(head.year.unique())}")


# ---------------------------------------------------------------- metrics
def theil(obs, prd):
    obs, prd = np.asarray(obs, float), np.asarray(prd, float)
    e = prd - obs
    mse = float(np.mean(e ** 2))
    so, sp = obs.std(), prd.std()
    r = float(np.corrcoef(obs, prd)[0, 1]) if so > 0 and sp > 0 else 0.0
    ub = (prd.mean() - obs.mean()) ** 2
    uv = (sp - so) ** 2
    uc = 2 * (1 - r) * sp * so
    return dict(MSE=mse, RMSE=float(np.sqrt(mse)),
                MAE=float(np.mean(np.abs(e))), bias=float(e.mean()), r=r,
                U_bias=ub / mse, U_var=uv / mse, U_cov=uc / mse)


def skill(obs, prd, null=1.0):
    obs, prd = np.asarray(obs, float), np.asarray(prd, float)
    return 1 - np.mean((prd - obs) ** 2) / np.mean((null - obs) ** 2)


rows = []
for m in MODELS:
    t = theil(head.CV_observed, head[m])
    t.update(model=m, skill_vs_null=skill(head.CV_observed, head[m]), n=len(head))
    rows.append(t)
M = pd.DataFrame(rows)[["model", "n", "MAE", "RMSE", "bias", "r",
                        "U_bias", "U_var", "U_cov", "skill_vs_null"]]
M.round(4).to_csv(OUT / "skill_metrics.csv", index=False)
print("\n=== TEST 1 + 2: matched skill and Theil decomposition ===")
print(M.round(3).to_string(index=False))

# paired comparison, zone-clustered bootstrap
rng = np.random.default_rng(0)
zones = head.bidding_zone.unique()
best_reg = M.loc[M.model.str.startswith("Regression"), "MAE"].idxmin()
REG = M.loc[best_reg, "model"]
d = (np.abs(head[REG] - head.CV_observed) -
     np.abs(head["System model"] - head.CV_observed)).values
zid = head.bidding_zone.values
boots = []
for _ in range(5000):
    pick = rng.choice(zones, len(zones), replace=True)
    boots.append(np.mean(np.concatenate([d[zid == z] for z in pick])))
lo, hi = np.percentile(boots, [2.5, 97.5])
print(f"\npaired MAE difference ({REG} minus system model): {d.mean():+.4f} "
      f"[{lo:+.4f}, {hi:+.4f}] 95% zone-clustered bootstrap")
pd.DataFrame([dict(comparison=f"{REG} minus System model", mean_diff=d.mean(),
                   lo=lo, hi=hi, n_zones=len(zones))]).round(4).to_csv(
    OUT / "paired_test.csv", index=False)

# sensitivity: DK2 back in
withdk2 = A.dropna(subset=MODELS + ["CV_observed"])
sens = pd.DataFrame([dict(model=m, **theil(withdk2.CV_observed, withdk2[m]))
                     for m in MODELS])
sens.round(4).to_csv(OUT / "skill_metrics_incl_DK2.csv", index=False)
print("\nsensitivity, DK2 included:")
print(sens[["model", "MAE", "bias", "U_bias", "U_var", "U_cov"]].round(3).to_string(index=False))

# ---------------------------------------------------------------- TEST 3 regime transfer
CRISIS = {2019: "pre-crisis (2019)", 2023: "post-crisis (2023-24)",
          2024: "post-crisis (2023-24)"}
tr_rows = []
for train_era, test_era in [("pre", "post"), ("post", "pre")]:
    trm = (df.year <= 2019) if train_era == "pre" else (df.year >= 2023)
    fit = model().fit(X[trm.values], y[trm.values])
    tgt = df[df.bidding_zone.isin(SCORE_ZONES + [OUTLIER]) &
             (df.year >= 2023 if test_era == "post" else df.year <= 2019)].copy()
    tgt["p"] = fit.predict(tgt[FEATURES])
    tgt["w"] = tgt.gen_MWh_norm.where(tgt.gen_MWh_norm > 0, 1.0)
    z = tgt[tgt.bidding_zone.isin(SCORE_ZONES) & tgt.year.isin(YEARS)]
    if not len(z):
        continue
    zm = z.groupby(["bidding_zone", "year", "month"]).apply(
        lambda s: pd.Series({"obs": wmean(s[TARGET], s.w), "prd": wmean(s.p, s.w)}))
    tr_rows.append(dict(model="Regression", trained_on=train_era, tested_on=test_era,
                        n=len(zm), MAE=float(np.mean(np.abs(zm.prd - zm.obs))),
                        bias=float(np.mean(zm.prd - zm.obs))))

for era, yrs in [("pre", [2019]), ("post", [2023, 2024])]:
    h = head[head.year.isin(yrs)]
    if not len(h):
        continue
    tr_rows.append(dict(model="System model", trained_on="none", tested_on=era,
                        n=len(h), MAE=float(np.mean(np.abs(h["System model"] - h.CV_observed))),
                        bias=float(np.mean(h["System model"] - h.CV_observed))))
T = pd.DataFrame(tr_rows)
T.round(4).to_csv(OUT / "regime_transfer.csv", index=False)
print("\n=== TEST 3: transfer across the 2022 regime break ===")
print(T.round(3).to_string(index=False))

# ================================================================ FIGURE
C = {"Regression, zone held out": "#2471a3", "Regression, year held out": "#5dade2",
     "System model": "#e67e22"}
fig, axes = plt.subplots(1, 2, figsize=(11.6, 4.9))

ax = axes[0]
xs = np.arange(len(M))
ax.bar(xs, M.MAE, 0.6, color=[C[m] for m in M.model], zorder=3)
for i, v in enumerate(M.MAE):
    ax.text(i, v + 0.0012, f"{v:.3f}", ha="center", fontsize=10, fontweight="bold",
            color="#2c3e50")
ax.set_xticks(xs)
ax.set_xticklabels([m.replace("Regression, ", "regression\n").replace(
    "System model", "system\nmodel") for m in M.model], fontsize=9)
ax.set_ylabel("Mean absolute error, zone-months", fontsize=10.5)
ax.set_title("Matched out-of-sample error", fontsize=11.5, color="#111")
ax.grid(axis="y", alpha=0.25); ax.margins(y=0.18)

ax = axes[1]
bot = np.zeros(len(M))
for key, lab, col in [("U_bias", "Bias", "#c0392b"),
                      ("U_var", "Variance", "#2471a3"),
                      ("U_cov", "Covariance", "#95a5a6")]:
    ax.bar(xs, M[key], 0.6, bottom=bot, color=col, zorder=3, label=lab)
    bot = bot + M[key].values
ax.set_xticks(xs)
ax.set_xticklabels([m.replace("Regression, ", "regression\n").replace(
    "System model", "system\nmodel") for m in M.model], fontsize=9)
ax.set_ylabel("Share of mean squared error", fontsize=10.5)
ax.set_title("Theil decomposition of the error", fontsize=11.5, color="#111")
for i, (_, r) in enumerate(M.iterrows()):
    ax.text(i, r.U_bias / 2, f"bias\n{r.bias:+.3f}", ha="center", va="center",
            fontsize=9, fontweight="bold", color="white")
ax.set_ylim(0, 1.16); ax.grid(axis="y", alpha=0.25)
ax.legend(fontsize=9, frameon=False, loc="upper center", ncol=3, columnspacing=1.0,
          bbox_to_anchor=(0.5, 1.005))

fig.suptitle("Predictive skill of the two models on identical held-out targets",
             fontsize=13.5, y=0.98, color="#111")
fig.subplots_adjust(top=0.82, bottom=0.17, wspace=0.26)
fig.savefig(FIGD / "fig_model_skill.png", dpi=200)
plt.close(fig)
print("\nsaved fig_model_skill.png")
