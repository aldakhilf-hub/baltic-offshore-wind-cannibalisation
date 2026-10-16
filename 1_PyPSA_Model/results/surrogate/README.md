# PyPSA surrogate emulator (Act 3)

**Updated 2026-06-12: retrained after the 2024-validation-year refit of the bias
correction. 1.14 now PARSES the canonical fit from `projections_v3/fit_metadata.txt`
(exactly as 1.18 does) instead of hardcoding constants — single source of truth;
the previously baked-in values (A −0.005, B 0.399, clamp 0.38) were from a
pre-canonical fit. All numbers below verified against the regenerated artifacts.**

**Scripts:** `1.12_surrogate_design.py` → `1.13_surrogate_runs.py` → `1.14_surrogate_fit.py`
→ `1.15_surrogate_sensitivity.py` → `1.16_resolution_check.py` (validation appendix)

## What this is
A fast XGBoost emulator of the validated PyPSA model: given 8 inputs (gas, CO₂, demand,
and realized Baltic/NS-offshore, solar, battery, H2 capacities) + zone + year, it predicts
per-zone offshore capture value and price in milliseconds instead of a multi-minute Gurobi
solve. Trained on **76 PyPSA runs** — 21 harvested full-hourly canonical/gas-shock networks
+ 50 fresh 3-hourly Latin-Hypercube scenarios + 5 TYNDP anchor points.

## Files
| File | What it is |
|---|---|
| `design_inputs.csv` | the 55-row Latin-Hypercube + anchor design (`1.12`) |
| `run_outputs.csv`, `run_summary.csv` | per-(run,zone) and per-run PyPSA outputs = training data (`1.13`) |
| `surrogate_cv.json`, `surrogate_price.json` | trained XGBoost models (`1.14`) |
| `surrogate_metrics.csv`, `surrogate_metrics_per_zone.csv`, `surrogate_anchor_check.csv` | validation |
| `resolution_check.csv` | full-hourly vs 3-hourly CV equivalence (`1.16`) |
| `fig_surrogate_fit.png` | predicted vs actual (out-of-fold) |
| `fig_shap_cv.png`, `surrogate_shap_importance.csv` | what drives capture value |
| `fig_sensitivity_1d.png`, `fig_response_surface.png`, `fig_montecarlo.png`, `sensitivity_montecarlo.csv` | the sensitivity tools (`1.15`) |

## So what (the findings)
- **Capture value emulated well:** grouped-CV (held-out-scenario) **R² = 0.863**; a degree-2
  polynomial baseline fails (R² ≈ 0) → the response surface is genuinely non-linear and
  XGBoost is essential. (Was 0.872 before the corrected training target moved to the
  canonical n=14 fit.)
- **Price now emulated well too: R² = 0.920** (was 0.46 pre-fix). Pricing scarcity through
  the DSR ladder + 4,000 EUR/MWh cap (instead of unbounded VOLL spikes) made wholesale
  prices physically learnable — itself evidence the corrected engine is better specified.
- **Anchor check (held-out canonical scenarios):** all four 2040 anchors reproduced to
  **±0.004–0.017**; the two 2030 anchors miss by 0.052/0.083. RULE: quote the surrogate
  for sensitivity exploration and uncertainty fans; quote the direct PyPSA solves for
  canonical point estimates.
- **Monte-Carlo over the full 8-input envelope (2,000 samples):** NS/Baltic capture-value
  asymmetry **median 2.28× [90%: 1.06, 3.19]**; Baltic CV median 0.29 [0.19, 0.61].
  (The envelope deliberately explores beyond TYNDP — up to 150 GW Baltic offshore — so the
  MC median sits below the TYNDP-anchored headline range 0.36–0.50.)
- **Buildout — not gas — drives Baltic cannibalisation** across the whole response surface.

## Caveats
- The two 2030 anchors are the emulator's weakest points (see RULE above).
- Training mixes full-hourly harvested runs and 3-hourly LHS runs; `resolution_check.csv`
  (`1.16`, run 2026-06-12): mean |ΔCV| = 0.024; ≤0.04 at the moderate design point, but
  up to 0.147 (DK2) at the extreme-buildout corner (139 GW Baltic) — 3-hourly sampling
  smooths windy-hour price crashes, so EXTREME-corner surrogate predictions lean
  optimistic. The canonical anchors are full-hourly harvested, so the headline-relevant
  region is unaffected.
- The Baltic bias correction is applied with penetration clamped to the validated range
  (consistent with 1.09); NS zones stay raw. GB and NO are excluded from the quotable
  `ns_*` aggregate columns (model-limitation zones — see 1.11).
