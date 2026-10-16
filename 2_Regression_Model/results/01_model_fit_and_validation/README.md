# Model fit & validation (2.06)

**Bidding-zone market panel since 2026-06-15; zone-resolved features since 2026-06-11
(lever C).** Files: `regression_metrics.csv` (current panel),
`regression_metrics_v1_country.csv` (pre-lever-C country baseline; the before/after pair
is a thesis result), `enclosed_baltic_oof.csv` (the panel transfer test),
`feature_importance.csv`, `oof_predictions_groupkfold.csv` (the out-of-fold predictions
3.01 uses), `xgb_operational.json`, `fig_pred_vs_actual_ns_to_baltic.png`, figures.

## Key numbers (verified 2026-06-15, panel)
| protocol | country-level | zone panel |
|---|---|---|
| Random K-fold (Paul) | 0.733 | **0.752** |
| Leave-farm-out (headline) | 0.598 | **0.686** |
| Leave-farm-out ex-2022 | — | 0.69 |
| NS→Baltic transfer | 0.360 | **0.379** |
| Time split (train≤2022) | — | **−0.032** |

Reading: resolving system features at the level prices form (+DK_1/DK_2/SE_4) and pricing
a virtual farm in every zone with observed prices buys ~9 R² points of out-of-sample skill
(0.598 to 0.686 leave-farm-out), while the time split stays negative: spatial resolution
cannot fix temporal extrapolation, which is exactly the two-track design's premise. Paul
comparator: his UNTUNED XGBoost = 0.82 on the leaky random K-fold (we don't tune;
like-for-like).

## Panel transfer test (`enclosed_baltic_oof.csv`)
The model predicts 6 of 7 enclosed Baltic zones out-of-fold, blind to each, within 0.07:
PL 0.017, DK2 0.025, LT 0.032, EE/LV 0.035, SE4 0.067. Only Finland misses (0.10), because
its low value is Olkiluoto-3 nuclear baseload, not a market feature. The feature-to-capture
relationship transfers across price zones; it is not a DK2 peculiarity.
