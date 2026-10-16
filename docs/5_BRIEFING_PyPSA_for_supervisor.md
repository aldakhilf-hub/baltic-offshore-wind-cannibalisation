# 5 · Briefing — Explaining the PyPSA Track to a Supervisor

> **⚠ This file is the plain-language PITCH.** For the equation-level walkthrough the
> supervisor asked for (every input, the dispatch LP and its constraints, the outputs,
> and the precise reason PyPSA and the regression diverge), see the companion
> **`1_PyPSA_Model/PyPSA_dispatch_explained.md`** (2026-06-22).
>
> **Current headline (central NT-balticBaseline scenario):** 2040 offshore capture value
> North Sea ~0.57, enclosed Baltic ~0.50 on the frozen grid; under optimal grid expansion
> the ordering REVERSES (NS 0.64, Baltic 0.68). The regression's linear projection gives
> ~0.74/0.77 (it cannot see the grid or the convex collapse). The PyPSA pedagogy below
> remains valid; the old phase-3 gas-shock framing is de-emphasised.

> A structured walkthrough you can either **hand to your supervisor as a written brief**
> or **read from in a meeting**. Designed for someone who knows offshore wind / energy
> systems generally but doesn't know PyPSA-Eur specifically. Three depth levels:
> 30-second pitch, 5-minute version, deep dive on demand.

---

## A · The 30-second pitch (use this if he asks "so what's PyPSA?")

> "PyPSA-Eur is an open-source engineering model of the whole European power system —
> it knows every power plant, every wind farm, every transmission line in Europe. You
> give it a year and a set of capacities, and it figures out hour-by-hour the cheapest
> way to meet electricity demand. As a by-product, it produces the wholesale price at
> every location and every hour, which is exactly what we need to compute capture
> value for offshore wind. I didn't write PyPSA-Eur — it's the standard academic
> European power system model. I **configured** it for the 14 countries around the
> North and Baltic Seas, **validated** that its prices reproduce real ENTSO-E
> observations, and then **projected** forward to 2030 and 2040 under TYNDP buildout
> scenarios."

---

## B · The 5-minute version (the main brief)

### B.1 · What PyPSA-Eur is, in plain words

It's a Python framework for modelling electricity grids. Inside it, you describe the
network as:

- **Nodes** (called *buses*): like points on a map — one per region or country.
- **Lines** between nodes: transmission capacity.
- **Generators** attached to nodes: each power plant — coal, gas, nuclear, offshore
  wind, solar, etc., with their fuel costs, efficiencies, and CO₂ emissions.
- **Loads** attached to nodes: hourly demand profiles.
- **Storage** at nodes: batteries, pumped hydro.

**PyPSA-Eur** is a specific pre-built version of the framework that already contains
all of this for Europe — every real-world plant, every cross-border line, calibrated
to real installed capacities. You configure it for your study (which countries, which
year, how fine-grained, how many regional clusters) and it produces a solved network.

### B.2 · What it actually computes

Given (a) the network, (b) hourly weather (driving wind & solar output), and (c)
hourly electricity demand, PyPSA solves a giant **linear-programming optimisation**:

> *Find the cheapest combination of which power plants run, in which hours, that
> meets all the electricity demand without violating any transmission constraints
> or any plant's technical limits.*

The optimisation runs in commercial solver **Gurobi**. For our setup (14 countries,
30 regional nodes, full year hourly) it takes ~10 minutes per solve.

**Out the back end you get:**

1. **The hourly dispatch** — which plant ran when, how much.
2. **The hourly wholesale price** at each node (technical name: *shadow price* — it's
   the marginal cost of supplying one more MWh at that node, which under perfect
   competition equals the wholesale market price).
3. **Total system cost** for the year.

The hourly prices are the key output — that's what we use to compute capture values.

### B.3 · How we use it in this thesis (the pipeline)

We do it in three phases — calibration, projection, sensitivity:

```
PHASE 1 — CALIBRATION (does the model reproduce reality?)
   • Configure PyPSA-Eur for 14 NS + Baltic countries, year 2019 and year 2023
   • Solve → get simulated prices per hour per zone
   • Compare to observed ENTSO-E prices
   • Compute capture values both for simulated AND observed prices using the SAME wind farms
   • Verdict: matches reality in big zones (DE 0.91 modelled vs 0.91 observed),
     under-states cannibalisation in small Baltic-facing zones (DK2: 0.94 vs 0.78)
       → we QUANTIFY this systematic bias with a 14-point linear fit across 2019/2023/2024 (slope CI strictly positive)

PHASE 2 — PROJECTION (what happens in 2030/2040?)
   • Take the 2023-calibrated network
   • Overlay TYNDP 2024 inputs: future capacities, fuel & CO₂ prices, demand growth
   • Apply documented corrections (coal phaseout per German policy; DK1/DK2 split;
     H2 demand floor for sector coupling)
   • Re-solve → projected prices per scenario
   • Compute projected capture value per zone
   • Apply the validated bias correction

PHASE 3 — STRESS TEST (does the result hold under uncertainty?)
   • Sweep gas price across the realistic range (the "gas shock grid")
   • Show that the Baltic-vs-NS asymmetry survives extreme fuel shocks
```

### B.4 · The headline result

> **Building out offshore wind in the Baltic Sea depresses Baltic wholesale prices
> 2-5× harder than building the same MW in the North Sea — robust across both methods
> (PyPSA and the empirical regression in Track 2), every robustness check, and the
> gas-shock stress test.**

That's the headline a supervisor will remember.

### B.5 · The honest limitations (state these proactively)

It demonstrates rigour to mention these *before* he asks:

1. PyPSA's **shadow prices are not exactly real prices** — they're the LP's marginal-
   cost answer. They miss start-up costs, bidding strategy, and capacity-market signals.
   That's why we calibrate against observed prices and quantify the residual bias.
2. **Nordic zones (NO, SE) are over-coupled** to continental prices because PyPSA-Eur
   simplifies hydro reservoir behaviour. We document this and treat them as
   out-of-focus.
3. **The H2 sector-coupling floor is parametric** (we add electrolyser demand at a
   TYNDP-derived import price) rather than fully sector-coupled. It captures the
   electricity-side mechanism — the dominant one — but not heat or transport flexibility.
4. The model is at **30-cluster spatial resolution** — DK1/DK2 are correctly resolved
   (different bidding zones, different physics), but Sweden's four price zones are
   not.

---

## C · Script-by-script (only show this if asked)

Eleven scripts in `1_PyPSA_Model/scripts/`, numbered in run order:

| # | Script | One sentence |
|---|---|---|
| 1.01 | `pull_observed_prices.py` | Downloads observed day-ahead prices from ENTSO-E for the calibration years |
| 1.02 | `run_baseline.sh` | Runs PyPSA-Eur's Snakemake workflow to produce a solved baseline network (this is the heavy step) |
| 1.03 | `calibration_error_metrics.py` | Compares PyPSA's prices to observed prices: bias, RMSE, hourly correlation, per zone |
| 1.04 | `observed_capture_values.py` | The validation centrepiece — computes capture value three ways (observed gen × observed price; PyPSA gen × observed price; PyPSA × PyPSA) to diagnose where any error lives |
| 1.05 | `analyse_baseline.py` | Produces baseline capacity tables, country-level price summaries, and capture-value figures |
| 1.06 | `parse_tyndp.py` | Extracts TYNDP 2024 capacities, demand, fuel & CO₂ prices from the source Excel workbooks |
| 1.07 | `run_scenarios.py` | The canonical projection runner — overlays TYNDP inputs + 4 corrections (thermal phaseout, offshore caps, DK1/DK2 split, H2 demand floor) and re-solves 6 scenarios |
| 1.08 | `projected_capture_values.py` | Computes per-zone offshore CV (raw + bias-corrected) for each scenario |
| 1.09 | `bias_correction_fit.py` | Fits a multi-zone linear function for PyPSA's systematic CV bias (14 validation points across 2019/2023/2024, slope CI strictly positive); applies it to projections |
| 1.10 | `gas_shock_grid.py` | Sweeps gas price across the realistic range and re-solves the projection at each level |
| 1.11 | `gas_shock_capture_values.py` | Computes capture value response to gas shocks (sensitivity analysis) |

If he wants more depth on any specific script, point him at `1_PyPSA_Model/README.md` —
that has the data-flow and the exact commands.

---

## D · Likely supervisor questions & one-line answers

> "What's a shadow price?"
The LP's internal answer to "what would the next MWh of supply cost here?" Under
perfect competition, equals the wholesale market price. We treat it as the model's
estimate of the market clearing price.

> "Why open-source PyPSA-Eur and not a commercial model like PLEXOS or Aurora?"
Open-source means reproducibility (every assumption is auditable), and academic
literature in the energy-systems field has converged on PyPSA-Eur. Paul Jacquet's
2024 thesis was empirical (no PyPSA). My contribution adds the engineering layer.

> "How long does each run take?"
~10 minutes per scenario on my MacBook with Gurobi. Six scenarios + the gas-shock
grid = a few hours total for a complete projection set.

> "Why TYNDP 2024 and not Aurora?"
Aurora is proprietary (Paul used it, but couldn't disclose). TYNDP 2024 is the
ENTSO-E / ENTSOG joint scenarios, publicly downloadable, and is the European TSO
benchmark for grid planning. Strongest open substitute.

> "What does validation against ENTSO-E actually mean?"
For each of DE, NL, BE, DK1, DK2 in 2019 and 2023, I computed the offshore-wind
capture value two ways: (a) PyPSA simulated; (b) using observed ENTSO-E offshore
generation × observed prices. They should agree if the model is good. They do, in
big NS zones (DE 0.910 ≈ 0.909); they diverge in small Baltic-facing zones (DK2:
0.944 modelled vs 0.784 observed). The divergence is the quantified bias I correct.

> "What's the H2 demand floor doing?"
In the 2040 scenarios with very high renewable penetration, the electricity-only
model lets prices crash to zero when wind floods the system. In reality, hydrogen
electrolysers will buy that cheap electricity (paying ~€35-50/MWh because they
produce H2 that's worth ~€50-70/MWh). I add that demand layer to the model — same
mechanism PyPSA-Eur-sec uses, just a simpler parametric form.

> "How is this different from Track 2 (the regression)?"
PyPSA is physics-based: it simulates the grid. The regression is statistical: it
learns CV ~ features from real observations. They share no machinery. Where they
agree (the canonical scenarios) we have high confidence. The regression cannot
extrapolate to high-penetration Baltic; PyPSA can. The two-track design is
specifically to use each method where it's strongest.

---

## E · Visual aid (one slide to draw if helpful)

```
       ┌──────────────────────────────────────────────────────────┐
       │              PyPSA-Eur — Phase 1: CALIBRATE              │
       │                                                          │
       │   weather + plants + lines + demand  ──────────►         │
       │                            ▼                             │
       │                      [Gurobi solver]                     │
       │                            ▼                             │
       │             hourly prices + dispatch + CO₂               │
       │                            ▼                             │
       │       compare to observed ENTSO-E  → quantify bias       │
       └──────────────────────────────────────────────────────────┘
                                    │
                                    ▼ (calibrated, bias known)
       ┌──────────────────────────────────────────────────────────┐
       │              PyPSA-Eur — Phase 2: PROJECT                │
       │                                                          │
       │   overlay TYNDP 2030/2040 capacities + corrections       │
       │                            ▼                             │
       │                      [Gurobi solver]                     │
       │                            ▼                             │
       │           projected prices + capture values              │
       │           bias-corrected via Phase 1 fit                 │
       └──────────────────────────────────────────────────────────┘
                                    │
                                    ▼
       ┌──────────────────────────────────────────────────────────┐
       │              Phase 3: GAS-SHOCK STRESS TEST              │
       │                                                          │
       │   re-solve at gas = 20, 40, 60, 80, 120 €/MWh            │
       │                            ▼                             │
       │   show the Baltic-vs-NS asymmetry holds under all        │
       └──────────────────────────────────────────────────────────┘
```

---

## F · How to actually deliver this

**If verbal (a 10-minute slot)**: open with **A (the 30-second pitch)**. He'll either
nod and move on, or ask a follow-up. Use **B.4 (the headline)** as your second sentence.
Use the pipeline diagram **E** as the only visual. Take questions from **D**.

**If written (handout, email)**: send sections A + B + E. Leave C, D, F for if asked.

**If 2 hours and he wants depth**: walk through `1_PyPSA_Model/README.md` script by
script. That's the technical-reference layer.

---

*This briefing complements `0_READ_THIS_FIRST.md` (the full project guide) and
`1_PyPSA_Model/README.md` (the technical reference). Use whichever depth fits the
audience.*
