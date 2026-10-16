"""
7.02_make_ch4_figures.py — the two figure assemblies Chapter 4 needs that no
track produces directly:

  fig_scarcity_bars.png        4.4.2 — energy-weighted Baltic CV per scenario,
                               all hours vs excluding scarcity-priced hours
                               (>390 EUR/MWh), from 1.17's scarcity_sensitivity.csv.
                               Raw frozen-grid values (the decomposition is
                               computed upstream of the bias correction).
  fig_clusters_matrix_map.png  4.3.3 — the clustered correlation matrix and the
                               geographic cluster map (2.09) side by side, one
                               include for the thesis.
  fig_calibration_cv_2023.png  4.2.2 — observed vs modelled vs hybrid capture
                               value per validation zone, 2023 (replaces fig5,
                               which aggregated DK and lacked the observed bar).

Outputs land in results/ here AND in 9_Thesis_LaTeX/figures/.
Usage: python 7.02_make_ch4_figures.py   (env pypsa-eur)
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from PIL import Image

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PV = ROOT / "1_PyPSA_Model"
REG = ROOT / "2_Regression_Model"
OUT = HERE / "results"
TEX = ROOT / "9_Thesis_LaTeX" / "figures"

C_BAL = "#c0392b"
C_BAL_LIGHT = "#e8a59e"

# ------------------------------------------------ scarcity bars (4.4.2)
df = pd.read_csv(PV / "results/projections_v3/scarcity_sensitivity.csv")
df = df.dropna(subset=["CV_full"])
df = df[df.zone != "FI"]   # Finland set aside from every Baltic aggregate

ORDER = [
    "2030-NT-balticBaseline", "2030-NT-balticHigh",
    "2040-NT-balticBaseline", "2040-NT-balticHigh",
    "2040-DE-balticHigh", "2040-GA-balticHigh",
]
LABELS = [s.replace("-baltic", "\n").replace("Baseline", "baseline")
           .replace("High", "high") for s in ORDER]

rows = []
for sc in ORDER:
    d = df[df.scenario == sc]
    w = d.energy_GWh
    full = float((d.CV_full * w).sum() / w.sum())
    ex = float((d.CV_ex_scarcity * w).sum() / w.sum())
    hrs = int(d.scarcity_hours.max())
    rows.append((sc, full, ex, ex - full, hrs))
    print(f"{sc:28s}  full {full:.3f}  ex-scarcity {ex:.3f}  "
          f"delta {ex-full:+.3f}  max scarcity h {hrs}")

fig, ax = plt.subplots(figsize=(8.5, 4.6))
x = np.arange(len(ORDER))
full_v = [r[1] for r in rows]
ex_v = [r[2] for r in rows]
ax.bar(x - 0.19, full_v, 0.38, color=C_BAL, label="all hours")
ax.bar(x + 0.19, ex_v, 0.38, color=C_BAL_LIGHT, edgecolor=C_BAL,
       label="excluding scarcity-priced hours (>390 EUR/MWh)")
for xi, r in zip(x, rows):
    if abs(r[3]) >= 0.005:
        ax.annotate(f"+{r[3]:.2f}", xy=(xi + 0.19, r[2] + 0.012),
                    ha="center", fontsize=9, fontweight="bold", color=C_BAL)
ax.axhline(0.883, color="grey", ls="--", lw=1)
ax.annotate("observed under-built Baltic, 2023-24 (0.88)",
            xy=(-0.38, 0.891), fontsize=8, color="grey", ha="left")
ax.set_xticks(x)
ax.set_xticklabels(LABELS, fontsize=9)
ax.set_ylabel("Baltic offshore capture value (energy-weighted, raw model)")
ax.set_ylim(0, 1.0)
ax.set_title("Baltic capture value with and without scarcity-priced hours",
             fontsize=11, color="#111")
ax.legend(fontsize=8, loc="upper right")
ax.grid(axis="y", alpha=0.3)
fig.tight_layout()
for dest in (OUT, TEX):
    fig.savefig(dest / "fig_scarcity_bars.png", dpi=200)
plt.close(fig)

# ---------------------------------------- calibration CV bars (4.2.2)
cal = pd.read_csv(PV / "results/calibration_2023/observed_capture_value_comparison.csv")
ZONES = ["DE", "NL", "BE", "DK1", "DK2"]
cal = cal.set_index("zone").loc[ZONES]

fig, ax = plt.subplots(figsize=(8, 4.4))
x = np.arange(len(ZONES))
ax.bar(x - 0.27, cal.CV_obs, 0.27, color="#333333", label="observed")
ax.bar(x, cal.CV_pypsa, 0.27, color="#2471a3", label="model (PyPSA prices)")
ax.bar(x + 0.27, cal.CV_hybrid, 0.27, color="#a9cce3", edgecolor="#2471a3",
       label="hybrid (model generation, observed prices)")
for xi, z in zip(x, ZONES):
    bias = cal.CV_pypsa[z] - cal.CV_obs[z]
    if bias > 0.02:
        ax.annotate(f"+{bias:.2f}", xy=(xi, cal.CV_pypsa[z] + 0.012),
                    ha="center", fontsize=9, fontweight="bold", color="#2471a3")
ax.set_xticks(x)
ax.set_xticklabels(ZONES, fontsize=10)
ax.set_ylabel("Offshore wind capture value, 2023")
ax.set_ylim(0, 1.05)
ax.axhline(1.0, color="grey", ls=":", lw=0.8)
ax.set_title("PyPSA capture value against observation by zone, 2023",
             fontsize=11, color="#111")
ax.legend(fontsize=8, loc="lower left")
ax.grid(axis="y", alpha=0.3)
fig.tight_layout()
for dest in (OUT, TEX):
    fig.savefig(dest / "fig_calibration_cv_2023.png", dpi=200)
plt.close(fig)
print("calibration zones:", ", ".join(
    f"{z} obs {cal.CV_obs[z]:.3f} model {cal.CV_pypsa[z]:.3f} "
    f"hybrid {cal.CV_hybrid[z]:.3f}" for z in ZONES))

# -------------------------------------- clusters matrix + map (4.3.3)
a = Image.open(REG / "results/04_farm_correlation_clusters/fig_farm_correlation_clusters.png")
b = Image.open(REG / "results/04_farm_correlation_clusters/fig_farm_map_clusters.png")
h = a.size[1]
b2 = b.resize((int(b.size[0] * h / b.size[1]), h), Image.LANCZOS)
combo = Image.new("RGB", (a.size[0] + b2.size[0] + 30, h), "white")
combo.paste(a, (0, 0))
combo.paste(b2, (a.size[0] + 30, 0))
for dest in (OUT, TEX):
    combo.save(dest / "fig_clusters_matrix_map.png")
print("clusters combo:", combo.size)
