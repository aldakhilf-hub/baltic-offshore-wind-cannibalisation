# 7 · Thesis Figures — the figure plan, mapped to the research questions

`7.01_make_thesis_figures.py` builds the thesis-level figures the per-track results
folders don't provide (figure strategy modelled on Jacquet 2024 / Efthymiadou 2025:
per-variable histories, headline trajectories, projection bands, honest diagnostics).
Re-run after any upstream refresh. All numbers verified 2026-06-12.

`7.02_make_ch4_figures.py` (added 2026-06-12, env pypsa-eur) builds the three
Chapter-4 assemblies no track provides directly, saving to results/ here AND to
9_Thesis_LaTeX/figures/:
- `fig_scarcity_bars.png` (4.4.2): energy-weighted Baltic CV per scenario, all hours
  vs ex-scarcity (>390 EUR/MWh). Weighted deltas: 2030 both 0.000; 2040-NT-base
  +0.145 (PL 476 h); 2040-NT-high +0.117 (273 h); 2040-DE-high +0.008; 2040-GA 0.000.
- `fig_calibration_cv_2023.png` (4.2.2): observed vs model vs hybrid CV for
  DE/NL/BE/DK1/DK2. Replaces calibration fig5 in the thesis (fig5 aggregates DK,
  blurring the DK1/DK2 contrast, and lacks the observed bar).
- `fig_clusters_matrix_map.png` (4.3.3): 2.09's clustered matrix + cluster map,
  combined side by side.

## RQ1 — Does Baltic offshore wind value survive the buildout? (No: it erodes severely)
| Figure | Source | Role |
|---|---|---|
| `fig_A_headline_scoreboard.png` | here | **THE thesis figure**: observed-era basin CV → corrected 2030/2040 with 95% CI |
| `fig_B_cv_history_basins.png` | here | Jacquet-Fig-45 analogue, both basins: near-parity pre-crisis, Baltic lags since 2022 |
| `fig_bias_fit_and_corrected.png` | 1_PyPSA/results/projections_v3 | the correction: fit + CI + clamp, corrected bars |
| `fig4_baltic_capture_value.png` | 1_PyPSA/results/projections_v3 | v1-rung robustness companion |
| `fig_gas_shock_cv.png`, `fig_gas_shock_sensitivity.png` | 1_PyPSA/results/gas_shock | gas is second-order; basins decouple by 2040 |
| `fig_montecarlo.png`, `fig_response_surface.png` | 1_PyPSA/results/surrogate | uncertainty fans over the full input envelope |

## RQ2 — What drives cannibalisation severity across markets?
| Figure | Source | Role |
|---|---|---|
| `fig_C_feature_evolution.png` | here | the 7 drivers over time, basin means (Jacquet Figs 24-30 in one panel) |
| `fig_shap_beeswarm.png`, `fig_shap_bar.png`, `fig_shap_dependence_penetration.png` | 2_Regression/results/02 | the mechanism decomposition (Gap-3 deliverable) |
| `fig_corr_matrix_clustered.png` + cluster map | 2_Regression/results/04 | weather-only corroboration: sea basins emerge from data |
| pair-synchronicity figures | 2_Regression/results/05 | diurnal/seasonal synchronicity (Jacquet Fig 43 analogue) |
| `fig_gap_waterfall.png` | 2_Regression/results/06 | **the flag resolved**: interconnection disadvantage + wind-pattern structure (not local penetration) opened the Baltic discount before the buildout |
| `fig_constants_comparison.png` | 2_Regression/results/07 | Paul's analytical form per basin on the panel: Baltic penalty more convex (α steeper in 99/100 bootstraps), implied slope about 1.9× steeper at buildout-like dominance |

## RQ3 — Can empirical models project this, or is a system model required? (Division of labour)
| Figure | Source | Role |
|---|---|---|
| `fig_validation_triangle_2023.png` | 3_Comparison/results/01 | three independent estimates; PyPSA's DK2 bias isolated |
| `fig_D_timesplit_failure.png` | here | the honest failure: the regression cannot cross the 2022 regime break |
| `fig_E_carbon_flatline.png` | here | the abstention proof: flat-line beyond training support, where TYNDP lives |
| `fig_baltic_projection_pypsa_vs_regression.png` | 3_Comparison/results/02 | PyPSA carries the projection; regression's in-range band |
| `fig_surrogate_fit.png` | 1_PyPSA/results/surrogate | the emulator's held-out-scenario skill |

## Methods-chapter figures
`fig_F_leverC_before_after.png` (here — zone vs country resolution, +0.08 R²);
`fig_pred_vs_actual_ns_to_baltic.png`, `fig_feature_importance.png` (2_Regression/results/01);
calibration figs 1–5 (1_PyPSA/results/calibration_2023); `fig_paul_fig45_NS.png`
(2_Regression data folder — the like-for-like Jacquet replication);
`fig_vwf_vs_observed.png` (2_Regression/results/08 — VWF shape validation, hourly r≈0.88);
`fig_grid_bracket.png` + `scarcity_sensitivity.csv` (1_PyPSA/results/projections_v3 —
the two robustness devices that close the 2040 headline's remaining attack surfaces).

## ⚠ FLAGGED INCONSISTENCY (2026-06-12) — lit-review premise correction
The lit review's Section-3 archetype table claims every Baltic zone shows a HIGHER value
factor than every NS zone today. **Our own data refutes this**: 2023-24 farm-level CV is
North Sea 0.886 > under-built Baltic states 0.837 > built-out DK2/SE4 0.788 (monotone in
buildout exposure; near-parity pre-crisis). When drafting, the setup must become: *the
Baltic is EARLIER on the cannibalisation curve, with DK2 as the preview of where it
leads* — not a present-day premium. The conclusion (erosion to 0.36–0.50 by 2040, post-2024-refit) is
unaffected; the story's STARTING POINT changes. fig_A/fig_B already use the corrected
framing. RESOLUTION (2.11 + corrected_archetype_table.csv here): the discount is driven
by the Baltic's interconnection disadvantage (−0.016, largest term, swung from neutral)
and structural wind-correlation penalty — the thesis's enclosure mechanism, already
visible pre-buildout. The old table's Hirth-2013-era theory values are superseded by
the measured column.
