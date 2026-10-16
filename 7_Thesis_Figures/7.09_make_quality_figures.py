#!/usr/bin/env python
"""New figures requested in the figure-quality review:
  (A) fig_reversal_dumbbell   - the RQ1 reversal as a slope/dumbbell chart
  (B) fig_corr_vs_distance    - Paul-style pairwise correlation vs separation,
                                coloured by within-NS / within-Baltic / cross-basin
Run with the pypsa-eur env python (matplotlib)."""
from pathlib import Path
import numpy as np, pandas as pd, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from itertools import combinations

ROOT = str(Path(__file__).resolve().parents[1])
OUT  = ROOT + "/9_Thesis_LaTeX/figures"
CORRDIR = ROOT + "/2_Regression_Model/results/04_farm_correlation_clusters"

NAVY="#16293D"; BLUE="#2E6E9E"; ORANGE="#E67E22"; GREY="#9AA6B2"; RED="#C0392B"

# Baltic 2040 raw band read live from the solved engine, not hardcoded, so the
# dumbbell never drifts from the headline after a re-solve.
_b = pd.read_csv(ROOT + "/1_PyPSA_Model/results/projections_v3/baltic_cv_fit_corrected.csv", index_col=0)
_b40 = _b.loc[[s for s in _b.index if s.startswith("2040")], "CV_raw"]
BAL_LO, BAL_HI = round(float(_b40.min()), 2), round(float(_b40.max()), 2)
BAL_MID = (BAL_LO + BAL_HI) / 2

# ----------------------------------------------------------------- (A) dumbbell
# Values are the reversal table (tab:reversal); Baltic 2040 is the raw range.
groups = [
    # label, cv_today, cv_2040_lo, cv_2040_hi, colour, bold
    ("North Sea (DE, NL, BE, DK1, FR)", 0.879, 0.61, 0.61, BLUE, True),
    ("Baltic, under-built (PL, EE, LV, LT)", 0.883, BAL_LO, BAL_HI, ORANGE, True),
    ("Baltic, built-out (DK2, SE4)", 0.766, BAL_LO, BAL_HI, ORANGE, False),
]
fin_today = 0.568

fig, ax = plt.subplots(figsize=(9.0, 5.6))
x0, x1 = 0.0, 1.0
for lab, t, lo, hi, col, bold in groups:
    mid = (lo + hi) / 2
    lw = 3.4 if bold else 2.0
    al = 1.0 if bold else 0.55
    ls = "-" if bold else (0, (5, 3))
    ax.plot([x0, x1], [t, mid], color=col, lw=lw, alpha=al, ls=ls, zorder=2,
            solid_capstyle="round", label=lab)
    ax.scatter([x0], [t], s=130, color=col, alpha=al, zorder=3, edgecolor="white", linewidth=1.2)
    if lo != hi:
        ax.plot([x1, x1], [lo, hi], color=col, lw=8, alpha=al*0.4, zorder=2, solid_capstyle="round")
    ax.scatter([x1], [mid], s=130, color=col, alpha=al, zorder=3, edgecolor="white", linewidth=1.2)
# Finland today, set aside
ax.scatter([x0], [fin_today], s=95, color=GREY, zorder=3, edgecolor="white", linewidth=1,
           label="Finland (set aside, nuclear)")

# value annotations
ax.text(x1+0.03, 0.61, "0.61", ha="left", va="center", fontsize=12, color=BLUE, fontweight="bold")
ax.text(x1+0.03, BAL_MID, f"{BAL_LO:.2f}-{BAL_HI:.2f}", ha="left", va="center", fontsize=12, color=ORANGE, fontweight="bold")
ax.annotate("parity at ~0.88", xy=(x0, 0.881), xytext=(0.16, 0.955), fontsize=10.5, color=NAVY,
            style="italic", ha="center", arrowprops=dict(arrowstyle="->", color=NAVY, lw=1))
ax.annotate("North Sea ends on top;\nthe Baltic loses a third to a half",
            xy=(x1, 0.61), xytext=(0.52, 0.80), fontsize=10.5, color=NAVY,
            ha="center", arrowprops=dict(arrowstyle="->", color=NAVY, lw=1.2))
ax.legend(loc="lower left", fontsize=9.5, framealpha=0.92)

ax.set_xlim(-0.12, 1.30); ax.set_ylim(0.30, 1.0)
ax.set_xticks([x0, x1]); ax.set_xticklabels(["2023-24 (measured)", "2040 (projected, raw)"], fontsize=11)
ax.set_ylabel("Capture value", fontsize=11, color=NAVY)
ax.set_title("The ordering reverses: at parity today, the North Sea on top by 2040",
             fontsize=12.5, color=NAVY, fontweight="bold", pad=12)
for s in ["top","right"]: ax.spines[s].set_visible(False)
ax.grid(axis="y", alpha=0.25)
fig.tight_layout()
fig.savefig(OUT + "/fig_reversal_dumbbell.png", dpi=200, bbox_inches="tight")
print("WROTE fig_reversal_dumbbell.png")

# ------------------------------------------------------ (B) corr vs distance
clusters = pd.read_csv(CORRDIR + "/farm_clusters.csv")
C = pd.read_csv(CORRDIR + "/farm_correlation_matrix.csv", index_col=0)
basin = dict(zip(clusters["farm"], clusters["basin"]))
lat = dict(zip(clusters["farm"], clusters["lat"]))
lon = dict(zip(clusters["farm"], clusters["lon"]))

def haversine(a, b):
    R=6371.0
    p1,p2=np.radians(lat[a]),np.radians(lat[b])
    dphi=np.radians(lat[b]-lat[a]); dlmb=np.radians(lon[b]-lon[a])
    h=np.sin(dphi/2)**2+np.cos(p1)*np.cos(p2)*np.sin(dlmb/2)**2
    return 2*R*np.arcsin(np.sqrt(h))

farms=[f for f in C.index if f in basin]
rows=[]
for a,b in combinations(farms,2):
    if a not in C.columns or b not in C.index: continue
    try: r=float(C.loc[a,b])
    except: continue
    d=haversine(a,b)
    if basin[a]=="NS" and basin[b]=="NS": kind="NS-NS"
    elif basin[a]=="Baltic" and basin[b]=="Baltic": kind="BS-BS"
    else: kind="cross"
    rows.append((d,r,kind))
P=pd.DataFrame(rows, columns=["dist","rho","kind"])

fig, ax = plt.subplots(figsize=(8.4, 5.4))
style={"NS-NS":(BLUE,"North Sea pairs","o"),
       "BS-BS":(ORANGE,"Baltic pairs","o"),
       "cross":(GREY,"cross-basin pairs","x")}
for k,(col,lab,mk) in style.items():
    s=P[P.kind==k]
    ax.scatter(s["dist"], s["rho"], c=col,
               label=f"{lab} (mean r={s["rho"].mean():.2f}, median {s["dist"].median():.0f} km)",
               alpha=0.55, s=34, marker=mk, edgecolor="none")
# exponential decay fit to all pairs: r = a*exp(-d/L)+c
from scipy.optimize import curve_fit
def decay(d,a,L,c): return a*np.exp(-d/L)+c
try:
    popt,_=curve_fit(decay, P["dist"], P["rho"], p0=[0.6,400,0.1], maxfev=10000)
    xs=np.linspace(0,P["dist"].max(),200)
    ax.plot(xs, decay(xs,*popt), color=NAVY, lw=2, ls="--",
            label=f"decay fit (length {popt[1]:.0f} km)")
except Exception as e:
    print("fit failed", e)
ax.set_xlabel("Separation distance between farms (km)", fontsize=11)
ax.set_ylabel("Correlation of hourly output", fontsize=11)
ax.set_title("Pairwise output correlation against separation distance",
             fontsize=12.5, color="#111", pad=10)
ax.legend(fontsize=9.5, loc="upper right", framealpha=0.9)
for s in ["top","right"]: ax.spines[s].set_visible(False)
ax.grid(alpha=0.22)
fig.tight_layout()
fig.savefig(OUT + "/fig_corr_vs_distance.png", dpi=200, bbox_inches="tight")
print("WROTE fig_corr_vs_distance.png")

# print the numbers behind it so we can judge the data
print("\n-- within-group means --")
for k in ["NS-NS","BS-BS","cross"]:
    s=P[P.kind==k]
    print(f"  {k}: n={len(s):3d}  mean corr={s["rho"].mean():.3f}  mean dist={s["dist"].mean():.0f} km  median dist={s["dist"].median():.0f} km")
