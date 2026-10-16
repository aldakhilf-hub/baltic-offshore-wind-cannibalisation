"""
7.19_make_seasonal_generation.py — the seasonal generation profile and how it
drives the capture-value erosion (supervisor slide-21: "average generation
profile / avg wind speed… during winter you get most the revenue, explains cv
going down? decompose, link to capture value, how it links to forecasting").

Finding: generation is strongly winter-peaked in both basins (capacity factor
~0.70 winter vs ~0.44 summer, driven by ~11-12 m/s winter winds vs ~7 m/s
summer). Today capture value is FLAT across seasons. By 2040, with the buildout,
the erosion is concentrated entirely in WINTER: winter capture value collapses
(NS 0.93->0.56, Baltic 0.91->0.50) while summer holds. Because winter carries the
most generation, that winter collapse is what drags the annual value down, and the
Baltic is worse because its winter synchronicity is tighter.

  today  = observed monthly capture value, generation-weighted (monthly_cv_per_farm)
  2040   = monthly capture value from the solved PyPSA network (NT-balticBaseline)

Output -> results/fig_seasonal_generation.png, 10_Presentation/figures/, + seasonal_cv_table.csv
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

NS = ["DE", "NL", "BE", "DK1", "FR"]; BAL = ["PL", "EE", "LV", "LT"]  # FI set aside
C_NS, C_BAL = "#2471a3", "#c0392b"
MONTHS = ["J", "F", "M", "A", "M", "J", "J", "A", "S", "O", "N", "D"]

# --- today: monthly CF + generation-weighted CV per basin ---
cv = pd.read_csv(ROOT / "2_Regression_Model/data/cv_strandA/monthly_cv_per_farm.csv").dropna(subset=["CV", "gen_MWh_norm"])
cv["CF"] = cv.gen_MWh_norm / cv.n_hours
def gw(g, c): return np.average(g[c], weights=g.gen_MWh_norm)
today = cv.groupby(["basin", "month"]).apply(
    lambda g: pd.Series({"CF": g.CF.mean(), "CV": gw(g, "CV")}), include_groups=False)

# --- 2040: monthly capture value from the solved network ---
def monthly_cv_2040(path, zones):
    n = pypsa.Network(path)
    mon = pd.Series(n.snapshots).dt.month.values
    price, gen, g = n.buses_t.marginal_price, n.generators_t.p, n.generators
    num = np.zeros(len(n.snapshots)); den = np.zeros(len(n.snapshots)); pbuses = []
    for z in zones:
        buses = sur.zone_buses(n, z)
        ids = [i for i in g[(g.bus.isin(buses)) & (g.carrier.isin(sur.OFFSHORE))].index if i in gen.columns]
        pb = [b for b in buses if b in price.columns]; pbuses += pb
        if not ids or not pb: continue
        num += gen[ids].sum(axis=1).values * price[pb].mean(axis=1).values
        den += gen[ids].sum(axis=1).values
    base = price[list(set(pbuses))].mean(axis=1).values
    df = pd.DataFrame({"m": mon, "num": num, "den": den, "p": base})
    return {m: (d.num.sum() / d.den.sum()) / d.p.mean() for m, d in df.groupby("m") if d.den.sum() > 0}

NET = Path.home() / "pypsa-eur/results/scenarios_tyndp_v3/2040-NT-balticBaseline.nc"
cv40 = {"NS": monthly_cv_2040(NET, NS), "Baltic": monthly_cv_2040(NET, BAL)}

# --- assemble + seasonal aggregates ---
def season(d, mset):
    v = [d[m] for m in mset if m in d]
    return np.mean(v) if v else np.nan
rows = []
for b in ("NS", "Baltic"):
    td = today.loc[b]
    rows.append(dict(basin=b,
        cf_winter=season(td.CF.to_dict(), (12, 1, 2)), cf_summer=season(td.CF.to_dict(), (6, 7, 8)),
        cv_today_w=season(td.CV.to_dict(), (12, 1, 2)), cv_today_s=season(td.CV.to_dict(), (6, 7, 8)),
        cv_2040_w=season(cv40[b], (12, 1, 2)), cv_2040_s=season(cv40[b], (6, 7, 8))))
T = pd.DataFrame(rows); T.to_csv(OUT / "seasonal_cv_table.csv", index=False)
print(T.round(3).to_string(index=False))

# --- plot ---
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6.2))
x = np.arange(1, 13)
# Panel 1: generation profile (capacity factor) by month
for b, c in [("NS", C_NS), ("Baltic", C_BAL)]:
    ax1.plot(x, [today.loc[b].CF[m] for m in range(1, 13)], "o-", color=c, lw=2.4, ms=6,
             label=("North Sea" if b == "NS" else "Baltic"))
ax1.axvspan(0.5, 2.5, color="#cfe2f3", alpha=0.5, zorder=0)
ax1.axvspan(11.5, 12.5, color="#cfe2f3", alpha=0.5, zorder=0)
ax1.text(1.5, 0.30, "winter", ha="center", fontsize=8.5, color="#1a5276")
ax1.set_xticks(x); ax1.set_xticklabels(MONTHS); ax1.set_ylim(0.3, 0.8)
ax1.set_ylabel("Offshore capacity factor (generation per MW)", fontsize=10.5)
ax1.set_title("Monthly capacity factor, 2017-24 mean", fontsize=11.5, color="#111")
ax1.legend(fontsize=10); ax1.grid(alpha=0.3)

# Panel 2: capture value, today vs 2040, winter vs summer (grouped bars)
groups = ["North Sea\nwinter", "North Sea\nsummer", "Baltic\nwinter", "Baltic\nsummer"]
today_v = [T.cv_today_w[0], T.cv_today_s[0], T.cv_today_w[1], T.cv_today_s[1]]
v2040 = [T.cv_2040_w[0], T.cv_2040_s[0], T.cv_2040_w[1], T.cv_2040_s[1]]
xb = np.arange(4); w = 0.38
ax2.bar(xb - w/2, today_v, w, color="#a9cce3", edgecolor="k", lw=0.6, label="today")
ax2.bar(xb + w/2, v2040, w, color=[C_NS, "#7fb3d9", C_BAL, "#e6a0a0"], edgecolor="k", lw=0.6, label="2040")
for i, (t, f) in enumerate(zip(today_v, v2040)):
    ax2.text(i - w/2, t + 0.01, f"{t:.2f}", ha="center", fontsize=8)
    ax2.text(i + w/2, f + 0.01, f"{f:.2f}", ha="center", fontsize=8, fontweight="bold")
    if "winter" in groups[i]:
        ax2.annotate("", (i + w/2, f + 0.04), (i - w/2, t - 0.02),
                     arrowprops=dict(arrowstyle="->", color="#b03a2e", lw=1.6))
ax2.set_xticks(xb); ax2.set_xticklabels(groups, fontsize=9); ax2.set_ylim(0, 1.05)
ax2.set_ylabel("Offshore-wind capture value", fontsize=10.5)
ax2.set_title("Seasonal capture value, today and 2040", fontsize=11.5, color="#111")
ax2.legend(fontsize=9, loc="lower left"); ax2.grid(axis="y", alpha=0.3)

fig.suptitle("Seasonal generation and seasonal capture value",
             fontsize=13.5, y=0.99, color="#111")
fig.tight_layout(rect=[0, 0, 1, 0.95])
fig.savefig(OUT / "fig_seasonal_generation.png", dpi=185)
print("saved fig_seasonal_generation.png")
