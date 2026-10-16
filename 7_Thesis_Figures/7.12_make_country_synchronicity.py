"""
7.12_make_country_synchronicity.py — per-country wind synchronicity matrices.

The granular, by-country analogue of the basin correlation figure (and of
Jacquet's Figure 42): one farm-by-farm hourly-output correlation matrix per
country that has more than one study farm, ordered within each by hierarchical
clustering. No cell numbers, RdBu colourbar, farm codes on the axes. Each panel
is titled with its within-country mean pairwise correlation, so the eye can
compare how tightly each country's fleet blows together. Great Britain and the
single-farm countries (FR, EE, LV, LT, FI, SE) are omitted: GB is outside the
market analysis, and a one-farm country has no within-country matrix.

Usage: python 7.12_make_country_synchronicity.py   (env pypsa-eur-arm64)
"""
import glob
import re
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
from scipy.cluster.hierarchy import dendrogram, linkage
from scipy.spatial.distance import squareform

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
REG = ROOT / "2_Regression_Model/data/wind_farms_strandA.csv"
VWF = ROOT / "2_Regression_Model/data/vwf"
OUT = HERE / "results"; OUT.mkdir(exist_ok=True)
GEO = fm.FontProperties(family="Georgia", weight="bold")

# in-scope countries with >1 study farm, ordered North Sea then Baltic
COUNTRIES = [("DE", "Germany", "NS"), ("NL", "Netherlands", "NS"),
             ("BE", "Belgium", "NS"), ("DK", "Denmark", "mixed"),
             ("PL", "Poland", "Baltic")]


def short_code(name):
    cleaned = re.sub(r"[^A-Za-z0-9 ]", " ", name)
    words = [w for w in cleaned.split() if w and not w.isdigit()]
    if not words:
        return name[:4].upper()
    if len(words) == 1:
        return words[0][:4].upper()
    return "".join(w[0] for w in words[:4]).upper()


def clustered_order(C):
    if len(C) < 3:
        return list(C.columns)
    d = 1.0 - C.values
    np.fill_diagonal(d, 0.0); d = (d + d.T) / 2.0
    Z = linkage(squareform(d, checks=False), method="average")
    return [C.columns[i] for i in dendrogram(Z, no_plot=True)["leaves"]]


def main():
    files = sorted(glob.glob(str(VWF / "hourly_cf_*.csv")))
    df = pd.concat([pd.read_csv(f) for f in files], ignore_index=True)
    df = df.drop(columns=[df.columns[0]]).apply(pd.to_numeric, errors="coerce").dropna(axis=1, how="all").dropna()
    reg = pd.read_csv(REG, comment="#").set_index("name")
    fc = {f: reg.at[f, "country"] for f in df.columns if f in reg.index}

    fig = plt.figure(figsize=(14.5, 8.4), dpi=200)
    gs = fig.add_gridspec(2, 3, hspace=0.42, wspace=0.30, top=0.86, bottom=0.07,
                          left=0.06, right=0.96)
    cells = [gs[0, 0], gs[0, 1], gs[0, 2], gs[1, 0], gs[1, 1]]
    im = None
    for (code, name, basin), cell in zip(COUNTRIES, cells):
        farms = [f for f in df.columns if fc.get(f) == code]
        if len(farms) < 2:
            continue
        C = df[farms].corr()
        order = clustered_order(C)
        C = C.loc[order, order]
        n = len(order)
        m = C.values[np.triu_indices(n, 1)].mean()
        ax = fig.add_subplot(cell)
        im = ax.imshow(C.values, cmap="RdBu_r", vmin=-1, vmax=1, aspect="equal")
        codes = [short_code(f) for f in order]
        ax.set_xticks(range(n)); ax.set_yticks(range(n))
        ax.set_xticklabels(codes, rotation=90, fontsize=7)
        ax.set_yticklabels(codes, fontsize=7)
        col = "#C0392B" if basin == "Baltic" else ("#7d5a3c" if basin == "mixed" else "#16293D")
        ax.set_title(f"{name}  (mean r = {m:.2f})", fontsize=11.5,
                     color=col, pad=5)
    # shared colourbar in the 6th cell
    cax = fig.add_subplot(gs[1, 2]); cax.axis("off")
    cb = fig.colorbar(im, ax=cax, fraction=0.5, pad=0.0, aspect=18)
    cb.set_label("correlation of hourly wind output", fontsize=10)
    fig.suptitle("Within-country correlation of hourly wind output",
                 fontsize=14, color="#111", x=0.5, y=0.95)
    fig.savefig(OUT / "fig_country_correlation.png", dpi=200, facecolor="white", bbox_inches="tight")
    print("within-country mean pairwise correlation:")
    for code, name, basin in COUNTRIES:
        farms = [f for f in df.columns if fc.get(f) == code]
        if len(farms) < 2:
            print(f"  {name}: <2 farms, skipped"); continue
        C = df[farms].corr()
        print(f"  {name:12s} ({basin:6s}): {C.values[np.triu_indices(len(farms),1)].mean():.3f}  ({len(farms)} farms)")
    print(f"Saved -> {OUT}/fig_country_correlation.png")


if __name__ == "__main__":
    main()
