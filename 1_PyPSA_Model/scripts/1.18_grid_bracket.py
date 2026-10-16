"""
1.18_grid_bracket.py — the frozen-vs-optimal grid BRACKET, computed.

The canonical projections freeze transmission at today's volume (v1.0) — the
conservative bound. This script solves the same six scenarios with the volume
constraint DROPPED (vopt = optimal expansion, the optimistic bound) under the
IDENTICAL current engine (fleet, demand rebase, corrections A–F, solver parity),
then tabulates the Baltic aggregate CV under both grids: "the truth lies between"
becomes a table instead of an assertion.

Outputs:
  ~/pypsa-eur/results/scenarios_tyndp_v3_vopt/<scenario>.nc   (6 solves, cached)
  results/projections_v3/grid_bracket.csv + fig_grid_bracket.png

Usage: python 1.18_grid_bracket.py     (~15-25 min first run; cached after)
"""
import importlib.util
import re
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pypsa

HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "results" / "projections_v3"
FROZEN_DIR = Path.home() / "pypsa-eur/results/scenarios_tyndp_v3"
VOPT_DIR = Path.home() / "pypsa-eur/results/scenarios_tyndp_v3_vopt"
VOPT_DIR.mkdir(parents=True, exist_ok=True)

spec = importlib.util.spec_from_file_location("scn07", HERE / "1.07_run_scenarios.py")
SCN = importlib.util.module_from_spec(spec)
spec.loader.exec_module(SCN)
spec13 = importlib.util.spec_from_file_location("sur13", HERE / "1.13_surrogate_runs.py")
sur = importlib.util.module_from_spec(spec13)
spec13.loader.exec_module(sur)

# bias-fit constants from the canonical 1.09 run (parsed, not hardcoded)
meta = (OUT / "fit_metadata.txt").read_text()
A, B = (float(x) for x in re.search(
    r"bias = ([+-][0-9.]+) \+ \+?([0-9.]+) \* pen", meta).groups())
CLAMP = float(re.search(r"penetration clamp: ([0-9.]+)", meta).group(1))
print(f"bias fit from fit_metadata.txt: bias = {A:+.4f} + {B:.4f}*pen, clamp {CLAMP:.3f}\n")

# ---- solve the vopt variants (cached by existence; 1.07 exports atomically)
for name, p in SCN.SCENARIOS.items():
    if (VOPT_DIR / f"{name}.nc").exists():
        print(f"cached: {name} (vopt)")
        continue
    SCN.run(name, p, out_dir=VOPT_DIR, relax_grid=True)

# ---- extract Baltic aggregates under both grids
def baltic_agg(path):
    n = pypsa.Network(path)
    # Finland set aside from the aggregate (nuclear outlier), matching 1.09/7.16.
    rows = [dict(sur.offshore_capture(n, z), zone=z) for z in sur.BALTIC if z != "FI"]
    d = pd.DataFrame(rows)
    prod = d[(d.energy_GWh > 0)].dropna(subset=["CV_raw"])
    w = prod.energy_GWh
    cv_raw = float((prod.CV_raw * w).sum() / w.sum())
    # same clamped correction as 1.09/1.14
    bias = A + B * prod.penetration.clip(upper=CLAMP)
    cv_corr = float(((prod.CV_raw - bias).clip(lower=0) * w).sum() / w.sum())
    return cv_raw, cv_corr

rows = []
for name in SCN.SCENARIOS:
    fr_raw, fr_corr = baltic_agg(FROZEN_DIR / f"{name}.nc")
    vo_raw, vo_corr = baltic_agg(VOPT_DIR / f"{name}.nc")
    rows.append({"scenario": name,
                 "CV_corr_frozen": fr_corr, "CV_corr_vopt": vo_corr,
                 "CV_raw_frozen": fr_raw, "CV_raw_vopt": vo_raw,
                 "bracket_width": vo_corr - fr_corr})
res = pd.DataFrame(rows).set_index("scenario")
res.round(4).to_csv(OUT / "grid_bracket.csv")
print("\nBaltic aggregate CV, frozen grid (conservative) vs optimal grid (optimistic):")
print(res.round(3).to_string())
s40 = [s for s in res.index if s.startswith("2040")]
print(f"\n2040 RAW bracket:       {res.loc[s40,'CV_raw_frozen'].min():.2f}-{res.loc[s40,'CV_raw_frozen'].max():.2f} (frozen)"
      f"  ->  {res.loc[s40,'CV_raw_vopt'].min():.2f}-{res.loc[s40,'CV_raw_vopt'].max():.2f} (optimal)")
print(f"2040 CORRECTED bracket: {res.loc[s40,'CV_corr_frozen'].min():.2f}-{res.loc[s40,'CV_corr_frozen'].max():.2f} (frozen)"
      f"  ->  {res.loc[s40,'CV_corr_vopt'].min():.2f}-{res.loc[s40,'CV_corr_vopt'].max():.2f} (optimal)")

# Show only the bias-corrected bracket (the de-biased estimate), with scenarios
# sorted by value so the decline reads cleanly throughout.
res = res.sort_values("CV_corr_frozen", ascending=False)
fig, ax = plt.subplots(figsize=(8.8, 4.9))
x = np.arange(len(res))
lo = np.minimum(res.CV_corr_frozen, res.CV_corr_vopt)
hi = np.maximum(res.CV_corr_frozen, res.CV_corr_vopt)
ax.fill_between(x, lo, hi, color="#aed6f1", alpha=0.6, label="grid bracket (frozen to optimal)")
ax.plot(x, res.CV_corr_frozen, "s-", color="#10485c", label="frozen grid (today's, conservative)")
ax.plot(x, res.CV_corr_vopt, "o--", color="#2471a3", mfc="white", label="optimal grid expansion")
ax.set_xticks(x)
ax.set_xticklabels(res.index, rotation=20, fontsize=8, ha="right")
ax.set(ylabel="Baltic aggregate capture value (bias-corrected)",
       title="The grid bracket: bias-corrected Baltic capture value under\n"
             "frozen vs optimally expanded transmission")
ax.legend(fontsize=8); ax.grid(axis="y", alpha=0.3)
fig.tight_layout(); fig.savefig(OUT / "fig_grid_bracket.png", dpi=150)
print(f"\nSaved -> {OUT}/grid_bracket.csv + fig_grid_bracket.png")
