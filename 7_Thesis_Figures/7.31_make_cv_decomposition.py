"""
7.31_make_cv_decomposition.py

Supervisor ask #3: "removing the grid constraint, why is CV going down, congestion
vs closed?" Decompose each basin's 2040 capture-value fall into two physical parts:

  CONGESTION (grid-removable) = optimal-grid CV  -  frozen-grid CV
  STRUCTURAL  (buildout, not grid-fixable) = today's CV  -  optimal-grid CV
  total fall = today  -  frozen = structural + congestion

Read straight from the solved PyPSA networks (frozen = scenarios_tyndp_v3, optimal
= ..._vopt), central NT balticBaseline, energy-weighted CV_raw, exactly as 7.16/7.30.
Present (2023-24) is observed. Baltic = PL, EE, LV, LT, the enclosed Baltic with Finland excluded
everywhere (nuclear-driven outlier set aside; matches 7.16). Both basins then start at true parity
(~0.89), so this decomposes the same 0.89 -> 0.47 (frozen) / 0.66 (optimal) line the grid figure shows.

Output -> results/ + 10_Presentation/figures/ + cv_decomposition_table.csv
"""
import importlib.util, warnings
from pathlib import Path
import numpy as np, pandas as pd, pypsa
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patheffects as pe
warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "7_Thesis_Figures" / "results"
DECK = ROOT / "10_Presentation" / "figures"
FROZEN = Path.home() / "pypsa-eur/results/scenarios_tyndp_v3/2040-NT-balticBaseline.nc"
VOPT = Path.home() / "pypsa-eur/results/scenarios_tyndp_v3_vopt/2040-NT-balticBaseline.nc"
HALO = [pe.withStroke(linewidth=2.2, foreground="white")]
DARKHALO = [pe.withStroke(linewidth=2.6, foreground="#1b2a36")]

spec = importlib.util.spec_from_file_location("sur", ROOT / "1_PyPSA_Model/scripts/1.13_surrogate_runs.py")
sur = importlib.util.module_from_spec(spec); spec.loader.exec_module(sur)

NS = ["DE", "NL", "BE", "DK1", "FR"]
BAL = ["PL", "EE", "LV", "LT"]   # enclosed Baltic; Finland excluded (nuclear-driven outlier)


def agg(path, zones):
    n = pypsa.Network(path)
    d = pd.DataFrame([dict(sur.offshore_capture(n, z), zone=z) for z in zones])
    d = d[d.energy_GWh > 0].dropna(subset=["CV_raw"])
    return float((d.CV_raw * d.energy_GWh).sum() / d.energy_GWh.sum())


# present (2023-24) observed, generation-weighted
obs = pd.read_csv(ROOT / "2_Regression_Model/data/cv_strandA/monthly_cv_per_farm.csv")
obs["z"] = obs.bidding_zone.map({"DE_LU": "DE", "DK_1": "DK1", "DK_2": "DK2", "SE_4": "SE4"}).fillna(obs.bidding_zone)
o = obs[obs.year.isin([2023, 2024])].dropna(subset=["CV", "gen_MWh_norm"])
def ocv(zs):
    d = o[o.z.isin(zs)]
    return float((d.CV * d.gen_MWh_norm).sum() / d.gen_MWh_norm.sum())

BASINS = ["North Sea", "Baltic"]
ZONES = {"North Sea": NS, "Baltic": BAL}
pres = {b: ocv(ZONES[b]) for b in BASINS}
opt = {b: agg(VOPT, ZONES[b]) for b in BASINS}
froz = {b: agg(FROZEN, ZONES[b]) for b in BASINS}

rows = []
for b in BASINS:
    t, op, f = pres[b], opt[b], froz[b]
    rows.append(dict(basin=b, today=t, optimal=op, frozen=f, total_fall=t - f,
                     structural=t - op, congestion=op - f,
                     struct_pct=round((t - op) / (t - f) * 100), cong_pct=round((op - f) / (t - f) * 100)))
D = pd.DataFrame(rows)
D.to_csv(OUT / "cv_decomposition_table.csv", index=False)
print(D.round(3).to_string(index=False))
bc, nc = D.set_index("basin").congestion["Baltic"], D.set_index("basin").congestion["North Sea"]
bs, ns_ = D.set_index("basin").structural["Baltic"], D.set_index("basin").structural["North Sea"]
print(f"\nBaltic congestion {bc:.3f} = {bc/nc:.1f}x North Sea {nc:.3f}; "
      f"Baltic structural {bs:.3f} {'<' if bs<ns_ else '>'} North Sea {ns_:.3f}")
print(f"Optimal-grid 2040: Baltic {opt['Baltic']:.3f} vs North Sea {opt['North Sea']:.3f} "
      f"({'ABOVE' if opt['Baltic']>opt['North Sea'] else 'below'}) -> the reversal")

# ---------------- figure: two-panel waterfall ----------------
C_STR, C_CON = "#2471a3", "#e67e22"      # structural (blue) vs congestion (orange)
C_TODAY, C_FROZ = "#95a5a6", "#34495e"
W = 0.64
fig, axes = plt.subplots(1, 2, figsize=(11.6, 6.4), sharey=True)
for ax, b in zip(axes, BASINS):
    t, op, f = pres[b], opt[b], froz[b]
    st, cg, tot = t - op, op - f, t - f
    ax.bar(0, t, W, color=C_TODAY, zorder=3)
    ax.bar(1, st, W, bottom=op, color=C_STR, zorder=3)
    ax.bar(2, cg, W, bottom=f, color=C_CON, zorder=3)
    ax.bar(3, f, W, color=C_FROZ, zorder=3)
    # waterfall connectors
    ax.plot([0 + W / 2, 1 - W / 2], [t, t], color="#666", lw=0.9, ls="--", zorder=2)
    ax.plot([1 + W / 2, 2 - W / 2], [op, op], color="#666", lw=0.9, ls="--", zorder=2)
    ax.plot([2 + W / 2, 3 - W / 2], [f, f], color="#666", lw=0.9, ls="--", zorder=2)
    # optimal-grid level marker
    ax.plot([1 - W / 2, 3 + W / 2], [op, op], color="#1e7d34", lw=1.1, ls=":", zorder=1, alpha=0.85)
    ax.text(2.35, op + 0.012, f"optimal-grid CV  {op:.2f}", fontsize=8.4, color="#1e7d34",
            va="bottom", ha="center")
    # anchor value labels
    ax.text(0, t + 0.015, f"{t:.2f}", ha="center", fontsize=11, fontweight="bold", color="#2c3e50")
    ax.text(3, f + 0.015, f"{f:.2f}", ha="center", fontsize=11, fontweight="bold", color="#2c3e50")
    # segment labels
    ax.text(1, op + st / 2, f"-{st:.2f}\n{st/tot*100:.0f}%", ha="center", va="center",
            fontsize=10.5, fontweight="bold", color="white", path_effects=DARKHALO)
    ax.text(2, f + cg / 2, f"-{cg:.2f}\n{cg/tot*100:.0f}%", ha="center", va="center",
            fontsize=10.5, fontweight="bold", color="white", path_effects=DARKHALO)
    ax.set_xticks([0, 1, 2, 3])
    ax.set_xticklabels(["2023-24\ntoday", "buildout\n(structural)", "congestion\n(grid)", "2040\nfrozen"], fontsize=9)
    ax.set_title(f"{b}, {t:.2f} to {f:.2f}", fontsize=12, color="#111")
    ax.set_ylim(0, 1.0); ax.grid(axis="y", alpha=0.25)
    ax.margins(x=0.12)
axes[0].set_ylabel("Offshore-wind capture value", fontsize=11)
# legend
from matplotlib.patches import Patch
fig.legend([Patch(fc=C_STR), Patch(fc=C_CON)],
           ["Structural component (buildout)",
            "Congestion component (grid)"],
           loc="lower center", ncol=2, fontsize=9.5, frameon=False, bbox_to_anchor=(0.5, -0.01))
fig.suptitle("Decomposition of the 2023-24 to 2040 capture-value fall",
             fontsize=13.5, y=0.98, color="#111")
fig.subplots_adjust(top=0.89, bottom=0.13, wspace=0.08)
fig.savefig(OUT / "fig_cv_decomposition.png", dpi=190)
plt.close(fig)
print("saved fig_cv_decomposition.png")
