"""
7.37_cfd_exposure_figure.py

Deck figure for the CfD who-pays analysis (7.36). Two panels:

  LEFT: share of wind energy in zero-price hours (CfD payment suspended, the
        farm-borne slice) per basin: observed 2023-24, 2030 frozen, 2040 frozen,
        2040 optimal grid. Punchline: the optimal grid RAISES the Baltic's
        farm-borne exposure (18.5% -> 33.1%) while cutting the North Sea's;
        it converts state-borne erosion into farm-borne erosion.

  RIGHT: 2040 per-zone dumbbells (frozen -> optimal). Shows the three regimes:
        scarcity-priced enclosure (PL, BE: near-zero exposure under the frozen
        grid because fossil/VOLL pricing floors the zone), local-oversupply
        enclosure (EE, LV, LT: 30-42% exposure the grid barely changes), and
        the open basin (DE, NL, DK1: high exposure the grid relieves).

Reads results/cfd_who_pays*.csv (from 7.36).
Output -> results/ + 10_Presentation/figures/fig_cfd_exposure.png
"""
from pathlib import Path
import numpy as np, pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patheffects as pe

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "7_Thesis_Figures" / "results"
DECK = ROOT / "10_Presentation" / "figures"
HALO = [pe.withStroke(linewidth=2.2, foreground="white")]

M = pd.read_csv(RES / "cfd_who_pays.csv")
O = pd.read_csv(RES / "cfd_who_pays_observed.csv").set_index("basin").neg_share_2324
Z = pd.read_csv(RES / "cfd_who_pays_zones.csv")

C_NS, C_BAL = "#2471a3", "#e67e22"
C_NS_L, C_BAL_L = "#7fb3d5", "#f0b27a"

def m(year, grid, basin, col="E0_share"):
    return float(M[(M.year == int(year)) & (M.grid == grid) & (M.basin == basin)][col].iloc[0])

stages = ["2023-24\nobserved", "2030\nfrozen grid", "2040\nfrozen grid", "2040\noptimal grid"]
ns_v = [O["North Sea"], m(2030, "frozen", "North Sea"), m(2040, "frozen", "North Sea"), m(2040, "optimal", "North Sea")]
ba_v = [O["Baltic"], m(2030, "frozen", "Baltic"), m(2040, "frozen", "Baltic"), m(2040, "optimal", "Baltic")]

fig, (ax, ax2) = plt.subplots(1, 2, figsize=(12.6, 6.2), width_ratios=[1.05, 1])

x = np.arange(4); W = 0.36
for i in range(4):
    hat = "//" if i == 3 else None
    ax.bar(x[i] - W / 2, ns_v[i] * 100, W, color=C_NS if i < 3 else C_NS_L, hatch=hat, zorder=3,
           edgecolor="white" if hat else None)
    ax.bar(x[i] + W / 2, ba_v[i] * 100, W, color=C_BAL if i < 3 else C_BAL_L, hatch=hat, zorder=3,
           edgecolor="white" if hat else None)
    for dx, v, c in [(-W / 2, ns_v[i], "#1a5276"), (W / 2, ba_v[i], "#af601a")]:
        ax.text(x[i] + dx, v * 100 + 1.0, f"{v * 100:.0f}%", ha="center", fontsize=10.5,
                fontweight="bold", color=c, path_effects=HALO)
ax.set_xticks(x); ax.set_xticklabels(stages, fontsize=9.5)
ax.set_ylabel("Share of wind energy in zero-price hours (%)", fontsize=10.5)
ax.set_ylim(0, 62); ax.grid(axis="y", alpha=0.25); ax.set_axisbelow(True)
ax.legend(handles=[plt.Rectangle((0, 0), 1, 1, fc=C_NS), plt.Rectangle((0, 0), 1, 1, fc=C_BAL)],
          labels=["North Sea", "Baltic (excl. FI)"], fontsize=9.5, frameon=False, loc="upper left")
ax.set_title("Wind energy in zero-price hours, by basin", fontsize=11.5, color="#111")

# ---- right: per-zone dumbbells, 2040 ----
order = ["DK1", "NL", "DE", "FR", "BE", "EE", "LV", "LT", "PL"]
zf = Z[Z.grid == "frozen"].set_index("zone")
zo = Z[Z.grid == "optimal"].set_index("zone")
y = np.arange(len(order))[::-1]
for yi, z in zip(y, order):
    c = C_NS if z in ["DK1", "NL", "DE", "FR", "BE"] else C_BAL
    f, o = zf.loc[z, "E0_share"] * 100, zo.loc[z, "E0_share"] * 100
    ax2.plot([f, o], [yi, yi], color=c, lw=2.0, alpha=0.55, zorder=2)
    ax2.scatter([f], [yi], s=64, color=c, zorder=3)
    ax2.scatter([o], [yi], s=64, facecolor="white", edgecolor=c, lw=2.0, zorder=3)
    if o > f + 1:
        ax2.annotate("", xy=(o - 0.8, yi), xytext=(o - 4.5, yi),
                     arrowprops=dict(arrowstyle="->", color=c, lw=1.5), zorder=4)
    elif f > o + 1:
        ax2.annotate("", xy=(o + 0.8, yi), xytext=(o + 4.5, yi),
                     arrowprops=dict(arrowstyle="->", color=c, lw=1.5), zorder=4)
ax2.set_yticks(y); ax2.set_yticklabels(order, fontsize=10)
ax2.set_xlabel("Share of wind energy in zero-price hours, 2040 (%)", fontsize=10.5)
ax2.set_xlim(0, 74); ax2.set_ylim(-1.15, 8.6); ax2.grid(axis="x", alpha=0.25); ax2.set_axisbelow(True)
ax2.axhline(3.5, color="#888", lw=0.8, ls=":")
ax2.scatter([], [], s=64, color="#555", label="frozen grid")
ax2.scatter([], [], s=64, facecolor="white", edgecolor="#555", lw=2, label="optimal grid")
ax2.legend(fontsize=9, frameon=False, loc="upper left")
ax2.set_title("Per-zone exposure, 2040, frozen and optimal grid", fontsize=11.5, color="#111")

fig.suptitle("Zero-price exposure by basin and by zone", fontsize=14, y=0.97, color="#111")
fig.subplots_adjust(top=0.86, bottom=0.12, left=0.065, right=0.985, wspace=0.18)
fig.savefig(RES / "fig_cfd_exposure.png", dpi=190)
print("saved fig_cfd_exposure.png")
