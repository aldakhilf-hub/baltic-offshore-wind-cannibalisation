"""
7.07_make_group_arc.py — the headline group-arc figure.

Capture value by zone group, from observed measurement into the 2040 projection,
in one view. Groups: North Sea, Baltic under-built (PL, EE, LV, LT), Baltic
built-out (DK2, SE4), Finland (nuclear, set aside). The under-built Baltic and
the North Sea start level; the buildout pulls the Baltic past the built-out
preview by 2040.

Observed: annual capture value per zone (VWF output x observed price), grouped.
Projection: PyPSA-Eur scenario aggregates (raw and bias-corrected) for the Baltic,
energy-weighted North Sea for reference.

Usage: python 7.07_make_group_arc.py   (env pypsa-eur-arm64)
"""
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
from matplotlib.lines import Line2D
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OUT = HERE / "results"
OUT.mkdir(exist_ok=True)

# ---- observed: annual capture value per zone, grouped ----
df = pd.read_csv(ROOT / "2_Regression_Model/data/features_strandA/features_monthly.csv")
df = df[df.bidding_zone != "GB"]
df = df[~((df.bidding_zone == "DE_LU") & (df.basin == "Baltic"))]   # drop German-priced Baltic
fy = df.groupby(["bidding_zone", "farm", "year"]).CV.mean().reset_index()
zy = fy.groupby(["bidding_zone", "year"]).CV.mean().reset_index()
GRP = {"DE_LU": "NS", "NL": "NS", "BE": "NS", "DK1": "NS", "FR": "NS",
       "PL": "UB", "EE": "UB", "LV": "UB", "LT": "UB",
       "DK2": "BO", "SE_4": "BO", "FI": "FI"}
zy["g"] = zy.bidding_zone.map(GRP)
gm = zy[zy.year >= 2019].groupby(["g", "year"]).CV.mean().reset_index()
ln = lambda g: (gm[gm.g == g].sort_values("year").year.values,
                gm[gm.g == g].sort_values("year").CV.values)
v24 = lambda g: zy[(zy.g == g) & (zy.year.isin([2023, 2024]))].CV.mean()

# ---- projection: PyPSA-Eur scenario aggregates ----
proj = pd.read_csv(ROOT / "1_PyPSA_Model/results/projections_v3/baltic_cv_fit_corrected.csv", index_col=0)
b30 = proj.loc[[s for s in proj.index if s.startswith("2030")]]
b40 = proj.loc[[s for s in proj.index if s.startswith("2040")]]
# Two distinct quantities, never mixed: the raw frozen-grid engine (the headline,
# matching the abstract and Table) and the bias correction (a refinement that
# deepens it). Each shown with its own exact range, raw primary, corrected hatched.
# centre lines = the CENTRAL scenario (NT baseline), matching the prose (0.47/0.57);
# bands = min-max across scenarios.
bal = {30: dict(raw_lo=b30.CV_raw.min(), raw_hi=b30.CV_raw.max(),
                raw_cen=proj.loc["2030-NT-balticBaseline", "CV_raw"],
                cor_lo=b30.CV_corr_fit.min(), cor_hi=b30.CV_corr_fit.max()),
       40: dict(raw_lo=b40.CV_raw.min(), raw_hi=b40.CV_raw.max(),
                raw_cen=proj.loc["2040-NT-balticBaseline", "CV_raw"],
                cor_lo=b40.CV_corr_fit.min(), cor_hi=b40.CV_corr_fit.max())}
zp = pd.read_csv(ROOT / "1_PyPSA_Model/results/projections_v3/projected_capture_values.csv")
ns = zp[(zp.region == "NorthSea") & (~zp.zone.isin(["GB", "NO"])) & (zp.energy_GWh > 0)]
nsp = {}
for yr in (2030, 2040):
    s = ns[ns.scenario == f"{yr}-NT-balticBaseline"]; w = s.energy_GWh
    nsp[yr] = (s.CV * w).sum() / w.sum()

NS, UB, BO, FIc, INK, MUT = "#2E6E9E", "#E0922F", "#9A3B1B", "#aab2b9", "#16293D", "#5E7184"
fig, ax = plt.subplots(figsize=(11.5, 6.2), dpi=200)

for g, c in [("BO", BO)]:                         # context group, faint
    x, y = ln(g); ax.plot(x, y, "-", color=c, lw=1.5, alpha=0.5, zorder=2)
for g, c in [("NS", NS), ("UB", UB)]:            # headline groups, bold
    x, y = ln(g); ax.plot(x, y, "-", color=c, lw=2.9, zorder=4)
# Finland set aside, not plotted: Olkiluoto-3 nuclear (online 2023) collapses its
# capture value for reasons unrelated to wind cannibalisation. Noted, not drawn,
# so it does not visually compete with the result.
ax.text(2019.0, 0.62, "Finland set aside (Olkiluoto-3)",
        fontsize=8.5, color=MUT, va="top", zorder=2)

ax.axvline(2024.5, color="#c4ced8", lw=1.1, zorder=1)
ns24, ub24 = v24("NS"), v24("UB")
ax.plot([2024.5, 2030, 2040], [ns24, nsp[2030], nsp[2040]], "--", color=NS, lw=2.9, zorder=4)
ax.scatter([2040], [nsp[2040]], color=NS, s=42, zorder=5)
yr = [2024.5, 2030, 2040]
# headline = the raw frozen-grid engine: primary shaded band + dashed central line
ax.fill_between(yr, [ub24, bal[30]["raw_lo"], bal[40]["raw_lo"]],
                [ub24, bal[30]["raw_hi"], bal[40]["raw_hi"]], color=UB, alpha=0.22, zorder=3)
ax.plot(yr, [ub24, bal[30]["raw_cen"], bal[40]["raw_cen"]], "--", color=UB, lw=2.9, zorder=4)
# bias correction = a refinement: a lower hatched band, deepening but not changing the story
ax.fill_between(yr, [ub24, bal[30]["cor_lo"], bal[40]["cor_lo"]],
                [ub24, bal[30]["cor_hi"], bal[40]["cor_hi"]],
                facecolor="none", edgecolor=UB, hatch="////", alpha=0.5, lw=0.0, zorder=2)
ax.plot([2019, 2040.3], [v24("BO"), v24("BO")], ":", color=BO, lw=1.5, alpha=0.8, zorder=1)

ax.text(2040.5, nsp[2040], f"{nsp[2040]:.2f}", color=NS, fontsize=12, va="center")
ax.text(2040.55, bal[40]["raw_cen"], f"raw {bal[40]['raw_lo']:.2f}-{bal[40]['raw_hi']:.2f}",
        color="#B5701A", fontsize=11, va="center")
ax.text(2040.55, bal[40]["cor_lo"], f"corrected {bal[40]['cor_lo']:.2f}-{bal[40]['cor_hi']:.2f}",
        color=MUT, fontsize=9, va="top")
ax.text(2040.3, v24("BO") + 0.02, "DK2 / SE4 today", color=BO, fontsize=10, va="bottom", ha="right", alpha=0.9)

ax.set_xticks([2020, 2024, 2030, 2040]); ax.set_xlim(2018.9, 2043.5); ax.set_ylim(0.24, 1.0)
ax.set_ylabel("Offshore capture value", fontsize=12.5); ax.set_xlabel("Year", fontsize=12)
ax.set_title("Offshore capture value by zone group, observed and projected to 2040",
             fontsize=13, color="#111", pad=12)
ax.grid(axis="y", alpha=0.22); ax.set_axisbelow(True)
for s in ["top", "right"]:
    ax.spines[s].set_visible(False)
from matplotlib.patches import Patch
leg = [Line2D([0], [0], color=NS, lw=2.9, label="North Sea"),
       Line2D([0], [0], color=UB, lw=2.9, label="Baltic, under-built (PL, EE, LV, LT), raw"),
       Patch(facecolor="none", edgecolor=UB, hatch="////", label="Baltic, bias-corrected"),
       Line2D([0], [0], color=BO, lw=1.5, alpha=0.6, label="Baltic, built-out (DK2, SE4)")]
ax.legend(handles=leg, fontsize=10, loc="lower left", framealpha=0.92)
plt.tight_layout()
fig.savefig(OUT / "fig_group_arc.png", dpi=200, facecolor="white", bbox_inches="tight")
print("observed 2023-24:", {g: round(v24(g), 3) for g in ["NS", "UB", "BO", "FI"]})
print(f"Saved -> {OUT}/fig_group_arc.png")

# ---- observed-only variant for the measured-record section (no projection) ----
fig2, ax2 = plt.subplots(figsize=(9.5, 5.2), dpi=200)
for g, c, lw, al in [("BO", BO, 1.8, 0.75), ("NS", NS, 2.9, 1.0), ("UB", UB, 2.9, 1.0)]:
    x, y = ln(g)
    ax2.plot(x, y, "-", color=c, lw=lw, alpha=al, zorder=3)
ax2.text(2019.0, 0.79, "Finland set aside (Olkiluoto-3)", fontsize=8.5, color=MUT,
         va="top", zorder=2)
ax2.set_xticks([2019, 2020, 2021, 2022, 2023, 2024])
ax2.set_xlim(2018.8, 2024.4); ax2.set_ylim(0.70, 1.0)
ax2.set_ylabel("Offshore capture value", fontsize=12)
ax2.set_xlabel("Year", fontsize=11.5)
ax2.set_title("Offshore capture value by zone group, observed 2019 to 2024",
              fontsize=13, color="#111", pad=10)
ax2.grid(axis="y", alpha=0.22); ax2.set_axisbelow(True)
for s in ["top", "right"]:
    ax2.spines[s].set_visible(False)
leg2 = [Line2D([0], [0], color=NS, lw=2.9, label="North Sea"),
        Line2D([0], [0], color=UB, lw=2.9, label="Baltic, under-built (PL, EE, LV, LT)"),
        Line2D([0], [0], color=BO, lw=1.8, alpha=0.75, label="Baltic, built-out (DK2, SE4)")]
ax2.legend(handles=leg2, fontsize=10, loc="lower left", framealpha=0.92)
plt.tight_layout()
fig2.savefig(OUT / "fig_group_arc_observed.png", dpi=200, facecolor="white",
             bbox_inches="tight")
print(f"Saved -> {OUT}/fig_group_arc_observed.png")
