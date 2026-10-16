"""
7.36_cfd_who_pays.py

Expert-meeting ask (deck S17/S28): split capture-value erosion by CAUSE
(oversupply vs grid limitation) and by BEARER under a modern two-sided CfD,
because the two causes are compensated differently:

  - transmission-caused losses: constrained-off farms are compensated
    (EU Reg 2019/943 Art. 13; GB constraint payments), and a zonal-price
    depression is absorbed by the CfD top-up -> the STATE bears it
  - oversupply-caused losses: zero/negative-price hours suspend CfD payment
    (GB AR4+; EU CEEAG / EMD reform) -> the FARM bears it, and no compliant
    support scheme may cover it

Hour-level accounting on the solved networks (frozen = scenarios_tyndp_v3,
optimal = ..._vopt), NT balticBaseline, zones exactly as 7.31 (FI excluded).
The LP floors prices at ~0 instead of going negative, so "price < EPS" is the
model's stand-in for the real negative-price tail (conservative: understates
the farm-borne share; slide 12 caveat).

At strike S the value gap per basin splits exactly:
  S*E - market revenue = SUM_{p<EPS} P*(S-p)  [farm: CfD suspended, ~S*E0]
                       + SUM_{p>=EPS} P*(S-p) [state: net top-up]
Zero-price exposure that DISAPPEARS under the optimal grid is transmission-
caused (compensable in reality); what REMAINS under vopt is true oversupply.
The farm's "CfD capture rate" = 1 - E0/E is strike-independent.

Today's anchor: observed 2023-24 wind-weighted share of energy in hours with
day-ahead price <= 0, from ENTSO-E prices x VWF farm profiles.

Output -> results/cfd_who_pays.csv + printed tables (figure in 7.37)
"""
import importlib.util, warnings
from pathlib import Path
import numpy as np, pandas as pd, pypsa

warnings.filterwarnings("ignore")
pd.set_option("display.width", 200)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "7_Thesis_Figures" / "results"
FROZEN_DIR = Path.home() / "pypsa-eur/results/scenarios_tyndp_v3"
VOPT_DIR = Path.home() / "pypsa-eur/results/scenarios_tyndp_v3_vopt"

spec = importlib.util.spec_from_file_location("sur", ROOT / "1_PyPSA_Model/scripts/1.13_surrogate_runs.py")
sur = importlib.util.module_from_spec(spec); spec.loader.exec_module(sur)

NS = ["DE", "NL", "BE", "DK1", "FR"]
BAL = ["PL", "EE", "LV", "LT"]          # enclosed Baltic, FI excluded (as 7.31)
BASINS = {"North Sea": NS, "Baltic": BAL}
EPS = 1.0                                # EUR/MWh: the LP's zero-price stand-in
STRIKE = {"2030": 70.0, "2040": 66.0}    # DEA-based LCOE path used in 7.26-7.28 (74->66)


def basin_hourly(n, zones, strike):
    """Hour-level CfD accounting for one basin in one solved network."""
    w = n.snapshot_weightings.generators
    prices = n.buses_t.marginal_price
    g = n.generators
    E = E0 = rev = rev0 = topup = avail = 0.0
    cv_rows = []
    for z in zones:
        buses = sur.zone_buses(n, z)
        ids = [i for i in g[(g.bus.isin(buses)) & (g.carrier.isin(sur.OFFSHORE))].index
               if i in n.generators_t.p.columns]
        cv_rows.append(dict(sur.offshore_capture(n, z), zone=z))
        for gid in ids:
            bus = g.at[gid, "bus"]
            if bus not in prices.columns:
                continue
            p = n.generators_t.p[gid]
            pr = prices[bus]
            zero = pr < EPS
            E += float((p * w).sum())
            E0 += float((p * w)[zero].sum())
            rev += float((p * pr * w).sum())
            rev0 += float((p * pr * w)[zero].sum())
            topup += float((p * (strike - pr) * w)[~zero].sum())
            if gid in n.generators_t.p_max_pu.columns:
                avail += float((n.generators_t.p_max_pu[gid] * g.at[gid, "p_nom"] * w).sum())
    cv = pd.DataFrame(cv_rows)
    cv = cv[cv.energy_GWh > 0].dropna(subset=["CV_raw"])
    cv_raw = float((cv.CV_raw * cv.energy_GWh).sum() / cv.energy_GWh.sum()) if len(cv) else np.nan
    farm_loss = strike * E0 - rev0            # what suspension costs the farm vs strike
    return dict(E_TWh=E / 1e6, E0_share=E0 / E if E else np.nan,
                curtail_share=1 - E / avail if avail else np.nan,
                CV_raw=cv_raw, capture_price=rev / E if E else np.nan,
                farm_loss_bnEUR=farm_loss / 1e9, state_topup_bnEUR=topup / 1e9,
                gap_bnEUR=(strike * E - rev) / 1e9)


# ---------------- model part: 2030/2040 x frozen/optimal ----------------
rows = []
for year in ["2030", "2040"]:
    for grid, d in [("frozen", FROZEN_DIR), ("optimal", VOPT_DIR)]:
        n = pypsa.Network(d / f"{year}-NT-balticBaseline.nc")
        for basin, zones in BASINS.items():
            r = basin_hourly(n, zones, STRIKE[year])
            rows.append(dict(year=year, grid=grid, basin=basin, **r))
        del n
M = pd.DataFrame(rows)
M.to_csv(OUT / "cfd_who_pays.csv", index=False)
print("=== model: hour-level CfD accounting (EPS = %.0f EUR/MWh) ===" % EPS)
print(M.round(3).to_string(index=False))

# attribution: zero-price exposure that survives the optimal grid = oversupply
print("\n=== attribution of zero-price exposure (share of generated energy) ===")
for year in ["2030", "2040"]:
    for basin in BASINS:
        f = M[(M.year == year) & (M.grid == "frozen") & (M.basin == basin)].iloc[0]
        v = M[(M.year == year) & (M.grid == "optimal") & (M.basin == basin)].iloc[0]
        trans = f.E0_share - v.E0_share
        print(f"{year} {basin:10s}: frozen {f.E0_share:5.1%} = transmission {trans:+5.1%} "
              f"(grid removes) + oversupply {v.E0_share:5.1%} (irreducible); "
              f"farm CfD capture rate {1 - f.E0_share:5.1%} -> {1 - v.E0_share:5.1%}")

# ---------------- per-zone detail, 2040 frozen vs optimal ----------------
zrows = []
for grid, d in [("frozen", FROZEN_DIR), ("optimal", VOPT_DIR)]:
    n = pypsa.Network(d / "2040-NT-balticBaseline.nc")
    w = n.snapshot_weightings.generators
    prices = n.buses_t.marginal_price
    g = n.generators
    for z in NS + BAL:
        buses = sur.zone_buses(n, z)
        pb = [b for b in buses if b in prices.columns]
        zp = prices[pb].mean(axis=1)
        ids = [i for i in g[(g.bus.isin(buses)) & (g.carrier.isin(sur.OFFSHORE))].index
               if i in n.generators_t.p.columns]
        E = E0 = rev = avail = 0.0
        for gid in ids:
            bus = g.at[gid, "bus"]
            p = n.generators_t.p[gid]; pr = prices[bus]
            E += float((p * w).sum()); rev += float((p * pr * w).sum())
            E0 += float((p * w)[pr < EPS].sum())
            if gid in n.generators_t.p_max_pu.columns:
                avail += float((n.generators_t.p_max_pu[gid] * g.at[gid, "p_nom"] * w).sum())
        zrows.append(dict(grid=grid, zone=z, mean=zp.mean(), mean_ex=zp[zp <= 390].mean(),
                          scarce_h=int((zp > 390).sum()), E_TWh=E / 1e6,
                          capture=rev / E if E else np.nan, CV=(rev / E) / zp.mean() if E else np.nan,
                          E0_share=E0 / E if E else np.nan,
                          curt=1 - E / avail if avail else np.nan))
    del n
Z = pd.DataFrame(zrows)
Z.to_csv(OUT / "cfd_who_pays_zones.csv", index=False)
print("\n=== per-zone, 2040 (scarcity = hours > 390 EUR/MWh, as 1.17) ===")
print(Z.round(3).to_string(index=False))

# ---------------- observed anchor: 2023-24 negative-price share ----------------
farms = pd.read_csv(ROOT / "2_Regression_Model/data/wind_farms_strandA.csv", comment="#")
ZMAP = {"DE": "DE_LU", "DK1": "DK_1", "DK2": "DK_2", "SE4": "SE_4"}
PRICE_DIR = ROOT / "2_Regression_Model/data/entsoe_strandA/prices"

def zone_prices(zdir, years):
    parts = []
    for y in years:
        fp = PRICE_DIR / zdir / f"{y}.csv"
        if fp.exists():
            s = pd.read_csv(fp, index_col=0, parse_dates=True)["price_EURMWh"]
            parts.append(s)
    return pd.concat(parts) if parts else None

cfs = {y: pd.read_csv(ROOT / f"2_Regression_Model/data/vwf/hourly_cf_{y}.csv",
                      index_col=0, parse_dates=True) for y in [2023, 2024]}
cf = pd.concat(cfs.values())
cf.index = pd.DatetimeIndex(cf.index, tz="UTC")

print("\n=== observed 2023-24: wind-weighted share of energy at price <= 0 ===")
obs_rows = []
for basin, zones in BASINS.items():
    num = den = 0.0
    for z in zones:
        zdir = ZMAP.get(z, z)
        pr = zone_prices(zdir, [2023, 2024])
        if pr is None:
            continue
        zf = farms[farms.bidding_zone == zdir]
        cols = [c for c in zf.name if c in cf.columns]
        if not cols:
            continue
        cap = zf.set_index("name").capacity_MW
        gen = (cf[cols] * cap.reindex(cols)).sum(axis=1)
        both = pd.concat([gen.rename("g"), pr.rename("p")], axis=1).dropna()
        num += float(both.g[both.p <= 0].sum())
        den += float(both.g.sum())
    share = num / den if den else np.nan
    obs_rows.append(dict(basin=basin, neg_share_2324=share))
    print(f"{basin:10s}: {share:5.1%}")
pd.DataFrame(obs_rows).to_csv(OUT / "cfd_who_pays_observed.csv", index=False)
