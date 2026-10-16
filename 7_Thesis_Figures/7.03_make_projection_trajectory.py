"""
7.03_make_projection_trajectory.py — the continuous observed-to-projected
capture-value trajectory, North Sea vs Baltic (Jacquet Appendix-D idiom:
noisy history, a dashed now-line, a smooth forecast with an uncertainty band,
scenario markers). The figure Faisal's projection lacked.

Honest construction, stated in the caption:
  - History (2017-2024): basin-mean annual capture value, energy-weighted
    across operational farms, from the observed monthly_cv_per_farm table.
  - Forecast markers: the DIRECT PyPSA solves at 2030 and 2040. North Sea is
    raw (validated accurate); Baltic is bias-corrected (1.09) with its 95% CI.
  - The smooth curve interpolates (PCHIP) between the 2024 observed anchor and
    the 2030/2040 solved anchors; it is a visual guide, not a year-by-year
    model run. The band is the real uncertainty: Baltic = propagated CI across
    scenarios; North Sea = scenario spread.

Outputs -> results/ here AND 9_Thesis_LaTeX/figures/fig_projection_trajectory.png
Usage: python 7.03_make_projection_trajectory.py   (env pypsa-eur)
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.interpolate import PchipInterpolator

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
REG = ROOT / "2_Regression_Model"
PV = ROOT / "1_PyPSA_Model"
OUT = HERE / "results"
TEX = ROOT / "9_Thesis_LaTeX" / "figures"
C_NS, C_BAL = "#2471a3", "#c0392b"

# ----------------------------------------------------- observed history
cv = pd.read_csv(REG / "data/cv_strandA/monthly_cv_per_farm.csv")
cv = cv.dropna(subset=["CV", "gen_MWh_norm"])
cv = cv[(cv.year >= 2017) & (cv.year <= 2024)]
# energy-weighted annual basin mean (weight by normalised generation)
def basin_year(df):
    w = df.gen_MWh_norm
    return (df.CV * w).sum() / w.sum()
hist = (cv.groupby(["basin", "year"]).apply(basin_year)
          .rename("CV").reset_index())
ns_h = hist[hist.basin == "NS"].sort_values("year")
ba_h = hist[hist.basin == "Baltic"].sort_values("year")
print("observed 2024:  NS", round(float(ns_h[ns_h.year == 2024].CV.iloc[0]), 3),
      " Baltic", round(float(ba_h[ba_h.year == 2024].CV.iloc[0]), 3))

# ----------------------------------------------------- projection anchors
proj = pd.read_csv(PV / "results/projections_v3/projected_capture_values.csv")
proj["yr"] = proj.scenario.str[:4].astype(int)
# North Sea: energy-weighted raw CV per scenario, then min/mean/max per year
ns = proj[proj.region == "NorthSea"].dropna(subset=["CV", "energy_GWh"])
def ew(df):
    w = df.energy_GWh
    return (df.CV * w).sum() / w.sum()
ns_sc = ns.groupby("scenario").apply(ew).rename("CV").reset_index()
ns_sc["yr"] = ns_sc.scenario.str[:4].astype(int)
ns_yr = ns_sc.groupby("yr").CV.agg(["min", "mean", "max"])
print("NS projection:\n", ns_yr.round(3))

# Baltic: bias-corrected central + CI band per scenario (1.09)
bal = pd.read_csv(PV / "results/projections_v3/baltic_cv_fit_corrected.csv")
bal["yr"] = bal.scenario.str[:4].astype(int)
bal_i = bal.set_index("scenario")
ba_yr = bal.groupby("yr").agg(lo=("CV_corr_fit", "min"),
                              hi=("CV_raw", "max"))
# centre = the CENTRAL scenario's raw engine (the headline); band = corrected
# floor to raw ceiling across scenarios (all treatments).
ba_yr["cen"] = [bal_i.loc[f"{y}-NT-balticBaseline", "CV_raw"] for y in ba_yr.index]
print("Baltic corrected projection:\n", ba_yr.round(3))

# ----------------------------------------------------- assemble smooth paths
def smooth(xa, ya):
    xs = np.linspace(xa[0], xa[-1], 200)
    return xs, PchipInterpolator(xa, ya)(xs)

ns24 = float(ns_h[ns_h.year == 2024].CV.iloc[0])
ba24 = float(ba_h[ba_h.year == 2024].CV.iloc[0])
xa = [2024, 2030, 2040]
ns_ctr = ns_sc.set_index("scenario").CV
ns_cen = smooth(xa, [ns24, ns_ctr["2030-NT-balticBaseline"], ns_ctr["2040-NT-balticBaseline"]])
ns_lo = smooth(xa, [ns24, ns_yr.loc[2030, "min"], ns_yr.loc[2040, "min"]])
ns_hi = smooth(xa, [ns24, ns_yr.loc[2030, "max"], ns_yr.loc[2040, "max"]])
ba_cen = smooth(xa, [ba24, ba_yr.loc[2030, "cen"], ba_yr.loc[2040, "cen"]])
ba_lo = smooth(xa, [ba24, ba_yr.loc[2030, "lo"], ba_yr.loc[2040, "lo"]])
ba_hi = smooth(xa, [ba24, ba_yr.loc[2030, "hi"], ba_yr.loc[2040, "hi"]])

# ----------------------------------------------------- plot
fig, ax = plt.subplots(figsize=(9, 5))
# history (noisy)
ax.plot(ns_h.year, ns_h.CV, color=C_NS, lw=1.3, marker="o", ms=3, alpha=0.9,
        label="North Sea, observed")
ax.plot(ba_h.year, ba_h.CV, color=C_BAL, lw=1.3, marker="o", ms=3, alpha=0.9,
        label="Baltic, observed")
# forecast bands + central
ax.fill_between(ns_cen[0], ns_lo[1], ns_hi[1], color=C_NS, alpha=0.15)
ax.fill_between(ba_cen[0], ba_lo[1], ba_hi[1], color=C_BAL, alpha=0.15)
ax.plot(*ns_cen, color=C_NS, lw=2, ls="--", label="North Sea, projected (raw)")
ax.plot(*ba_cen, color=C_BAL, lw=2, ls="--",
        label="Baltic, projected (raw central)")
# direct-solve markers at 2030/2040
for yr in (2030, 2040):
    ax.scatter([yr], [ba_yr.loc[yr, "cen"]], color=C_BAL, s=45, zorder=5,
               edgecolor="white", linewidth=0.8)
    ax.scatter([yr], [ns_ctr[f"{yr}-NT-balticBaseline"]], color=C_NS, s=45, zorder=5,
               edgecolor="white", linewidth=0.8)
# now-line
ax.axvline(2024.5, color="grey", ls=":", lw=1.2)
ax.text(2024.6, 0.27, "observed | projected", rotation=90, va="bottom",
        ha="left", fontsize=8, color="grey")
ax.set_xlim(2017, 2040.5)
ax.set_ylim(0.2, 1.02)
ax.set_xlabel("Year")
ax.set_ylabel("Offshore wind capture value (basin mean)")
ax.set_title("North Sea and Baltic offshore capture value, observed and "
             "projected", fontsize=12, color="#111")
ax.legend(fontsize=8, loc="lower left", framealpha=0.9)
ax.grid(alpha=0.3)
fig.tight_layout()
for d in (OUT, TEX):
    fig.savefig(d / "fig_projection_trajectory.png", dpi=200)
print("saved fig_projection_trajectory.png")
