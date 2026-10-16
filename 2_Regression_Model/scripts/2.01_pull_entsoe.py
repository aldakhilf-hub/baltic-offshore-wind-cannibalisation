"""
01_pull_entsoe.py

Extended ENTSO-E pull for Strand A (Paul + Lina hybrid regression).

For each focus zone, 2017-2024, pulls:
  - Hourly day-ahead prices                          (already partly cached)
  - Hourly actual total load
  - Hourly generation per production type
        Solar (B16), Wind Onshore (B19), Wind Offshore (B18),
        plus thermal types: Fossil Gas (B04), Fossil Hard Coal (B05),
        Lignite (B06/B08), Nuclear (B14), Hydro reservoir (B12)
  - Cross-border physical flows between focus-country pairs

Outputs to data/entsoe_strandA/:
  prices/{zone}/{year}.csv          hourly EUR/MWh
  load/{country}/{year}.csv         hourly MW
  generation/{country}/{year}.csv   hourly MW per production type
  flows/{from}__{to}/{year}.csv     hourly MW

Re-runs are cheap: existing files are skipped. Resume after interruption is OK.
Expected total wall clock: 2-4 hours due to ENTSO-E rate limits.

Usage: python 01_pull_entsoe.py [--start YEAR --end YEAR]
"""
import sys
import time
import argparse
from pathlib import Path

import pandas as pd
import yaml
from entsoe import EntsoePandasClient

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "entsoe_strandA"
(OUT / "prices").mkdir(parents=True, exist_ok=True)
(OUT / "load").mkdir(parents=True, exist_ok=True)
(OUT / "generation").mkdir(parents=True, exist_ok=True)
(OUT / "flows").mkdir(parents=True, exist_ok=True)

# --------------------------------------------------------------------------
# Focus zones (ENTSO-E codes)
# --------------------------------------------------------------------------
ZONES = {
    # country -> list of bidding zones used for day-ahead price
    "DE": ["DE_LU"], "FR": ["FR"], "BE": ["BE"], "NL": ["NL"], "GB": ["GB"],
    "IE": ["IE_SEM"],
    "DK": ["DK_1", "DK_2"],
    "PL": ["PL"], "EE": ["EE"], "LV": ["LV"], "LT": ["LT"], "FI": ["FI"],
    "SE": ["SE_1", "SE_2", "SE_3", "SE_4"],
    "NO": ["NO_1", "NO_2", "NO_3", "NO_4", "NO_5"],
}
COUNTRIES_FOR_AGGREGATES = list(ZONES.keys())  # country-level codes for load/gen
# entsoe-py uses single country codes for load/generation queries (DE_LU for DE,
# country-level for most, etc.); we use the FIRST listed zone as the proxy.
COUNTRY_AGG_CODE = {c: zs[0] for c, zs in ZONES.items()}
# Override: load/gen for DK should be country-level "DK"; not per-zone
COUNTRY_AGG_CODE["DK"] = "DK"
COUNTRY_AGG_CODE["SE"] = "SE"
COUNTRY_AGG_CODE["NO"] = "NO"

# Lever C (2026-06-11): ZONE-resolved load + generation for the bidding zones
# that host farms inside multi-zone countries (7 DK farms split DK1/DK2 — the
# thesis's core contrast — and Lillgrund in SE_4). Saved under load/{zone}/ and
# generation/{zone}/ alongside the country aggregates; 2.04 prefers the zone
# folder when it exists. Single-zone countries need nothing (country == zone).
ZONE_DATA = ["DK_1", "DK_2", "SE_4"]

# Production types we want from "Actual Generation per Type" (PSR codes)
# Full production-type set. RES (B16/B18/B19) for the 7-feature regression;
# thermal + hydro types kept for thermal-mix / merit-order analyses and for
# parity with Paul's Sec 3.2 data scope.
PSR_TYPES = {
    "B16": "Solar",
    "B18": "Wind Offshore",
    "B19": "Wind Onshore",
    "B04": "Fossil Gas",
    "B05": "Fossil Hard Coal",
    "B06": "Fossil Brown Coal/Lignite",
    "B14": "Nuclear",
    "B12": "Hydro Pumped Storage",
    "B11": "Hydro Run-of-river and poundage",
    "B17": "Waste",
}

# Border pairs for cross-border physical flows (both directions)
# Focus on borders relevant to NS-Baltic story; add more later if needed.
BORDER_PAIRS = [
    ("DE_LU", "DK_1"), ("DE_LU", "DK_2"), ("DE_LU", "PL"), ("DE_LU", "NL"),
    ("DE_LU", "FR"), ("DE_LU", "BE"),
    ("DK_1", "NL"), ("DK_1", "GB"),
    ("DK_2", "SE_4"), ("DK_2", "DE_LU"),
    ("NL", "GB"), ("NL", "BE"),
    ("BE", "FR"), ("BE", "GB"),
    ("PL", "SE_4"), ("PL", "LT"),
    ("LT", "LV"), ("LT", "SE_4"),
    ("LV", "EE"),
    ("EE", "FI"),
    ("FI", "SE_3"), ("FI", "NO_4"),
    ("SE_3", "FI"), ("SE_4", "DE_LU"),
    ("FR", "GB"), ("FR", "IE_SEM"),
    ("NO_2", "GB"), ("NO_2", "DK_1"), ("NO_2", "NL"),
]


# --------------------------------------------------------------------------
def make_client():
    key = yaml.safe_load(open(Path.home() / ".entsoerc"))["api_key"]
    return EntsoePandasClient(api_key=key)


def year_window(year):
    return pd.Timestamp(f"{year}-01-01", tz="UTC"), pd.Timestamp(f"{year + 1}-01-01", tz="UTC")


def safe_pull(label, fn, max_retries=2):
    """Call fn() with retries; return DataFrame/Series or None on failure."""
    for attempt in range(max_retries + 1):
        try:
            result = fn()
            return result
        except Exception as e:
            if attempt < max_retries:
                time.sleep(2)
                continue
            print(f"    FAILED {label}: {type(e).__name__}: {str(e)[:90]}")
            return None


def to_hourly(series_or_df):
    """Resample to hourly mean, tz_convert to UTC."""
    if series_or_df is None or len(series_or_df) == 0:
        return None
    if hasattr(series_or_df.index, "tz") and series_or_df.index.tz is not None:
        idx = series_or_df.index.tz_convert("UTC")
        series_or_df = series_or_df.copy()
        series_or_df.index = idx
    return series_or_df.resample("h").mean()


# --------------------------------------------------------------------------
def pull_prices(client, zone, year):
    out = OUT / "prices" / zone / f"{year}.csv"
    if out.exists():
        return "cached"
    out.parent.mkdir(exist_ok=True)
    start, end = year_window(year)
    s = safe_pull(f"price {zone} {year}",
                  lambda: client.query_day_ahead_prices(zone, start=start, end=end))
    s = to_hourly(s)
    if s is None or s.empty:
        return "failed"
    s.to_frame("price_EURMWh").to_csv(out)
    return "saved"


def pull_load(client, country, year, code=None):
    code = code or COUNTRY_AGG_CODE[country]
    out = OUT / "load" / country / f"{year}.csv"
    if out.exists():
        return "cached"
    out.parent.mkdir(exist_ok=True)
    start, end = year_window(year)
    s = safe_pull(f"load {country} {year}",
                  lambda: client.query_load(code, start=start, end=end))
    if s is None or (hasattr(s, "empty") and s.empty):
        return "failed"
    # query_load returns a DataFrame with one col 'Actual Load'
    if hasattr(s, "columns"):
        col = "Actual Load" if "Actual Load" in s.columns else s.columns[0]
        s = s[col]
    s = to_hourly(s)
    if s is None or s.empty:
        return "failed"
    s.to_frame("load_MW").to_csv(out)
    return "saved"


def pull_generation(client, country, year, code=None):
    """Pull generation per production type, then collapse to wide hourly df."""
    code = code or COUNTRY_AGG_CODE[country]
    out = OUT / "generation" / country / f"{year}.csv"
    if out.exists():
        return "cached"
    out.parent.mkdir(exist_ok=True)
    start, end = year_window(year)
    cols = {}
    for psr, label in PSR_TYPES.items():
        df = safe_pull(
            f"gen {country}/{psr} {year}",
            lambda psr=psr: client.query_generation(code, start=start, end=end, psr_type=psr))
        time.sleep(0.3)
        if df is None or (hasattr(df, "empty") and df.empty):
            continue
        # entsoe-py may return MultiIndex col with 'Actual Aggregated' / 'Actual Consumption'
        if hasattr(df, "columns"):
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = [" ".join(str(x) for x in tup) for tup in df.columns]
            # pick the 'Actual Aggregated' column (drop Consumption)
            mat = [c for c in df.columns if label in str(c) and "Consumption" not in str(c)]
            if not mat:
                mat = list(df.columns)
            df = df[mat[0]]
        df = to_hourly(df)
        if df is not None and not df.empty:
            cols[label] = df
    if not cols:
        return "failed"
    big = pd.DataFrame(cols)
    big.index.name = "timestamp_utc"
    big.to_csv(out)
    return "saved"


def pull_flow(client, from_zone, to_zone, year):
    out = OUT / "flows" / f"{from_zone}__{to_zone}" / f"{year}.csv"
    if out.exists():
        return "cached"
    out.parent.mkdir(exist_ok=True)
    start, end = year_window(year)
    s = safe_pull(f"flow {from_zone}->{to_zone} {year}",
                  lambda: client.query_crossborder_flows(from_zone, to_zone, start=start, end=end))
    s = to_hourly(s)
    if s is None or s.empty:
        return "failed"
    s.to_frame("flow_MW").to_csv(out)
    return "saved"


# --------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=int, default=2017)
    ap.add_argument("--end", type=int, default=2024)
    ap.add_argument("--zones-only", action="store_true",
                    help="pull only the lever-C zone-resolved load/generation")
    args = ap.parse_args()
    years = list(range(args.start, args.end + 1))

    client = make_client()
    counts = {"saved": 0, "cached": 0, "failed": 0}
    t0 = time.time()

    if args.zones_only:
        print(f"\n===== Lever C: zone-resolved load + generation, {years[0]}-{years[-1]} =====\n")
        for zone in ZONE_DATA:
            for yr in years:
                r = pull_load(client, zone, yr, code=zone)
                counts[r] = counts.get(r, 0) + 1
                if r != "cached":
                    print(f"  load {zone} {yr}: {r}")
                    time.sleep(0.4)
            for yr in years:
                r = pull_generation(client, zone, yr, code=zone)
                counts[r] = counts.get(r, 0) + 1
                if r != "cached":
                    print(f"  gen  {zone} {yr}: {r}")
        print(f"\nDone in {(time.time()-t0)/60:.1f} min — "
              f"saved={counts['saved']} cached={counts['cached']} failed={counts['failed']}")
        return

    print(f"\n===== Strand A pull, years {years[0]}-{years[-1]} =====\n")
    print("--- 1. Prices per bidding zone ---")
    for country, zones in ZONES.items():
        for zone in zones:
            for yr in years:
                r = pull_prices(client, zone, yr)
                counts[r] = counts.get(r, 0) + 1
                if r == "saved":
                    print(f"  price {zone} {yr}: saved")
                    time.sleep(0.4)

    print("\n--- 2. Load per country ---")
    for country in COUNTRIES_FOR_AGGREGATES:
        for yr in years:
            r = pull_load(client, country, yr)
            counts[r] = counts.get(r, 0) + 1
            if r == "saved":
                print(f"  load {country} {yr}: saved")
                time.sleep(0.4)

    print("\n--- 3. Generation per type per country ---")
    for country in COUNTRIES_FOR_AGGREGATES:
        for yr in years:
            r = pull_generation(client, country, yr)
            counts[r] = counts.get(r, 0) + 1
            if r == "saved":
                print(f"  gen {country} {yr}: saved")

    print("\n--- 4. Cross-border physical flows ---")
    for fr, to in BORDER_PAIRS:
        for yr in years:
            r = pull_flow(client, fr, to, yr)
            counts[r] = counts.get(r, 0) + 1
            if r == "saved":
                print(f"  flow {fr}->{to} {yr}: saved")
                time.sleep(0.4)

    dt = time.time() - t0
    print(f"\n===== Done in {dt/60:.1f} min =====")
    print(f"  saved   : {counts['saved']}")
    print(f"  cached  : {counts['cached']}")
    print(f"  failed  : {counts['failed']}")


if __name__ == "__main__":
    main()
