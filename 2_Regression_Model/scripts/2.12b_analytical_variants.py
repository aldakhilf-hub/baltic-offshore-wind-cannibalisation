"""
2.12b_analytical_variants.py  --  Can the analytical equation's low R^2 be raised
LEGITIMATELY, without changing the per-basin convexity finding?

Fits Jacquet's closed-form cannibalisation equation (same form, same bounds, same
initial guess as 2.12) under several principled treatments, and for each reports
R^2 AND the pattern-penalty exponent alpha per basin. The acceptance test: a
treatment is only acceptable if the Baltic exponent stays above the North Sea's
(the load-bearing RQ2 result). Treatments:
  1. monthly_all      baseline (reproduces 2.12, ~0.23)
  2. monthly_ex2022   drop the 2022 crisis year (Paul's IQR-cleaning analogue)
  3. monthly_robust   soft-L1 loss, down-weights outliers without dropping data
  4. zoneyear_all     aggregate to zone-year means (fit at the mechanism's resolution)
  5. zoneyear_ex2022  zone-year, ex-2022
Run: ~/miniforge3-arm64/envs/pypsa-eur-arm64/bin/python 2.12b_analytical_variants.py
"""
import importlib.util
from pathlib import Path
import numpy as np, pandas as pd
from scipy.optimize import least_squares

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("fit06", HERE / "2.06_fit_regression.py")
fit06 = importlib.util.module_from_spec(spec); spec.loader.exec_module(fit06)

PAUL = dict(alpha=1.1, delta=0.15, gamma=0.86, B=0.38, C=0.0025)
NAMES = list(PAUL); X0 = np.array([PAUL[k] for k in NAMES])
BOUNDS = (np.array([0.05, 0.01, 0.10, 0.0, 0.0]), np.array([3.0, 1.5, 2.0, 5.0, 0.1]))
EPS = 1e-6
FEAT = ["feature_1_Corr_VRE", "feature_2_Corr_Load", "feature_3_VRE_MarketShare",
        "feature_4_Gas_Price", "feature_5_Carbon_Price",
        "feature_6_Flexibility_Index", "feature_7_Interconnection_Index"]

def model_cv(p, d):
    alpha, delta, gamma, B, C = p
    diff = d["c_vre"] - d["c_load"]
    modwf = np.sign(diff) * np.abs(diff) ** alpha
    modbzn = np.maximum(d["i_inter"] + d["i_flex"], EPS) ** delta
    fuel = np.maximum(0.202 * d["carbon"] + d["gas"], EPS) ** gamma
    return 1.0 - B * (modwf / modbzn) * d["vrems"] - C * modwf * fuel

def fit(d, loss="linear"):
    res = least_squares(lambda p: model_cv(p, d).values - d["cv"].values, X0,
                        bounds=BOUNDS, method="trf", loss=loss,
                        f_scale=(0.1 if loss != "linear" else 1.0), max_nfev=5000)
    pred = model_cv(res.x, d)
    r2 = 1 - float(((d["cv"] - pred) ** 2).sum() / ((d["cv"] - d["cv"].mean()) ** 2).sum())
    return res.x, r2

def prep(df):
    return pd.DataFrame({
        "cv": df[fit06.TARGET].values, "basin": df["basin"].values,
        "c_vre": df["feature_1_Corr_VRE"].values, "c_load": df["feature_2_Corr_Load"].values,
        "vrems": df["feature_3_VRE_MarketShare"].values, "gas": df["feature_4_Gas_Price"].values,
        "carbon": df["feature_5_Carbon_Price"].values,
        "i_flex": df["feature_6_Flexibility_Index"].values,
        "i_inter": df["feature_7_Interconnection_Index"].values,
    })

def zoneyear(df):
    agg = {f: "mean" for f in FEAT}; agg[fit06.TARGET] = "mean"
    g = df.groupby(["bidding_zone", "year"]).agg({**agg, "basin": "first"}).reset_index()
    return g

raw = fit06.load_training_panel().dropna(subset=FEAT + [fit06.TARGET])
variants = {
    "monthly_all":     (prep(raw), "linear"),
    "monthly_ex2022":  (prep(raw[raw.year != 2022]), "linear"),
    "monthly_robust":  (prep(raw), "soft_l1"),
    "zoneyear_all":    (prep(zoneyear(raw)), "linear"),
    "zoneyear_ex2022": (prep(zoneyear(raw[raw.year != 2022])), "linear"),
}

print(f"{'variant':18} {'n':>5} {'R2_pool':>8} {'R2_NS':>7} {'R2_Bal':>7} "
      f"{'a_NS':>6} {'a_Bal':>6} {'gap':>6}  convexity_holds")
print("-" * 86)
for name, (d, loss) in variants.items():
    _, r2p = fit(d, loss)
    ns, bal = d[d.basin == "NS"], d[d.basin == "Baltic"]
    pn, r2n = fit(ns, loss); pb, r2b = fit(bal, loss)
    a_ns, a_bal = pn[0], pb[0]
    holds = "YES" if a_bal > a_ns else "NO  <-- breaks RQ2"
    print(f"{name:18} {len(d):5d} {r2p:8.3f} {r2n:7.3f} {r2b:7.3f} "
          f"{a_ns:6.2f} {a_bal:6.2f} {a_bal-a_ns:6.2f}  {holds}")
