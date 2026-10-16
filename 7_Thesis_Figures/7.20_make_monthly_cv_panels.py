"""
7.20_make_monthly_cv_panels.py — monthly capture value, North Sea vs Baltic,
across 2025 / 2030 / 2040 (supervisor request, 2026-06-22). Three panels, one per
horizon, each comparing the two basins month by month. Shows the seasonal capture
value going from flat today to a deep winter trough by 2040, the Baltic falling
furthest.

  2025 = observed monthly capture value, generation-weighted (monthly_cv_per_farm)
  2030, 2040 = monthly capture value from the solved PyPSA networks (NT-balticBaseline):
               offshore-generation-weighted zone price / monthly mean zone price.
Single weather year for the projections, so some month-to-month noise is weather.

Output -> results/fig_monthly_cv_panels.png, 10_Presentation/figures/, + monthly_cv_panels.csv
"""
import importlib.util, warnings
from pathlib import Path
import numpy as np, pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "7_Thesis_Figures" / "results"
DECK = ROOT / "10_Presentation" / "figures"
spec = importlib.util.spec_from_file_location("sur", ROOT / "1_PyPSA_Model/scripts/1.13_surrogate_runs.py")
sur = importlib.util.module_from_spec(spec); spec.loader.exec_module(sur)
import pypsa

NS = ["DE", "NL", "BE", "DK1", "FR"]; BAL = ["PL", "EE", "LV", "LT", "FI"]
C_NS, C_BAL = "#2471a3", "#c0392b"
MONTHS = ["J", "F", "M", "A", "M", "J", "J", "A", "S", "O", "N", "D"]


def observed_monthly(zones_basin):
    # within-month capture value = month captured price / that month's mean price
    # (the standard monthly capture value, as in monthly_cv_per_farm and Jacquet).
    cv = pd.read_csv(ROOT / "2_Regression_Model/data/cv_strandA/monthly_cv_per_farm.csv").dropna(subset=["CV", "gen_MWh_norm"])
    d = cv[(cv.basin == zones_basin) & (cv.year.isin([2023, 2024]))]
    return {m: np.average(g.CV, weights=g.gen_MWh_norm) for m, g in d.groupby("month")}


def network_monthly(path, zones):
    n = pypsa.Network(path)
    mon = pd.Series(n.snapshots).dt.month.values
    price, gen, g = n.buses_t.marginal_price, n.generators_t.p, n.generators
    num = np.zeros(len(n.snapshots)); den = np.zeros(len(n.snapshots)); pbuses = []
    for z in zones:
        buses = sur.zone_buses(n, z)
        ids = [i for i in g[(g.bus.isin(buses)) & (g.carrier.isin(sur.OFFSHORE))].index if i in gen.columns]
        pb = [b for b in buses if b in price.columns]; pbuses += pb
        if not ids or not pb:
            continue
        num += gen[ids].sum(axis=1).values * price[pb].mean(axis=1).values
        den += gen[ids].sum(axis=1).values
    price_h = price[list(set(pbuses))].mean(axis=1).values
    df = pd.DataFrame({"m": mon, "num": num, "den": den, "p": price_h})
    return {m: (d.num.sum() / d.den.sum()) / d.p.mean() for m, d in df.groupby("m") if d.den.sum() > 0}


NET = Path.home() / "pypsa-eur/results/scenarios_tyndp_v3"
data = {
    "2025": {"NS": observed_monthly("NS"), "Baltic": observed_monthly("Baltic")},
    "2030": {"NS": network_monthly(NET / "2030-NT-balticBaseline.nc", NS),
             "Baltic": network_monthly(NET / "2030-NT-balticBaseline.nc", BAL)},
    "2040": {"NS": network_monthly(NET / "2040-NT-balticBaseline.nc", NS),
             "Baltic": network_monthly(NET / "2040-NT-balticBaseline.nc", BAL)},
}

# tidy table out
rows = []
for hz in data:
    for b in ("NS", "Baltic"):
        for m in range(1, 13):
            rows.append(dict(horizon=hz, basin=b, month=m, CV=round(data[hz][b].get(m, np.nan), 3)))
pd.DataFrame(rows).to_csv(OUT / "monthly_cv_panels.csv", index=False)

def smooth(d):
    # circular 3-month centred moving average (seasonal cycle; removes single-year weather noise)
    y = np.array([d.get(m, np.nan) for m in range(1, 13)], float)
    ext = np.concatenate([y[-1:], y, y[:1]])
    return np.array([np.nanmean(ext[i:i + 3]) for i in range(12)])


fig, axes = plt.subplots(1, 3, figsize=(15.5, 5.6), sharey=True)
x = np.arange(1, 13)
for ax, hz in zip(axes, ["2025", "2030", "2040"]):
    for b, c in [("NS", C_NS), ("Baltic", C_BAL)]:
        y = smooth(data[hz][b])
        ax.plot(x, y, "o-", color=c, lw=2.4, ms=5.5, label=("North Sea" if b == "NS" else "Baltic"))
        w = np.nanmean([data[hz][b].get(m, np.nan) for m in (12, 1, 2)])
        s = np.nanmean([data[hz][b].get(m, np.nan) for m in (6, 7, 8)])
    ax.axvspan(0.5, 2.5, color="#cfe2f3", alpha=0.45, zorder=0)
    ax.axvspan(11.5, 12.5, color="#cfe2f3", alpha=0.45, zorder=0)
    ax.set_xticks(x); ax.set_xticklabels(MONTHS, fontsize=9)
    ax.set_title(hz, fontsize=14, fontweight="bold")
    ax.grid(alpha=0.3); ax.set_xlabel("month")
axes[0].set_ylim(0.35, 1.18)
for ax in axes:
    ax.axhline(1.0, color="#999", lw=0.8, ls=":", zorder=0)
axes[0].set_ylabel("Offshore-wind capture value (within-month)", fontsize=11)
axes[0].legend(fontsize=10, loc="lower left")
axes[0].text(1.5, 0.42, "winter", ha="center", fontsize=8, color="#1a5276", style="italic")
# annotate the winter collapse on the 2040 panel
wns = np.nanmean([data["2040"]["NS"].get(m) for m in (12, 1, 2)])
wba = np.nanmean([data["2040"]["Baltic"].get(m) for m in (12, 1, 2)])
axes[2].annotate(f"winter: NS {wns:.2f}, Baltic {wba:.2f}", (1.5, 0.30), ha="center",
                 fontsize=8.5, color="#b03a2e")

fig.suptitle("Monthly capture value by basin, 2025 to 2040",
             fontsize=13.5, y=0.98, color="#111")
fig.tight_layout(rect=[0, 0, 1, 0.94])
fig.savefig(OUT / "fig_monthly_cv_panels.png", dpi=185)
print("saved fig_monthly_cv_panels.png")
for hz in data:
    print(f"{hz}: NS winter {np.nanmean([data[hz]['NS'].get(m) for m in (12,1,2)]):.2f} summer "
          f"{np.nanmean([data[hz]['NS'].get(m) for m in (6,7,8)]):.2f} | "
          f"Baltic winter {np.nanmean([data[hz]['Baltic'].get(m) for m in (12,1,2)]):.2f} summer "
          f"{np.nanmean([data[hz]['Baltic'].get(m) for m in (6,7,8)]):.2f}")
