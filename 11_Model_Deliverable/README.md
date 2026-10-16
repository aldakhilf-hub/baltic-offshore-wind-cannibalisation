# Baltic Offshore-Wind Capture-Value Model

A fast, runnable model of offshore-wind **capture value** and **wholesale price**
across the North and Baltic Seas. You give it a build-out and fuel scenario; it
returns the answer for every zone in milliseconds. No Gurobi licence, no
market-data credentials, no multi-hour solve.

Faisal Bindakhil, MSc Sustainable Energy Futures, Imperial College London.

---

## What this is (and what it is not)

This is an **XGBoost emulator of the validated PyPSA-Eur power-system model**. The
full PyPSA model simulates the whole European grid hour by hour and takes minutes
to hours per scenario, needs a commercial Gurobi licence, and is not portable.
This emulator was trained to reproduce its capture-value and price outputs from
**76 PyPSA-Eur solves**, so it gives the same answers instantly and runs anywhere.

> Capture value (CV) is the average price a wind farm earns divided by the
> time-average price. CV = 1 means it earns the average; CV < 1 means it earns
> less because it sells when all the other wind is also selling and the price is
> low. That erosion is **cannibalisation**, and the thesis question is how much
> harder it bites in the small, enclosed Baltic than in the open North Sea.

Use it for **sensitivity sweeps, response surfaces and uncertainty fans**. For an
exact canonical point estimate, use the direct PyPSA solve (see accuracy below).

---

## Quick start

```bash
# 1. Install dependencies (one time).
pip install -r requirements.txt
# macOS only, if xgboost fails to load: brew install libomp

# 2. Run the guided tour.
python run_example.py
```

That prints the four things the model does and saves results to
`example_outputs/`. Then open `run_example.py`, change the numbers, and re-run.

To use it in your own code:

```python
import baltic_wind_model as m

# Per-zone capture value and price for one scenario:
print(m.predict(baltic_offshore_gw=80, gas=30, year=2040))

# The headline numbers for one scenario:
h = m.headline(baltic_offshore_gw=80)
print(h["enclosed_baltic_cv"], h["core_north_sea_cv"], h["asymmetry_ns_over_baltic"])
```

---

## Inputs (the levers you set)

Nine scenario inputs. Defaults are the thesis 2040 high-build-out scenario, so
calling `predict()` with no arguments reproduces that case.

| Argument | Meaning | Unit | Trained range | Default |
|---|---|---|---|---|
| `gas` | gas price | EUR/MWh thermal | 15 to 100 | 20.3 |
| `co2` | carbon price | EUR/tCO2 | 50 to 200 | 147 |
| `demand_multiplier` | electricity demand vs 2019 | ratio | 1.0 to 2.0 | 1.50 |
| `baltic_offshore_gw` | Baltic offshore wind installed | GW | 10 to 150 | 60 |
| `ns_offshore_gw` | North Sea offshore wind installed | GW | 30 to 450 | 307 |
| `solar_gw` | solar installed (14 countries) | GW | 200 to 1050 | 742 |
| `battery_gw` | battery power installed | GW | 50 to 400 | 160 |
| `h2_gw` | hydrogen electrolyser power | GW | 30 to 200 | 101 |
| `year` | projection year | 2030 or 2040 | 2030 to 2040 | 2040 |

Inputs outside the trained range still return a number but raise a warning: the
emulator extrapolates poorly beyond the range it learned, so treat those as
indicative only. Pass `warn=False` to silence the warning in sweeps.

---

## Outputs (what it returns)

`predict(...)` returns one row per zone:

| Column | Meaning |
|---|---|
| `zone` | the bidding zone |
| `capture_value` | offshore-wind capture value (0 to 1, the headline metric) |
| `wholesale_price_eur_mwh` | mean annual wholesale price |
| `group` | zone grouping (see below) |

`headline(...)` collapses that to three numbers: the enclosed-Baltic mean CV, the
core-North-Sea mean CV, and the cannibalisation asymmetry (NS / Baltic).

**Zone groups.** The 15 zones are grouped for the headline:
- `enclosed_baltic` = PL, FI, EE, LV, LT (the headline cannibalisation basin)
- `core_north_sea` = DE, NL, BE, DK1 (the validated North Sea zones)
- `model_limitation` = GB, NO (GB structurally under-priced, NO hydro constrained
  at this resolution; reported but excluded from the headline aggregates)
- `other` = DK2, SE, FR, IE (emitted for context; DK2 is the Baltic-facing
  transition zone used to validate the model)

---

## The headline result, reproduced live

Run the Baltic build-out sweep in `run_example.py` and you see the whole thesis in
one table: push Baltic offshore from 10 to 150 GW and its capture value collapses
while the North Sea barely moves.

| Baltic GW | Baltic CV | North Sea CV | Asymmetry |
|---|---|---|---|
| 10 | 0.65 | 0.66 | 1.02x |
| 40 | 0.45 | 0.60 | 1.34x |
| 80 | 0.30 | 0.60 | 2.04x |
| 150 | 0.24 | 0.61 | 2.53x |

The gas-price sweep shows the companion finding: gas is second-order. Swing it
across its whole range and Baltic CV moves by under 0.03. Build-out, not fuel,
drives Baltic cannibalisation.

---

## Accuracy and honest limits

Validated on held-out PyPSA scenarios (the emulator was never trained on the test
scenario):

| Target | R-squared | Mean absolute error |
|---|---|---|
| Capture value | 0.86 | 0.068 CV |
| Wholesale price | 0.92 | 45 EUR/MWh |

- **Canonical 2040 scenarios** are reproduced to within 0.004 to 0.017 CV.
- **The two 2030 scenarios** are the weakest points (off by 0.05 to 0.08 CV).
  Quote the emulator for sensitivity exploration; quote the direct PyPSA solves
  for exact 2030 point estimates.
- **Extreme build-out corners** (well above 100 GW Baltic) lean slightly
  optimistic, because some training runs were solved at coarser time resolution
  which smooths the windiest, lowest-price hours.
- The Baltic zones already carry the **validated PyPSA bias correction** (PyPSA
  over-states Baltic capture value; the correction is baked into the model's
  training target). North Sea zones are left raw, where PyPSA is accurate.

---

## Files

| File | What it is |
|---|---|
| `baltic_wind_model.py` | the model: `predict()` and `headline()` |
| `run_example.py` | the guided tour (run this first) |
| `model/surrogate_cv.json` | trained capture-value emulator (XGBoost) |
| `model/surrogate_price.json` | trained wholesale-price emulator (XGBoost) |
| `requirements.txt` | dependencies |
| `example_outputs/` | what `run_example.py` produces |

## Provenance

This emulator is Track 1, scripts 1.12 to 1.15, of the thesis project. It was
trained on the post-audit re-solved PyPSA-Eur networks (2026). The source
training data, design and validation figures live in the full project under
`1_PyPSA_Model/results/surrogate/`.
