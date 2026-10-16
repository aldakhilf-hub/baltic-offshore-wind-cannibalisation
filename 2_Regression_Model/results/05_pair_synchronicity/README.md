# Diurnal / seasonal synchronicity of farm pairs

**Figures:** `fig_pair_synchronicity_Hornsea2_BalticPowe.png` (cross-basin),
`fig_pair_synchronicity_Lillgrund_BalticPowe.png` (within-basin)
**Data:** matching `pair_synchronicity_*.csv` (12 month × 24 hour matrices)
**Script:** `2.10_farm_pair_synchronicity.py` · pooled **2017–2024 (8 years)** · analogue of Paul's Fig 43

## What it shows
For a pair of farms, the correlation of hourly output computed separately in each (month, hour-of-day)
bucket — i.e. *do these two farms blow together at this time of day, this season?*

## So what (the finding)
- **Cross-basin (Hornsea 2 GB × Baltic Power PL): overall r = 0.21** — weak, like Paul's cross-region pair.
  But the structure is physical: **winter (Nov–Jan) is positively correlated (~0.2–0.3)** because winter wind
  is driven by large Atlantic storm systems that span all of NW Europe; **summer midday (Jul) decouples to
  ~0 / slightly negative** because summer wind is local (thermal/sea-breeze). So the North Sea and Baltic are
  *not* uniformly decoupled — the decoupling is a **summer** phenomenon.
- **Within-basin (Lillgrund SE × Baltic Power PL, ~400 km): r = 0.66** — far stronger and uniform.
  The contrast (0.21 cross-basin vs 0.66 within-basin) is the "Baltic blows in unison" story at pair level.

## Caveats — and why a figure was removed
The virtual-wind-farm output is on the ~0.25° ERA5/Open-Meteo grid, so farms closer than that fall on the
**same weather cell and have identical output**. A first contrast pick (Arkona × Baltic Eagle, both off
Rügen) returned a perfect **r = 1.000** for exactly this reason; that figure was **removed as misleading**.
Lesson for the thesis: do not present near-neighbour pairs as independent. Hundreds-of-km pairs (used here)
are unaffected.
