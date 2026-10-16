"""
7.08_make_basin_correlation.py — Jacquet-style clustered correlation matrix + map.

Done exactly like Jacquet's Figure (cross-correlation matrix + farm map): the
ACTUAL farms are labelled and reordered by hierarchical clustering into SMALL
geographic clusters, each outlined by a numbered black box on the matrix (no cell
numbers, no coloured group boxes) and circled with the same number on the map.
Axis labels are coloured only to flag basin membership (navy = North Sea, red =
Baltic), and the within-basin correlation means sit in the subtitle for the RQ2
"enclosed basin blows together" point.

Two panels: (left) the farm-by-farm correlation matrix, clustered; (right) a map
of the farms with the same numbered clusters circled.

Usage: python 7.08_make_basin_correlation.py [--k 8]   (env pypsa-eur-arm64, cartopy)
"""
import argparse
import glob
import re
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
from matplotlib.patches import Rectangle, Ellipse
from matplotlib.lines import Line2D
import matplotlib.patheffects as pe
from scipy.cluster.hierarchy import dendrogram, fcluster, linkage
from scipy.spatial.distance import squareform
import cartopy.crs as ccrs
import cartopy.feature as cf

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
REG = ROOT / "2_Regression_Model/data/wind_farms_strandA.csv"
VWF = ROOT / "2_Regression_Model/data/vwf"
OUT = HERE / "results"; OUT.mkdir(exist_ok=True)

# zone -> analysis group, used only for the within-basin means in the subtitle
GRP = {"DE_LU": "NS", "NL": "NS", "BE": "NS", "DK1": "NS", "FR": "NS",
       "PL": "UB", "EE": "UB", "LV": "UB", "LT": "UB", "DK2": "BO", "SE_4": "BO", "FI": "FI"}
PALETTE = list(plt.get_cmap("tab10").colors) + list(plt.get_cmap("tab20b").colors)
GEO = fm.FontProperties(family="Georgia", weight="bold")


def short_code(name):
    cleaned = re.sub(r"[^A-Za-z0-9 ]", " ", name)
    words = [w for w in cleaned.split() if w and not w.isdigit()]
    if not words:
        return name[:4].upper()
    if len(words) == 1:
        return words[0][:4].upper()
    return "".join(w[0] for w in words[:4]).upper()


def ellipse_params(lons, lats):
    pts = np.column_stack([lons, lats]).astype(float)
    c = pts.mean(0)
    if len(pts) == 1:
        return c, 1.5, 1.5, 0.0
    cov = np.cov(pts.T)
    vals, vecs = np.linalg.eigh(cov)
    o = np.argsort(vals)[::-1]; vals, vecs = vals[o], vecs[:, o]
    md = np.sqrt(np.einsum("ij,jk,ik->i", pts - c, np.linalg.pinv(cov), pts - c))
    r = (md.max() if np.isfinite(md.max()) and md.max() > 0 else 1.0) * 1.35
    w = max(2 * r * np.sqrt(max(vals[0], 1e-6)), 1.7)
    h = max(2 * r * np.sqrt(max(vals[1], 1e-6)), 1.5)
    ang = np.degrees(np.arctan2(vecs[1, 0], vecs[0, 0]))
    return c, w, h, ang


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--k", type=int, default=8)   # Jacquet-style clusters, readable count
    args = ap.parse_args()

    files = sorted(glob.glob(str(VWF / "hourly_cf_*.csv")))
    df = pd.concat([pd.read_csv(f) for f in files], ignore_index=True)
    df = df.drop(columns=[df.columns[0]]).apply(pd.to_numeric, errors="coerce").dropna(axis=1, how="all").dropna()
    reg = pd.read_csv(REG, comment="#").set_index("name")
    farms_all = [f for f in df.columns if f in reg.index and GRP.get(reg.at[f, "bidding_zone"]) is not None]
    df = df[farms_all]
    basin = {f: reg.at[f, "basin"] for f in farms_all}
    grp = {f: GRP[reg.at[f, "bidding_zone"]] for f in farms_all}

    corr = df.corr(method="pearson")
    farms = list(corr.columns)
    dist = 1.0 - corr.values
    np.fill_diagonal(dist, 0.0); dist = (dist + dist.T) / 2.0
    Z = linkage(squareform(dist, checks=False), method="ward")   # balanced, small clusters
    order = dendrogram(Z, no_plot=True)["leaves"]
    raw = fcluster(Z, t=args.k, criterion="maxclust")
    remap, nxt = {}, 1
    for i in order:
        if raw[i] not in remap:
            remap[raw[i]] = nxt; nxt += 1
    clusters = np.array([remap[c] for c in raw])      # per farm (corr order)
    ordered = [farms[i] for i in order]
    diag = [clusters[i] for i in order]               # per diagonal position
    C = corr.loc[ordered, ordered]
    n = len(ordered)

    # Within-basin means are reported at ZONE level, matching the headline numbers
    # used throughout the thesis (the clusters above are at farm level).
    zmap = {}
    for f in farms:
        zmap.setdefault(reg.at[f, "bidding_zone"], []).append(f)
    Zc = pd.DataFrame({z: df[cols].mean(axis=1) for z, cols in zmap.items()})
    zc = Zc.corr()
    def zmean(g):
        zs = [z for z in Zc.columns if GRP.get(z) == g]
        if len(zs) < 2: return float("nan")
        return zc.loc[zs, zs].values[np.triu_indices(len(zs), 1)].mean()
    m_ns, m_ub, m_bo = zmean("NS"), zmean("UB"), zmean("BO")
    nsz = [z for z in Zc.columns if GRP.get(z) == "NS"]
    oz = [z for z in Zc.columns if GRP.get(z) in ("UB", "BO", "FI")]
    m_cross = zc.loc[nsz, oz].values.mean()

    fig = plt.figure(figsize=(15, 6.6), dpi=200)
    gs = fig.add_gridspec(1, 2, width_ratios=[1.05, 1.2], wspace=0.18, top=0.80, bottom=0.10)

    # ---- (A) farm correlation matrix, clustered, Jacquet-style ----
    ax = fig.add_subplot(gs[0, 0])
    im = ax.imshow(C.values, cmap="RdBu_r", vmin=-1, vmax=1, aspect="equal")
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04, label="correlation of hourly output")
    codes = [short_code(f) for f in ordered]
    ax.set_xticks(range(n)); ax.set_yticks(range(n))
    ax.set_xticklabels(codes, rotation=90, fontsize=6.5)
    ax.set_yticklabels(codes, fontsize=6.5)
    def lab_color(f):
        return "#9aa3ab" if grp[f] == "FI" else ("#C0392B" if basin[f] == "Baltic" else "#16293D")
    for tl, f in zip(ax.get_xticklabels(), ordered): tl.set_color(lab_color(f))
    for tl, f in zip(ax.get_yticklabels(), ordered): tl.set_color(lab_color(f))
    # numbered black boxes around each diagonal cluster (no cell numbers)
    start = 0
    for ci in range(1, n + 1):
        if ci == n or diag[ci] != diag[start]:
            size = ci - start
            ax.add_patch(Rectangle((start - 0.5, start - 0.5), size, size,
                                   fill=False, edgecolor="black", lw=2.0, zorder=5))
            ax.text(start - 0.4, start - 0.4, str(diag[start]), fontsize=11,
                    fontweight="bold", va="top", ha="left", color="black", zorder=6)
            start = ci
    ax.set_xlim(-0.5, n - 0.5); ax.set_ylim(n - 0.5, -0.5)
    ax.set_title("Farm-by-farm correlation of hourly wind output, clustered",
                 fontsize=12, color="#111", pad=6)

    # ---- (B) map with the same numbered clusters circled ----
    proj = ccrs.PlateCarree()
    axm = fig.add_subplot(gs[0, 1], projection=proj)
    axm.set_extent([-7, 29, 47.5, 66], crs=proj)
    axm.add_feature(cf.OCEAN.with_scale("50m"), facecolor="#dbe7f0")
    axm.add_feature(cf.LAND.with_scale("50m"), facecolor="#f4f2ed")
    axm.add_feature(cf.COASTLINE.with_scale("50m"), lw=0.5)
    axm.add_feature(cf.BORDERS.with_scale("50m"), lw=0.4, edgecolor="gray")
    gl = axm.gridlines(draw_labels=True, lw=0.3, color="gray", alpha=0.4, ls=":")
    gl.top_labels = gl.right_labels = False
    lon = {f: reg.at[f, "lon"] for f in farms}; lat = {f: reg.at[f, "lat"] for f in farms}
    handles = []
    for cid in sorted(set(clusters)):
        cf_ = [f for f in farms if clusters[farms.index(f)] == cid]
        col = PALETTE[(cid - 1) % len(PALETTE)]
        lons = np.array([lon[f] for f in cf_]); lats = np.array([lat[f] for f in cf_])
        axm.scatter(lons, lats, s=70, color=col, edgecolor="white", lw=0.7, zorder=6, transform=proj)
        cen, w, h, ang = ellipse_params(lons, lats)
        axm.add_patch(Ellipse(cen, w, h, angle=ang, facecolor="none", edgecolor="black",
                              lw=1.6, zorder=5, transform=proj))
        axm.text(cen[0] + w / 2 * 0.82, cen[1] + h / 2 * 0.82, str(cid), fontsize=12,
                 fontweight="bold", color="black", zorder=8, transform=proj,
                 path_effects=[pe.withStroke(linewidth=2.6, foreground="white")])
        ctry = pd.Series([reg.at[f, "country"] for f in cf_]).value_counts().index[:2]
        handles.append(Line2D([0], [0], marker="o", color="none", markerfacecolor=col,
                              markeredgecolor="white", markersize=9,
                              label=f"{cid}.  {'/'.join(ctry)}  ({len(cf_)})"))
    # legend BELOW the map so it never covers the dots
    axm.legend(handles=handles, title="cluster", loc="upper center",
               bbox_to_anchor=(0.5, -0.07), fontsize=8.5, title_fontsize=9,
               framealpha=0.93, ncol=4)
    axm.set_title("Cluster locations", fontsize=12, color="#111", pad=6)

    fig.suptitle("Farm-level output correlation and its spatial clusters",
                 fontsize=14, color="#111", x=0.5, y=0.96)
    fig.savefig(OUT / "fig_basin_correlation.png", dpi=200, facecolor="white", bbox_inches="tight")
    print(f"k={args.k} clusters | within NS {m_ns:.3f} | under-built {m_ub:.3f} | "
          f"built-out {m_bo:.3f} | cross {m_cross:.3f}")
    for cid in sorted(set(clusters)):
        members = [short_code(f) for f in farms if clusters[farms.index(f)] == cid]
        print(f"  cluster {cid}: {len(members)} farms :: {', '.join(members)}")
    print(f"Saved -> {OUT}/fig_basin_correlation.png")


if __name__ == "__main__":
    main()
