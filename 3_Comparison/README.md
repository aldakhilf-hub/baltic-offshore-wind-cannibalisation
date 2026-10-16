# Track 3 · Comparison — technical reference

The cross-track join: **Observed vs PyPSA vs Regression** capture values — the headline
deliverable the supervisor asked for. Owned by neither model; `3.01_compare_three_way.py`
reads both tracks' `results/`. **Since 2026-06-11 the regression column is the GroupKFold
OUT-OF-FOLD prediction** (the model never saw the zone's farms) — the three estimates are
genuinely independent.

→ Plain-language story: `../0_READ_THIS_FIRST.md` § 5 (2026-06-11 update block).

Run: `python 3.01_compare_three_way.py` (env `pypsa-eur-arm64`; instant; requires 2.06's
`oof_predictions_groupkfold.csv`).

---

## Part 1: validation triangle (verified 2026-06-15; regression column on the bidding-zone panel, 15 zone-years)

| zone (2023) | Observed | PyPSA | Regression (OOF) |
|---|---|---|---|
| DE | 0.909 | 0.908 | 0.913 |
| NL | 0.881 | 0.883 | 0.887 |
| BE | 0.869 | 0.896 | 0.879 |
| DK1 | 0.854 | 0.917 | 0.861 |
| **DK2** | **0.784** | **0.927** | **0.798** |

Out-of-fold regression error ≤0.014 in 2023 (table above), ≤0.024 in 2024, ≤0.025 in
2019; **PyPSA's error grows with congestion exposure and REPLICATES across years,
peaking +0.143 (2023) / +0.141 (2024) at DK2**, where the regression, predicting zones
it never saw, lands within 0.014 / 0.006. A `CV_vwf_empirical` column (synthetic-farm ×
observed-price) is kept as a data cross-check.

## Part 2 — projection (2030/2040 Baltic, no observed truth)

PyPSA bias-corrected Baltic CV **0.75–0.77 (2030) → 0.36–0.50 (2040)** with 95% CI bands
(±0.02–0.04; bias fit n=14, slope CI strictly positive since the 2024 refit).
The regression **formally abstains**: 0/36 projection rows are within its full training
support (carbon exceeds the training range everywhere, and the carbon-clamp sensitivity
proves the tree model flat-lines) → **PyPSA carries the Baltic projection, by demonstrated
necessity.** That division of labour is itself the result.

## Outputs (`results/`)
`validation_triangle.csv`, `projection_pypsa.csv`, `projection_regression.csv`,
`fig_validation_triangle_2023.png`, `fig_baltic_projection_pypsa_vs_regression.png`.

## Caveats
Regression zone CV is a simple mean over the zone's farm-months (PyPSA's is
energy-weighted) — small, documented aggregation difference. The triangle's PyPSA 2019 leg
carries the year-correct fleet since 2026-06-11; 2019 shows a mild uniform +0.06 bias.
