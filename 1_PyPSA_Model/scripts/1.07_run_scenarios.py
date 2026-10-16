"""
07_run_scenarios.py

The canonical projection scenario runner. Overlays TYNDP 2024 capacities +
demand + fuel/CO2 prices onto the prepared 2023 PyPSA-Eur network and
re-solves with Gurobi to produce the projected 2030 / 2040 wholesale prices.

Applies four corrections (vs the original 06 v1, all justified in the thesis):
  (A) Thermal phaseout per German Coal Exit Act + conservative PL transition.
      DE coal/lignite x 0.5-0.6 (2030) / x 0.1-0.2 (2040). PL x 0.85-0.7 / x 0.4-0.3.
  (B) Offshore hard-caps: DK 50 GW, FI 25 GW, SE 35 GW. Bounds the TYNDP
      Energy-Island attribution artifact (DK HIGH = 129 GW unrealistic).
  (C) DK1 / DK2 split: year-dependent (65/35 -> 60/40 -> 55/45) instead of
      atlite's distribute-by-resource-potential which under-allocates DK2.
      Per Danish Energy Agency Energy Island MoUs.
  (D) H2 sector-coupling-lite floor (electrolyser Link + mandatory H2 demand +
      TYNDP-priced import backstop). Eliminates the electricity-only-model
      near-zero-price + CV>1 artifacts. Floor at ~EUR 35-42/MWh AC.
  (E) Adequacy patches for the RES-only TYNDP parse (2026-06-11): PL nuclear
      +3.9 GW by 2040 (PEP2040 — parsed_capacity has no thermal techs, so the
      coal phaseout otherwise leaves PL shedding ~1% of demand at the price
      cap); NO demand fallback at the Statnett central path (1.22x), since the
      high path left inflow-constrained Norway structurally short.
  (F) DSR scarcity tier (2026-06-11): 5% of each bus's peak load at
      400 EUR/MWh, standing in for TYNDP's unparsed flexibility portfolio
      (DSR/V2G/reserves, 3-8% of peak in TYNDP). Scarcity prices through
      thermal -> DSR(400) -> shedding(4000) instead of jumping to the cap.

Method-integrity fixes (2026-06-11, post-audit):
  1. Prescribed TYNDP capacity overlays are no longer silently truncated at the
     30-cluster atlite resource potential (p_nom_max only binds extendables);
     exceedances are allocated in full and WARNED about, so the scenario's
     buildout "dose" matches the TYNDP label.
  2. Demand: TYNDP growth factors are vs 2019, but the prepared network carries
     crisis-depressed 2023 loads. Loads are first rebased to 2019 via observed
     ENTSO-E demand (data/observed_demand_rebase.csv), then grown. GB/NO are
     absent from parsed TYNDP demand; documented exogenous growth fallbacks
     (FES 2024 / Statnett LMA 2023) replace the silent freeze-at-base.
  3. Solver parity with the validated baseline (config.faisal-2023.yaml):
     barrier WITHOUT crossover, BarConvTol 1e-6, plus the same load-shedding
     backstop (carrier "load", 100 kEUR/MWh) and seeded noisy costs that
     PyPSA-Eur's solve_network applied to the calibration runs. The 1.09 bias
     correction is fitted on baseline duals; projections must price identically.
  4. Solver status is checked before export, and exports are atomic
     (.tmp -> rename), so a killed/suboptimal run can never poison the cache.

Six scenarios across two pathways:
  2030/2040 NT (BEST trajectory)        baltic Baseline + High variants
  2040 DE-balticHigh                    HIGH trajectory + DE demand
  2040 GA-balticHigh                    HIGH trajectory + Global Ambition demand

NOTE on demand scenarios: parsed_demand.csv contains only REF/DE/GA — TYNDP's
National Trends demand sheet was never parsed. All "NT" runs therefore use the
Distributed-Energy (DE) demand trajectory; the NT label refers to the SUPPLY
trajectory (BEST). This is a deliberate, documented high-electrification
assumption — state it in the thesis scenario table.

Inputs (under PyPSA Model/data/tyndp/):
  parsed_capacity.csv  parsed_demand.csv  parsed_prices.csv  parsed_batteries.csv

Output:
  ~/pypsa-eur/results/scenarios_tyndp_v3/<scenario>.nc        (one per scenario)

Usage:
  python 07_run_scenarios.py                          # all 6 scenarios
  python 07_run_scenarios.py 2040-NT-balticHigh       # single scenario
"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import pypsa

# ---------------------------------------------------------------------------
# Inputs / outputs
# ---------------------------------------------------------------------------
HERE = Path(__file__).resolve().parent.parent / "data"
PREPARED = Path.home() / "pypsa-eur/resources/faisal-2023/networks/base_s_30_elec_.nc"
OUT_DIR = Path.home() / "pypsa-eur/results/scenarios_tyndp_v3"
OUT_DIR.mkdir(parents=True, exist_ok=True)

CAP = pd.read_csv(HERE / "tyndp/parsed_capacity.csv")
PRICES = pd.read_csv(HERE / "tyndp/parsed_prices.csv").set_index("year")
DEMAND = pd.read_csv(HERE / "tyndp/parsed_demand.csv")
BATT = pd.read_csv(HERE / "tyndp/parsed_batteries.csv")
# Observed 2019-vs-base demand ratio per country (ENTSO-E): converts the
# 2023-base network loads to a 2019 base before applying growth-vs-2019.
REBASE = pd.read_csv(HERE / "observed_demand_rebase.csv", comment="#").set_index("country")

# Exogenous 2040-vs-2019 demand growth for countries absent from parsed TYNDP
# demand. GB: National Grid FES 2024 (Holistic Transition) ~1.45x by 2040.
# NO: Statnett Langsiktig markedsanalyse 2023 CENTRAL (basis) path, ~165 TWh
# by 2040 vs ~135 TWh in 2019 -> 1.22x. (An earlier 1.35x — the high path —
# left inflow-constrained Norway structurally short year-round, with mean
# prices >1000 EUR/MWh; 1.22x is the defensible central estimate.)
DEMAND_GROWTH_FALLBACK_2040 = {"GB": 1.45, "NO": 1.22}

# Gurobi options identical to the validated baseline solve
# (config.faisal-2023.yaml -> solving.solver). Barrier WITHOUT crossover:
# the DK2 bias correction was fitted on interior-point duals, so projections
# must be priced the same way.
SOLVER_OPTIONS = {
    "threads": 8, "method": 2, "crossover": 0,
    "BarConvTol": 1e-6, "FeasibilityTol": 1e-6,
    "AggFill": 0, "PreDual": 0, "GURO_PAR_BARDENSETHRESH": 200,
}

# Thermal merit-order: (efficiency, VOM EUR/MWh, CO2 intensity t/MWh_th)
THERMAL = {
    "CCGT": (0.56, 5.8775, 0.198), "OCGT": (0.40, 6.0111, 0.198),
    "coal": (0.356, 4.1005, 0.3361), "lignite": (0.33, 4.1005, 0.4069),
    "oil": (0.35, 8.0148, 0.2571),
}
NUCLEAR_MC = 12.0
BALTIC_STATES = ["PL", "FI", "EE", "LV", "LT"]

# (A) thermal phaseout: per-country, per-year factor on coal + lignite p_nom
THERMAL_PHASEOUT = {
    "DE": {2030: {"coal": 0.50, "lignite": 0.60}, 2040: {"coal": 0.10, "lignite": 0.20}},
    "PL": {2030: {"coal": 0.85, "lignite": 0.70}, 2040: {"coal": 0.40, "lignite": 0.30}},
}
# (A2) announced thermal ADDITIONS missing from the RES-only TYNDP parse
# (parsed_capacity.csv carries only offwind/onwind/solar, so new thermal
# builds never reach the overlay). Without this, Poland — coal phased to
# 30-40% with no replacement — sheds ~1% of demand (731 scarcity hours in
# 2040-NT-balticHigh) and its capture values become scarcity artifacts.
# PL: PEP2040 nuclear programme, first unit 2033, ~3.9 GW (3 x AP1000) by 2040.
THERMAL_ADDITIONS_MW = {"PL": {2040: {"nuclear": 3900.0}}}
# (B) offshore caps per country (MW), applied inside cap_lookup
OFFSHORE_CAP_MW = {"DK": 50000, "FI": 25000, "SE": 35000}
# (C) DK1/DK2 split, year-dependent (DK1 share, DK2 share)
DK_OFFSHORE_SPLIT = {2030: (0.65, 0.35), 2040: (0.60, 0.40), 2050: (0.55, 0.45)}
DK_LON_CUT = 11.0
# (D) H2 layer parameters (sources in module docstring)
H2_ELECTROLYSER_GW = {
    2030: {"DE": 10.0, "FR": 6.5, "NL": 4.0, "BE": 1.5, "DK": 4.0, "GB": 5.0,
           "IE": 1.0, "NO": 1.0, "SE": 2.0, "FI": 2.0,
           "PL": 2.0, "EE": 0.5, "LV": 0.2, "LT": 0.5},
    2040: {"DE": 30.0, "FR": 15.0, "NL": 8.0, "BE": 4.0, "DK": 10.0, "GB": 10.0,
           "IE": 3.0, "NO": 3.0, "SE": 5.0, "FI": 5.0,
           "PL": 5.0, "EE": 1.0, "LV": 0.5, "LT": 1.5},
}
H2_DEMAND_TWH = {
    2030: {"DE": 25.0, "FR": 20.0, "NL": 15.0, "BE": 8.0, "DK": 3.0, "GB": 15.0,
           "IE": 2.0, "NO": 3.0, "SE": 5.0, "FI": 4.0,
           "PL": 5.0, "EE": 0.5, "LV": 0.3, "LT": 0.5},
    2040: {"DE": 100.0, "FR": 70.0, "NL": 45.0, "BE": 25.0, "DK": 12.0, "GB": 50.0,
           "IE": 7.0, "NO": 10.0, "SE": 15.0, "FI": 12.0,
           "PL": 25.0, "EE": 2.0, "LV": 1.5, "LT": 3.0},
}
H2_IMPORT_PRICE_EURMWH = {2030: 60.0, 2040: 50.0}   # TYNDP sheet 4.3 NT pipeline H2
ELECTROLYSER_EFF = 0.70

SCENARIOS = {
    "2030-NT-balticBaseline": dict(year=2030, traj="BEST", baltic="BEST", demand_scn="DE"),
    "2030-NT-balticHigh":     dict(year=2030, traj="BEST", baltic="HIGH", demand_scn="DE"),
    "2040-NT-balticBaseline": dict(year=2040, traj="BEST", baltic="BEST", demand_scn="DE"),
    "2040-NT-balticHigh":     dict(year=2040, traj="BEST", baltic="HIGH", demand_scn="DE"),
    "2040-DE-balticHigh":     dict(year=2040, traj="HIGH", baltic="HIGH", demand_scn="DE"),
    "2040-GA-balticHigh":     dict(year=2040, traj="HIGH", baltic="HIGH", demand_scn="GA"),
}


# ---------------------------------------------------------------------------
# Lookup helpers (TYNDP data)
# ---------------------------------------------------------------------------
def cap_lookup(tech, country, traj, year):
    """TYNDP capacity (MW), with fallbacks across trajectories and offshore cap (B)."""
    sub = CAP[(CAP.tech == tech) & (CAP.country == country) & (CAP.year == year)]
    for t in [traj, "BEST", "LOW", "HIGH"]:
        v = sub[sub.trajectory == t]
        if len(v):
            mw = float(v.MW.iloc[0])
            if tech == "offwind" and country in OFFSHORE_CAP_MW:
                mw = min(mw, OFFSHORE_CAP_MW[country])
            return mw
    return None


def demand_growth(country, scn, year):
    """Per-country demand growth vs 2019; 2030 linearly interpolates 2019 -> 2040.

    GB and NO are absent from parsed TYNDP demand — they take the documented
    exogenous fallbacks above. Any OTHER missing country is frozen at the base
    year with a loud warning (silent freezing was an audit finding)."""
    row = DEMAND[(DEMAND.country == country) & (DEMAND.scenario == scn) & (DEMAND.year == 2040)]
    if not len(row) or pd.isna(row.growth_vs_2019.iloc[0]):
        if country in DEMAND_GROWTH_FALLBACK_2040:
            g2040 = DEMAND_GROWTH_FALLBACK_2040[country]
            print(f"  demand {country}: not in TYNDP — exogenous growth x{g2040} vs 2019 (documented fallback)")
        else:
            print(f"  WARNING demand {country}: no TYNDP growth and no fallback — FROZEN at base year")
            return 1.0
    else:
        g2040 = float(row.growth_vs_2019.iloc[0])
    if year == 2030:
        return 1.0 + (g2040 - 1.0) * (2030 - 2019) / (2040 - 2019)
    return g2040


def demand_rebase(country):
    """Observed demand_2019 / demand_2023 (ENTSO-E). Applied before growth so
    that growth-vs-2019 multiplies a true 2019 base, not the crisis-depressed
    2023 loads baked into the prepared network (audit fix: ~5-12% understatement)."""
    if country in REBASE.index:
        return float(REBASE.loc[country, "rebase_2019_over_base"])
    print(f"  WARNING demand {country}: no observed rebase ratio — using 1.0")
    return 1.0


def batt_lookup(country, traj, year):
    sub = BATT[(BATT.country == country) & (BATT.year == year)]
    for t in [traj, "BEST", "LOW", "HIGH"]:
        v = sub[sub.trajectory == t]
        if len(v):
            return float(v.power_MW.iloc[0]), float(v.max_hours.iloc[0])
    return None, None


# ---------------------------------------------------------------------------
# Network-mutation helpers (apply corrections + H2 layer to a loaded network)
# ---------------------------------------------------------------------------
def add_battery(n, country, power_mw, max_hours):
    if not power_mw or power_mw <= 0 or not max_hours or max_hours <= 0:
        return 0.0
    ac = n.buses[(n.buses.carrier == "AC") & (n.buses.country == country)]
    if ac.empty:
        return 0.0
    loads = n.loads[n.loads.bus.isin(ac.index)]
    if len(loads):
        load_by_bus = n.loads_t.p_set[loads.index.intersection(n.loads_t.p_set.columns)].mean()
        bus = loads.loc[load_by_bus.idxmax(), "bus"] if len(load_by_bus) else ac.index[0]
    else:
        bus = ac.index[0]
    n.add("StorageUnit", f"{country}-battery-scn", bus=bus, carrier="battery",
          p_nom=power_mw, max_hours=max_hours,
          efficiency_store=0.95, efficiency_dispatch=0.95,
          cyclic_state_of_charge=True, marginal_cost=0.0, p_nom_extendable=False)
    return power_mw


def set_capacity(n, country, carriers, target_mw):
    """Distribute a country target across its generators by p_nom_max share.

    Prescribed TYNDP overlays are NOT capped at the summed cluster potential:
    p_nom_max only binds extendable generators, and the 30-cluster atlite
    eligible-area potentials are far coarser than national buildout plans.
    Silent truncation attenuated the scenario dose (audit: PL 11.0 vs 21.8 GW,
    LT 3.0 vs 4.2 GW under HIGH) — now the full target is allocated and any
    exceedance is warned about so it can be reported in the thesis."""
    g = n.generators
    mask = (g.bus.map(n.buses.country) == country) & (g.carrier.isin(carriers))
    ids = g[mask].index
    if len(ids) == 0 or target_mw is None:
        return 0.0
    weight = g.loc[ids, "p_nom_max"].replace([np.inf], 0)
    if weight.sum() <= 0:
        weight = pd.Series(1.0, index=ids)
    potential = float(weight.sum())
    if target_mw > potential and potential > len(ids):  # ignore degenerate uniform weights
        print(f"  WARNING {country} {carriers[0].split('-')[0]}: TYNDP target "
              f"{target_mw/1e3:.1f} GW exceeds cluster potential {potential/1e3:.1f} GW "
              f"— allocating full target (no truncation)")
    alloc = weight / weight.sum() * target_mw
    n.generators.loc[ids, "p_nom"] = alloc.values
    n.generators.loc[ids, "p_nom_extendable"] = False
    return float(target_mw)


def apply_thermal_phaseout(n, year):
    """(A) Scale DE/PL coal + lignite p_nom by per-year factor, then (A2) add
    announced thermal builds absent from the RES-only TYNDP parse."""
    g = n.generators
    for country, sched in THERMAL_PHASEOUT.items():
        if year not in sched:
            continue
        for carrier, factor in sched[year].items():
            mask = (g.bus.map(n.buses.country) == country) & (g.carrier == carrier)
            ids = g[mask].index
            if len(ids):
                before = g.loc[ids, "p_nom"].sum() / 1e3
                n.generators.loc[ids, "p_nom"] *= factor
                after = n.generators.loc[ids, "p_nom"].sum() / 1e3
                print(f"  phaseout {country}/{carrier} {year}: {before:.1f} -> {after:.1f} GW (x{factor})")
    # (A2) announced additions, placed at the country's largest-load bus
    for country, sched in THERMAL_ADDITIONS_MW.items():
        if year not in sched:
            continue
        for carrier, add_mw in sched[year].items():
            ac = n.buses[(n.buses.carrier == "AC") & (n.buses.country == country)]
            if ac.empty:
                continue
            loads = n.loads[n.loads.bus.isin(ac.index)]
            cols = loads.index.intersection(n.loads_t.p_set.columns)
            bus = (loads.loc[n.loads_t.p_set[cols].mean().idxmax(), "bus"]
                   if len(cols) else ac.index[0])
            mc = NUCLEAR_MC if carrier == "nuclear" else None
            n.add("Generator", f"{country}-{carrier}-addition", bus=bus,
                  carrier=carrier, p_nom=add_mw, marginal_cost=mc,
                  p_nom_extendable=False)
            print(f"  thermal addition {country}/{carrier} {year}: +{add_mw/1e3:.1f} GW "
                  f"(announced build, absent from RES-only TYNDP parse)")


def apply_dk_offshore_split(n, target_mw, year):
    """(C) Year-dependent DK1/DK2 split, then allocate inside each cluster."""
    if target_mw is None or target_mw <= 0:
        return 0.0
    ac = n.buses[(n.buses.carrier == "AC") & (n.buses.country == "DK")]
    dk1_buses = ac[ac.x < DK_LON_CUT].index
    dk2_buses = ac[ac.x >= DK_LON_CUT].index
    yrs = sorted(DK_OFFSHORE_SPLIT.keys())
    if year <= yrs[0]:
        dk1_share, dk2_share = DK_OFFSHORE_SPLIT[yrs[0]]
    elif year >= yrs[-1]:
        dk1_share, dk2_share = DK_OFFSHORE_SPLIT[yrs[-1]]
    else:
        for i in range(len(yrs) - 1):
            if yrs[i] <= year <= yrs[i + 1]:
                w = (year - yrs[i]) / (yrs[i + 1] - yrs[i])
                a1, a2 = DK_OFFSHORE_SPLIT[yrs[i]]
                b1, b2 = DK_OFFSHORE_SPLIT[yrs[i + 1]]
                dk1_share = a1 + w * (b1 - a1)
                dk2_share = a2 + w * (b2 - a2)
                break
    g = n.generators
    off_carriers = ["offwind-ac", "offwind-dc", "offwind-float"]
    total = 0.0
    allocated = {}
    for label, buses, sub_target in [("DK1", dk1_buses, target_mw * dk1_share),
                                     ("DK2", dk2_buses, target_mw * dk2_share)]:
        mask = (g.bus.isin(buses)) & (g.carrier.isin(off_carriers))
        ids = g[mask].index
        if len(ids) == 0:
            allocated[label] = 0.0
            continue
        weight = g.loc[ids, "p_nom_max"].replace([np.inf], 0)
        if weight.sum() <= 0:
            weight = pd.Series(1.0, index=ids)
        potential = float(weight.sum())
        # The split's whole purpose is to OVERRIDE atlite's allocation, so the
        # intended sub-target is not re-capped at the cluster potential (audit:
        # the cap silently reinstated DK2 under-allocation, 74/26 vs 60/40).
        if sub_target > potential and potential > len(ids):
            print(f"  WARNING {label}: intended {sub_target/1e3:.1f} GW exceeds cluster "
                  f"potential {potential/1e3:.1f} GW — allocating full intended share")
        alloc = weight / weight.sum() * sub_target
        n.generators.loc[ids, "p_nom"] = alloc.values
        n.generators.loc[ids, "p_nom_extendable"] = False
        allocated[label] = sub_target
        total += sub_target
    print(f"  DK offshore split (allocated): DK1={allocated.get('DK1', 0)/1e3:.1f}GW "
          f"DK2={allocated.get('DK2', 0)/1e3:.1f}GW (year={year}, "
          f"intended ratio {dk1_share:.0%}/{dk2_share:.0%})")
    return total


def add_h2_layer(n, year):
    """(D) Add per-country H2 bus + electrolyser Link + mandatory demand + import backstop."""
    if year not in H2_ELECTROLYSER_GW:
        print(f"  no H2 inputs for year {year}, skipping H2 layer")
        return
    cap_dict = H2_ELECTROLYSER_GW[year]
    dem_dict = H2_DEMAND_TWH[year]
    p_imp = H2_IMPORT_PRICE_EURMWH[year]
    for car in ["h2", "electrolyser", "h2_demand_imports", "h2_store"]:
        if car not in n.carriers.index:
            n.add("Carrier", car)
    total_cap = total_dem = 0.0
    ac = n.buses[n.buses.carrier == "AC"]
    for country, cap_gw in cap_dict.items():
        if cap_gw <= 0:
            continue
        cap_mw = cap_gw * 1e3
        annual_h2_mwh = dem_dict.get(country, 0.0) * 1e6
        if annual_h2_mwh <= 0:
            continue
        hourly_h2_load = annual_h2_mwh / 8760.0
        c_buses = ac[ac.country == country]
        if c_buses.empty:
            continue
        loads = n.loads[n.loads.bus.isin(c_buses.index)]
        if len(loads):
            load_cols = loads.index.intersection(n.loads_t.p_set.columns)
            if len(load_cols):
                ac_bus = loads.loc[n.loads_t.p_set[load_cols].mean().idxmax(), "bus"]
            else:
                ac_bus = c_buses.index[0]
        else:
            ac_bus = c_buses.index[0]
        h2_bus = f"{country} H2"
        n.add("Bus", h2_bus, carrier="h2",
              x=c_buses.loc[ac_bus, "x"], y=c_buses.loc[ac_bus, "y"], country=country)
        n.add("Link", f"{country}-electrolyser", bus0=ac_bus, bus1=h2_bus,
              p_nom=cap_mw, efficiency=ELECTROLYSER_EFF, marginal_cost=0.0,
              carrier="electrolyser")
        n.add("Load", f"{country}-h2-load", bus=h2_bus, carrier="h2", p_set=hourly_h2_load)
        n.add("Store", f"{country}-h2-store", bus=h2_bus, carrier="h2_store",
              e_nom=annual_h2_mwh / 4.0, e_cyclic=True, marginal_cost=0.0)
        n.add("Generator", f"{country}-h2-import", bus=h2_bus, carrier="h2_demand_imports",
              p_nom=hourly_h2_load * 2.0, marginal_cost=p_imp)
        total_cap += cap_gw
        total_dem += annual_h2_mwh / 1e6
    print(f"  H2 layer: {total_cap:.1f} GW electrolyser, {total_dem:.0f} TWh demand, "
          f"import price EUR{p_imp}/MWh (floor ~ EUR{p_imp*ELECTROLYSER_EFF:.0f}/MWh AC)")


def add_dsr(n, share=0.05, price=400.0):
    """(F) Demand-side response tier (2026-06-11). The projection overlay
    scales demand to 2030/2040 but TYNDP's flexibility portfolio (DSR, V2G,
    emergency reserves) is not in the parsed data, so stressed systems jumped
    straight from the last thermal plant to the 4,000 EUR/MWh cap — Norway
    (power-constrained peaks despite an annual energy surplus) averaged
    ~900 EUR/MWh. TYNDP carries country DSR at roughly 3-8% of peak load;
    this adds 5% of each load's peak as a DSR generator at 400 EUR/MWh
    (between peaker cost and the cap), so scarcity prices through a realistic
    ladder: thermal -> DSR(400) -> shedding(4000)."""
    if "DSR" not in n.carriers.index:
        n.add("Carrier", "DSR")
    peaks = n.loads_t.p_set.max()
    ids = [i for i in peaks.index if peaks[i] > 0]
    buses = n.loads.loc[ids, "bus"]
    n.add("Generator", [f"{i} DSR" for i in ids], bus=list(buses.values),
          carrier="DSR", p_nom=(peaks[ids] * share).values, marginal_cost=price)
    print(f"  DSR tier: {peaks[ids].sum() * share / 1e3:.1f} GW at {price:.0f} EUR/MWh "
          f"({share:.0%} of peak load per bus)")


def add_load_shedding(n, default_cost=4000.0):
    """Load-shedding backstop, one 'load' generator per bus (p_nom=inf) —
    the same mechanism PyPSA-Eur's solve_network added to the baselines.

    VOLL choice (2026-06-11): scenarios price unserved energy at the EU
    harmonised day-ahead price CAP (4,000 EUR/MWh), not the baseline's
    100,000 EUR/MWh. Rationale: the projection overlay carries TYNDP
    capacities but not all TYNDP flexibility (DSR, peakers, sector coupling),
    so stressed 2030/2040 systems shed a small volume (~0.1% of energy). At
    100k EUR/MWh those few hours dominate the annual MEAN price and crush
    capture value mechanically; at the market cap they price exactly as the
    real day-ahead auction would. The baselines never shed (~0 MWh), so their
    duals — and the bias fit — are unaffected by this choice. Shed volume is
    printed per solve; report it in the thesis scenario table."""
    if "load" not in n.carriers.index:
        n.add("Carrier", "load")
    buses_i = n.buses.index
    n.add("Generator", buses_i, " load shedding", bus=buses_i, carrier="load",
          marginal_cost=default_cost, p_nom=np.inf, sign=1)


def add_noisy_costs(n, seed=123):
    """Mirror of PyPSA-Eur solve_network's noisy_costs (baseline parity): tiny
    seeded perturbations that break LP degeneracy. Identical formulas and the
    same default seed (123) as the installed PyPSA-Eur."""
    np.random.seed(seed)
    for t in n.components:
        if "marginal_cost" in t.static:
            t.static["marginal_cost"] += 1e-2 + 2e-3 * (np.random.random(len(t.static)) - 0.5)
    for t in n.components[["Line", "Link"]]:
        if t.static.empty:
            continue
        t.static["capital_cost"] += (1e-1 + 2e-2 * (np.random.random(len(t.static)) - 0.5)) * t.static["length"]


# ---------------------------------------------------------------------------
# Per-scenario run
# ---------------------------------------------------------------------------
def run(name, p, gas_override=None, out_dir=OUT_DIR, every=1, relax_grid=False):
    """Solve one projection scenario. gas_override (EUR/MWh) replaces the TYNDP
    gas price for CCGT+OCGT only (the gas-shock grid, script 10) -- everything
    else is identical to the canonical v3 run. out_dir lets shock runs write to
    a separate directory so the canonical networks are never overwritten.
    every>1 coarsens to every Nth snapshot (3 = 3-hourly), rescaling weightings
    so totals stay correct -- used by the surrogate (1.13) resolution check.
    relax_grid=True drops the lv_limit volume constraint -> optimal transmission
    expansion (vopt), the OPTIMISTIC grid bound used by 1.18's bracket."""
    print(f"\n{'=' * 70}\n{name}  (year {p['year']}, traj {p['traj']}, Baltic {p['baltic']}"
          f"{'' if gas_override is None else f', GAS={gas_override}'}"
          f"{'' if every == 1 else f', EVERY={every}'})\n{'=' * 70}")
    n = pypsa.Network(PREPARED)
    if relax_grid:
        # True vopt: under v1.0 PyPSA-Eur leaves lines NON-extendable (the
        # lv_limit constraint is inert), so dropping the constraint alone is a
        # no-op — lines and DC links must be made extendable explicitly, from
        # today's capacity upward, at their PyPSA-Eur capital costs.
        if "lv_limit" in n.global_constraints.index:
            n.remove("GlobalConstraint", "lv_limit")
        n.lines["s_nom_min"] = n.lines.s_nom
        n.lines["s_nom_extendable"] = True
        dc = n.links.carrier == "DC"
        n.links.loc[dc, "p_nom_min"] = n.links.loc[dc, "p_nom"]
        n.links.loc[dc, "p_nom_extendable"] = True
        print(f"  GRID RELAXED -> vopt bound: {int(len(n.lines))} lines + "
              f"{int(dc.sum())} DC links extendable (capex-bearing)")
    if every > 1:
        n.set_snapshots(n.snapshots[::every])
        n.snapshot_weightings.loc[:, :] = float(every)
    yr = p["year"]

    # Thermal marginal costs from TYNDP fuel + CO2 (gas_override shocks gas only)
    pr = PRICES.loc[yr]
    gas = pr.gas_eurMWh if gas_override is None else float(gas_override)
    fuel = {"CCGT": gas, "OCGT": gas, "coal": pr.coal_eurMWh,
            "lignite": pr.lignite_eurMWh, "oil": pr.oil_eurMWh}
    for car, (eff, vom, co2i) in THERMAL.items():
        mc = vom + (fuel[car] + pr.co2_eurton * co2i) / eff
        n.generators.loc[n.generators.carrier == car, "marginal_cost"] = mc
    n.generators.loc[n.generators.carrier == "nuclear", "marginal_cost"] = NUCLEAR_MC

    # Apply corrections
    apply_thermal_phaseout(n, yr)   # (A)
    countries = n.buses[n.buses.carrier == "AC"].country.unique()
    tot = {"solar": 0, "onwind": 0, "offwind": 0}
    for c in countries:
        if not isinstance(c, str):
            continue
        tot["solar"] += set_capacity(n, c, ["solar"], cap_lookup("solar", c, p["traj"], yr))
        tot["onwind"] += set_capacity(n, c, ["onwind"], cap_lookup("onwind", c, p["traj"], yr))
        off_traj = p["baltic"] if c in BALTIC_STATES else p["traj"]
        target = cap_lookup("offwind", c, off_traj, yr)   # (B) cap inside cap_lookup
        if c == "DK":
            tot["offwind"] += apply_dk_offshore_split(n, target, yr)   # (C)
        else:
            tot["offwind"] += set_capacity(n, c, ["offwind-ac", "offwind-dc", "offwind-float"], target)
    print(f"  RES (GW): solar {tot['solar']/1e3:.0f}, "
          f"onwind {tot['onwind']/1e3:.0f}, offwind {tot['offwind']/1e3:.0f}")

    # Batteries
    batt_total = 0.0
    for c in countries:
        if not isinstance(c, str):
            continue
        pw, mh = batt_lookup(c, p["traj"], yr)
        batt_total += add_battery(n, c, pw, mh)
    print(f"  battery: {batt_total/1e3:.0f} GW")

    # Demand: rebase 2023 loads to 2019, then apply TYNDP growth-vs-2019
    print(f"  demand scenario: {p['demand_scn']} (TYNDP NT demand not parsed; see module docstring)")
    for c in countries:
        if not isinstance(c, str):
            continue
        gf = demand_rebase(c) * demand_growth(c, p["demand_scn"], yr)
        load_ids = n.loads[n.loads.bus.map(n.buses.country) == c].index
        cols = [l for l in load_ids if l in n.loads_t.p_set.columns]
        if cols:
            n.loads_t.p_set[cols] *= gf

    add_h2_layer(n, yr)   # (D)

    # Baseline-parity solve preparation (see module docstring, fix 3) plus the
    # DSR scarcity tier (correction F) — DSR is added AFTER demand growth so
    # its capacity scales with the projected peaks
    add_dsr(n)
    add_load_shedding(n)
    add_noisy_costs(n)

    status, condition = n.optimize(solver_name="gurobi", solver_options=SOLVER_OPTIONS)
    if status != "ok" or condition != "optimal":
        raise RuntimeError(f"{name}: solver returned {status}/{condition} — NOT exporting")
    shed = n.generators_t.p.filter(like="load shedding").sum().sum() if len(n.generators_t.p) else 0.0
    print(f"  solved, objective EUR {n.objective:,.0f} (load shed: {shed:.1f} MWh)")
    out_dir.mkdir(parents=True, exist_ok=True)
    # atomic export: a killed run can never leave a truncated .nc behind
    tmp = out_dir / f"{name}.nc.tmp"
    n.export_to_netcdf(tmp)
    tmp.rename(out_dir / f"{name}.nc")
    return n


if __name__ == "__main__":
    todo = {sys.argv[1]: SCENARIOS[sys.argv[1]]} if len(sys.argv) == 2 else SCENARIOS
    for nm, pp in todo.items():
        run(nm, pp)
    print(f"\nAll done. Networks in: {OUT_DIR}")
