#!/usr/bin/env python
"""The three referenced-but-missing conceptual figures, built to their captions:
  merit_order_effect (Ch2), architecture (Ch3), power_curve (Ch3).
Run with the pypsa-eur env python (matplotlib + scipy)."""
from pathlib import Path
import numpy as np, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
from scipy.ndimage import gaussian_filter1d

OUT = str(Path(__file__).resolve().parents[1] / "9_Thesis_LaTeX/figures")
NAVY="#16293D"; BLUE="#2E6E9E"; ORANGE="#E67E22"; GREY="#9AA6B2"; LGREY="#C9CFD6"; RED="#C0392B"

# ---------------------------------------------------------------- merit order
gens = [("Wind", 1, "#6FA8DC"), ("Nuclear", 12, "#8E7CC3"),
        ("Coal", 45, "#7f7f7f"), ("Gas CCGT", 85, "#E69138"), ("Peaker", 130, "#CC4125")]
caps_low  = {"Wind": 4,  "Nuclear": 8, "Coal": 15, "Gas CCGT": 18, "Peaker": 8}
caps_high = {"Wind": 22, "Nuclear": 8, "Coal": 15, "Gas CCGT": 18, "Peaker": 8}
DEMAND = 35.0

def stack(caps):
    x = 0.0; xs=[]; ys=[]; segs=[]
    for name, cost, col in gens:
        w = caps[name]; xs += [x, x+w]; ys += [cost, cost]; segs.append((x, x+w, cost, col, name)); x += w
    return segs
def clearing(caps):
    x=0.0
    for name, cost, col in gens:
        x += caps[name]
        if x >= DEMAND: return cost
    return gens[-1][1]

fig, ax = plt.subplots(figsize=(8.6, 5.0))
for x0, x1, cost, col, name in stack(caps_high):
    ax.add_patch(plt.Rectangle((x0, 0), x1-x0, cost, color=col, alpha=0.85, ec="white", lw=1.2))
    if x1-x0 > 3:
        ax.text((x0+x1)/2, cost+3, name, ha="center", fontsize=8.5, color=NAVY)
p_low, p_high = clearing(caps_low), clearing(caps_high)
ax.axvline(DEMAND, color=NAVY, lw=1.6, ls=":"); ax.text(DEMAND+0.4, 138, "demand", color=NAVY, fontsize=9)
# low-wind clearing reference (where the stack would clear with little wind)
ax.axhline(p_low, xmax=DEMAND/64, color=RED, lw=1.2, ls="--")
ax.annotate("", xy=(6, p_high), xytext=(6, p_low),
            arrowprops=dict(arrowstyle="->", color=RED, lw=2))
ax.text(7, (p_low+p_high)/2, f"price falls\n{p_low}→{p_high} €/MWh", color=RED, fontsize=9.5, va="center")
ax.text(DEMAND-1, p_high+4, f"clearing price {p_high}", ha="right", color=NAVY, fontsize=9)
ax.set_xlim(0, 64); ax.set_ylim(0, 150)
ax.set_xlabel("Cumulative capacity dispatched (GW)", fontsize=11, color=NAVY)
ax.set_ylabel("Marginal cost / price (€/MWh)", fontsize=11, color=NAVY)
ax.set_title("Merit-order effect of an added wind infeed",
             fontsize=12, color="#111")
for s in ["top","right"]: ax.spines[s].set_visible(False)
fig.tight_layout(); fig.savefig(OUT+"/merit_order_effect.png", dpi=200); plt.close()
print("WROTE merit_order_effect.png")

# ---------------------------------------------------------------- power curve
v = np.linspace(0, 28, 600); dv = v[1]-v[0]
def raw_pc(x):
    ci, vr, co = 3.0, 10.59, 25.0
    p = np.zeros_like(x); r = (x>=ci) & (x<vr)
    p[r] = ((x[r]-ci)/(vr-ci))**3; p[(x>=vr) & (x<co)] = 1.0
    return p
raw = raw_pc(v)
adj = gaussian_filter1d(raw_pc(v-0.71), sigma=1.17/dv)
fig, ax = plt.subplots(figsize=(7.4, 4.6))
ax.plot(v, raw, color=GREY, lw=2, ls="--", label="IEA 15 MW reference (raw)")
ax.plot(v, adj, color=BLUE, lw=2.5, label="after Hayes smoothing + shift")
ax.set_xlim(0, 28); ax.set_ylim(0, 1.08)
ax.set_xlabel("Hub-height wind speed (m s$^{-1}$)", fontsize=11, color=NAVY)
ax.set_ylabel("Normalised power output", fontsize=11, color=NAVY)
ax.set_title("IEA 15 MW power curve, raw and smoothed",
             fontsize=12, color="#111")
ax.legend(fontsize=9.5, loc="lower right")
for s in ["top","right"]: ax.spines[s].set_visible(False)
ax.grid(alpha=0.25)
fig.tight_layout(); fig.savefig(OUT+"/power_curve.png", dpi=200); plt.close()
print("WROTE power_curve.png")

# ---------------------------------------------------------------- architecture
fig, ax = plt.subplots(figsize=(10.4, 5.2)); ax.set_xlim(0, 100); ax.set_ylim(0, 56); ax.axis("off")
def box(x, y, w, h, text, fc, tc=NAVY, fs=10):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.6,rounding_size=2",
                 fc=fc, ec=NAVY, lw=1.3))
    ax.text(x+w/2, y+h/2, text, ha="center", va="center", fontsize=fs, color=tc, wrap=True)
def arrow(x0, y0, x1, y1):
    ax.add_patch(FancyArrowPatch((x0, y0), (x1, y1), arrowstyle="-|>", mutation_scale=16,
                 color=NAVY, lw=1.6))
box(2, 22, 17, 12, "Open data\nENTSO-E  ERA5\nTYNDP", "#EAF1F7", fs=9.5)
box(27, 38, 22, 12, "Empirical regression\nmeasures the past", "#DCEAF6", BLUE, 9.5)
box(27, 6, 22, 12, "PyPSA system model\nprojects the future", "#FDEBD7", "#9c5a12", 9.5)
box(56, 22, 18, 12, "Validation\ntriangle\nvs observed", "#ECECEC", NAVY, 9.5)
box(80, 22, 18, 12, "Projection\n2030 / 2040\n(bias-corrected)", "#E7F0E5", "#3B6D11", 9.5)
arrow(19, 28, 27, 42); arrow(19, 28, 27, 12)
arrow(49, 44, 60, 31); arrow(49, 12, 60, 25)
arrow(74, 28, 80, 28)
ax.set_title("The two-instrument pipeline",
             fontsize=12.5, color="#111", loc="center")
fig.tight_layout(); fig.savefig(OUT+"/architecture.png", dpi=200); plt.close()
print("WROTE architecture.png")
