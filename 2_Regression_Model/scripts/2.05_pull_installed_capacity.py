"""
05_pull_installed_capacity.py

W4 stage 2 data pull: yearly installed generation capacity per production type
per country, from ENTSO-E (`query_installed_generation_capacity`). This is the
ONLY missing input for Paul's features 6 (Flexibility Index) and 7
(Interconnection Index) -- the cross-border flows and VRE generation those
features also need were already pulled by script 01.

Paul's definitions (Methods Reference Sec 3.3 / Sec 5):
  Cap_VRE          = Solar + Wind Onshore + Wind Offshore installed (yearly)
  Flexibility num. = Cap_Battery + Cap_DSR + Cap_PumpedHydro
  Interconnection  uses Cap_VRE + Cap_Interconnect (= yearly-max flows, script 01)

NOTE on flexibility numerator: Paul sourced battery + DSR from proprietary /
national datasets (RTE, RWTH-Aachen dashboard, Aurora, French regulator) that
are not available as an open 14-country panel. ENTSO-E reports installed
storage as "Hydro Pumped Storage" (and, for a few country-years, a dedicated
battery / energy-storage column). We therefore approximate the flexibility
numerator with the openly-reported ENTSO-E pumped-hydro (+ battery where
present) and omit DSR -- documented as a deviation from Paul in the methods
chapter. In our NS+Baltic geography pumped hydro dominates flexibility in this
period, so the index ordering is preserved.

Output:
  data/entsoe_strandA/installed_capacity/{country}.csv
      rows = year (2017-2024), cols = production type (MW)

Usage:
  python 05_pull_installed_capacity.py [--start 2017 --end 2024]
"""
import argparse
import time
from pathlib import Path

import pandas as pd
import yaml
from entsoe import EntsoePandasClient

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "entsoe_strandA" / "installed_capacity"
OUT.mkdir(parents=True, exist_ok=True)

# Same country -> aggregate ENTSO-E code mapping as script 01.
COUNTRY_AGG_CODE = {
    "DE": "DE_LU", "FR": "FR", "BE": "BE", "NL": "NL", "GB": "GB",
    "IE": "IE_SEM", "DK": "DK", "PL": "PL", "EE": "EE", "LV": "LV",
    "LT": "LT", "FI": "FI", "SE": "SE", "NO": "NO",
    # Lever C (2026-06-11): zone-resolved capacity for the farm-hosting zones
    # of multi-zone countries; saved as {zone}.csv next to the country files,
    # 2.04 prefers the zone file when it exists.
    "DK_1": "DK_1", "DK_2": "DK_2", "SE_4": "SE_4",
}


def make_client():
    key = yaml.safe_load(open(Path.home() / ".entsoerc"))["api_key"]
    return EntsoePandasClient(api_key=key)


def pull_country(client, country, code, start_year, end_year):
    """Pull the full year range in one call; reindex to every year with
    ffill/bfill so years ENTSO-E omits (e.g. DE 2017) inherit the nearest
    reported vintage (Paul used linear extrapolation for the same gaps)."""
    out = OUT / f"{country}.csv"
    if out.exists():
        return "cached"
    start = pd.Timestamp(f"{start_year}-01-01", tz="UTC")
    end = pd.Timestamp(f"{end_year + 1}-01-01", tz="UTC")
    for attempt in range(3):
        try:
            df = client.query_installed_generation_capacity(code, start=start, end=end)
            break
        except Exception as e:
            if attempt == 2:
                print(f"  FAILED {country} ({code}): {type(e).__name__}: {str(e)[:90]}")
                return "failed"
            time.sleep(3)
    if df is None or df.empty:
        return "failed"
    # ENTSO-E indexes by a Jan-02 timestamp per year -> reduce to integer year.
    df.index = [ts.year for ts in df.index]
    df.index.name = "year"
    df = df[~df.index.duplicated(keep="first")]
    df = df.reindex(range(start_year, end_year + 1)).ffill().bfill()
    df.to_csv(out)
    return "saved"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=int, default=2017)
    ap.add_argument("--end", type=int, default=2024)
    args = ap.parse_args()

    client = make_client()
    counts = {"saved": 0, "cached": 0, "failed": 0}
    print(f"Installed-capacity pull, {args.start}-{args.end}, {len(COUNTRY_AGG_CODE)} countries\n")
    for country, code in COUNTRY_AGG_CODE.items():
        r = pull_country(client, country, code, args.start, args.end)
        counts[r] = counts.get(r, 0) + 1
        print(f"  {country:3s} ({code:7s}): {r}")
        if r == "saved":
            time.sleep(0.5)
    print(f"\nDone. saved={counts['saved']} cached={counts['cached']} failed={counts['failed']}")


if __name__ == "__main__":
    main()
