#!/usr/bin/env python
"""fig_aurora_benchmark: external validation against Aurora Energy Research's
France Power & Renewables Market Forecast (Oct 2025), the commercial standard
Jacquet's projections relied on.

Aurora capture-value discounts to baseload (2031-40, real 2024):
  offshore wind 6%, onshore 11%, solar 41-42%.
Read naively, Aurora's OFFSHORE (0.94) sits far above this thesis's Baltic 2040.
The reconciliation: France barely builds offshore, so its offshore never
self-cannibalises (an under-built market). The matched comparison is Aurora's
heavily-built technology, SOLAR (~0.59), which is the closest analogue to this
thesis's Baltic 2040 raw band (0.34-0.50), sitting just above it. Same
mechanism, similar floor; only the over-built technology differs.
Run with pypsa-eur env python."""
from pathlib import Path
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = str(Path(__file__).resolve().parents[1])
OUT = ROOT + "/9_Thesis_LaTeX/figures/fig_aurora_benchmark.png"
NAVY="#16293D"; BLUE="#2E6E9E"; ORANGE="#E67E22"; GOLD="#C9A227"; GREY="#9AA6B2"

# Baltic 2040 raw band read live from the solved engine, NOT hardcoded, so it
# never drifts from the headline after a re-solve.
_b = pd.read_csv(ROOT + "/1_PyPSA_Model/results/projections_v3/baltic_cv_fit_corrected.csv", index_col=0)
_b40 = _b.loc[[s for s in _b.index if s.startswith("2040")], "CV_raw"]
BAL_LO, BAL_HI = round(float(_b40.min()), 2), round(float(_b40.max()), 2)
BAL_CEN = round(float(_b.loc["2040-NT-balticBaseline", "CV_raw"]), 3)  # central scenario

# (label, capture value, lo, hi, source, colour)
lightly = [
    ("Aurora FR offshore wind",   0.94, 0.94, 0.94, "Aurora", GOLD),
    ("Aurora FR onshore wind",    0.89, 0.89, 0.89, "Aurora", GOLD),
    ("This thesis: under-built\nBaltic, today", 0.88, 0.88, 0.88, "thesis", BLUE),
]
heavily = [
    ("Aurora FR solar",                          0.59, 0.59, 0.59, "Aurora", GOLD),
    ("This thesis: North Sea\noffshore, 2040",   0.57, 0.57, 0.57, "thesis", BLUE),  # central scenario
    ("This thesis: Baltic\noffshore, 2040 (raw)", BAL_CEN, BAL_LO, BAL_HI, "thesis", ORANGE),
]

fig, (axL, axR) = plt.subplots(1, 2, figsize=(11.6, 5.0), sharex=True)

def panel(ax, items, title):
    y = np.arange(len(items))[::-1]
    for yi, (lab, cv, lo, hi, src, col) in zip(y, items):
        ax.barh(yi, cv, color=col, alpha=0.9, height=0.6, edgecolor="white")
        if hi > lo:
            ax.plot([lo, hi], [yi, yi], color=NAVY, lw=2.5, solid_capstyle="round", zorder=4)
            ax.text(hi + 0.015, yi, f"{lo:.2f}-{hi:.2f}", va="center", fontsize=9.5, color=NAVY)
        else:
            ax.text(cv + 0.015, yi, f"{cv:.2f}", va="center", fontsize=10, color=NAVY)
    ax.set_yticks(y); ax.set_yticklabels([it[0] for it in items], fontsize=9.5)
    ax.set_xlim(0, 1.08); ax.set_xlabel("Capture value (1 = earns the average price)", fontsize=10)
    ax.set_title(title, fontsize=12, color="#111")
    ax.axvline(1.0, color=GREY, lw=1, ls=":")
    for s in ["top","right"]: ax.spines[s].set_visible(False)
    ax.grid(axis="x", alpha=0.25)

panel(axL, lightly, "Lightly built-out fleets")
panel(axR, heavily, "Heavily built-out fleets")

fig.suptitle("Capture values against the Aurora France benchmark",
             fontsize=13, color="#111")
# legend
from matplotlib.patches import Patch
fig.legend(handles=[Patch(color=GOLD, label="Aurora (France, Oct 2025)"),
                    Patch(color=BLUE, label="This thesis (North Sea)"),
                    Patch(color=ORANGE, label="This thesis (Baltic 2040)")],
           loc="lower center", ncol=3, fontsize=9.5, frameon=False, bbox_to_anchor=(0.5, -0.02))
fig.tight_layout(rect=[0, 0.05, 1, 0.95])
fig.savefig(OUT, dpi=200, bbox_inches="tight")
print("WROTE", OUT)
