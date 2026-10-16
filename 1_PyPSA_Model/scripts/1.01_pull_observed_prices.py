"""
pull_entsoe_prices.py

Pulls hourly day-ahead wholesale prices for European bidding zones
directly from ENTSO-E Transparency Platform using entsoe-py.

Reads API token from ~/.entsoerc (yaml: api_key: <token>).

Usage:
    python pull_entsoe_prices.py <year>
e.g. python pull_entsoe_prices.py 2021

Saves: data_observed/entsoe_prices_<year>.csv with columns
[timestamp_utc, country, zone, price_eurMWh].
"""

import sys
import time
from pathlib import Path

import pandas as pd
import yaml
from entsoe import EntsoePandasClient

if len(sys.argv) != 2:
    sys.exit("Usage: pull_entsoe_prices.py <year>")
YEAR = int(sys.argv[1])

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "data" / "observed_prices"
OUTPUT_DIR.mkdir(exist_ok=True)

# ENTSO-E zone codes per country (entsoe-py uses underscore form)
# Multi-zone countries get all their sub-zones.
ZONES = {
    "BE": ["BE"],
    "DE": ["DE_LU"],
    "DK": ["DK_1", "DK_2"],
    "EE": ["EE"],
    "FI": ["FI"],
    "FR": ["FR"],
    "GB": ["GB"],
    "IE": ["IE_SEM"],
    "LT": ["LT"],
    "LV": ["LV"],
    "NL": ["NL"],
    "NO": ["NO_1", "NO_2", "NO_3", "NO_4", "NO_5"],
    "PL": ["PL"],
    "SE": ["SE_1", "SE_2", "SE_3", "SE_4"],
}

key = yaml.safe_load(open(Path.home() / ".entsoerc"))["api_key"]
client = EntsoePandasClient(api_key=key)

# Use UTC for the global query window; the API itself handles the timezone
start = pd.Timestamp(f"{YEAR}-01-01", tz="UTC")
end = pd.Timestamp(f"{YEAR+1}-01-01", tz="UTC")

print(f"Pulling ENTSO-E day-ahead prices for {YEAR}, {sum(len(z) for z in ZONES.values())} zones")
print()

rows = []
for country, zone_codes in ZONES.items():
    for zone in zone_codes:
        # Pretty label without underscore
        label = zone.replace("_", "")
        print(f"  {country} / {label} ({zone}) ...", end=" ", flush=True)
        try:
            series = client.query_day_ahead_prices(zone, start=start, end=end)
        except Exception as e:
            print(f"FAILED ({type(e).__name__}: {str(e)[:60]})")
            continue
        if series is None or len(series) == 0:
            print("empty payload")
            continue
        # Series timestamps are in the zone's local tz; convert to UTC for joining
        utc_idx = series.index.tz_convert("UTC")
        for ts, p in zip(utc_idx, series.values):
            rows.append({
                "timestamp_utc": ts,
                "country": country,
                "zone": label,
                "price_eurMWh": p,
            })
        print(f"{len(series)} hours")
        time.sleep(0.4)  # ENTSO-E rate limit

df = pd.DataFrame(rows)
out_path = OUTPUT_DIR / f"entsoe_prices_{YEAR}.csv"
df.to_csv(out_path, index=False)

print()
print(f"Saved: {out_path}")
print(f"Shape: {df.shape}")
print(f"Zones present: {sorted(df.zone.unique())}")
print(f"\nNon-null hours per zone:")
print(df.dropna(subset=["price_eurMWh"]).groupby("zone").size().sort_values().to_string())
