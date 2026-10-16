"""Poster figures for the A1 conference poster (Imperial template).

Every figure is drawn at the physical size of the slot it occupies on the
sheet, so a 20 pt label in this script prints at 20 pt on the poster.
Colours follow the Imperial theme: North Sea navy (#000080), Baltic
orange-red (#FF4500). No titles inside the figures; the poster headings do
that job.
"""
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "12_Poster/figures"
OUT.mkdir(parents=True, exist_ok=True)
FIG = ROOT / "7_Thesis_Figures"

NS, BAL = "#000080", "#FF4500"
GREY, INK, MUT, GRID = "#C9CED8", "#222222", "#5B6170", "#E3E3E3"
MM = 1 / 25.4

plt.rcParams.update({
    "font.family": "Arial", "font.size": 18,
    "axes.edgecolor": "#444444", "axes.linewidth": 1.2,
    "axes.spines.top": False, "axes.spines.right": False,
    "xtick.labelsize": 18, "ytick.labelsize": 18, "axes.labelsize": 20,
    "legend.fontsize": 18, "figure.dpi": 110,
})


def save(fig, name):
    fig.savefig(OUT / name, dpi=220, facecolor="white")
    w, h = fig.get_size_inches()
    plt.close(fig)
    print(f"saved {name}: {w*25.4:.0f} x {h*25.4:.0f} mm")


# ---------------------------------------------------------------- 1. mechanism
def mechanism():
    """Merit-order schematic: the same demand met with one wind farm and with
    many wind farms producing in the same hour."""
    fig, axes = plt.subplots(1, 2, figsize=(268 * MM, 52 * MM), layout="constrained",
                             sharey=True)
    thermal = [(3.0, 15, "#9AA3B5"), (3.0, 50, "#7C8698"), (4.0, 100, "#5E687A"),
               (2.0, 150, "#3F4858")]
    demand = 9.0
    for ax, wind, price in [(axes[0], 1.5, 100), (axes[1], 5.0, 50)]:
        x = 0.0
        ax.bar(x, 10, width=wind, align="edge", color=NS if wind < 2 else BAL, lw=0)
        ax.text(x + wind / 2, 13, "wind", ha="center", va="bottom", fontsize=16,
                color=NS if wind < 2 else BAL, fontweight="bold")
        x += wind
        for cap, p, col in thermal:
            ax.bar(x, p, width=cap, align="edge", color=col, lw=0)
            x += cap
        ax.axvline(demand, color=INK, lw=2.0, ls="-", ymax=0.84)
        ax.text(demand, 192, "demand", fontsize=16, color=INK, va="top", ha="center")
        ax.plot([0, demand], [price, price], color=INK, lw=1.4, ls="--")
        ax.text(0.2, price + 6, f"price {price}", fontsize=18, fontweight="bold",
                color=INK, va="bottom")
        ax.set_xlim(0, 13.5)
        ax.set_ylim(0, 195)
        ax.set_xticks([])
        ax.set_yticks([0, 50, 100])
        ax.set_xlabel("supply, cheapest first", fontsize=16)
        ax.tick_params(axis="y", labelsize=16)
    axes[0].set_ylabel("price", fontsize=16)
    save(fig, "fig_p_mechanism.png")


# ---------------------------------------------------------------- 2. observed
def observed():
    """Observed monthly capture value per sea, 2017 to 2024: monthly mean of the
    farms (thin) and a centred 12-month mean (thick)."""
    # same panel and filters as the arc (thesis panel of record)
    df = pd.read_csv(ROOT / "2_Regression_Model/data/features_strandA/features_monthly.csv")
    df = df[df.bidding_zone != "GB"]
    df = df[~((df.bidding_zone == "DE_LU") & (df.basin == "Baltic"))]
    grp = {"DE_LU": "North Sea", "NL": "North Sea", "BE": "North Sea", "DK1": "North Sea",
           "FR": "North Sea", "PL": "Baltic", "EE": "Baltic", "LV": "Baltic", "LT": "Baltic"}
    df["sea"] = df.bidding_zone.map(grp)
    df = df[df.sea.notna()].copy()
    df["date"] = pd.to_datetime(dict(year=df.year, month=df.month, day=1))
    print("farms used:", df.farm.nunique(), "| zones:", sorted(df.bidding_zone.unique()))
    # monthly mean over zones (each zone first averaged over its farms), then over the sea
    zm = df.groupby(["sea", "bidding_zone", "date"]).CV.mean().reset_index()
    m = zm.groupby(["sea", "date"]).CV.mean().unstack(0).sort_index()
    # trailing 24-month mean: its last value is the 2023-24 mean, the poster's 'today'
    r = m.rolling(24, min_periods=12).mean()
    for sea in ["North Sea", "Baltic"]:
        s = r[sea].dropna()
        print(f"  {sea}: 24-month mean {s.iloc[0]:.3f} ({s.index[0]:%Y-%m}) -> "
              f"{s.iloc[-1]:.3f} ({s.index[-1]:%Y-%m}); monthly mean 2017={m[sea][m.index.year==2017].mean():.3f}")
    import json
    json.dump({sea: [float(r[sea].dropna().iloc[0]), float(r[sea].dropna().iloc[-1])]
               for sea in ["North Sea", "Baltic"]}, open(OUT / "observed_values.json", "w"))
    fig, ax = plt.subplots(figsize=(268 * MM, 62 * MM), layout="constrained")
    for sea, col in [("North Sea", NS), ("Baltic", BAL)]:
        ax.plot(m.index, m[sea], color=col, lw=1.0, alpha=0.35)
        ax.plot(r.index, r[sea], color=col, lw=3.2, label=f"{sea}, 24-month mean")
    ax.axhline(1.0, color=INK, lw=1.2, ls="--")
    ax.text(m.index[0], 1.012, "average market price", fontsize=15, color=INK, va="bottom")
    ax.set_ylim(0.55, 1.08)
    ax.set_yticks([0.6, 0.8, 1.0])
    ax.set_ylabel("capture value", fontsize=18)
    ax.yaxis.grid(True, color=GRID, lw=0.8)
    ax.set_axisbelow(True)
    ax.tick_params(labelsize=16)
    ax.legend(frameon=False, loc="lower left", ncol=2, fontsize=16, handlelength=1.6)
    save(fig, "fig_p_observed.png")


# ---------------------------------------------------------------- 3. hero arc
def arc():
    """Observed capture value to 2024, then the projection to 2040 with the grid
    as today and with transmission expanded, both seas."""
    df = pd.read_csv(ROOT / "2_Regression_Model/data/features_strandA/features_monthly.csv")
    df = df[df.bidding_zone != "GB"]
    df = df[~((df.bidding_zone == "DE_LU") & (df.basin == "Baltic"))]
    fy = df.groupby(["bidding_zone", "farm", "year"]).CV.mean().reset_index()
    zy = fy.groupby(["bidding_zone", "year"]).CV.mean().reset_index()
    grp = {"DE_LU": "NS", "NL": "NS", "BE": "NS", "DK1": "NS", "FR": "NS",
           "PL": "UB", "EE": "UB", "LV": "UB", "LT": "UB"}
    zy["g"] = zy.bidding_zone.map(grp)
    gm = zy[(zy.year >= 2019) & zy.g.notna()].groupby(["g", "year"]).CV.mean().reset_index()
    rv = pd.read_csv(FIG / "results/grid_reversal_table.csv").set_index("year")
    proj = {"NS": {"frozen": [rv.loc[2030, "ns_frozen"], rv.loc[2040, "ns_frozen"]],
                   "exp": [rv.loc[2030, "ns_opt"], rv.loc[2040, "ns_opt"]]},
            "UB": {"frozen": [rv.loc[2030, "bal_frozen"], rv.loc[2040, "bal_frozen"]],
                   "exp": [rv.loc[2030, "bal_opt"], rv.loc[2040, "bal_opt"]]}}
    for g in ["NS", "UB"]:
        s = gm[gm.g == g].sort_values("year")
        print(f"  arc {g}: observed {s.year.values[0]}={s.CV.values[0]:.3f} ... "
              f"{s.year.values[-1]}={s.CV.values[-1]:.3f}; 2040 frozen {proj[g]['frozen'][1]:.3f}, "
              f"expanded {proj[g]['exp'][1]:.3f}")

    fig, ax = plt.subplots(figsize=(270 * MM, 84 * MM), layout="constrained")
    nudge = {("NS", "exp"): -0.018, ("UB", "exp"): 0.018, ("NS", "frozen"): 0.0, ("UB", "frozen"): 0.0}
    for g, col in [("NS", NS), ("UB", BAL)]:
        s = gm[gm.g == g].sort_values("year")
        ax.plot(s.year, s.CV, "-", color=col, lw=4.0, zorder=4)
        x0, y0 = s.year.values[-1], s.CV.values[-1]
        for kind, style in [("frozen", dict(ls="--", dashes=(5, 3))),
                            ("exp", dict(ls=":", dashes=(1.5, 2.2)))]:
            ys = proj[g][kind]
            ax.plot([x0, 2030, 2040], [y0] + ys, color=col, lw=3.6, zorder=4, **style)
            mfc = col if kind == "frozen" else "white"
            ax.plot(2040, ys[1], "o", color=col, mfc=mfc, mew=2.6, ms=13, zorder=5)
            ax.text(2040.6, ys[1] + nudge[(g, kind)], f"{ys[1]:.2f}", color=col,
                    fontsize=21, va="center", fontweight="bold")
    ax.axvline(2024.5, color="#c4ced8", lw=1.6, zorder=1)
    ax.text(2024.15, 0.985, "observed", ha="right", va="top", fontsize=16, color=MUT)
    ax.text(2024.85, 0.985, "projected", ha="left", va="top", fontsize=16, color=MUT)
    ax.set_xlim(2018.6, 2043.5)
    ax.set_ylim(0.38, 1.0)
    ax.set_yticks([0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0])
    ax.set_ylabel("capture value")
    ax.set_xticks([2019, 2024, 2030, 2040])
    ax.yaxis.grid(True, color=GRID, lw=0.9)
    ax.set_axisbelow(True)
    legend = [
        Line2D([], [], color=NS, lw=3.6, label="North Sea, observed"),
        Line2D([], [], color=NS, ls="--", lw=3.6, marker="o", ms=11, label="North Sea, grid as today"),
        Line2D([], [], color=NS, ls=":", lw=3.6, marker="o", mfc="white", mew=2.4, ms=11,
               label="North Sea, transmission expanded"),
        Line2D([], [], color=BAL, lw=3.6, label="Baltic, observed"),
        Line2D([], [], color=BAL, ls="--", lw=3.6, marker="o", ms=11, label="Baltic, grid as today"),
        Line2D([], [], color=BAL, ls=":", lw=3.6, marker="o", mfc="white", mew=2.4, ms=11,
               label="Baltic, transmission expanded"),
    ]
    ax.legend(handles=legend, frameon=False, loc="lower left", ncol=2, fontsize=13.5,
              handlelength=2.2, columnspacing=1.0, labelspacing=0.3)
    save(fig, "fig_p_arc.png")


# ---------------------------------------------------------------- 4. decomposition
def decomposition():
    """Where the 2040 loss comes from: value kept with today's grid, the part
    lost to grid congestion (removed by transmission), and the part lost to the
    buildout itself. Bars sum to today's capture value."""
    D = pd.read_csv(FIG / "results/cv_decomposition_table.csv").set_index("basin")
    fig, ax = plt.subplots(figsize=(270 * MM, 42 * MM), layout="constrained")
    H = 0.56
    for y, (b, col) in zip([1, 0], [("North Sea", NS), ("Baltic", BAL)]):
        f, cg, st = D.loc[b, ["frozen", "congestion", "structural"]]
        ax.barh(y, f, height=H, color=col, lw=0)
        ax.barh(y, cg, left=f, height=H, color="white", edgecolor=col, hatch="////", lw=1.5)
        ax.barh(y, st, left=f + cg, height=H, color=GREY, lw=0)
        ax.text(f / 2, y, f"{f:.2f}", ha="center", va="center", color="white",
                fontsize=20, fontweight="bold")
        ax.text(f + cg / 2, y, f"{cg:.2f}", ha="center", va="center", color=col,
                fontsize=18, fontweight="bold")
        ax.text(f + cg + st / 2, y, f"{st:.2f}", ha="center", va="center", color=INK,
                fontsize=18, fontweight="bold")
        total = round(f, 2) + round(cg, 2) + round(st, 2)
        ax.text(f + cg + st + 0.012, y, f"{total:.2f} today", ha="left", va="center",
                color=INK, fontsize=16)
        print(f"  {b}: kept {f:.3f}, congestion {cg:.3f}, buildout {st:.3f}, today {f+cg+st:.3f}")
    ax.set_yticks([1, 0])
    ax.set_yticklabels(["North Sea", "Baltic"], fontsize=18, fontweight="bold")
    ax.set_xlim(0, 1.0)
    ax.set_xticks([0, 0.2, 0.4, 0.6, 0.8, 1.0])
    ax.set_xlabel("capture value, 2040", fontsize=16)
    ax.tick_params(axis="x", labelsize=15)
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0)
    handles = [Patch(facecolor="#555555", label="kept in 2040, today's grid"),
               Patch(facecolor="white", edgecolor="#555555", hatch="////",
                     label="lost to grid congestion"),
               Patch(facecolor=GREY, label="lost to the buildout itself")]
    ax.legend(handles=handles, frameon=False, loc="upper center", bbox_to_anchor=(0.5, 1.36),
              ncol=3, fontsize=13.5, handlelength=1.5, columnspacing=1.2)
    save(fig, "fig_p_decomposition.png")


if __name__ == "__main__":
    mechanism()
    observed()
    arc()
    decomposition()
