"""
7.06_make_revenue_decomp.py — revenue decomposition (Jacquet Fig 44 analogue).
Market revenue per MW = hours x capacity factor x capture value x price level.
This figure shows the three time-varying terms separately, 2017-2024, by basin,
to establish which one carries the structural trend: capacity factor is
weather-driven and roughly flat, the price level is dominated by the 2022
fuel crisis, and capture value is the term with the persistent downward
drift. That is why the thesis tracks capture value, and why projected revenue
scales with it at a given capacity factor and price level.

Output -> results/ + 9_Thesis_LaTeX/figures/fig_revenue_decomp.png
"""
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OUT = HERE / "results"
TEX = ROOT / "9_Thesis_LaTeX" / "figures"
C_NS, C_BAL = "#2471a3", "#c0392b"

cv = pd.read_csv(ROOT / "2_Regression_Model/data/cv_strandA/monthly_cv_per_farm.csv").dropna(subset=["CV", "gen_MWh_norm", "baseload"])

def basin_year(basin):
    d = cv[cv.basin == basin]
    cf = d.groupby("year").gen_MWh_norm.mean()
    cf = cf / cf.loc[2017:2019].mean()          # index to pre-crisis mean
    price = d.groupby("year").baseload.mean()
    capv = d.groupby("year").apply(
        lambda x: (x.CV * x.gen_MWh_norm).sum() / x.gen_MWh_norm.sum(),
        include_groups=False)
    return cf, price, capv

panels = [("Capacity factor (indexed to 2017--19)", 0),
          ("Price level (\\euro/MWh)", 1),
          ("Capture value", 2)]
fig, axes = plt.subplots(1, 3, figsize=(13, 4.2))
for basin, c in [("NS", C_NS), ("Baltic", C_BAL)]:
    cf, price, capv = basin_year(basin)
    axes[0].plot(cf.index, cf.values, color=c, marker="o", ms=3, label=basin)
    axes[1].plot(price.index, price.values, color=c, marker="o", ms=3)
    axes[2].plot(capv.index, capv.values, color=c, marker="o", ms=3)
titles = ["Capacity factor (indexed to 2017--19)", "Price level (EUR/MWh)",
          "Capture value"]
for ax, t in zip(axes, titles):
    ax.set_title(t, fontsize=10); ax.grid(alpha=0.3); ax.set_xlabel("Year")
axes[0].legend(fontsize=9)
axes[0].set_ylim(0.7, 1.3)
fig.suptitle("Decomposition of revenue per MW, 2017-2024", fontsize=11.5, color="#111")
fig.tight_layout()
for d in (OUT, TEX):
    fig.savefig(d / "fig_revenue_decomp.png", dpi=200)
# numbers
for basin in ("NS", "Baltic"):
    cf, price, capv = basin_year(basin)
    print(f"{basin}: CF 2017 {cf.loc[2017]:.2f} 2024 {cf.loc[2024]:.2f} | "
          f"price 2021 {price.loc[2021]:.0f} 2022 {price.loc[2022]:.0f} | "
          f"CV 2017 {capv.loc[2017]:.3f} 2024 {capv.loc[2024]:.3f}")
print("saved fig_revenue_decomp.png")
