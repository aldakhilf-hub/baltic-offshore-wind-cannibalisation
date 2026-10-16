# PyPSA calibration & validation — 2023 (headline year)

**Re-solved 2026-06-11** (frozen v1.0 grid, 2023 fleet via powerplants_filter, baseline
solver). **Figures:** fig1–fig5 (means, scatter, monthly trajectories, duration curves,
offshore CV). **Data:** `calibration_error_metrics.csv`,
`observed_capture_value_comparison.csv`, `observed_monthly.csv`, `pypsa_monthly.csv`.
**Scripts:** `1.03`, `1.04` (year 2023).

## So what (the finding)
- **Capture value (the key test):** near-perfect in big interconnected zones
  (**DE 0.908 vs observed 0.909**), over-stated in small congested Baltic-facing zones,
  monotone in exposure: BE +0.03 → DK1 +0.06 → **DK2 +0.143 (0.927 vs 0.784)**. Cause is
  PRICE structure (shadow prices too flat in windy hours) — isolated by the corrected
  hybrid decomposition (CV_pypsa vs CV_hybrid share generation; the gap is price).
- **Prices:** the frozen grid prices congestion honestly but costs level accuracy —
  median |bias| ≈ 15% across resolved zones (was ~7% under the old optimal-expansion
  setup, which was silently easing congestion). The thesis quantity is the CV *ratio*,
  which is what validates. State this trade-off explicitly in the methods chapter.
- nMAE replaces MAPE (MAPE is undefined with 2023's negative price hours).

## Why this protects the headline
DK2 is the closest existing analogue to the future Baltic; PyPSA is optimistic there, so
projected Baltic cannibalisation is conservative. The bias becomes the clamped, CI-banded
correction fitted in `projections_v3` (`1.09`).
