"""7.40 - map of the 31 study farms for Chapter 1."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import cartopy.crs as ccrs
import cartopy.feature as cfeature
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
d = pd.read_csv(ROOT / "2_Regression_Model/data/wind_farms_strandA.csv", comment="#")
d = d.dropna(subset=["lat", "lon"])

def group(r):
    if r.country == "FI":
        return "FI"
    if r.bidding_zone in ("DK2", "SE_4", "SE4"):
        return "BO"
    return "NS" if r.basin == "NS" else "UB"
d["grp"] = d.apply(group, axis=1)

COL = {"NS": "#2E6E9E", "UB": "#E0922F", "BO": "#9A3B1B", "FI": "#aab2b9"}
LBL = {"NS": "North Sea (open)", "UB": "Baltic, under-built (PL, EE, LV, LT)",
       "BO": "Baltic, built-out (DK2, SE4)", "FI": "Finland (set aside)"}

fig = plt.figure(figsize=(8.6, 5.6))
ax = plt.axes(projection=ccrs.PlateCarree())
ax.set_extent([-1.5, 29.5, 50.5, 62.5])
ax.add_feature(cfeature.LAND.with_scale("50m"), facecolor="#f2f0eb")
ax.add_feature(cfeature.OCEAN.with_scale("50m"), facecolor="#eaf1f5")
ax.add_feature(cfeature.COASTLINE.with_scale("50m"), lw=0.5, edgecolor="#888")
ax.add_feature(cfeature.BORDERS.with_scale("50m"), lw=0.35, edgecolor="#bbb")
for g in ["NS", "UB", "BO", "FI"]:
    sub = d[d.grp == g]
    ax.scatter(sub.lon, sub.lat, s=18 + sub.capacity_MW / 12, color=COL[g],
               edgecolor="white", linewidth=0.6, alpha=0.95, zorder=5,
               label=LBL[g], transform=ccrs.PlateCarree())
ax.set_title("The 31 study farms, marker size by capacity", fontsize=12)
ax.legend(loc="upper left", fontsize=8.5, framealpha=0.9)
fig.tight_layout()
for out in [ROOT / "7_Thesis_Figures/results/fig_study_farms.png",
            ROOT / "9_Thesis_LaTeX/figures/fig_study_farms.png"]:
    fig.savefig(out, dpi=200, bbox_inches="tight")
print("saved fig_study_farms.png,", len(d), "farms")
