# 4 · Surrogate Model — Plan for the Next Modelling Phase

> **Read this AFTER `0_READ_THIS_FIRST.md`.** That doc explains what's been done.
> This doc explains the next methodological extension and how to execute it.

**Last updated 2026-06-11. Status: BUILT (scripts 1.12–1.15) and retrained on the post-audit re-solved networks; this document is the original design (historical reference). Delivered design deviates where documented in 1.12–1.14 docstrings.**

---

## 1 · Why we're adding a third method

The thesis currently has two independent methods (Track 1 PyPSA + Track 2 Regression) plus a three-way comparison (Track 3). That's already a strong contribution. The **surrogate model** adds a third methodological layer that:

1. Distils a validated PyPSA into a fast ML emulator (predictions in milliseconds, not minutes).
2. Sidesteps the regression's documented extrapolation limitation (`0_READ_THIS_FIRST.md` §7) by training the emulator on PyPSA's *simulated* high-penetration outputs — PyPSA can generate training data anywhere in the input space.
3. Becomes a *deliverable* in itself — a tool a future researcher can use to interrogate Baltic offshore scenarios without re-running PyPSA.

**Key methodological positioning** (this is the line to defend):
> "Methods 1 and 2 establish that the headline result is robust across two independent
> methodologies. The surrogate then *distils the validated PyPSA model* into a fast
> emulator, enabling sensitivity analysis and counterfactual exploration that the raw
> PyPSA solve makes impractical."

The independence of Tracks 1 and 2 is preserved (they were built and compared *before* the surrogate). The surrogate is positioned as a *practical extension* on top of a validated model, not as a substitute for either.

---

## 2 · The three-act thesis structure (with the surrogate)

| Act | Chapter | Method | Validation | Output |
|---|---|---|---|---|
| 1 | 4 | PyPSA-Eur | vs observed ENTSO-E CV (Track 1 `1.04`) | Calibration metrics + DK2 bias quantification + projection v3 |
| 2 | 5 | Empirical regression | vs observed CV + PyPSA comparison (Track 3) | Independent confirmation of headline + SHAP mechanism |
| **3** | **6** | **PyPSA surrogate emulator** | **vs held-out PyPSA scenarios** | **Fast sensitivity / Monte Carlo tool + bounded uncertainty intervals** |
| Synthesis | 7 | 3-way comparison + surrogate sensitivity | — | Final headline with documented uncertainty bounds |

---

## 3 · Experimental design (the sketch)

### 3.1 Input space — 8 dimensions

PyPSA inputs that meaningfully move the projected CV. Ranges cover the realistic envelope from TYNDP LOW through HIGH plus stress-test extremes:

| # | Input | Symbol | Range | Default (NT 2040) | Rationale |
|---|---|---|---|---|---|
| 1 | Gas price (€/MWh_th) | `gas` | 15 – 100 | 20.3 | Dominant marginal-cost driver |
| 2 | CO₂ price (€/tCO₂) | `co2` | 50 – 200 | 147 | Modifies thermal merit order |
| 3 | Baltic offshore total (GW) | `baltic_off` | 10 – 150 | ~24 | Headline input |
| 4 | North Sea offshore total (GW) | `ns_off` | 30 – 250 | ~170 | NS reference; couples via flows |
| 5 | Solar (EU-14) (GW) | `solar` | 200 – 800 | ~742 | Daily profile shape |
| 6 | Demand growth multiplier (vs 2019) | `dem_mult` | 1.0 – 2.0 | TYNDP NT-DE | Captures DE/GA range + stress |
| 7 | Battery (EU-14) (GW) | `batt` | 50 – 400 | ~160 | Flexibility absorbs surplus |
| 8 | H2 electrolyser (EU-14) (GW) | `h2` | 30 – 200 | ~101 | Price floor mechanism |

### 3.2 Experimental design — Latin Hypercube Sampling

LHS with **N = 50 samples** in 8 dimensions. LHS guarantees marginal coverage of each input dimension without combinatorial blow-up (vs full factorial 2⁸ = 256). 50 samples → 40 train / 10 test split.

Optional: 5 additional **policy-anchor points** (TYNDP NT-2030, NT-2040, DE-2040, GA-2040, plus 2030-NT-balticHigh) to ensure the surrogate is accurate at the scenarios the thesis quotes directly. So **55 PyPSA runs total**.

### 3.3 Outputs (what the surrogate predicts)

For each PyPSA run, extract per (year, zone) row:

- **CV_offshore_zone** — raw (and bias-corrected via the validated DK2 fit)
- **mean_price_zone** — annual mean wholesale price (€/MWh)
- **baltic_vs_ns_ratio** — the headline metric (% Baltic price drop ÷ % NS price drop)

Surrogate model = one XGBoost regressor per output, with `(zone, year)` as categorical features alongside the 8 inputs. Total samples = 55 runs × ~14 zones × 2 years = ~1,540 rows.

### 3.4 ML model + validation

- **Primary**: XGBoost (depth 4–6, n_estimators 300, early stopping on validation set). Cross-validate by held-out scenario (not by row — to avoid leakage across the same run's zones).
- **Diagnostic**: Polynomial regression (Paul-style) on the same features as a complexity baseline.
- **Validation metrics**:
  - R² (overall and per zone)
  - MAE on the headline metric (Baltic/NS ratio)
  - Anchor check: does it reproduce the 5 policy scenarios within ±0.02 CV / ±2% price?
- **Feature importance**: SHAP (already in env from Track 2).

### 3.5 Compute cost

| Item | Cost |
|---|---|
| 55 PyPSA runs at ~10 min each (script `1.07`-style) | ~9 hours background |
| LHS sample generation | seconds |
| ML training + cross-validation | minutes |
| **Total wall clock** | **~10 hr** (mostly background overnight) |

---

## 4 · Scripts to write (4 files in `1_PyPSA_Model/scripts/`)

Follow the existing numbering convention; surrogate sits at end of Track 1.

| Script | Purpose |
|---|---|
| `1.12_surrogate_design.py` | Generate LHS samples + policy-anchor points; save inputs to a CSV |
| `1.13_surrogate_runs.py` | Iterate over the 55 input rows, configure PyPSA per-run, solve, extract per-zone CV + price |
| `1.14_surrogate_fit.py` | Train XGBoost per output, cross-validate, save model + SHAP |
| `1.15_surrogate_sensitivity.py` | Use trained surrogate for ±50% gas / ±30% penetration sweeps; produce figures |

Outputs land in `1_PyPSA_Model/results/surrogate/` (new subfolder).

The cross-track comparison stays in `3_Comparison/` but gains a row for the surrogate.

---

## 5 · Time budget for Act 3 (~2 weeks if focused)

| Week | Work |
|---|---|
| 1 | Write `1.12` + `1.13`. Kick off 55 PyPSA runs in background. Write `1.14` while runs execute. |
| 2 | Once runs land: fit XGBoost, cross-validate, anchor-check. Write `1.15` + run sensitivities. Produce figures. |
| 3 (writing) | Surrogate chapter draft + sensitivity-analysis section + updated synthesis chapter. |

This fits comfortably in the ~3 months remaining (per `0_READ_THIS_FIRST.md` §8 the rest of the time is refinement levers A–F + thesis writing).

---

## 6 · Open questions to resolve in the next chat

Before writing code, the next-chat agent should confirm with the user:

1. **Do we want 55 runs, or fewer/more?** 50 LHS + 5 anchors is the standard recommendation; budget allows 30–80 depending on appetite.
2. **Should the surrogate predict per-zone CV, or just the Baltic/NS ratio?** The richer per-zone output costs nothing extra and supports more thesis figures.
3. **Refinement levers A–F vs surrogate** — should Act 3 happen before or after the refinement work in `0_READ_THIS_FIRST.md` §8? **Recommendation**: surrogate first (it's a new contribution; refinements polish the existing ones).
4. **Where does the surrogate's bias-correction live?** Apply the validated DK2 fit (from `1.09`) before training, or after? Recommend: apply *to the PyPSA outputs* before training the surrogate, so the surrogate learns the corrected mapping.

---

## 7 · Methodological framing for the thesis (the paragraph to defend)

> "Methods 1 (PyPSA) and 2 (regression) provide two independent estimates of Baltic
> offshore-wind capture value. Where they agree (the canonical scenarios) we have high
> confidence in the headline asymmetry. Where the regression cannot reliably operate
> (high Baltic penetration well beyond the historical training envelope), PyPSA serves
> as the primary projection engine. To make PyPSA's projections themselves
> *interrogable* — to perform sensitivity analysis, Monte Carlo uncertainty
> propagation, and counterfactual exploration without the computational burden of
> re-solving the optimisation — we trained an XGBoost surrogate emulator on a Latin-
> Hypercube design of 55 PyPSA scenarios spanning the realistic input envelope. The
> surrogate reproduces PyPSA outputs to R² > 0.9 on held-out scenarios and provides
> the practical tool that makes the modelling chain usable for downstream policy
> analysis."

This framing:
- Preserves independence of Tracks 1 & 2 (built and compared *before* the surrogate)
- Justifies the surrogate as solving a *real* practical problem (PyPSA is slow)
- Avoids circular validation (surrogate is validated against PyPSA itself, not against the regression)
- Makes the surrogate a deliverable (downstream usability) not just a methodological flourish

---

*Generated from the 2026-06-03 conversation about coupling PyPSA outputs into an ML surrogate. Pairs with `0_READ_THIS_FIRST.md` (the canonical project doc) and the three-track READMEs.*
