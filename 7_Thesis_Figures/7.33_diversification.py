"""
7.33_diversification.py -- Objective 5: the portfolio value of spreading offshore
wind across the North Sea AND the Baltic, rather than concentrating in the North Sea.

Two measurable benefits:
  (1) CANNIBALISATION HEDGE (level): concentrating a fixed total in the North Sea
      drives it deep down its cannibalisation curve; spreading some to the Baltic
      (earlier on its curve, smaller market) keeps each basin higher, so the
      portfolio's aggregate capture value beats North-Sea-only.
      -> allocation curve: aggregate capture value vs the Baltic share.
  (2) RISK HEDGE (volatility): the basins' monthly capture value is only partly
      correlated, so a mixed portfolio earns more steadily than either alone.
      -> Markowitz frontier: portfolio mean vs volatility across allocations.

Output -> results/ + 10_Presentation/figures/ : fig_diversification.png + CSVs
"""
from pathlib import Path
import warnings
warnings.filterwarnings("ignore")
import numpy as np, pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "7_Thesis_Figures" / "results"
DECK = ROOT / "10_Presentation" / "figures"
NS = ["DE", "NL", "BE", "DK1", "FR"]
BAL = ["PL", "EE", "LV", "LT"]              # enclosed Baltic, Finland excluded
C_NS, C_BAL, C_MIX = "#2471a3", "#c0392b", "#1e7d34"
WIND_CORR = 0.28                            # cross-basin hourly generation correlation (7.08)

# ================= MECHANISM 1: cannibalisation hedge (allocation curve) =================
proj = pd.read_csv(ROOT / "1_PyPSA_Model/results/projections_v3/projected_capture_values.csv")


def basin_point(sc, zs):
    g = proj[(proj.scenario == sc) & (proj.zone.isin(zs))].dropna(subset=["CV"])
    en, ld = g.energy_GWh.sum(), g.load_GWh.sum()
    return en / ld, (g.CV * g.energy_GWh).sum() / en, ld


# (penetration, capture value) points + basin demand (GWh); 2025 ~ parity at low penetration
pts = {"NS": [(0.04, 0.887)], "Baltic": [(0.0, 0.889)]}
dem = {}
for sc in ["2030-NT-balticBaseline", "2040-NT-balticBaseline"]:
    for nm, zs in [("NS", NS), ("Baltic", BAL)]:
        pen, cv, ld = basin_point(sc, zs)
        pts[nm].append((pen, cv)); dem[nm] = ld          # demand ~ the 2040 value
# fit a quadratic cannibalisation curve CV(pen) per basin
fit = {b: np.polyfit([p for p, _ in pts[b]], [c for _, c in pts[b]], 2) for b in pts}
cv_of = {b: (lambda pen, f=fit[b]: float(np.clip(np.polyval(f, pen), 0.0, 1.0))) for b in pts}
print("cannibalisation points (pen, CV):")
for b in pts:
    print(f"  {b:7s} {pts[b]}  demand {dem[b]/1e3:.0f} TWh")

E_TOT = 538288 + 84537          # 2040 NS + Baltic offshore energy (GWh): the fixed total to allocate
shares = np.linspace(0.0, 0.45, 91)
agg, pnNS, pnB = [], [], []
for s in shares:                # s = Baltic share of total offshore energy
    eB, eN = s * E_TOT, (1 - s) * E_TOT
    pN, pB = eN / dem["NS"], eB / dem["Baltic"]
    cvN, cvB = cv_of["NS"](pN), cv_of["Baltic"](pB)
    agg.append((eN * cvN + eB * cvB) / E_TOT); pnNS.append(pN); pnB.append(pB)
agg = np.array(agg)
i_opt = int(np.argmax(agg)); s_opt = shares[i_opt]
s_plan = 84537 / E_TOT
agg_allNS = agg[0]
agg_plan = float(np.interp(s_plan, shares, agg))
print(f"\nMECH 1 allocation (fix {E_TOT/1e3:.0f} TWh total offshore):")
print(f"  all-North-Sea (0% Baltic):  aggregate CV {agg_allNS:.3f}")
print(f"  planned split ({s_plan*100:.0f}% Baltic): aggregate CV {agg_plan:.3f}")
print(f"  OPTIMAL split ({s_opt*100:.0f}% Baltic):  aggregate CV {agg[i_opt]:.3f}  "
      f"(+{(agg[i_opt]-agg_allNS)*100:.1f} pts, +{(agg[i_opt]/agg_allNS-1)*100:.0f}% vs all-NS)")
pd.DataFrame({"baltic_share": shares, "aggregate_CV": agg, "pen_NS": pnNS, "pen_Baltic": pnB}).to_csv(
    OUT / "diversification_allocation.csv", index=False)

# ================= MECHANISM 2: risk hedge (Markowitz frontier) =================
m = pd.read_csv(ROOT / "2_Regression_Model/data/cv_strandA/monthly_cv_per_farm.csv")
m["z"] = m.bidding_zone
NSz = ["DE_LU", "NL", "BE", "DK_1", "FR"]; BALz = ["PL", "EE", "LV", "LT", "DK_2", "SE_4"]   # FI, GB excluded
m = m[m.z.isin(NSz + BALz)].dropna(subset=["CV", "gen_MWh_norm"]).copy()
m["bas"] = np.where(m.z.isin(NSz), "NS", "Baltic")


def monthly_basin(bas):
    g = m[m.bas == bas].groupby(["year", "month"]).apply(
        lambda d: (d.CV * d.gen_MWh_norm).sum() / d.gen_MWh_norm.sum())
    return g.rename("CV")


ts = pd.concat([monthly_basin("NS").rename("NS"), monthly_basin("Baltic").rename("Baltic")], axis=1).dropna()
mu = ts.mean(); sd = ts.std(); rho = ts.corr().loc["NS", "Baltic"]
print(f"\nMECH 2 monthly capture value 2017-2024 ({len(ts)} months):")
print(f"  North Sea  mean {mu.NS:.3f}  vol {sd.NS:.3f}")
print(f"  Baltic     mean {mu.Baltic:.3f}  vol {sd.Baltic:.3f}")
print(f"  cross-basin correlation {rho:.2f}")
w = np.linspace(0, 1, 101)        # w = North Sea weight
pm = w * mu.NS + (1 - w) * mu.Baltic
pv = np.sqrt((w * sd.NS) ** 2 + ((1 - w) * sd.Baltic) ** 2 + 2 * w * (1 - w) * sd.NS * sd.Baltic * rho)
i_mv = int(np.argmin(pv))
print(f"  min-variance portfolio: {w[i_mv]*100:.0f}% North Sea / {(1-w[i_mv])*100:.0f}% Baltic, "
      f"vol {pv[i_mv]:.3f} (vs North-Sea-only {sd.NS:.3f}, a {(1-pv[i_mv]/sd.NS)*100:.0f}% cut)")
pd.DataFrame({"ns_weight": w, "port_mean": pm, "port_vol": pv}).to_csv(OUT / "diversification_frontier.csv", index=False)

# ================= figure =================
plt.rcParams.update({"axes.spines.top": False, "axes.spines.right": False})
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13.4, 5.8))

# ---- panel 1: allocation curve ----
ax1.plot(shares * 100, agg, color=C_MIX, lw=3, zorder=3, solid_capstyle="round")
ax1.scatter([0], [agg_allNS], s=80, color=C_NS, zorder=5)
ax1.scatter([s_opt * 100], [agg[i_opt]], s=180, color=C_MIX, zorder=5, marker="*")
ax1.axvline(s_plan * 100, color="#aaa", ls=":", lw=1.3, zorder=1)
# headroom so labels never touch the title or the curve
ax1.set_ylim(agg.min() - 0.02, agg.max() + 0.045)
ax1.set_xlim(-2, 46)
ax1.annotate("all North Sea", (0, agg_allNS), xytext=(4, agg_allNS), fontsize=10,
             color=C_NS, va="center")
ax1.annotate(f"optimum {s_opt*100:.0f}% Baltic\n+{(agg[i_opt]-agg_allNS)*100:.0f} points",
             (s_opt * 100, agg[i_opt]), xytext=(s_opt * 100 + 4, agg[i_opt] + 0.005),
             fontsize=10, color=C_MIX, va="center")
ax1.text(s_plan * 100, agg.min() - 0.012, f"planned {s_plan*100:.0f}%",
         fontsize=9, color="#888", ha="center")
ax1.set_xlabel("Baltic share of offshore buildout (%)", fontsize=11)
ax1.set_ylabel("Fleet capture value (2040)", fontsize=11)
ax1.set_title("Fleet capture value by basin mix", fontsize=12, pad=12, color="#111")
ax1.grid(axis="y", alpha=0.25)

# ---- panel 2: efficient frontier ----
ax2.plot(pv, pm, color="#7d3c98", lw=3, zorder=3, solid_capstyle="round")
ax2.scatter([sd.NS], [mu.NS], s=120, color=C_NS, zorder=5)
ax2.scatter([sd.Baltic], [mu.Baltic], s=120, color=C_BAL, zorder=5)
# headroom and clear corners for the two labels
ax2.set_xlim(sd.NS - 0.003, sd.Baltic + 0.004)
ax2.set_ylim(mu.Baltic - 0.004, mu.NS + 0.006)
ax2.annotate("100% North Sea", (sd.NS, mu.NS),
             xytext=(sd.NS + 0.0015, mu.NS), fontsize=10, color=C_NS,
             va="center")
ax2.annotate("100% Baltic", (sd.Baltic, mu.Baltic), xytext=(sd.Baltic, mu.Baltic + 0.0025),
             fontsize=10, color=C_BAL, ha="right", va="bottom")
ax2.set_xlabel("Risk  (volatility of capture value)", fontsize=11)
ax2.set_ylabel("Mean capture value", fontsize=11)
ax2.set_title("Mean-volatility frontier of the two-basin portfolio", fontsize=12, pad=12, color="#111")
ax2.grid(axis="y", alpha=0.25)

fig.suptitle("Basin diversification of the 2040 offshore fleet",
             fontsize=13.5, y=1.0, color="#111")
fig.tight_layout(rect=[0, 0.01, 1, 0.93])
fig.savefig(OUT / "fig_diversification.png", dpi=185)
plt.close(fig)
print("\nsaved fig_diversification.png")
