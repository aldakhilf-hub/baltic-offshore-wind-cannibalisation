"""Headline arc: observed capture value to 2024, then a forked projection to
2040 under National Trends (scheduled buildout): grid as today vs transmission
expanded, for both basins. Data: features_monthly (observed) and
grid_reversal_table.csv (projection, frozen and expanded)."""
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent

df = pd.read_csv(ROOT / "2_Regression_Model/data/features_strandA/features_monthly.csv")
df = df[df.bidding_zone != "GB"]
df = df[~((df.bidding_zone == "DE_LU") & (df.basin == "Baltic"))]
fy = df.groupby(["bidding_zone", "farm", "year"]).CV.mean().reset_index()
zy = fy.groupby(["bidding_zone", "year"]).CV.mean().reset_index()
GRP = {"DE_LU": "NS", "NL": "NS", "BE": "NS", "DK1": "NS", "FR": "NS",
       "PL": "UB", "EE": "UB", "LV": "UB", "LT": "UB"}
zy["g"] = zy.bidding_zone.map(GRP)
gm = zy[(zy.year >= 2019) & zy.g.notna()].groupby(["g", "year"]).CV.mean().reset_index()

rv = pd.read_csv(HERE / "results/grid_reversal_table.csv").set_index("year")
proj = {
    "NS":  {"frozen": [rv.loc[2030, "ns_frozen"],  rv.loc[2040, "ns_frozen"]],
            "exp":    [rv.loc[2030, "ns_opt"],     rv.loc[2040, "ns_opt"]]},
    "UB":  {"frozen": [rv.loc[2030, "bal_frozen"], rv.loc[2040, "bal_frozen"]],
            "exp":    [rv.loc[2030, "bal_opt"],    rv.loc[2040, "bal_opt"]]},
}

NS_BLUE, BALTIC_RED, MUT = "#2C5985", "#A63D40", "#5E7184"
matplotlib.rcParams.update({"font.size": 11, "axes.titlesize": 13,
    "axes.spines.top": False, "axes.spines.right": False})

fig, ax = plt.subplots(figsize=(9.8, 5.4), dpi=220)

label_nudge = {("NS", "exp"): -0.016, ("UB", "exp"): 0.016,
               ("NS", "frozen"): 0.0, ("UB", "frozen"): 0.0}
for g, col in [("NS", NS_BLUE), ("UB", BALTIC_RED)]:
    s = gm[gm.g == g].sort_values("year")
    ax.plot(s.year, s.CV, "-", color=col, lw=2.6, zorder=4)
    x0, y0 = s.year.values[-1], s.CV.values[-1]
    for kind, style in [("frozen", dict(ls="--", dashes=(5, 3))),
                        ("exp", dict(ls=":", dashes=(1.5, 2.2)))]:
        ys = proj[g][kind]
        ax.plot([x0, 2030, 2040], [y0] + ys, color=col, lw=2.5, zorder=4, **style)
        mfc = col if kind == "frozen" else "white"
        ax.plot(2040, ys[1], "o", color=col, mfc=mfc, mew=1.8, ms=7, zorder=5)
        ax.text(2040.5, ys[1] + label_nudge[(g, kind)], f"{ys[1]:.2f}",
                color=col, fontsize=11.5, va="center", fontweight="bold")

ax.axvline(2024.5, color="#c4ced8", lw=1.1, zorder=1)
ax.text(2024.2, 0.985, "observed", ha="right", va="top", fontsize=9.5, color=MUT)
ax.text(2024.9, 0.985, "projected", ha="left", va="top", fontsize=9.5, color=MUT)

ax.set_xlim(2018.6, 2043.0)
ax.set_ylim(0.28, 1.0)
ax.set_ylabel("Capture value")
ax.set_xticks([2019, 2024, 2030, 2040])
ax.yaxis.grid(True, color="#E3E3E3", lw=0.8)
ax.set_axisbelow(True)
ax.set_title("Observed and projected capture value, with and without grid expansion")

legend = [
    Line2D([], [], color=NS_BLUE, ls="--", lw=2.5, marker="o", ms=7,
           label="North Sea, grid as today"),
    Line2D([], [], color=NS_BLUE, ls=":", lw=2.5, marker="o", mfc="white",
           mew=1.8, ms=7, label="North Sea, transmission expanded"),
    Line2D([], [], color=BALTIC_RED, ls="--", lw=2.5, marker="o", ms=7,
           label="Baltic, grid as today"),
    Line2D([], [], color=BALTIC_RED, ls=":", lw=2.5, marker="o", mfc="white",
           mew=1.8, ms=7, label="Baltic, transmission expanded"),
]
ax.legend(handles=legend, frameon=False, loc="lower left", fontsize=10)

fig.tight_layout()
fig.savefig(ROOT / "9_Thesis_LaTeX/figures/fig_group_arc_simple.png", bbox_inches="tight")
print("saved", {g: {k: [round(v, 3) for v in vs] for k, vs in d.items()} for g, d in proj.items()})
