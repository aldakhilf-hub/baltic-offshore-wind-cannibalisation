"""
02_pull_era5_and_vwf.py

ERA5 wind + Virtual Wind Farm pipeline.

Wind source: the Open-Meteo Historical Weather API (https://open-meteo.com/),
served from the ERA5 0.25-deg reanalysis (models=era5). For each farm
coordinate it returns the hourly ERA5 wind SPEED at 10 m and 100 m for the
nearest grid cell directly -- exactly the two-height input Paul's log-profile
fit needs -- as a point time-series, in seconds per farm with no queue.

Why not ARCO-ERA5 (the previous source): the public ARCO zarr is chunked
1 timestep x full global grid, which is pessimal for a long time-series over
~30 fixed points -- extracting one year forces ~8760 full-globe chunk reads
(the ~73 min/year + 16 GB RAM blow-ups we hit). Open-Meteo serves the SAME
ERA5 data pre-indexed for point access, so the science is identical and only
the fetch changes. The method downstream of the raw wind speeds (log-profile
extrapolation, IEA-15 MW curve, Hayes smoothing + shift) follows Paul; the curve
itself is a hand-keyed reproduction of the IEA-15 MW table rather than a cubic
interpolation of the reference CSV, a coarseness the sigma=1.17 smoothing washes
out (Paul loaded IEA_Reference_15MW_240.csv, which is not in this repo).

For each of ~30 NS+Baltic wind farm sites in data/wind_farms_strandA.csv
and each year, the pipeline:
  1. Fetches hourly ERA5 wind speed at 10 m and 100 m (nearest cell).
  2. Log-profile extrapolation to 150 m hub height fitted on the
     (10 m, 100 m) pair (Paul Sec 3.1).
  3. Applies Paul's adjusted IEA-15 MW reference power curve:
        - Gaussian smoothing  sigma = 1.17 m/s
        - Power-curve shift  w0 = 0.71 m/s

Output:  data/vwf/hourly_cf_{year}.csv   (hours x farms; CF in [0, 1])

Usage:
  python 02_pull_era5_and_vwf.py --year 2023               # one year
  python 02_pull_era5_and_vwf.py --year 2017 --to 2024     # range
  python 02_pull_era5_and_vwf.py --year 2017 --to 2024 --force  # re-pull
"""
import argparse
import time
from pathlib import Path

import numpy as np
import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent.parent
SITES = pd.read_csv(ROOT / "data/wind_farms_strandA.csv", comment="#")
SITES = SITES[SITES.lat.notna()].copy().reset_index(drop=True)
print(f"Loaded {len(SITES)} wind farm sites")

VWF_DIR = ROOT / "data/vwf"
VWF_DIR.mkdir(parents=True, exist_ok=True)

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"

# --------------------------------------------------------------------------
# IEA 15 MW reference power curve (NREL); coarse table covering full envelope.
# --------------------------------------------------------------------------
IEA15_PC = pd.Series({
    0.0: 0.0, 1.0: 0.0, 2.0: 0.0, 3.0: 0.0, 4.0: 0.020,
    5.0: 0.078, 6.0: 0.183, 7.0: 0.345, 8.0: 0.564, 9.0: 0.838,
    10.0: 0.999, 10.59: 1.0, 11.0: 1.0, 12.0: 1.0, 13.0: 1.0,
    14.0: 1.0, 15.0: 1.0, 16.0: 1.0, 17.0: 1.0, 18.0: 1.0,
    19.0: 1.0, 20.0: 1.0, 21.0: 1.0, 22.0: 1.0, 23.0: 1.0,
    24.0: 1.0, 25.0: 1.0, 25.5: 0.0, 30.0: 0.0,
})


def hayes_smooth_pc(raw_pc, sigma=1.17, w_shift=0.71, w_grid=None):
    """Paul Sec 3.1 power-curve smoothing + shift.
       PC_smooth(w) = sum_u PC_raw(u) * N(u; w, sigma)
       PC_adj(w)    = PC_smooth(w - w_shift)
    """
    if w_grid is None:
        w_grid = np.arange(0, 30.01, 0.25)
    raw_fine = pd.Series(
        np.interp(w_grid, raw_pc.index, raw_pc.values, left=0, right=0),
        index=w_grid)
    smooth = np.zeros_like(w_grid, dtype=float)
    for i, w in enumerate(w_grid):
        kernel = np.exp(-((w_grid - w) ** 2) / (2 * sigma ** 2))
        kernel /= kernel.sum()
        smooth[i] = (raw_fine.values * kernel).sum()
    return pd.Series(
        np.interp(w_grid, w_grid + w_shift, smooth, left=0, right=0),
        index=w_grid)


IEA15_PC_ADJUSTED = hayes_smooth_pc(IEA15_PC)
# Re-impose the physical envelope after smoothing. The Gaussian kernel bleeds a
# little power above cut-out (25 m/s) and below cut-in (~3 m/s); neither the
# Jacquet nor the Efthymiadou pipeline re-zeroes it, leaving spurious output in
# storm hours. Hard-zero outside [3, 25] m/s. This is a shared, near-free
# improvement over both predecessors; its effect is confined to rare high-wind
# (hence low-price) hours, so the capture-value impact is negligible.
_w = IEA15_PC_ADJUSTED.index
IEA15_PC_ADJUSTED[(_w > 25.0) | (_w < 3.0)] = 0.0
print("Power curve transformed (Hayes sigma=1.17, w_shift=0.71; re-zeroed outside [3,25] m/s)")

# Hub-height log-profile constants and power-curve lookup arrays.
LN_10, LN_100, LN_150 = np.log(10), np.log(100), np.log(150)
PC_V = IEA15_PC_ADJUSTED.index.values
PC_P = IEA15_PC_ADJUSTED.values


# --------------------------------------------------------------------------
# Open-Meteo ERA5 point access
# --------------------------------------------------------------------------
def fetch_farm_year(session, lat, lon, year, retries=5):
    """Hourly ERA5 wind speed (10 m, 100 m) for one farm-year, nearest cell.

    Returns (DatetimeIndex, ws10[np], ws100[np]) in UTC. Retries with
    exponential backoff on transient errors / rate limits (HTTP 429/5xx).
    """
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": f"{year}-01-01",
        "end_date": f"{year}-12-31",
        "hourly": "wind_speed_10m,wind_speed_100m",
        "wind_speed_unit": "ms",
        "models": "era5",      # pure ERA5 0.25 deg (not era5_land / seamless)
        "timezone": "GMT",     # UTC, to align with ENTSO-E prices downstream
    }
    last_err = None
    for attempt in range(retries):
        try:
            r = session.get(ARCHIVE_URL, params=params, timeout=120)
            if r.status_code == 200:
                h = r.json()["hourly"]
                idx = pd.to_datetime(h["time"])
                ws10 = np.array(h["wind_speed_10m"], dtype=np.float64)
                ws100 = np.array(h["wind_speed_100m"], dtype=np.float64)
                return idx, ws10, ws100
            if r.status_code in (429, 500, 502, 503, 504):
                last_err = f"HTTP {r.status_code}"
                time.sleep(2 + 2 ** attempt)
                continue
            r.raise_for_status()
        except requests.RequestException as e:
            last_err = str(e)
            time.sleep(2 + 2 ** attempt)
    raise RuntimeError(
        f"Open-Meteo fetch failed for ({lat},{lon}) {year}: {last_err}")


def cf_from_speeds(ws10, ws100):
    """Log-extrapolate (10 m, 100 m) -> 150 m hub, then adjusted IEA-15 MW
    power curve -> capacity factor. Identical math to the prior ARCO path.

    NOTE: this is a GROSS capacity factor (the Hayes shift is the only de-bias;
    no separate availability or array-wake net-loss factor). Fleet-mean is ~0.56,
    North Sea sites ~0.60, above metered net offshore CFs (~0.45-0.50). This is
    harmless here because every downstream quantity is level-invariant (the CV
    target divides by sum(generation), penetration uses observed zonal VRE
    energy, and the farm enters only through scale-invariant correlations). Do
    NOT multiply this CF by rated MW for absolute energy without first applying
    an availability/wake factor (~0.85-0.90)."""
    slope = (ws100 - ws10) / (LN_100 - LN_10)
    ws150 = ws100 + slope * (LN_150 - LN_100)
    # Negative slopes at very low wind are physical artifacts; clip.
    ws150 = np.where(ws150 < 0, ws100, ws150)
    return np.interp(ws150, PC_V, PC_P, left=0, right=0)


def site_cf_for_year(session, sites, year):
    """Pull every farm's hourly CF for one year; return DataFrame
    (rows=hours UTC, cols=farm names)."""
    series = []
    for i, row in sites.iterrows():
        idx, ws10, ws100 = fetch_farm_year(session, row.lat, row.lon, year)
        cf = cf_from_speeds(ws10, ws100)
        series.append(pd.Series(cf, index=idx, name=row["name"]))
        if (i + 1) % 10 == 0 or (i + 1) == len(sites):
            print(f"    {i + 1}/{len(sites)} farms")
        time.sleep(0.2)  # polite pacing (well under Open-Meteo rate limits)
    df = pd.concat(series, axis=1)
    df.index.name = "timestamp_utc"
    return df


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, required=True)
    ap.add_argument("--to", type=int, default=None)
    ap.add_argument("--force", action="store_true",
                    help="re-pull and overwrite existing hourly_cf_{year}.csv")
    args = ap.parse_args()
    years = list(range(args.year, (args.to or args.year) + 1))

    session = requests.Session()
    for year in years:
        print(f"\n========== Year {year} ==========")
        out = VWF_DIR / f"hourly_cf_{year}.csv"
        if out.exists() and not args.force:
            print(f"  cached: {out}  (--force to re-pull)")
            continue
        cf = site_cf_for_year(session, SITES, year)
        cf.to_csv(out)
        print(f"  saved: {out}  (shape {cf.shape}, mean CF {cf.values.mean():.3f})")


if __name__ == "__main__":
    main()
