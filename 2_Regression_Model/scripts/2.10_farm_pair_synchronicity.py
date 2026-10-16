"""
2.10_farm_pair_synchronicity.py  ·  TRACK 2 — diurnal/seasonal synchronicity

Reproduce Paul Jacquet's Figure 43 (OCC-BARD) for our geography: a month × hour-
of-day heatmap of the cross-correlation between TWO wind farms' hourly output.
Each cell (month m, hour h) is the Pearson correlation of the two farms across
all days/years that fall in that month and that clock hour -- i.e. "do these two
farms blow together at this time of day, this season?".

Paul's pair (OCC Mediterranean vs BARD German North Sea) spans his two basins and
is weakly, patchily correlated (±0.2). Our analogue is North Sea vs Baltic, which
should be even weaker / noisier -- visual evidence that the two seas are
decoupled hour-by-hour, not just on average (cross-basin mean r ~ 0.26 from 2.09).

Input  : ../data/vwf/hourly_cf_YYYY.csv   (timestamp + one column per farm)
Output : ../results/fig_pair_synchronicity_<A>_<B>.png
         ../results/pair_synchronicity_<A>_<B>.csv   (12×24 matrix)

Usage:
  python 2.10_farm_pair_synchronicity.py                          # default NS×Baltic pair
  python 2.10_farm_pair_synchronicity.py --a "Hornsea 2" --b "Klaipeda offshore"
  python 2.10_farm_pair_synchronicity.py --a "Arkona" --b "Baltic Eagle"   # within-basin contrast
"""
import argparse
import glob
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
VWF = ROOT / "data" / "vwf"
OUT = ROOT / "results" / "05_pair_synchronicity"
OUT.mkdir(parents=True, exist_ok=True)
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def load_hourly():
    files = sorted(glob.glob(str(VWF / "hourly_cf_*.csv")))
    df = pd.concat([pd.read_csv(f) for f in files], ignore_index=True)
    tcol = df.columns[0]
    ts = pd.to_datetime(df[tcol], utc=True, errors="coerce")
    df = df.drop(columns=[tcol]).apply(pd.to_numeric, errors="coerce")
    df["month"] = ts.dt.month
    df["hour"] = ts.dt.hour
    return df.dropna(subset=["month", "hour"])


def resolve(name, columns):
    """Allow exact name or case-insensitive substring."""
    if name in columns:
        return name
    hits = [c for c in columns if name.lower() in c.lower()]
    if len(hits) == 1:
        return hits[0]
    raise SystemExit(f"farm '{name}' -> {hits or 'no match'}; be more specific. "
                     f"Available: {list(columns)}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--a", default="Hornsea 2", help="farm A (North Sea by default)")
    ap.add_argument("--b", default="Baltic Power", help="farm B (Baltic by default)")
    ap.add_argument("--vlim", type=float, default=None,
                    help="symmetric colour limit; default = data max|r| (use 0.2 to match Paul)")
    args = ap.parse_args()

    df = load_hourly()
    farms = [c for c in df.columns if c not in ("month", "hour")]
    A, B = resolve(args.a, farms), resolve(args.b, farms)
    overall = df[A].corr(df[B])
    print(f"Pair: '{A}'  ×  '{B}'   |   overall correlation r = {overall:.3f}")

    # 12 × 24 month × hour correlation matrix
    mat = np.full((12, 24), np.nan)
    for (m, h), sub in df.groupby(["month", "hour"]):
        if len(sub) > 5:
            mat[int(m) - 1, int(h)] = sub[A].corr(sub[B])
    M = pd.DataFrame(mat, index=MONTHS, columns=range(24))
    safe = lambda s: s.replace(" ", "").replace("/", "")[:10]
    M.to_csv(OUT / f"pair_synchronicity_{safe(A)}_{safe(B)}.csv")

    vlim = args.vlim if args.vlim else max(np.nanmax(np.abs(mat)), 0.05)
    fig, ax = plt.subplots(figsize=(13, 5.5))
    im = ax.imshow(mat, cmap="RdBu_r", vmin=-vlim, vmax=vlim,
                   aspect="auto", origin="lower")
    cbar = fig.colorbar(im, ax=ax, pad=0.02)
    cbar.set_label("Correlation")
    ax.set_xticks(range(24)); ax.set_xticklabels(range(24))
    ax.set_yticks(range(12)); ax.set_yticklabels(MONTHS)
    ax.set_xlabel("Hour"); ax.set_ylabel("Month")
    ax.set_title(f"Diurnal/seasonal synchronicity of hourly output: {A}  ×  {B}\n"
                 f"(overall r = {overall:.3f}; colour scale ±{vlim:.2f})", fontsize=11)
    plt.tight_layout()
    out = OUT / f"fig_pair_synchronicity_{safe(A)}_{safe(B)}.png"
    fig.savefig(out, dpi=140)
    plt.close()
    print(f"Saved -> {out}")
    print(f"  month×hour correlation range: [{np.nanmin(mat):.3f}, {np.nanmax(mat):.3f}], "
          f"mean {np.nanmean(mat):.3f}")


if __name__ == "__main__":
    main()
