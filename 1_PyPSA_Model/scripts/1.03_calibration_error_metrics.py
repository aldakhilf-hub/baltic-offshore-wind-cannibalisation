"""
03_calibration_error_metrics.py

Quantitative calibration metrics: PyPSA-Eur shadow prices vs observed
ENTSO-E day-ahead prices, per analysis-zone, for a chosen year.

Improvements over 03_validate_vs_observed.py:
  - Denmark is kept SPLIT into DK1 (North-Sea-facing) / DK2 (Baltic-facing),
    since the 30-cluster solve resolves them (DK1~9.8E west, DK2~12.3E east).
    These are matched to observed zones DK1 / DK2 directly.
  - Consistent treatment: single-zone countries compared 1:1; SE/NO flagged
    as un-resolved national aggregates (the clusters are not SEn/NOn faithful).
  - Reports a full error table: mean levels, bias (ME), MAE, RMSE, MAPE,
    hourly Pearson r, monthly Pearson r, monthly RMSE.

Hourly correlation is the key addition: PyPSA's linear dispatch produces a
stair-stepped price (discrete marginal-cost bands), so a good annual-mean
match can still hide a poor hour-to-hour shape -- which is what drives
capture value.

Usage:
    python 03_calibration_error_metrics.py <year>
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pypsa

if len(sys.argv) != 2:
    sys.exit("Usage: 03_calibration_error_metrics.py <year>")
YEAR = int(sys.argv[1])

ROOT = Path(__file__).resolve().parent.parent
OBS_CSV = ROOT / "data" / "observed_prices" / f"entsoe_prices_{YEAR}.csv"
NETWORK_PATH = Path.home() / f"pypsa-eur/results/faisal-{YEAR}/networks/base_s_30_elec_.nc"
OUTPUT_DIR = ROOT / "results" / f"calibration_{YEAR}"
OUTPUT_DIR.mkdir(exist_ok=True)

# Multi-zone countries that the 30-cluster model does NOT resolve faithfully.
UNRESOLVED = {"SE", "NO"}
# Longitude cut separating the two Danish clusters into DK1 (west) / DK2 (east).
DK_LON_CUT = 11.0


def section(t):
    print(f"\n{'=' * 78}\n{t}\n{'=' * 78}")


def tz_utc(idx_obj):
    """Return a copy with tz set to UTC (localize if naive)."""
    if idx_obj.index.tz is None:
        idx_obj = idx_obj.copy()
        idx_obj.index = idx_obj.index.tz_localize("UTC")
    return idx_obj


# ---------------------------------------------------------------------------
# 1. Observed prices, kept at ZONE level (so DK1/DK2 survive)
# ---------------------------------------------------------------------------
section(f"1. Observed prices ({YEAR})")
if not OBS_CSV.exists():
    sys.exit(f"Missing: {OBS_CSV}")
obs = pd.read_csv(OBS_CSV, parse_dates=["timestamp_utc"])
obs["timestamp_utc"] = pd.to_datetime(obs["timestamp_utc"], utc=True)

# zone-level matrix (DK1, DK2, SE1..SE4, ...)
obs_zone = (
    obs.groupby(["timestamp_utc", "zone"])["price_eurMWh"].mean().unstack("zone")
)
# country-level matrix (simple mean across a country's zones)
obs_country = (
    obs.groupby(["timestamp_utc", "country"])["price_eurMWh"].mean().unstack("country")
)
print(f"Observed zones available: {sorted(obs_zone.columns)}")

# ---------------------------------------------------------------------------
# 2. PyPSA prices. Country-level load-weighted; DK kept per-cluster.
# ---------------------------------------------------------------------------
section(f"2. PyPSA-Eur shadow prices ({YEAR})")
if not NETWORK_PATH.exists():
    sys.exit(f"Missing solved network: {NETWORK_PATH}")
n = pypsa.Network(NETWORK_PATH)
ac_buses = n.buses[n.buses.carrier == "AC"]
prices_t = n.buses_t.marginal_price
loads = n.loads
load_ts = n.loads_t.p_set


def load_weighted_country_price(bus_ids):
    """Load-weighted mean price across a set of buses (hourly series)."""
    p = prices_t[[b for b in bus_ids if b in prices_t.columns]]
    if p.shape[1] == 0:
        return None
    loads_c = loads[loads.bus.isin(bus_ids)]
    load_cols = loads_c.index.intersection(load_ts.columns)
    if len(load_cols) == 0:
        return p.mean(axis=1)
    num = pd.Series(0.0, index=p.index)
    den = pd.Series(0.0, index=p.index)
    for lid in load_cols:
        bus = loads_c.loc[lid, "bus"]
        if bus in p.columns:
            w = load_ts[lid]
            num += w * p[bus]
            den += w
    return num / den.replace(0, np.nan)


pypsa_zone = {}  # analysis-zone label -> hourly price series
for country, group in ac_buses.groupby("country"):
    bus_ids = list(group.index)
    if country == "DK":
        # split clusters into DK1 (west) / DK2 (east) by longitude
        for bus in bus_ids:
            lon = ac_buses.loc[bus, "x"]
            zlabel = "DK1" if lon < DK_LON_CUT else "DK2"
            s = prices_t[bus] if bus in prices_t.columns else None
            if s is not None:
                pypsa_zone[zlabel] = s  # one cluster per DK zone
    else:
        s = load_weighted_country_price(bus_ids)
        if s is not None:
            pypsa_zone[country] = s

pypsa_zone = {k: tz_utc(v.to_frame()).iloc[:, 0] for k, v in pypsa_zone.items()}
print(f"PyPSA analysis-zones: {sorted(pypsa_zone.keys())}")

# ---------------------------------------------------------------------------
# 3. Build matched observed series for each analysis-zone
# ---------------------------------------------------------------------------
def observed_for(zone_label):
    """Pick the right observed series for a PyPSA analysis-zone label."""
    if zone_label in ("DK1", "DK2"):
        return obs_zone[zone_label] if zone_label in obs_zone.columns else None
    # single-zone (or unresolved national) country -> country mean
    return obs_country[zone_label] if zone_label in obs_country.columns else None


# ---------------------------------------------------------------------------
# 4. Metrics per analysis-zone
# ---------------------------------------------------------------------------
section(f"4. Calibration error metrics {YEAR}")
rows = []
for zone in sorted(pypsa_zone.keys()):
    pp = pypsa_zone[zone]
    oo = observed_for(zone)
    if oo is None:
        continue
    df = pd.concat([pp.rename("pypsa"), oo.rename("obs")], axis=1).dropna()
    if len(df) < 100:
        continue
    err = df["pypsa"] - df["obs"]
    monthly = df.resample("MS").mean()
    rows.append({
        "zone": zone,
        "n_hours": len(df),
        "mean_pypsa": df["pypsa"].mean(),
        "mean_obs": df["obs"].mean(),
        "bias": err.mean(),
        "bias_pct": 100 * err.mean() / df["obs"].mean(),
        "MAE": err.abs().mean(),
        "RMSE": np.sqrt((err ** 2).mean()),
        # nMAE replaces MAPE (audit fix): MAPE is undefined with negative and
        # near-zero observed prices — 2023 produced impossible values like
        # -757% (FR) and +3431% (FI). MAE / mean(|obs|) is well-defined always.
        "nMAE_pct": 100 * err.abs().mean() / df["obs"].abs().mean(),
        "r_hourly": df["pypsa"].corr(df["obs"]),
        "r_monthly": monthly["pypsa"].corr(monthly["obs"]),
        "RMSE_monthly": np.sqrt(((monthly["pypsa"] - monthly["obs"]) ** 2).mean()),
        "resolved": "no" if zone in UNRESOLVED else "yes",
    })

metrics = pd.DataFrame(rows).set_index("zone")
# order: resolved zones first ("yes" before "no"), then by absolute bias
metrics = metrics.sort_values(
    ["resolved", "bias_pct"],
    ascending=[False, True],
    key=lambda s: s if s.name != "bias_pct" else s.abs())
print(metrics.round(2).to_string())
metrics.round(4).to_csv(OUTPUT_DIR / "calibration_error_metrics.csv")
print(f"\nSaved: {OUTPUT_DIR / 'calibration_error_metrics.csv'}")

# quick headline
res = metrics[metrics.resolved == "yes"]
print(f"\nResolved zones: median |bias%| = {res.bias_pct.abs().median():.1f}%, "
      f"median hourly r = {res.r_hourly.median():.2f}, "
      f"median monthly r = {res.r_monthly.median():.2f}")
