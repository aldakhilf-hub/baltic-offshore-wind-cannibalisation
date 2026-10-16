# PyPSA calibration & validation — 2019 (pre-crisis companion year)

**Re-solved 2026-06-11** with the year-correct 2019 fleet (DE offshore 7.7 GW — the old
run wrongly carried a ~2025 fleet AND excluded German nuclear) and frozen grid. Same
scripts/files as `calibration_2023/`.

## So what
2019 shows a mild, roughly UNIFORM PyPSA over-statement of capture value (~+0.06 in all
five zones) at the low penetrations of 2019 — consistent with the bias-vs-penetration
story: little congestion exposure, little differential bias. Used as low-penetration
support in the 1.09 bias fit (NL 2019 excluded as low-confidence observed data).
