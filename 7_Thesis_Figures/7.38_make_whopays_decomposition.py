"""
7.38_make_whopays_decomposition.py

Expert ask (deck S17/S28): the congestion-vs-oversupply split decides HOW a CfD
pays, so push the decomposition through to who bears the loss.

Capture value factorises exactly:

    CV = (1 - z) x CV_pos          z      = share of energy in zero-price hours
                                   CV_pos = price depression WITHIN paid hours

and therefore the loss relative to perfect capture splits additively:

    1 - CV  =  z  +  (1 - z)(1 - CV_pos)
               |            |
               |            state-borne: a two-sided CfD tops a positive-but-
               |            depressed price up to strike (and Art. 13 pays for
               |            constrained-off volume) -> the farm still earns strike
               farm-borne: at price ~0 the CfD is SUSPENDED (GB AR4+, EU market
               reform) and no compliant scheme may cover it -> the farm eats it

Reads results/cfd_who_pays.csv (from 7.36). The LP floors prices at ~0 rather
than going negative, so z (and the farm-borne slice) is a conservative floor.

Output -> results/ + 10_Presentation/figures/fig_whopays_decomposition.png
"""
from pathlib import Path
import numpy as np, pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patheffects as pe
from matplotlib.patches import Patch

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "7_Thesis_Figures" / "results"
DECK = ROOT / "10_Presentation" / "figures"
WHITEHALO = [pe.withStroke(linewidth=2.4, foreground="white")]

m = pd.read_csv(RES / "cfd_who_pays.csv")
m = m[m.year == 2040].copy()
m["paid"] = 1 - m.E0_share
m["CV_pos"] = m.CV_raw / m.paid
m["farm"] = m.E0_share                       # z
m["state"] = m.paid * (1 - m.CV_pos)         # (1-z)(1-CV_pos)

C_KEEP, C_STATE, C_FARM = "#7f8c8d", "#2471a3", "#c0392b"
PRESENT = 0.888                              # 2023-24 observed parity (7.31)

order = [("North Sea", "frozen"), ("North Sea", "optimal"),
         ("Baltic", "frozen"), ("Baltic", "optimal")]
labels = ["frozen grid\n(today's)", "optimal grid\n(built out)",
          "frozen grid\n(today's)", "optimal grid\n(built out)"]

fig, ax = plt.subplots(figsize=(12.2, 6.5))
X = [0, 1, 2.55, 3.55]; W = 0.66

for x, (basin, grid) in zip(X, order):
    r = m[(m.basin == basin) & (m.grid == grid)].iloc[0]
    cv, farm, state = r.CV_raw, r.farm, r.state
    ax.bar(x, cv, W, color=C_KEEP, zorder=3)
    if state >= 0:
        ax.bar(x, state, W, bottom=cv, color=C_STATE, zorder=3)
        ax.bar(x, farm, W, bottom=cv + state, color=C_FARM, zorder=3)
    else:   # North Sea frozen: paid-hour price sits ABOVE the annual mean
        ax.bar(x, farm, W, bottom=cv, color=C_FARM, zorder=3)
        ax.plot([x - W / 2, x + W / 2], [cv + farm, cv + farm], color=C_STATE, lw=2.4, zorder=4)
        ax.annotate(f"paid-hour premium +{-state:.2f}",
                    xy=(x + W / 2 - 0.05, cv + farm), xytext=(x + 0.60, 1.075),
                    fontsize=8.2, color=C_STATE, ha="center",
                    arrowprops=dict(arrowstyle="->", color=C_STATE, lw=1.1))
    ax.text(x, cv / 2, f"captured\n{cv:.2f}", ha="center", va="center", fontsize=11,
            fontweight="bold", color="white", path_effects=[pe.withStroke(linewidth=2.4, foreground="#4d5656")])
    if state > 0.02:
        ax.text(x, cv + state / 2, f"{state:.2f}\n{state / (1 - cv) * 100:.0f}%", ha="center",
                va="center", fontsize=10, fontweight="bold", color="white")
    if farm > 0.04:
        ax.text(x, cv + max(state, 0) + farm / 2, f"{farm:.2f}\n{farm / (1 - cv) * 100:.0f}%",
                ha="center", va="center", fontsize=10, fontweight="bold", color="white")

ax.axhline(PRESENT, color="#27ae60", lw=1.3, ls=":", zorder=2)
ax.text(4.28, PRESENT + 0.012, f"today {PRESENT:.2f}", fontsize=8.6, color="#1e8449",
        ha="right", path_effects=WHITEHALO)
ax.axvline(1.775, color="#bbb", lw=1.0)
ax.set_xticks(X); ax.set_xticklabels(labels, fontsize=9.4)
ax.set_xlim(-0.62, 4.35); ax.set_ylim(0, 1.24)
ax.set_yticks(np.arange(0, 1.01, 0.2))
ax.set_ylabel("Share of the average market price (capture value)", fontsize=10.8)
ax.grid(axis="y", alpha=0.25); ax.set_axisbelow(True)
for x, t in [(0.5, "North Sea"), (3.05, "Baltic (excl. FI)")]:
    ax.text(x, 1.185, t, ha="center", fontsize=11.5, fontweight="bold", color="#2c3e50")

ax.legend([Patch(fc=C_KEEP), Patch(fc=C_STATE), Patch(fc=C_FARM)],
          ["Captured at market", "Depressed positive prices (CfD top-up, state-borne)",
           "Zero-price hours (CfD suspended, farm-borne)"],
          loc="upper center", bbox_to_anchor=(0.5, -0.105), ncol=3, fontsize=9.3, frameon=False)

fig.suptitle("Capture-value loss in 2040 by bearer under a two-sided CfD",
             fontsize=13.5, y=0.975, color="#111")
fig.subplots_adjust(top=0.885, bottom=0.185, left=0.075, right=0.985)
fig.savefig(RES / "fig_whopays_decomposition.png", dpi=190)
plt.close(fig)

out = m[["basin", "grid", "CV_raw", "E0_share", "CV_pos", "farm", "state"]].copy()
out["farm_pct_of_loss"] = (out.farm / (1 - out.CV_raw) * 100).round(0)
out["state_pct_of_loss"] = (out.state / (1 - out.CV_raw) * 100).round(0)
out.round(3).to_csv(RES / "whopays_decomposition.csv", index=False)
print(out.round(3).to_string(index=False))
print("\nsaved fig_whopays_decomposition.png")
