"""
7.41_make_model_gap_decomposition.py

Supervisor ask: "decompose the drivers of WHY the two models differ in output."

The two models construct capture value from two inputs that differ, so the gap
between their outputs decomposes exactly into a GENERATION channel and a PRICE
channel. The regression model is fitted on the virtual wind farm's generation
series priced at observed day-ahead prices; the system model uses its own
dispatched generation priced at its own marginal prices.

    CV(g, p) = [sum_t g_t p_t / sum_t g_t] / mean(p)

Bridge, model output to model output:

    regression model (out-of-fold)
      + fit residual            -> CV(g_vwf, p_obs), the construction it is fitted on
      + generation profile      -> swap VWF series for PyPSA dispatched series
      + zero price floor        -> observed prices clipped at zero, the LP's constraint
      + residual price shape    -> clipped observed prices to PyPSA marginal prices
      + network representation  -> market NTCs back to thermal ratings (as reported)
    = system model (as reported in the validation triangle)

Generation and price are Shapley-averaged over both bridging paths, so the split
is exact and independent of the order in which the channels are applied. The
price channel is then split by re-pricing against observed prices floored at
zero, which is precisely the constraint the linear program imposes.

A single zone price series (the mean across the zone's buses) is used on both
sides so the swap is exact; this reproduces the reported zone capture values to
within 0.01.

DK2 is excluded. Its price formation is a documented outlier driven by must-run
and unit-commitment behaviour outside this model class, and it enters no headline
aggregate. Zones are the four the 2023 record can arbitrate.

Output -> results/fig_model_gap_decomposition.png
          results/model_gap_channels.csv
"""
import warnings
from pathlib import Path
import numpy as np, pandas as pd, pypsa
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patheffects as pe
warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "7_Thesis_Figures" / "results"
NET = ROOT / "1_PyPSA_Model/results/ntc_correction/base_s_30_elec_ntc2023.nc"
NTCZ = ROOT / "1_PyPSA_Model/results/ntc_correction/per_zone.csv"
TRI = ROOT / "3_Comparison/results/01_validation_triangle_2023/validation_triangle.csv"
OBS = ROOT / "1_PyPSA_Model/data/observed_prices/entsoe_prices_2023.csv"
VWF = ROOT / "2_Regression_Model/data/vwf/hourly_cf_2023.csv"
REG = ROOT / "2_Regression_Model/data/wind_farms_strandA.csv"
HALO = [pe.withStroke(linewidth=2.6, foreground="#1b2a36")]

YEAR = 2023
ZONES = ["DE", "NL", "BE", "DK1"]            # DK2 excluded, see docstring
OBS_ZONE = {"DE": "DELU", "NL": "NL", "BE": "BE", "DK1": "DK1"}
VWF_ZONE = {"DE": "DE_LU", "NL": "NL", "BE": "BE", "DK1": "DK1"}
OFFSHORE = ["offwind-ac", "offwind-dc", "offwind-float", "offwind"]


def cv(g, p):
    g, p = np.asarray(g, float), np.asarray(p, float)
    m = np.isfinite(g) & np.isfinite(p)
    g, p = g[m], p[m]
    return float((g * p).sum() / g.sum() / p.mean()) if g.sum() > 0 else np.nan


# ------------------------------------------------------------ system model
n = pypsa.Network(NET)
snap = pd.DatetimeIndex(n.snapshots)
gen, prices = n.generators, n.buses_t.marginal_price


def zone_buses(z):
    return [b for b in n.buses.index
            if b.split()[0].startswith(z) and not b.split()[0].startswith("DK2")]


sys_g, sys_p = {}, {}
for z in ZONES:
    buses = zone_buses(z)
    ids = [i for i in gen[(gen.bus.isin(buses)) & (gen.carrier.isin(OFFSHORE))].index
           if i in n.generators_t.p.columns]
    pb = [b for b in buses if b in prices.columns]
    assert ids and pb, f"zone {z}: {len(ids)} offshore gens, {len(pb)} priced buses"
    sys_g[z] = n.generators_t.p[ids].sum(axis=1).values
    sys_p[z] = prices[pb].mean(axis=1).values      # zone price, matches the CV base

SG = pd.DataFrame(sys_g, index=snap)
SP = pd.DataFrame(sys_p, index=snap)

# ------------------------------------------------------------ observed prices
obs = pd.read_csv(OBS, parse_dates=["timestamp_utc"])
obs["timestamp_utc"] = pd.DatetimeIndex(obs.timestamp_utc).tz_localize(None)
OP = obs.pivot_table(index="timestamp_utc", columns="zone",
                     values="price_eurMWh", aggfunc="mean")
OP = OP.rename(columns={v: k for k, v in OBS_ZONE.items()})
missing = [z for z in ZONES if z not in OP.columns]
assert not missing, f"observed prices missing {missing}; have {list(OP.columns)}"
OP = OP[ZONES]

# ------------------------------------------------------------ VWF generation
reg = pd.read_csv(REG, comment="#")
reg = reg[reg.commissioning_year <= YEAR]
cf = pd.read_csv(VWF, parse_dates=["timestamp_utc"]).set_index("timestamp_utc")
cf.index = pd.DatetimeIndex(cf.index).tz_localize(None)
VG = {}
for z in ZONES:
    farms = reg[reg.bidding_zone == VWF_ZONE[z]]
    cols = [f for f in farms.name if f in cf.columns]
    assert cols, f"no VWF columns for {z}"
    caps = farms.set_index("name").loc[cols, "capacity_MW"].astype(float)
    VG[z] = (cf[cols] * caps.values).sum(axis=1)
VG = pd.DataFrame(VG)

idx = SG.index.intersection(OP.index).intersection(VG.index)
SG, SP, OP, VG = SG.loc[idx], SP.loc[idx], OP.loc[idx], VG.loc[idx]
print(f"aligned hours: {len(idx)}   zones: {ZONES}")

# ------------------------------------------------------------ reported outputs
tri = pd.read_csv(TRI)
tri = tri[(tri.year == YEAR)].set_index("zone")
ntc = pd.read_csv(NTCZ).set_index("zone")

# ------------------------------------------------------------ decomposition
rows = []
for z in ZONES:
    gv, gs, po, ps = VG[z], SG[z], OP[z], SP[z]
    pof = po.clip(lower=0)

    c_vo, c_so = cv(gv, po), cv(gs, po)
    c_vs, c_ss = cv(gv, ps), cv(gs, ps)

    d_gen = 0.5 * ((c_so - c_vo) + (c_ss - c_vs))
    d_price = 0.5 * ((c_vs - c_vo) + (c_ss - c_so))
    d_floor = 0.5 * ((cv(gv, pof) - c_vo) + (cv(gs, pof) - c_so))
    d_shape = d_price - d_floor

    cv_reg = float(tri.at[z, "CV_regression"])           # regression, out of fold
    cv_ntc = float(ntc.at[z, "CV_ntc"])                  # system model, NTC-corrected
    cv_thermal = float(ntc.at[z, "CV_thermal"])          # system model, as reported
    # bookkeeping: out-of-fold fit residual, plus multi-bus price aggregation on
    # the system side (only DE carries more than one priced bus)
    d_constr = (c_vo - cv_reg) + (cv_ntc - c_ss)
    d_net = cv_thermal - cv_ntc                          # NTC back to thermal ratings

    rows.append(dict(zone=z, CV_regression=cv_reg, CV_system=cv_thermal,
                     total_gap=cv_thermal - cv_reg, construction=d_constr,
                     generation=d_gen, zero_floor=d_floor, price_shape=d_shape,
                     network=d_net,
                     neg_hours_obs=int((po < 0).sum()), neg_hours_sys=int((ps < 0).sum()),
                     energy_GWh=float(gv.sum() / 1e3)))

D = pd.DataFrame(rows)
CH = ["construction", "generation", "zero_floor", "price_shape", "network"]
resid = D.total_gap - D[CH].sum(axis=1)
assert resid.abs().max() < 1e-9, f"bridge not exact: {resid.values}"

w = D.energy_GWh / D.energy_GWh.sum()
AGG = {"zone": "Weighted mean"}
for c in ["CV_regression", "CV_system", "total_gap"] + CH:
    AGG[c] = float((D[c] * w).sum())
AGG.update(neg_hours_obs=int(D.neg_hours_obs.mean()),
           neg_hours_sys=int(D.neg_hours_sys.mean()),
           energy_GWh=float(D.energy_GWh.sum()))
D = pd.concat([D, pd.DataFrame([AGG])], ignore_index=True)
D.round(4).to_csv(OUT / "model_gap_channels.csv", index=False)
print(D.round(3).to_string(index=False))

A = D.iloc[-1]
print(f"\nregression {A.CV_regression:.3f} -> system {A.CV_system:.3f}, "
      f"total gap {A.total_gap:+.3f}")
for c in CH:
    print(f"   {c:<13} {A[c]:+.3f}")
print(f"largest single channel, any zone: "
      f"{D.iloc[:-1][CH].abs().max().max():.3f}")

# ================================================================ FIGURE
LBL = {"construction": "construction", "generation": "generation",
       "zero_floor": "zero floor", "price_shape": "price shape",
       "network": "network"}
LEG = {"construction": "Construction residual", "generation": "Generation profile",
       "zero_floor": "Zero price floor", "price_shape": "Residual price shape",
       "network": "Network representation"}
COL = {"construction": "#9aa5ab", "generation": "#2471a3", "zero_floor": "#e67e22",
       "price_shape": "#c0793a", "network": "#1e7d34"}
C_REG, C_SYS = "#7f8c8d", "#34495e"

fig, (ax, axz) = plt.subplots(1, 2, figsize=(14.4, 5.6),
                              gridspec_kw={"width_ratios": [1.75, 1.0]})

# ---- left: the bridge
start, end = A.CV_regression, A.CV_system
W = 0.62
ax.bar(0, start, W, color=C_REG, zorder=3)
run = start
for i, c in enumerate(CH, start=1):
    v = A[c]
    bottom = run if v >= 0 else run + v
    ax.bar(i, abs(v), W, bottom=bottom, color=COL[c], zorder=3)
    ax.plot([i - 1 + W / 2, i - W / 2], [run, run], color="#666", lw=0.9, ls="--", zorder=2)
    run += v
    off = 0.0045 if v >= 0 else -0.0045
    ax.text(i, bottom + abs(v) + off if v >= 0 else bottom + off, f"{v:+.3f}",
            ha="center", va="bottom" if v >= 0 else "top", fontsize=10,
            fontweight="bold", color="#2c3e50")
ax.bar(6, end, W, color=C_SYS, zorder=3)
ax.plot([5 + W / 2, 6 - W / 2], [run, run], color="#666", lw=0.9, ls="--", zorder=2)
for xx, vv in [(0, start), (6, end)]:
    ax.text(xx, vv + 0.005, f"{vv:.3f}", ha="center", fontsize=11.5,
            fontweight="bold", color="#2c3e50")
ax.set_xticks(range(7))
ax.set_xticklabels(["regression\nmodel"] + [LBL[c] for c in CH] + ["system\nmodel"],
                   fontsize=9.2)
ax.set_ylabel("Offshore-wind capture value, 2023", fontsize=10.5)
ax.set_ylim(0.845, 0.925)
ax.grid(axis="y", alpha=0.25)
ax.margins(x=0.05)
ax.set_title("Weighted mean across the four zones", fontsize=11, color="#111")

# ---- right: per zone
Z = D.iloc[:-1]
x = np.arange(len(Z))
neg = np.zeros(len(Z)); pos = np.zeros(len(Z))
for c in CH:
    v = Z[c].values
    bot = np.where(v >= 0, pos, neg)
    axz.bar(x, v, 0.6, bottom=bot, color=COL[c], zorder=3)
    pos = pos + np.where(v >= 0, v, 0)
    neg = neg + np.where(v < 0, v, 0)
axz.plot(x, Z.total_gap.values, "o", color="#111", ms=6.5, zorder=5)
axz.axhline(0, color="#444", lw=0.9)
axz.set_xticks(x); axz.set_xticklabels(Z.zone, fontsize=10.5)
axz.set_ylabel("Contribution to the gap in capture value", fontsize=10.5)
axz.grid(axis="y", alpha=0.25)
axz.set_title("By zone", fontsize=11, color="#111")
axz.margins(y=0.16)

from matplotlib.patches import Patch
from matplotlib.lines import Line2D
fig.legend([Patch(fc=COL[c]) for c in CH] +
           [Line2D([], [], marker="o", color="#111", ls="none", ms=6.5)],
           [LEG[c] for c in CH] + ["Total gap"],
           loc="lower center", ncol=6, fontsize=9.2, frameon=False,
           bbox_to_anchor=(0.5, -0.012), handlelength=1.2, columnspacing=1.3)
fig.suptitle("Decomposition of the gap between the two models, 2023",
             fontsize=13.5, y=0.975, color="#111")
fig.subplots_adjust(top=0.85, bottom=0.19, wspace=0.24)
fig.savefig(OUT / "fig_model_gap_decomposition.png", dpi=200)
plt.close(fig)
print("\nsaved fig_model_gap_decomposition.png")
