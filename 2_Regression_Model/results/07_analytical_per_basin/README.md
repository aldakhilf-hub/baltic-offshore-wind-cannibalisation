# Paul's analytical equation, fitted per basin (2.12)

Paul Jacquet's mechanistic capture-value equation
`CV = 1 − B·(ModWF/ModBZN)·VREMS − C·ModWF·(0.202·carbon + gas)^γ`
refitted on this project's zone-resolved data: pooled, NS-only, Baltic-only, with
farm-block bootstrap 90% CIs. Files: `analytical_constants.csv`,
`implied_cannibalisation_slope.csv`, `fig_constants_comparison.png`, `fig_fit_quality.png`.

## Findings (verified 2026-06-15, bidding-zone market panel)
1. **The basins obey the same equation with different shape constants.** The robust
   difference is CONVEXITY, not scale: the pattern-penalty exponent α is 0.74 (Baltic)
   vs 0.37 (NS), steeper in 99 of 100 farm-block bootstraps; the Baltic's penalty
   escalates faster as wind-pattern dominance grows. δ (buffering sensitivity) and γ
   also lean higher in the Baltic. (B trades off against α inside the same term: do not
   compare constants one-by-one.)
2. **The interpretable headline, the implied cannibalisation slope dCV/dpenetration at
   common reference conditions:** at TODAY'S mean pattern dominance the Baltic slope is
   about 1.6× the North Sea's (steeper in 83 of 100 bootstraps); at BUILDOUT-LIKE
   dominance (P90) it is about 1.9× (steeper in 90 of 100). The asymmetry is a property
   of where buildout pushes the system, not of today's operating point, consistent with
   PyPSA's moderate-2030 / severe-2040 shape and with 2.11 (enclosure mechanisms).
3. Fit quality: R² 0.23 pooled / 0.20 NS / 0.30 Baltic, same league as Paul's 0.36; the
   equation is the interpretable mechanism backup, not the headline predictor. Notably
   the mechanism is MORE visible in the Baltic.

## Caveats
In-sample fits; the Baltic now rests on 15 farms across 7 zones (the panel, up from 8
operational farms); bootstrap CIs are farm-block (n=200); the reference-conditions
evaluation fixes buffering at the pooled mean, vary it as a robustness check when writing.
