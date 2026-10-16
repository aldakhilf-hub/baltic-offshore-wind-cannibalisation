# Regression projection 2030/2040 (2.07)

**Updated 2026-06-11.** Files: `projected_capture_values.csv` (per farm × horizon ×
trajectory, with `in_range`, `in_range_vre_only`, `out_of_range_features`,
`pred_CV_xgb_carbonclamp`), `projection_summary.csv`.

## The finding: a formal abstention
Under the strict all-features range check, **0/36 projection rows are within training
support** — every TYNDP scenario carries carbon prices (113–147 EUR/t) beyond the
training maximum (91 EUR/t), carbon being the model's TOP SHAP feature. The carbon-clamp
sensitivity equals the unclamped XGBoost prediction exactly — direct proof the tree model
flat-lines out-of-support (the linear model meanwhile extrapolates to 0.44–0.74: wide,
untrustworthy). **The regression therefore abstains from future projections and the
PyPSA track carries them** — the division of labour, demonstrated rather than asserted.
(The old VRE-share-only check would have wrongly passed 18/36 rows.)
