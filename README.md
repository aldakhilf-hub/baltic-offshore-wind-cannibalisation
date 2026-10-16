# Offshore wind cannibalisation in the North and Baltic Seas

How much of its market value does offshore wind lose as a sea fills up with wind
farms, and how much of that loss is avoidable? This repository holds the complete
work behind an MSc thesis that answers both questions for the North Sea and the
Baltic Sea: two independent models, the data they were built from, every result
table and figure, and the thesis itself.

**Faisal Bindakhil**, MSc Sustainable Energy Futures, Energy Futures Lab,
Imperial College London, August 2026. Proposed and guided by Dr Ruslan Galimov
(RWE), supervised by Prof Adam Hawkes.

The thesis is in [`thesis/`](thesis/). Read the abstract there first if you want
the argument before the code.

---

## The finding, in one table

A wind farm's **capture value** is the average price it is paid divided by the
average price in its market over the same period. A capture value of 1.0 means it
was paid the market average. A value of 0.5 means it was paid half, because it
sells when every other wind farm is also selling and the price is low. That
erosion is **cannibalisation**.

| | North Sea | Baltic Sea |
|---|---|---|
| Measured today (2023 to 2024) | 0.887 | 0.889 |
| 2040, on today's grid | 0.573 | **0.471** |
| 2040, with the least-cost grid built | 0.637 | **0.664** |

Both seas start level. On today's grid the Baltic loses almost half its value and
falls well below the North Sea. Build the transmission the system model itself
chooses as least-cost, and the Baltic recovers past the North Sea.

The reason is not that Baltic wind is intrinsically worse. Decomposing each
basin's fall separates the part caused by the buildout itself from the part caused
by congestion:

| | Total fall | Buildout | Congestion |
|---|---|---|---|
| North Sea | 0.314 | 0.250 (80%) | 0.064 (20%) |
| Baltic | 0.418 | 0.225 (54%) | 0.193 (46%) |

The Baltic's congestion penalty is three times the North Sea's, while its
buildout-driven fall is actually *smaller*. The extra erosion comes from the
basin being poorly connected to the rest of Europe, and transmission is a thing
that can be built.

Two consequences follow, and both are in the thesis. Learning cannot fix it: the
levelised cost of offshore wind falls from 74 to 66 EUR/MWh while the
**value-adjusted** cost, meaning cost divided by capture value, *rises* from 87 to
121. And the cure pays for itself: congestion income on Baltic-related corridors
runs several times the annualised cost of the lines that would relieve them.

---

## Start here: five minutes to a working model

The fast model needs no licence, no credentials and no conda.

```bash
git clone https://github.com/<your-account>/baltic-offshore-wind-cannibalisation.git
cd baltic-offshore-wind-cannibalisation
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-light.txt
python tools/smoke_test.py
```

`smoke_test.py` checks your install and the bundled data in about ten seconds and
tells you exactly which parts of the stack are missing. Eight checks should pass.
On macOS, if check 2 fails with `libomp.dylib` not loaded, run `brew install
libomp`. That is the single most common setup failure.

Then run the model:

```bash
cd 11_Model_Deliverable
python run_example.py
```

This is an emulator of the full power-system model, trained on 76 of its solves.
You hand it a buildout and fuel scenario, and it returns capture value and
wholesale price for every market zone in milliseconds.

```python
import baltic_wind_model as m

m.headline()                        # the basin-level summary
m.predict(realized_baltic_off=50,   # GW of Baltic offshore
          gas=30, co2=120, year=2040)
```

> **Do not quote the emulator's numbers as the thesis results.** Its capture-value
> training target has the Baltic bias correction already applied, so its default
> Baltic figure is around 0.36 where the thesis headline is 0.47. The emulator is
> for sensitivity sweeps and response surfaces. The numbers of record live in the
> result tables listed further down.

---

## What you can actually run

Being honest about this matters more than making the repository look turnkey.
There are four tiers. The first three run on a laptop with no licence and no
market-data account, because the data they need is bundled here.

| Tier | What it does | Needs | Time |
|---|---|---|---|
| **1. Emulator** `11_Model_Deliverable/` | Capture value and price per zone for any buildout and fuel scenario | `requirements-light.txt` | Milliseconds |
| **2. Regression model** `2_Regression_Model/` | Refit, explain and project the statistical model from the bundled 2,706-month panel | `requirements-light.txt` | Minutes |
| **3. Figures, maps and the value layer** `7_Thesis_Figures/`, `12_Poster/` | Regenerate about 40 figures, the cost field, the value-adjusted cost maps and the site ranking | `environment.yml` plus `tools/setup_pypsa_inputs.py` | Seconds to minutes each |
| **4. Re-solving the system model** `1_PyPSA_Model/` | Re-solve the European power system and regenerate every projection from scratch | Everything above, plus a **Gurobi licence**, a PyPSA-Eur clone and roughly 100GB of weather data | Hours per scenario, 5 to 8 hours for the full chain |

**Tier 3 needs one setup step.** About twenty scripts read three files that
normally come out of a PyPSA-Eur build: the offshore region polygons, the
prepared network and the GEBCO depth grid. Building those yourself means
installing PyPSA-Eur and running its snakemake chain, where the weather cutout
alone takes over four hours. All three are small, so they ship here in
`pypsa_inputs/`. One command puts them where the scripts look:

```bash
mamba env create -f environment.yml
mamba activate baltic-wind
python tools/setup_pypsa_inputs.py          # add --link to save 46MB
```

After that, `python 7_Thesis_Figures/7.18_make_value_heatmaps.py` reproduces the
capture-value maps byte for byte. Nothing is overwritten unless you pass
`--force`, and if you install PyPSA-Eur later the directories merge.

**Eleven scripts still need a solved network** and will fail without tier 4.
They are `7.16`, `7.19`, `7.20`, `7.28`, `7.30`, `7.31`, `7.36`, `7.39`, `7.44`,
and the two in `3_Comparison/scripts/`. Between them they produce the grid
reversal, the buildout-against-congestion decomposition, who bears the loss, the
congestion income and the matched skill scoring. **Their output tables are all
bundled** in `7_Thesis_Figures/results/`, so you can read, plot and build on
every one of those results. You only need tier 4 to recompute them under a
changed model.

**For tier 4 you also need:**

- **PyPSA-Eur** cloned to `~/pypsa-eur` at version `v2026.02.0-39-g23c2fac7`,
  recorded in `environment.lock.yml`. Every Track 1 script expects that
  location. Later versions have moved config keys and will not run these configs
  unchanged.
- **A Gurobi licence** at `~/gurobi.lic`. Free academic licences cover this.
  HiGHS ships with linopy and is open source, but the 30-cluster hourly solves
  were never tested on it.
- **An ENTSO-E Transparency Platform account**, only if you want to re-pull
  market data. The key goes in `~/.entsoerc` as `api_key: <token>`. The pulled
  data is already bundled, so this is optional.

---

## How the repository is laid out

Folders are numbered in reading order. Scripts inside each are numbered in **run
order**, and that numbering is the only orchestration there is. There is no
Makefile and no Snakemake wrapper, so running steps out of order will silently
produce results from stale inputs. Run them in sequence.

```
0_README/              The original orientation document, written as the work
                       progressed, plus the standalone literature review
1_PyPSA_Model/         TRACK 1: the system model. 24 scripts, 1.01 to 1.23
2_Regression_Model/    TRACK 2: the statistical model. 18 scripts, 2.01 to 2.14
3_Comparison/          TRACK 3: both models against observed prices
7_Thesis_Figures/      44 figure and analysis scripts, 7.01 to 7.44
9_Thesis_LaTeX/        Thesis source, figures and bibliography
10_Presentation/       Supervisor deck and the group presentation, with builders
11_Model_Deliverable/  The standalone emulator. Start here
12_Poster/             A1 conference poster and its figure scripts
docs/                  Surrogate design plan, supervisor briefing, the forensic
                       audit of 2026-06-10, the thesis skeleton
pypsa_inputs/          Three small PyPSA-Eur build products the figure scripts
                       need, so you do not have to run its build chain
thesis/                The submitted thesis, 114 pages
tools/                 smoke_test.py, setup_pypsa_inputs.py
```

Each track has its own `README.md` with a script-by-script reference, inputs and
outputs. Those are the detailed documentation; this file is only the front door.

### Run order

```bash
# Track 1, the system model. Heavy. 1.02, 1.07 and 1.10 are the solves.
1.01 pull prices  ->  1.02 solve baseline  ->  1.03-1.05 validate
  ->  1.06-1.08 project to 2030 and 2040  ->  1.09 fit the bias correction
  ->  1.10-1.11 gas shocks  ->  1.12-1.16 build the emulator
  ->  1.17-1.23 sensitivities: scarcity, grid bracket, hydrogen floor,
                network ratings, hydro foresight, must-run heat
# or the whole chain:  bash 1_PyPSA_Model/scripts/run_week1_refresh.sh

# Track 2, the statistical model. Light. Data is bundled, so start at 2.03.
2.01-2.02 pull market and weather data  ->  2.03 capture value per farm
  ->  2.04-2.05 build the seven features  ->  2.06 fit
  ->  2.07 project  ->  2.08-2.14 explain, cluster, analytical forms

# Track 3, both models against reality.
3.01 three-way comparison  ->  3_Comparison/scripts/3.02 matched skill scoring
  ->  3.03 backtest the projection
```

---

## The two models, and why there are two

| | Regression model | System model |
|---|---|---|
| What it is | Gradient-boosted trees (XGBoost) over seven market features | PyPSA-Eur, the European power system solved hour by hour |
| Where prices come from | Observed day-ahead prices, 2017 to 2024 | The shadow price of the nodal energy balance |
| Trained on | 31 farms, 2,706 farm-months, 7 bidding zones with enclosed Baltic prices | Nothing. It is built from plants, costs, demand and network |
| Strength | Anchored on prices that actually occurred, so it absorbs real market behaviour | Can simulate a buildout that has never happened |
| Weakness | Cannot extrapolate beyond the observed record | Simplifications (linear dispatch, no unit commitment, perfect foresight, clustered network) bite hardest in the observed record |

They were scored against each other on identical unseen targets, with the
regression refitted leave-one-zone-out and leave-one-year-out so neither model had
seen the answer. The result is the methodological core of the thesis:

- **Accuracy does not separate them.** Mean absolute error 0.041 against 0.046,
  paired difference not significant.
- **Their errors have opposite signs**, so averaging the two models is wrong and
  handing over from one to the other at a defined point is right.
- **Energy-weighted, they agree to 0.005** (0.890 against 0.885).
- **At 2040 the regression declines to answer.** None of the 36 projection rows
  sit inside its training range, and its response across scenarios spans 0.008
  where the system model spans 0.428. So the system model carries the projection
  by demonstrated necessity.

The boundary between them falls at the edge of the observed record rather than at
any particular number of years, which a 2021 backtest locates: over 2023 to 2024, where 58% of targets are
still inside the training range, the two project equally well.

---

## Things that will trip you up

Read this section before you change anything. Each item cost real time to learn.

1. **Finland is excluded from every Baltic aggregate.** It barely builds offshore,
   so it never cannibalises, and its nuclear-driven prices pulled the Baltic mean
   up and masked the wind effect. "Baltic" means Poland, Estonia, Latvia and
   Lithuania throughout. Per-zone tables still carry Finland, clearly labelled.
2. **DK2 (eastern Denmark) is in no headline aggregate.** It is the built-out
   preview zone. The system model overstates its capture value by about 0.15 and
   this is structural rather than a bug: its observed 264 negative-price hours
   come from must-run heat, sub-zero subsidised bidding and unit commitment, none
   of which exist in a linear model without unit commitment. **Eight documented
   attempts to fix it all failed** and are recorded in `docs/` and the thesis
   appendix. Do not attempt a ninth from the dispatch side, and never tune the
   model to hit the observed 0.784.
3. **Raw results are the headline, the bias correction is a refinement.** The
   frozen-grid system model produces most of the cannibalisation on its own. The
   correction's slope rests heavily on DK2, so leading with the raw figure keeps
   the conclusion off the shakiest assumption. Where a single number is needed,
   the figure of record is **0.47**.
4. **`0_README/0_READ_THIS_FIRST.md` contains superseded numbers.** It was written
   before Finland was removed and still quotes 0.36 to 0.50 corrected and 0.46 to
   0.57 raw. It is kept because its explanations of method are the best in the
   project. Trust the thesis and the result CSVs for numbers, and that document
   for understanding.
5. **`9_Thesis_LaTeX/` is one revision behind `thesis/Thesis_Bindakhil_2026_final.pdf`.**
   The final cuts were made in Overleaf. The PDF is authoritative.
6. **Two different scripts are numbered 3.02**, one in `3_Comparison/` and one in
   `3_Comparison/scripts/`. They do different things. Check the path.
7. **Zone codes are inconsistent across files.** `features_monthly.csv` uses
   `DK1`/`DK2`, `monthly_cv_per_farm.csv` uses `DK_1`/`DK_2`, and observed prices
   use `DELU` for Germany. A careless merge silently drops rows. Both comparison
   scripts now assert zone coverage; keep that habit.
8. **Any figure showing "the" North Sea or Baltic number must use the central
   National Trends scenario**, never the pooled average across scenarios. Mixing
   the two once put 0.61 on a figure while the text said 0.57.
9. **Re-quantise figures after regenerating them.** PNGs are palette-quantised to
   keep the thesis PDF under control. Regenerating without re-quantising doubles
   the file size. Quantise, never resize: resampling adds anti-aliasing colours
   and makes PNGs larger.
10. **ENTSO-E under-reports Dutch renewable generation.** Script `2.04` rescales
    it to physical capacity factors. This is a known upstream data defect.

---

## Where the numbers of record live

| Result | File |
|---|---|
| Capture value by basin, today's grid and expanded, 2030 and 2040 | `7_Thesis_Figures/results/grid_reversal_table.csv` |
| Buildout against congestion decomposition | `7_Thesis_Figures/results/cv_decomposition_table.csv` |
| Capture value per zone, every scenario and horizon | `1_PyPSA_Model/results/projections_v3/projected_capture_values.csv` |
| Bias correction fit and its diagnostics | `1_PyPSA_Model/results/projections_v3/fit_metadata.txt` |
| Regression fit metrics, all five algorithms | `2_Regression_Model/results/01_model_fit_and_validation/` |
| Three-way comparison against observed prices | `3_Comparison/results/01_validation_triangle_2023/` |
| Value-adjusted cost, net value, site ranking, diversification | `7_Thesis_Figures/results/vlcoe_summary.csv`, `netvalue_summary.csv`, `site_ranking.csv` |
| Who bears the loss, and congestion income | `7_Thesis_Figures/results/whopays_decomposition.csv`, `congestion_rent_financing.csv` |
| Transmission the least-cost grid builds, by scope | `7_Thesis_Figures/results/tab_grid_expansion.csv` |
| The 31-farm registry | `2_Regression_Model/data/wind_farms_strandA.csv` |

---

## If you are taking this over

Work through it in this order. Each stage ends with a number you should be able
to reproduce, which is how you know your setup is right before you trust
anything you compute yourself. **Resist starting with the system model.** It is
the tempting thing to open first and it will cost you weeks before you have
learned anything.

### Stage 1, about an hour. Get a model running and read the argument.

```bash
pip install -r requirements-light.txt
python tools/smoke_test.py
python 11_Model_Deliverable/run_example.py
```

Read the thesis abstract and Chapter 1 while that installs. Twenty minutes, and
it tells you what every folder here was for.

**Checkpoint:** the smoke test passes 8 of 8 and prints `North Sea 0.57, Baltic
0.47`, and the emulator returns a capture value for all 15 zones.

### Stage 2, a day. Reproduce the empirical half.

The data is bundled, so you can skip the pulls and start at the fit.

```bash
cd 2_Regression_Model/scripts
python 2.06_fit_regression.py          # fits five algorithms
python 2.08b_demeaned_shap.py          # what actually drives capture value
python 2.07_project_capture_values.py  # and where the model gives up
```

**Checkpoints.** `2.06` should give **0.686** predicting farms it never saw and
**0.752** on the easier random split, with XGBoost ahead of random forest ahead
of support vector regression. `2.08b` should show crowding leading at about 32%
once each farm is compared with the month's average, with carbon collapsing from
29% to 4%. `2.07` should report **0 of 36** projection rows inside the training
range.

That last number is the whole reason this project has two models, so make sure
you understand it before going further. It is not a bug.

### Stage 3, a day. Reproduce the figures and the value layer.

```bash
mamba env create -f environment.yml && mamba activate baltic-wind
python tools/setup_pypsa_inputs.py
python 7_Thesis_Figures/7.18_make_value_heatmaps.py   # the capture-value maps
python 7_Thesis_Figures/7.32_make_site_ranking.py     # does value change where to build
python 7_Thesis_Figures/7.43_make_group_arc_simple.py # the headline figure
```

**Checkpoint:** `7.32` should rank German Bight first on both cost and value at
every horizon, with the correlation between the two rankings falling from 0.99
in 2025 to 0.90 in 2040.

### Stage 4, only when you have a reason. Touch the system model.

Read `docs/6_REVIEW_FINDINGS_2026-06-10.md` first. It is the forensic audit that
found five result-changing defects in this model, and it will teach you more
about the traps than any amount of running it. Then get a Gurobi licence, clone
PyPSA-Eur at the pinned version, and start with `1.02_run_baseline.sh` for a
single year so you can compare against the recorded validation before you try a
scenario.

**Checkpoint:** Germany 2023 should come out at about 0.908 against an observed
0.909. If it does, the chain is sound. If DK2 comes out near 0.93 against an
observed 0.784, that is expected and documented, so read trap 2 above before you
try to fix it.

### Then

`CONTINUATION.md` lists what is unfinished, ranked by payoff, along with what was
already tried and failed. The first two items there, curtailment volume and the
planned-grid case, are both tractable for a single MSc and neither needs the
full chain re-solved.

---

## Citation

> Bindakhil, F. (2026). *Modelling Wind Energy Potentials and Energy Pricing
> Between the North and Baltic Seas.* MSc thesis, Energy Futures Lab, Imperial
> College London.

This work builds directly on two earlier Imperial MSc theses, Paul Jacquet's
(2024) comparison of the North Sea with the French Mediterranean, whose
virtual-wind-farm and regression design it follows, and Lina Efthymiadou's (2025)
work on UK price volatility, whose interconnection metric it adopts. Neither
thesis is included here, since they are the authors' own to share.

## Licence

Code is MIT (`LICENSE`). Data, results, figures and documents are CC BY 4.0
(`LICENSE-DATA.md`), which also lists every upstream data source and what was
deliberately left out of this repository, including one confidential commercial
report used only as an external benchmark.
