# Capture-value mechanism — SHAP decomposition (2.08)

**Zone-resolved features since 2026-06-11.** Files: `shap_importance.csv`, beeswarm/bar/
dependence figures, `analytical_polynomial.txt` (closed-form backup, in-sample R² in file).

## Shares of explained CV variation (verified 2026-06-15, panel)
Carbon 29.0% · **Corr_VRE 22.8%** · Gas 14.3% · Corr_Load 10.6% · Penetration 9.5% ·
Flexibility 7.3% · Interconnection 6.6%. All directions match cannibalisation theory
(beeswarm). Zone resolution RAISED the system-wind-correlation share to ~23%: the core
cannibalisation channel sharpens once DK1/DK2 are no longer blurred.

## Caveats
SHAP is computed on the in-sample fit (label it); carbon's share partly proxies the
2021-22 fuel-crisis time signal — quote alongside the ex-2022 fit. The analytical
polynomial is RFE-mechanical; the per-basin fit of Paul's mechanistic functional form is
the planned upgrade.
