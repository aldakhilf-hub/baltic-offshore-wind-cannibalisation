"""
compare_three_way.py  --  W6, the headline deliverable.

Brings the two thesis tracks together against observed truth:

  OBSERVED    : observed offshore generation x observed price (ground truth)
  PyPSA       : system-optimisation modelled capture value
  REGRESSION  : Paul-style empirical model (Strand A)

Two comparisons:

  PART 1  Validation triangle (where observed exists: 2019 + 2023 + 2024,
          zones DE / NL / BE / DK1 / DK2). Three independent estimates of the
          SAME observable. Agreement = confidence; disagreement = finding.
          (2024 rows appear once calibration_2024 exists; missing years are
          skipped, so the script runs on whatever has been solved.)

  PART 2  Projection (2030 / 2040 Baltic, no observed). PyPSA vs Regression.
          The regression abstains in the high-penetration regime it cannot
          extrapolate to, so PyPSA carries the Baltic projection -- the
          division of labour is itself the result.

Reads both tracks' result CSVs (this folder is the cross-track join, owned by
neither track). Writes tables + figures to Comparison/results/.

Usage:  python compare_three_way.py
"""
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent.parent
REG = ROOT / "2_Regression_Model"
PV = ROOT / "1_PyPSA_Model"
OUT = Path(__file__).resolve().parent / "results"
OUT_VAL = OUT / "01_validation_triangle_2023"
OUT_PROJ = OUT / "02_projection_pypsa_vs_regression"
for _d in (OUT_VAL, OUT_PROJ):
    _d.mkdir(parents=True, exist_ok=True)

# regression bidding-zone -> PyPSA calibration zone. Danish zones appear in
# BOTH spellings across Track-2 artifacts: the farm registry (and hence
# features/OOF files) uses DK1/DK2, while monthly_cv_per_farm.csv stores the
# ENTSO-E form DK_1/DK_2 — map both.
ZMAP = {"DE_LU": "DE", "NL": "NL", "BE": "BE",
        "DK_1": "DK1", "DK_2": "DK2", "DK1": "DK1", "DK2": "DK2"}
ZONE_ORDER = ["DE", "NL", "BE", "DK1", "DK2"]


def regression_zone_cv(year):
    """Two regression-side estimates per calibration zone:

    CV_regression      — mean OUT-OF-FOLD model prediction over the zone's
                         operational farm-months (GroupKFold by farm, from
                         2.06): each farm is predicted by a model that never
                         saw it. This is the honest 'independent method'
                         column (audit fix: previously the column held
                         in-sample VWF values, overstating independence).
    CV_vwf_empirical   — the VWF-empirical CV (synthetic farm gen x observed
                         price, simple mean over farms): not a model output,
                         but a useful data-construction cross-check.
    """
    sites = pd.read_csv(REG / "data/wind_farms_strandA.csv", comment="#")
    st = sites.set_index("name").status.to_dict()

    oof_path = REG / "results/01_model_fit_and_validation/oof_predictions_groupkfold.csv"
    if not oof_path.exists():
        raise SystemExit(f"missing {oof_path} — run 2.06 first (it now exports "
                         f"out-of-fold predictions).")
    oof = pd.read_csv(oof_path)
    oof = oof[oof.year == year].copy()
    oof["zone"] = oof.bidding_zone.map(ZMAP)
    pred = oof[oof.zone.notna()].groupby("zone").CV_pred_oof.mean()

    cv = pd.read_csv(REG / "data/cv_strandA/monthly_cv_per_farm.csv")
    cv["status"] = cv.farm.map(st)
    cv = cv[(cv.status == "operational") & (cv.year == year)].copy()
    cv["zone"] = cv.bidding_zone.map(ZMAP)
    vwf = cv[cv.zone.notna()].groupby("zone").CV.mean()
    return pred, vwf


def validation_triangle():
    rows = []
    for year in (2019, 2023, 2024):
        cv_path = PV / f"results/calibration_{year}/observed_capture_value_comparison.csv"
        if not cv_path.exists():
            print(f"  triangle: skipping {year} (no calibration outputs yet)")
            continue
        pcv = pd.read_csv(cv_path)
        pcv = pcv.set_index("zone")
        rcv, vwf = regression_zone_cv(year)
        for z in ZONE_ORDER:
            if z not in pcv.index:
                continue
            rows.append({
                "zone": z, "year": year,
                "CV_observed": round(float(pcv.loc[z, "CV_obs"]), 3),
                "CV_pypsa": round(float(pcv.loc[z, "CV_pypsa"]), 3),
                "CV_regression": round(float(rcv.get(z, np.nan)), 3),
                "CV_vwf_empirical": round(float(vwf.get(z, np.nan)), 3),
            })
    df = pd.DataFrame(rows)
    df["pypsa_err"] = (df.CV_pypsa - df.CV_observed).round(3)
    df["regr_err"] = (df.CV_regression - df.CV_observed).round(3)
    return df


def projection_table():
    """PyPSA Baltic projections vs the regression's Baltic projection."""
    pj = pd.read_csv(PV / "results/projections_v3/baltic_cv_fit_corrected.csv")
    pj = pj.rename(columns={pj.columns[0]: "scenario"})
    # regression projected Baltic CV (BEST trajectory), split in-range vs extrap
    rp = pd.read_csv(REG / "results/03_projection_2030_2040/projected_capture_values.csv")
    rp = rp[(rp.trajectory == "BEST") & (rp.basin == "Baltic")]
    rows = []
    inrange_preds = []
    for yr in (2030, 2040):
        ir = rp[(rp.horizon == yr) & (rp.in_range)]
        oor = rp[(rp.horizon == yr) & (~rp.in_range)]
        band_lo = oor[["pred_CV_linear", "pred_CV_xgb"]].min(axis=1)
        band_hi = oor[["pred_CV_linear", "pred_CV_xgb"]].max(axis=1)
        inrange_preds.append(ir[["pred_CV_xgb", "pred_CV_linear"]])
        rows.append({
            "horizon": yr,
            "reg_inrange_CV": round(ir[["pred_CV_xgb", "pred_CV_linear"]].mean(axis=1).mean(), 3),
            "reg_inrange_nfarms": ir.farm.nunique(),
            "reg_extrap_band": (f"[{band_lo.min():.2f}, {band_hi.max():.2f}]"
                                if len(oor) else "n/a"),
        })
    reg = pd.DataFrame(rows)
    # the regression's in-range band for the projection figure — computed from
    # the data (audit fix: was hardcoded 0.79-0.86 and went stale on re-runs)
    allp = pd.concat(inrange_preds)
    reg_band = ((float(allp.min().min()), float(allp.max().max()))
                if len(allp.dropna()) else None)
    return pj, reg, reg_band


def main():
    # ---- Part 1 -----------------------------------------------------------
    tri = validation_triangle()
    tri.to_csv(OUT_VAL / "validation_triangle.csv", index=False)
    print("=== PART 1: validation triangle (Observed / PyPSA / Regression-OOF) ===")
    print(tri.to_string(index=False))
    print("\nReading: CV_regression is the GroupKFold OUT-OF-FOLD prediction (the model"
          "\nnever saw the zone's farms), so the three columns are genuinely independent"
          "\nestimates. Where all three agree -> confident; where PyPSA diverges from"
          "\nObserved+Regression -> PyPSA over-states CV in small wind-saturated zones,"
          "\nthe documented bias the projection corrects for.")

    # ---- Part 2 -----------------------------------------------------------
    pj, reg, reg_band = projection_table()
    pj.to_csv(OUT_PROJ / "projection_pypsa.csv", index=False)
    reg.to_csv(OUT_PROJ / "projection_regression.csv", index=False)
    print("\n=== PART 2: Baltic projection -- PyPSA vs Regression ===")
    print("PyPSA (NT scenarios):")
    pj_cols = [c for c in ["scenario", "avg_penetration", "CV_raw", "CV_corr_fit",
                           "CV_corr_lo", "CV_corr_hi"] if c in pj.columns]
    print(pj[pj_cols].round(3).to_string(index=False))
    print("\nRegression Baltic:")
    print(reg.to_string(index=False))
    print("\nReading: PyPSA projects strong cannibalisation (see CV_corr_fit with its"
          "\nCI band); the regression's in-range farms stay moderate and it CANNOT reach"
          "\nthe high-penetration zones (extrapolation band uselessly wide)."
          "\n-> The regression validates the moderate-penetration regime; PyPSA carries"
          "\nthe high-penetration Baltic. That division of labour is the result.")

    # ---- figures ----------------------------------------------------------
    # Fig 1: validation triangle, 2023 - levels (left) + error vs observed (right)
    t23 = tri[tri.year == 2023].set_index("zone").reindex(ZONE_ORDER)
    x = np.arange(len(t23))
    C_PY, C_RG = "#1f6f8b", "#c06c3e"
    fig, (axL, axR) = plt.subplots(1, 2, figsize=(11.2, 4.3),
                                   gridspec_kw={"width_ratios": [1, 1]})
    # left: levels, observed as a wide black tick, instruments as dots
    axL.scatter(x, t23.CV_observed, marker="_", s=900, linewidth=3.2,
                color="#2d2d2d", label="Observed", zorder=3)
    axL.scatter(x - 0.13, t23.CV_pypsa, s=64, color=C_PY, label="PyPSA", zorder=4)
    axL.scatter(x + 0.13, t23.CV_regression, s=64, color=C_RG,
                label="Regression (out of fold)", zorder=4)
    for xi, z in zip(x, t23.index):
        axL.plot([xi - 0.13, xi - 0.13], [t23.loc[z, "CV_observed"], t23.loc[z, "CV_pypsa"]],
                 color=C_PY, lw=1.1, alpha=0.6, zorder=2)
        axL.plot([xi + 0.13, xi + 0.13], [t23.loc[z, "CV_observed"], t23.loc[z, "CV_regression"]],
                 color=C_RG, lw=1.1, alpha=0.6, zorder=2)
    axL.set(xticks=x, xticklabels=t23.index,
            ylabel="Offshore-wind capture value, 2023",
            title="Three estimates per zone")
    axL.legend(fontsize=9, loc="lower left")
    axL.grid(axis="y", alpha=0.3)
    # right: signed error against observed
    err_py = t23.CV_pypsa - t23.CV_observed
    err_rg = t23.CV_regression - t23.CV_observed
    w = 0.34
    axR.bar(x - w / 2, err_py, w, color=C_PY, label="PyPSA")
    axR.bar(x + w / 2, err_rg, w, color=C_RG, label="Regression (out of fold)")
    axR.axhline(0, color="#2d2d2d", lw=1.4)
    for xi, v in zip(x, err_py):
        axR.annotate(f"{v:+.2f}", xy=(xi - w / 2, v + 0.004), ha="center",
                     fontsize=8.5, color=C_PY, fontweight="bold")
    axR.set(xticks=x, xticklabels=t23.index,
            ylabel="Error against observed",
            title="Error against observation")
    axR.legend(fontsize=9, loc="upper left")
    axR.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(OUT_VAL / "fig_validation_triangle_2023.png", dpi=200)

    # Fig 2: Baltic projection, PyPSA corrected vs regression in-range
    fig, ax = plt.subplots(figsize=(7, 4))
    nt = pj[pj.scenario.str.contains("NT")].copy().sort_values("avg_penetration")
    ax.plot(nt.avg_penetration, nt.CV_raw, "o-", color="#1f6f8b", label="PyPSA raw")
    ax.plot(nt.avg_penetration, nt.CV_corr_fit, "s--", color="#10485c", label="PyPSA bias-corrected")
    if {"CV_corr_lo", "CV_corr_hi"}.issubset(nt.columns):
        ax.fill_between(nt.avg_penetration, nt.CV_corr_lo, nt.CV_corr_hi,
                        color="#10485c", alpha=0.15, label="correction 95% CI")
    if reg_band:
        ax.axhspan(reg_band[0], reg_band[1], color="#c06c3e", alpha=0.25,
                   label=f"Regression in-range [{reg_band[0]:.2f}, {reg_band[1]:.2f}]")
    ax.set(xlabel="Baltic offshore penetration", ylabel="Baltic capture value",
           title="Baltic projection: PyPSA spans the high-penetration regime\n"
                 "the regression cannot reach")
    ax.legend(fontsize=10); ax.grid(alpha=0.3)
    fig.tight_layout(); fig.savefig(OUT_PROJ / "fig_baltic_projection_pypsa_vs_regression.png", dpi=200)

    print(f"\nSaved tables + 2 figures -> {OUT}/")


if __name__ == "__main__":
    main()
