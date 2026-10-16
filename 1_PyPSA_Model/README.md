# Track 1 · PyPSA Model: technical reference

System-optimisation track. Build PyPSA-Eur for the 14-country North-Sea + Baltic
geography, validate it against observed prices and capture values, project 2030/2040
under TYNDP buildout, test gas-shock sensitivity, and emulate the whole model with a
fast surrogate. **Fully re-solved 2026-06-11 after the forensic audit** (frozen v1.0
grid, year-correct fleets, solver parity, DSR scarcity ladder); see
`../6_REVIEW_FINDINGS_2026-06-10.md`.

Plain-language story: `../0_README/0_READ_THIS_FIRST.md` § 3 (and its 2026-06-11
update block).

**Headline (verified 2026-06-12, after the 2024 validation year was added):** corrected
Baltic capture value **0.75-0.77 (2030) -> 0.36-0.50 (2040)**, 95% CI about ±0.02-0.04;
the raw frozen-grid model already shows most of the effect (0.46-0.57 in 2040). The bias
fit now rests on 14 points across three years (slope CI strictly positive). Gas shocks
are second-order: 2030 NS ~10x more gas-exposed than the Baltic; by 2040 both basins
largely decouple.

---

## 1 · Architecture: how the pieces fit together

Two engines produce every number in this track, and they share one physics.

```
ENTSO-E (prices, generation,        TYNDP 2024 workbooks
demand, capacity)                   (capacity, demand, fuel/CO2)
        |                                   |
        v                                   v
  1.01 pulls observed data            1.06 parses to CSVs
        |                                   |
        |     ~/pypsa-eur repo (snakemake)  |
        |     1.02 -> SOLVED BASELINES      |
        |     2019 + 2023 + 2024 (.nc)      |
        v           |                       v
  1.03/1.04/1.05 validate    1.07 SCENARIO ENGINE: loads the prepared
  prices + capture values    2023 network in Python, applies TYNDP
  (the bias is measured      overlay + corrections A-F, solves with
  here)                      identical Gurobi settings -> 6 scenarios
        |                           |
        v                           v
  1.09 bias-correction fit   1.08 per-zone projected CVs
  (clamped, CI-banded)  ---> canonical corrected projection
                                    |
        reused by: 1.10/1.11 gas grid · 1.12-1.16 surrogate ·
                   1.17 scarcity decomposition · 1.18 grid bracket
```

**Engine 1, the baselines, run through snakemake.** Snakemake is PyPSA-Eur's build
system: a directed graph of rules, where each rule declares its inputs, its outputs,
and the script that turns one into the other (the same idea as `make`). Asking for
the final network file makes snakemake walk the graph backwards, run whatever is
missing or out of date, and skip everything already built. That is why
`1.02_run_baseline.sh` is re-runnable: it requests one target file and snakemake does
only the necessary work. `figures/rulegraph.png` shows the full rule graph.

**Engine 2, the scenarios, bypass snakemake.** Script 1.07 loads the already-prepared
2023 network directly with the `pypsa` Python API, edits it in memory (TYNDP
capacities, demand, fuel and carbon prices, corrections A-F), and calls Gurobi with
the same solver settings as the baselines. Every downstream instrument (gas grid,
surrogate runs, grid bracket) calls `1.07.run()` rather than reimplementing physics,
so there is exactly one scenario engine to audit.

## 2 · How PyPSA-Eur turns raw data into a solved network

The snakemake chain, in reading order:

1. **Base network.** The European transmission grid (buses, lines, links) is
   extracted from the ENTSO-E interactive map dataset.
2. **Power plants.** Conventional generators come from the powerplantmatching
   database with capacity, fuel, efficiency, and commissioning/retirement dates.
   Our configs set `electricity.powerplants_filter` so each baseline carries the
   fleet that existed in its year (the audit found both years silently carrying a
   ~2025 fleet; the renewables `year` key only tops capacities UP, it never removes).
3. **Renewable profiles.** atlite converts an ERA5 weather cutout into hourly
   per-cell capacity factors for wind and solar, aggregated to each network bus.
   This is the same ERA5 family the regression track's virtual wind farm uses.
4. **Clustering.** The thousands of raw buses are merged to **30 representative
   nodes** across the 14 countries, weighted so the offshore-heavy markets keep
   resolution. Denmark resolves into real DK1/DK2 (split at 11°E); Sweden and
   Norway remain coarse (3 clusters), which is why SE/NO are flagged in validation.
5. **Prepare.** `electricity.transmission_limit: v1.0` freezes line and link
   capacities at today's volume (the audit's headline fix: the old `ll:` key was
   silently ignored and every solve ran with optimal grid expansion). 1.18 drops
   this constraint to compute the optimistic bound.
6. **Solve.** One year of hourly dispatch (8,760 snapshots) as a linear program in
   Gurobi: barrier method, **crossover 0** (solver parity with the validated
   baseline; also ~5x faster, ~90 s per scenario solve). The solved `.nc` file
   contains dispatch per generator (`generators_t.p`) and the **shadow price** per
   bus-hour (`buses_t.marginal_price`): how much total system cost would rise if
   one more MWh had to be served there, which under marginal pricing is the model's
   wholesale price.

Configs: the canonical YAMLs live in `configs/` here and are mirrored to
`~/pypsa-eur/config/` (1.02 reads them there; keep the two in sync).
`custom_costs_2023.csv` tunes 2023 fuel prices to observed levels. Solved networks
(~35-50 MB each) stay outside the project at `~/pypsa-eur/results/`; pre-audit
optimal-grid networks are preserved at `~/pypsa-eur/results/_backup_vopt_2026-06-11/`.

## 3 · Key definitions used throughout

- **Capture value (CV)** = generation-weighted price / time-mean zone price, on
  common hours; zone price = unweighted mean over the zone's buses (same convention
  in 1.04 / 1.05 / 1.08 / 1.09 / 1.11; an audit fix unified this).
- **Hybrid CV** (1.04) = PyPSA generation x observed prices. Same generation as the
  model, real prices: any model-vs-hybrid gap isolates PRICE structure as the error
  source; hybrid-vs-observed isolates generation shape.
- **Penetration** = offshore energy / zone consumption, a true ratio of sums
  (never a mean of per-zone ratios); the axis the bias correction lives on.
- **Frozen grid (v1.0) vs vopt** = transmission fixed at today's capacity vs
  expandable at PyPSA-Eur capex; conservative vs optimistic bound (1.18).
- **DSR ladder (correction F)** = demand response at 5% of each node's peak load
  offered at 400 EUR/MWh, then unserved energy at the 4,000 EUR/MWh day-ahead cap;
  scarcity prices like the real auction instead of unbounded penalty spikes.
- **HEADLINE_EXCLUDE** = GB + NO, the two documented model-limitation zones
  (GB structurally under-priced; NO internally grid-constrained at 3 clusters),
  excluded from every quoted aggregate.

## 4 · Script reference (run in order)

| # | Script | Reads | Writes | What it does |
|---|---|---|---|---|
| 1.01 | `pull_observed_prices.py <year>` | ENTSO-E API | `data/observed_prices/` | hourly day-ahead prices per bidding zone |
| 1.02 | `run_baseline.sh <2019\|2023\|2024>` | configs + `~/pypsa-eur` | `~/pypsa-eur/results/faisal-<year>/networks/base_s_30_elec_.nc` | snakemake chain to a solved baseline; cached, re-runnable |
| 1.03 | `calibration_error_metrics.py <year>` | solved network + 1.01 | `results/calibration_<year>/` | per-zone price bias, nMAE, RMSE, hourly/monthly correlation (DK kept split; hourly r matters because CV depends on price SHAPE) |
| 1.04 | `observed_capture_values.py <year>` | network + ENTSO-E offshore generation | `results/calibration_<year>/` | the CV validation: observed / model / hybrid on common hours |
| 1.05 | `analyse_baseline.py [year]` | solved network | `results/baseline_<year>/` | capacities, price levels (load-weighted as ratio of sums), CV tables and figures |
| 1.06 | `parse_tyndp.py` | TYNDP xlsx/xlsb | `data/tyndp/parsed_*.csv` | capacity/demand/price tables per country and trajectory (RES only; carries no thermal additions) |
| 1.07 | `run_scenarios.py` | prepared 2023 network + 1.06 | `~/pypsa-eur/results/scenarios_tyndp_v3/*.nc` | THE scenario engine: TYNDP overlay + corrections A-F + parity solve; prints shed energy per scenario |
| 1.08 | `projected_capture_values.py` | scenario networks | `results/projections_v3/projected_capture_values.csv` | per-zone projected CVs (+ superseded constant-bias v1 column, kept as the robustness trail) |
| 1.09 | `bias_correction_fit.py` | 1.04 outputs + networks | `results/projections_v3/baltic_cv_fit_corrected.csv`, `fit_metadata.txt` | CANONICAL correction: bias ~ model penetration, n=14 across 2019/2023/2024 (NL 2019 excluded as low-confidence), clamped at pen 0.50, CV floored at 0, 95% CI + leave-one-out diagnostics + input-mtime staleness guard |
| 1.10 | `gas_shock_grid.py` | `1.07.run(gas_override=)` | `~/pypsa-eur/results/gas_shock/*.nc` | 15-cell grid: 3 buildouts x 5 gas prices (15-120 EUR/MWh); separate directory, canonical networks untouched |
| 1.11 | `gas_shock_capture_values.py` | 1.10 networks | `results/gas_shock/` | response surface + computed NS/Baltic exposure slopes (every offshore zone; an early 2-region shortcut gave the WRONG sign) |
| 1.12 | `surrogate_design.py` | 1.06 + canonical inputs | `results/surrogate/design_inputs.csv` | 50-point Latin-Hypercube + 5 TYNDP anchors over 8 inputs (no simulation; decides what 1.13 solves) |
| 1.13 | `surrogate_runs.py` | design + `1.07.run()` | `results/surrogate/run_outputs.csv` | training data: harvest 21 solved full-hourly networks + solve 50 LHS points 3-hourly (resumable); the 8 inputs are MEASURED from each solved network so harvested and fresh rows are consistent |
| 1.14 | `surrogate_fit.py` | run_outputs.csv | `results/surrogate/surrogate_*.json` + metrics | XGBoost emulator; held-out-scenario validation (R² 0.863 CV / 0.920 price) + TYNDP anchor check |
| 1.15 | `surrogate_sensitivity.py` | trained surrogate | `results/surrogate/` figures + MC csv | 1-D sweeps, gas x buildout response surface, 2,000-sample Monte-Carlo fans |
| 1.16 | `resolution_check.py` | 2 design rows re-solved hourly | `results/surrogate/resolution_check.csv` | full-hourly vs 3-hourly equivalence (mean abs dCV 0.024; up to 0.147 only at the 139-GW extreme corner) |
| 1.17 | `scarcity_cv_sensitivity.py` | scenario networks | `results/projections_v3/scarcity_sensitivity.csv` | CV excluding hours >390 EUR/MWh: NT-2040 carries +0.12-0.15 adequacy (concentrated in PL); 2030 and DE/GA-2040 scarcity-free |
| 1.18 | `grid_bracket.py` | 1.07 engine, volume constraint dropped | `results/projections_v3/grid_bracket.csv` | frozen-vs-optimal bracket: corrected 2040 range 0.36-0.50 -> 0.42-0.65 |

`run_week1_refresh.sh` re-runs the entire chain end-to-end (~3 h post-parity) with
backups and verification gates; use it after any engine change.

## 5 · Corrections applied by 1.07 (full reasons in its docstring)

(A) DE/PL coal-lignite phase-out by year · (A2) PL nuclear +3.9 GW by 2040 (PEP2040;
the TYNDP parse carries no thermal additions) · (B) offshore hard-caps DK 50 / FI 25 /
SE 35 GW (bounds the Energy-Island attribution artefact) · (C) year-dependent DK1/DK2
split 65/35 -> 55/45 (resource-based allocation under-weights DK2) · (D) H2
sector-coupling-lite floor (electrolyser link + fixed H2 demand + priced import
backstop; removes the electricity-only zero-price artefacts) · (E) demand rebase
crisis-2023 -> 2019 before TYNDP growth + documented GB/NO fallbacks · (F) DSR
scarcity ladder (see definitions). Prescribed capacities are never silently
truncated; exceedances over cluster potential are logged.

## 6 · Validation result (2026-06-11 numbers)

PyPSA reproduces capture value cleanly in large interconnected zones (DE 2023:
**0.908 vs observed 0.909**) and over-states it in small Baltic-facing zones,
monotonically in congestion exposure: BE +0.03 -> DK1 +0.06 -> **DK2 +0.143 (0.927 vs
0.784)**. The hybrid decomposition (1.04) pins the cause to PRICE structure: shadow
prices too flat in windy hours. 2019 shows a mild near-uniform +0.06 (NL excepted,
+0.009, which is why 1.09 drops it). **2024 (added 2026-06-12, solved after the
projection engine was frozen) replicates the signature a third time:** large zones
+0.02 to +0.04, DK1 +0.104, **DK2 +0.141 (0.949 vs 0.808)**, hybrid again assigning
the error to prices. DK2 is the closest analogue to the future Baltic, so the model
is optimistic there and the corrected headline is conservative. The deliberate
trade-off: freezing the grid worsened price-LEVEL fit (2023 median abs bias ~15%)
while the capture-value RATIO, the thesis quantity, validates.

## 7 · Documented limitations

1. GB structurally under-priced and absent post-Brexit; NO grid-constrained at
   3-cluster resolution; both HEADLINE_EXCLUDE.
2. H2 floor and DSR tier are parametric stand-ins for sector coupling and TYNDP
   flexibility volumes.
3. Residual unserved energy ~0.04-0.05% of demand, priced at the cap; shed volumes
   printed per scenario by 1.07.
4. Bias fit: 14 points across three years; slope 95% CI [0.08, 0.39] strictly
   positive, leave-one-out slope range [0.19, 0.27]; still quote the CI bands. The
   correction is a refinement (the raw model already erodes), not the source.
5. Validation years: 2019 + 2023 + 2024 (2024 added 2026-06-12; required
   `load: supplement_synthetic: false` because the bundled synthetic demand dataset
   ends before 2024 while the real ENTSO-E/NESO sources are complete).

## 8 · Reproduce

```bash
conda activate pypsa-eur-arm64
bash scripts/run_week1_refresh.sh           # everything, with gates (~3 h)
# or step-by-step in script-number order; per-scenario solve ~90 s since solver parity.
# 1.02 accepts 2019|2023|2024. Adding another year means a new
# config.faisal-<year>.yaml, a cutout covering that year, and extending its case list
# (pattern: the 2024 add on 2026-06-12; see configs/config.faisal-2024.yaml).
```
