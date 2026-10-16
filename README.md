# Offshore wind cannibalisation in the North and Baltic Seas

How much of its market value does offshore wind lose as a sea fills up with wind
farms, and how much of that loss is avoidable? This repository holds the complete
work behind an MSc thesis that answers both questions for the North Sea and the
Baltic Sea.

**Faisal Bindakhil**, MSc Sustainable Energy Futures, Energy Futures Lab,
Imperial College London, August 2026. Proposed and guided by Dr Ruslan Galimov
(RWE), supervised by Prof Adam Hawkes.

The thesis is in [`thesis/`](thesis/).

---

## What you are getting

Three working things, each usable on its own:

1. **A statistical model of capture value** (`2_Regression_Model/`). Gradient-boosted
   trees over seven market features, trained on 31 offshore wind farms and 2,706
   farm-months of observed European prices from 2017 to 2024. **The data is
   bundled**, so you can refit it in minutes without an API key.
2. **A configured European power-system model** (`1_PyPSA_Model/`). PyPSA-Eur set
   up for the 14 countries around the two seas, validated against observed prices,
   projected to 2030 and 2040 on official scenarios, with 24 scripts covering
   validation, projection and seven kinds of sensitivity.
3. **A figure and analysis pipeline** (`7_Thesis_Figures/`). Forty-four scripts
   producing every map, chart and result table in the thesis, including the
   value-adjusted cost layer and the spatial cost field.

If you are picking this up to do your own project, the useful framing is that you
inherit a validated price-and-capture-value dataset, a working power-system model
of the region, and a figure pipeline. What question you point them at is up to
you. [`CONTINUATION.md`](CONTINUATION.md) lists the open ones from this work.

---

## The finding, in one table

A wind farm's **capture value** is the average price it is paid divided by the
average price in its market over the same period. A value of 1.0 means it was paid
the market average. A value of 0.5 means it was paid half, because it sells when
every other wind farm is also selling and the price is low. That erosion is
**cannibalisation**.

| | North Sea | Baltic Sea |
|---|---|---|
| Measured today (2023 to 2024) | 0.887 | 0.889 |
| 2040, on today's grid | 0.573 | **0.471** |
| 2040, with the least-cost grid built | 0.637 | **0.664** |

Both seas start level. On today's grid the Baltic loses almost half its value and
falls well below the North Sea. Build the transmission the system model itself
chooses as least-cost, and the Baltic recovers past the North Sea.

Decomposing each basin's fall separates the part caused by the buildout from the
part caused by congestion:

| | Total fall | Buildout | Congestion |
|---|---|---|---|
| North Sea | 0.314 | 0.250 (80%) | 0.064 (20%) |
| Baltic | 0.418 | 0.225 (54%) | 0.193 (46%) |

The Baltic's congestion penalty is three times the North Sea's, while its
buildout-driven fall is actually *smaller*. The extra erosion comes from the basin
being poorly connected to the rest of Europe, and transmission can be built.

Two consequences follow. Learning cannot fix it: the levelised cost of offshore
wind falls from 74 to 66 EUR/MWh while the **value-adjusted** cost, meaning cost
divided by capture value, *rises* from 87 to 121. And the cure pays for itself:
congestion income on Baltic-related corridors runs several times the annualised
cost of the lines that would relieve them.

---

## Install

There are two installs. Start with the light one.

**Light, for the regression model.** No conda, no licence, no API key.

```bash
git clone https://github.com/aldakhilf-hub/baltic-offshore-wind-cannibalisation.git
cd baltic-offshore-wind-cannibalisation
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-light.txt
python tools/smoke_test.py
```

**Full, for the figures, maps and the power-system model.**

```bash
mamba env create -f environment.yml        # conda works too, mamba is faster
mamba activate baltic-wind
python tools/setup_pypsa_inputs.py         # add --link to save 46MB
python tools/smoke_test.py
```

`smoke_test.py` runs nine checks in about ten seconds and tells you exactly which
part of the stack is missing and what to install for it. On macOS, if check 2
fails with `libomp.dylib` not loaded, run `brew install libomp`. That is the single
most common setup failure.

`setup_pypsa_inputs.py` copies three files from `pypsa_inputs/` to `~/pypsa-eur`,
where the figure scripts look for them: the offshore region polygons, the prepared
network and the GEBCO depth grid. These normally come out of a PyPSA-Eur build,
where the weather cutout alone takes over four hours, so they ship here instead.
Nothing is overwritten unless you pass `--force`, and if you install PyPSA-Eur
later the directories merge.

---

## What you can actually run

Being clear about this matters more than making the repository look turnkey.

| | What it does | What it needs | Time |
|---|---|---|---|
| **Regression model** `2_Regression_Model/` | Refit, explain and project the statistical model from the bundled panel | Light install | Minutes |
| **Figures and maps** `7_Thesis_Figures/`, `12_Poster/` | Regenerate about 40 figures, the cost field, the value-adjusted cost maps, the site ranking | Full install plus `setup_pypsa_inputs.py` | Seconds to minutes each |
| **Re-solving the power system** `1_PyPSA_Model/` | Re-solve Europe and regenerate every projection from scratch | Everything above, plus a **Gurobi licence**, a PyPSA-Eur clone and roughly 100GB of weather data | Hours per scenario, 5 to 8 hours for the full chain |

**Eleven scripts need a solved network** and will fail without the third row.
They are `7.16`, `7.19`, `7.20`, `7.28`, `7.30`, `7.31`, `7.36`, `7.39`, `7.44`,
and the two in `3_Comparison/scripts/`. Between them they produce the grid
reversal, the buildout-against-congestion decomposition, who bears the loss, the
congestion income and the matched skill scoring. **Their output tables are all
bundled** in `7_Thesis_Figures/results/`, so you can read, plot and build on every
one of those results. You only need to re-solve to recompute them under a changed
model.

**To re-solve you also need:**

- **PyPSA-Eur** cloned to `~/pypsa-eur` at version `v2026.02.0-39-g23c2fac7`,
  recorded in `environment.lock.yml`. Every Track 1 script expects that location.
  Later versions moved config keys and will not run these configs unchanged.
- **A Gurobi licence** at `~/gurobi.lic`. Free academic licences cover this. HiGHS
  ships with linopy and is open source, but the 30-cluster hourly solves were
  never tested on it.
- **An ENTSO-E Transparency Platform account**, only to re-pull market data. The
  key goes in `~/.entsoerc` as `api_key: <token>`. The pulled data is already
  bundled, so this is optional.

---

## How the repository is laid out

Folders are numbered in reading order. Scripts inside each are numbered in **run
order**, and that numbering is the only orchestration there is. There is no
Makefile and no Snakemake wrapper, so running steps out of order will silently
produce results from stale inputs. Run them in sequence.

```
0_README/              The original orientation document, written as the work
                       progressed, plus the standalone literature review
1_PyPSA_Model/         The power-system model. 24 scripts, 1.01 to 1.23
2_Regression_Model/    The statistical model. 18 scripts, 2.01 to 2.14
3_Comparison/          Both models scored against observed prices
7_Thesis_Figures/      44 figure and analysis scripts, 7.01 to 7.44
9_Thesis_LaTeX/        Thesis source, figures and bibliography
10_Presentation/       Supervisor deck and the group presentation, with builders
12_Poster/             A1 conference poster and its figure scripts
docs/                  Supervisor briefing, the forensic audit of 2026-06-10,
                       the thesis skeleton
pypsa_inputs/          Three small PyPSA-Eur build products the figure scripts
                       need, so you do not have to run its build chain
thesis/                The submitted thesis, 114 pages
tools/                 smoke_test.py, setup_pypsa_inputs.py
```

Each track has its own `README.md` with a script-by-script reference, inputs and
outputs. Those are the detailed documentation; this file is the front door.

### Run order

```bash
# The statistical model. Light. Data is bundled, so start at 2.03.
2.01-2.02 pull market and weather data  ->  2.03 capture value per farm
  ->  2.04-2.05 build the seven features  ->  2.06 fit
  ->  2.07 project  ->  2.08-2.14 explain, cluster, analytical forms

# The power-system model. Heavy. 1.02, 1.07 and 1.10 are the solves.
1.01 pull prices  ->  1.02 solve baseline  ->  1.03-1.05 validate
  ->  1.06-1.08 project to 2030 and 2040  ->  1.09 fit the bias correction
  ->  1.10-1.11 gas shocks  ->  1.12-1.16 fast approximation and resolution checks
  ->  1.17-1.23 sensitivities: scarcity, grid bracket, hydrogen floor,
                network ratings, hydro foresight, must-run heat
# or the whole chain:  bash 1_PyPSA_Model/scripts/run_week1_refresh.sh

# Both models against reality.
3.01 three-way comparison  ->  3_Comparison/scripts/3.02 matched skill scoring
  ->  3.03 backtest the projection
```

---

## The two models, and why there are two

| | Regression model | System model |
|---|---|---|
| What it is | Gradient-boosted trees (XGBoost) over seven market features | PyPSA-Eur, the European power system solved hour by hour |
| Where prices come from | Observed day-ahead prices, 2017 to 2024 | The shadow price of the nodal energy balance |
| Trained on | 31 farms, 2,706 farm-months, 7 bidding zones with enclosed Baltic prices | Nothing. It is built from plants, costs, network and demand |
| Strength | Anchored on prices that actually occurred, so it absorbs real market behaviour | Can simulate a buildout that has never happened |
| Weakness | Cannot extrapolate beyond the observed record | Simplifications (linear dispatch, no unit commitment, perfect foresight, clustered network) bite hardest in the observed record |

They were scored against each other on identical unseen targets, with the
regression refitted leave-one-zone-out and leave-one-year-out so neither model had
seen the answer:

- **Accuracy does not separate them.** Mean absolute error 0.041 against 0.046,
  paired difference not significant.
- **Their errors have opposite signs**, so averaging the two models is wrong and
  handing over from one to the other at a defined point is right.
- **Energy-weighted, they agree to 0.005** (0.890 against 0.885).
- **At 2040 the regression declines to answer.** None of the 36 projection rows sit
  inside its training range, and its response across scenarios spans 0.008 where
  the system model spans 0.428. So the system model carries the projection by
  demonstrated necessity.

The boundary between them falls at the edge of the observed record rather than at
any particular number of years, which a 2021 backtest locates: over 2023 to 2024,
where 58% of targets are still inside the training range, the two project equally
well.

---

## If you are taking this over

Work through it in this order. Each stage ends with a number you should be able to
reproduce, which is how you know your setup is right before you trust anything you
compute yourself. **Resist starting with the power-system model.** It is the
tempting thing to open first and it will cost you weeks before you have learned
anything.

### Stage 1, a day. Reproduce the empirical half.

Read the thesis abstract and Chapter 1 first. Twenty minutes, and it tells you
what every folder here was for. Then, with the light install:

```bash
cd 2_Regression_Model/scripts
python 2.06_fit_regression.py          # fits five algorithms
python 2.08b_demeaned_shap.py          # what actually drives capture value
python 2.07_project_capture_values.py  # and where the model gives up
```

**Checkpoints.** `2.06` should give **0.686** predicting farms it never saw and
**0.752** on the easier random split, with XGBoost ahead of random forest ahead of
support vector regression. `2.08b` should show crowding leading at about 32% once
each farm is compared with the month's average, with carbon collapsing from 29% to
4%. `2.07` should report **0 of 36** projection rows inside the training range.

That last number is the whole reason this project has two models. A flat-lining
model looks broken; here it is the correct behaviour of a tree asked to
extrapolate, and the thesis proves it rather than asserting it. Understand that
before going further.

### Stage 2, a day. Reproduce the figures and the value layer.

With the full install:

```bash
python 7_Thesis_Figures/7.18_make_value_heatmaps.py   # the capture-value maps
python 7_Thesis_Figures/7.32_make_site_ranking.py     # does value change where to build
python 7_Thesis_Figures/7.43_make_group_arc_simple.py # the headline figure
```

**Checkpoint:** `7.32` should rank German Bight first on both cost and value at
every horizon, with the correlation between the two rankings falling from 0.99 in
2025 to 0.90 in 2040.

### Stage 3, only when you have a reason. Touch the power-system model.

Read `docs/6_REVIEW_FINDINGS_2026-06-10.md` first. It is the forensic audit that
found five result-changing defects in this model, and it will teach you more about
the traps than any amount of running it. Then get a Gurobi licence, clone PyPSA-Eur
at the pinned version, and start with `1.02_run_baseline.sh` for a single year so
you can compare against the recorded validation before trying a scenario.

**Checkpoint:** Germany 2023 should come out at about 0.908 against an observed
0.909. If it does, the chain is sound. If DK2 comes out near 0.93 against an
observed 0.784, that is expected and documented, so read trap 2 below before you
try to fix it.

### Then

[`CONTINUATION.md`](CONTINUATION.md) lists what is unfinished, ranked by payoff,
along with what was already tried and failed. The first two items, curtailment
volume and the planned-grid case, are both tractable for a single MSc and neither
needs the full chain re-solved.

---

## Things that will trip you up

Read this before you change anything. Each item cost real time to learn.

1. **Finland is excluded from every Baltic aggregate.** It barely builds offshore,
   so it never cannibalises, and its nuclear-driven prices pulled the Baltic mean
   up and masked the wind effect. "Baltic" means Poland, Estonia, Latvia and
   Lithuania throughout. Per-zone tables still carry Finland, clearly labelled.
2. **DK2 (eastern Denmark) is in no headline aggregate.** It is the built-out
   preview zone. The system model overstates its capture value by about 0.15, and
   this is structural rather than a bug: its observed 264 negative-price hours come
   from must-run heat, sub-zero subsidised bidding and unit commitment, none of
   which exist in a linear model without unit commitment. **Eight documented
   attempts to fix it all failed**, and they are listed in `CONTINUATION.md`. Do
   not attempt a ninth from the dispatch side, and never tune the model to hit the
   observed 0.784.
3. **Raw results are the headline, the bias correction is a refinement.** The
   frozen-grid system model produces most of the cannibalisation on its own. The
   correction's slope rests heavily on DK2, so leading with the raw figure keeps
   the conclusion off the shakiest assumption. Where a single number is needed, the
   figure of record is **0.47**.
4. **`0_README/0_READ_THIS_FIRST.md` contains superseded numbers.** It was written
   before Finland was removed and still quotes 0.36 to 0.50 corrected and 0.46 to
   0.57 raw. It is kept because its explanations of method are the best in the
   project. Use the thesis and the result tables for numbers, and that document for
   understanding.
5. **`9_Thesis_LaTeX/` is one revision behind `thesis/Thesis_Bindakhil_2026_final.pdf`.**
   The final cuts were made in Overleaf. The PDF is authoritative.
6. **Some script numbers are used twice.** There are two `3.02` scripts, one in
   `3_Comparison/` and one in `3_Comparison/scripts/`, and two `7.42` scripts in
   `7_Thesis_Figures/`. In both cases they do different things, so check the full
   filename rather than the number.
7. **Zone codes are inconsistent across files.** `features_monthly.csv` uses
   `DK1`/`DK2`, `monthly_cv_per_farm.csv` uses `DK_1`/`DK_2`, and observed prices
   use `DELU` for Germany. A careless merge silently drops rows. Both comparison
   scripts assert zone coverage; keep that habit.
8. **The seven features are named `feature_1_Corr_VRE` through
   `feature_7_Interconnection_Index`** in the panel, and the scripts expect exactly
   those strings.
9. **Any figure showing "the" North Sea or Baltic number must use the central
   National Trends scenario**, never the pooled average across scenarios. Mixing
   the two once put 0.61 on a figure while the text said 0.57.
10. **Re-quantise figures after regenerating them.** PNGs are palette-quantised to
    keep the thesis PDF under control. Regenerating without re-quantising doubles
    the file size. Quantise, never resize: resampling adds anti-aliasing colours
    and makes PNGs larger.
11. **ENTSO-E under-reports Dutch renewable generation.** Script `2.04` rescales it
    to physical capacity factors. This is a known upstream data defect.

---

## Where the numbers of record live

| Result | File |
|---|---|
| Capture value by basin, today's grid and expanded, 2030 and 2040 | `7_Thesis_Figures/results/grid_reversal_table.csv` |
| Buildout against congestion decomposition | `7_Thesis_Figures/results/cv_decomposition_table.csv` |
| Capture value per zone, every scenario and horizon | `1_PyPSA_Model/results/projections_v3/projected_capture_values.csv` |
| Bias correction fit and its diagnostics | `1_PyPSA_Model/results/projections_v3/fit_metadata.txt` |
| Regression fit metrics, all five algorithms | `2_Regression_Model/results/01_model_fit_and_validation/regression_metrics.csv` |
| Three-way comparison against observed prices | `3_Comparison/results/01_validation_triangle_2023/` |
| Value-adjusted cost, net value, site ranking, diversification | `7_Thesis_Figures/results/vlcoe_summary.csv`, `netvalue_summary.csv`, `site_ranking.csv` |
| Who bears the loss, and congestion income | `7_Thesis_Figures/results/whopays_decomposition.csv`, `congestion_rent_financing.csv` |
| Transmission the least-cost grid builds, by scope | `7_Thesis_Figures/results/tab_grid_expansion.csv` |
| The 31-farm registry | `2_Regression_Model/data/wind_farms_strandA.csv` |

---

## Citation

> Bindakhil, F. (2026). *Modelling Wind Energy Potentials and Energy Pricing
> Between the North and Baltic Seas.* MSc thesis, Energy Futures Lab, Imperial
> College London.

This work builds directly on two earlier Imperial MSc theses: Paul Jacquet's
(2024) comparison of the North Sea with the French Mediterranean, whose
virtual-wind-farm and regression design it follows, and Lina Efthymiadou's (2025)
work on UK price volatility, whose interconnection metric it adopts. Neither
thesis is included here, since they are the authors' own to share.

## Licence

Code is MIT (`LICENSE`). Data, results, figures and documents are CC BY 4.0
(`LICENSE-DATA.md`), which also lists every upstream data source and what was
deliberately left out of this repository, including one confidential commercial
report used only as an external benchmark.
