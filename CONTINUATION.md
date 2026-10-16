# What is unfinished, and what is worth doing next

Notes for whoever picks this up. Everything here was identified during the work
and left deliberately, either because it was out of scope for one MSc or because
it needs compute this project did not have. Each item says what is already in
place, so you are not starting from nothing.

The first section is where the real research is. The second section lists things
that were tried and failed, so you do not spend a week rediscovering them. The
third is engineering debt.

---

## 1. Open research, roughly best payoff first

### 1.1 Curtailment volume as the third channel of loss

**The clearest gap in the thesis.** Capture value is computed on the energy a farm
actually generates, so energy lost to curtailment is invisible to it. That makes
the loss accounting incomplete in exactly one direction.

The thesis splits the loss into a farm-borne part (hours at or below zero price,
where a two-sided contract for difference suspends payment) and a state-borne part
(price depression within paid hours, which the contract tops up). There is a third
channel: volume curtailed and compensated under EU Regulation 2019/943 Article 13,
which is state-borne. In 2040 on today's grid, modelled curtailment is 33.6% in the
North Sea against 3.6% in the Baltic, and Germany alone reaches 44.5%. So the
thesis's finding that North Sea losses are overwhelmingly investor-borne is
understated until volume is added.

What exists: the hour-level accounting in `7_Thesis_Figures/7.36_cfd_who_pays.py`
already reads the solved networks and has the curtailment figures. Adding a third
term to the factorisation in `7.38` is a contained piece of work on data that is
already on disk. No re-solve needed.

### 1.2 The realistic grid, between frozen and optimal

The thesis brackets the answer with two grids: today's network held fixed, and the
network the model expands at least cost. The real 2040 grid will be neither. It
will be roughly what the ten-year network development plan actually builds.

This matters because the bracket is wide and the whole argument turns on it: 0.471
frozen against 0.664 optimal. A planned-grid case would convert the thesis's
bracket into a forecast.

What exists: the configs and both solved scenario sets. What is needed: the TYNDP
or ONDP transmission project list encoded as line capacity additions, then a
re-solve. This is the single highest-value addition to the system model, and it is
a few days of careful data entry plus compute rather than new method.

### 1.3 How much interconnection is enough

Related but separate. The model's least-cost expansion builds 137 GW across the
whole 14-country system, of which only 18.7 GW is cross-border capacity touching
Poland, Estonia, Latvia or Lithuania, at an annualised 0.43 bn EUR per year. The
Baltic's own congestion income is several times that. So the Baltic's cure is
cheap relative to its benefit, but nobody has found the *threshold*: how much
Baltic interconnection recovers most of the value.

What is needed: re-solve at intermediate expansion limits, sweeping the
transmission volume, and plot recovered capture value against capacity added.
Pure compute, no new data. `7_Thesis_Figures/7.44_grid_expansion_table.py` already
scopes the expansion by border, so the measurement machinery exists.

### 1.4 Great Britain as an out-of-sample test

GB was excluded from headline results because the system model structurally
under-prices it and post-Brexit data sits outside the ENTSO-E pull. But GB market
data is public, GB has the most built-out offshore fleet in the region, and it
therefore offers the strongest available test of whether the regression model
transfers to a genuinely saturated market.

This was asked for directly in an industry expert meeting. It is a self-contained
project: pull GB prices and metered offshore output, build the virtual farm for GB
sites, and score the existing regression against them without refitting.

### 1.5 Sector coupling at hourly resolution

Flexible demand turns out to matter as much as transmission. A sector-coupled
variant at 12-hour resolution raises 2040 capture value by +0.23 in the North Sea
and +0.28 in the Baltic, which is larger than the transmission effect of +0.19.
The thesis reports this as a bracket rather than a headline because 12-hour
resolution cannot resolve price shape, and 16GB of memory could not solve it
hourly. The full chain thrashed at 3-hourly and 6-hourly.

What exists: a verified isolated PyPSA-Eur-sec install and a working 2x2
experimental design (sector and electricity-only arms, cost-optimal and
capacity-pinned), with results in
`7_Thesis_Figures/results/sector_coupling_arms_cv_12H.csv`. What is needed: an HPC
allocation. The experiment is designed and the configs exist, so this is a compute
problem rather than a research-design problem.

### 1.6 Where cannibalisation saturates

A fast approximation fitted over 76 solves (scripts 1.12 to 1.16) finds
the loss is **concave** in
penetration, with a penetration-squared coefficient of −0.193 and a confidence
interval of [−0.215, −0.169] that does not cross zero. Marginal damage
*saturates*. This was a surprise, since the loss is usually described as
accelerating.

The likely cause is that a linear optimisation floors the price at zero, so damage
cannot keep growing. If that is right, the thesis's 2040 values are **upper
bounds** and true cannibalisation is worse. Testing it properly needs a price
formation that admits negative prices, which means unit commitment or must-run
constraints, which is the same wall as item 2.1 below. Worth a paper on its own if
you can get past it.

### 1.7 Widening the Baltic training base

Most true Baltic-state farms are still unbuilt, so the regression learns the
enclosed Baltic largely by pricing virtual farms in observed Baltic zones. That
device is defensible and was validated (the model predicts six of seven enclosed
Baltic zones out of fold, blind to each, within 0.07), but it will simply get
better every year as Polish and Baltic farms commission. Re-pulling the panel in
2027 or 2028 with real metered Baltic offshore output would strengthen the single
weakest link in the empirical half.

### 1.8 Two smaller method gaps

- **The regression is roughly half time-following.** About 47% of capture-value
  variation is a common time signal, mostly the 2021 to 2022 fuel crisis, and only
  about 19% is stable farm-to-farm difference. The cross-sectional skill is the
  weaker half, and it is the half the thesis cares about. Zone-resolved fuel
  signals or explicit year effects would help. Within-month de-meaning
  (`2.08b_demeaned_shap.py`) was the fix used for attribution and it worked, so
  carry that idea into the fit itself.
- **Features are national.** Penetration and interconnection are country-level, so
  all within-country variation comes from weather alone. Sub-zonal features would
  sharpen the cross-sectional half.

---

## 2. Already tried and failed. Do not repeat these.

### 2.1 Making the system model reproduce DK2's price shape

Eight documented attempts, all failed. DK2 is modelled as one node tied to Sweden
by a fat, rarely congesting line, so its price pins to the Nordic hydro water
value of about 35 EUR/MWh and never goes negative. Observed DK2 has 264
negative-price hours.

What was tried: a plain re-solve (price is not even unique, dual degeneracy moved
it by 0.04), region-wide negative wind bids (no effect, hydro absorbs the surplus),
derating the Oresund link alone (backfired, repinned DK2 to German gas and tripled
the mean price), correcting both Danish corridors to published market ratings (this
one is a genuine improvement and was kept: DK1's error fell from +0.063 to +0.013
and overall error from 0.049 to 0.038, but **DK2 did not move at all**), capping
hydro foresight to 24 hours (exploded, mean price 1207 EUR/MWh), rolling monthly
solves with carried storage (made it worse, 0.932 to 0.957), and a nine-point grid
of must-run heat levels crossed with negative bids (bracket 0.947 to 0.958, zero
negative hours in all nine).

The conclusion is that DK2's price shape is outside this model class, because
negative prices there come from unit commitment, must-run heat and subsidised
sub-zero bidding, none of which exist in a linear dispatch model. **Do not attempt
a ninth dispatch-side fix, and never tune the model to hit the observed 0.784.**
The correct move, already taken, is to exclude DK2 from headline aggregates on a
criterion stated in advance and report it as a sensitivity.

### 2.2 Going global with this model

Tempting and wrong. The regression is calibrated on European zonal pricing and its
coefficients do not transfer to US independent system operators, Chinese
provincial dispatch or Gulf single-buyer markets. Even the system model would need
a separately maintained regional variant and full recalibration. The honest
extension path is sideways within the same market family: Great Britain (item 1.4)
and the German and UK offshore zones.

### 2.3 Projecting with the regression model alone

The regression cannot carry 2040. None of the 36 projection rows lie inside its
seven-dimensional training range, the trees are exactly constant outside it, and
its response across all four Baltic scenarios spans 0.008 against the system
model's 0.428. A smooth analytical form fitted to the same data extrapolates too
gently, landing near 0.79 where the system model gives 0.57, because penetration
enters it linearly and it cannot reproduce congestion. That stands as a finding in
its own right, and it is why the two models hand over.

---

## 3. Engineering debt

- **No automated tests beyond `tools/smoke_test.py`, and no CI.** The smoke test
  checks that the install works and the data is intact. It does not check that any
  analysis still produces the published numbers. A regression test asserting the
  headline table against `grid_reversal_table.csv` would be cheap and valuable.
- **Script numbering is the only orchestration.** Running out of order silently
  consumes stale inputs. A Snakemake or Makefile wrapper over each track would
  make the dependency graph real. Track 1's `run_week1_refresh.sh` is the nearest
  thing that exists.
- **Two scripts are both numbered 3.02**, in `3_Comparison/` and
  `3_Comparison/scripts/`. Renumber the second one.
- **PyPSA-Eur is not vendored** and must be cloned to `~/pypsa-eur` at version
  `v2026.02.0-39-g23c2fac7`. Later versions moved config keys. Pin it, or better,
  record the exact commit in a submodule.
- **One known data staleness.** The virtual-wind-farm power curve was corrected to
  hard-zero outside the 3 to 25 m/s range after smoothing, but the eight-year
  hourly panel was never regenerated with the corrected curve. The expected effect
  on capture value is under 0.5%, it is documented in the thesis appendix, and
  regenerating it needs a full re-pull and cascade. Worth doing once if you are
  re-pulling anyway.
- **A diagnostic that was cut for being confusing.** A regime-transfer test across
  the 2022 structural break is still computed into
  `3_Comparison/results/.../regime_transfer.csv` but is not used in the thesis. Its
  numbers: regression error rises from 0.046 to 0.067 across the break and its
  bias flips sign, while the system model stays flat at 0.041 and 0.049. It is a
  genuine result that needs a clearer explanation before anyone uses it.
