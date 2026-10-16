"""
04_observed_capture_values.py

The real "can we trust the capture prices?" test.

Computes THREE capture values per offshore-wind zone and compares them:
  CV_pypsa  = PyPSA generation  x  PyPSA shadow price   (the model's answer)
  CV_obs    = observed gen      x  observed price        (ground truth, a la Paul)
  CV_hybrid = PyPSA generation  x  observed price        (isolates the error source)

Decomposition logic (all three CVs computed on the SAME common hours):
  - CV_pypsa  vs CV_obs    -> does the model reproduce the real capture value?
  - CV_hybrid vs CV_obs    -> SAME observed price, different generation:
                              any gap isolates the GENERATION shape.
  - CV_pypsa  vs CV_hybrid -> SAME PyPSA generation, different price:
                              any gap isolates the PRICE structure.
  (Audit fix 2026-06-11: the original key had these two attributions swapped;
   verify any thesis prose that cites this decomposition.)

Observed offshore generation (ENTSO-E "Wind Offshore", PSR B18) is pulled once
and cached under data/observed_generation/. Only zones with real offshore wind
exist historically (North Sea): DE, NL, BE, DK1, DK2. GB has offshore but no
post-Brexit observed prices; the Baltic has ~no offshore (projection only).

Usage:
    python 04_observed_capture_values.py <year>
"""

import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import pypsa
import yaml

if len(sys.argv) != 2:
    sys.exit("Usage: 04_observed_capture_values.py <year>")
YEAR = int(sys.argv[1])

ROOT = Path(__file__).resolve().parent.parent
OBS_CSV = ROOT / "data" / "observed_prices" / f"entsoe_prices_{YEAR}.csv"
GEN_CACHE = ROOT / "data" / "observed_generation"
GEN_CACHE.mkdir(parents=True, exist_ok=True)
GEN_CSV = GEN_CACHE / f"offwind_gen_{YEAR}.csv"
NETWORK_PATH = Path.home() / f"pypsa-eur/results/faisal-{YEAR}/networks/base_s_30_elec_.nc"
OUTPUT_DIR = ROOT / "results" / f"calibration_{YEAR}"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# analysis-zone -> ENTSO-E query code for offshore generation
ZONE_QUERY = {"DE": "DE_LU", "NL": "NL", "BE": "BE", "DK1": "DK_1", "DK2": "DK_2"}
DK_LON_CUT = 11.0


def section(t):
    print(f"\n{'=' * 78}\n{t}\n{'=' * 78}")


def tz_utc(s):
    if s.index.tz is None:
        s = s.copy()
        s.index = s.index.tz_localize("UTC")
    return s


# ---------------------------------------------------------------------------
# 1. Observed offshore generation (cached pull, resampled to hourly UTC)
# ---------------------------------------------------------------------------
section(f"1. Observed offshore generation ({YEAR})")
if GEN_CSV.exists():
    print(f"Using cache: {GEN_CSV}")
    gdf = pd.read_csv(GEN_CSV, parse_dates=["timestamp_utc"])
    gdf["timestamp_utc"] = pd.to_datetime(gdf["timestamp_utc"], utc=True)
    obs_gen = gdf.pivot(index="timestamp_utc", columns="zone", values="gen_MW")
else:
    from entsoe import EntsoePandasClient
    key = yaml.safe_load(open(Path.home() / ".entsoerc"))["api_key"]
    client = EntsoePandasClient(api_key=key)
    start = pd.Timestamp(f"{YEAR}-01-01", tz="UTC")
    end = pd.Timestamp(f"{YEAR+1}-01-01", tz="UTC")
    cols = {}
    for zone, code in ZONE_QUERY.items():
        print(f"  {zone} ({code}) ...", end=" ", flush=True)
        try:
            g = client.query_generation(code, start=start, end=end, psr_type="B18")
        except Exception as e:
            print(f"FAILED ({type(e).__name__}: {str(e)[:50]})")
            continue
        if g is None or len(g) == 0:
            print("empty")
            continue
        if hasattr(g, "columns"):
            # entsoe-py may return MultiIndex cols and/or both
            # 'Actual Aggregated' + 'Actual Consumption' for a production type.
            if isinstance(g.columns, pd.MultiIndex):
                g.columns = [" ".join(str(x) for x in tup) for tup in g.columns]
            off_cols = [c for c in g.columns if "Wind Offshore" in str(c)] or list(g.columns)
            agg = [c for c in off_cols if "Consumption" not in str(c)]
            g = g[(agg or off_cols)[0]]
        if hasattr(g, "columns"):       # still 2-D for any reason -> first col
            g = g.iloc[:, 0]
        g = g.tz_convert("UTC").resample("h").mean()  # 15-min -> hourly avg MW
        cols[zone] = g
        print(f"{len(g)} hours")
        time.sleep(0.4)
    obs_gen = pd.DataFrame(cols)
    obs_gen.index.name = "timestamp_utc"
    (obs_gen.reset_index().melt("timestamp_utc", var_name="zone", value_name="gen_MW")
     .dropna(subset=["gen_MW"]).to_csv(GEN_CSV, index=False))
    print(f"Cached -> {GEN_CSV}")
print(f"Observed-gen zones: {list(obs_gen.columns)}")

# ---------------------------------------------------------------------------
# 2. Observed prices (zone-level so DK1/DK2 survive)
# ---------------------------------------------------------------------------
obs = pd.read_csv(OBS_CSV, parse_dates=["timestamp_utc"])
obs["timestamp_utc"] = pd.to_datetime(obs["timestamp_utc"], utc=True)
obs_zone = obs.groupby(["timestamp_utc", "zone"])["price_eurMWh"].mean().unstack("zone")
obs_country = obs.groupby(["timestamp_utc", "country"])["price_eurMWh"].mean().unstack("country")


def obs_price_for(zone):
    if zone in ("DK1", "DK2"):
        return obs_zone[zone] if zone in obs_zone.columns else None
    return obs_country[zone] if zone in obs_country.columns else None


# ---------------------------------------------------------------------------
# 3. PyPSA gen + price per zone
# ---------------------------------------------------------------------------
section(f"2. PyPSA offshore gen + shadow prices ({YEAR})")
n = pypsa.Network(NETWORK_PATH)
prices_t = n.buses_t.marginal_price
off = n.generators[n.generators.carrier.isin(["offwind-ac", "offwind-dc", "offwind-float"])].copy()
off["country"] = off.bus.map(n.buses.country)
off["lon"] = off.bus.map(n.buses.x)


def pypsa_zone_gen_ids(zone):
    if zone in ("DK1", "DK2"):
        west = off.lon < DK_LON_CUT
        sub = off[(off.country == "DK") & (west if zone == "DK1" else ~west)]
    else:
        sub = off[off.country == zone]
    return [g for g in sub.index if g in n.generators_t.p.columns]


def pypsa_zone_gen(zone):
    """Hourly PyPSA offshore generation (MW) for the zone. (The old version
    also computed a per-bus capture price that was then discarded — audit fix:
    dead code removed; CV_pypsa is defined below on the zone-mean price,
    the same convention as 1.08/1.09/1.11.)"""
    ids = pypsa_zone_gen_ids(zone)
    if not ids:
        return None
    return tz_utc(n.generators_t.p[ids].sum(axis=1))


# zone shadow-price series: simple (unweighted) time series mean across the
# zone's AC bus prices — the CV denominator convention used project-wide
def pypsa_zone_avg_price(zone):
    if zone in ("DK1", "DK2"):
        buses = [b for b in n.buses.index
                 if n.buses.at[b, "carrier"] == "AC" and n.buses.at[b, "country"] == "DK"
                 and ((n.buses.at[b, "x"] < DK_LON_CUT) == (zone == "DK1"))]
    else:
        buses = [b for b in n.buses.index
                 if n.buses.at[b, "carrier"] == "AC" and n.buses.at[b, "country"] == zone]
    buses = [b for b in buses if b in prices_t.columns]
    if not buses:
        return None
    return tz_utc(prices_t[buses].mean(axis=1))


# ---------------------------------------------------------------------------
# 4. Three capture values per zone
# ---------------------------------------------------------------------------
section(f"3. Capture-value comparison ({YEAR})")


def cv(gen, price):
    """CV = sum(gen*price)/(sum(gen)*mean(price)) on pre-aligned hours."""
    if gen.sum() <= 0:
        return np.nan, np.nan, np.nan
    capture = (gen * price).sum() / gen.sum()
    base = price.mean()
    return capture / base if base else np.nan, capture, base


rows = []
for zone in ZONE_QUERY:
    P_pypsa = pypsa_zone_gen(zone)
    lam_pypsa = pypsa_zone_avg_price(zone)
    lam_obs = obs_price_for(zone)
    g_obs = obs_gen[zone] if zone in obs_gen.columns else None
    if P_pypsa is None or lam_obs is None:
        continue

    # Align ALL available series on ONE common hour set so the three CVs are
    # strictly comparable (audit fix: pairwise alignment computed each CV on a
    # different hour set, distorting the decomposition by up to ~0.013).
    frames = {"P_pypsa": P_pypsa, "lam_obs": tz_utc(lam_obs)}
    if lam_pypsa is not None:
        frames["lam_pypsa"] = lam_pypsa
    if g_obs is not None:
        frames["g_obs"] = tz_utc(g_obs)
    al = pd.concat(frames, axis=1).dropna()
    if len(al) < 100:
        continue

    cv_p, cap_p, base_p = (cv(al["P_pypsa"], al["lam_pypsa"])
                           if "lam_pypsa" in al.columns else (np.nan,) * 3)
    cv_o, cap_o, base_o = (cv(al["g_obs"], al["lam_obs"])
                           if "g_obs" in al.columns else (np.nan,) * 3)
    cv_h, cap_h, base_h = cv(al["P_pypsa"], al["lam_obs"])

    rows.append({
        "zone": zone,
        "n_common_hours": len(al),
        "energy_obs_GWh": (g_obs.sum() / 1e3) if g_obs is not None else np.nan,
        "energy_pypsa_GWh": P_pypsa.sum() / 1e3,
        "CV_pypsa": cv_p,
        "CV_obs": cv_o,
        "CV_hybrid": cv_h,
        "capt_price_pypsa": cap_p,
        "capt_price_obs": cap_o,
        "base_price_obs": base_o,
    })

cmp = pd.DataFrame(rows).set_index("zone")
print(cmp.round(3).to_string())
cmp.round(4).to_csv(OUTPUT_DIR / "observed_capture_value_comparison.csv")
print(f"\nSaved: {OUTPUT_DIR / 'observed_capture_value_comparison.csv'}")

# interpretation helper (corrected attributions — see module docstring)
print("\nReading the table:")
print("  CV_pypsa  vs CV_obs    -> does PyPSA reproduce the real capture value?")
print("  CV_hybrid vs CV_obs    -> same observed PRICE, different generation:")
print("                            any gap isolates the GENERATION shape.")
print("  CV_pypsa  vs CV_hybrid -> same PyPSA GENERATION, different price:")
print("                            any gap isolates the PRICE structure.")
