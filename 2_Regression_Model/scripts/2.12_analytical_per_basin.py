"""
2.12_analytical_per_basin.py — Paul Jacquet's mechanistic capture-value equation,
fitted on this project's data, SEPARATELY PER BASIN.

Paul's signature contribution (his Sec 4.3.3) is a hand-built analytical form:

    CV = 1 − B · (ModWF / ModBZN) · VREMS − C · ModWF · (0.202·P_carbon + P_gas)^γ

    ModWF  = sign(C_VRE − C_Load) · |C_VRE − C_Load|^α     (wind-pattern penalty)
    ModBZN = (I_inter + I_flex)^δ                          (bidding-zone buffering)

with constants (his fit, 18 FR/DE/NL farms): α=1.1, δ=0.15, γ=0.86, B=0.38,
C=0.0025, r²=0.36. 0.202 tCO2/MWh_th folds carbon into the gas price.

The move he never made: fit the SAME form per sea basin and compare the constants.
If the Baltic's pattern-penalty scale B (and/or its buffering exponent δ) differs,
the thesis's enclosure mechanism is expressed in one interpretable equation — and it
should corroborate 2.11 (interconnection + wind-pattern structure drive the gap).

Method: scipy least_squares (soft bounds, Paul's constants as the initial guess) on
operational farm-months (zone-resolved features, lever C); pooled + NS-only +
Baltic-only fits; 200-draw FARM-BLOCK bootstrap (resample farms, not rows — respects
the panel structure) for 90% CIs on every constant.

Outputs -> results/07_analytical_per_basin/:
  analytical_constants.csv     constants + 90% CI + R² for pooled / NS / Baltic
  fig_constants_comparison.png the basin comparison with CI whiskers
  fig_fit_quality.png          predicted vs actual per basin

Usage: python 2.12_analytical_per_basin.py
"""
import importlib.util
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.optimize import least_squares

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OUT = ROOT / "results" / "07_analytical_per_basin"
OUT.mkdir(parents=True, exist_ok=True)

spec = importlib.util.spec_from_file_location("fit06", HERE / "2.06_fit_regression.py")
fit06 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fit06)

RNG = np.random.default_rng(20260612)
PAUL = dict(alpha=1.1, delta=0.15, gamma=0.86, B=0.38, C=0.0025)
NAMES = list(PAUL)
X0 = np.array([PAUL[k] for k in NAMES])
BOUNDS = (np.array([0.05, 0.01, 0.10, 0.0, 0.0]),
          np.array([3.00, 1.50, 2.00, 5.0, 0.1]))
EPS = 1e-6
N_BOOT = 200


def model_cv(p, d):
    alpha, delta, gamma, B, C = p
    diff = d.c_vre - d.c_load
    modwf = np.sign(diff) * np.abs(diff) ** alpha
    modbzn = np.maximum(d.i_inter + d.i_flex, EPS) ** delta
    fuel = np.maximum(0.202 * d.carbon + d.gas, EPS) ** gamma
    return 1.0 - B * (modwf / modbzn) * d.vrems - C * modwf * fuel


def fit(d):
    res = least_squares(lambda p: model_cv(p, d) - d.cv, X0,
                        bounds=BOUNDS, method="trf", max_nfev=5000)
    pred = model_cv(res.x, d)
    ss_res = float(((d.cv - pred) ** 2).sum())
    ss_tot = float(((d.cv - d.cv.mean()) ** 2).sum())
    return res.x, 1 - ss_res / ss_tot


def block_bootstrap(d, n=N_BOOT):
    farms = d.farm.unique()
    draws = []
    for _ in range(n):
        pick = RNG.choice(farms, size=len(farms), replace=True)
        sample = pd.concat([d[d.farm == f] for f in pick], ignore_index=True)
        try:
            p, _ = fit(sample)
            draws.append(p)
        except Exception:
            continue
    return np.array(draws)


def prep(df):
    return pd.DataFrame({
        "farm": df.farm.values,
        "cv": df[fit06.TARGET].values,
        "c_vre": df.feature_1_Corr_VRE.values,
        "c_load": df.feature_2_Corr_Load.values,
        "vrems": df.feature_3_VRE_MarketShare.values,
        "gas": df.feature_4_Gas_Price.values,
        "carbon": df.feature_5_Carbon_Price.values,
        "i_flex": df.feature_6_Flexibility_Index.values,
        "i_inter": df.feature_7_Interconnection_Index.values,
    })


df = fit06.load_training_panel()
data = {"pooled": prep(df),
        "NS": prep(df[df.basin == "NS"]),
        "Baltic": prep(df[df.basin == "Baltic"])}

rows = []
boots = {}
print("Paul's analytical equation, fitted per basin (lever-C features)")
print("=" * 72)
print(f"Paul's own constants (18 FR/DE/NL farms): "
      + ", ".join(f"{k}={v}" for k, v in PAUL.items()) + "  (r²=0.36)\n")
for label, d in data.items():
    p, r2 = fit(d)
    bs = block_bootstrap(d)
    boots[label] = bs
    lo, hi = np.percentile(bs, [5, 95], axis=0)
    print(f"{label:7s} (n={len(d)}, farms={d.farm.nunique()}): R² = {r2:.3f}")
    for i, k in enumerate(NAMES):
        print(f"    {k:6s} {p[i]:8.4f}   90% CI [{lo[i]:8.4f}, {hi[i]:8.4f}]")
        rows.append({"fit": label, "constant": k, "value": p[i],
                     "ci_lo": lo[i], "ci_hi": hi[i], "R2": r2,
                     "n": len(d), "n_farms": d.farm.nunique(),
                     "paul_value": PAUL[k]})
    print()

res = pd.DataFrame(rows)
res.to_csv(OUT / "analytical_constants.csv", index=False)

# basin-difference probability from the bootstrap
print("Bootstrap basin comparison (share of draws where Baltic > NS):")
for i, k in enumerate(NAMES):
    nb, nn = boots["Baltic"][:, i], boots["NS"][:, i]
    m = min(len(nb), len(nn))
    share = float((nb[:m] > nn[:m]).mean())
    print(f"    {k:6s}: P(Baltic > NS) = {share:.2f}")

# ---- the interpretable headline: implied cannibalisation slope --------------
# B and alpha trade off inside the same term, so constants compared one-by-one
# are attackable. The clean comparison: dCV/dVREMS = -B * ModWF / ModBZN,
# evaluated at COMMON reference conditions (pooled means) — "at identical
# average pattern/buffering conditions, how fast does each basin's equation
# say CV falls per unit penetration?" CI from the same bootstrap draws.
dp = data["pooled"]
ref_buf = float((dp.i_inter + dp.i_flex).mean())
refs = {
    "today (pooled mean dominance)": float((dp.c_vre - dp.c_load).mean()),
    "buildout-like (P90 dominance)": float((dp.c_vre - dp.c_load).quantile(0.90)),
}
slope_rows = []
for ref_label, ref_diff in refs.items():
    print(f"\nImplied cannibalisation slope dCV/dVREMS — {ref_label} "
          f"(|C_VRE−C_Load|={ref_diff:.3f}, buffering={ref_buf:.3f}):")
    slope_draws = {}
    for label in ["NS", "Baltic"]:
        bs = boots[label]
        a, dl, B = bs[:, 0], bs[:, 1], bs[:, 3]
        slopes = -B * (abs(ref_diff) ** a) / (max(ref_buf, EPS) ** dl)
        slope_draws[label] = slopes
        lo, med, hi = np.percentile(slopes, [5, 50, 95])
        print(f"    {label:7s} median {med:+.4f}   90% CI [{lo:+.4f}, {hi:+.4f}]")
    m = min(len(slope_draws["Baltic"]), len(slope_draws["NS"]))
    p_steeper = float((slope_draws["Baltic"][:m] < slope_draws["NS"][:m]).mean())
    ratio = float(np.median(slope_draws["Baltic"]) / np.median(slope_draws["NS"]))
    print(f"    P(Baltic steeper) = {p_steeper:.2f} | median ratio Baltic/NS = {ratio:.2f}x")
    for b in ["NS", "Baltic"]:
        slope_rows.append({
            "reference": ref_label, "basin": b,
            "ref_dominance": ref_diff, "ref_buffering": ref_buf,
            "slope_median": float(np.median(slope_draws[b])),
            "slope_ci_lo": float(np.percentile(slope_draws[b], 5)),
            "slope_ci_hi": float(np.percentile(slope_draws[b], 95)),
            "p_baltic_steeper": p_steeper, "ratio_baltic_over_ns": ratio,
        })
pd.DataFrame(slope_rows).to_csv(OUT / "implied_cannibalisation_slope.csv", index=False)

# ---- figure: what the text concludes — the convexity (alpha) and the implied
#      cannibalisation slope, NS vs Baltic. The other four constants are not
#      separately identified and are kept to analytical_constants.csv only.
C = {"NS": "#2471a3", "Baltic": "#c0392b"}
slope_df = pd.DataFrame(slope_rows)
fig, (axL, axR) = plt.subplots(1, 2, figsize=(11, 4.4))

# Left: the pattern-penalty exponent alpha (the convexity)
for j, label in enumerate(["NS", "Baltic"]):
    r = res[(res.fit == label) & (res.constant == "alpha")].iloc[0]
    axL.errorbar([j], [r.value], yerr=[[r.value - r.ci_lo], [r.ci_hi - r.value]],
                 fmt="o", ms=12, capsize=6, color=C[label], lw=2)
    axL.annotate(f"{r.value:.2f}", (j, r.value), xytext=(13, 0),
                 textcoords="offset points", va="center", fontsize=12, color=C[label])
axL.set_xticks([0, 1]); axL.set_xticklabels(["North Sea", "Baltic"], fontsize=11)
axL.set_xlim(-0.5, 1.6)
axL.set_ylabel(r"Pattern-penalty exponent $\alpha$")
axL.set_title("Pattern-penalty exponent by basin", fontsize=11)
axL.grid(axis="y", alpha=0.3)

# Right: implied slope dCV/dpenetration at today's vs buildout-like dominance
refs_order = ["today (pooled mean dominance)", "buildout-like (P90 dominance)"]
xlab = ["today's\nconditions", "buildout-like\ndominance (P90)"]
w = 0.16
for basin in ["NS", "Baltic"]:
    sign = -1 if basin == "NS" else 1
    xs, ys, los, his = [], [], [], []
    for i, ref in enumerate(refs_order):
        r = slope_df[(slope_df.reference == ref) & (slope_df.basin == basin)].iloc[0]
        xs.append(i + sign * w)
        ys.append(r.slope_median)
        los.append(r.slope_median - r.slope_ci_lo)
        his.append(r.slope_ci_hi - r.slope_median)
    axR.errorbar(xs, ys, yerr=[los, his], fmt="o", ms=10, capsize=6,
                 color=C[basin], lw=2, label=basin)
axR.set_xticks([0, 1]); axR.set_xticklabels(xlab, fontsize=10)
axR.set_xlim(-0.5, 1.5)
axR.set_ylabel("Implied slope  d(CV)/d(penetration)\n(more negative = steeper erosion)")
axR.set_title("Implied slope at the two reference points", fontsize=11)
axR.legend(fontsize=10); axR.grid(axis="y", alpha=0.3)

fig.suptitle("The analytical equation per basin (15 Baltic farms across 7 zones)",
             fontsize=12)
fig.tight_layout()
fig.savefig(OUT / "fig_constants_comparison.png", dpi=200)
plt.close(fig)

fig, axes = plt.subplots(1, 2, figsize=(10, 4.6))
for ax, label in zip(axes, ["NS", "Baltic"]):
    d = data[label]
    p = res[res.fit == label].set_index("constant").value
    pred = model_cv(p[NAMES].values, d)
    r2 = res[res.fit == label].R2.iloc[0]
    ax.scatter(d.cv, pred, s=9, alpha=0.4, color=C[label])
    lim = [min(d.cv.min(), pred.min()) - 0.02, max(d.cv.max(), pred.max()) + 0.02]
    ax.plot(lim, lim, "k--", lw=1)
    ax.set(xlim=lim, ylim=lim, xlabel="actual monthly CV",
           ylabel="analytical-model CV", title=f"{label}: R² = {r2:.3f}")
    ax.grid(alpha=0.3)
fig.suptitle("Fit quality of the per-basin analytical equation", fontsize=11)
fig.tight_layout()
fig.savefig(OUT / "fig_fit_quality.png", dpi=200)
plt.close(fig)
print(f"\nSaved -> {OUT}/")
