"""
1.13_surrogate_runs.py  ·  TRACK 1 — Surrogate emulator, step 2 of 4

Produce the surrogate training data: one row of (8 inputs -> per-zone offshore
CV + price) per PyPSA scenario. Rows come from TWO sources:

  (a) HARVEST — the ~20 already-solved networks with identical v3 physics
      (6 canonical scenarios + 14 gas-shock cells). Free: no re-solve. They
      densely cover the gas + buildout axes.
  (b) SOLVE   — new Latin-Hypercube points from 1.12 that move the OTHER six
      inputs (solar, battery, H2, demand, CO2, NS-offshore) which are pinned at
      defaults in every harvested run. Solved at reduced time resolution
      (--every N hours) for speed.

Both sources are extracted by the SAME code path, and the 8 input features are
MEASURED from the solved network (realized capacities) so a harvested row and a
freshly-solved row are directly comparable:
  gas, co2, dem_mult  -> the knobs as set (back-derived for harvested runs)
  baltic_off, ns_off, solar, batt, h2 -> realized GW summed from the network
(realized capacity can be < requested when resource potential p_nom_max binds;
the surrogate must learn from what was actually in the model.)

It generalises 1.07.run() to 8 continuous inputs, reusing 1.07's mutation
helpers so the physics stay identical. Deliberate departures from 1.07
(documented for the thesis): no policy offshore caps (only physical p_nom_max
binds), and demand applied as one uniform EU-14 multiplier.

DOWNSAMPLING is validated, not assumed: --every coarsens the snapshots and
rescales snapshot_weightings so energy/cost totals stay correct. Run the SAME
config at full res and at --every N and confirm CV agrees before trusting the
coarse grid (see --pilot + the resolution-check workflow in the README).

Robustness: outputs append after each row; done rows are skipped (resumable);
networks are extracted then discarded unless --keep-nc.

Outputs (../results/surrogate/):
  run_outputs.csv   long: one row per (run_id, zone)
  run_summary.csv   one row per run: Baltic/NS aggregate CV + price + ratios

Usage:
  python 1.13_surrogate_runs.py --harvest                      # extract ~20 existing (free)
  python 1.13_surrogate_runs.py --pilot --every 3              # ONE solve at 3-hourly, timed
  python 1.13_surrogate_runs.py --pilot                        # ONE solve at full res, timed
  python 1.13_surrogate_runs.py --every 3                      # all LHS rows at 3-hourly
  python 1.13_surrogate_runs.py --rows lhs_000 --every 1       # explicit row, full res
"""
import argparse
import importlib.util
import time
from pathlib import Path

import numpy as np
import pandas as pd
import pypsa

HERE = Path(__file__).resolve().parent
DATA = HERE.parent / "data"
RES = HERE.parent / "results" / "surrogate"
RES.mkdir(parents=True, exist_ok=True)
DESIGN_CSV = RES / "design_inputs.csv"
OUT_LONG = RES / "run_outputs.csv"
OUT_SUMMARY = RES / "run_summary.csv"
NC_DIR = Path.home() / "pypsa-eur/results/surrogate_runs"

# the two harvestable solved-network directories (identical v3 physics)
HARVEST_DIRS = [Path.home() / "pypsa-eur/results/scenarios_tyndp_v3",
                Path.home() / "pypsa-eur/results/gas_shock"]

BALTIC = ["PL", "FI", "EE", "LV", "LT"]
NORTHSEA = ["DE", "FR", "NL", "BE", "DK", "GB", "IE", "NO", "SE"]
FOCUS = NORTHSEA + BALTIC
OFFSHORE = ["offwind-ac", "offwind-dc", "offwind-float"]
NS_ZONES = ["DE", "FR", "NL", "BE", "DK1", "DK2", "GB", "IE", "NO", "SE"]
DK_LON_CUT = 11.0
# model-limitation zones (see 1.11): per-zone rows are kept in run_outputs.csv
# for transparency, but the quotable ns_* aggregate columns exclude them
AGG_EXCLUDE = ["GB", "NO"]

# bias fit from 1.09 (applied BEFORE training, per the design decision)
BIAS_A, BIAS_B = -0.005, 0.399
INPUT_COLS = ["gas", "co2", "dem_mult", "baltic_off", "ns_off", "solar", "batt", "h2"]


# ---------------------------------------------------------------------------
# Reuse 1.07's helpers + TYNDP tables (single source of truth for the physics)
# ---------------------------------------------------------------------------
def load_scn():
    spec = importlib.util.spec_from_file_location("scn07", HERE / "1.07_run_scenarios.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


SCN = load_scn()
DEMAND = pd.read_csv(DATA / "tyndp/parsed_demand.csv")


def scenario_dem_mult(demand_scn, year):
    """Aggregate EU-14 demand multiplier 1.07 effectively applied (energy-weighted
    growth vs 2019; 2030 interpolates 2019->2040). Matches 1.12's anchor logic."""
    base = DEMAND[(DEMAND.country.isin(FOCUS)) & (DEMAND.year == 2019)].set_index("country").demand_TWh
    g2040 = DEMAND[(DEMAND.country.isin(FOCUS)) & (DEMAND.scenario == demand_scn)
                   & (DEMAND.year == 2040)].set_index("country").growth_vs_2019
    common = g2040.index.intersection(base.index)
    g2040 = g2040.reindex(common).fillna(1.0)
    b = base.reindex(common).fillna(0.0)
    if b.sum() <= 0:
        return 1.0
    g = 1.0 + (g2040 - 1.0) * (2030 - 2019) / (2040 - 2019) if year == 2030 else g2040
    return float((g * b).sum() / b.sum())


def country_shares(values_by_country, countries):
    w = pd.Series({c: max(values_by_country.get(c, 0.0), 0.0) for c in countries})
    if w.sum() <= 0:
        w[:] = 1.0
    return w / w.sum()


def build_allocation_keys():
    """TYNDP-HIGH-2040 capacity shares used to split regional totals -> countries."""
    cap = pd.read_csv(DATA / "tyndp/parsed_capacity.csv")
    batt = pd.read_csv(DATA / "tyndp/parsed_batteries.csv")

    def cap_by(tech):
        s = cap[(cap.tech == tech) & (cap.trajectory == "HIGH") & (cap.year == 2040)]
        return dict(zip(s.country, s.MW))

    bt = batt[(batt.trajectory == "HIGH") & (batt.year == 2040)]
    return {
        "baltic_off": country_shares(cap_by("offwind"), BALTIC),
        "ns_off": country_shares(cap_by("offwind"), NORTHSEA),
        "solar": country_shares(cap_by("solar"), FOCUS),
        "batt": country_shares(dict(zip(bt.country, bt.power_MW)), FOCUS),
    }


KEYS = build_allocation_keys()


# ---------------------------------------------------------------------------
# Build a network from a design row (new SOLVE path)
# ---------------------------------------------------------------------------
def set_thermal_costs(n, year, gas, co2):
    pr = SCN.PRICES.loc[year]
    fuel = {"CCGT": gas, "OCGT": gas, "coal": pr.coal_eurMWh,
            "lignite": pr.lignite_eurMWh, "oil": pr.oil_eurMWh}
    for car, (eff, vom, co2i) in SCN.THERMAL.items():
        n.generators.loc[n.generators.carrier == car, "marginal_cost"] = vom + (fuel[car] + co2 * co2i) / eff
    n.generators.loc[n.generators.carrier == "nuclear", "marginal_cost"] = SCN.NUCLEAR_MC


def place_offshore(n, region_total_gw, region, year):
    key = KEYS["baltic_off"] if region == "baltic" else KEYS["ns_off"]
    realized = 0.0
    for c, share in key.items():
        target = region_total_gw * 1e3 * share
        realized += SCN.apply_dk_offshore_split(n, target, year) if c == "DK" \
            else SCN.set_capacity(n, c, OFFSHORE, target)
    return realized / 1e3


def place_simple(n, total_gw, key, carriers):
    return sum(SCN.set_capacity(n, c, carriers, total_gw * 1e3 * s) for c, s in key.items()) / 1e3


def add_scaled_h2(n, year, h2_total_gw):
    """Scale ONLY the electrolyser fleet capacity to hit the surrogate input
    (h2 = electrolyser GW, the flexibility / price-floor knob). H2 DEMAND stays
    at the realistic year-level TYNDP value -- scaling demand too (as a first
    version did) produced ~400+ TWh of mandatory H2 load, which both distorted
    every price and blew up the H2-store bound (Kappa ~1e13 -> infeasible). A
    big electrolyser + modest fixed demand + store is exactly the flexible-
    absorption / floor mechanism we want to vary."""
    base_cap, base_dem = SCN.H2_ELECTROLYSER_GW.get(year, {}), SCN.H2_DEMAND_TWH.get(year, {})
    focus_total = sum(base_cap.get(c, 0.0) for c in FOCUS)
    scale = (h2_total_gw / focus_total) if focus_total > 0 else 0.0
    saved = SCN.H2_ELECTROLYSER_GW, SCN.H2_DEMAND_TWH
    try:
        SCN.H2_ELECTROLYSER_GW = {year: {c: v * scale for c, v in base_cap.items()}}
        SCN.H2_DEMAND_TWH = {year: dict(base_dem)}   # demand fixed, not scaled
        SCN.add_h2_layer(n, year)
    finally:
        SCN.H2_ELECTROLYSER_GW, SCN.H2_DEMAND_TWH = saved


def add_load_shedding(n):
    """Value-of-lost-load backstop. The LHS samples demand (dem_mult) and
    generation INDEPENDENTLY, so it readily creates physically under-built
    systems that have no feasible dispatch; the backstop makes every point
    solvable, pricing scarcity instead of failing. PARITY (audit fix): uses
    1.07's implementation — identical to the validated baseline and to the
    harvested networks (carrier 'load', 100 kEUR/MWh, p_nom=inf at all buses)
    — so harvested and fresh training rows price scarcity identically."""
    SCN.add_load_shedding(n)


def downsample(n, every):
    """Coarsen to every Nth snapshot; rescale weightings so totals stay correct."""
    if every and every > 1:
        snaps = n.snapshots[::every]
        n.set_snapshots(snaps)
        n.snapshot_weightings.loc[:, :] = float(every)


def configure(row, every):
    yr = int(row.year)
    n = pypsa.Network(SCN.PREPARED)
    downsample(n, every)
    set_thermal_costs(n, yr, float(row.gas), float(row.co2))
    SCN.apply_thermal_phaseout(n, yr)
    place_offshore(n, float(row.baltic_off), "baltic", yr)
    place_offshore(n, float(row.ns_off), "northsea", yr)
    place_simple(n, float(row.solar), KEYS["solar"], ["solar"])
    for c, share in KEYS["batt"].items():
        SCN.add_battery(n, c, float(row.batt) * 1e3 * share, 4.0)
    load_ids = n.loads[n.loads.bus.map(n.buses.country).isin(FOCUS)].index
    cols = [l for l in load_ids if l in n.loads_t.p_set.columns]
    if cols:
        n.loads_t.p_set[cols] *= float(row.dem_mult)
    add_scaled_h2(n, yr, float(row.h2))
    SCN.add_dsr(n)           # correction (F): DSR scarcity tier, parity with 1.07
    add_load_shedding(n)
    SCN.add_noisy_costs(n)   # baseline/harvest parity (seeded degeneracy-breaking)
    return n


# ---------------------------------------------------------------------------
# Extraction — identical for harvested and freshly-solved networks
# ---------------------------------------------------------------------------
def zone_buses(n, zone):
    ac = n.buses[n.buses.carrier == "AC"]
    if zone in ("DK1", "DK2"):
        dk = ac[ac.country == "DK"]
        west = dk.x < DK_LON_CUT
        return list(dk[west if zone == "DK1" else ~west].index)
    return list(ac[ac.country == zone].index)


def measure_realized(n):
    """Realized GW per surrogate input, summed from the solved network."""
    g, b = n.generators, n.buses
    country = g.bus.map(b.country)
    off = g.carrier.isin(OFFSHORE)
    solar = g.carrier == "solar"
    out = {
        "baltic_off": g.loc[off & country.isin(BALTIC), "p_nom"].sum() / 1e3,
        "ns_off": g.loc[off & country.isin(NORTHSEA), "p_nom"].sum() / 1e3,
        "solar": g.loc[solar & country.isin(FOCUS), "p_nom"].sum() / 1e3,
    }
    if len(n.storage_units):
        su = n.storage_units
        out["batt"] = su.loc[(su.carrier == "battery")
                             & su.bus.map(b.country).isin(FOCUS), "p_nom"].sum() / 1e3
    else:
        out["batt"] = 0.0
    if len(n.links):
        el = n.links[n.links.carrier == "electrolyser"]
        out["h2"] = el.p_nom.sum() / 1e3
    else:
        out["h2"] = 0.0
    return {f"realized_{k}": float(v) for k, v in out.items()}


def offshore_capture(n, zone):
    buses = zone_buses(n, zone)
    prices = n.buses_t.marginal_price
    g = n.generators
    ids = [i for i in g[(g.bus.isin(buses)) & (g.carrier.isin(OFFSHORE))].index
           if i in n.generators_t.p.columns]
    pbuses = [b for b in buses if b in prices.columns]
    base = prices[pbuses].mean(axis=1).mean() if pbuses else np.nan
    if not ids:
        return dict(p_nom=0.0, energy_GWh=0.0, penetration=np.nan,
                    mean_price=base, capture_price=np.nan, CV_raw=np.nan)
    P = n.generators_t.p[ids].sum(axis=1)
    p_nom = float(g.loc[ids, "p_nom"].sum())
    if P.sum() <= 0:
        return dict(p_nom=p_nom, energy_GWh=0.0, penetration=np.nan,
                    mean_price=base, capture_price=np.nan, CV_raw=np.nan)
    num = pd.Series(0.0, index=P.index)
    for gid in ids:
        bus = g.at[gid, "bus"]
        if bus in prices.columns:
            num += n.generators_t.p[gid] * prices[bus]
    capture = num.sum() / P.sum()
    loads = n.loads[n.loads.bus.isin(buses)]
    lcols = loads.index.intersection(n.loads_t.p_set.columns)
    load_e = n.loads_t.p_set[lcols].sum().sum() if len(lcols) else np.nan
    pen = P.sum() / load_e if load_e and load_e > 0 else np.nan
    return dict(p_nom=p_nom, energy_GWh=P.sum() / 1e3, penetration=pen,
                mean_price=base, capture_price=capture,
                CV_raw=(capture / base if base else np.nan))


def extract(n, meta):
    """meta = dict(run_id, kind, year, gas, co2, dem_mult). Returns (long, summary)."""
    realized = measure_realized(n)
    long_rows = []
    for zone in BALTIC + NS_ZONES:
        d = offshore_capture(n, zone)
        is_baltic = zone in BALTIC
        d["region"] = "Baltic" if is_baltic else "NorthSea"
        pen = d["penetration"]
        d["bias_pred"] = (BIAS_A + BIAS_B * pen) if pen == pen else np.nan
        # The bias correction is the DK2-analogue device for SMALL, congested,
        # Baltic-facing zones -- PyPSA was validated ACCURATE in the big
        # interconnected North Sea zones (1.04/1.08), so correcting them would
        # extrapolate the penetration fit far past its 0-38% validation range
        # and crush their CV implausibly. Correct Baltic only; NS stays raw.
        if is_baltic:
            d["CV_corr"] = (d["CV_raw"] - d["bias_pred"]) if d["CV_raw"] == d["CV_raw"] else np.nan
        else:
            d["CV_corr"] = d["CV_raw"]
        d.update(zone=zone, **meta, **realized)
        long_rows.append(d)
    long = pd.DataFrame(long_rows)

    def agg(region, field):
        sub = long[(long.region == region) & (long.energy_GWh > 0)
                   & (~long.zone.isin(AGG_EXCLUDE))].dropna(subset=[field])
        if sub.empty:
            return np.nan
        w = sub.energy_GWh
        return float((sub[field] * w).sum() / w.sum())

    s = dict(meta, **realized)
    s.update(baltic_CV_raw=agg("Baltic", "CV_raw"), baltic_CV_corr=agg("Baltic", "CV_corr"),
             ns_CV_raw=agg("NorthSea", "CV_raw"), ns_CV_corr=agg("NorthSea", "CV_corr"),
             baltic_price=agg("Baltic", "mean_price"), ns_price=agg("NorthSea", "mean_price"))
    bcv, ncv, np_, bp = s["baltic_CV_corr"], s["ns_CV_corr"], s["ns_price"], s["baltic_price"]
    s["cv_ratio_ns_over_baltic"] = ncv / bcv if (bcv == bcv and bcv not in (0,)) else np.nan
    s["price_ratio_baltic_over_ns"] = bp / np_ if (np_ == np_ and np_ not in (0,)) else np.nan
    return long, pd.DataFrame([s])


# ---------------------------------------------------------------------------
# Harvest metadata for an existing solved-network filename
# ---------------------------------------------------------------------------
def harvest_meta(path):
    """Derive (run_id, year, gas, co2, dem_mult) from an existing .nc filename."""
    stem = path.stem                       # e.g. 2040-NT-balticHigh__gas080
    base, _, gtag = stem.partition("__")
    if base not in SCN.SCENARIOS:
        return None
    p = SCN.SCENARIOS[base]
    yr = p["year"]
    pr = SCN.PRICES.loc[yr]
    gas = float(gtag.replace("gas", "")) if gtag.startswith("gas") else float(pr.gas_eurMWh)
    return dict(run_id=stem, kind="harvest", year=yr, gas=gas,
                co2=float(pr.co2_eurton), dem_mult=scenario_dem_mult(p["demand_scn"], yr))


# ---------------------------------------------------------------------------
# I/O
# ---------------------------------------------------------------------------
def append_csv(df, path):
    df.to_csv(path, mode="a", header=not path.exists(), index=False)


def done_run_ids():
    return set(pd.read_csv(OUT_SUMMARY).run_id.astype(str)) if OUT_SUMMARY.exists() else set()


def run_harvest(force):
    already = set() if force else done_run_ids()
    files = [f for d in HARVEST_DIRS if d.exists() for f in sorted(d.glob("*.nc"))]
    print(f"Harvest: {len(files)} solved networks found.")
    done = 0
    for f in files:
        meta = harvest_meta(f)
        if meta is None:
            print(f"  skip (unknown scenario): {f.name}")
            continue
        if meta["run_id"] in already:
            continue
        n = pypsa.Network(f)
        long, summary = extract(n, meta)
        append_csv(long, OUT_LONG)
        append_csv(summary, OUT_SUMMARY)
        s = summary.iloc[0]
        print(f"  harvested {meta['run_id']:32s} BalticCVc={s.baltic_CV_corr:.3f} "
              f"NS CVc={s.ns_CV_corr:.3f} (gas={meta['gas']:.0f})")
        done += 1
    print(f"Harvested {done} new rows -> {OUT_SUMMARY.name}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--harvest", action="store_true", help="extract existing solved networks (no solve)")
    ap.add_argument("--pilot", action="store_true", help="solve ONE LHS row, time it, stop")
    ap.add_argument("--every", type=int, default=1, help="snapshot stride (3 = 3-hourly)")
    ap.add_argument("--rows", nargs="*", help="explicit run_ids to solve")
    ap.add_argument("--start", type=int, default=None)
    ap.add_argument("--end", type=int, default=None)
    ap.add_argument("--keep-nc", action="store_true")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    if args.harvest:
        run_harvest(args.force)
        return

    design = pd.read_csv(DESIGN_CSV)
    if args.rows:
        design = design[design.run_id.isin(args.rows)]
    elif args.start is not None or args.end is not None:
        design = design.iloc[(args.start or 0):(args.end if args.end is not None else len(design))]
    if args.pilot:
        design = design.head(1)

    already = set() if args.force else done_run_ids()
    todo = design[~design.run_id.isin(already)]
    print(f"{len(design)} selected, {len(todo)} to solve "
          f"(every={args.every} -> {'full 8760h' if args.every==1 else f'{8760//args.every}h'}).")
    if args.keep_nc:
        NC_DIR.mkdir(parents=True, exist_ok=True)

    times = []
    for i, row in enumerate(todo.itertuples(index=False), 1):
        t0 = time.time()
        print(f"\n[{i}/{len(todo)}] {row.run_id} (yr {int(row.year)}) "
              f"gas={row.gas} co2={row.co2} baltic_off={row.baltic_off} ns_off={row.ns_off}")
        try:
            n = configure(row, args.every)
            # Solver parity with the validated baseline + re-solved harvest
            # networks (crossover OFF -> interior duals, same tolerances);
            # NumericFocus + BarHomogeneous harden the barrier against the
            # ill-conditioned extremes of the LHS box (large capacities/loads).
            status, cond = n.optimize(
                solver_name="gurobi",
                solver_options={"threads": 8, "method": 2, "crossover": 0,
                                "BarConvTol": 1e-6, "FeasibilityTol": 1e-6,
                                "NumericFocus": 2, "BarHomogeneous": 1})
            if status != "ok":
                print(f"  !! non-optimal ({status}/{cond}) -- skipping, not written")
                continue
            meta = dict(run_id=row.run_id, kind=row.kind, year=int(row.year),
                        gas=float(row.gas), co2=float(row.co2), dem_mult=float(row.dem_mult))
            long, summary = extract(n, meta)
            append_csv(long, OUT_LONG)
            append_csv(summary, OUT_SUMMARY)
            if args.keep_nc:
                n.export_to_netcdf(NC_DIR / f"{row.run_id}.nc")
            dt = time.time() - t0
            times.append(dt)
            s = summary.iloc[0]
            print(f"  solved {dt/60:.1f} min | BalticCVc={s.baltic_CV_corr:.3f} "
                  f"NS CVc={s.ns_CV_corr:.3f} | realized off baltic={s.realized_baltic_off:.0f} "
                  f"ns={s.realized_ns_off:.0f} GW | obj {n.objective:,.0f}")
        except Exception as e:
            print(f"  !! FAILED {row.run_id}: {type(e).__name__}: {e}")
            continue

    if times:
        print(f"\nDone {len(times)} runs. mean {np.mean(times)/60:.1f} min/run, total {sum(times)/3600:.2f} h.")
        if args.pilot:
            rem = len(pd.read_csv(DESIGN_CSV)) - len(done_run_ids())
            print(f"PILOT: ~{rem} LHS rows remaining × {np.mean(times)/60:.1f} min "
                  f"≈ {rem*np.mean(times)/3600:.1f} h at every={args.every}.")


if __name__ == "__main__":
    main()
