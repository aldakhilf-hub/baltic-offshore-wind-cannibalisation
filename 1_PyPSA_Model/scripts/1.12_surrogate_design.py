"""
1.12_surrogate_design.py  ·  TRACK 1 — Surrogate emulator, step 1 of 4

Generate the experimental design for the PyPSA surrogate (Act 3).

We want a fast XGBoost emulator of the validated PyPSA model. To train it we
need PyPSA outputs spread across the realistic input envelope. This script
produces that design matrix — it runs NO simulation, it only decides *which*
55 input combinations the heavy runner (1.13) will solve.

Design = 50 Latin-Hypercube samples over 8 inputs + 5 policy-anchor points.
  - LHS gives even marginal coverage of every input dimension without the
    combinatorial blow-up of a full factorial (2^8 = 256).
  - The 5 anchors pin the surrogate to the exact TYNDP scenarios the thesis
    quotes directly (2030-NT, 2040-NT, 2040-DE, 2040-GA, 2030-NT-balticHigh),
    so it is accurate where it matters most. Their input values are read from
    the real parsed TYNDP data, not guessed.

The 8 inputs (ranges from 4_PLAN_Surrogate_Model.md §3.1):
  gas        gas price            EUR/MWh_th   15 – 100
  co2        CO2 price            EUR/tCO2      50 – 200
  baltic_off Baltic offshore tot  GW           10 – 150   (PL+FI+EE+LV+LT)
  ns_off     North-Sea offshore   GW           30 – 450   (DE+NL+BE+DK+GB+NO+SE+IE+FR)
  solar      solar EU-14          GW          200 – 1050

NOTE — deviation from 4_PLAN_Surrogate_Model.md §3.1: the plan proposed ns_off
30-250 and solar 200-800, but the real TYNDP anchors reach ns_off 440 GW and
solar 1020 GW (2040-HIGH). Sampling only to 250/800 would leave the headline
2040 scenarios OUTSIDE the LHS training box, forcing the surrogate to
extrapolate exactly where the thesis quotes it. We therefore widen ns_off to
450 and solar to 1050 so the LHS envelope contains every anchor.
  dem_mult   demand vs 2019       —           1.0 – 2.0
  batt       battery EU-14        GW           50 – 400
  h2         electrolyser EU-14   GW           30 – 200

Each LHS row also carries a `year` (2030 or 2040) so the surrogate learns the
year-dependent corrections (DK split, H2 dicts) the runner applies. Anchors
carry their own year.

Output:
  ../results/surrogate/design_inputs.csv   (one row per PyPSA run to perform)

Usage:
  python 1.12_surrogate_design.py            # 50 LHS + 5 anchors = 55 rows
  python 1.12_surrogate_design.py --n 80     # more LHS samples (anchors always added)
"""
import argparse
import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import qmc

HERE = Path(__file__).resolve().parent
DATA = HERE.parent / "data"
OUT_DIR = HERE.parent / "results" / "surrogate"
OUT_DIR.mkdir(parents=True, exist_ok=True)

SEED = 20260604  # fixed → design is reproducible (no Math.random equivalent needed)

# 14-country focus geography (same split the rest of Track 1 uses)
BALTIC = ["PL", "FI", "EE", "LV", "LT"]
NORTHSEA = ["DE", "FR", "NL", "BE", "DK", "GB", "IE", "NO", "SE"]
FOCUS = NORTHSEA + BALTIC

# 8 inputs: (name, low, high)
INPUTS = [
    ("gas",        15.0, 100.0),
    ("co2",        50.0, 200.0),
    ("baltic_off", 10.0, 150.0),
    ("ns_off",     30.0, 450.0),
    ("solar",     200.0, 1050.0),
    ("dem_mult",    1.0,   2.0),
    ("batt",       50.0, 400.0),
    ("h2",         30.0, 200.0),
]
NAMES = [n for n, _, _ in INPUTS]
LOW = np.array([lo for _, lo, _ in INPUTS])
HIGH = np.array([hi for _, _, hi in INPUTS])


# ---------------------------------------------------------------------------
# Read the real TYNDP totals so the 5 anchor points are faithful
# ---------------------------------------------------------------------------
def _load_scenario_module():
    """Import 1.07 (filename has dots) to reuse its H2 electrolyser dict."""
    path = HERE / "1.07_run_scenarios.py"
    spec = importlib.util.spec_from_file_location("scn07", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _cap_total(cap, tech, countries, traj, year):
    s = cap[(cap.tech == tech) & (cap.country.isin(countries))
            & (cap.trajectory == traj) & (cap.year == year)]
    return float(s.MW.sum()) / 1e3  # GW


def _batt_total(batt, traj, year):
    s = batt[(batt.country.isin(FOCUS)) & (batt.trajectory == traj) & (batt.year == year)]
    return float(s.power_MW.sum()) / 1e3  # GW


def _dem_mult(dem, scenario, year):
    """Energy-weighted EU-14 demand multiplier vs 2019 for the focus geography.

    Mirrors 1.07.demand_growth: growth_vs_2019 is stored only at the 2040 row,
    so 2030 is the linear 2019->2040 interpolation (not a flat 1.0)."""
    base = dem[(dem.country.isin(FOCUS)) & (dem.year == 2019)].set_index("country").demand_TWh
    g2040 = dem[(dem.country.isin(FOCUS)) & (dem.scenario == scenario)
                & (dem.year == 2040)].set_index("country").growth_vs_2019
    common = g2040.index.intersection(base.index)
    g2040 = g2040.reindex(common).fillna(1.0)
    b = base.reindex(common).fillna(0.0)
    if b.sum() <= 0:
        return 1.0
    if year == 2030:
        g = 1.0 + (g2040 - 1.0) * (2030 - 2019) / (2040 - 2019)
    else:
        g = g2040
    return float((g * b).sum() / b.sum())


def build_anchors():
    cap = pd.read_csv(DATA / "tyndp/parsed_capacity.csv")
    prices = pd.read_csv(DATA / "tyndp/parsed_prices.csv").set_index("year")
    batt = pd.read_csv(DATA / "tyndp/parsed_batteries.csv")
    dem = pd.read_csv(DATA / "tyndp/parsed_demand.csv")
    scn = _load_scenario_module()

    def h2_total(year):
        return sum(scn.H2_ELECTROLYSER_GW[year].get(c, 0.0) for c in FOCUS)

    # (label, year, capacity-trajectory, baltic-trajectory, demand scenario)
    defs = [
        ("anchor_2030-NT",          2030, "BEST", "BEST", "DE"),
        ("anchor_2040-NT",          2040, "BEST", "BEST", "DE"),
        ("anchor_2040-DE-balticHi", 2040, "HIGH", "HIGH", "DE"),
        ("anchor_2040-GA-balticHi", 2040, "HIGH", "HIGH", "GA"),
        ("anchor_2030-NT-balticHi", 2030, "BEST", "HIGH", "DE"),
    ]
    rows = []
    for label, yr, traj, btraj, dscn in defs:
        pr = prices.loc[yr]
        rows.append({
            "run_id": label,
            "kind": "anchor",
            "year": yr,
            "gas": float(pr.gas_eurMWh),
            "co2": float(pr.co2_eurton),
            "baltic_off": _cap_total(cap, "offwind", BALTIC, btraj, yr),
            "ns_off": _cap_total(cap, "offwind", NORTHSEA, traj, yr),
            "solar": _cap_total(cap, "solar", FOCUS, traj, yr),
            "dem_mult": _dem_mult(dem, dscn, yr),
            "batt": _batt_total(batt, traj, yr),
            "h2": h2_total(yr),
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# LHS sample
# ---------------------------------------------------------------------------
def build_lhs(n):
    sampler = qmc.LatinHypercube(d=len(INPUTS), seed=SEED)
    unit = sampler.random(n)                       # n x 8 in [0,1)
    scaled = qmc.scale(unit, LOW, HIGH)            # to real ranges
    df = pd.DataFrame(scaled, columns=NAMES).round(3)
    # split years evenly across the LHS block so both projection horizons are covered
    df.insert(0, "year", np.where(np.arange(n) % 2 == 0, 2030, 2040))
    df.insert(0, "kind", "lhs")
    df.insert(0, "run_id", [f"lhs_{i:03d}" for i in range(n)])
    return df


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=50, help="number of LHS samples")
    args = ap.parse_args()

    lhs = build_lhs(args.n)
    anchors = build_anchors()
    design = pd.concat([lhs, anchors], ignore_index=True)
    design = design[["run_id", "kind", "year"] + NAMES]

    out = OUT_DIR / "design_inputs.csv"
    design.to_csv(out, index=False)

    print(f"Wrote {len(design)} runs ({len(lhs)} LHS + {len(anchors)} anchors) -> {out}")
    print("\nAnchor points (faithful TYNDP totals):")
    with pd.option_context("display.width", 160, "display.max_columns", 20):
        print(anchors[["run_id", "year"] + NAMES].to_string(index=False))
    print("\nLHS coverage (min / median / max per input):")
    print(lhs[NAMES].agg(["min", "median", "max"]).round(1).to_string())


if __name__ == "__main__":
    main()
