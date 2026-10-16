"""
7.35_make_regression_diagram.py -- a one-slide schematic of the empirical
instrument, mirroring 7.17 (PyPSA): inputs -> the model -> outputs -> capture
value, plus how it PROJECTS (the tree abstains, the analytical form extrapolates).
Parallel to fig_pypsa_pipeline so the two instruments get equal billing.

Clean/minimal pass (2026-06): header left-aligned (was clipping), arrows fanned
to one point, bottom band cut from three prose paragraphs to two boxes + one line.

Output -> results/fig_regression_pipeline.png + 10_Presentation/figures/
"""
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "7_Thesis_Figures" / "results"
DECK = ROOT / "10_Presentation" / "figures"

C_IN, C_M, C_OUT, C_CV = "#d6eaf8", "#7d3c98", "#d5f5e3", "#f9e79f"
EDGE = "#34495e"

fig = plt.figure(figsize=(15, 8.6))
ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, 100); ax.set_ylim(0, 100); ax.axis("off")


def box(x, y, w, h, text, fc, fs=9.5, tc="#1a1a1a", weight="normal", align="center"):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.4,rounding_size=1.6",
                                fc=fc, ec=EDGE, lw=1.2, zorder=2))
    hx = x + w / 2 if align == "center" else x + 1.6
    ax.text(hx, y + h / 2, text, ha=align, va="center", fontsize=fs,
            color=tc, fontweight=weight, zorder=3, linespacing=1.35)


def arrow(x1, y1, x2, y2, color=EDGE, lw=1.8):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>", mutation_scale=16,
                                 color=color, lw=lw, zorder=1))


ax.text(50, 96, "Inside the regression: how it produces a capture value, and how it projects",
        ha="center", fontsize=15.5, fontweight="bold")

# ---- INPUTS (left column) ----
ax.text(2.0, 90, "INPUTS", ha="left", fontsize=11, fontweight="bold", color="#1b4f72")
ax.text(2.0, 86.8, "7 market features per farm-month", ha="left", fontsize=8.2, color="#666", style="italic")
inputs = [
    "Crowding  (corr. with system wind)",
    "Correlation with demand",
    "Penetration  (VRE market share)",
    "Fuel  (gas + carbon price)",
    "Buffering  (storage + interconnection)",
]
ys = [78, 71.5, 65, 58.5, 52]
for t, yy in zip(inputs, ys):
    box(2.0, yy - 2.6, 20, 5.0, t, C_IN, fs=8.6)
    arrow(22.5, yy, 27, 65)            # fan into one point on the model's left edge

# ---- THE MODEL (center) ----
box(28, 50, 28, 32, "", C_M)
ax.text(42, 78, "Gradient boosting", ha="center", fontsize=12.5, fontweight="bold", color="white")
ax.text(42, 71.5, r"$\widehat{CV} \;=\; \sum_{k=1}^{400} f_k(\mathbf{x})$", ha="center", fontsize=14, color="white")
ax.text(42, 64.5, "400 trees, each corrects\nthe error the last ones leave", ha="center",
        fontsize=8.8, color="#e8daef", linespacing=1.3)
ax.text(42, 56.5, "trained on real farms,\nscored leave-farm-out (blind)", ha="center",
        fontsize=8.8, color="#f9e79f", fontweight="bold", linespacing=1.3)

arrow(56, 66, 61.5, 66)

# ---- OUTPUTS (right) ----
ax.text(79, 90, "OUTPUTS", ha="center", fontsize=11, fontweight="bold", color="#1e8449")
box(61.5, 72, 36, 11, "Capture value per farm-month\n= gen-weighted price / average price",
    C_OUT, fs=9.2)
arrow(79.5, 72, 79.5, 67.5)
box(61.5, 56, 36, 11, "Validated BLIND (leave-farm-out)\nR² = 0.69 on unseen farms;\nNorth-Sea-only model still transfers\nto the Baltic (0.38)",
    C_CV, fs=9.0, weight="bold")

# ---- HOW IT PROJECTS (bottom band) ----
ax.add_patch(FancyBboxPatch((2.0, 3.5), 95.5, 36, boxstyle="round,pad=0.5,rounding_size=2",
                            fc="#fbfcfc", ec="#aab7b8", lw=1.2, zorder=0))
ax.text(50, 35.5, "How it projects to 2040", ha="center", fontsize=12.5, fontweight="bold", color="#5b2c6f")
box(5, 18, 43, 12.5,
    "The tree ABSTAINS\nevery future leaves the training range,\nso it flat-lines at ~0.82",
    "#f4ecf7", fs=9.6, align="left")
box(52, 18, 43, 12.5,
    "The analytical form EXTRAPOLATES\npenetration enters linearly (no collapse),\nso it projects NS 0.79, Baltic 0.72",
    "#eaf2f8", fs=9.6, align="left")
ax.text(50, 9.5, "Both sit above PyPSA's 0.57 / 0.47; that gap is the convex collapse only PyPSA sees,",
        ha="center", fontsize=9.6, color="#1a5276")
ax.text(50, 6.0, "which is why PyPSA carries the 2040 headline.",
        ha="center", fontsize=9.6, fontweight="bold", color="#7b241c")

for d in (OUT, DECK):
    fig.savefig(d / "fig_regression_pipeline.png", dpi=170)
print("saved fig_regression_pipeline.png")
