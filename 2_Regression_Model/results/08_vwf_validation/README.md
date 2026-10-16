# VWF validation vs metered offshore generation (2.13)

The foundation test neither predecessor ran: the Virtual Wind Farm's synthetic
output, aggregated to zone level (registry farms commissioned by that year),
correlated against ENTSO-E observed offshore generation for the five validation
zones in all three baseline years (2024 added 2026-06-12). The comparison is on SHAPE, not level, because the
VWF covers a subset of each zone's fleet and capture value only needs the timing
right (CV weights prices by generation).

**Files:** `vwf_validation_metrics.csv` (per zone-year: hourly/daily/monthly
Pearson r, common hours, VWF capacity), `fig_vwf_vs_observed.png` (normalised
monthly energy overlay, thesis methods figure).

## So what (verified 2026-06-12)

Median across the fifteen zone-years: **hourly r 0.885, daily 0.94, monthly
0.95** (quoted in Chapter 3 as 0.88 / 0.95). Range: hourly 0.73-0.78 (DE 2023
and 2024, the one soft spot, its registry farms cover a small share of a large
fleet) to 0.93 (NL 2024); monthly 0.60 (DK1 2019) to 0.98. No systematic basin
difference: the pipeline is as faithful in the Baltic-facing zones (DK2
0.88-0.90 hourly across all three years) as in the North Sea.

## Caveat

The test covers zones with metered offshore fleets (DE, NL, BE, DK1, DK2);
Baltic-state zones have no metered offshore to test against yet, so VWF fidelity
there rests on the same physics transferring, stated in Chapter 5 limitations.
