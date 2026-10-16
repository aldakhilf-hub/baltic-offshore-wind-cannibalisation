"""
baltic_wind_model.py

A fast, self-contained emulator of the validated PyPSA-Eur power-system model,
for offshore-wind capture value in the North and Baltic Seas.

WHAT IT DOES
    You give it a build-out and fuel scenario (how much offshore wind, solar,
    battery and hydrogen is installed, plus gas and carbon prices). It returns,
    for every zone, the offshore-wind CAPTURE VALUE and the mean WHOLESALE PRICE,
    in milliseconds. No Gurobi licence, no market-data credentials, no multi-hour
    solve: it is an XGBoost emulator trained on 76 PyPSA-Eur solves.

    Capture value (CV) = average price a wind farm earns, divided by the
    time-average price. CV = 1 means it earns the average; CV < 1 means it earns
    less because it sells when everyone else's wind is also selling
    (cannibalisation). The thesis question is how hard CV falls as the enclosed
    Baltic builds out, versus the open North Sea.

ACCURACY (held-out PyPSA scenarios, from surrogate_metrics.csv)
    Capture value : R2 = 0.86   (mean abs error 0.068 CV)
    Wholesale price: R2 = 0.92   (mean abs error 45 EUR/MWh)
    Canonical 2040 scenarios reproduced to +/- 0.004 to 0.017 CV.
    USE FOR: sensitivity sweeps, response surfaces, uncertainty fans.
    For an exact canonical point estimate, use the direct PyPSA solve instead
    (the two 2030 anchor scenarios are the emulator's weakest points, off by
    0.05 to 0.08 CV).

The Baltic zones already carry the validated PyPSA bias correction (the model
over-states Baltic capture value; the correction is baked into the training
target). North Sea zones are left raw, where PyPSA is validated accurate.

Author: Faisal Bindakhil, MSc Sustainable Energy Futures, Imperial College London.
"""
from __future__ import annotations

import warnings
from pathlib import Path

import pandas as pd
import xgboost as xgb

# --------------------------------------------------------------------------- #
# The model's feature contract (must match how it was trained, exactly).
# 9 numeric inputs, then one one-hot column per zone, in this order.
# --------------------------------------------------------------------------- #
NUMERIC_INPUTS = [
    "gas",                 # gas price, EUR/MWh thermal
    "co2",                 # carbon price, EUR/tCO2
    "dem_mult",            # electricity demand multiplier vs 2019
    "realized_baltic_off", # installed Baltic offshore wind, GW
    "realized_ns_off",     # installed North Sea offshore wind, GW
    "realized_solar",      # installed solar across the 14 countries, GW
    "realized_batt",       # installed battery power, GW
    "realized_h2",         # installed hydrogen electrolyser power, GW
    "year",                # 2030 or 2040
]

ZONES = ["BE", "DE", "DK1", "DK2", "EE", "FI", "FR", "GB", "IE",
         "LT", "LV", "NL", "NO", "PL", "SE"]

FEATURE_ORDER = NUMERIC_INPUTS + [f"zone_{z}" for z in ZONES]

# Zone groupings used for the headline numbers.
# The five enclosed Baltic zones (the headline cannibalisation basin).
ENCLOSED_BALTIC = ["PL", "FI", "EE", "LV", "LT"]
# The four validated North Sea zones (the Track 3 validation set).
CORE_NORTH_SEA = ["DE", "NL", "BE", "DK1"]
# Documented model-limitation zones: GB structurally under-priced, NO hydro
# constrained at this resolution. Emitted, but excluded from headline aggregates.
MODEL_LIMITATION = ["GB", "NO"]

# The realistic input envelope the emulator was trained across (from the Latin
# Hypercube design). Inputs outside this raise a warning, not an error.
ENVELOPE = {
    "gas": (15, 100), "co2": (50, 200), "demand_multiplier": (1.0, 2.0),
    "baltic_offshore_gw": (10, 150), "ns_offshore_gw": (30, 450),
    "solar_gw": (200, 1050), "battery_gw": (50, 400), "h2_gw": (30, 200),
    "year": (2030, 2040),
}

# A faithful default scenario: the realised inputs of the thesis 2040-NT-balticHigh
# canonical run. Change any of these to ask the model a new question.
DEFAULT_SCENARIO = dict(
    gas=20.3, co2=147.0, demand_multiplier=1.50,
    baltic_offshore_gw=60.0, ns_offshore_gw=307.0, solar_gw=742.0,
    battery_gw=160.0, h2_gw=101.0, year=2040,
)

_MODEL_DIR = Path(__file__).resolve().parent / "model"
_cv_model: xgb.XGBRegressor | None = None
_price_model: xgb.XGBRegressor | None = None


def _load_models() -> tuple[xgb.XGBRegressor, xgb.XGBRegressor]:
    """Load the two trained boosters once, then cache them."""
    global _cv_model, _price_model
    if _cv_model is None:
        _cv_model = xgb.XGBRegressor()
        _cv_model.load_model(_MODEL_DIR / "surrogate_cv.json")
        _price_model = xgb.XGBRegressor()
        _price_model.load_model(_MODEL_DIR / "surrogate_price.json")
    return _cv_model, _price_model


def _check_envelope(scenario: dict, warn: bool) -> None:
    if not warn:
        return
    for key, (lo, hi) in ENVELOPE.items():
        v = scenario[key]
        if not (lo <= v <= hi):
            warnings.warn(
                f"{key}={v} is outside the trained envelope [{lo}, {hi}]. "
                "The emulator extrapolates poorly outside this range; "
                "treat the result as indicative only.",
                stacklevel=3,
            )


def _build_feature_frame(scenario: dict, zones: list[str]) -> pd.DataFrame:
    """One row per requested zone, in the model's exact feature order."""
    base = {
        "gas": scenario["gas"], "co2": scenario["co2"],
        "dem_mult": scenario["demand_multiplier"],
        "realized_baltic_off": scenario["baltic_offshore_gw"],
        "realized_ns_off": scenario["ns_offshore_gw"],
        "realized_solar": scenario["solar_gw"],
        "realized_batt": scenario["battery_gw"],
        "realized_h2": scenario["h2_gw"],
        "year": scenario["year"],
    }
    rows = []
    for z in zones:
        row = dict(base)
        for zz in ZONES:
            row[f"zone_{zz}"] = 1.0 if zz == z else 0.0
        rows.append(row)
    return pd.DataFrame(rows)[FEATURE_ORDER].astype(float)


def predict(
    gas: float = DEFAULT_SCENARIO["gas"],
    co2: float = DEFAULT_SCENARIO["co2"],
    demand_multiplier: float = DEFAULT_SCENARIO["demand_multiplier"],
    baltic_offshore_gw: float = DEFAULT_SCENARIO["baltic_offshore_gw"],
    ns_offshore_gw: float = DEFAULT_SCENARIO["ns_offshore_gw"],
    solar_gw: float = DEFAULT_SCENARIO["solar_gw"],
    battery_gw: float = DEFAULT_SCENARIO["battery_gw"],
    h2_gw: float = DEFAULT_SCENARIO["h2_gw"],
    year: int = DEFAULT_SCENARIO["year"],
    zones: list[str] | None = None,
    warn: bool = True,
) -> pd.DataFrame:
    """Predict per-zone capture value and wholesale price for one scenario.

    Returns a DataFrame: zone, capture_value, wholesale_price_eur_mwh, group,
    one row per zone (all 15 zones unless `zones` is given).
    """
    scenario = dict(
        gas=gas, co2=co2, demand_multiplier=demand_multiplier,
        baltic_offshore_gw=baltic_offshore_gw, ns_offshore_gw=ns_offshore_gw,
        solar_gw=solar_gw, battery_gw=battery_gw, h2_gw=h2_gw, year=int(year),
    )
    _check_envelope(scenario, warn)
    zones = zones or ZONES
    bad = [z for z in zones if z not in ZONES]
    if bad:
        raise ValueError(f"unknown zone(s) {bad}; valid zones are {ZONES}")

    cv_model, price_model = _load_models()
    X = _build_feature_frame(scenario, zones)

    def group(z: str) -> str:
        if z in ENCLOSED_BALTIC:
            return "enclosed_baltic"
        if z in CORE_NORTH_SEA:
            return "core_north_sea"
        if z in MODEL_LIMITATION:
            return "model_limitation"
        return "other"

    out = pd.DataFrame({
        "zone": zones,
        "capture_value": cv_model.predict(X).round(3),
        "wholesale_price_eur_mwh": price_model.predict(X).round(1),
        "group": [group(z) for z in zones],
    })
    return out


def headline(warn: bool = True, **scenario) -> dict:
    """The thesis headline numbers for one scenario.

    Returns enclosed-Baltic mean capture value, core-North-Sea mean capture
    value, and the cannibalisation asymmetry (NS / Baltic). Any scenario lever
    can be overridden as a keyword, e.g. headline(baltic_offshore_gw=120).
    """
    df = predict(zones=None, warn=warn, **scenario)
    baltic = df[df.zone.isin(ENCLOSED_BALTIC)].capture_value.mean()
    ns = df[df.zone.isin(CORE_NORTH_SEA)].capture_value.mean()
    return {
        "enclosed_baltic_cv": round(float(baltic), 3),
        "core_north_sea_cv": round(float(ns), 3),
        "asymmetry_ns_over_baltic": round(float(ns / baltic), 2) if baltic else None,
        "per_zone": df,
    }


if __name__ == "__main__":
    # A one-line smoke test: print the default-scenario headline.
    h = headline()
    print("Default scenario (2040-NT-balticHigh):")
    print(f"  enclosed Baltic capture value : {h['enclosed_baltic_cv']}")
    print(f"  core North Sea capture value  : {h['core_north_sea_cv']}")
    print(f"  cannibalisation asymmetry     : {h['asymmetry_ns_over_baltic']}x")
