"""
7.17_make_pypsa_diagram.py — a one-slide schematic of the PyPSA dispatch model:
inputs -> the linear program -> outputs -> capture value, plus the equation-level
reason PyPSA and the regression diverge. For the supervisor (2026-06-22).

Output -> results/fig_pypsa_pipeline.png + 10_Presentation/figures/
"""
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "7_Thesis_Figures" / "results"
DECK = ROOT / "10_Presentation" / "figures"

fig = plt.figure(figsize=(15, 8.6))
ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, 100); ax.set_ylim(0, 100); ax.axis("off")

C_IN, C_LP, C_OUT, C_CV = "#d6eaf8", "#1b4f72", "#d5f5e3", "#f9e79f"
EDGE = "#34495e"


def box(x, y, w, h, text, fc, fs=9.5, tc="#1a1a1a", weight="normal", align="center"):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.4,rounding_size=1.6",
                                fc=fc, ec=EDGE, lw=1.2, zorder=2))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs,
            color=tc, fontweight=weight, zorder=3, linespacing=1.35)


def arrow(x1, y1, x2, y2, color=EDGE, lw=2.0):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>", mutation_scale=18,
                                 color=color, lw=lw, zorder=1))


ax.text(50, 96.5, "How PyPSA produces the price, and why it answers differently from the regression",
        ha="center", fontsize=15.5, fontweight="bold")

# ---- INPUTS (left column) ----
ax.text(11, 90, "INPUTS  (you supply)", ha="center", fontsize=10.5, fontweight="bold", color="#1b4f72")
inputs = [
    "Grid  ·  ~30 nodes, 14 countries\nline limits (frozen 2020, or expandable)",
    "Fleet / energy mix  ·  every plant by\ncarrier: wind, solar, gas, coal, nuclear…",
    "Weather  ·  ERA5 -> hourly wind &\nsolar availability per node",
    "Demand  ·  hourly load per node",
    "Costs  ·  fuel + CO2 price -> each\nplant's marginal cost (merit order)",
]
y = 84
for t in inputs:
    box(1.5, y - 6.2, 19, 6.0, t, C_IN, fs=8.2)
    arrow(20.5, y - 3.2, 25.5, 56 if y < 60 else (74 if y > 78 else 65))
    y -= 7.2

# ---- THE LP (center) ----
box(26, 47, 30, 36, "", C_LP)
ax.text(41, 79, "PyPSA  ·  the linear program", ha="center", fontsize=12, fontweight="bold", color="white")
ax.text(41, 74.5, "(solved hourly, all 8,760 h, Gurobi)", ha="center", fontsize=8.5, color="#d6eaf8", style="italic")
ax.text(41, 69, r"$\min \;\; \sum_t \sum_g \; c_g \, p_{g,t}$", ha="center", fontsize=13, color="white")
ax.text(41, 64.3, "minimise total system cost", ha="center", fontsize=8, color="#d6eaf8")
ax.text(41, 59.5, "subject to, every node & hour:", ha="center", fontsize=8.5, color="white", fontweight="bold")
ax.text(41, 55.4, r"supply $=$ demand   $\Rightarrow$   price $\lambda_{n,t}$", ha="center", fontsize=10.5, color="#f9e79f", fontweight="bold")
ax.text(41, 51.7, "0  ≤  generation  ≤  weather × capacity", ha="center", fontsize=8.6, color="white")
ax.text(41, 48.5, "| line flow |  ≤  line limit  (frozen, or expandable)", ha="center", fontsize=8.0, color="#d6eaf8")

arrow(56, 65, 62, 65)

# ---- OUTPUTS (right) ----
ax.text(80, 90, "OUTPUTS", ha="center", fontsize=10.5, fontweight="bold", color="#1e8449")
box(62.5, 73, 35, 9, r"Hourly wholesale price  $\lambda_{n,t}$" "\n= shadow price of supply=demand\n(windy hour -> ~0 ;  still hour -> gas sets it)", C_OUT, fs=8.6)
box(62.5, 62.5, 35, 7.5, r"Hourly generation  $p_{g,t}$" "\nby plant and carrier", C_OUT, fs=8.6)
arrow(80, 73, 80, 70.2)
arrow(80, 62.5, 80, 57.5)
box(62.5, 49, 35, 8.2, "Capture value  =  (gen-weighted price)\n/ (average price)\nsame formula as observed & Jacquet", C_CV, fs=8.8, weight="bold")

# ---- WHY THEY DIVERGE (bottom band) ----
ax.add_patch(FancyBboxPatch((1.5, 2.5), 96, 38, boxstyle="round,pad=0.5,rounding_size=2",
                            fc="#fbfcfc", ec="#aab7b8", lw=1.2, zorder=0))
ax.text(50, 37, "Why PyPSA and the regression give different 2040 answers", ha="center",
        fontsize=12.5, fontweight="bold", color="#7b241c")
box(3.5, 22, 44, 11.5,
    "PyPSA  ·  SOLVES the market\n· has the grid (congestion, line limits)\n"
    "· price collapse is CONVEX as wind floods\n· solves any future from physics",
    "#eaf2f8", fs=9.2, align="left")
box(52.5, 22, 44, 11.5,
    "Regression  ·  FITS history\n· no grid term at all\n"
    "· penetration enters LINEARLY (no collapse)\n· abstains out-of-range (tree flat-lines)",
    "#fdedec", fs=9.2)

# the numbers row
ax.text(50, 18.0, "2040 capture value, central scenario:", ha="center", fontsize=9.5, fontweight="bold")
rows = [("Regression (analytical)", "0.79", "0.72", "no grid, no convexity  ->  no enclosure penalty"),
        ("PyPSA, frozen grid", "0.57", "0.47", "convex collapse  +  binding congestion"),
        ("PyPSA, optimal grid", "0.64", "0.66", "convex collapse only (congestion relieved)")]
ax.text(20, 14.3, "method", fontsize=8.5, fontweight="bold", ha="center")
ax.text(45, 14.3, "North Sea", fontsize=8.5, fontweight="bold", ha="center", color="#2471a3")
ax.text(56, 14.3, "Baltic", fontsize=8.5, fontweight="bold", ha="center", color="#c0392b")
ax.text(80, 14.3, "what it isolates", fontsize=8.5, fontweight="bold", ha="center")
yy = 10.8
for m, ns, bal, note in rows:
    ax.text(20, yy, m, fontsize=8.6, ha="center")
    ax.text(45, yy, ns, fontsize=9.2, ha="center", color="#2471a3", fontweight="bold")
    ax.text(56, yy, bal, fontsize=9.2, ha="center", color="#c0392b", fontweight="bold")
    ax.text(80, yy, note, fontsize=8.0, ha="center", color="#444")
    yy -= 3.0

for d in (OUT, DECK):
    fig.savefig(d / "fig_pypsa_pipeline.png", dpi=170)
print("saved fig_pypsa_pipeline.png")
