"""
7.05_make_perzone_projection.py — per-zone Baltic offshore capture-value
projection panels (the Jacquet Appendix C/D idiom, system-instrument version).
Faisal projected only at basin-mean level; this resolves the five Baltic
zones that build out (PL, FI, EE, LV, LT), so a reader can find a zone and
read its trajectory and spread.

Per panel: a MODELLED annual capture value 2017-2024 (energy-weighted across the
zone's registry farms, VWF synthetic output x observed zone price; these zones
have little or no metered offshore, so this is not measured market revenue);
a dashed now-line;
the direct PyPSA solves at 2030 and 2040, bias-corrected per zone using the
canonical fit (bias = 0.0035 + 0.2331*pen, clamped at pen 0.498, floored at
0), with the 2040 four-scenario spread as a vertical bar. Raw model points
shown faint for reference. The empirical model abstains, so these are
system-instrument projections.

Output -> results/ + 9_Thesis_LaTeX/figures/fig_perzone_projection.png
"""
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OUT = HERE / "results"
TEX = ROOT / "9_Thesis_LaTeX" / "figures"
C_BAL = "#c0392b"
A, B, CLAMP = 0.0035, 0.2331, 0.4983   # canonical 1.09 fit
ZONES = ["PL", "FI", "EE", "LV", "LT"]
NAME = {"PL": "Poland", "FI": "Finland", "EE": "Estonia",
        "LV": "Latvia", "LT": "Lithuania"}

def corrected(cv, pen):
    return max(cv - (A + B * min(pen, CLAMP)), 0.0)

cv = pd.read_csv(ROOT / "2_Regression_Model/data/cv_strandA/monthly_cv_per_farm.csv").dropna(subset=["CV", "gen_MWh_norm"])
proj = pd.read_csv(ROOT / "1_PyPSA_Model/results/projections_v3/projected_capture_values.csv")
proj["yr"] = proj.scenario.str[:4].astype(int)

fig, axes = plt.subplots(2, 3, figsize=(13, 7), sharex=True, sharey=True)
for ax, z in zip(axes.flat, ZONES):
    h = (cv[cv.country == z].groupby("year")
         .apply(lambda x: (x.CV * x.gen_MWh_norm).sum() / x.gen_MWh_norm.sum(),
                include_groups=False))
    ax.plot(h.index, h.values, color="0.4", lw=1.2, marker="o", ms=3,
            label="modelled (VWF x price)")
    pz = proj[proj.zone == z]
    for yr in (2030, 2040):
        d = pz[pz.yr == yr]
        cor = [corrected(r.CV, r.penetration) for _, r in d.iterrows()]
        raw = list(d.CV)
        ax.scatter([yr] * len(raw), raw, facecolors="none", edgecolors=C_BAL,
                   s=22, alpha=0.5)
        ax.vlines(yr, min(cor), max(cor), color=C_BAL, lw=2)
        ax.scatter([yr], [np.mean(cor)], color=C_BAL, s=45, zorder=5,
                   edgecolor="white", linewidth=0.8)
    ax.axvline(2024.5, color="grey", ls=":", lw=1)
    ax.set_title(NAME[z], fontsize=10)
    if z == "FI":
        ax.text(0.5, 0.06, "set aside (Olkiluoto-3)",
                transform=ax.transAxes, ha="center", va="bottom",
                fontsize=7.3, color="0.35")
    ax.set_ylim(0.2, 1.02); ax.set_xlim(2017, 2041)
    ax.grid(alpha=0.3)
# legend panel in the 6th cell
lax = axes.flat[5]; lax.axis("off")
lax.plot([], [], color="0.4", marker="o", ms=4, label="modelled CV (VWF output x observed price)")
lax.scatter([], [], facecolors="none", edgecolors=C_BAL, label="raw model 2030/2040")
lax.scatter([], [], color=C_BAL, label="bias-corrected (bar = scenario spread)")
lax.legend(loc="center", fontsize=9, frameon=False)
fig.supylabel("Offshore wind capture value")
fig.suptitle("Per-zone Baltic offshore capture value, modelled history and "
             "projection", fontsize=12, color="#111")
fig.tight_layout()
for d in (OUT, TEX):
    fig.savefig(d / "fig_perzone_projection.png", dpi=200)
# print summary
for z in ZONES:
    pz = proj[proj.zone == z]
    c40 = [corrected(r.CV, r.penetration) for _, r in pz[pz.yr == 2040].iterrows()]
    print(f"{z}: 2040 corrected {min(c40):.2f}-{max(c40):.2f}")
print("saved fig_perzone_projection.png")
