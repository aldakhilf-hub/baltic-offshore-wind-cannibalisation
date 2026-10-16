"""
7.16_make_grid_reversal_and_convergence.py

Two supervisor questions (2026-06-22):
  (Q5) "Even if you build optimal capacity, does the Baltic still erode faster
        than the North Sea?"  -> fig_grid_reversal.png
  (Q3) "Decompose into built-out vs under-built Baltic; at some point they merge."
        -> fig_baltic_convergence.png

Both read offshore capture value straight from the solved PyPSA networks
(frozen grid = scenarios_tyndp_v3, optimal grid = ..._vopt), central NT
balticBaseline. Present (2025) is the observed generation-weighted value.

Output -> results/ + 10_Presentation/figures/ + grid_reversal_table.csv
"""
import importlib.util, warnings
from pathlib import Path
import numpy as np, pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patheffects as pe
warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "7_Thesis_Figures" / "results"
DECK = ROOT / "10_Presentation" / "figures"
FROZEN = Path.home() / "pypsa-eur/results/scenarios_tyndp_v3"
VOPT = Path.home() / "pypsa-eur/results/scenarios_tyndp_v3_vopt"
HALO = [pe.withStroke(linewidth=2.4, foreground="white")]

spec = importlib.util.spec_from_file_location("sur", ROOT / "1_PyPSA_Model/scripts/1.13_surrogate_runs.py")
sur = importlib.util.module_from_spec(spec); spec.loader.exec_module(sur)
import pypsa

NS = ["DE", "NL", "BE", "DK1", "FR"]
BAL = ["PL", "EE", "LV", "LT"]   # enclosed Baltic; Finland excluded (nuclear-driven outlier)
BUILT = ["DK2"]          # the built-out Baltic preview (also SE4, not in projection)


def cv(path, zones):
    n = pypsa.Network(path)
    d = pd.DataFrame([dict(sur.offshore_capture(n, z), zone=z) for z in zones])
    d = d[d.energy_GWh > 0].dropna(subset=["CV_raw"])
    if d.empty:
        return np.nan
    return float((d.CV_raw * d.energy_GWh).sum() / d.energy_GWh.sum())


# present (2025) observed, generation-weighted 2023-24
obs = pd.read_csv(ROOT / "2_Regression_Model/data/cv_strandA/monthly_cv_per_farm.csv")
obs["z"] = obs.bidding_zone.map({"DE_LU": "DE", "DK_1": "DK1", "DK_2": "DK2", "SE_4": "SE4"}).fillna(obs.bidding_zone)
o = obs[obs.year.isin([2023, 2024])].dropna(subset=["CV", "gen_MWh_norm"])
def obs_cv(zs):
    d = o[o.z.isin(zs)]
    return float((d.CV * d.gen_MWh_norm).sum() / d.gen_MWh_norm.sum())

pres_ns, pres_bal, pres_built = obs_cv(NS), obs_cv(BAL), obs_cv(BUILT)

rows = []
for y in [2030, 2040]:
    fr = FROZEN / f"{y}-NT-balticBaseline.nc"
    vo = VOPT / f"{y}-NT-balticBaseline.nc"
    rows.append(dict(year=y, ns_frozen=cv(fr, NS), bal_frozen=cv(fr, BAL),
                     ns_opt=cv(vo, NS), bal_opt=cv(vo, BAL),
                     underbuilt_frozen=cv(fr, BAL), underbuilt_opt=cv(vo, BAL),
                     built_frozen=cv(fr, BUILT), built_opt=cv(vo, BUILT)))
T = pd.DataFrame(rows)
T.to_csv(OUT / "grid_reversal_table.csv", index=False)
print(T.round(3).to_string(index=False))

yrs = [2025, 2030, 2040]
C_NS, C_BAL = "#2471a3", "#c0392b"

# ---------- Figure 1: the grid reversal ----------
fig, ax = plt.subplots(figsize=(9.2, 6.0))
ns_fr = [pres_ns] + list(T.ns_frozen); bal_fr = [pres_bal] + list(T.bal_frozen)
ns_op = [pres_ns] + list(T.ns_opt); bal_op = [pres_bal] + list(T.bal_opt)
ax.plot(yrs, ns_fr, "o-", color=C_NS, lw=2.4, ms=7, label="North Sea, frozen grid")
ax.plot(yrs, bal_fr, "o-", color=C_BAL, lw=2.4, ms=7, label="Baltic, frozen grid")
ax.plot(yrs, ns_op, "s--", color=C_NS, lw=2.0, ms=6, mfc="white", label="North Sea, optimal grid")
ax.plot(yrs, bal_op, "s--", color=C_BAL, lw=2.0, ms=6, mfc="white", label="Baltic, optimal grid")
ax.scatter([2025], [pres_ns], s=120, color="#555", zorder=6)
ax.annotate("parity today\n~0.89", (2025, pres_ns), xytext=(2025.1, 0.93),
            fontsize=9, color="#555", ha="left")
ax.set_xticks(yrs); ax.set_ylim(0.3, 1.0)
ax.set_ylabel("Offshore-wind capture value", fontsize=11)
ax.set_title("Capture value to 2040 under frozen and optimal grids",
             fontsize=13, color="#111")
ax.legend(fontsize=9, loc="lower left"); ax.grid(alpha=0.3)
fig.tight_layout()
fig.savefig(OUT / "fig_grid_reversal.png", dpi=190)
plt.close(fig)
print("saved fig_grid_reversal.png")

# ---------- Figure 2: built-out vs under-built convergence ----------
fig, ax = plt.subplots(figsize=(9.2, 6.0))
ub = [pres_bal] + list(T.underbuilt_frozen)
bt = [pres_built] + list(T.built_frozen)
ax.plot(yrs, ub, "o-", color=C_BAL, lw=2.6, ms=8, label="Under-built Baltic (PL, EE, LV, LT)")
ax.plot(yrs, bt, "D-", color="#7d3c98", lw=2.4, ms=7, label="Built-out Baltic (DK2)")
ax.plot(yrs, [pres_ns] + list(T.ns_frozen), "o:", color=C_NS, lw=1.6, ms=5,
        alpha=0.7, label="North Sea (reference)")
# convergence shading between the two Baltic lines
ax.fill_between(yrs, ub, bt, color="#d2b4de", alpha=0.35)
ax.set_xticks(yrs); ax.set_ylim(0.3, 1.0)
ax.set_ylabel("Offshore-wind capture value (frozen grid)", fontsize=11)
ax.set_title("Under-built Baltic zones and built-out DK2, frozen grid",
             fontsize=12.5, color="#111")
ax.legend(fontsize=9, loc="lower left"); ax.grid(alpha=0.3)
fig.tight_layout()
fig.savefig(OUT / "fig_baltic_convergence.png", dpi=190)
plt.close(fig)
print("saved fig_baltic_convergence.png")
print(f"\npresent: NS {pres_ns:.3f}  under-built Baltic {pres_bal:.3f}  built-out DK2 {pres_built:.3f}")
