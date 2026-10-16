"""
2.09_farm_correlation_clusters.py  ·  TRACK 2 — wind-output spatial correlation

Two paired figures, the Baltic/North-Sea analogue of Paul Jacquet's correlation
matrix + farm map:

  (A) Clustered cross-correlation matrix of hourly wind-power output across all
      31 farms. Each cell = Pearson correlation of two farms' hourly output;
      farms are reordered by hierarchical clustering so co-varying farms form the
      dark blocks down the diagonal, outlined and numbered.
  (B) A geographic map of the farms coloured by the SAME clusters, with an
      enclosing ellipse + number per cluster -- so the statistical blocks in (A)
      are tied to real geography.

Cluster numbering is in DIAGONAL ORDER (1 = top-left block of the matrix ... N =
bottom-right), shared by both figures, so the labels are coherent.

Why it matters: farms inside one cluster generate at the SAME hours, depressing
the local price together -- the geographic root of cannibalisation. Tighter,
more isolated Baltic clusters => harder self-cannibalisation, the thesis story.

Input  : ../data/vwf/hourly_cf_YYYY.csv  (timestamp + one column per farm; CF is
          proportional to output and correlation is scale-invariant, so CF
          correlation == output correlation). All years pooled (~70k hours).
         ../data/wind_farms_strandA.csv   (lat/lon/basin/zone for map + labels)

Output : ../results/fig_farm_correlation_clusters.png
         ../results/fig_farm_map_clusters.png
         ../results/farm_correlation_matrix.csv   (clustered order)
         ../results/farm_clusters.csv             (farm -> cluster, diagonal-numbered)

Usage:
  python 2.09_farm_correlation_clusters.py            # default k=8
  python 2.09_farm_correlation_clusters.py --k 7
"""
import argparse
import glob
import re
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Ellipse, Rectangle
from scipy.cluster.hierarchy import dendrogram, fcluster, linkage
from scipy.spatial.distance import squareform

ROOT = Path(__file__).resolve().parent.parent
VWF = ROOT / "data" / "vwf"
REG = ROOT / "data" / "wind_farms_strandA.csv"
OUT = ROOT / "results" / "04_farm_correlation_clusters"
OUT.mkdir(parents=True, exist_ok=True)
PALETTE = plt.get_cmap("tab10").colors + plt.get_cmap("tab20b").colors


def short_code(name):
    cleaned = re.sub(r"[^A-Za-z0-9 ]", " ", name)
    words = [w for w in cleaned.split() if w and not w.isdigit()]
    if not words:
        return name[:4].upper()
    if len(words) == 1:
        return words[0][:4].upper()
    return "".join(w[0] for w in words[:4]).upper()


def load_hourly():
    files = sorted(glob.glob(str(VWF / "hourly_cf_*.csv")))
    df = pd.concat([pd.read_csv(f) for f in files], ignore_index=True)
    df = df.drop(columns=[df.columns[0]]).apply(pd.to_numeric, errors="coerce")
    df = df.dropna(axis=1, how="all").dropna()
    print(f"Pooled {len(files)} years -> {len(df):,} hours × {df.shape[1]} farms")
    return df


def cluster_ellipse_params(lons, lats):
    """Enclosing ellipse (center, width, height, angle deg) for a cluster's points."""
    pts = np.column_stack([lons, lats]).astype(float)
    c = pts.mean(0)
    if len(pts) == 1:
        return c, 1.4, 1.4, 0.0
    cov = np.cov(pts.T)
    vals, vecs = np.linalg.eigh(cov)
    order = np.argsort(vals)[::-1]
    vals, vecs = vals[order], vecs[:, order]
    inv = np.linalg.pinv(cov)
    md = np.sqrt(np.einsum("ij,jk,ik->i", pts - c, inv, pts - c))
    r = (md.max() if np.isfinite(md.max()) and md.max() > 0 else 1.0) * 1.3
    width = max(2 * r * np.sqrt(max(vals[0], 1e-6)), 1.6)
    height = max(2 * r * np.sqrt(max(vals[1], 1e-6)), 1.4)
    angle = np.degrees(np.arctan2(vecs[1, 0], vecs[0, 0]))
    return c, width, height, angle


def make_map(farms, new_clusters, meta, k):
    import cartopy.crs as ccrs
    import cartopy.feature as cf
    from matplotlib.lines import Line2D

    lon = np.array([meta.at[f, "lon"] for f in farms])
    lat = np.array([meta.at[f, "lat"] for f in farms])
    ctry = np.array([meta.at[f, "country"] for f in farms])
    proj = ccrs.PlateCarree()
    fig = plt.figure(figsize=(14, 10))
    ax = plt.axes(projection=proj)
    ax.set_extent([-7, 29, 47.5, 66], crs=proj)
    try:
        ax.add_feature(cf.OCEAN.with_scale("50m"), facecolor="#bcd4e6")
        ax.add_feature(cf.LAND.with_scale("50m"), facecolor="#f4f2ed")
        ax.add_feature(cf.COASTLINE.with_scale("50m"), lw=0.5)
        ax.add_feature(cf.BORDERS.with_scale("50m"), lw=0.4, edgecolor="gray")
    except Exception as e:
        print(f"  (cartopy features unavailable, plain background: {e})")
    gl = ax.gridlines(draw_labels=True, lw=0.3, color="gray", alpha=0.4, ls=":")
    gl.top_labels = gl.right_labels = False

    handles = []
    for cid in sorted(set(new_clusters)):
        idx = [i for i, c in enumerate(new_clusters) if c == cid]
        color = PALETTE[(cid - 1) % len(PALETTE)]
        ax.scatter(lon[idx], lat[idx], s=85, color=color, edgecolor="white",
                   lw=0.8, zorder=6, transform=proj)
        cen, w, h, ang = cluster_ellipse_params(lon[idx], lat[idx])
        ax.add_patch(Ellipse(cen, w, h, angle=ang, facecolor=color, alpha=0.13,
                             edgecolor=color, lw=2.0, zorder=4, transform=proj))
        ax.text(cen[0] + w / 2 * 0.78, cen[1] + h / 2 * 0.78, str(cid),
                fontsize=16, fontweight="bold", color="black",
                path_effects=None, zorder=7, transform=proj)
        # legend label = dominant countries in the cluster
        top = pd.Series(ctry[idx]).value_counts().index[:2]
        handles.append(Line2D([0], [0], marker="o", color="none",
                              markerfacecolor=color, markeredgecolor="white",
                              markersize=9,
                              label=f"{cid}.  {'/'.join(top)}  ({len(idx)} farm{'s' if len(idx)>1 else ''})"))
    ax.legend(handles=handles, title="Correlation cluster", loc="lower right",
              fontsize=9, title_fontsize=10, framealpha=0.92)

    ax.set_title(f"Offshore wind farms grouped by hourly-output correlation (k={k})\n"
                 f"cluster numbers match the cross-correlation matrix", fontsize=13)
    fig.savefig(OUT / "fig_farm_map_clusters.png", dpi=150, bbox_inches="tight")
    plt.close()
    print(f"Saved map -> {OUT/'fig_farm_map_clusters.png'}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--k", type=int, default=8)
    args = ap.parse_args()

    hourly = load_hourly()
    meta = pd.read_csv(REG, comment="#").set_index("name")
    basin = {n: (meta.at[n, "basin"] if n in meta.index else "?") for n in hourly.columns}

    corr = hourly.corr(method="pearson")
    farms = list(corr.columns)

    # hierarchical clustering on 1 - correlation
    dist = 1.0 - corr.values
    np.fill_diagonal(dist, 0.0)
    dist = (dist + dist.T) / 2.0
    Z = linkage(squareform(dist, checks=False), method="average")
    order = dendrogram(Z, no_plot=True)["leaves"]
    raw = fcluster(Z, t=args.k, criterion="maxclust")

    # ---- renumber clusters in DIAGONAL order (first seen along the order = 1) ----
    remap, nxt = {}, 1
    for i in order:
        if raw[i] not in remap:
            remap[raw[i]] = nxt
            nxt += 1
    new_clusters = np.array([remap[c] for c in raw])      # per farm (corr column order)

    ordered = [farms[i] for i in order]
    diag_new = [new_clusters[i] for i in order]           # per diagonal position
    C = corr.loc[ordered, ordered]

    # save tables (diagonal-numbered)
    C.to_csv(OUT / "farm_correlation_matrix.csv")
    pd.DataFrame({"farm": farms, "basin": [basin[f] for f in farms],
                  "code": [short_code(f) for f in farms],
                  "lat": [meta.at[f, "lat"] for f in farms],
                  "lon": [meta.at[f, "lon"] for f in farms],
                  "cluster": new_clusters}).sort_values("cluster").to_csv(
        OUT / "farm_clusters.csv", index=False)

    # ---------- (A) correlation matrix ----------
    n = len(ordered)
    fig, ax = plt.subplots(figsize=(11, 10))
    im = ax.imshow(C.values, cmap="RdBu_r", vmin=-1, vmax=1, aspect="equal")
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04,
                 label="Pearson correlation of hourly output")
    codes = [short_code(f) for f in ordered]
    ax.set_xticks(range(n)); ax.set_yticks(range(n))
    ax.set_xticklabels(codes, rotation=90, fontsize=7)
    ax.set_yticklabels(codes, fontsize=7)
    for tl, f in zip(ax.get_xticklabels(), ordered):
        tl.set_color("firebrick" if basin[f] == "Baltic" else "navy")
    for tl, f in zip(ax.get_yticklabels(), ordered):
        tl.set_color("firebrick" if basin[f] == "Baltic" else "navy")
    start = 0
    for ci in range(1, n + 1):
        if ci == n or diag_new[ci] != diag_new[start]:
            size = ci - start
            ax.add_patch(Rectangle((start - 0.5, start - 0.5), size, size,
                                   fill=False, edgecolor="black", lw=2.2))
            ax.text(ci - 0.5 + 0.25, start - 0.5 + 0.25, str(diag_new[start]),
                    fontsize=12, fontweight="bold", va="top")
            start = ci
    ax.set_title("Cross-correlation of hourly wind-power output: North Sea and Baltic\n"
                 f"(clusters numbered top-left to bottom-right; navy = North Sea, red = Baltic)",
                 fontsize=11)
    plt.tight_layout()
    fig.savefig(OUT / "fig_farm_correlation_clusters.png", dpi=140)
    plt.close()
    print(f"Saved matrix -> {OUT/'fig_farm_correlation_clusters.png'}")

    # ---------- (B) geographic map ----------
    make_map(farms, new_clusters, meta, args.k)

    # ---------- summary ----------
    print(f"\n{args.k} clusters (diagonal-numbered):")
    summ = pd.DataFrame({"farm": farms, "basin": [basin[f] for f in farms],
                         "cluster": new_clusters}).sort_values("cluster")
    for c in sorted(summ.cluster.unique()):
        sub = summ[summ.cluster == c]
        print(f"  cluster {c}: {len(sub):2d} farms "
              f"[{dict(sub.basin.value_counts())}] :: {', '.join(sub.farm)}")
    for b in ["NS", "Baltic"]:
        cols = [f for f in farms if basin[f] == b]
        sub = corr.loc[cols, cols].values
        print(f"  mean pairwise correlation within {b:6s}: "
              f"{sub[np.triu_indices(len(cols), 1)].mean():.3f}")
    ns = [f for f in farms if basin[f] == "NS"]
    ba = [f for f in farms if basin[f] == "Baltic"]
    print(f"  mean cross-basin (NS vs Baltic) correlation: {corr.loc[ns, ba].values.mean():.3f}")


if __name__ == "__main__":
    main()
