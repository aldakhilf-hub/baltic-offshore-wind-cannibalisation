"""
7.04_make_seasonality.py — cross-basin wind synchronicity heatmap
(North Sea aggregate vs Baltic aggregate), the Jacquet Fig-43 idiom but for
basins rather than a single farm pair. Shows which months the two basins blow
together (high correlation, the export valve shut) and which they decouple
(low correlation, the Baltic can export its surplus).

Clean cores only: farms whose hourly output correlates below 0.55 with their
own basin are dropped as geographic outliers (NS: Anholt/Kattegat,
Saint-Brieuc/Brittany, North Sea Energy Island; Baltic: Olhava/Gulf of
Bothnia, Liivi Bay and Saare-Liiv/Gulf of Riga). This leaves a western and
central core in each sea, so the pattern is the basins' shared weather, not a
peripheral site.

Result (literature-consistent): cross-basin correlation is ~0.38 in winter
and ~0.20 in summer, peaking Nov-Jan, bottoming in July (0.13). The basins
share Atlantic storm systems in winter and decouple in summer.

Output -> results/ + 9_Thesis_LaTeX/figures/fig_crossbasin_sync.png
"""
from pathlib import Path
import glob
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OUT = HERE / "results"
TEX = ROOT / "9_Thesis_LaTeX" / "figures"
MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
       "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

df = pd.concat([pd.read_csv(f, parse_dates=[0], index_col=0)
                for f in sorted(glob.glob(str(ROOT / "2_Regression_Model/data/vwf/hourly_cf_*.csv")))]
               ).sort_index()
reg = pd.read_csv(ROOT / "2_Regression_Model/data/wind_farms_strandA.csv", comment="#")
basin = reg.set_index("name").basin.to_dict()
ns = [c for c in df.columns if basin.get(c) == "NS"]
ba = [c for c in df.columns if basin.get(c) == "Baltic"]

def core(cols, thr=0.55):
    keep = [f for f in cols
            if df[f].corr(df[[c for c in cols if c != f]].mean(axis=1)) >= thr]
    return keep

ns_c, ba_c = core(ns), core(ba)
print("NS core", len(ns_c), "| Baltic core", len(ba_c))
print("dropped:", [f for f in ns + ba if f not in ns_c + ba_c])

t = pd.DataFrame({"NS": df[ns_c].mean(axis=1), "BA": df[ba_c].mean(axis=1)})
t["month"], t["hour"] = t.index.month, t.index.hour
mh = (t.groupby(["month", "hour"]).apply(lambda x: x.NS.corr(x.BA),
      include_groups=False).unstack().reindex(range(1, 13)))
mm = t.groupby("month").apply(lambda x: x.NS.corr(x.BA), include_groups=False)

fig, ax = plt.subplots(figsize=(9, 5))
im = ax.imshow(mh.values, aspect="auto", cmap="RdBu_r",
               vmin=0.05, vmax=0.50, origin="upper")
ax.set_yticks(range(12)); ax.set_yticklabels(MON)
ax.set_xticks(range(0, 24, 3)); ax.set_xticklabels(range(0, 24, 3))
ax.set_xlabel("Hour of day (UTC)")
ax.set_title("North Sea to Baltic hourly output correlation by month and hour\n"
             "(2017-2024, basin cores)", fontsize=11, color="#111")
cb = fig.colorbar(im, ax=ax, pad=0.02)
cb.set_label("Pearson correlation")
fig.tight_layout()
for d in (OUT, TEX):
    fig.savefig(d / "fig_crossbasin_sync.png", dpi=200)
print("winter(DJF) %.2f  summer(JJA) %.2f" %
      (mm[[12, 1, 2]].mean(), mm[[6, 7, 8]].mean()))
print("saved fig_crossbasin_sync.png")
