# Track 2 · Regression Model: technical reference

Empirical track. Replicate Paul Jacquet's (2024) per-farm capture-value regression
(Virtual Wind Farm -> monthly capture value -> 7-feature model), extended with Lina
Efthymiadou's (2025) interconnection metrics, on a bidding-zone market panel of 31
North-Sea + Baltic sites, **at bidding-zone resolution since 2026-06-11 (lever C),
expanded to a 7-zone enclosed-Baltic price panel 2026-06-15**.

Plain-language story: `../0_README/0_READ_THIS_FIRST.md` § 4 (and its 2026-06-11
update block).

**State (verified 2026-06-15, bidding-zone market panel):** 2,706 zone-months across
31 sites (16 North Sea + 15 Baltic), all 7 features 0-NaN. Capture value is a property
of prices, so the training panel is every site with observed prices, operational or
planned alike; the operational farms remain the validation subset (the only sites where
generation can be checked against metered output). This widens the enclosed Baltic from
one operational price zone (DK2 + one Swedish farm) to seven (DK2, SE4, PL, FI, EE, LV,
LT). XGBoost **R² = 0.752 on Paul's K-fold** (his untuned 0.82), **0.686 leave-farm-out**
(0.598 at country resolution: the lever-C gain), NS->Baltic transfer 0.379, and
**negative on a time split**: projecting futures is the PyPSA track's job, by proof.
Decisive test: 6 of 7 enclosed Baltic zones predicted out-of-fold within 0.07 (only
Finland misses, on nuclear baseload). See `results/01_model_fit_and_validation/enclosed_baltic_oof.csv`.

---

## 1 · Architecture: how the pieces fit together

```
ENTSO-E API                  Open-Meteo (ERA5)            TYNDP (shared parse)
2.01 prices/load/gen/flows   2.02 wind 10m+100m              |
2.05 installed capacity          |                           |
        |                        v                           |
        |                  VIRTUAL WIND FARM (2.02):         |
        |                  log-profile to 150 m,             |
        |                  IEA-15MW curve + Hayes adj.       |
        |                  -> hourly CF per farm             |
        v                        |                           |
   market series                 v                           |
        |             2.03 monthly CV per farm-month  <- prices
        |                        |        (the TARGET)
        v                        v
   2.04 SEVEN FEATURES at market-area resolution
   (zone for DK1/DK2/SE4, country elsewhere)
                |
                v
   2.06 FIT + VALIDATE (5 algorithms, 5 protocols,
        GroupKFold out-of-fold export)
        |               |                |
        v               v                v
   2.08 SHAP       2.07 projection   exports OOF ->  ../3_Comparison
   2.12 analytical      + strict          (the triangle's regression
        per basin       in-range check    column)
   2.11 basin-gap       (abstention)
        decomposition
   2.09/2.10 weather-only corroboration (clusters, synchronicity)
   2.13 VWF vs metered generation (validation of the foundation)
```

Everything downstream of 2.06 reuses its data assembly and model definitions by
import; there is one feature table and one trained model on disk, not several.

## 2 · How the model is trained

- **Target.** Monthly capture value per farm: CV = (sum of hourly CF x price) /
  (CF sum x time-mean price), computed by 2.03 on hours where farm output and zone
  price both exist; months with fewer than 500 overlapping hours are dropped.
  Capacity factors are normalised, so rated MW cancels in the ratio.
- **Sample (bidding-zone market panel).** One row = one zone-month: a virtual offshore
  farm in a zone, described by the seven features and labelled with its monthly capture
  value. By the price-property principle, a zone with observed prices is a valid
  observation whether or not a farm operates there, so all 2,706 rows across 31 sites
  train. The operational farms are the validation subset (metered generation exists
  there); the price-only zones (PL, FI, EE, LV, LT) are anchored on observed prices.
- **Features (2.04).** Paul's seven, each at the farm's market area: Corr_VRE,
  Corr_Load (hourly Pearson correlations of farm output with area renewables and
  load), VRE_MarketShare (monthly renewable energy / consumption), Gas_Price,
  Carbon_Price (monthly averages), Flexibility_Index (storage / VRE capacity),
  Interconnection_Index (realised utilisation: annual mean cross-border flow / border
  capacity, Efthymiadou's form, corrected 2026-06-15 from the earlier capacity-ratio
  form that mis-ranked the basins). Collinearity is clean (low VIF).
- **Lever C (zone resolution).** Features use the bidding zone wherever
  zone-resolved series exist (DK_1, DK_2, SE_4 from `2.01 --zones-only` and 2.05),
  the country elsewhere; a `feature_resolution` column records which. This is the
  structural upgrade over both predecessors: the 7 Danish farms see DK1-vs-DK2
  conditions instead of a national blur.
- **Algorithms (2.06).** Five families, fixed hyperparameters, no tuning (Paul's
  untuned 0.82 is the comparator): XGBoost (n_estimators 400, max_depth 4,
  learning_rate 0.05, subsample 0.8, colsample_bytree 0.8, reg_lambda 1.0),
  RandomForest (300 trees, depth 8), SVR (RBF), ridge-stabilised degree-2
  polynomial, and OLS.
- **Validation protocols (2.06), all scored on out-of-fold predictions.** A
  prediction is out-of-fold when the model that made it never trained on that data
  point. Random K-fold(5) withholds farm-months (leaky for panel data; kept for
  comparability with Paul). **GroupKFold(5) grouped by farm is the headline**: farms
  are partitioned into 5 groups, 5 model copies are trained, each predicts only the
  farms it never saw, and the stitched series (every farm-month predicted exactly
  once, blind) is what the quoted R² is computed on. A chronological split
  (train <=2022, test 2023-24) withholds the future and fails by design. Basin
  transfer (train NS, test Baltic, and the reverse) probes transportability. An
  ex-2022 variant mirrors Paul's crisis-outlier removal.
- **Exports.** `xgb_operational.json` (the trained model 2.07/2.08 reuse) and
  `oof_predictions_groupkfold.csv` (farm, zone, basin, year, month, CV_actual,
  CV_pred_oof): the genuinely blind predictions that 3.01 uses as the triangle's
  regression column.

## 3 · Key definitions

- **Farm-month**: the unit of observation; one farm's capture value in one month.
- **Out-of-fold (OOF)**: see above; the discipline behind every quoted metric.
- **Market area**: the zone the farm sells into where zone data exists, else the
  country; the resolution at which all seven features are computed.
- **Basin labels**: NS vs Baltic per farm registry (`wind_farms_strandA.csv`);
  DK2/SE4 farms are Baltic-facing, which is what makes them the buildout preview.
- **Abstention (2.07)**: a projection is quoted only if every feature lies inside
  the training range; 0/36 TYNDP rows pass (carbon 113-147 vs max 91 EUR/t), the
  carbon-clamp sensitivity proves XGBoost flat-lines beyond support, so the track
  formally hands projection to PyPSA.

## 4 · Script reference (run in order)

| # | Script | Reads | Writes | What it does |
|---|---|---|---|---|
| 2.01 | `pull_entsoe.py` | ENTSO-E API | `data/entsoe_strandA/` | 2017-2024 prices (22 zones), load, generation by type, cross-border flows; `--zones-only` adds DK_1/DK_2/SE_4 series (lever C) |
| 2.02 | `pull_era5_and_vwf.py` | Open-Meteo ERA5 | `data/vwf/hourly_cf_YYYY.csv` | wind at 10/100 m per farm cell -> log-profile to 150 m -> IEA-15MW curve with Hayes adjustments (sigma 1.17, shift 0.71) -> hourly CF per farm |
| 2.03 | `monthly_cv_per_farm.py` | 2.02 + prices | `data/cv_strandA/monthly_cv_per_farm.csv` | the target: monthly CV per farm (>=500 common hours); + Paul Fig 45 replication |
| 2.04 | `build_features.py` | 2.01/2.03/2.05 + external fuel prices | `data/features_strandA/features_monthly.csv` | the 7 features at market-area resolution + `feature_resolution` column |
| 2.05 | `pull_installed_capacity.py` | ENTSO-E API | `data/entsoe_strandA/` | yearly installed capacity per type (countries + DK_1/DK_2): feeds features 6 and 7 |
| 2.06 | `fit_regression.py` | features table | `results/01_model_fit_and_validation/` | 5 algorithms x protocols; exports the trained model + the GroupKFold OOF predictions |
| 2.07 | `project_capture_values.py` | trained model + TYNDP | `results/03_projection_2030_2040/` | planned farms -> 2030/2040 feature vectors; strict all-features `in_range` + carbon-clamp sensitivity -> the formal abstention |
| 2.08 | `mechanism_decomposition.py` | 2.06 data + model | `results/02_capture_value_mechanism_SHAP/` | SHAP shares + directions (the Gap-3 deliverable) + RFE polynomial backup |
| 2.09 | `farm_correlation_clusters.py` | `data/vwf/` | `results/04_farm_correlation_clusters/` | 31x31 hourly-output correlation matrix, hierarchical clusters, cluster map (weather-only corroboration) |
| 2.10 | `farm_pair_synchronicity.py` | `data/vwf/` | `results/05_pair_synchronicity/` | month x hour-of-day correlation heatmaps for chosen farm pairs (Paul Fig 43 analogue); near-neighbour pairs on one ERA5 cell are excluded as misleading |
| 2.11 | `cv_gap_decomposition.py` | 2.06 data + model | `results/06_cv_gap_decomposition/` | SHAP group-difference decomposition of the (Baltic - NS) gap, parity era vs divergence era: interconnection swing + wind-pattern penalty, NOT local penetration |
| 2.12 | `analytical_per_basin.py` | 2.06 data | `results/07_analytical_per_basin/` | Paul's analytical equation refit pooled/NS/Baltic with farm-block bootstrap: alpha 0.74 (Baltic) vs 0.37 (NS), steeper in 99/100 bootstraps; implied slope ~1.6x today, ~1.9x at P90 dominance |
| 2.13 | `vwf_validation.py` | `data/vwf/` + Track 1's cached observed generation | `results/08_vwf_validation/` | VWF vs metered offshore generation, shape test: median hourly r 0.88, monthly 0.95 (a validation neither predecessor ran) |

## 5 · Key results (verified 2026-06-15, bidding-zone market panel)

- **Fit (2.06):** 0.752 random K-fold (Paul protocol) / **0.686 leave-farm-out** /
  0.69 leave-farm-out ex-2022 / 0.379 NS->Baltic / negative time split. Country-level
  baseline preserved (`regression_metrics_v1_country.csv`,
  `features_monthly_v1_country.csv`): the lever-C before/after is itself a thesis
  result (+0.09 R², 0.598 to 0.686, from resolving features where prices form).
- **Panel transfer test (`enclosed_baltic_oof.csv`):** 6 of 7 enclosed Baltic zones
  predicted out-of-fold within 0.07 (PL 0.017, DK2 0.025, EE/LV/LT ~0.03, SE4 0.067;
  only FI misses at 0.10, on nuclear baseload). The mechanism transfers across price
  zones, not a DK2 peculiarity.
- **Triangle (out-of-fold):** every 2023 zone error <=0.014; DK2 +0.014 vs PyPSA's
  +0.143 (regression within 0.014 of DK2 in every validation year).
- **Mechanism (2.08, SHAP):** Carbon 29.0 · Corr_VRE 22.8 · Gas 14.3 · Corr_Load
  10.6 · Penetration 9.5 · Flexibility 7.3 · Interconnection 6.6 (%). Directions
  all match cannibalisation theory. Carbon's share partly proxies the 2021-22 time
  signal; quote alongside the ex-2022 fit.
- **Projection (2.07):** strict in-range **0/36**; the regression abstains and PyPSA
  carries the projection, by proof.

## 6 · Methodology fidelity and data integrity (vs Paul)

Faithful: VWF pipeline, CV formula, features 1-5 + 7. Improvements: GroupKFold
headline, time-split + basin-transfer tests, OOF export, collinearity clean, NL VRE
under-reporting fixed (his documented bug), zone resolution, the bidding-zone market
panel (training every zone with observed prices, which widens the enclosed Baltic from
one operational zone to seven), and the 2.13 VWF validation. Documented deviations:
flexibility
numerator = ENTSO-E pumped hydro (+ battery where reported); Paul's battery/DSR
source is proprietary. 2022 kept (ex-2022 reported separately). No hyperparameter
tuning (his untuned 0.82 is the like-for-like comparator). GB farms contribute no
farm-months after 2020 (post-Brexit price gap).

## 7 · Reproduce

```bash
conda activate pypsa-eur-arm64
cd "2_Regression_Model/scripts"
python 2.01_pull_entsoe.py --start 2017 --end 2024   # cached; ~5 h first time
python 2.01_pull_entsoe.py --zones-only               # lever-C zone series (~25 min)
python 2.02_pull_era5_and_vwf.py --year 2017 --to 2024
python 2.05_pull_installed_capacity.py
python 2.03_monthly_cv_per_farm.py
python 2.04_build_features.py
python 2.06_fit_regression.py
python 2.07_project_capture_values.py
python 2.08_mechanism_decomposition.py
python 2.09_farm_correlation_clusters.py
python 2.10_farm_pair_synchronicity.py
python 2.11_cv_gap_decomposition.py
python 2.12_analytical_per_basin.py
python 2.13_vwf_validation.py    # needs Track 1's cached observed generation (1.04)
```

## 8 · Data folder map

- `wind_farms_strandA.csv`: the 31-farm registry (name, lat/lon, capacity, status,
  country, basin); the single source of farm truth.
- `entsoe_strandA/`: prices, load, generation by type, flows, capacity (2.01/2.05).
- `vwf/`: hourly capacity factor per farm per year (2.02 output).
- `cv_strandA/`: the monthly CV target table (2.03 output).
- `features_strandA/`: the model-ready feature table (2.04 output) + the preserved
  country-resolution v1 for the before/after.
- `external/`: monthly TTF gas and EU ETS carbon price series.
- `tyndp/`: the shared TYNDP parse used by 2.07.
