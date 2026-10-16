"""
11_gas_shock_capture_values.py

Reads the gas-shock x buildout networks (script 10) and builds the offshore
capture-value RESPONSE SURFACE to gas-price shocks.

PER-ZONE coverage: every offshore-bearing zone in the system is included (GB is
the largest, ~52 GW; the earlier 2-region shortcut wrongly dropped GB/IE/NO/SE).
Each (scenario, zone) becomes one point at its own penetration, so the central
question -- does capture value fall more steeply under gas shocks as penetration
rises, and is that the same in both seas? -- is tested across the whole fleet.

Basin assignment (geographic):
  Baltic-facing : PL FI EE LV LT + DK2 (Kriegers Flak/Rodsand) + SE
  North-Sea     : DE NL BE FR DK1 GB IE NO
  CAVEAT (audit): "SE" here is ALL of Sweden — at 30-cluster resolution the
  Swedish offshore generators cannot be split east/west coast (one cluster
  spans both). SE is a material share of the Baltic aggregate, so the region
  means are ALSO reported ex-SE as a sensitivity; state the all-Sweden
  attribution in the thesis.

CV method mirrors 08_projected_capture_values.offshore_capture() (kept local to
avoid 08's import-time side effects).

Inputs:  ~/pypsa-eur/results/gas_shock/<scenario>__gas<g>.nc
Outputs: results/gas_shock/
  gas_shock_capture_values.csv   per scenario x gas x ZONE -> CV, pen, energy, price
  gas_shock_region_means.csv     energy-weighted Baltic vs NS aggregate per gas
  gas_shock_sensitivity.csv      per (scenario, zone) slope dCV/dgas vs penetration
  fig_gas_shock_cv.png           region-aggregate CV vs gas
  fig_gas_shock_sensitivity.png  per-zone slope vs penetration (the headline)

Usage:  python 11_gas_shock_capture_values.py
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pypsa

ROOT = Path(__file__).resolve().parent.parent
GAS_DIR = Path.home() / "pypsa-eur/results/gas_shock"
OUT = ROOT / "results" / "gas_shock"
OUT.mkdir(parents=True, exist_ok=True)

OFFSHORE = ["offwind-ac", "offwind-dc", "offwind-float"]
DK_LON_CUT = 11.0
# every offshore-bearing zone -> basin (DK split by longitude; SE/DK2 are Baltic-facing)
ZONE_BASIN = {
    "DE": "NorthSea", "NL": "NorthSea", "BE": "NorthSea", "FR": "NorthSea",
    "DK1": "NorthSea", "GB": "NorthSea", "IE": "NorthSea", "NO": "NorthSea",
    "PL": "Baltic", "FI": "Baltic", "EE": "Baltic", "LV": "Baltic", "LT": "Baltic",
    "DK2": "Baltic", "SE": "Baltic",
}
MIN_ENERGY_GWH = 500.0   # ignore trivially-small offshore zones in slope fits
# Documented model-limitation zones, kept in the full per-zone table for
# transparency but excluded from headline aggregates + trend fits:
#  GB — island over-supply, structurally under-priced, no post-Brexit
#       observed prices to validate against; behaves anomalously.
#  NO — internally grid/power-constrained at 3-cluster resolution under the
#       frozen line volume (real NO1-NO5 moves hydro to the load centres);
#       one cluster prices at scarcity ~20% of hours in 2040, inflating the
#       country mean to ~800 EUR/MWh — a resolution artifact, not physics.
HEADLINE_EXCLUDE = ["GB", "NO"]


def zone_buses(n, zone):
    ac = n.buses[n.buses.carrier == "AC"]
    if zone in ("DK1", "DK2"):
        dk = ac[ac.country == "DK"]
        west = dk.x < DK_LON_CUT
        return list(dk[west if zone == "DK1" else ~west].index)
    return list(ac[ac.country == zone].index)


def offshore_capture(n, zone):
    """(energy_GWh, load_GWh, penetration, CV) for offshore wind in a zone.
    Snapshot-weighted; zone load is returned so regional penetration can be a
    TRUE ratio of sums rather than an energy-weighted mean of zone ratios."""
    buses = zone_buses(n, zone)
    prices = n.buses_t.marginal_price
    g = n.generators
    w = n.snapshot_weightings.generators
    loads = n.loads[n.loads.bus.isin(buses)]
    lcols = loads.index.intersection(n.loads_t.p_set.columns)
    load_energy = float((n.loads_t.p_set[lcols].sum(axis=1) * w).sum()) if len(lcols) else np.nan
    load_gwh = load_energy / 1e3 if load_energy == load_energy else np.nan
    ids = [i for i in g[(g.bus.isin(buses)) & (g.carrier.isin(OFFSHORE))].index
           if i in n.generators_t.p.columns]
    if not ids:
        return dict(energy_GWh=0.0, load_GWh=load_gwh, penetration=np.nan, CV=np.nan)
    P = n.generators_t.p[ids].sum(axis=1)
    energy = float((P * w).sum())
    if energy <= 0:
        return dict(energy_GWh=0.0, load_GWh=load_gwh, penetration=np.nan, CV=np.nan)
    num = pd.Series(0.0, index=P.index)
    for gid in ids:
        bus = g.at[gid, "bus"]
        if bus in prices.columns:
            num += n.generators_t.p[gid] * prices[bus]
    capture_price = float((num * w).sum()) / energy
    pbuses = [b for b in buses if b in prices.columns]
    base = float((prices[pbuses].mean(axis=1) * w).sum() / w.sum())
    pen = energy / load_energy if load_energy and load_energy > 0 else np.nan
    return dict(energy_GWh=energy / 1e3, load_GWh=load_gwh, penetration=pen,
                CV=capture_price / base if base else np.nan)


EXPECTED_GRID = {("2030-NT-balticBaseline", g) for g in [15, 30, 50, 80, 120]} | \
                {("2040-NT-balticBaseline", g) for g in [15, 30, 50, 80, 120]} | \
                {("2040-NT-balticHigh", g) for g in [15, 30, 50, 80, 120]}


def main():
    nets = sorted(GAS_DIR.glob("*__gas*.nc"))
    if not nets:
        print(f"No gas-shock networks in {GAS_DIR} -- run script 10 first.")
        return
    # completeness guard: a silently missing cell truncates that scenario's
    # slope fit and corrupts CV_lowgas/CV_highgas comparability (audit finding)
    found = {(p.stem.split("__gas")[0], int(p.stem.split("__gas")[1])) for p in nets}
    missing = EXPECTED_GRID - found
    if missing:
        print(f"WARNING: gas grid INCOMPLETE — missing {sorted(missing)}.")
        print("         Slopes for those scenarios are fit on a truncated gas range.")
        print("         Fill with: python 1.10_gas_shock_grid.py <scenario> <gas>")
    print(f"Reading {len(nets)} gas-shock networks (all offshore zones) ...")
    rows = []
    for p in nets:
        scenario, gas = p.stem.split("__gas")
        n = pypsa.Network(p)
        for zone, basin in ZONE_BASIN.items():
            r = offshore_capture(n, zone)
            # keep zero-offshore zones too: their load belongs in the TRUE
            # regional penetration denominator
            rows.append({"scenario": scenario, "year": int(scenario[:4]),
                         "buildout": scenario.split("-")[-1], "gas": int(gas),
                         "zone": zone, "basin": basin, **r})
        print(f"  {p.stem}")
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "gas_shock_capture_values.csv", index=False)

    # ---- energy-weighted region aggregate (GB excluded -- see note) ------
    def wmean(s, w):
        m = s.notna() & w.notna()
        return (s[m] * w[m]).sum() / w[m].sum() if w[m].sum() else np.nan

    def region_agg(d):
        """Energy-weighted CV; penetration as TRUE ratio of sums (audit fix:
        the energy-weighted mean of zone ratios overstated regional
        penetration ~2.4-3x and was quotable as 'penetration')."""
        prod = d[d.energy_GWh > 0]
        return pd.Series({
            "CV": wmean(prod.CV, prod.energy_GWh),
            "penetration": (prod.energy_GWh.sum() / d.load_GWh.sum()
                            if d.load_GWh.sum() > 0 else np.nan),
            "zone_mean_local_penetration": wmean(prod.penetration, prod.energy_GWh),
            "offshore_TWh": prod.energy_GWh.sum() / 1e3,
        })

    df_head = df[~df.zone.isin(HEADLINE_EXCLUDE)]
    reg = (df_head.groupby(["scenario", "basin", "gas"])
             .apply(region_agg, include_groups=False).reset_index())
    reg.to_csv(OUT / "gas_shock_region_means.csv", index=False)
    # sensitivity: Baltic aggregate without Sweden (all-SE attribution caveat)
    reg_exse = (df_head[df_head.zone != "SE"]
                .groupby(["scenario", "basin", "gas"])
                .apply(region_agg, include_groups=False).reset_index())
    reg_exse.to_csv(OUT / "gas_shock_region_means_exSE.csv", index=False)

    # ---- per-zone slope dCV/dgas (the headline scatter) ------------------
    sens = []
    for (scn, zone), z in df.groupby(["scenario", "zone"]):
        z = z.dropna(subset=["CV"]).sort_values("gas")
        if len(z) >= 3 and z.energy_GWh.mean() >= MIN_ENERGY_GWH:
            slope = np.polyfit(z.gas, z.CV, 1)[0]
            sens.append({"scenario": scn, "zone": zone, "basin": ZONE_BASIN[zone],
                         "penetration": z.penetration.mean(),
                         "offshore_TWh": z.energy_GWh.mean() / 1e3,
                         "dCV_per_10EUR": slope * 10,
                         "gas_min": int(z.gas.min()), "gas_max": int(z.gas.max()),
                         "CV_lowgas": z.CV.iloc[0], "CV_highgas": z.CV.iloc[-1]})
    sens = pd.DataFrame(sens)
    sens.to_csv(OUT / "gas_shock_sensitivity.csv", index=False)

    print("\n=== Region-aggregate CV vs gas (energy-weighted, ex-GB) ===")
    print(reg.pivot_table(index=["scenario", "basin"], columns="gas", values="CV").round(3).to_string())
    # the defensible headline ratio, computed (not asserted): NS slope / Baltic slope
    print("\n=== NS-vs-Baltic gas exposure ratio per scenario (end-to-end slope) ===")
    for scn, g in reg.groupby("scenario"):
        sl = {}
        for basin, gg in g.groupby("basin"):
            gg = gg.dropna(subset=["CV"]).sort_values("gas")
            if len(gg) >= 2:
                sl[basin] = np.polyfit(gg.gas, gg.CV, 1)[0]
        if "NorthSea" in sl and "Baltic" in sl and sl["Baltic"] != 0:
            print(f"  {scn}: NS {sl['NorthSea']*10:+.4f} vs Baltic {sl['Baltic']*10:+.4f} per +10 EUR"
                  f"  -> ratio {sl['NorthSea']/sl['Baltic']:.2f}x"
                  if sl["Baltic"] < 0 else
                  f"  {scn}: NS {sl['NorthSea']*10:+.4f}; Baltic {sl['Baltic']*10:+.4f} per +10 EUR"
                  f"  -> Baltic decoupled (slope >= 0)")
    if len(sens):
        print("\n=== Per-zone gas sensitivity (dCV per +10 EUR/MWh) vs penetration ===")
        print(sens.sort_values("penetration")[
            ["zone", "basin", "scenario", "penetration", "offshore_TWh",
             "dCV_per_10EUR"]].round(3).to_string(index=False))

    # ---- figures ---------------------------------------------------------
    colors = {"Baltic": "#c0392b", "NorthSea": "#2471a3"}
    # 1. region-aggregate CV vs gas
    fig, ax = plt.subplots(figsize=(7.5, 5))
    styles = {"2030-NT-balticBaseline": ":", "2040-NT-balticBaseline": "--",
              "2040-NT-balticHigh": "-"}
    for (scn, basin), g in reg.groupby(["scenario", "basin"]):
        g = g.dropna(subset=["CV"]).sort_values("gas")
        if len(g):
            ax.plot(g.gas, g.CV, styles.get(scn, "-"), color=colors[basin],
                    marker="o", ms=4, label=f"{basin} · {scn.replace('-NT-baltic','/')}")
    ax.set(xlabel="Gas price (EUR/MWh)", ylabel="Offshore capture value (energy-wtd)",
           title="Capture value vs gas-price shock (solid = highest Baltic buildout)")
    ax.legend(fontsize=7); ax.grid(alpha=0.3)
    fig.tight_layout(); fig.savefig(OUT / "fig_gas_shock_cv.png", dpi=200)

    # 2. THE HEADLINE: per-zone slope vs penetration (GB shown but excluded from fit)
    if len(sens):
        fit = sens[~sens.zone.isin(HEADLINE_EXCLUDE)]
        gb = sens[sens.zone.isin(HEADLINE_EXCLUDE)]
        fig, ax = plt.subplots(figsize=(7, 5))
        if len(fit) >= 2:
            a, b = np.polyfit(fit.penetration, fit.dCV_per_10EUR, 1)
            xs = np.linspace(fit.penetration.min(), fit.penetration.max(), 50)
            ax.plot(xs, a * xs + b, color="grey", lw=1, zorder=1,
                    label=f"trend (ex-GB): {a:.3f}/pen")
        for basin, g in fit.groupby("basin"):
            ax.scatter(g.penetration, g.dCV_per_10EUR, s=40, color=colors[basin],
                       label=basin, zorder=2, edgecolor="white")
        if len(gb):
            ax.scatter(gb.penetration, gb.dCV_per_10EUR, s=45, marker="x",
                       color="grey", zorder=2, label="GB (excluded: model limitation)")
        for _, r in sens.iterrows():
            ax.annotate(r.zone, (r.penetration, r.dCV_per_10EUR), fontsize=6,
                        xytext=(3, 3), textcoords="offset points")
        ax.axhline(0, color="k", lw=0.8)
        # title computed from the data, not asserted (audit fix: hardcoded
        # empirical claims in figure titles go stale when inputs change)
        q10, q90 = fit.dCV_per_10EUR.quantile([0.1, 0.9])
        ax.set(xlabel="Offshore penetration (zone wind energy / zone load)",
               ylabel="ΔCV per +10 EUR/MWh gas  (steeper = more gas-exposed)",
               title="Gas-shock effect on capture value, per zone\n"
                     f"(10th-90th pct of slopes: {q10:+.3f} to {q90:+.3f} per +10 EUR, ex-GB)")
        ax.legend(fontsize=8); ax.grid(alpha=0.3)
        fig.tight_layout(); fig.savefig(OUT / "fig_gas_shock_sensitivity.png", dpi=200)

    print(f"\nSaved tables + figures -> {OUT}/")


if __name__ == "__main__":
    main()
