"""
3.03_projection_backtest.py

Neither model can be scored at 2040. But the ACT OF PROJECTING can be scored at
the one horizon where reality arbitrates: fit only on data up to 2021, project
2023 and 2024, and compare against what happened.

Three predictions on identical targets (four zones x two years = 96 zone-months,
DK2 excluded on the model-class rule of Section 3.6.4):

  A  regression, actual features   fit <=2021, predict from the REALISED
                                   2023-24 monthly features. Isolates whether
                                   the fitted relationship transfers in time.

  B  regression, projected features fit <=2021, predict from CONSTRUCTED feature
                                   vectors built the way a projection must build
                                   them: weather features at the farm's own
                                   pre-2022 monthly climatology, system features
                                   at the realised annual level carrying the
                                   pre-2022 monthly shape. This is the
                                   seasonal-disaggregation construction the
                                   predecessor uses and that 2.07 applies at
                                   2030/2040. Adds the construction error on top
                                   of A.

  C  system model                   PyPSA solved for 2023 and 2024, fitted to
                                   nothing, so already a projection in this sense.

A vs B separates the error of the fitted relationship from the error of building
future feature vectors. B vs C is the like-for-like projection comparison.

LIMIT, stated in the write-up: B uses the REALISED annual system levels, not the
scenario levels a 2021 forecaster would have assumed. It therefore tests the
projection machinery under perfect scenario foresight and understates the error
a real 2021-vintage forecast would have carried.

Output -> results/05_projection_backtest/*.csv  and  fig_projection_backtest.png
"""
import warnings
from pathlib import Path
import numpy as np, pandas as pd, pypsa, xgboost as xgb
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "3_Comparison/results/05_projection_backtest"
OUT.mkdir(parents=True, exist_ok=True)
FIGD = ROOT / "7_Thesis_Figures/results"
NETS = {y: Path.home() / f"pypsa-eur/results/faisal-{y}/networks/base_s_30_elec_.nc"
        for y in (2023, 2024)}

TRAIN_MAX = 2021
TEST_YEARS = [2023, 2024]
SCORE_ZONES = ["DE_LU", "NL", "BE", "DK1"]
OUTLIER = "DK2"
PYPSA_ZONE = {"DE_LU": "DE", "NL": "NL", "BE": "BE", "DK1": "DK1"}
OFFSHORE = ["offwind-ac", "offwind-dc", "offwind-float", "offwind"]

# Paul's seasonal-disaggregation scheme, mapped onto our seven features
ADDITIVE = ["feature_1_Corr_VRE", "feature_2_Corr_Load"]              # correlations
MULTIPLICATIVE = ["feature_3_VRE_MarketShare",
                  "feature_7_Interconnection_Index"]                   # shares/indices
ANNUAL = ["feature_4_Gas_Price", "feature_5_Carbon_Price",
          "feature_6_Flexibility_Index"]                               # level only
FEATURES = ADDITIVE + MULTIPLICATIVE + ANNUAL
TARGET = "CV"


def model():
    return xgb.XGBRegressor(n_estimators=400, max_depth=4, learning_rate=0.05,
                            subsample=0.8, colsample_bytree=0.8, reg_lambda=1.0,
                            objective="reg:squarederror", random_state=0, n_jobs=-1)


def theil(obs, prd):
    obs, prd = np.asarray(obs, float), np.asarray(prd, float)
    e = prd - obs
    mse = float(np.mean(e ** 2))
    so, sp = obs.std(), prd.std()
    r = float(np.corrcoef(obs, prd)[0, 1]) if so > 0 and sp > 0 else 0.0
    return dict(MAE=float(np.mean(np.abs(e))), RMSE=float(np.sqrt(mse)),
                bias=float(e.mean()), r=r,
                U_bias=(prd.mean() - obs.mean()) ** 2 / mse,
                U_var=(sp - so) ** 2 / mse, U_cov=2 * (1 - r) * sp * so / mse)


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
assert set(SCORE_ZONES + [OUTLIER]) <= set(df.bidding_zone.unique())

train = df[df.year <= TRAIN_MAX]
test = df[df.year.isin(TEST_YEARS) &
          df.bidding_zone.isin(SCORE_ZONES + [OUTLIER])].copy()
print(f"train {len(train)} farm-months (<= {TRAIN_MAX}); "
      f"test {len(test)} farm-months ({TEST_YEARS})")

fit = model().fit(train[FEATURES], train[TARGET].values)

# ---- A: realised features
test["pred_actual"] = fit.predict(test[FEATURES])

# ---- B: features constructed the way a projection must construct them
shape_add, shape_mul, base_add = {}, {}, {}
for farm, g in train.groupby("farm"):
    for f in ADDITIVE:                      # additive monthly deviation
        base_add[(farm, f)] = g[f].mean()
        shape_add[(farm, f)] = (g.groupby("month")[f].mean() - g[f].mean()).to_dict()
    for f in MULTIPLICATIVE:                # multiplicative monthly shape
        ann = g.groupby("year")[f].transform("mean")
        ratio = (g[f] / ann.replace(0, np.nan))
        shape_mul[(farm, f)] = ratio.groupby(g.month).mean().to_dict()

rows = []
for _, r in test.iterrows():
    v = {}
    for f in ADDITIVE:
        b = base_add.get((r.farm, f)); d = shape_add.get((r.farm, f), {}).get(r.month)
        v[f] = r[f] if b is None or d is None else b + d
    for f in MULTIPLICATIVE:
        sh = shape_mul.get((r.farm, f), {}).get(r.month)
        # realised annual level for this farm-year, carrying the pre-2022 shape
        ann = test[(test.farm == r.farm) & (test.year == r.year)][f].mean()
        v[f] = r[f] if sh is None or not np.isfinite(sh) or not np.isfinite(ann) else ann * sh
    for f in ANNUAL:
        v[f] = test[(test.farm == r.farm) & (test.year == r.year)][f].mean()
    rows.append(v)
proj = pd.DataFrame(rows, index=test.index)[FEATURES]
test["pred_projected"] = fit.predict(proj)

# ---------------------------------------------------------------- system model
def sys_monthly_cv(year):
    n = pypsa.Network(NETS[year]); snap = pd.DatetimeIndex(n.snapshots)
    g, prices = n.generators, n.buses_t.marginal_price
    out = []
    for zf, zp in PYPSA_ZONE.items():
        buses = [b for b in n.buses.index if b.split()[0].startswith(zp)
                 and not b.split()[0].startswith("DK2")]
        ids = [i for i in g[(g.bus.isin(buses)) & (g.carrier.isin(OFFSHORE))].index
               if i in n.generators_t.p.columns]
        pb = [b for b in buses if b in prices.columns]
        if not ids or not pb:
            continue
        t = pd.DataFrame({"g": n.generators_t.p[ids].sum(axis=1).values,
                          "p": prices[pb].mean(axis=1).values}, index=snap)
        for m, sgrp in t.groupby(t.index.month):
            if sgrp.g.sum() > 0:
                out.append(dict(bidding_zone=zf, year=year, month=m,
                                pred_system=(sgrp.g * sgrp.p).sum() / sgrp.g.sum() / sgrp.p.mean()))
    return pd.DataFrame(out)


SYS = pd.concat([sys_monthly_cv(y) for y in TEST_YEARS], ignore_index=True)

# ---------------------------------------------------------------- zone-months
test["w"] = test.gen_MWh_norm.where(test.gen_MWh_norm > 0, 1.0)
agg = []
for (z, y, m), g in test.groupby(["bidding_zone", "year", "month"]):
    w = g.w
    agg.append(dict(bidding_zone=z, year=y, month=m,
                    CV_observed=float((g[TARGET] * w).sum() / w.sum()),
                    pred_actual=float((g.pred_actual * w).sum() / w.sum()),
                    pred_projected=float((g.pred_projected * w).sum() / w.sum())))
A = pd.DataFrame(agg).merge(SYS, on=["bidding_zone", "year", "month"], how="left")
head = A[A.bidding_zone.isin(SCORE_ZONES)].dropna(
    subset=["CV_observed", "pred_actual", "pred_projected", "pred_system"])
assert set(head.bidding_zone) == set(SCORE_ZONES), sorted(set(head.bidding_zone))
A.to_csv(OUT / "backtest_panel.csv", index=False)
print(f"scored zone-months: {len(head)}  zones {sorted(head.bidding_zone.unique())}")

# ---- how far do the 2023-24 targets sit outside the pre-2022 training range?
lo, hi = train[FEATURES].min(), train[FEATURES].max()
inside = ((test[FEATURES] >= lo) & (test[FEATURES] <= hi))
per_feat = (1 - inside.mean()) * 100
all_in = inside.all(axis=1).mean() * 100
sup = per_feat.rename("pct_rows_outside").to_frame()
sup.round(1).to_csv(OUT / "support_check.csv")
print("\n=== support: share of 2023-24 rows outside the pre-2022 range ===")
print(sup.round(1).to_string())
print(f"rows inside the range on ALL seven features: {all_in:.1f}%")

LAB = {"pred_actual": "Regression, realised features",
       "pred_projected": "Regression, projected features",
       "pred_system": "System model"}
M = pd.DataFrame([dict(model=LAB[k], **theil(head.CV_observed, head[k]))
                  for k in LAB])
M.round(4).to_csv(OUT / "backtest_metrics.csv", index=False)
print("\n=== projection backtest: fit <=2021, predict 2023-24 ===")
print(M.round(3).to_string(index=False))

sens = pd.DataFrame([dict(model=LAB[k], **theil(A.dropna(subset=list(LAB)).CV_observed,
                                                A.dropna(subset=list(LAB))[k]))
                     for k in LAB])
sens.round(4).to_csv(OUT / "backtest_metrics_incl_DK2.csv", index=False)
print("\nsensitivity, DK2 included:")
print(sens[["model", "MAE", "bias"]].round(3).to_string(index=False))

# ================================================================ FIGURE
COL = ["#2471a3", "#5dade2", "#e67e22"]
fig, (a1, a2) = plt.subplots(1, 2, figsize=(11.6, 4.9))
xs = np.arange(len(M))
a1.bar(xs, M.MAE, 0.6, color=COL, zorder=3)
for i, v in enumerate(M.MAE):
    a1.text(i, v + 0.0015, f"{v:.3f}", ha="center", fontsize=10.5,
            fontweight="bold", color="#2c3e50")
a1.set_xticks(xs)
a1.set_xticklabels(["regression\nrealised\nfeatures", "regression\nprojected\nfeatures",
                    "system\nmodel"], fontsize=9)
a1.set_ylabel("Mean absolute error, zone-months", fontsize=10.5)
a1.set_title("Error when projecting 2023-24 from pre-2022 data", fontsize=11, color="#111")
a1.grid(axis="y", alpha=0.25); a1.margins(y=0.20)

bot = np.zeros(len(M))
for key, lab, c in [("U_bias", "Bias", "#c0392b"), ("U_var", "Variance", "#2471a3"),
                    ("U_cov", "Covariance", "#95a5a6")]:
    a2.bar(xs, M[key], 0.6, bottom=bot, color=c, zorder=3, label=lab)
    bot = bot + M[key].values
for i, r in M.iterrows():
    a2.text(i, max(r.U_bias / 2, 0.04), f"bias\n{r.bias:+.3f}", ha="center", va="center",
            fontsize=8.8, fontweight="bold", color="white")
a2.set_xticks(xs)
a2.set_xticklabels(["regression\nrealised\nfeatures", "regression\nprojected\nfeatures",
                    "system\nmodel"], fontsize=9)
a2.set_ylabel("Share of mean squared error", fontsize=10.5)
a2.set_title("Theil decomposition of the projection error", fontsize=11, color="#111")
a2.set_ylim(0, 1.16); a2.grid(axis="y", alpha=0.25)
a2.legend(fontsize=9, frameon=False, loc="upper center", ncol=3, bbox_to_anchor=(0.5, 1.005))

fig.suptitle("Backtest of the projection: fitted to 2021, scored on 2023-24",
             fontsize=13.5, y=0.98, color="#111")
fig.subplots_adjust(top=0.80, bottom=0.19, wspace=0.26)
fig.savefig(FIGD / "fig_projection_backtest.png", dpi=200)
plt.close(fig)
print("\nsaved fig_projection_backtest.png")
