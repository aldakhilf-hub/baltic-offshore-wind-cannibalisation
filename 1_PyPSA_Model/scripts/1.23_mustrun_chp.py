"""
1.23_mustrun_chp.py

DK2 diagnosis, route 4: represent the two mechanisms that actually make Danish
prices go negative, which a plain LP omits.

Observed DK2 in 2023 had 264 negative-price hours. The model has none, and the
previous six fix attempts (five in June, plus the NTC correction and the rolling
horizon) could not create any, because both mechanisms are missing by construction:

  1. MUST-RUN CHP. Zealand's large units (Amagervaerket, Avedoerevaerket) serve
     Copenhagen district heating. In the heating season they cannot be turned
     down below a technical minimum regardless of the power price. An LP without
     unit commitment has no minimum-generation constraint, so it simply switches
     them off whenever wind is cheap.
  2. PREMIUM-DRIVEN NEGATIVE BIDDING. A wind farm on a feed-in premium loses that
     premium if it curtails, so it rationally bids DOWN TO MINUS the premium
     rather than stop. That is what sets the negative price. With a zero floor on
     costs an LP cannot reproduce it.

Both are represented here with physically motivated parameters, NOT fitted to the
observed capture value:
  - p_min_pu on Danish dispatchable thermal during the heating season, at the
    technical minimum of a large steam CHP unit
  - a negative marginal cost on Danish offshore wind equal to minus the premium

Because both parameters are uncertain, the script runs a small GRID over plausible
values and reports the resulting RANGE of DK2 capture value. The deliverable is a
bracket that either does or does not contain the observed 0.784; no single
combination is presented as the answer, and none is chosen by looking at the target.

Usage:  python 1.23_mustrun_chp.py
Output: results/mustrun_chp/{grid.csv, per_zone_central.csv}
"""
import importlib.util, itertools, warnings
from pathlib import Path
import numpy as np, pandas as pd, pypsa

warnings.filterwarnings("ignore")
pd.set_option("display.width", 200)

ROOT = Path(__file__).resolve().parents[2]
NET = ROOT / "1_PyPSA_Model/results/ntc_correction/base_s_30_elec_ntc2023.nc"
OUT = ROOT / "1_PyPSA_Model/results/mustrun_chp"
OUT.mkdir(parents=True, exist_ok=True)

spec = importlib.util.spec_from_file_location("sur", ROOT / "1_PyPSA_Model/scripts/1.13_surrogate_runs.py")
sur = importlib.util.module_from_spec(spec); spec.loader.exec_module(sur)

ZONES = ["DK2", "DK1", "DE", "NL", "BE"]
OBS = {"DK2": 0.784, "DK1": 0.854, "DE": 0.909, "NL": 0.881, "BE": 0.869}
CHP_CARRIERS = ["biomass", "coal", "lignite", "CCGT", "OCGT", "oil"]
HEATING_MONTHS = [1, 2, 3, 4, 10, 11, 12]

# technical minimum of a large steam CHP unit, and the wind premium it bids against
MINLOAD_GRID = [0.20, 0.35, 0.50]      # p_min_pu when committed for heat
PREMIUM_GRID = [0.0, 5.0, 10.0]        # EUR/MWh bid below zero when curtailing


def zone_cv(n, P, G, zone):
    buses = sur.zone_buses(n, zone)
    ids = [i for i in n.generators[(n.generators.bus.isin(buses)) &
           (n.generators.carrier.isin(sur.OFFSHORE))].index if i in G.columns]
    pb = [b for b in buses if b in P.columns]
    zp = P[pb].mean(axis=1)
    if not ids or G[ids].sum().sum() <= 0:
        return np.nan, np.nan
    tot = G[ids].sum(axis=1)
    num = sum(G[g] * P[n.generators.at[g, "bus"]] for g in ids
              if n.generators.at[g, "bus"] in P.columns)
    return (num.sum() / tot.sum()) / zp.mean(), float((zp < 0).mean())


rows = []
for minload, premium in itertools.product(MINLOAD_GRID, PREMIUM_GRID):
    n = pypsa.Network(str(NET))
    snaps = n.snapshots
    heat = snaps.month.isin(HEATING_MONTHS)

    dk_buses = set(sur.zone_buses(n, "DK1")) | set(sur.zone_buses(n, "DK2"))
    g = n.generators
    chp = g[(g.bus.isin(dk_buses)) & (g.carrier.isin(CHP_CARRIERS)) & (g.p_nom > 0)].index
    wind = g[(g.bus.isin(dk_buses)) & (g.carrier.isin(sur.OFFSHORE))].index

    # 1. must-run: minimum generation during the heating season only
    if len(chp):
        pmin = pd.DataFrame(0.0, index=snaps, columns=chp)
        pmin.loc[heat, :] = minload
        n.generators_t.p_min_pu = pd.concat(
            [n.generators_t.p_min_pu.drop(columns=chp, errors="ignore"), pmin], axis=1)

    # 2. premium-driven negative bidding by Danish offshore wind
    if premium > 0 and len(wind):
        n.generators.loc[wind, "marginal_cost"] = -premium

    n.optimize(solver_name="gurobi", method=2, crossover=0, threads=6,
               BarConvTol=1e-6, FeasibilityTol=1e-6)
    P, G = n.buses_t.marginal_price, n.generators_t.p
    cv_dk2, neg_dk2 = zone_cv(n, P, G, "DK2")
    rec = dict(min_load=minload, premium=premium, n_chp=len(chp),
               CV_DK2=cv_dk2, neg_hours_DK2=neg_dk2 * 8760,
               err_DK2=cv_dk2 - OBS["DK2"])
    for z in ["DK1", "DE", "NL", "BE"]:
        cv, _ = zone_cv(n, P, G, z)
        rec[f"CV_{z}"] = cv
        rec[f"err_{z}"] = cv - OBS[z]
    rows.append(rec)
    print(f"min_load {minload:.2f}  premium -{premium:>4.1f}  ->  DK2 CV {cv_dk2:.3f} "
          f"(err {cv_dk2 - OBS['DK2']:+.3f}, {neg_dk2 * 8760:.0f} negative hours)")
    D = pd.DataFrame(rows); D.to_csv(OUT / "grid.csv", index=False)
    del n

D = pd.DataFrame(rows)
print("\n=== DK2 capture value across physically plausible must-run / premium settings ===")
print(D[["min_load", "premium", "CV_DK2", "err_DK2", "neg_hours_DK2"]].round(3).to_string(index=False))
print(f"\nDK2 bracket: {D.CV_DK2.min():.3f} to {D.CV_DK2.max():.3f}   observed 0.784   "
      f"{'CONTAINS the observation' if D.CV_DK2.min() <= 0.784 <= D.CV_DK2.max() else 'does NOT contain it'}")
other = [c for c in D.columns if c.startswith("err_") and c != "err_DK2"]
print(f"other zones, mean |error| across the grid: "
      f"{D[other].abs().mean(axis=1).min():.3f} to {D[other].abs().mean(axis=1).max():.3f}")
