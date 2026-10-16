# Why the Baltic discount emerged BEFORE the buildout (2.11)

SHAP group-difference decomposition of the (Baltic − NS) capture-value gap, exactly
additive on the predicted gap. Files: `gap_decomposition.csv`, `fig_gap_waterfall.png`.

## The finding (verified 2026-06-12)
The basin gap doubled from −0.017 (2017–19) to −0.035 (2023–24), and its COMPOSITION
changed:

| driver | 2017–19 | 2023–24 |
|---|---|---|
| **Interconnection_Index** | +0.002 | **−0.016** (largest term) |
| Corr_VRE (wind-pattern structure) | −0.013 | −0.011 |
| Carbon_Price | +0.000 | −0.006 |
| VRE_MarketShare (local penetration) | −0.009 | **−0.002** (shrank!) |

Reading: the discount that opened by 2023–24 is NOT driven by local penetration — that
contribution shrank. It is driven by the Baltic's **interconnection disadvantage**
(swung from neutral to the dominant penalty as NS interconnection expanded) plus the
structural **wind-correlation penalty** of an enclosed basin. These are precisely the
enclosure mechanisms the thesis projects will amplify under buildout — observable in
historical data before a single TYNDP gigawatt is added. The flagged lit-review
inconsistency is thereby resolved AND converted into evidence for the thesis mechanism.

## Caveats
In-sample SHAP on the full operational fit (2.08 convention); predicted gaps track
actual gaps to ±0.002 in both eras. FI/SE rows rest on one operational farm each
(price-side driven, so zone-representative). Quote alongside the ex-2022 robustness fit.
