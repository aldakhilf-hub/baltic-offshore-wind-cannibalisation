"""
1.17_scarcity_cv_sensitivity.py — how much of the projected Baltic CV erosion is
wind-driven price depression vs scarcity-driven base-price inflation?

The 2040 scenarios retain residual scarcity hours (DSR at 400 EUR/MWh, shedding
at the 4,000 cap), concentrated in PL. Scarcity raises the MEAN price (the CV
denominator) while wind output in scarce (low-wind) hours is small — so CV falls
for a reason that is adequacy, not cannibalisation. This sensitivity recomputes
every zone CV EXCLUDING hours whose zone price exceeds the DSR activation level
(>390 EUR/MWh): if the Baltic erosion survives ex-scarcity, the headline is
cannibalisation, defensibly.

Output: results/projections_v3/scarcity_sensitivity.csv + console verdict.
Usage: python 1.17_scarcity_cv_sensitivity.py   (reads solved networks; ~2 min)
"""
import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pypsa

HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "results" / "projections_v3"
V3 = Path.home() / "pypsa-eur/results/scenarios_tyndp_v3"
THRESH = 390.0   # just below the DSR tier at 400 EUR/MWh

spec = importlib.util.spec_from_file_location("sur13", HERE / "1.13_surrogate_runs.py")
sur = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sur)


def zone_cv(n, zone, mask=None):
    """Energy/CV for a zone, optionally restricted to non-scarcity hours."""
    buses = sur.zone_buses(n, zone)
    pr = n.buses_t.marginal_price
    pbuses = [b for b in buses if b in pr.columns]
    if not pbuses:
        return np.nan, 0.0, np.nan
    zp = pr[pbuses].mean(axis=1)
    sel = zp.index if mask is None else zp.index[zp <= THRESH]
    g = n.generators
    ids = [i for i in g[(g.bus.isin(buses)) & (g.carrier.isin(sur.OFFSHORE))].index
           if i in n.generators_t.p.columns]
    if not ids:
        return np.nan, 0.0, np.nan
    P = n.generators_t.p[ids].sum(axis=1).loc[sel]
    if P.sum() <= 0:
        return np.nan, 0.0, np.nan
    num = pd.Series(0.0, index=sel)
    for gid in ids:
        bus = g.at[gid, "bus"]
        if bus in pr.columns:
            num += n.generators_t.p[gid].loc[sel] * pr[bus].loc[sel]
    capture = num.sum() / P.sum()
    base = zp.loc[sel].mean()
    n_scarce = int((zp > THRESH).sum()) if mask is not None else 0
    return capture / base if base else np.nan, float(P.sum()), n_scarce


rows = []
for f in sorted(V3.glob("*.nc")):
    n = pypsa.Network(f)
    for zone in sur.BALTIC:
        cv_full, e_full, _ = zone_cv(n, zone)
        cv_ex, e_ex, n_scarce = zone_cv(n, zone, mask=True)
        rows.append({"scenario": f.stem, "zone": zone, "CV_full": cv_full,
                     "CV_ex_scarcity": cv_ex, "delta": (cv_ex - cv_full)
                     if cv_full == cv_full and cv_ex == cv_ex else np.nan,
                     "scarcity_hours": n_scarce, "energy_GWh": e_full / 1e3})
    print(f"  {f.stem} done")

d = pd.DataFrame(rows)
d.round(4).to_csv(OUT / "scarcity_sensitivity.csv", index=False)

print("\nBaltic aggregate CV: full hours vs ex-scarcity (energy-weighted):")
for scn, sub in d.groupby("scenario"):
    prod = sub[(sub.energy_GWh > 0)].dropna(subset=["CV_full", "CV_ex_scarcity"])
    w = prod.energy_GWh
    full = (prod.CV_full * w).sum() / w.sum()
    ex = (prod.CV_ex_scarcity * w).sum() / w.sum()
    print(f"  {scn:26s} full {full:.3f} | ex-scarcity {ex:.3f} | delta {ex - full:+.3f}")
print("\nReading: if ex-scarcity CV remains low, the erosion is CANNIBALISATION,"
      "\nnot an adequacy artifact. Per-zone detail in scarcity_sensitivity.csv.")
