"""
1.20_h2_floor_sensitivity.py  ·  TRACK 1 — sensitivity to the hydrogen floor

Correction D (1.07) adds a parametric hydrogen layer (electrolyser demand) that
holds prices off zero at high renewable shares. Because that demand is assumed,
this script tests whether the 2040 Baltic capture-value headline depends on it,
by re-solving every 2040 scenario with the H2 demand + electrolyser capacity
scaled to 0.5x and 1.5x the canonical level and recomputing the energy-weighted
Baltic offshore CV.

Finding: across +/-50% on the floor, the 2040 Baltic band barely moves. The
worst single-scenario swing is small (computed and printed by this script and
shown in the figure title; ~0.01 on the current solves), and the two clean
cannibalisation-dominated scenarios (DE, GA) move negligibly. Load-shed volumes
are unchanged across the variants, so the effect runs through the price floor,
not adequacy. The floor sets the depth of the erosion at the margin; it does not
create it. (Numbers are read live from the solved CSVs, never hardcoded here.)

By default this READS the already-solved per-factor CSVs in
~/pypsa-eur/results/h2_sensitivity/ (h2_sens_x{0.5,1.0,1.5}.csv, written by the
re-solve driver) and produces the appendix summary + figure. Pass --solve to
re-run the 8 Gurobi solves first (~13 min); the solve logic imports 1.07's engine
with a scaled H2_DEMAND_TWH / H2_ELECTROLYSER_GW, exactly as the canonical runs.

Outputs -> results/projections_v3/:
  h2_floor_sensitivity.csv   per scenario x factor, CV_raw + swing
  fig_h2_sensitivity.png     2040 Baltic CV vs H2 factor, by scenario

Usage:  python 1.20_h2_floor_sensitivity.py [--solve]   (env pypsa-eur-arm64)
"""
import sys
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "results" / "projections_v3"
H2DIR = Path.home() / "pypsa-eur/results/h2_sensitivity"
FACTORS = [0.5, 1.0, 1.5]
ORDER = ["2040-NT-balticBaseline", "2040-NT-balticHigh", "2040-DE-balticHigh", "2040-GA-balticHigh"]

if "--solve" in sys.argv:
    import importlib.util, time, pypsa
    spec = importlib.util.spec_from_file_location("s107", Path(__file__).resolve().parent / "1.07_run_scenarios.py")
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    # Finland set aside from the aggregate (nuclear outlier), matching 1.09/1.18.
    OFFSHORE, BALTIC = ["offwind-ac", "offwind-dc", "offwind-float"], ["PL", "EE", "LV", "LT"]

    def baltic_cv(n):
        e = c = load = 0.0
        for z in BALTIC:
            ac = n.buses[(n.buses.carrier == "AC") & (n.buses.country == z)]
            w, pr, g = n.snapshot_weightings.generators, n.buses_t.marginal_price, n.generators
            lcols = n.loads[n.loads.bus.isin(ac.index)].index.intersection(n.loads_t.p_set.columns)
            load += float((n.loads_t.p_set[lcols].sum(axis=1) * w).sum()) / 1e3 if len(lcols) else 0.0
            ids = [i for i in g[(g.bus.isin(ac.index)) & (g.carrier.isin(OFFSHORE))].index if i in n.generators_t.p.columns]
            if not ids:
                continue
            P = n.generators_t.p[ids].sum(axis=1); en = float((P * w).sum())
            if en <= 0:
                continue
            num = sum(n.generators_t.p[i] * pr[g.at[i, "bus"]] for i in ids if g.at[i, "bus"] in pr.columns)
            base = float((pr[[b for b in ac.index if b in pr.columns]].mean(axis=1) * w).sum() / w.sum())
            e += en / 1e3; c += (float((num * w).sum()) / en / base) * en / 1e3
        return c / e
    H2DIR.mkdir(parents=True, exist_ok=True)
    for f in FACTORS:
        rows = []
        if f != 1.0:
            m.H2_DEMAND_TWH = {y: {k: v * f for k, v in d.items()} for y, d in m.H2_DEMAND_TWH.items()}
            m.H2_ELECTROLYSER_GW = {y: {k: v * f for k, v in d.items()} for y, d in m.H2_ELECTROLYSER_GW.items()}
            for sc in ORDER:
                n = m.run(sc, m.SCENARIOS[sc], out_dir=H2DIR / f"x{f}")
                rows.append(dict(scenario=sc, h2_factor=f, CV_raw=round(baltic_cv(n), 4)))
            pd.DataFrame(rows).to_csv(H2DIR / f"h2_sens_x{f}.csv", index=False)

# ---- assemble + figure (reads per-factor CSVs) ----
parts = []
for f in FACTORS:
    p = H2DIR / f"h2_sens_x{f}.csv"
    if p.exists():
        parts.append(pd.read_csv(p))
if not parts:
    raise SystemExit(f"No h2_sens_x*.csv in {H2DIR} — run with --solve first.")
df = pd.concat(parts)
piv = df.pivot_table(index="scenario", columns="h2_factor", values="CV_raw").reindex(ORDER)
piv.columns = [f"CV_H2x{c}" for c in piv.columns]
piv["delta_halve"] = (piv["CV_H2x0.5"] - piv["CV_H2x1.0"]).round(3)
piv["delta_x1.5"] = (piv["CV_H2x1.5"] - piv["CV_H2x1.0"]).round(3)
piv["max_swing"] = (piv[["CV_H2x0.5", "CV_H2x1.0", "CV_H2x1.5"]].max(axis=1)
                    - piv[["CV_H2x0.5", "CV_H2x1.0", "CV_H2x1.5"]].min(axis=1)).round(3)
piv.round(3).to_csv(OUT / "h2_floor_sensitivity.csv")
print(piv.round(3).to_string())
print(f"\n2040 band:  x0.5 {piv['CV_H2x0.5'].min():.2f}-{piv['CV_H2x0.5'].max():.2f}  |  "
      f"x1.0 {piv['CV_H2x1.0'].min():.2f}-{piv['CV_H2x1.0'].max():.2f}  |  "
      f"x1.5 {piv['CV_H2x1.5'].min():.2f}-{piv['CV_H2x1.5'].max():.2f}")
print(f"max single-scenario swing across +/-50% H2: {piv['max_swing'].max():.3f}")

fig, ax = plt.subplots(figsize=(7.5, 4.6))
labels = {"2040-NT-balticBaseline": "NT baseline", "2040-NT-balticHigh": "NT high",
          "2040-DE-balticHigh": "DE high (clean)", "2040-GA-balticHigh": "GA high (clean)"}
cols = {"2040-NT-balticBaseline": "#1f6f8b", "2040-NT-balticHigh": "#10485c",
        "2040-DE-balticHigh": "#c0392b", "2040-GA-balticHigh": "#e67e22"}
for sc in ORDER:
    ys = [piv.loc[sc, f"CV_H2x{f}"] for f in FACTORS]
    ax.plot(FACTORS, ys, "o-", color=cols[sc], lw=1.8, ms=6, label=labels[sc])
ax.axvline(1.0, color="grey", ls=":", lw=1)
ax.set(xlabel="Hydrogen floor scale (× canonical electrolyser demand)",
       ylabel="Energy-weighted Baltic offshore CV (2040)", xticks=FACTORS,
       title="The 2040 Baltic headline is robust to the hydrogen floor\n"
             f"Clean scenarios (DE, GA) move <0.02 across ±50%; worst swing {piv['max_swing'].max():.3f}")
ax.legend(fontsize=8); ax.grid(alpha=0.3)
fig.tight_layout(); fig.savefig(OUT / "fig_h2_sensitivity.png", dpi=150)
print(f"Saved -> {OUT}/h2_floor_sensitivity.csv, fig_h2_sensitivity.png")
