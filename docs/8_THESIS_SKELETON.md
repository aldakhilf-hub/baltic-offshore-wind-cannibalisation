# 8 · Thesis Skeleton

**Modelling Wind Energy Potentials and Energy Pricing Between the Northern and Baltic Sea**
Working blueprint, 2026-06-12. Style rules: no em dashes, ever. Concise, eloquent,
engaging. Every concept built from first principles before it is used. Figures carry
the explanation wherever possible.

Conventions in this file:
- [FIG: path] = existing figure, ready to use.
- [FIG-NEW: name] = figure to be created (full list and specs at the bottom).
- [TAB: source] = table, with its data source.
- Each section lists its JOB (one line), its content beats, and its HANDOFF
  (the sentence-level bridge into the next section).
- Page budget targets a ~65-70 page main body (Paul 100 and Lina 107 included
  front matter and appendices; check the current SEF page limit before drafting).

---

## Front matter
Abstract (one page: puzzle, method, three findings, one implication).
Acknowledgements. Contents. List of Figures. List of Tables. Abbreviations
(CV, VWF, TYNDP, SDAC, DSR, LHS, SHAP, OOF, NS, BS and friends).

---

## Chapter 1 · Introduction (4-5 pages)

**JOB:** make a stranger care in four pages, plant the puzzle, state the questions.

### 1.1 Europe's next sea
Beats: the offshore buildout wave moves east; Baltic targets (Marienborg, national
programmes, PL 5.9 GW by 2030); investment decisions being made NOW on revenue
assumptions. Hook fact: negative-price hours multiplying across Europe.
First-principles seed: energy produced is not money earned.
[FIG-NEW: basin_map] Two seas, the 31 farms of this study, key interconnectors.

### 1.2 When the wind blows for everyone
Beats: build capture value from a single intuitive story (a windy afternoon, every
turbine selling at once, the price dips exactly then). Define capture value in one
sentence and one ratio. Introduce the revenue decomposition R = P · 8760 · CF · CV · p̄
as the thesis's organising equation: this work is about the CV term.
[FIG-NEW: cv_concept] One-panel schematic: a week of prices and wind, the
generation-weighted price visibly below the time average.

### 1.3 The puzzle this thesis answers
Beats: theory expects the under-built, hydro-buffered Baltic to enjoy a value
premium. State plainly that this thesis measures the opposite, and that the planned
buildout will widen the gap. One paragraph preview of the answer (no numbers yet,
the reader earns those in Chapter 4). DK2 introduced as the preview zone: the one
Baltic-like market that already built out.

### 1.4 Research questions and contributions
RQ1: How does offshore wind market value evolve in the Baltic relative to the North
Sea as the planned buildout proceeds?
RQ2: What market mechanisms determine the severity of value erosion, and do they
differ between an enclosed and an open sea basin?
RQ3: Can empirical models anchored on history project these futures, or is a system
model indispensable, and how can the two be combined credibly?
Contributions list (five bullets: measured cross-basin value landscape at
bidding-zone resolution; validated two-instrument design with an out-of-fold
triangle; mechanism decomposition incl. the per-basin analytical equation; corrected,
uncertainty-banded Baltic projection with scarcity and grid brackets; a fast
surrogate emulator of the system model).

### 1.5 How to read this thesis
One paragraph per chapter, the validate-then-project rhythm announced.
HANDOFF: "Every claim above rests on concepts the next chapter builds from the
ground up."

---

## Chapter 2 · Background and Literature Review (18-21 pages)

**JOB:** teach everything a smart non-specialist needs, funnel from market basics to
three sharp gaps. Each section ends with one sentence stating what the thesis takes
from it (Lina's chapter-end handoff discipline).

### 2.1 How electricity markets set prices
**2.1.1 The merit order and marginal pricing.** Supply stack from first principles;
the day-ahead auction; why the most expensive accepted plant sets the price for all.
[FIG-NEW: merit_order] Author-drawn merit-order schematic, two panels: calm hour
and windy hour, the price drop visible.
**2.1.2 Bidding zones, market coupling and interconnection.** Zonal pricing, SDAC,
why prices equalise until interconnectors saturate; congestion. The Baltic states'
February 2025 synchronisation as a live example.
**2.1.3 What wind does to prices.** The merit-order effect, formally; negative
prices; curtailment. Take-away sentence: wind shifts the stack rightward exactly
when wind output is high.

### 2.2 The value problem of variable renewables
**2.2.1 Capture price, capture value, value factor.** Formal definitions, monthly
vs annual conventions, the revenue decomposition revisited rigorously.
**2.2.2 Cannibalisation.** Mechanism and the canonical evidence (Hirth's curves,
penetration dependence); domestic and cross-border variants (Stiewe spillovers).
**2.2.3 What moderates erosion.** Flexibility (hydro, storage, DSR), interconnection,
demand correlation; Hirth's hydro claim stated explicitly because Chapter 4 tests it.
**2.2.4 Why merchant value still matters under support schemes.** CfD designs across
the basins; merchant tails, negative-price clauses; bankability.

### 2.3 Two seas, two market environments
**2.3.1 The North Sea.** Deep, thermally priced, heavily interconnected; maturity.
**2.3.2 The Baltic.** Enclosed, fragmented pricing, hydro-adjacent, post-2022
decoupling from Russia; the buildout pipeline by country.
**2.3.3 What theory predicts.** The archetype table, EXPECTATION COLUMNS ONLY
(generation mix, flexibility, interconnection, the literature/theory value-factor
expectation). Pose the open question: do these expectations hold in measured data?
[TAB: 7_Thesis_Figures/results/corrected_archetype_table.csv, expectation columns]
HANDOFF: "Chapter 4 answers this with measured values; the answer motivates
everything in between."

### 2.4 Modelling market value: three traditions
**2.4.1 The forecasting taxonomy.** Weron's classes in one paragraph each; why
hourly price forecasting is the wrong tool for a decadal value question.
**2.4.2 System optimisation models.** PyPSA-Eur lineage; shadow prices as model
prices; known price-flatness issues; why validation is non-negotiable.
**2.4.3 Reduced-form capture-value regressions.** Jacquet's design as the direct
ancestor (VWF, seven features, monthly CV target); Efthymiadou's interconnection
metrics; what each achieved and where each stopped.
**2.4.4 The unexamined seam.** No study validates the two traditions against each
other where ground truth exists; none covers the Baltic buildout question.

### 2.5 Research gaps and questions
Gap 1: no systematic NS vs Baltic market-value comparison at the resolution prices
form. Gap 2: no cross-method validation of cannibalisation projections (system
model vs empirical model vs observation). Gap 3: no parameterised model explaining
WHY severity differs across markets. RQ1-3 restated formally against the gaps.
HANDOFF: "Answering these requires two instruments and a protocol for confronting
them, which the next chapter builds."

---

## Chapter 3 · Methodology (18-20 pages)

**JOB:** present one experiment with two instruments, not two projects. Pedagogy:
every design choice introduced with its reason before its mechanics.

### 3.0 Design philosophy: two instruments that fail differently
One page. The empirical instrument is anchored to reality but cannot leave it; the
system instrument can simulate unprecedented futures but its prices need auditing.
The design confronts both with observation where truth exists, then hands the
projection to whichever instrument survives.
[FIG-NEW: architecture] The thesis pipeline in one diagram: data sources, two
instruments, the triangle, the corrected projection. THE methods figure.

### 3.1 The common currency: capture value, defined once
Formal CV definition used by every component (generation-weighted price over
time-mean zone price, common hours); zone conventions (DK1/DK2 split); why one
definition everywhere matters (the audit lesson, stated without drama).

### 3.2 Data foundation
**3.2.1 Market data.** ENTSO-E: prices for 22 zones, load, generation, flows,
capacities, 2017-2024; the GB post-Brexit gap; the NL generation fix.
**3.2.2 Weather and farms.** ERA5 via Open-Meteo; the 31-farm registry.
[TAB: farm registry summary, from wind_farms_strandA.csv]
**3.2.3 Scenario data.** TYNDP 2024 capacities, demand, prices; what the parse
contains and lacks (RES only; the adequacy implications handled in 3.4.4).

### 3.3 The empirical instrument
**3.3.1 The virtual wind farm.** Log-law to 150 m from first principles; IEA 15 MW
reference turbine; Hayes smoothing and shift, with reasons.
[FIG-NEW: power_curve] Raw vs adjusted power curve (Jacquet Fig 22 analogue).
Validation against metered generation: [FIG: 2_Regression_Model/results/08_vwf_validation/fig_vwf_vs_observed.png]
with the metrics table (hourly r 0.88, monthly 0.95). State plainly: neither
predecessor validated this step.
**3.3.2 Seven features at bidding-zone resolution.** Each feature defined with its
economic meaning first, formula second. The zone-resolution choice (lever C) and
why country aggregates blur exactly the contrast under study.
[FIG: 7_Thesis_Figures/results/fig_C_feature_evolution.png]
**3.3.3 Models and validation.** Algorithms; the three protocols (random
K-fold for comparability with Jacquet, leave-farm-out as the headline, the
time split as a deliberate stress test); basin-transfer tests; out-of-fold
prediction export (feeds 3.5.1).
**3.3.4 Mechanism tools.** SHAP in two sentences a reader can trust; the analytical
equation (Jacquet's form), per-basin fitting, farm-block bootstrap.

### 3.4 The system instrument
**3.4.1 Scope and configuration.** PyPSA-Eur, 14 countries, 30 clusters, hourly
year, frozen grid (v1.0) with the conservative-bound logic stated; year-correct
fleets via commissioning-date filters.
**3.4.2 Historical baselines.** 2019 and 2023; what calibration means here
(price levels vs the CV ratio); solver settings and why duals demand parity.
**3.4.3 Projecting 2030/2040.** The TYNDP overlay and corrections A-F, one short
paragraph each with its justification.
[TAB: corrections summary table, from 1.07 docstring]
**3.4.4 Scarcity representation.** The DSR ladder and the 4,000 EUR/MWh cap; why
unbounded penalty prices would poison a value metric; residual shed volumes
reported per scenario.

### 3.5 The confrontation protocol
**3.5.1 The validation triangle.** Three independent estimates of the same
observable; why the regression column must be out-of-fold to claim independence.
**3.5.2 The bias correction.** The DK2 analogue argument; the penetration fit on
the model's own axis; clamping; confidence intervals carried to the headline.
**3.5.3 Robustness instruments.** Gas-price grid; the frozen-vs-optimal grid
bracket; the scarcity-hour decomposition; the surrogate emulator (design, training,
held-out validation) as the uncertainty engine.
**3.5.4 Reproducibility.** One paragraph: the numbered pipeline, the refresh chain,
runtimes. Details to Appendix D.

HANDOFF: "The instruments are built; the next chapter turns them loose in a fixed
order: measure, validate, explain, project."

---

## Chapter 4 · Results (20-24 pages)

**JOB:** answer the research questions in the order the evidence allows. The
validate-then-project rhythm; DK2 appears in every section.

### 4.1 The measured landscape: today's value, answered (opens RQ1)
**4.1.1 Eight years of capture value, two basins.**
[FIG: 7_Thesis_Figures/results/fig_B_cv_history_basins.png]
Near-parity before the crisis, the Baltic lagging since 2022. The archetype table
completed with the measured column; theory's expectations versus measurement,
row by row (Finland the starkest miss, and why).
[TAB: corrected_archetype_table.csv, full]
**4.1.2 The discount pre-dates the buildout.** The three-way split (NS 0.886,
under-built Baltic 0.837, built-out DK2/SE4 0.788), monotone in exposure.
**4.1.3 Why the gap opened.**
[FIG: 2_Regression_Model/results/06_cv_gap_decomposition/fig_gap_waterfall.png]
Interconnection disadvantage and wind-pattern structure, not local penetration.
HANDOFF: "A measured puzzle deserves measured instruments; first they must earn
trust."

### 4.2 Can the instruments be trusted? (answers RQ3, part one)
**4.2.1 The empirical instrument.** Fit metrics across protocols; the zone
resolution payoff; then the honest failure.
[FIG: 7_Thesis_Figures/results/fig_F_leverC_before_after.png]
[FIG: 7_Thesis_Figures/results/fig_D_timesplit_failure.png]
**4.2.2 The system instrument.** Calibration in brief (level accuracy traded for
honest congestion); capture value reproduced where the grid is strong.
[FIG: 1_PyPSA_Model/results/calibration_2023/fig5_offshore_wind_cv.png or fig2 scatter, pick at draft time]
**4.2.3 The triangle.** Three independent estimates; DK2 as the divergence point.
[FIG: 3_Comparison/results/01_validation_triangle_2023/fig_validation_triangle_2023.png]
**4.2.4 The division of labour, demonstrated.** The strict range check; the
carbon flat-line.
[FIG: 7_Thesis_Figures/results/fig_E_carbon_flatline.png]
HANDOFF: "With roles assigned, the question turns from whether to why."

### 4.3 The mechanism: what sets the severity (answers RQ2)
**4.3.1 The drivers, decomposed.**
[FIG: 2_Regression_Model/results/02_capture_value_mechanism_SHAP/fig_shap_beeswarm.png]
Shares with directions; the carbon/time-signal caveat stated inline.
**4.3.2 One equation, two basins.**
[FIG: 2_Regression_Model/results/07_analytical_per_basin/fig_constants_comparison.png]
The convexity result (alpha steeper in 99/100 bootstraps); implied slopes at today's vs
buildout-like conditions (about 1.6x today, 1.9x at P90 dominance).
**4.3.3 The weather agrees.** Clusters from output correlations alone; the Anholt
detail; synchronicity pairs in one paragraph.
[FIG: 2_Regression_Model/results/04_farm_correlation_clusters/ matrix + map, combined]
HANDOFF: "Mechanisms that accelerate with dominance predict their own future; the
system instrument now quantifies it."

### 4.4 The projection: Baltic value under buildout (closes RQ1)
**4.4.1 The corrected projection.**
[FIG: 1_PyPSA_Model/results/projections_v3/fig_bias_fit_and_corrected.png]
Headline numbers with CI bands; per-scenario table.
[TAB: baltic_cv_fit_corrected.csv]
**4.4.2 Is it cannibalisation or scarcity?**
[FIG-NEW: scarcity_bars] Full vs ex-scarcity CV per scenario (from
scarcity_sensitivity.csv). Clean scenarios erode regardless.
**4.4.3 Does the grid assumption decide the answer?**
[FIG: 1_PyPSA_Model/results/projections_v3/fig_grid_bracket.png]
The bracket: 0.36-0.50 frozen, 0.42-0.65 optimal; clean scenarios move 0.04-0.06.
**4.4.4 The wider envelope.** Surrogate response surface and Monte-Carlo fans;
where TYNDP sits inside the explored space.
[FIG: 1_PyPSA_Model/results/surrogate/fig_response_surface.png]
[FIG: 1_PyPSA_Model/results/surrogate/fig_montecarlo.png]

### 4.5 Gas shocks: the risk that is not the story
The supervisor's question answered with the computed ratios: 2030 NS roughly 10x
more exposed; both basins decoupled by 2040.
[FIG: 1_PyPSA_Model/results/gas_shock/fig_gas_shock_cv.png]
[FIG: 1_PyPSA_Model/results/gas_shock/fig_gas_shock_sensitivity.png]

### 4.6 The thesis in one figure
[FIG: 7_Thesis_Figures/results/fig_A_headline_scoreboard.png]
Half a page of prose tying 4.1 through 4.5 into the single trajectory.
HANDOFF: "What this means beyond the model is the final chapter's business."

---

## Chapter 5 · Discussion (6-8 pages)

### 5.1 The findings against the literature
Where the results confirm Hirth-style theory and where they overturn it (the hydro
premium, inverted post-2022); positioning against Jacquet's Mediterranean answer
and Efthymiadou's interconnection finding; external value-factor projections
comparison (writing-phase literature task, no new modelling).

### 5.2 Implications for investors and policy
CfD design in thin Baltic markets; the Poland coal-displacement window and its
closing; interconnection as the highest-leverage mitigation (consistent with both
2.11 and the grid bracket); what DK2's present says about 2035 Baltic revenues.

### 5.3 Methodological reflections
The division of labour as a transferable framework: empirical instruments should
abstain measurably, system instruments should be corrected against observation;
what the out-of-fold triangle adds over single-method studies.

### 5.4 Limitations
Consolidated and honest, roughly ten items, each one sentence of limitation and one
of mitigation: bias fit n=9 with wide slope CI; GB and NO exclusions; adequacy
representation parametric; VWF covers registry farms only; thin operational Baltic
sample (FI/SE single farms); frozen correlations in projections; country-level
features outside the three zone-resolved areas; surrogate extreme-corner optimism;
2019 validation year softness; scenario demand labelled NT uses DE trajectory.

### 5.5 Future work
Sector-coupled PyPSA; hybrid offshore bidding zones and energy islands; widening
the basin set; tuning and Kendall correlations; an investor-facing revenue tool on
the surrogate.

---

## Chapter 6 · Conclusion (2-3 pages)
RQ-by-RQ answers in plain language, one paragraph each. The contributions restated
as delivered. A closing paragraph returning to the opening image: the windy
afternoon, now priced.

---

## References
(Harvest from the lit review .tex bibliography plus methods sources.)

## Appendices
- **A. Farm registry and data inventory.** The 31 farms, sources, coverage; data
  fixes (NL rescale, GB gap).
- **B. Assumptions register.** Paul-style enumerated list: every assumption, value,
  source, and sensitivity pointer. Build from the corrections table, solver
  settings, VWF parameters, DSR/cap, demand fallbacks.
- **C. Extended results tables.** Per-zone CVs, full metrics tables, gas grid,
  surrogate metrics, resolution check.
- **D. Reproducibility.** Pipeline map (scripts 1.01-1.18, 2.01-2.13, 3.01),
  refresh chain, runtimes, environment; the audit-and-fix history in two
  paragraphs referencing 6_REVIEW_FINDINGS.
- **E. Supplementary figures.** Calibration extras, pair synchronicity, surrogate
  SHAP, per-farm trajectories if drafted.

---

## New figures to create (7, all light work)

| # | Name | For | Spec |
|---|---|---|---|
| N1 | basin_map | 1.1 | Clean two-basin map: 31 farms sized by capacity, coloured by status, key interconnectors as lines. Build from registry lat/lon (matplotlib + coastlines or cartopy). |
| N2 | cv_concept | 1.2 | One-week hourly prices + wind output (real DK2 week from data), shaded generation-weighted vs time-mean price. The "aha" figure. |
| N3 | merit_order | 2.1.1 | Author-drawn two-panel merit-order schematic, calm vs windy hour. |
| N4 | architecture | 3.0 | The pipeline diagram: data, two instruments, triangle, corrected projection. Draw once, reuse in slides and viva. |
| N5 | power_curve | 3.3.1 | IEA-15MW raw vs Hayes-adjusted curve, from 2.02's tables. Two lines, one panel. |
| N6 | scarcity_bars | 4.4.2 | Full vs ex-scarcity CV per scenario, from scarcity_sensitivity.csv. |
| N7 | thesis_roadmap (optional) | 1.5 | Mini chapter-flow graphic. Cut first if space is tight. |

Existing figures already slotted: A, B, C, D, E, F (7_Thesis_Figures), triangle,
projection + bias fit + grid bracket, gas pair, SHAP set, clusters + map, gap
waterfall, constants comparison, VWF validation, surrogate fit/response/MC.

## Open decisions (flag now, decide at drafting)
1. Confirm the current SEF page/word limit and adjust budgets.
2. 4.2.2's single calibration figure: scatter vs CV bar, pick whichever reads
   faster in context.
3. Whether the surrogate earns a short methods subsection of its own in 3.5.3 or
   one paragraph plus Appendix C tables (depends on space).
4. External benchmark figure in 5.1 (literature value-factor curves overlaid with
   our points): desirable, zero modelling, add if a clean source set exists.
