# PyPSA calibration & validation — 2024 (third validation year)

**Added 2026-06-12, solved AFTER the projection engine and headline were frozen**
(frozen v1.0 grid, 2024 fleet via powerplants_filter, 2024 fuel/CO2 overrides from
the project's own monthly series: gas 34.7 EUR/MWh_th, EUA 67.0 EUR/t, identical
solver settings). One config-level fix was required: `load: supplement_synthetic:
false`, because the bundled synthetic demand dataset ends before 2024 while the
real ENTSO-E/NESO demand sources are complete (only IE missing 67 h, within the
gap-filling limits). **Figures/Data:** same layout as calibration_2023.
**Scripts:** `1.03`, `1.04` (year 2024).

## So what (the finding)
- **The congestion signature replicates a third time, out of sample:** model vs
  observed CV bias DE +0.031, NL +0.019, BE +0.035, then **DK1 +0.104** and
  **DK2 +0.141 (0.949 vs 0.808)** — the same monotone-in-congestion pattern as
  2023 (DK2 +0.143) at nearly identical magnitude.
- The hybrid decomposition again assigns the congested-zone error to PRICE
  structure (DK2 hybrid 0.821 vs observed 0.808: wind shape fine).
- Feeds 1.09: the refit on 14 points turns the slope CI strictly positive
  ([0.08, 0.39]) and tightens the headline bands to ±0.02–0.04. See
  `../projections_v3/README.md`.

## Why this matters for the headline
2024 contributes a second high-penetration DK2 anchor (pen 0.467) plus four more
points. The bias correction no longer depends on any single zone-year
(leave-one-out slope range [0.19, 0.27]), and the 2024 baseline was solved after
all projections were finalised, so the replication is a genuine out-of-sample
check of the bias model.
