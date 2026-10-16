"""
7.34_capture_value_evolution.py -- capture-value evolution 2025->2040 for the
North Sea vs the Baltic, every instrument on one chart, so the two-instrument
logic is visible:

  PyPSA frozen grid   -> the conservative headline (finds the convex collapse)
  PyPSA optimal grid  -> recovers with transmission (the reversal)
  Regression analytic -> Jacquet closed form, projects gently (linear penalty)
  Regression tree     -> abstains: flat-lines at its training boundary

The gap between the regression lines (high) and PyPSA frozen (low) IS the convex
cannibalisation collapse the empirical form cannot see -> why PyPSA carries 2040.

Sources: grid_reversal_table.csv (PyPSA), analytical_projection.csv (analytic),
projection_summary.csv (tree). Present 2025 = observed (NS 0.887, Baltic 0.889).
Output -> results/ + 10_Presentation/figures/ : fig_capture_value_evolution.png
"""
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "7_Thesis_Figures" / "results"
DECK = ROOT / "10_Presentation" / "figures"
yrs = [2025, 2030, 2040]

# method -> {basin: [2025, 2030, 2040]}
D = {
    "PyPSA, frozen grid":   {"NS": [0.887, 0.839, 0.573], "Baltic": [0.889, 0.790, 0.471]},
    "PyPSA, optimal grid":  {"NS": [0.887, 0.808, 0.637], "Baltic": [0.889, 0.778, 0.664]},
    "Regression (analytic)":{"NS": [0.887, 0.840, 0.786], "Baltic": [0.889, 0.825, 0.717]},
    "Regression (tree)":    {"NS": [0.887, 0.825, 0.810], "Baltic": [0.889, 0.824, 0.819]},
}
STYLE = {
    "PyPSA, frozen grid":   dict(color="#c0392b", lw=2.8, ls="-",  marker="o", ms=7, zorder=5),
    "PyPSA, optimal grid":  dict(color="#1e7d34", lw=2.4, ls="--", marker="s", ms=6, mfc="white", zorder=4),
    "Regression (analytic)":dict(color="#2471a3", lw=2.2, ls=":",  marker="^", ms=6, zorder=3),
    "Regression (tree)":    dict(color="#999999", lw=1.6, ls=(0, (1, 1)), marker="x", ms=6, zorder=2),
}

fig, axes = plt.subplots(1, 2, figsize=(13.2, 6.2), sharey=True)
for ax, bas in zip(axes, ["NS", "Baltic"]):
    for meth, st in STYLE.items():
        ax.plot(yrs, D[meth][bas], label=meth, **st)
    # shade the collapse the empirical form misses (frozen vs analytic at 2040)
    ax.annotate("", xy=(2040, D["PyPSA, frozen grid"][bas][2]), xytext=(2040, D["Regression (analytic)"][bas][2]),
                arrowprops=dict(arrowstyle="<->", color="#555", lw=1.1))
    gap = D["Regression (analytic)"][bas][2] - D["PyPSA, frozen grid"][bas][2]
    ax.text(2040.15, (D["PyPSA, frozen grid"][bas][2] + D["Regression (analytic)"][bas][2]) / 2,
            f"gap {gap:.2f}", fontsize=8.5, color="#555", va="center")
    ax.set_xticks(yrs); ax.set_ylim(0.35, 1.0)
    ax.set_title("North Sea" if bas == "NS" else "Baltic", fontsize=12, color="#111")
    ax.grid(alpha=0.3)
axes[0].set_ylabel("Offshore-wind capture value", fontsize=11)
axes[0].legend(fontsize=9, loc="lower left", framealpha=0.95)
fig.suptitle("Capture value to 2040 under all four instruments",
             fontsize=13, y=0.98, color="#111")
fig.tight_layout(rect=[0, 0, 1, 0.94])
fig.savefig(OUT / "fig_capture_value_evolution.png", dpi=190)
plt.close(fig)
print("saved fig_capture_value_evolution.png")
print("2040 endpoints (NS / Baltic):")
for meth in D:
    print(f"  {meth:24s} {D[meth]['NS'][2]:.2f} / {D[meth]['Baltic'][2]:.2f}")
