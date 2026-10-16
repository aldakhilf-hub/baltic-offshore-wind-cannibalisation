"""
7.14_make_value_maps.py — geographic value maps, 2025 -> 2030 -> 2040.

Supervisor request (meeting 2026-06-22, deck slide 22): a wind-related heat map
over the North Sea and Baltic, each zone a node, evolving across horizons, with
units of capture value or revenue.

Each bubble is a bidding zone, placed at the centroid of its study wind farms.
  colour = offshore-wind capture value (the structural quantity the thesis tracks)
  size   = installed offshore capacity (MW); shows the build-out moving east
Panels share colour and size scales so they read like-for-like.

  2025  = observed (2023-24 generation-weighted), the measured present
  2030  = PyPSA NT-balticHigh projection (raw per-zone capture value, headline)
  2040  = PyPSA NT-balticHigh projection
Price level for the revenue layer comes from the validated surrogate emulator.
Finland is the thesis set-aside (nuclear price collapse, not wind) and is drawn
hollow. GB and Norway are excluded model-limitation zones.

Output -> results/fig_value_maps.png, 10_Presentation/figures/, + value_map_table.csv
"""
from pathlib import Path
import sys, warnings
warnings.filterwarnings("ignore")
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import matplotlib.patheffects as pe
import cartopy.crs as ccrs
import cartopy.feature as cfeature

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OUT = HERE / "results"
DECK = ROOT / "10_Presentation" / "figures"
DECK.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(ROOT / "11_Model_Deliverable"))
import baltic_wind_model as bwm

NS = {"DE", "NL", "BE", "DK1", "FR"}
BAL = {"PL", "EE", "LV", "LT", "FI"}
PREVIEW = {"DK2"}
ZONES = ["DE", "NL", "BE", "DK1", "FR", "PL", "EE", "LV", "LT", "FI", "DK2"]
SETASIDE = {"FI"}


def norm(z):
    return {"DE_LU": "DE", "DK_1": "DK1", "DK_2": "DK2", "SE_4": "SE4"}.get(z, z)


# --- geography + present capacity from the farm registry ------------------- #
reg = pd.read_csv(ROOT / "2_Regression_Model/data/wind_farms_strandA.csv", comment="#")
reg["zone"] = reg.bidding_zone.map(norm)
# DE spans two seas; anchor its bubble in the North Sea where most DE offshore sits
de_ns = reg[(reg.zone == "DE") & (reg.lon < 9)]
cent = reg.groupby("zone")[["lat", "lon"]].mean()
if len(de_ns):
    cent.loc["DE", ["lat", "lon"]] = de_ns[["lat", "lon"]].mean().values
cap_now = reg[reg.status == "operational"].groupby("zone").capacity_MW.sum()


# --- present: observed 2023-24, generation-weighted ------------------------ #
obs = pd.read_csv(ROOT / "2_Regression_Model/data/cv_strandA/monthly_cv_per_farm.csv")
obs["zone"] = obs.bidding_zone.map(norm)
o = obs[obs.year.isin([2023, 2024])].dropna(subset=["CV", "gen_MWh_norm", "capture_price"])


def gw(g, col):
    return np.average(g[col], weights=g.gen_MWh_norm)


pres = o.groupby("zone").apply(lambda g: pd.Series({
    "CV": gw(g, "CV"),
    "capture_price": gw(g, "capture_price"),
    "price_level": gw(g, "baseload"),
    "rev_per_MW": g.groupby("farm").apply(
        lambda f: (f.gen_MWh_norm * f.capture_price).sum() / f.year.nunique()).mean(),
}), include_groups=False)
pres["capacity_MW"] = cap_now.reindex(pres.index).fillna(0.0)


# --- future: PyPSA projection CV + p_nom, surrogate price ------------------ #
proj = pd.read_csv(ROOT / "1_PyPSA_Model/results/projections_v3/projected_capture_values.csv")
rs = pd.read_csv(ROOT / "1_PyPSA_Model/results/surrogate/run_summary.csv")


def levers(scn):
    r = rs[rs.run_id == scn].iloc[0]
    return dict(gas=r.gas, co2=r.co2, demand_multiplier=r.dem_mult,
                baltic_offshore_gw=r.realized_baltic_off, ns_offshore_gw=r.realized_ns_off,
                solar_gw=r.realized_solar, battery_gw=r.realized_batt,
                h2_gw=r.realized_h2, year=int(r.year))


def future(scn):
    d = proj[proj.scenario == scn].copy()
    d["zone"] = d.zone.map(norm)
    d = d.set_index("zone")
    price = bwm.predict(**levers(scn), warn=False).set_index("zone")["wholesale_price_eur_mwh"]
    rows = {}
    for z in ZONES:
        if z not in d.index:
            continue
        cv, cap, en = d.loc[z, "CV"], d.loc[z, "p_nom"], d.loc[z, "energy_GWh"]
        p = float(price.get(z, np.nan))
        rows[z] = dict(CV=cv, capacity_MW=cap, price_level=p, capture_price=cv * p,
                       rev_per_MW=(en * 1e3 / cap) * cv * p if cap > 0 else np.nan)
    return pd.DataFrame(rows).T


SCN_2030, SCN_2040 = "2030-NT-balticBaseline", "2040-NT-balticBaseline"  # central TYNDP buildout
frames = {
    "2025": pres.reindex([z for z in ZONES if z in pres.index]),
    "2030": future(SCN_2030),
    "2040": future(SCN_2040),
}

# tidy table out
tidy = pd.concat({k: v for k, v in frames.items()}, names=["horizon", "zone"]).reset_index()
tidy.to_csv(OUT / "value_map_table.csv", index=False)


# --- plot ------------------------------------------------------------------ #
def msize(mw):
    return 32 + 1.15 * np.sqrt(np.maximum(mw, 0.0))


CMAP, VMIN, VMAX = "RdYlGn", 0.20, 0.95
EXTENT = [-6, 30, 46.5, 63.5]
HALO = [pe.withStroke(linewidth=1.8, foreground="white")]
proj_crs = ccrs.PlateCarree()

titles = {"2025": "2025  ·  today (observed)",
          "2030": "2030  ·  build-out begins",
          "2040": "2040  ·  full build-out"}


def draw(value_col, cmap, vmin, vmax, cbar_label, suptitle, subtitle, fmt, fname):
    fig, axes = plt.subplots(1, 3, figsize=(16, 5.2),
                             subplot_kw={"projection": proj_crs})
    for ax, hz in zip(axes, ["2025", "2030", "2040"]):
        ax.set_extent(EXTENT, crs=proj_crs)
        ax.add_feature(cfeature.OCEAN.with_scale("50m"), facecolor="#eaf2f8")
        ax.add_feature(cfeature.LAND.with_scale("50m"), facecolor="#f4f1ec")
        ax.add_feature(cfeature.COASTLINE.with_scale("50m"), lw=0.4, edgecolor="#888")
        ax.add_feature(cfeature.BORDERS.with_scale("50m"), lw=0.3, edgecolor="#bbb")
        df = frames[hz]
        for z in df.index:
            lat, lon = cent.loc[z, "lat"], cent.loc[z, "lon"]
            val = df.loc[z, value_col]
            hollow = z in SETASIDE
            ax.scatter(lon, lat, s=msize(df.loc[z, "capacity_MW"]),
                       c="none" if hollow else [val], cmap=cmap, vmin=vmin, vmax=vmax,
                       edgecolor=("#777" if hollow else "black"),
                       alpha=(1.0 if hollow else 0.82),
                       linewidth=(1.1 if hollow else 0.7), zorder=5, transform=proj_crs)
            ax.annotate(f"{z} {fmt(val)}", (lon, lat), xytext=(0, 0),
                        textcoords="offset points", ha="center", va="center",
                        fontsize=6.8, fontweight="bold", zorder=6, annotation_clip=True,
                        color=("#555" if hollow else "#111"), path_effects=HALO)
        ax.set_title(titles[hz], fontsize=12, fontweight="bold")
        ax.text(-2.5, 61.7, "NORTH SEA", fontsize=7.5, color="#2471a3", fontweight="bold",
                style="italic", transform=proj_crs, zorder=4, ha="center", path_effects=HALO)
        ax.text(25.0, 61.3, "BALTIC SEA", fontsize=7.5, color="#c0392b", fontweight="bold",
                style="italic", transform=proj_crs, zorder=4, ha="center", path_effects=HALO)

    sm = plt.cm.ScalarMappable(cmap=cmap, norm=plt.Normalize(vmin, vmax))
    cax = fig.add_axes([0.28, 0.135, 0.44, 0.03])
    fig.colorbar(sm, cax=cax, orientation="horizontal").set_label(cbar_label, fontsize=9.5)

    handles = [Line2D([0], [0], marker="o", color="w", markerfacecolor="#bbb",
                      markeredgecolor="k", markersize=2 * np.sqrt(msize(mw) / np.pi),
                      label=f"{mw//1000:g} GW") for mw in (1000, 10000, 40000)]
    axes[2].legend(handles=handles, title="Installed offshore", loc="lower right",
                   fontsize=8, title_fontsize=8, labelspacing=1.4, borderpad=1.0, framealpha=0.9)

    fig.suptitle(suptitle, fontsize=15, fontweight="bold", y=0.965)
    fig.text(0.5, 0.895, subtitle, ha="center", fontsize=10, color="#444")
    fig.subplots_adjust(left=0.01, right=0.99, top=0.85, bottom=0.30, wspace=0.04)
    for d in (OUT, DECK):
        fig.savefig(d / fname, dpi=190)
    plt.close(fig)
    print("saved", fname)


draw("CV", "RdYlGn", 0.20, 0.95,
     "Offshore-wind capture value  (share of the average price the farm earns)",
     "The market value of offshore wind moves east and erodes, 2025 to 2040",
     "Each bubble is a bidding zone at its wind-farm centroid · colour = capture value · "
     "size = installed offshore capacity · Finland (hollow) set aside",
     lambda v: f"{v:.2f}", "fig_value_maps.png")

draw("rev_per_MW", "YlGn", 0, 430_000,
     "Annual market revenue per installed MW  (EUR / MW / year)",
     "Folding in the price level: revenue per installed MW, 2025 to 2040",
     "colour = revenue per MW (capacity factor x capture value x price level) · "
     "size = installed offshore capacity · revenue adds zone-specific price swings to the "
     "capture-value story · Finland (hollow) set aside",
     lambda v: f"{v/1000:.0f}k", "fig_revenue_maps.png")

print(tidy.round(2).to_string(index=False))
