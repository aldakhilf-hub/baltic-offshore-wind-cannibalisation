# Spatial correlation of wind output — clusters + map

**Figures:** `fig_farm_correlation_clusters.png` (clustered matrix), `fig_farm_map_clusters.png` (geographic)
**Data:** `farm_correlation_matrix.csv`, `farm_clusters.csv`
**Script:** `2.09_farm_correlation_clusters.py` · pooled hourly output **2017–2024 (8 years, ~70k hours)**

## What it shows
Pearson correlation of hourly wind-power output between all 31 farms (16 North Sea + 15 Baltic),
hierarchically clustered so co-varying farms form the diagonal blocks (matrix), then those same 8
clusters placed on the map. Cluster numbers are shared between the two figures (diagonal order).

## So what (the finding)
Independent, **weather-only** corroboration of the cannibalisation story (no prices involved):

| | Mean pairwise correlation |
|---|---|
| Within North Sea | 0.524 |
| **Within Baltic** | **0.571** |
| Cross-basin (NS ↔ Baltic) | 0.255 |

Baltic farms co-vary **more** with each other and are **decoupled** from the North Sea — so Baltic wind
crashes its own local price simultaneously across a smaller, more isolated basin with little outside
market to absorb the surplus. The 8 clusters map cleanly onto real wind regions (Southern Bight, central
North Sea, Gulf of Riga, eastern Baltic, German/western Baltic…); note Anholt (a North-Sea bidding zone in
the Kattegat) correctly clusters with the Baltic — the method tracks meteorology, not zone labels.

## Caveats
Country/grid resolution: farms within ~0.25° share a weather cell (see `05_pair_synchronicity`).
