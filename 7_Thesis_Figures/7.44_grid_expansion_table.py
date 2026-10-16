"""Transmission capacity added by the least-cost grid (2040 National Trends,
expanded minus frozen network), summarised by scope. Writes results/
tab_grid_expansion.csv, a white-background PNG of the table, and prints a
booktabs LaTeX table for the appendix."""
from pathlib import Path
import pypsa, pandas as pd, numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

OUT = Path(__file__).resolve().parent / "results"
F = Path.home() / "pypsa-eur/results/scenarios_tyndp_v3/2040-NT-balticBaseline.nc"
V = Path.home() / "pypsa-eur/results/scenarios_tyndp_v3_vopt/2040-NT-balticBaseline.nc"
nv = pypsa.Network(str(V))

def zone(b):
    b = str(b)
    return "DK1" if b.startswith("DK1") else "DK2" if b.startswith("DK2") else b[:2]

L = nv.lines.copy(); L["added"] = (L.s_nom_opt - L.s_nom).clip(lower=0)
L["cap0"] = L.s_nom; L["cc"] = L.capital_cost
D = nv.links[nv.links.carrier == "DC"].copy(); D["added"] = (D.p_nom_opt - D.p_nom).clip(lower=0)
D["cap0"] = D.p_nom; D["cc"] = D.capital_cost
cols = ["bus0", "bus1", "length", "cap0", "added", "cc"]
A = pd.concat([L[cols], D[cols]])
A["z0"] = A.bus0.map(zone); A["z1"] = A.bus1.map(zone)
A["twkm"] = A.added * A.length / 1e6
A["cost"] = A.added * A.cc / 1e9
A["cross"] = A.z0 != A.z1
BAL = {"PL", "EE", "LV", "LT"}; RIM = BAL | {"FI", "SE", "DK2"}
A["baltic"] = A.z0.isin(BAL) | A.z1.isin(BAL)
A["rim"] = A.z0.isin(RIM) | A.z1.isin(RIM)

scopes = [("Whole model (AC lines and DC links)", A.added >= 0),
          ("Cross-border corridors only", A.cross),
          ("Corridors touching PL, EE, LV, LT", A.baltic),
          ("Cross-border, touching PL, EE, LV, LT", A.baltic & A.cross),
          ("Baltic rim including FI, SE, DK2", A.rim)]
rows = []
for label, m in scopes:
    s = A[m]
    add, ex = s.added.sum() / 1e3, s.cap0.sum() / 1e3
    rows.append({"scope": label, "added_GW": round(add, 1), "added_TWkm": round(s.twkm.sum(), 1),
                 "existing_GW": round(ex, 1), "change_pct": round(100 * add / ex), "cost_bn_per_yr": round(s.cost.sum(), 2)})
T = pd.DataFrame(rows)
T.to_csv(OUT / "tab_grid_expansion.csv", index=False)
print(T.to_string(index=False))

def fmt_gw(v): return f"{v:.0f} GW" if v >= 30 else f"{v:.1f} GW"
disp = [[r.scope,
         (f"{fmt_gw(r.added_GW)}, {r.added_TWkm:.0f} TWkm" if i == 0 else fmt_gw(r.added_GW)),
         f"+{r.change_pct:.0f}% on {fmt_gw(r.existing_GW)}",
         f"{r.cost_bn_per_yr:.2f}"] for i, r in T.iterrows()]
hdr = ["Scope of the least-cost expansion", "Added capacity", "Change on existing", "Annualised cost\n(bn EUR per year)"]

fig, ax = plt.subplots(figsize=(9.8, 2.75), dpi=300)
ax.axis("off"); ax.set_xlim(0, 1); ax.set_ylim(0, 1)
xs = [(0.01, "left"), (0.555, "right"), (0.765, "right"), (0.99, "right")]
ys = [0.70, 0.56, 0.42, 0.28, 0.14]
hdr2 = ["Scope of the least-cost expansion", "Added capacity", "Change on existing", "Annualised cost\n(bn EUR per year)"]
for (x, ha), h in zip(xs, hdr2):
    ax.text(x, 0.885, h, ha=ha, va="center", fontsize=10.5, fontweight="bold", color="#111111", linespacing=1.15)
for y, row in zip(ys, disp):
    for (x, ha), v in zip(xs, row):
        ax.text(x, y, v, ha=ha, va="center", fontsize=10.5, color="#111111")
for yy, lw in ((0.975, 1.0), (0.795, 0.6), (0.045, 1.0)):
    ax.plot([0, 1], [yy, yy], color="#111111", lw=lw, clip_on=False)
fig.savefig(OUT / "tab_grid_expansion.png", dpi=300, facecolor="white", bbox_inches="tight", pad_inches=0.12)
print("saved", OUT / "tab_grid_expansion.png")

print("\n%% ---- paste-ready LaTeX ----")
print(r"\begin{table}[htbp]")
print(r"\centering")
print(r"\caption{Transmission capacity added by the least-cost grid in the 2040 National Trends case, expanded network minus the frozen network. Cost is the annualised capital cost of the added lines and links; the whole-model figure reconciles with Table~\ref{tab:congestion_rent}.}")
print(r"\label{tab:grid_expansion}")
print(r"\begin{tabular}{lrrr}")
print(r"\toprule")
print(r"Scope of the least-cost expansion & Added capacity & Change on existing & Annualised cost (bn EUR/yr) \\")
print(r"\midrule")
for row in disp:
    print(" & ".join(x.replace("%", r"\%") for x in row) + r" \\")
print(r"\bottomrule")
print(r"\end{tabular}")
print(r"\end{table}")
