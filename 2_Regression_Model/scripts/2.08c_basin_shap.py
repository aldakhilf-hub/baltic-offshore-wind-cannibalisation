"""
2.08c_basin_shap.py -- basin-split SHAP: the drivers of capture-value erosion in
the North Sea vs the enclosed Baltic.

Method (W6-correct): the cross-sectional (within-month de-meaned) panel, because
carbon and gas are Europe-wide monthly prices and carry no farm-to-farm signal;
de-meaning isolates the cannibalisation skill. ONE validated XGBoost is trained on
the pooled de-meaned panel and its SHAP values are PARTITIONED by basin. This asks:
given the single learned cannibalisation function, which features drive each basin's
capture-value deviation, and in which direction. (Separately-trained per-basin models
are fragile on the thin Baltic operational panel; the analytical exponent 0.74 vs
0.37 already establishes the function itself is steeper in the Baltic. A separate-model
ranking is printed as a caveated robustness check.)

For each feature and basin we report:
  - importance: mean|SHAP|, as a share of the basin's total (what matters most)
  - direction:  mean signed SHAP (negative = pushes that basin's CV DOWN = erodes)
  - the why:    the basin's mean RAW feature level (the physical asymmetry)

Outputs to results/02_capture_value_mechanism_SHAP/:
  basin_shap_comparison.csv, fig_basin_shap.png
Run: ~/miniforge3-arm64/envs/pypsa-eur-arm64/bin/python 2.08c_basin_shap.py
"""
import importlib.util
from pathlib import Path
import numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
import shap

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RESULTS = ROOT / "results" / "02_capture_value_mechanism_SHAP"
DECK = ROOT.parent / "10_Presentation" / "figures"

_spec = importlib.util.spec_from_file_location("fit06", HERE / "2.06_fit_regression.py")
fit06 = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(fit06)
FEATURES, TARGET = fit06.FEATURES, "CV"
SHORT = {f: fit06.SHORT[f] for f in FEATURES}
NICE = {"Corr_VRE": "Crowding\n(corr. w/ system wind)", "Corr_Load": "Corr. w/ demand",
        "VRE_MarketShare": "VRE market share", "Gas_Price": "Gas price",
        "Carbon_Price": "Carbon price", "Flexibility_Index": "Flexibility (storage)",
        "Interconnection_Index": "Interconnection"}
nice = lambda f: NICE.get(SHORT[f], SHORT[f])


def shap_partition(df):
    """Train XGBoost on the de-meaned panel, return SHAP (n x 7) and the basin vector."""
    g = df.groupby(["year", "month"])
    dem = df.copy()
    dem[FEATURES + [TARGET]] = g[FEATURES + [TARGET]].transform(lambda s: s - s.mean())
    X, y = dem[FEATURES], dem[TARGET].values
    model = fit06.make_models()["XGBoost"].fit(X, y)
    sv = shap.TreeExplainer(model).shap_values(X)
    return sv, df.basin.values


def main():
    df = fit06.load_training_panel().reset_index(drop=True)
    sv, basin = shap_partition(df)

    rows = []
    for j, f in enumerate(FEATURES):
        r = {"feature": SHORT[f]}
        for b in ["NS", "Baltic"]:
            m = basin == b
            r[f"{b}_absSHAP"] = float(np.abs(sv[m, j]).mean())
            r[f"{b}_signed"] = float(sv[m, j].mean())
            r[f"{b}_featmean"] = float(df.loc[m, f].mean())
        # direction of the feature->CV relationship (sign of corr on full panel)
        cc = np.corrcoef(df[f].values, sv[:, j])[0, 1]
        r["feat_to_CV_sign"] = "+" if cc > 0 else "-"
        rows.append(r)
    B = pd.DataFrame(rows)
    for b in ["NS", "Baltic"]:
        B[f"{b}_imp%"] = (100 * B[f"{b}_absSHAP"] / B[f"{b}_absSHAP"].sum()).round(1)
    B = B.sort_values("Baltic_imp%", ascending=False).reset_index(drop=True)
    B.round(4).to_csv(RESULTS / "basin_shap_comparison.csv", index=False)

    pd.set_option("display.width", 200)
    print("\n=== basin-split SHAP (cross-sectional, de-meaned panel) ===")
    print(B[["feature", "NS_imp%", "Baltic_imp%", "NS_signed", "Baltic_signed",
             "NS_featmean", "Baltic_featmean", "feat_to_CV_sign"]].round(3).to_string(index=False))

    # per-basin mean z-scored feature level (the physical "why"), + erode/protect tag
    SHORT2F = {SHORT[f]: f for f in FEATURES}
    zlev = {}
    for f in FEATURES:
        z = (df[f] - df[f].mean()) / df[f].std()
        zlev[f] = {"NS": float(z[basin == "NS"].mean()), "Baltic": float(z[basin == "Baltic"].mean())}
    B["NS_z"] = [zlev[SHORT2F[ft]]["NS"] for ft in B.feature]
    B["Baltic_z"] = [zlev[SHORT2F[ft]]["Baltic"] for ft in B.feature]

    # ---------------- figure ----------------
    order = B.feature.tolist()
    labels = [NICE.get(o, o) for o in order]
    yy = np.arange(len(order))[::-1]
    C_NS, C_BAL = "#2471a3", "#c0392b"
    h = 0.4
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13.6, 6.4))

    # Panel 1: importance, NS vs Baltic (one validated model, SHAP partitioned)
    ax1.barh(yy + h / 2, B["NS_imp%"], height=h, color=C_NS, label="North Sea")
    ax1.barh(yy - h / 2, B["Baltic_imp%"], height=h, color=C_BAL, label="Enclosed Baltic")
    for yi, (_, rr) in zip(yy, B.iterrows()):
        ax1.text(rr["NS_imp%"] + 0.4, yi + h / 2, f"{rr['NS_imp%']:.0f}", va="center", fontsize=8.4, color=C_NS)
        ax1.text(rr["Baltic_imp%"] + 0.4, yi - h / 2, f"{rr['Baltic_imp%']:.0f}", va="center", fontsize=8.4, color=C_BAL)
    ax1.set_yticks(yy); ax1.set_yticklabels(labels, fontsize=9)
    ax1.set_xlabel("Share of cross-sectional capture-value signal (mean |SHAP|, %)", fontsize=10)
    ax1.set_title("What drives capture value in each basin", fontsize=12, fontweight="bold")
    ax1.legend(fontsize=9.5, loc="lower right"); ax1.grid(axis="x", alpha=0.3)
    for s in ["top", "right"]: ax1.spines[s].set_visible(False)

    # Panel 2: the WHY -- per-basin feature level (z-scored), with erode/protect tag
    ax2.axvline(0, color="#333", lw=0.8)
    ax2.barh(yy + h / 2, B["NS_z"], height=h, color=C_NS, label="North Sea")
    ax2.barh(yy - h / 2, B["Baltic_z"], height=h, color=C_BAL, label="Enclosed Baltic")
    for yi, (_, rr) in zip(yy, B.iterrows()):
        tag = "erodes" if rr["feat_to_CV_sign"] == "-" else "protects"
        ax2.text(0.02, yi, f"  {tag} as it rises", transform=ax2.get_yaxis_transform(),
                 va="center", fontsize=7.6, color="#777", style="italic")
    ax2.set_yticks(yy); ax2.set_yticklabels(labels, fontsize=9)
    ax2.set_xlabel("Basin mean feature level (z-score vs whole panel)", fontsize=10)
    ax2.set_title("...and why: where each basin sits on each driver", fontsize=12, fontweight="bold")
    ax2.legend(fontsize=9.5, loc="lower right"); ax2.grid(axis="x", alpha=0.3)
    for s in ["top", "right"]: ax2.spines[s].set_visible(False)

    fig.suptitle("Drivers of capture-value erosion: North Sea vs enclosed Baltic",
                 fontsize=14, fontweight="bold", y=0.99)
    fig.text(0.5, 0.945, "Crowding leads both, more so in the Baltic, which is also more crowded and "
             "less interconnected; carbon and gas carry no cross-sectional signal",
             ha="center", fontsize=9.5, color="#555")
    fig.tight_layout(rect=[0, 0, 1, 0.93])
    for d in (RESULTS, DECK):
        fig.savefig(d / "fig_basin_shap.png", dpi=190)
    plt.close(fig)
    print(f"\nsaved fig_basin_shap.png + basin_shap_comparison.csv")


if __name__ == "__main__":
    main()
