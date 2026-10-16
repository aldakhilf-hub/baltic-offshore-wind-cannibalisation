"""Poster hero chart: capture value of the two seas from 2017 to 2040 in one
figure. Observed monthly values (thin) and a 24-month mean (thick) to 2024,
then the projection to 2030 and 2040 with the grid as today (dashed) and with
transmission expanded (dotted). The numbers are written on the chart itself.
Drawn at the physical size of its slot (270 x 120 mm) with 20 pt type."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "12_Poster/figures"
FIG = ROOT / "7_Thesis_Figures"
NS, BAL, INK, MUT, GRID = "#000080", "#FF4500", "#222222", "#5B6170", "#E3E3E3"
MM = 1 / 25.4
W_MM, H_MM = 270, 120
plt.rcParams.update({"font.family": "Arial", "font.size": 20, "axes.edgecolor": "#444444",
                     "axes.linewidth": 1.2, "axes.spines.top": False, "axes.spines.right": False})

df = pd.read_csv(ROOT / "2_Regression_Model/data/features_strandA/features_monthly.csv")
df = df[df.bidding_zone != "GB"]
df = df[~((df.bidding_zone == "DE_LU") & (df.basin == "Baltic"))]
grp = {"DE_LU": "North Sea", "NL": "North Sea", "BE": "North Sea", "DK1": "North Sea", "FR": "North Sea",
       "PL": "Baltic", "EE": "Baltic", "LV": "Baltic", "LT": "Baltic"}
df["sea"] = df.bidding_zone.map(grp)
df = df[df.sea.notna()].copy()
df["date"] = pd.to_datetime(dict(year=df.year, month=df.month, day=1))
zm = df.groupby(["sea", "bidding_zone", "date"]).CV.mean().reset_index()
m = zm.groupby(["sea", "date"]).CV.mean().unstack(0).sort_index()
r = m.rolling(24, min_periods=12).mean()
t = m.index.year + (m.index.month - 0.5) / 12.0

rv = pd.read_csv(FIG / "results/grid_reversal_table.csv").set_index("year")
proj = {"North Sea": {"frozen": [rv.loc[2030, "ns_frozen"], rv.loc[2040, "ns_frozen"]],
                      "exp": [rv.loc[2030, "ns_opt"], rv.loc[2040, "ns_opt"]]},
        "Baltic": {"frozen": [rv.loc[2030, "bal_frozen"], rv.loc[2040, "bal_frozen"]],
                   "exp": [rv.loc[2030, "bal_opt"], rv.loc[2040, "bal_opt"]]}}

fig, ax = plt.subplots(figsize=(W_MM * MM, H_MM * MM), layout="constrained")
x_end = float(t[-1])
for sea, col in [("North Sea", NS), ("Baltic", BAL)]:
    ax.plot(t, m[sea], color=col, lw=1.2, alpha=0.28, zorder=2)
    ax.plot(t, r[sea], color=col, lw=4.2, zorder=4)
    y0 = float(r[sea].dropna().iloc[-1])
    for kind, style, mfc in [("frozen", dict(ls="--", dashes=(5, 3)), col),
                             ("exp", dict(ls=":", dashes=(1.5, 2.2)), "white")]:
        ys = proj[sea][kind]
        ax.plot([x_end, 2030, 2040], [y0] + ys, color=col, lw=3.8, zorder=4, **style)
        ax.plot(2040, ys[1], "o", color=col, mfc=mfc, mew=2.8, ms=14, zorder=5)
    fz, ex = proj[sea]["frozen"][1], proj[sea]["exp"][1]
    print(f"{sea}: today {y0:.3f}, 2040 frozen {fz:.3f}, expanded {ex:.3f}, congestion {ex - fz:.3f}")
# value labels at 2040, nudged apart where they crowd
labels = [("North Sea", "frozen", 0.0), ("North Sea", "exp", -0.012),
          ("Baltic", "frozen", 0.0), ("Baltic", "exp", 0.014)]
for sea, kind, nudge in labels:
    col = NS if sea == "North Sea" else BAL
    v = proj[sea][kind][1]
    ax.text(2040.7, v + nudge, f"{v:.2f}", color=col, fontsize=21, fontweight="bold", va="center")
# bracket: the part of the 2040 loss that the grid removes (Baltic)
fz, ex = proj["Baltic"]["frozen"][1], proj["Baltic"]["exp"][1]
bx = 2042.9
ax.plot([bx, bx], [fz, ex], color=BAL, lw=2.0)
ax.plot([bx - 0.25, bx], [fz, fz], color=BAL, lw=2.0)
ax.plot([bx - 0.25, bx], [ex, ex], color=BAL, lw=2.0)
ax.text(bx + 0.3, (fz + ex) / 2, f"{ex - fz:.2f}\nremoved\nby the grid", color=BAL, fontsize=17,
        va="center", ha="left", linespacing=1.05)
# today marker
ax.axvline(x_end, color="#c4ced8", lw=1.6, zorder=1)
ax.text(x_end - 0.3, 0.995, "observed", ha="right", va="top", fontsize=19, color=MUT)
ax.text(x_end + 0.3, 0.995, "projected", ha="left", va="top", fontsize=19, color=MUT)
y_today = float(r["North Sea"].dropna().iloc[-1])
ax.annotate(f"level today, {y_today:.2f}", xy=(x_end, y_today), xytext=(2027.6, 0.925),
            fontsize=19, color=INK, ha="left", va="center",
            arrowprops=dict(arrowstyle="-", color="#888888", lw=1.2))
ax.axhline(1.0, color=INK, lw=1.0, ls=(0, (2, 3)), alpha=0.6)
ax.text(2036.5, 1.008, "average market price", fontsize=17, color=MUT, va="bottom", ha="center")
ax.set_xlim(2016.9, 2047.5)
ax.set_ylim(0.4, 1.04)
ax.set_xticks([2017, 2020, 2024, 2030, 2040])
ax.set_yticks([0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0])
ax.set_ylabel("capture value", fontsize=21)
ax.yaxis.grid(True, color=GRID, lw=0.9)
ax.set_axisbelow(True)
ax.tick_params(labelsize=19)
legend = [Line2D([], [], color=NS, lw=4.2, label="North Sea"),
          Line2D([], [], color=BAL, lw=4.2, label="Baltic"),
          Line2D([], [], color="#666666", lw=3.4, ls="--", label="grid as today"),
          Line2D([], [], color="#666666", lw=3.4, ls=":", label="transmission expanded")]
ax.legend(handles=legend, frameon=False, loc="lower left", fontsize=18, ncol=2,
          handlelength=2.4, columnspacing=1.4, labelspacing=0.4)
fig.savefig(OUT / "fig_p_hero.png", dpi=220, facecolor="white")
json.dump({"today": round(y_today, 3)}, open(OUT / "hero_values.json", "w"))
print("saved fig_p_hero.png", f"{W_MM} x {H_MM} mm")
