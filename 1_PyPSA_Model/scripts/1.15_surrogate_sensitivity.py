"""
1.15_surrogate_sensitivity.py  ·  TRACK 1 — Surrogate emulator, step 4 of 4

Use the trained surrogate (1.14) as the fast tool it was built to be: sweep
inputs and propagate uncertainty in milliseconds, instead of re-solving PyPSA.
This is the practical payoff of Act 3 — the deliverable a future researcher can
interrogate without Gurobi.

Three products:
  1. One-at-a-time sensitivity sweeps around a reference scenario (2040-NT):
     - gas price          15 -> 100  EUR/MWh_th
     - Baltic offshore    10 -> 150  GW   (the headline cannibalisation axis)
     - North-Sea offshore 30 -> 450  GW
     Plotted as Baltic vs NS capture value, showing where each cannibalises.
  2. A gas x Baltic-offshore response surface (the surrogate's whole point:
     a 2-D map that would cost ~400 PyPSA solves, here ~instant).
  3. Monte-Carlo uncertainty band on the headline NS/Baltic CV asymmetry:
     sample the 8 inputs across the design envelope, predict, summarise.

Reference point = the realized inputs of the 2040-NT-balticHigh canonical run
(read from 1.13's outputs), so the sweeps are anchored on the thesis scenario.

Outputs (../results/surrogate/):
  fig_sensitivity_1d.png        three one-at-a-time sweeps
  fig_response_surface.png      gas x Baltic-offshore CV surface
  sensitivity_montecarlo.csv    MC distribution of the asymmetry ratio
  fig_montecarlo.png            MC histogram

Usage:
  python 1.15_surrogate_sensitivity.py
"""
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import xgboost as xgb
from scipy.stats import qmc

RES = Path(__file__).resolve().parent.parent / "results" / "surrogate"
LONG = RES / "run_outputs.csv"
INPUTS = ["gas", "co2", "dem_mult", "realized_baltic_off", "realized_ns_off",
          "realized_solar", "realized_batt", "realized_h2", "year"]
BALTIC = ["PL", "FI", "EE", "LV", "LT"]
SEED = 20260604


def load_models_and_template():
    cv = xgb.XGBRegressor(); cv.load_model(RES / "surrogate_cv.json")
    pr = xgb.XGBRegressor(); pr.load_model(RES / "surrogate_price.json")
    df = pd.read_csv(LONG)
    zones = sorted(df.zone.unique())
    feat_cols = INPUTS + [f"zone_{z}" for z in zones]
    return cv, pr, df, zones, feat_cols


def make_frame(base, zones, feat_cols, **overrides):
    """Build a prediction frame: one row per zone, base inputs with overrides."""
    rows = []
    for z in zones:
        row = dict(base)
        row.update(overrides)
        for zz in zones:
            row[f"zone_{zz}"] = 1.0 if zz == z else 0.0
        row["_zone"] = z
        rows.append(row)
    f = pd.DataFrame(rows)
    return f, f[feat_cols].astype(float)


def region_cv(cv_model, base, zones, feat_cols, **ov):
    """Predicted Baltic-mean and NS-mean CV for a given input override."""
    f, X = make_frame(base, zones, feat_cols, **ov)
    f["cv"] = cv_model.predict(X)
    bal = f[f._zone.isin(BALTIC)].cv.mean()
    ns = f[~f._zone.isin(BALTIC)].cv.mean()
    return bal, ns


def main():
    if not (RES / "surrogate_cv.json").exists():
        raise SystemExit("missing trained surrogate -- run 1.14 first.")
    cv_model, pr_model, df, zones, feat_cols = load_models_and_template()

    # reference = realized inputs of 2040-NT-balticHigh (one representative row)
    ref_rows = df[df.run_id == "2040-NT-balticHigh"]
    if ref_rows.empty:
        ref_rows = df[df.year == 2040]
    base = {c: float(ref_rows[c].iloc[0]) for c in INPUTS}
    print("Reference inputs (2040-NT-balticHigh):")
    print({k: round(v, 1) for k, v in base.items()})

    # ---------- 1. one-at-a-time sweeps ----------
    sweeps = {
        "gas": ("Gas price (€/MWh_th)", np.linspace(15, 100, 25)),
        "realized_baltic_off": ("Baltic offshore (GW)", np.linspace(10, 150, 25)),
        "realized_ns_off": ("North-Sea offshore (GW)", np.linspace(30, 450, 25)),
    }
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.5))
    for ax, (key, (xlabel, grid)) in zip(axes, sweeps.items()):
        bal, ns = [], []
        for v in grid:
            b, n = region_cv(cv_model, base, zones, feat_cols, **{key: v})
            bal.append(b); ns.append(n)
        ax.plot(grid, bal, "-o", ms=3, color="indianred", label="Baltic")
        ax.plot(grid, ns, "-o", ms=3, color="steelblue", label="North Sea")
        ax.set_xlabel(xlabel); ax.set_ylabel("Predicted capture value")
        ax.grid(alpha=0.3); ax.legend(fontsize=8)
    fig.suptitle("Surrogate one-at-a-time sensitivity (around 2040-NT-balticHigh)")
    plt.tight_layout(); plt.savefig(RES / "fig_sensitivity_1d.png", dpi=200); plt.close()
    print(f"Saved -> {RES/'fig_sensitivity_1d.png'}")

    # ---------- 2. gas x Baltic-offshore response surface ----------
    gg = np.linspace(15, 100, 30)
    bb = np.linspace(10, 150, 30)
    Z = np.zeros((len(bb), len(gg)))
    for i, b_off in enumerate(bb):
        for j, g in enumerate(gg):
            bal, _ = region_cv(cv_model, base, zones, feat_cols,
                               gas=g, realized_baltic_off=b_off)
            Z[i, j] = bal
    fig, ax = plt.subplots(figsize=(8, 6))
    cs = ax.contourf(gg, bb, Z, levels=20, cmap="RdYlBu")
    ax.contour(gg, bb, Z, levels=10, colors="k", linewidths=0.4, alpha=0.5)
    fig.colorbar(cs, label="Predicted Baltic capture value")
    ax.set_xlabel("Gas price (€/MWh_th)"); ax.set_ylabel("Baltic offshore (GW)")
    ax.set_title("Surrogate response surface: Baltic CV vs gas × buildout")
    plt.tight_layout(); plt.close()  # response-surface figure removed 2026-06-15 (hard to read; MC + 1D views kept)

    # ---------- 3. Monte-Carlo uncertainty on the asymmetry ----------
    lo = np.array([15, 50, 1.0, 10, 30, 200, 50, 30])
    hi = np.array([100, 200, 2.0, 150, 450, 1050, 400, 200])
    cols8 = ["gas", "co2", "dem_mult", "realized_baltic_off", "realized_ns_off",
             "realized_solar", "realized_batt", "realized_h2"]
    sample = qmc.scale(qmc.LatinHypercube(d=8, seed=SEED).random(2000), lo, hi)
    mc = []
    for s in sample:
        ov = dict(zip(cols8, s)); ov["year"] = 2040
        bal, ns = region_cv(cv_model, base, zones, feat_cols, **ov)
        if bal and bal == bal and bal != 0:
            mc.append({"baltic_CV": bal, "ns_CV": ns, "ratio_ns_over_baltic": ns / bal,
                       **ov})
    mc = pd.DataFrame(mc)
    mc.to_csv(RES / "sensitivity_montecarlo.csv", index=False)
    q = mc.ratio_ns_over_baltic.quantile([0.05, 0.5, 0.95])
    print(f"\nMonte-Carlo asymmetry (NS CV / Baltic CV) over {len(mc)} samples:")
    print(f"  median {q[0.5]:.2f}  |  90% interval [{q[0.05]:.2f}, {q[0.95]:.2f}]")
    print(f"  Baltic CV: median {mc.baltic_CV.median():.3f} "
          f"[{mc.baltic_CV.quantile(0.05):.3f}, {mc.baltic_CV.quantile(0.95):.3f}]")

    fig, ax = plt.subplots(1, 2, figsize=(12, 4.5))
    ax[0].hist(mc.baltic_CV, bins=40, color="indianred", alpha=0.8)
    ax[0].set_xlabel("Predicted Baltic capture value"); ax[0].set_ylabel("MC samples")
    ax[0].set_title("Baltic CV distribution (2040 envelope)")
    ax[1].hist(mc.ratio_ns_over_baltic.clip(upper=5), bins=40, color="seagreen", alpha=0.8)
    ax[1].axvline(1.0, color="k", ls="--", lw=1)
    ax[1].set_xlabel("NS CV / Baltic CV (asymmetry)"); ax[1].set_ylabel("MC samples")
    ax[1].set_title("Cannibalisation asymmetry distribution")
    plt.tight_layout(); plt.savefig(RES / "fig_montecarlo.png", dpi=200); plt.close()
    print(f"Saved -> {RES/'fig_montecarlo.png'}")


if __name__ == "__main__":
    main()
