# Gas-shock sensitivity

**Updated 2026-06-11 (post-audit re-solve — complete 15-cell grid incl. the previously
missing gas120 cell; ratios below are computed by 1.11, never asserted).**

**Figures:** `fig_gas_shock_cv.png`, `fig_gas_shock_sensitivity.png`
**Data:** `gas_shock_capture_values.csv` (per zone, incl. zone load for true penetrations),
`gas_shock_region_means.csv` (+ `_exSE` sensitivity), `gas_shock_sensitivity.csv`
(slopes with gas_min/gas_max range columns)
**Scripts:** `1.10_gas_shock_grid.py`, `1.11_gas_shock_capture_values.py`
(the supervisor's "adaptable to gas shocks" request)

## What it shows
Capture value and prices re-solved across a grid of gas prices (€15–120/MWh) × build-out
scenarios — how sensitive each basin's wind value is to a gas-price spike.

## So what (the finding)
- The effect of a gas spike on capture value is **modest** overall and **second-order
  relative to buildout**.
- **2030: the North Sea is ~10× more gas-exposed than the Baltic** (end-to-end slope
  −0.0067 vs −0.0007 per +10 EUR/MWh) — gas sets the price more often in the
  thermal-heavy, interconnected North Sea, while the Baltic is already nearly decoupled.
- **2040: BOTH basins largely decouple from gas** (slopes −0.001 to −0.002 per +10 EUR)
  as renewables, the DSR tier and the hydrogen floor set prices instead of gas.

## Caveats
- GB and NO are documented model-limitation zones excluded from headline aggregates
  (`HEADLINE_EXCLUDE`): GB structurally under-priced; NO internally grid-constrained at
  3-cluster resolution. Region means are also provided ex-SE (all-Sweden attribution caveat).
- Regional `penetration` is the true ratio of sums; `zone_mean_local_penetration` is the
  energy-weighted mean of zone ratios (different quantity — do not mix).
- A lesson worth stating in the write-up: an early look at only a few zones suggested
  gas-sensitivity *rose* with penetration — checking **all** zones overturned that.
  Aggregation can hide the truth.
