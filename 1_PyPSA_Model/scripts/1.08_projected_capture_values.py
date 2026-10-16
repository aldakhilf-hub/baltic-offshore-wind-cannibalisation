"""
08_projected_capture_values.py

Computes the projected OFFSHORE WIND CAPTURE VALUE per zone for each TYNDP
scenario -- the "capture price" deliverable that 07 does not produce (07 only
reports mean wholesale price). Then bias-corrects the Baltic capture values
using the DK2 analogue from the historical validation (1.04).

NOTE (2026-06-11): the constant DK2-bias correction here is the superseded v1
device, kept only as the first rung of the robustness trail. The CANONICAL
correction is the penetration-dependent fit in 1.09 — quote those numbers.
Audit fixes applied: reads the v3 scenario directory (was a non-existent
path), writes into results/projections_v3/, fails loudly when no scenario
files are found, reports the TRUE aggregate penetration (total offshore energy
/ total zone load, all Baltic zones incl. zero-offshore ones) instead of the
energy-weighted mean of per-zone ratios (which overstated ~37%), and applies
snapshot weightings so energy totals are correct at any time resolution.

Why DK2 is the analogue:
  Track-B validation showed PyPSA reproduces offshore capture value well for
  large, well-interconnected North Sea zones (DE 2023: 0.91 vs 0.91) but
  systematically OVER-states it (under-states cannibalisation) for the small,
  congestion-prone, Baltic-facing zone DK2 (2023: 0.944 modelled vs 0.784
  observed; bias grows with penetration). The future Baltic zones are small,
  wind-saturated and export-constrained -- i.e. DK2-like -- so PyPSA's raw
  projected Baltic capture value is an OPTIMISTIC upper estimate. We subtract
  the validated DK2 bias to obtain a conservative (lower-bound) capture value.

Outputs to results/projections_v3/:
  - projected_capture_values.csv       (per zone × scenario, raw)
  - baltic_capture_value_corrected.csv (Baltic aggregate, raw + constant-bias v1 corr)
  - fig4_baltic_capture_value.png

Usage: python 1.08_projected_capture_values.py
"""

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pypsa

ROOT = Path(__file__).resolve().parent.parent
SCEN_DIR = Path.home() / "pypsa-eur/results/scenarios_tyndp_v3"   # canonical v3 networks (1.07)
OUT = ROOT / "results" / "projections_v3"
OUT.mkdir(parents=True, exist_ok=True)
VALID_CSV = ROOT / "results" / "calibration_2023" / "observed_capture_value_comparison.csv"

SCENARIOS = [
    "2030-NT-balticBaseline", "2030-NT-balticHigh",
    "2040-NT-balticBaseline", "2040-NT-balticHigh",
    "2040-DE-balticHigh", "2040-GA-balticHigh",
]
OFFSHORE = ["offwind-ac", "offwind-dc", "offwind-float"]
BALTIC_STATES = ["PL", "FI", "EE", "LV", "LT"]
NS_ZONES = ["DE", "NL", "BE", "DK1", "DK2", "FR"]
DK_LON_CUT = 11.0


def zone_buses(n, zone):
    ac = n.buses[n.buses.carrier == "AC"]
    if zone in ("DK1", "DK2"):
        dk = ac[ac.country == "DK"]
        west = dk.x < DK_LON_CUT
        return list(dk[west if zone == "DK1" else ~west].index)
    return list(ac[ac.country == zone].index)


def offshore_capture(n, zone):
    """Return p_nom, energy, zone load energy, penetration and CV for a zone.

    Snapshot-weighted throughout (correct at any time resolution); zone load
    energy is always computed (even for zero-offshore zones) so the aggregate
    penetration can be a true ratio of sums."""
    buses = zone_buses(n, zone)
    prices = n.buses_t.marginal_price
    g = n.generators
    w = n.snapshot_weightings.generators
    # zone load energy (MWh) — needed for the aggregate even with no offshore
    loads = n.loads[n.loads.bus.isin(buses)]
    lcols = loads.index.intersection(n.loads_t.p_set.columns)
    load_energy = float((n.loads_t.p_set[lcols].sum(axis=1) * w).sum()) if len(lcols) else np.nan
    out = dict(p_nom=0.0, energy_GWh=0.0, load_GWh=load_energy / 1e3 if load_energy == load_energy else np.nan,
               penetration=np.nan, CV=np.nan)
    ids = g[(g.bus.isin(buses)) & (g.carrier.isin(OFFSHORE))].index
    ids = [i for i in ids if i in n.generators_t.p.columns]
    if not ids:
        return out
    P = n.generators_t.p[ids].sum(axis=1)
    energy = float((P * w).sum())
    out["p_nom"] = float(g.loc[ids, "p_nom"].sum())
    if energy <= 0:
        return out
    # capture price = generation-weighted shadow price at each gen's bus
    num = pd.Series(0.0, index=P.index)
    for gid in ids:
        bus = g.at[gid, "bus"]
        if bus in prices.columns:
            num += n.generators_t.p[gid] * prices[bus]
    capture_price = float((num * w).sum()) / energy
    # zone baseload = weighted time-mean across the zone's bus prices. The
    # numerator uses each generator's OWN bus price; this denominator averages
    # the zone's AC buses UNWEIGHTED, i.e. a single posted zonal price (the
    # Jacquet/Efthymiadou convention). The two coincide exactly when offshore
    # spans all of a zone's buses (verified: PL, NL deltas 0.000); the only gap
    # is in multi-bus zones with inland buses that carry no offshore (DE ~0.16,
    # possibly SE). The DE 0.908 calibration comes from 1.04 (symmetric), and the
    # DK2 +0.14 anchor and Baltic headline are single-offshore-bus and unaffected.
    pbuses = [b for b in buses if b in prices.columns]
    base = float((prices[pbuses].mean(axis=1) * w).sum() / w.sum())
    out["energy_GWh"] = energy / 1e3
    out["penetration"] = energy / load_energy if load_energy and load_energy > 0 else np.nan
    out["CV"] = capture_price / base if base else np.nan
    return out


# ---------------------------------------------------------------------------
# 1. Per-zone capture values for every scenario
# ---------------------------------------------------------------------------
print("Computing offshore capture values per zone × scenario ...")
records = []
for s in SCENARIOS:
    p = SCEN_DIR / f"{s}.nc"
    if not p.exists():
        print(f"  (missing {s})")
        continue
    n = pypsa.Network(p)
    for zone in BALTIC_STATES + NS_ZONES:
        r = offshore_capture(n, zone)
        r.update(scenario=s, zone=zone,
                 region="Baltic" if zone in BALTIC_STATES else "NorthSea")
        records.append(r)

proj = pd.DataFrame(records)
if proj.empty:
    sys.exit(f"FATAL: no scenario networks found in {SCEN_DIR} — run 1.07 first.")
proj.to_csv(OUT / "projected_capture_values.csv", index=False)
print(f"Saved per-zone table -> {OUT / 'projected_capture_values.csv'}")

# ---------------------------------------------------------------------------
# 2. Baltic aggregate: energy-weighted CV, TRUE aggregate penetration
# ---------------------------------------------------------------------------
def agg_cv(df_sub):
    """CV is energy-weighted across producing zones; penetration is the TRUE
    aggregate (total offshore energy / total zone load, ALL zones incl. those
    with zero offshore) — not the energy-weighted mean of per-zone ratios,
    which Cauchy-Schwarz guarantees to overstate (audit: ~0.24 vs ~0.18)."""
    d = df_sub.dropna(subset=["CV"])
    d = d[d.energy_GWh > 0]
    if d.empty:
        return np.nan, np.nan, np.nan
    w = d.energy_GWh
    cv = (d.CV * w).sum() / w.sum()
    total_load = df_sub.load_GWh.sum()   # all zones, incl. zero-offshore
    pen = d.energy_GWh.sum() / total_load if total_load > 0 else np.nan
    return cv, pen, d.energy_GWh.sum()


# ---------------------------------------------------------------------------
# 3. DK2 bias correction (data-driven from the 2023 validation)
# ---------------------------------------------------------------------------
val = pd.read_csv(VALID_CSV).set_index("zone")
bias_dk2 = float(val.loc["DK2", "CV_pypsa"] - val.loc["DK2", "CV_obs"])   # central
bias_dk1 = float(val.loc["DK1", "CV_pypsa"] - val.loc["DK1", "CV_obs"])   # milder NS bound
print(f"\nValidated CV bias (PyPSA over-statement, 2023):")
print(f"  DK2 (small/congested, Baltic-facing)  = {bias_dk2:.3f}  -> central correction")
print(f"  DK1 (better-connected North Sea)      = {bias_dk1:.3f}  -> mild bound")

rows = []
for year in [2030, 2040]:
    for tag, scn in [("baseline", f"{year}-NT-balticBaseline"),
                     ("high", f"{year}-NT-balticHigh")]:
        sub = proj[(proj.scenario == scn) & (proj.region == "Baltic")]
        cv_raw, pen, energy = agg_cv(sub)
        rows.append({
            "year": year, "buildout": tag,
            "baltic_offshore_GWh": energy,
            "baltic_offshore_penetration": pen,
            "CV_raw": cv_raw,
            "CV_corr_central": cv_raw - bias_dk2 if not np.isnan(cv_raw) else np.nan,
            "CV_corr_mild": cv_raw - bias_dk1 if not np.isnan(cv_raw) else np.nan,
        })
corr = pd.DataFrame(rows)
print("\nBaltic-states offshore capture value (energy-weighted across PL/FI/EE/LV/LT):")
print(corr.round(3).to_string(index=False))
corr.round(4).to_csv(OUT / "baltic_capture_value_corrected.csv", index=False)

# reference DK2 2023 figures for the analogue justification (energy and, where
# available, true penetration — previously this print mislabelled TWh as
# penetration, an audit finding)
dk2_energy_twh = val.loc["DK2", "energy_obs_GWh"] / 1e3
print(f"\nAnalogue check -- DK2 2023 observed offshore energy was ~{dk2_energy_twh:.1f} TWh"
      f" (see 1.09 for the validated penetration axis); Baltic projected"
      f" penetrations above show whether the DK2 analogue is conservative.")

# ---------------------------------------------------------------------------
# 4. Figure: raw vs bias-corrected Baltic capture value
# ---------------------------------------------------------------------------
fig, ax = plt.subplots(figsize=(9, 5))
x = np.arange(len(corr))
labels = [f"{r.year}\n{r.buildout}" for r in corr.itertuples()]
ax.bar(x - 0.2, corr.CV_raw, 0.4, label="PyPSA raw (optimistic)", color="steelblue")
ax.bar(x + 0.2, corr.CV_corr_central, 0.4,
       label=f"DK2-corrected (−{bias_dk2:.2f}, conservative)", color="indianred")
for xi, r in zip(x, corr.itertuples()):
    if not np.isnan(r.CV_corr_central):
        ax.plot([xi + 0.2, xi + 0.2], [r.CV_corr_central, r.CV_corr_mild],
                color="k", lw=1)  # range whisker to milder DK1 bound
ax.axhline(1.0, color="k", ls="--", lw=1, label="CV = 1 (no cannibalisation)")
ax.set_xticks(x); ax.set_xticklabels(labels)
ax.set_ylabel("Offshore wind capture value")
ax.set_title("Projected Baltic offshore CV: raw vs constant DK2 bias\n"
             "(v1 robustness rung — canonical correction is the 1.09 penetration fit)")
ax.legend(fontsize=8)
ax.grid(axis="y", alpha=0.3)
plt.tight_layout()
plt.savefig(OUT / "fig4_baltic_capture_value.png", dpi=130)
plt.close()
print(f"\nSaved figure -> {OUT / 'fig4_baltic_capture_value.png'}")
