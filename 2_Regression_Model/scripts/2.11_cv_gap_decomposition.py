"""
2.11_cv_gap_decomposition.py — why does the Baltic already trade at a capture-value
discount, BEFORE its buildout?

Context (flag of 2026-06-12): the lit review's archetype table promised a Baltic
value premium; the project's own data shows the opposite ordering by 2023-24
(NS 0.886 > under-built Baltic 0.837 > built-out DK2/SE4 0.788), with near-parity
pre-crisis. This script answers WHY, quantitatively — turning the flagged
inconsistency into a contribution.

Method: SHAP group-difference decomposition. TreeExplainer SHAP values are exactly
additive per prediction, so the PREDICTED basin gap decomposes exactly:

    pred_CV(Baltic) - pred_CV(NS)  =  sum_j [ mean phi_j(Baltic) - mean phi_j(NS) ]

computed separately for the near-parity era (2017-19) and the divergence era
(2023-24). The change in each feature's contribution between the two periods
identifies the drivers that OPENED the gap. (In-sample SHAP on the full
operational fit — same convention as 2.08; label it as such.)

Outputs -> results/06_cv_gap_decomposition/:
  gap_decomposition.csv      per-feature contribution to the basin gap, both eras
  fig_gap_waterfall.png      the answer as one figure
  README.md is written separately.

Usage: python 2.11_cv_gap_decomposition.py
"""
import importlib.util
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import shap

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OUT = ROOT / "results" / "06_cv_gap_decomposition"
OUT.mkdir(parents=True, exist_ok=True)

spec = importlib.util.spec_from_file_location("fit06", HERE / "2.06_fit_regression.py")
fit06 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fit06)

SHORT = {f: f.split("_", 2)[-1] for f in fit06.FEATURES}
PERIODS = {"2017-19 (near-parity era)": (2017, 2019),
           "2023-24 (divergence era)": (2023, 2024)}

# the basin gap is the OBSERVED divergence among farms that actually exist, so
# this decomposition stays on the operational subset (the model and mechanism
# analyses use the full zone-market panel).
df = fit06.load_operational()
X, y = df[fit06.FEATURES], df[fit06.TARGET].values
model = fit06.make_models()["XGBoost"].fit(X, y)
sv = shap.TreeExplainer(model).shap_values(X)
sv = pd.DataFrame(sv, columns=fit06.FEATURES, index=df.index)
pred = model.predict(X)

rows = []
print("SHAP group-difference decomposition of the NS->Baltic capture-value gap")
print("=" * 74)
for label, (y0, y1) in PERIODS.items():
    in_period = df.year.between(y0, y1)
    mb = in_period & (df.basin == "Baltic")
    mn = in_period & (df.basin == "NS")
    actual_gap = y[mb.values].mean() - y[mn.values].mean()
    pred_gap = pred[mb.values].mean() - pred[mn.values].mean()
    contrib = sv[mb].mean() - sv[mn].mean()
    print(f"\n{label}:  actual gap {actual_gap:+.4f} | predicted gap {pred_gap:+.4f} "
          f"(= sum of contributions, exact)")
    for f in fit06.FEATURES:
        rows.append({"period": label, "feature": SHORT[f],
                     "contribution": contrib[f],
                     "actual_gap": actual_gap, "predicted_gap": pred_gap,
                     "n_baltic": int(mb.sum()), "n_ns": int(mn.sum())})
        print(f"   {SHORT[f]:24s} {contrib[f]:+.4f}")

res = pd.DataFrame(rows)
res.to_csv(OUT / "gap_decomposition.csv", index=False)

# ---- figure: grouped horizontal bars, sorted by divergence-era contribution
piv = res.pivot(index="feature", columns="period", values="contribution")
order = piv[list(PERIODS)[1]].sort_values().index
piv = piv.loc[order]
fig, ax = plt.subplots(figsize=(8.5, 5))
ypos = np.arange(len(piv))
h = 0.38
ax.barh(ypos + h / 2, piv.iloc[:, 0], h, color="#9bb3c4", label=piv.columns[0])
ax.barh(ypos - h / 2, piv.iloc[:, 1], h, color="#c0392b", label=piv.columns[1])
ax.set_yticks(ypos); ax.set_yticklabels(piv.index, fontsize=9)
ax.axvline(0, color="k", lw=0.8)
gaps = res.groupby("period").first()
ax.set(xlabel="Contribution to (Baltic − NS) predicted capture-value gap",
       title="Why the Baltic discount emerged before the buildout:\n"
             "SHAP decomposition of the basin gap, parity era vs divergence era\n"
             + " | ".join(f"{p}: actual {g.actual_gap:+.3f}"
                          for p, g in gaps.iterrows()))
ax.legend(fontsize=8); ax.grid(axis="x", alpha=0.3)
fig.tight_layout()  # gap-waterfall figure removed 2026-06-15 (kept as prose; not saved)
plt.close(fig)
print(f"\nSaved -> {OUT}/")
