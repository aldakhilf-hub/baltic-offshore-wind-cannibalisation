"""
1.05_analyse_baseline.py

Post-solve analysis of a PyPSA-Eur historical baseline run (2019 or 2023).

Reads the solved network from disk and computes:
  1. Topology + scope (countries, buses, snapshots, generators)
  2. Installed capacity by carrier (fixed inputs — this is a dispatch run)
  3. Annual mean wholesale prices per country
       - simple time-mean per bus, then mean over country's buses
       - load-weighted (audit fix: true ratio of sums, not a mean of ratios)
  4. Offshore wind capture values per country
       CV = capture price / time-mean zone price — the SAME denominator
       convention as 1.04/1.08/1.09/1.11 (audit fix: previously divided by the
       load-weighted country price, contradicting the validated definition).
  5. Same for onshore wind and solar (comparison reference).

Outputs -> results/baseline_<year>/ as CSVs + PNGs.

Usage:
    python 1.05_analyse_baseline.py          # 2019 (default)
    python 1.05_analyse_baseline.py 2023
"""

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pypsa

YEAR = int(sys.argv[1]) if len(sys.argv) > 1 else 2019
NETWORK_PATH = Path.home() / f"pypsa-eur/results/faisal-{YEAR}/networks/base_s_30_elec_.nc"
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "results" / f"baseline_{YEAR}"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
# observed DE annual mean day-ahead price, for the reference line in the plot
DE_OBS_PRICE = {2019: 38, 2023: 95}


def section(title: str) -> None:
    print(f"\n{'=' * 78}\n{title}\n{'=' * 78}")


# ---------------------------------------------------------------------------
# Load
# ---------------------------------------------------------------------------
section("1. Network")
n = pypsa.Network(NETWORK_PATH)
print(f"Source:    {NETWORK_PATH}")
print(f"Objective: €{n.objective:,.0f}  (annual system cost)")
print(f"Snapshots: {len(n.snapshots)} from {n.snapshots[0]} to {n.snapshots[-1]}")

# ---------------------------------------------------------------------------
# Topology
# ---------------------------------------------------------------------------
section("2. Topology")
ac_buses = n.buses[n.buses.carrier == "AC"]
print(f"AC buses: {len(ac_buses)} across {ac_buses.country.nunique()} countries")
print()
print("Buses per country:")
print(ac_buses.country.value_counts().sort_index().to_string())

# ---------------------------------------------------------------------------
# Optimal capacity by carrier
# ---------------------------------------------------------------------------
section("3. Installed capacity by carrier (MW, summed across all clusters)")
# filter the load-shedding pseudo-generator (carrier 'load', p_nom=inf) —
# audit fix: it polluted the capacity tables; and these are fixed INPUTS in a
# historical dispatch run, not optimised capacities
gens_real = n.generators[n.generators.carrier != "load"]
cap = gens_real.groupby("carrier").p_nom_opt.sum().sort_values(ascending=False)
print(cap.round(0).to_string())
cap.round(2).to_csv(OUTPUT_DIR / "optimal_capacity_by_carrier.csv", header=["MW"])

# Capacity by country and carrier — more thesis-relevant
section("3b. Installed capacity by country × carrier (MW)")
cap_by = (
    gens_real.assign(country=gens_real.bus.map(n.buses.country))
    .groupby(["country", "carrier"])
    .p_nom_opt.sum()
    .unstack(fill_value=0)
    .round(0)
)
print(cap_by.to_string())
cap_by.to_csv(OUTPUT_DIR / "capacity_by_country_carrier.csv")

# ---------------------------------------------------------------------------
# Annual mean prices per country
# ---------------------------------------------------------------------------
section("4. Annual mean wholesale prices per country (€/MWh)")

prices = n.buses_t.marginal_price
loads = n.loads
load_ts = n.loads_t.p_set

rows = []
for country, group in ac_buses.groupby("country"):
    bus_ids = [b for b in group.index if b in prices.columns]
    if not bus_ids:
        continue
    p = prices[bus_ids]
    simple = p.mean(axis=0).mean()

    # Load-weighted mean per country: accumulate numerator and denominator
    # across ALL the country's loads (audit fix: the old unweighted mean of
    # per-bus ratios gave every bus equal weight regardless of its load —
    # e.g. NO was reported 38.42 instead of the true 35.70 EUR/MWh)
    loads_c = loads[loads.bus.isin(bus_ids)]
    load_cols = loads_c.index.intersection(load_ts.columns)
    num = den = 0.0
    for lid in load_cols:
        bus = loads_c.loc[lid, "bus"]
        if bus in p.columns and load_ts[lid].sum() > 0:
            num += float((load_ts[lid] * p[bus]).sum())
            den += float(load_ts[lid].sum())
    lw = num / den if den > 0 else float("nan")
    rows.append({"country": country, "simple_mean_eurMWh": simple, "load_weighted_eurMWh": lw})

price_df = pd.DataFrame(rows).sort_values("load_weighted_eurMWh").set_index("country")
print(price_df.round(2).to_string())
price_df.round(4).to_csv(OUTPUT_DIR / "annual_prices_by_country.csv")

# ---------------------------------------------------------------------------
# Capture value per country × renewable carrier
# ---------------------------------------------------------------------------
section("5. Capture value per country × renewable carrier")
print("CV = capture price / time-mean zone price (same denominator as 1.04/1.08/1.09).")
print("CV < 1 → generator earns less than time-average → cannibalisation.")

renewable_carriers = ["offwind-ac", "offwind-dc", "offwind-float", "onwind", "solar"]
gens = n.generators[n.generators.carrier.isin(renewable_carriers)].copy()
gens["country"] = gens.bus.map(n.buses.country)

cv_rows = []
for (country, carrier), group in gens.groupby(["country", "carrier"]):
    # Sum generation across all clusters of this country×carrier
    gen_ids = [g for g in group.index if g in n.generators_t.p.columns]
    if not gen_ids:
        continue
    P = n.generators_t.p[gen_ids].sum(axis=1)
    if P.sum() == 0:
        continue
    # Bus-level shadow prices, weighted by each generator's share of country output
    # Simpler: use generation-weighted price across clusters
    capture_price_num = 0.0
    capture_price_den = 0.0
    for gid in gen_ids:
        bus = n.generators.at[gid, "bus"]
        if bus not in prices.columns:
            continue
        p_gen = n.generators_t.p[gid]
        lam = prices[bus]
        capture_price_num += (p_gen * lam).sum()
        capture_price_den += p_gen.sum()
    if capture_price_den == 0:
        continue
    capture_price = capture_price_num / capture_price_den

    # CV denominator: simple time-mean of the country's bus prices — the
    # project-wide convention (1.04/1.08/1.09/1.11). Audit fix: the old code
    # divided by the load-weighted country price, contradicting both this
    # file's own stated formula and the validated definition the bias
    # correction is fitted on (NO offshore CV was 0.913 instead of 0.983).
    country_avg = price_df.at[country, "simple_mean_eurMWh"]
    cv = capture_price / country_avg if country_avg > 0 else float("nan")

    p_nom = group.p_nom_opt.sum()
    energy = P.sum()
    cf = energy / (p_nom * len(P)) if p_nom > 0 else float("nan")

    cv_rows.append({
        "country": country,
        "carrier": carrier,
        "p_nom_opt_MW": p_nom,
        "energy_MWh": energy,
        "capacity_factor": cf,
        "capture_price_eurMWh": capture_price,
        "country_avg_price_eurMWh": country_avg,
        "capture_value": cv,
    })

cv_df = pd.DataFrame(cv_rows).set_index(["country", "carrier"]).sort_index()
print()
print(cv_df.round(3).to_string())
cv_df.to_csv(OUTPUT_DIR / "capture_values_by_country_carrier.csv")

# Quick pivot for the thesis-relevant view: offshore wind only
section("6. Offshore wind capture values (NS + Baltic comparison)")
offshore = cv_df.reset_index()
offshore = offshore[offshore.carrier.isin(["offwind-ac", "offwind-dc", "offwind-float"])]
pivot = offshore.pivot_table(
    index="country",
    columns="carrier",
    values="capture_value",
    aggfunc="mean",
)
print(pivot.round(3).to_string())
pivot.to_csv(OUTPUT_DIR / "offshore_wind_capture_values.csv")

# ---------------------------------------------------------------------------
# Plots
# ---------------------------------------------------------------------------
section("7. Plotting")

# Plot 1: country-level annual mean prices
fig, ax = plt.subplots(figsize=(10, 5))
price_df["load_weighted_eurMWh"].plot.bar(ax=ax, color="steelblue")
ax.set_ylabel("Load-weighted annual mean price (€/MWh)")
ax.set_title(f"PyPSA-Eur {YEAR} baseline — wholesale prices by country")
if YEAR in DE_OBS_PRICE:
    ax.axhline(DE_OBS_PRICE[YEAR], color="red", linestyle="--", lw=1,
               label=f"DE observed {YEAR} (~€{DE_OBS_PRICE[YEAR]})")
ax.legend()
plt.tight_layout()
plt.savefig(OUTPUT_DIR / "country_prices.png", dpi=130)
plt.close()

# Plot 2: offshore wind capture value by country
if not offshore.empty:
    fig, ax = plt.subplots(figsize=(10, 5))
    offshore_avg = offshore.groupby("country").capture_value.mean().sort_values()
    offshore_avg.plot.bar(ax=ax, color="seagreen")
    ax.set_ylabel("Capture value (CV)")
    ax.set_title(f"Offshore wind capture values by country, {YEAR}")
    ax.axhline(1.0, color="black", linestyle="--", lw=1, label="CV = 1 (no cannibalisation)")
    ax.legend()
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "offshore_wind_capture_values.png", dpi=130)
    plt.close()

print(f"Saved outputs to: {OUTPUT_DIR}")
print(f"  - annual_prices_by_country.csv")
print(f"  - optimal_capacity_by_carrier.csv")
print(f"  - capacity_by_country_carrier.csv")
print(f"  - capture_values_by_country_carrier.csv")
print(f"  - offshore_wind_capture_values.csv")
print(f"  - country_prices.png")
print(f"  - offshore_wind_capture_values.png")
