> ## Note added when this repository was published
>
> **Use this document for its explanations and take every number from the
> thesis instead.** It was
> written while the work was in progress and last revised in mid-June 2026. Two
> things changed afterwards and are not reflected below.
>
> 1. **Finland was removed from every Baltic aggregate.** It barely builds
>    offshore, so it never cannibalises, and its nuclear-driven prices pulled the
>    Baltic mean up and masked the wind effect. "Baltic" now means Poland,
>    Estonia, Latvia and Lithuania.
> 2. **The headline numbers moved.** Where this document says 2040 Baltic capture
>    value is 0.46 to 0.57 raw and 0.36 to 0.50 corrected, the final figures are
>    **0.471 on today's grid and 0.664 with the least-cost grid built**, against
>    **0.573 and 0.637** for the North Sea. The single figure of record is
>    **0.47**.
>
> The method explanations, the validation story, the division of labour between
> the two models and the limitations are all still accurate and are the clearest
> write-up of them anywhere in the project. For numbers, use the thesis in
> `thesis/` or the result tables listed in the top-level `README.md`.

---

# 0 · READ THIS FIRST — The Complete Guide to This Thesis Project

**Modelling Wind Energy Potentials and Energy Pricing Between the Northern and Baltic Sea**
Faisal Bindakhil · MSc Sustainable Energy Futures · Imperial College London

> **Purpose of this document.** A single, ordered walkthrough of *everything* in this
> project — assuming you know nothing about the topic — so you can understand every
> decision and write the thesis from it. Read it top to bottom. It points you to the
> three numbered folders for the technical detail; you do not need anything else.

---
## How this project is organised (the numbering)

Read in number order. Top-level docs and folders are numbered by *reading order*;
scripts inside each track are numbered `track.step` (e.g. `2.06` = Regression track,
step 6).

```
Faisal's Thesis/
├── 0_READ_THIS_FIRST.md      ← you are here (the whole story)
├── 1_PyPSA_Model/            TRACK 1: the engineering / simulation model
│   ├── README.md             technical reference for this track
│   ├── scripts/  1.01 … 1.18 run in order (+ run_week1_refresh.sh = whole chain)
│   ├── configs/  data/  results/
├── 2_Regression_Model/       TRACK 2: the empirical / statistical model
│   ├── README.md
│   ├── scripts/  2.01 … 2.13
│   └── data/  results/
├── 3_Comparison/             TRACK 3: putting the two models against reality
    ├── README.md
    ├── 3.01_compare_three_way.py
    └── results/
└── 7_Thesis_Figures/         thesis-level figures mapped to the research questions
```

Inside each track, `scripts/` is the code (numbered = run order), `data/` is what the
code reads, `results/` is what it writes (tables + figures — these are your thesis
figures). The big solved simulation files live outside the project at `~/pypsa-eur/`.

---

## 1 · What question are we answering, and why?

**Plain-English question:** if Europe builds lots of offshore wind in the **Baltic Sea**,
what happens to electricity prices and to how much money that wind actually earns —
and how does that compare to building it in the **North Sea**?

**Why it matters — two ideas you must understand first:**

- **Capture value (CV).** Wind farms don't sell at the average electricity price. They
  sell *when the wind blows* — and that's exactly when lots of other wind is also
  selling, pushing the price down. So wind earns *less* than the average price. We
  measure this with the **capture value**: the average price a wind farm actually
  captures, divided by the time-average price. **CV = 1** means it earns the average;
  **CV < 1** means it earns less. Today most offshore wind has CV ≈ 0.85–0.90.

- **Cannibalisation.** As you build *more* wind, all the wind in a region produces at
  the same windy hours, crashing the price in those hours. Wind "eats its own lunch."
  The more wind, the lower the capture value. This is the central risk for offshore-wind
  investment, and the core subject of this thesis.

**The thesis contribution:** the Baltic Sea is about to be built out massively, but it's
a *smaller, more enclosed, less interconnected* sea than the North Sea. Does that make
Baltic wind cannibalise *harder*? We answer this **two completely independent ways** and
compare them. Agreement between the two methods = confidence; disagreement = a finding.

This builds directly on **Paul Jacquet's 2024 Imperial MSc thesis** (North Sea vs French
Mediterranean) — we reuse his method and swap the Mediterranean for the Baltic — and
borrows interconnection metrics from **Lina Efthymiadou (2025)**.

---

## 2 · The two methods (why there are two tracks)

| | **Track 1 — PyPSA** (`1_PyPSA_Model/`) | **Track 2 — Regression** (`2_Regression_Model/`) |
|---|---|---|
| Type | Engineering simulation of the whole power system | Statistical model learned from history |
| Prices come from | The model optimises generation → "shadow prices" | Real observed market prices |
| Strength | Can simulate *futures that have never happened* (huge Baltic buildout) | Anchored on reality; explains *why* CV varies |
| Weakness | Shadow prices aren't exactly real prices (must be validated) | Can't reliably predict conditions far outside history |

**Track 3 (`3_Comparison/`)** puts both models' answers next to the **real observed**
capture value, wherever we have ground truth. This three-way comparison is the headline
deliverable, and it's the comparison the supervisor explicitly asked for.

**The division of labour that emerged** (a key result in itself): the regression is
excellent at *explaining* capture value where data exists, but **cannot extrapolate** to
the unprecedented Baltic buildout; PyPSA *can* simulate that buildout. So the regression
validates the present, PyPSA projects the future.

---

## 3 · TRACK 1 — PyPSA (the simulation model)

**What it is:** PyPSA-Eur is an open-source model of the entire European power system. It
decides, hour by hour, the cheapest way to meet demand given every power plant, wind
farm, and transmission line — and the "shadow price" it produces is the model's estimate
of the wholesale electricity price. We configured it for the 14 countries around the
North + Baltic Seas. *Full script-by-script detail: `1_PyPSA_Model/README.md`.*

**The steps (scripts `1.01`–`1.16`), in plain language (surrogate = 1.12–1.16):**

1. **Build + run the model** (`1.01`, `1.02`) — pull real prices, run the simulation for
   2019 and 2023.
2. **Check it's realistic** (`1.03`, `1.04`, `1.05`) — compare simulated prices and
   capture values against what *actually* happened. **This is the crucial validation.**
3. **Project the future** (`1.06`–`1.08`) — overlay 2030/2040 build-out plans (from
   TYNDP, the official European grid scenarios) and re-run, with four real-world
   corrections: coal phase-out, offshore-capacity caps, splitting Denmark into its two
   price zones, and a hydrogen "price floor" so 2040 prices don't crash to zero.
4. **Bias-correct** (`1.09`) — use the validation to correct the projection (see below).
5. **Gas-shock sensitivity** (`1.10`, `1.11`) — the supervisor's "adaptable to gas shocks"
   request: re-run everything across a grid of gas prices.

**Key validation result (the one to trust most)** *(numbers updated 2026-06-11)*:
PyPSA reproduces the *real* capture value almost perfectly in big, well-connected
North Sea zones (Germany 2023: model 0.908 vs reality 0.909). But it **over-states**
capture value (i.e. *under*-states cannibalisation) in small, congested,
Baltic-facing zones — worst in Danish zone **DK2: model 0.927 vs reality 0.784**
(bias +0.143), with the error growing monotonically in congestion exposure
(DE ≈0 → BE +0.03 → DK1 +0.06 → DK2 +0.14). The cause is that the model's prices
are "too flat" in windy hours there. **Why this is good news, not bad:** DK2 is the
closest existing look-alike for the future Baltic zones, so the model is *optimistic*
about the Baltic — our projected cannibalisation is a *conservative* estimate.
We turn this into a correction: `1.09` fits `bias = +0.004 + 0.233 × penetration`
on the model's own penetration axis (R² = 0.47, n = 14 across 2019/2023/2024;
slope 95% CI [0.08, 0.39], strictly positive; leave-one-out slope [0.19, 0.27]),
applies it CLAMPED to the validated range, and carries the CI through to the
corrected values. The correction is now a small refinement, not the main effect —
the frozen-grid model produces most of the cannibalisation endogenously.

**Headline PyPSA results** *(updated 2026-06-11)*:
- Baltic build-out depresses Baltic wholesale prices several times harder than the
  North Sea (recompute the exact ratio from the re-solved networks before quoting).
- Bias-corrected Baltic **capture value: 0.75–0.77 (2030) → 0.36–0.50 (2040)**
  with 95% CI bands of roughly ±0.02–0.04 (raw model: 0.82–0.83 → 0.46–0.57).
  Robust: the qualitative finding survived a full audit, re-solve, every
  correction, and a third validation year — severity stable, bands tightened.

**Gas-shock finding (`1.10`–`1.11`)** *(updated 2026-06-11)*: the effect of a
gas-price spike on capture value is *modest* everywhere. In **2030 the North Sea is
~10× more gas-exposed than the Baltic** (gas sets the price more often in the
thermal-heavy, interconnected North Sea; the Baltic is already nearly decoupled);
by **2040 BOTH basins largely decouple from gas** (prices set by wind, hydro, the
DSR tier and the hydrogen floor). The ratios are now computed and printed by `1.11`
— never assert them from memory. GB and NO are documented model-limitation zones
excluded from the headline aggregates (`HEADLINE_EXCLUDE`). *Note in your write-up:*
an early look at only a few zones suggested gas-sensitivity rose with penetration —
checking **all** zones overturned that, a lesson about aggregation hiding the truth.

---

## 4 · TRACK 2 — Regression (the empirical model, replicating Paul Jacquet)

**What it is:** instead of simulating the system, we *learn* the relationship between
capture value and the market conditions from 8 years of real data, then predict. This is
the lit-review-committed contribution ("Gap 3"). *Full detail: `2_Regression_Model/README.md`.*

**The steps (scripts `2.01`–`2.10`), in plain language:**

1. **Pull the data** (`2.01`) — 8 years (2017–2024) of prices, demand, generation and
   cross-border flows for every relevant zone, from ENTSO-E (Europe's grid-data platform).
2. **Build a "Virtual Wind Farm"** (`2.02`) — Paul's trick: we don't have each farm's real
   output, so we *simulate* it from weather. We take ERA5 reanalysis wind speed at the
   farm's location, extrapolate it up to the 150 m turbine hub height, and run it through
   a standard 15-MW turbine power curve (with Paul's "Hayes" smoothing corrections). This
   gives a synthetic hourly output for all 31 farms (real *and* planned).
3. **Compute capture value** (`2.03`) — multiply that output by the local price, monthly,
   for each farm → the thing we want to predict.
4. **Build the features** (`2.04`, `2.05`) — Paul's 7 "explanatory variables" for each
   farm-month: correlation of the farm with system wind, with demand, the renewable
   penetration, gas price, carbon price, a flexibility index, and an interconnection index.
5. **Fit the model** (`2.06`) — train machine-learning models (XGBoost is best) to predict
   capture value from the 7 features. We dont have to train different machine learnign models since paul did 
   that already and found this is the best one. Maybe we can elaborate on why.
6. **Project** (`2.07`) — apply the trained model to 2030/2040 conditions for planned farms. How should we do this?? .
7. **Explain it** (`2.08`) — SHAP analysis: decompose *which* market parameter drives
   capture value and by how much. **This is the scientific payoff.**

**Data set:** a bidding-zone market panel of 31 sites (16 North Sea + 15 Baltic across
7 enclosed zones), **2,706 zone-months**, all 7 features complete.

**Key fit result and how to read the R² (important for the viva):**
- On **Paul's own validation method** (random cross-validation) we get **R² = 0.752**,
  right next to his untuned 0.82. *Our model is competitive.*
- On a *harder* test (predicting completely unseen farms, leave-farm-out) it is **0.686**:
  the lower number you will see quoted is just a tougher test, not a worse model.
- On a **time test** (train on 2017–22, predict 2023–24) it **fails** (negative R²). The
  model does **not** generalise across time. This is the strict reason it cannot forecast
  the future on its own, and exactly why PyPSA exists for projections. State it plainly;
  it is a strength of the two-track design, not a weakness to hide.
- Algorithm ranking matches Paul: on the leave-farm-out test XGBoost 0.686 > RandomForest
  0.636 > SVR 0.497 > polynomial/OLS.

**Key explanatory result (SHAP, `2.08`) — the mechanism, your Gap-3 deliverable:**
Share of capture-value variation explained by each driver, with direction:

| Driver | Share | Effect on capture value |
|---|---|---|
| Carbon price | 27% | higher → **lower** CV |
| Corr. with system wind | 15% | higher → **lower** CV (core cannibalisation) |
| Interconnection | 14% | higher → **higher** CV (exports absorb surplus) |
| Gas price | 14% | mixed/small |
| Penetration (VRE share) | 13% | higher → **lower** CV (cannibalisation) |
| Corr. with demand | 12% | higher → **higher** CV |
| Flexibility | 4% | small |

Every direction matches cannibalisation theory. See `fig_shap_beeswarm.png` — a
viva-ready figure. We also produced a closed-form **analytical equation** (`2.08` →
`analytical_polynomial.txt`) as an interpretable, extrapolatable backup model.

**The projection limit (`2.07`) — a genuine finding:** the regression's planned Baltic
farms have penetrations far beyond anything in the training data (export hubs exceed
100%). XGBoost *flat-lines* there (it can't extrapolate). So the regression **abstains**
from the high-penetration Baltic and PyPSA carries it.

---

## 5 · TRACK 3 — The three-way comparison (the headline deliverable)

`3_Comparison/3.01_compare_three_way.py` puts **Observed vs PyPSA vs Regression** side by
side. *Detail: `3_Comparison/README.md`.*

**Part 1 — validation (2023, where real data exists)** *(updated 2026-06-11; the
regression column is now the GroupKFold OUT-OF-FOLD prediction — the model never saw
the zone's farms — so the three estimates are genuinely independent):*

| Zone | Observed | PyPSA | Regression (OOF) |
|---|---|---|---|
| DE | 0.909 | 0.908 | 0.913 |
| NL | 0.881 | 0.883 | 0.887 |
| BE | 0.869 | 0.896 | 0.879 |
| DK1 | 0.854 | 0.917 | 0.861 |
| **DK2** | **0.784** | **0.927** | **0.798** |

**The finding (15 zone-years, panel since 2026-06-15):** the out-of-fold regression error is
≤0.014 in 2023, ≤0.024 in 2024, ≤0.025 in 2019; PyPSA's error *grows with
cannibalisation exposure*, peaking at +0.143 (2023) and +0.141 (2024) in DK2, where
the regression, predicting zones it never saw, lands within 0.014 and 0.006. Two
independent methods agree, in three separate years, that PyPSA over-states capture
value in Baltic-like zones, corroborating the bias correction. Out of fold 
a machine learning technique where predictions are generated for each data point in a training dataset 
by a model that was never trained on that specific data point. It is a method of evaluating how well a 
model will perform on entirely new, unseen data. 

**Part 2 — projection (no observed data)** *(updated 2026-06-12)*: PyPSA's
bias-corrected Baltic capture value falls to 0.36–0.50 by 2040 (95% CI ≈ ±0.03–0.04).
The regression formally abstains from ALL future projections under the strict
all-features range check (every TYNDP scenario exceeds its training carbon range,
and the carbon-clamp sensitivity proves XGBoost flat-lines there).
**PyPSA carries the Baltic projection — by demonstrated necessity, not choice.**

---

## 6 · The headline findings (for the thesis)

*(updated 2026-06-11 — quote these, not the pre-audit versions)*

1. **Baltic offshore wind value erodes far harder than North Sea value as the basin
   builds out**: corrected Baltic CV falls from ~0.75–0.77 (2030) to ~0.36–0.50 (2040)
   with tight 95% CI bands (±0.02–0.04) — because the basin is smaller, more enclosed
   and less interconnected. Robust across both methods, a full audit and re-solve,
   every correction, and a third validation year (the frozen-grid model produces the
   effect endogenously; grid bracket 0.42–0.65 under optimal expansion).
2. **Capture value validation:** PyPSA matches reality in big NS zones (DE −0.001);
   over-states it in small Baltic-like zones with a monotone congestion pattern
   (DK2 +0.143) — quantified, corrected with a clamped fit + CI, and corroborated
   out-of-fold by the regression.
3. **The regression explains the mechanism** (SHAP): carbon price, correlation-with-
   system-wind and penetration are the dominant cannibalisation drivers;
   interconnection mitigates.
4. **Gas shocks** are second-order relative to buildout: NS ~10× more exposed than the
   Baltic in 2030; both basins largely decouple by 2040.
5. **Methodological:** the regression is competitive with Paul (R² 0.752 on his
   protocol; 0.686 leave-farm-out) but provably cannot extrapolate: negative
   time-split R², and every TYNDP projection leaves its carbon training range, where
   XGBoost demonstrably flat-lines. The two-track design is essential, not optional.

---

## 7 · Honest limitations (put these in the thesis)

- **Regression is ~half "time-following":** 47% of capture-value variation is a common
  time signal (mostly the 2021–22 fuel crisis); only 19% is stable farm-to-farm
  difference. The cross-sectional skill — what we most want — is the weaker half.
- **Regression cannot extrapolate** to high-penetration Baltic or future years.
- **Thin Baltic training data:** most true Baltic-state farms are still *planned*, so the
  model learns the Baltic largely by extrapolation.
- **Everything is country-resolution** (penetration, interconnection are national), so
  within-country differences come only from the wind/weather features.
- **PyPSA** *(updated 2026-06-11)*: Great Britain structurally under-priced (and absent
  from post-Brexit data) and Norway internally grid/power-constrained at 3-cluster
  resolution — both are documented model-limitation zones excluded from headline
  aggregates. The hydrogen floor and the DSR tier are simple parametric stand-ins for
  full sector coupling / TYNDP's flexibility portfolio; residual unserved energy
  (~0.04–0.05% of demand, priced at the 4,000 EUR/MWh cap) remains in stressed 2040
  scenarios — report shed volumes per scenario. The frozen-grid (v1.0) assumption is
  conservative for 2040; the pre-fix optimal-expansion (vopt) networks are preserved in
  `_backup_vopt_2026-06-11/` and bracket the truth from the optimistic side. The bias
  correction is fitted on 9 points with a wide slope CI — it is now clamped, banded,
  and a refinement rather than the main effect. PyPSA's raw capacity factors run high
  vs observed (no wake/availability losses) — handled by fitting bias on the model's
  own penetration axis.
- **Data fix applied:** ENTSO-E under-reported Dutch (NL) renewable generation (the same
  bug Paul documented) — we rescaled it to physical capacity factors (`2.04`). One planned
  farm (Saare-Liiv) sits on a coastal grid cell.

---

## 8 · Current state & what's next (for the next working session)

**Done and reproducible** *(updated 2026-06-11)*: both models built + validated,
three-way comparison (out-of-fold), gas-shock sensitivity (complete 15-cell grid),
the surrogate emulator (1.12–1.15), a full data-integrity pass, the SHAP mechanism
decomposition + analytical model — and a complete forensic audit + fix + re-solve of
the entire PyPSA track (see the 2026-06-11 update block at the top and
`6_REVIEW_FINDINGS_2026-06-10.md`). The whole chain re-runs end-to-end via
`1_PyPSA_Model/scripts/run_week1_refresh.sh` (~3 h wall-clock; solves are ~5× faster
since the solver-parity fix). All results are in the three `results/` folders.

**Not yet done (next session = more modelling refinement, per your plan):**
- **A.** Reduce the regression's time-following (zone-resolved fuel signals / year effects).
- **B.** Make projections extrapolate sensibly (a monotone CV–penetration form, or formally
  hand off to PyPSA above a penetration threshold).
- **C.** Sub-zonal features (penetration/interconnection below country level).
- **D.** Widen the Baltic training base. **E.** Energy-weight the comparison.
- **F.** Harmonise the regression and PyPSA scenarios for a like-for-like projection.

*(Writing the thesis is intentionally deferred — but the spine above plus the `results/`
figures are everything you need when you start.)*

**Surrogate (built, refreshed 2026-06-11):** the third methodological layer — a
**PyPSA surrogate emulator** (XGBoost over harvested canonical/gas-shock runs + 50
LHS-designed 3-hourly solves; scripts `1.12`–`1.15`, results in
`1_PyPSA_Model/results/surrogate/`) — exists and was retrained on the post-fix
networks. Check `surrogate_metrics.csv` for current grouped-CV R² and the anchor
check before quoting; the price emulator is weak — quote the CV emulator only.
`4_PLAN_Surrogate_Model.md` is the original design document (historical).

---

## 9 · How to reproduce (environment + run order)

Everything runs in the conda env `pypsa-eur-arm64` (PyPSA 1.2, Gurobi, xgboost, shap…).
Run scripts in number order within each track. **Each track's `README.md` has the exact
commands.** Quick map:

- **Track 1:** `1.01`→`1.05` (validate) → `1.06`→`1.09` (project) → `1.10`–`1.11` (gas shock) → `1.12`–`1.16` (surrogate). Or all at once: `scripts/run_week1_refresh.sh` (~3 h).
  The simulation solves (`1.02`, `1.07`, `1.10`) are heavy (minutes–hours, Gurobi).
- **Track 2:** `2.01` (+`--zones-only`)→`2.05` (data → features) → `2.06` (fit) → `2.07` (project) → `2.08`–`2.10`
  (explain). Light except the one-off ENTSO-E/ERA5 pulls.
- **Track 3:** `3.01` (reads both tracks' results; instant).

Credentials needed: ENTSO-E (`~/.entsoerc`), Gurobi licence (`~/gurobi.lic`); ERA5 via the
free Open-Meteo API (no key).

---

*This is the canonical project document. Each track's `README.md` holds the technical
script-by-script reference. Last updated 2026-06-11 (post-audit re-solve).*
