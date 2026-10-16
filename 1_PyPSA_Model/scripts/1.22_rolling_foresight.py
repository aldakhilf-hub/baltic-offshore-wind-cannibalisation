"""
1.22_rolling_foresight.py

DK2 diagnosis, route 3: remove PERFECT FORESIGHT from hydro dispatch.

The NTC correction (1.21) fixed DK1 and left DK2 untouched: DK2's mean price fell
31% while its capture RATIO did not move at all, so the residual error is in the
price SHAPE, not the price level or the grid. The shape is set by 151 TWh of
Nordic reservoir hydro dispatched against a solver that sees the entire year of
weather at once. With perfect foresight, hydro absorbs every wind surplus exactly
when it arrives, wind is never the local marginal unit in DK2, and the price never
approaches zero (0 negative hours modelled vs 264 observed).

Real operators re-optimise on a rolling basis against a forecast horizon of days
to weeks, not a year. This script replaces the annual solve with a rolling horizon:

  for each month m:
      solve [start of m  ..  end of m + LOOKAHEAD]
      keep the results for month m only
      carry the reservoir state of charge at the end of m into month m+1

The lookahead prevents the well-known end-of-block artefact, where a block with no
future drains its reservoirs to empty on the final day. Storage state is carried
explicitly, and the January starting state is taken from the perfect-foresight
solve so that FORESIGHT is the only thing that changes between the two runs.

This is a standard representation of imperfect foresight, not a calibration knob:
no parameter is chosen by reference to the observed capture value.

Usage:  python 1.22_rolling_foresight.py
Output: results/rolling_foresight/{per_zone.csv, hours.csv}
"""
import importlib.util, warnings
from pathlib import Path
import numpy as np, pandas as pd, pypsa

warnings.filterwarnings("ignore")
pd.set_option("display.width", 200)

ROOT = Path(__file__).resolve().parents[2]
NTC_NET = ROOT / "1_PyPSA_Model/results/ntc_correction/base_s_30_elec_ntc2023.nc"
OUT = ROOT / "1_PyPSA_Model/results/rolling_foresight"
OUT.mkdir(parents=True, exist_ok=True)
LOOKAHEAD = pd.Timedelta(days=14)

spec = importlib.util.spec_from_file_location("sur", ROOT / "1_PyPSA_Model/scripts/1.13_surrogate_runs.py")
sur = importlib.util.module_from_spec(spec); spec.loader.exec_module(sur)

ZONES = ["DK2", "DK1", "DE", "NL", "BE"]
OBS = {"DK2": 0.784, "DK1": 0.854, "DE": 0.909, "NL": 0.881, "BE": 0.869}

n = pypsa.Network(str(NTC_NET))
snaps = n.snapshots

# starting reservoir state from the perfect-foresight solve: only foresight changes
su = n.storage_units
if len(su) and not n.storage_units_t.state_of_charge.empty:
    soc0 = n.storage_units_t.state_of_charge.iloc[0].reindex(su.index).fillna(
        0.5 * su.p_nom * su.max_hours)
else:
    soc0 = 0.5 * su.p_nom * su.max_hours
print(f"{len(su)} storage units, starting SOC total {soc0.sum() / 1e6:.1f} TWh")

n.storage_units["cyclic_state_of_charge"] = False
n.storage_units["state_of_charge_initial"] = soc0

months = sorted({(t.year, t.month) for t in snaps})
price_parts, gen_parts = [], []

for k, (yy, mm) in enumerate(months, 1):
    keep = snaps[(snaps.year == yy) & (snaps.month == mm)]
    horizon = snaps[(snaps >= keep[0]) & (snaps <= keep[-1] + LOOKAHEAD)]
    n.optimize(snapshots=horizon, solver_name="gurobi", method=2, crossover=0,
               threads=6, BarConvTol=1e-6, FeasibilityTol=1e-6)
    price_parts.append(n.buses_t.marginal_price.loc[keep].copy())
    gen_parts.append(n.generators_t.p.loc[keep].copy())
    # carry the state at the end of the KEPT month, not the end of the lookahead
    if len(su):
        n.storage_units["state_of_charge_initial"] = \
            n.storage_units_t.state_of_charge.loc[keep[-1]].reindex(su.index).fillna(0.0)
    print(f"  [{k:2d}/12] {yy}-{mm:02d} solved, kept {len(keep)} h "
          f"(horizon {len(horizon)} h)")

P = pd.concat(price_parts).sort_index()
G = pd.concat(gen_parts).sort_index()
P.to_csv(OUT / "hourly_prices.csv")


def cv_from(P, G, zone):
    buses = sur.zone_buses(n, zone)
    ids = [i for i in n.generators[(n.generators.bus.isin(buses)) &
           (n.generators.carrier.isin(sur.OFFSHORE))].index if i in G.columns]
    pb = [b for b in buses if b in P.columns]
    base = P[pb].mean(axis=1).mean()
    if not ids:
        return np.nan, np.nan, base, np.nan
    tot = G[ids].sum(axis=1)
    num = sum(G[g] * P[n.generators.at[g, "bus"]] for g in ids
              if n.generators.at[g, "bus"] in P.columns)
    zp = P[pb].mean(axis=1)
    return (num.sum() / tot.sum()) / base, tot.sum() / 1e3, base, float((zp < 1).mean())


base_net = pypsa.Network(str(NTC_NET))
rows = []
for z in ZONES:
    cv_r, e, mp, zero_h = cv_from(P, G, z)
    d_pf = sur.offshore_capture(base_net, z)
    rows.append(dict(zone=z, observed=OBS[z], CV_perfect_foresight=d_pf["CV_raw"],
                     CV_rolling=cv_r, delta=cv_r - d_pf["CV_raw"],
                     err_pf=d_pf["CV_raw"] - OBS[z], err_rolling=cv_r - OBS[z],
                     mean_price_pf=d_pf["mean_price"], mean_price_roll=mp,
                     zero_price_hours_share=zero_h))
D = pd.DataFrame(rows)
D.to_csv(OUT / "per_zone.csv", index=False)
print("\n=== 2023 capture value: perfect foresight vs rolling horizon (both NTC-corrected) ===")
print(D.round(3).to_string(index=False))
print(f"\nmean |error|  perfect foresight {D.err_pf.abs().mean():.3f} "
      f"-> rolling {D.err_rolling.abs().mean():.3f}")
print(f"DK2  {D.set_index('zone').err_pf['DK2']:+.3f} -> "
      f"{D.set_index('zone').err_rolling['DK2']:+.3f}")
