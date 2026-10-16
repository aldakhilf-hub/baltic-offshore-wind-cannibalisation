"""
7.13_make_analytical_equation.py — typeset the analytical capture-value equation
for the projection-method slide. Static (no data), rendered via matplotlib
mathtext so it needs no LaTeX install.
"""
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

OUT = str(Path(__file__).resolve().parents[1] / "9_Thesis_LaTeX/figures/fig_analytical_equation.png")
NAVY = "#16293D"; GREY = "#5E7184"; RED = "#C0392B"; BLUE = "#2E6E9E"

fig, ax = plt.subplots(figsize=(11.2, 4.4)); ax.axis("off")

eq = (r"$\mathrm{CV} \;=\; 1 \;-\; B\,\frac{M_{WF}}{M_{BZN}}\,S"
      r"\;-\; C\,M_{WF}\,(0.202\,p_{CO_2} + p_{gas})^{\gamma}$")
ax.text(0.5, 0.80, eq, ha="center", va="center", fontsize=27, color=NAVY)

ax.text(0.30, 0.56, "cannibalisation", ha="center", fontsize=12.5, color=RED, fontweight="bold")
ax.text(0.74, 0.56, "fuel-price distortion", ha="center", fontsize=12.5, color=BLUE, fontweight="bold")

defs = [
    r"$M_{WF}=|\rho_{VRE}-\rho_{load}|^{\alpha}$   pattern penalty (crowding);   "
    r"$\alpha$ = 0.74 Baltic vs 0.37 North Sea",
    r"$M_{BZN}=(I_{int}+I_{flex})^{\delta}$   buffering by interconnection and flexibility",
    r"$S$ penetration  ·  $B$ cannibalisation scale  ·  $C,\,\gamma$ fuel term  ·  "
    r"$0.202$ folds carbon into a gas-equivalent",
]
for i, d in enumerate(defs):
    ax.text(0.5, 0.36 - i * 0.135, d, ha="center", va="center", fontsize=12.5, color=GREY)

fig.savefig(OUT, dpi=200, facecolor="white", bbox_inches="tight")
print("WROTE", OUT)
