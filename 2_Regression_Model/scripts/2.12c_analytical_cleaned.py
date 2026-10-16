"""
2.12c_analytical_cleaned.py  --  How high does the analytical R^2 go under
DEFENSIBLE cleaning (each exclusion justified independently of the R^2)?

Justifications (all used elsewhere in the thesis or by Jacquet):
  - drop Finland: nuclear-driven price collapse, set aside from every other
    aggregate in the thesis; it is not a wind-cannibalisation signal.
  - drop 6 peripheral outlier farms: the SAME farms dropped from the cross-basin
    synchronicity analysis for correlating <0.55 with their own basin
    (Olhava, Liivi Bay, Saare-Liiv, Anholt, Saint-Brieuc, North Sea Energy Island);
    meteorologically atypical, not the enclosure mechanism the equation describes.
  - zone-year resolution: the mechanism is structural; monthly farm noise is not
    what the closed form is meant to capture.
  - IQR trim of capture value: Jacquet's own outlier step (1.5*IQR), removing
    anomalous months (negative/near-zero-price months that send CV wild).
Every variant reports R^2 AND the per-basin exponent: a clean fit only counts if
Baltic stays steeper than the North Sea.
Run: ~/miniforge3-arm64/envs/pypsa-eur-arm64/bin/python 2.12c_analytical_cleaned.py
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
OUTLIERS = ["Olhava", "Liivi Bay", "Saare-Liiv", "Anholt", "Saint-Brieuc",
            "North Sea Energy Island"]

def model_cv(p, d):
    a, dl, g, B, C = p
    diff = d["c_vre"] - d["c_load"]
    modwf = np.sign(diff) * np.abs(diff) ** a
    modbzn = np.maximum(d["i_inter"] + d["i_flex"], EPS) ** dl
    fuel = np.maximum(0.202 * d["carbon"] + d["gas"], EPS) ** g
    return 1.0 - B * (modwf / modbzn) * d["vrems"] - C * modwf * fuel

def fit(d):
    res = least_squares(lambda p: model_cv(p, d).values - d["cv"].values, X0,
                        bounds=BOUNDS, method="trf", max_nfev=5000)
    pred = model_cv(res.x, d)
    r2 = 1 - float(((d["cv"] - pred) ** 2).sum() / ((d["cv"] - d["cv"].mean()) ** 2).sum())
    return res.x, r2

def prep(df):
    return pd.DataFrame({
        "cv": df[fit06.TARGET].values, "basin": df["basin"].values,
        "c_vre": df.feature_1_Corr_VRE.values, "c_load": df.feature_2_Corr_Load.values,
        "vrems": df.feature_3_VRE_MarketShare.values, "gas": df.feature_4_Gas_Price.values,
        "carbon": df.feature_5_Carbon_Price.values,
        "i_flex": df.feature_6_Flexibility_Index.values,
        "i_inter": df.feature_7_Interconnection_Index.values})

def drop_fi(df):       return df[df.bidding_zone != "FI"]
def drop_out(df):      return df[~df.farm.str.contains("|".join(OUTLIERS), case=False, na=False)]
def iqr_trim(df):
    q1, q3 = df[fit06.TARGET].quantile([.25, .75]); iqr = q3 - q1
    return df[(df[fit06.TARGET] >= q1 - 1.5*iqr) & (df[fit06.TARGET] <= q3 + 1.5*iqr)]
def zoneyear(df):
    agg = {f: "mean" for f in FEAT}; agg[fit06.TARGET] = "mean"
    return df.groupby(["bidding_zone", "year"]).agg({**agg, "basin": "first"}).reset_index()

raw = fit06.load_training_panel().dropna(subset=FEAT + [fit06.TARGET])
V = {
 "0 baseline monthly":          prep(raw),
 "1 drop Finland":              prep(drop_fi(raw)),
 "2 drop FI+outliers":          prep(drop_out(drop_fi(raw))),
 "3 drop-specials + IQR trim":  prep(iqr_trim(drop_out(drop_fi(raw)))),
 "4 zone-year baseline":        prep(zoneyear(raw)),
 "5 zone-year drop FI":         prep(zoneyear(drop_fi(raw))),
 "6 zone-year drop FI+outliers":prep(zoneyear(drop_out(drop_fi(raw)))),
 "7 zone-year drop-specials, ex-2022": prep(zoneyear(drop_out(drop_fi(raw[raw.year != 2022])))),
}
print(f"{'variant':36} {'n':>5} {'R2pool':>7} {'R2_NS':>6} {'R2_Bal':>7} {'a_NS':>5} {'a_Bal':>6}  conv")
print("-" * 92)
for name, d in V.items():
    _, r2p = fit(d)
    ns, bal = d[d.basin == "NS"], d[d.basin == "Baltic"]
    pn, r2n = fit(ns); pb, r2b = fit(bal)
    conv = "YES" if pb[0] > pn[0] else "NO"
    print(f"{name:36} {len(d):5d} {r2p:7.3f} {r2n:6.3f} {r2b:7.3f} {pn[0]:5.2f} {pb[0]:6.2f}  {conv}")
