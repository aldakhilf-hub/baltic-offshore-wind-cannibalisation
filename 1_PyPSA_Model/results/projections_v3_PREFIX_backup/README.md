# Projection v3 — canonical Baltic capture value (bias-corrected)

**Updated 2026-06-11 (post-audit re-solve — numbers below supersede all earlier versions).**

**Figures:** `fig_bias_fit_and_corrected.png` (fit + CI band + clamp line; corrected bars with CI whiskers)
**Data:** `baltic_cv_fit_corrected.csv`, `baltic_per_zone_bias_fit.csv`, `fit_metadata.txt`
(fit coefficients, diagnostics, input-network mtimes — the staleness guard)
**Scripts:** `1.08_projected_capture_values.py` (per-zone CVs + superseded v1 constant correction),
`1.09_bias_correction_fit.py` (**the canonical correction**)

## What it shows
The 2030/2040 Baltic offshore capture value under TYNDP build-out, solved on the frozen
(v1.0) grid with the full correction set (A coal phase-out, A2 PL nuclear, B offshore caps,
C DK1/DK2 split, D H2 floor, E adequacy patches, F DSR tier), after the data-driven,
clamped, CI-banded bias correction.

## So what (the finding) — REFIT 2026-06-12 with the 2024 validation year (n = 14)
- Bias fit (model-penetration axis, consistent with application):
  **bias = +0.004 + 0.233 × penetration (R² = 0.47, n = 14; slope 95% CI [0.08, 0.39],
  STRICTLY POSITIVE; leave-one-out slope range [0.19, 0.27], no single point decisive)**,
  applied clamped to the validated range (pen ≤ 0.50), CV floored at 0, CI propagated.
- **Corrected Baltic capture value: 0.75–0.77 (2030) → 0.36–0.50 (2040)**, 95% CI ≈ ±0.02–0.04
  (bands TIGHTENED from ±0.04–0.06; 2030 unchanged; 2040 floor moved 0.37 → 0.36).
- The **raw frozen-grid model already shows most of the cannibalisation** (0.82–0.83 → 0.46–0.57);
  the correction is a refinement, not the source of the result.
- DK2 bias REPLICATES across years: +0.143 (2023) and +0.141 (2024) — the high-penetration
  anchor is no longer a single zone-year.
- Old constant-DK2 and unclamped columns are kept in the CSVs as the labelled robustness trail.
- Pre-refit (n = 9) record: bias = +0.011 + 0.195·pen, R² 0.36, slope CI [−0.04, 0.43]
  (crossed zero); corrected 2040 range was 0.37–0.50 with ±0.04–0.06 bands.

## Scarcity decomposition (1.17, added 2026-06-12)
`scarcity_sensitivity.csv`: recomputing CVs EXCLUDING scarcity-priced hours (>390
EUR/MWh) shows the 2030 and HIGH-supply 2040 scenarios are scarcity-free (delta
+0.00-0.01 — pure cannibalisation), while the two NT scenarios carry an adequacy
component of +0.12-0.15 (concentrated in PL, whose TYNDP-NT thermal additions are
not in the RES-only parse). Quote the decomposition: even adequacy-clean scenarios
show severe erosion (raw 0.46-0.49 in 2040 DE/GA-high).

## Grid bracket (1.18, added 2026-06-12)
`grid_bracket.csv` / `fig_grid_bracket.png`: the same six scenarios re-solved with
transmission made extendable at PyPSA-Eur capex (true vopt — note: under v1.0 the
prepared network's lines are genuinely FIXED, so the canonical runs are truly frozen).
2030 brackets are ~0 (no expansion economic); the 2040-NT brackets are wide
(+0.15/+0.19 — expansion relieves the same PL congestion/scarcity 1.17 identified);
the adequacy-clean 2040 DE/GA scenarios move only +0.04-0.06. Quotable (post-refit
2026-06-12): corrected 2040 Baltic CV is 0.36-0.50 under today's grid and 0.42-0.65
under optimal expansion — severe erosion from today's ~0.84 under ANY grid assumption.

## Caveats
- The fit rests on 14 points across three validation years; the slope CI is strictly
  positive and the leave-one-out range is tight, but quote the CI bands, not the point
  estimates alone. (The old "one high-leverage zone-year" caveat is retired: DK2's bias
  replicates in 2024.)
- 2040 penetrations exceed the validated range; predictions are CLAMPED there (the unclamped
  column is a labelled sensitivity only).
- Frozen-grid (v1.0) is the conservative bound; the pre-fix optimal-expansion networks
  (`~/pypsa-eur/results/_backup_vopt_2026-06-11/`) provide the optimistic bound.
- Residual unserved energy (~0.04–0.05% of demand) prices at the 4,000 EUR/MWh cap; report
  shed volumes per scenario (printed by 1.07).
(`projections_v1/` and `v2/` are the superseded robustness trail — do not quote.)
