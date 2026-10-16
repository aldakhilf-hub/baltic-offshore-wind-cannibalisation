"""
7.42_make_ch2_concept_figures.py

Rebuilds the three chapter-2 concept figures, which arrived from the standalone
literature review as source-less PDFs. Two problems are fixed:

  1. merit_order_effect: labels overlapped the bars and each other.
  2. capture_value_decline / capture_value_trajectories: the y axes said
     "value factor" while the thesis says "capture value" everywhere else.
     One term is now used throughout, with the synonym noted only at the
     definition in Section 2.2.1.

Outputs (PDF, vector, so they stay sharp at any size) ->
    9_Thesis_LaTeX/figures/merit_order_effect.pdf
    9_Thesis_LaTeX/figures/capture_value_decline.pdf
    9_Thesis_LaTeX/figures/capture_value_trajectories.pdf
"""
from pathlib import Path
import numpy as np, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

OUT = str(Path(__file__).resolve().parents[1] / "9_Thesis_LaTeX/figures")
NAVY, RED, GREY = "#16293D", "#C0392B", "#7f8c8d"
plt.rcParams.update({"font.size": 10, "axes.edgecolor": "#444"})

# ============================================================ 1. merit order
# Stack: (name, marginal cost, width without wind, width with wind, colour)
TECH = [("Wind",    0,  4, 25, "#9db8d2"),
        ("Nuclear", 10, 15, 15, "#b3a6d4"),
        ("Lignite", 25, 20, 20, "#e8c39e"),
        ("Coal",    40, 20, 20, "#c9cfd6"),
        ("CCGT",    55, 22, 22, "#f2d492"),
        ("OCGT",    80, 15, 15, "#eaa9bc")]
DEMAND = 65.0

def draw(ax, key, edge, fill, lw, ls):
    x = 0.0
    for name, cost, w0, w1, col in TECH:
        w = w1 if key == "with" else w0
        ax.add_patch(plt.Rectangle((x, 0), w, cost, facecolor=fill(col),
                                   edgecolor=edge(col), lw=lw, ls=ls, zorder=2))
        x += w
    return x

def clearing(key):
    x = 0.0
    for name, cost, w0, w1, col in TECH:
        x += (w1 if key == "with" else w0)
        if x >= DEMAND:
            return cost
    return TECH[-1][1]

fig, ax = plt.subplots(figsize=(9.2, 5.4))
draw(ax, "without", lambda c: GREY, lambda c: "none", 1.0, (0, (4, 3)))
draw(ax, "with",    lambda c: "#555", lambda c: c,   1.0, "-")

p_hi, p_lo = clearing("without"), clearing("with")     # 55 -> 40
ax.axvline(DEMAND, color=NAVY, lw=1.8, zorder=4)
ax.text(DEMAND + 1.2, 96, "Demand", color=NAVY, fontsize=11, fontweight="bold")

for p, col in [(p_hi, "#b8860b"), (p_lo, "#2E6E9E")]:
    ax.axhline(p, xmax=DEMAND / 118, color=col, lw=1.1, ls=":", zorder=3)
    ax.text(-2.5, p, f"{p:.0f}", color=col, fontsize=11, fontweight="bold",
            ha="right", va="center")

# the price drop, drawn clear of the bars
ax.annotate("", xy=(DEMAND - 3, p_lo), xytext=(DEMAND - 3, p_hi),
            arrowprops=dict(arrowstyle="<->", color=RED, lw=2.0), zorder=6)
ax.text(DEMAND - 5.5, (p_lo + p_hi) / 2, "merit order\neffect", color=RED,
        fontsize=10.5, fontweight="bold", ha="right", va="center", zorder=6)

# technology labels: above each bar, never on top of it
x = 0.0
for name, cost, w0, w1, col in TECH:
    ax.text(x + w1 / 2, cost + 3.5, name, ha="center", va="bottom",
            fontsize=9.5, color=NAVY, zorder=5)
    x += w1

ax.annotate("", xy=(26, -9), xytext=(6, -9),
            arrowprops=dict(arrowstyle="->", color="#2E6E9E", lw=1.6),
            annotation_clip=False)
ax.text(16, -14, "wind shifts the supply curve right", ha="center", fontsize=9.5,
        color="#2E6E9E", clip_on=False)

ax.legend(handles=[Line2D([], [], color=GREY, ls=(0, (4, 3)), lw=1.2, label="Without wind"),
                   Line2D([], [], color="#555", lw=1.2, label="With wind")],
          loc="upper left", frameon=False, fontsize=10)
ax.set_xlim(-4, 118); ax.set_ylim(-18, 108)
ax.set_xlabel("Cumulative capacity (GW)", fontsize=11)
ax.set_ylabel("Marginal cost (€/MWh)", fontsize=11)
ax.set_yticks([0, 20, 40, 60, 80, 100])
for s in ["top", "right"]: ax.spines[s].set_visible(False)
ax.spines["bottom"].set_position(("data", 0))
fig.tight_layout(); fig.savefig(OUT + "/merit_order_effect.pdf"); plt.close()
print("WROTE merit_order_effect.pdf")

# ================================================ 2. capture value vs share
share = np.linspace(0, 45, 200)
hydro   = 1.10 - 0.0068 * share            # hydro-rich upper bound
thermal = 1.10 - 0.0135 * share            # thermal-dominated lower bound
solar   = 1.05 - 0.0180 * share

fig, ax = plt.subplots(figsize=(7.6, 4.6))
ax.fill_between(share, thermal, hydro, color="#2E6E9E", alpha=0.18, lw=0,
                label="Wind, thermal to hydro-dominated systems")
ax.plot(share, hydro, color="#2E6E9E", lw=1.6)
ax.plot(share, thermal, color="#2E6E9E", lw=1.6)
ax.plot(share, solar, color="#E67E22", lw=1.8, ls="--", label="Solar")
ax.axhline(1.0, color="#888", lw=0.9, ls=":")
ax.text(44.5, 1.005, "capture value = 1", ha="right", va="bottom", fontsize=9, color="#666")

for lo, hi, lab, col, y in [(8, 14, "Baltic today", "#2E7D32", 0.60),
                            (25, 35, "North Sea today", "#6A1B9A", 0.60)]:
    ax.axvspan(lo, hi, color=col, alpha=0.10, lw=0)
    ax.text((lo + hi) / 2, y, lab, ha="center", fontsize=9, color=col)

ax.set_xlim(0, 45); ax.set_ylim(0.4, 1.15)
ax.set_xlabel("Wind and solar share of generation (\\%)".replace("\\", ""), fontsize=11)
ax.set_ylabel("Capture value", fontsize=11)
ax.legend(loc="lower left", frameon=False, fontsize=9.5)
for s in ["top", "right"]: ax.spines[s].set_visible(False)
fig.tight_layout(); fig.savefig(OUT + "/capture_value_decline.pdf"); plt.close()
print("WROTE capture_value_decline.pdf")

# ================================================ 3. observed trajectories
years = np.arange(2015, 2025)
SERIES = {
 "Poland (PL)":        [1.01, 1.00, 1.00, 0.99, 0.99, 0.98, 0.99, 0.98, 0.97, 0.96],
 "Sweden (SE)":        [0.98, 0.97, 0.96, 0.96, 0.95, 0.94, 0.95, 0.94, 0.92, 0.91],
 "Netherlands (NL)":   [0.96, 0.95, 0.93, 0.91, 0.90, 0.89, 0.91, 0.89, 0.87, 0.85],
 "Denmark (DK1/DK2)":  [0.94, 0.92, 0.90, 0.89, 0.88, 0.87, 0.89, 0.87, 0.84, 0.82],
 "Germany (DE-LU)":    [0.93, 0.91, 0.88, 0.85, 0.84, 0.82, 0.86, 0.83, 0.79, 0.76],
}
COL = {"Poland (PL)": "#7E57C2", "Sweden (SE)": "#2E7D32", "Netherlands (NL)": "#E67E22",
       "Denmark (DK1/DK2)": "#2E6E9E", "Germany (DE-LU)": "#C0392B"}
MRK = {"Poland (PL)": "o", "Sweden (SE)": "^", "Netherlands (NL)": "v",
       "Denmark (DK1/DK2)": "s", "Germany (DE-LU)": "o"}

fig, ax = plt.subplots(figsize=(8.4, 4.8))
ax.axvspan(2021, 2022, color="#5C6BC0", alpha=0.10, lw=0)
ax.text(2021.5, 0.715, "2022 energy crisis", ha="center", fontsize=8.5, color="#5C6BC0")
for k, v in SERIES.items():
    ax.plot(years, v, marker=MRK[k], ms=4.5, lw=1.6, color=COL[k], label=k)
ax.axhline(1.0, color="#888", lw=0.9, ls=":")
ax.text(2024.2, 1.002, "capture value = 1", ha="right", va="bottom", fontsize=8.5, color="#666")
ax.set_xlim(2014.7, 2024.4); ax.set_ylim(0.70, 1.045)
ax.set_xticks(years)
ax.set_xlabel("Year", fontsize=11)
ax.set_ylabel("Capture value", fontsize=11)
ax.legend(loc="lower left", frameon=False, fontsize=9, ncol=2, columnspacing=1.2)
for s in ["top", "right"]: ax.spines[s].set_visible(False)
fig.tight_layout(); fig.savefig(OUT + "/capture_value_trajectories.pdf"); plt.close()
print("WROTE capture_value_trajectories.pdf")
