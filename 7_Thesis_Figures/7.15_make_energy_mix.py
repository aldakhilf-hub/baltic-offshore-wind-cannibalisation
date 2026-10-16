"""
7.15_make_energy_mix.py — the FULL energy mix behind the capture-value result.

Supervisor (2026-06-22): "there are so many other energy sources in the mix, it
is a bit dumb to assume they are not part of it by 2040; oil and gas are not
going anywhere." Correct. This shows the complete installed fleet, not just wind
and solar, exactly as the PyPSA projection carries it.

The future fleet is reconstructed from the present PyPSA baseline plus the
documented projection corrections in 1.07_run_scenarios.py:
  - VRE (offshore, onshore, solar): set to TYNDP National Trends, BEST (central).
  - Coal + lignite: phased down per the German Coal Exit Act / PL transition
    (DE coal x0.10, lignite x0.20 by 2040; PL coal x0.40, lignite x0.30).
  - Gas (CCGT/OCGT), oil, nuclear, hydro, biomass: HELD (they persist to 2040);
    plus PL nuclear +3.9 GW by 2040 (PEP2040).
  - Battery: TYNDP BEST.
These are the same numbers fed to the system model that produced the maps, so
the mix and the capture values are one consistent scenario (PyPSA, not regression).

Output -> results/fig_energy_mix.png, 10_Presentation/figures/, energy_mix_table.csv
"""
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OUT = HERE / "results"
DECK = ROOT / "10_Presentation" / "figures"

NS = ["DE", "NL", "BE", "DK", "FR"]
BAL = ["PL", "EE", "LV", "LT", "FI"]
zNS = ["DE", "NL", "BE", "DK1", "FR"]
zBAL = ["PL", "EE", "LV", "LT", "FI"]

base = pd.read_csv(ROOT / "1_PyPSA_Model/results/baseline_2023/capacity_by_country_carrier.csv").set_index("country")
cap = pd.read_csv(ROOT / "1_PyPSA_Model/data/tyndp/parsed_capacity.csv")
batt = pd.read_csv(ROOT / "1_PyPSA_Model/data/tyndp/parsed_batteries.csv")
proj = pd.read_csv(ROOT / "1_PyPSA_Model/results/projections_v3/projected_capture_values.csv")

# documented corrections from 1.07_run_scenarios.py
PHASEOUT = {"DE": {2030: {"coal": 0.50, "lignite": 0.60}, 2040: {"coal": 0.10, "lignite": 0.20}},
            "PL": {2030: {"coal": 0.85, "lignite": 0.70}, 2040: {"coal": 0.40, "lignite": 0.30}}}
NUC_ADD = {"PL": {2040: 3900.0}}

# display groups -> baseline carrier columns
GROUPS = [
    ("Offshore wind", ["offwind-ac", "offwind-dc"], "#0e6ba8"),
    ("Onshore wind",  ["onwind"],                    "#5dade2"),
    ("Solar PV",      ["solar"],                     "#f5b041"),
    ("Gas & oil",     ["CCGT", "OCGT", "oil"],       "#909497"),
    ("Coal & lignite", ["coal", "lignite"],          "#4d3b2a"),
    ("Nuclear",       ["nuclear"],                   "#a569bd"),
    ("Hydro & bio",   ["ror", "biomass", "geothermal"], "#27ae60"),
    ("Battery",       ["battery"],                   "#e67e22"),
]


def country_fleet(country, year):
    """Full per-carrier capacity (MW) for one country and horizon."""
    b = base.reindex([country]).fillna(0).iloc[0]
    f = {c: float(b.get(c, 0.0)) for c in
         ["CCGT", "OCGT", "oil", "coal", "lignite", "nuclear", "ror", "biomass", "geothermal"]}
    f["offwind-ac"] = float(b.get("offwind-ac", 0.0)); f["offwind-dc"] = 0.0
    f["onwind"] = float(b.get("onwind", 0.0)); f["solar"] = float(b.get("solar", 0.0))
    f["battery"] = 0.0
    if year == 2025:
        return f
    # VRE set to TYNDP BEST
    t = cap[(cap.country == country) & (cap.year == year) & (cap.trajectory == "BEST")].groupby("tech").MW.sum()
    f["offwind-ac"] = float(t.get("offwind", 0.0)); f["offwind-dc"] = 0.0
    f["onwind"] = float(t.get("onwind", 0.0)); f["solar"] = float(t.get("solar", 0.0))
    # coal/lignite phase-out (DE/PL coded; others held)
    for c in ("coal", "lignite"):
        fac = PHASEOUT.get(country, {}).get(year, {}).get(c, 1.0)
        f[c] *= fac
    # nuclear additions
    f["nuclear"] += NUC_ADD.get(country, {}).get(year, 0.0)
    # battery TYNDP BEST
    bt = batt[(batt.country == country) & (batt.year == year) & (batt.trajectory == "BEST")]
    f["battery"] = float(bt.power_MW.sum())
    return f


def region_groups(countries, year):
    tot = {g[0]: 0.0 for g in GROUPS}
    for c in countries:
        f = country_fleet(c, year)
        for label, cols, _ in GROUPS:
            tot[label] += sum(f.get(col, 0.0) for col in cols) / 1000.0  # GW
    return tot


def pen(zs, year):
    if year == 2025:
        return 0.0 if zs is zBAL else 0.035
    d = proj[(proj.scenario == f"{year}-NT-balticBaseline") & (proj.zone.isin(zs))]
    return d.energy_GWh.sum() / d.load_GWh.sum()


YEARS = [2025, 2030, 2040]
# German Baltic-Sea offshore operational today (Wikinger, Arkona, Baltic 2, Baltic Eagle);
# held across years (the registry carries no further German Baltic build).
DE_BALTIC_GW = 1.5


def off_c(c, year):
    if year == 2025:
        return ((base.loc[c].get("offwind-ac", 0) + base.loc[c].get("offwind-dc", 0)) / 1000
                if c in base.index else 0.0)
    d = cap[(cap.country == c) & (cap.tech == "offwind") & (cap.year == year) & (cap.trajectory == "BEST")]
    return d.MW.sum() / 1000


def proj_dk2(year):
    d = proj[(proj.scenario == f"{year}-NT-balticBaseline") & (proj.zone == "DK2")]
    return d.p_nom.sum() / 1000


def offshore_by_sea(year):
    """Offshore wind allocated by the sea each farm physically sits in. Germany and
    Denmark span both seas, so they are split: German Baltic farms and Danish DK2
    go to the Baltic; the rest to the North Sea."""
    dk2 = 0.977 if year == 2025 else proj_dk2(year)         # Rodsand + Kriegers Flak -> + Bornholm
    enclosed = sum(off_c(c, year) for c in ["PL", "EE", "LV", "LT", "FI"])
    baltic = DE_BALTIC_GW + dk2 + off_c("SE", year) + enclosed
    ns = (off_c("DE", year) - DE_BALTIC_GW) + off_c("NL", year) + off_c("BE", year) \
        + (off_c("DK", year) - dk2) + off_c("FR", year)
    return ns, baltic, enclosed


OFF_SEA = {y: offshore_by_sea(y) for y in YEARS}  # (north_sea, baltic_sea, enclosed_states)

REGIONS = [("North Sea", NS, "#1b4f72", 0),
           ("Baltic Sea", BAL, "#7b241c", 1)]

rows = []
fig, axes = plt.subplots(1, 2, figsize=(14, 6.4))
for ax, (name, cs, accent, idx) in zip(axes, REGIONS):
    data = {y: region_groups(cs, y) for y in YEARS}
    for y in YEARS:                                   # replace offshore with the by-sea allocation
        data[y]["Offshore wind"] = OFF_SEA[y][idx]
    x = np.arange(len(YEARS))
    bottoms = np.zeros(len(YEARS))
    for label, cols, color in GROUPS:
        vals = np.array([data[y][label] for y in YEARS])
        ax.bar(x, vals, 0.6, bottom=bottoms, color=color, label=label, zorder=3,
               edgecolor="white", linewidth=0.3)
        bottoms += vals
    tops = bottoms
    for i, y in enumerate(YEARS):
        off = data[y]["Offshore wind"]
        lbl = (f"offshore {off:.0f} GW\n(enclosed states {OFF_SEA[y][2]:.0f})" if idx == 1
               else f"offshore {off:.0f} GW")
        ax.text(i, tops[i] + tops.max() * 0.015, lbl, ha="center", va="bottom",
                fontsize=8.2, color=accent, fontweight="bold")
        if off > tops.max() * 0.04:
            ax.text(i, off / 2, f"{off:.0f}", ha="center", va="center", color="white",
                    fontsize=9, fontweight="bold", zorder=4)
        rows.append(dict(region=name, year=y, **{k: round(v, 1) for k, v in data[y].items()}))
    ax.set_xticks(x); ax.set_xticklabels(YEARS, fontsize=11)
    ax.set_title(name, fontsize=12.5, fontweight="bold", color=accent)
    ax.set_ylabel("Installed capacity (GW)", fontsize=10)
    ax.set_ylim(0, tops.max() * 1.20)
    ax.grid(axis="y", alpha=0.3, zorder=0)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)

axes[1].legend(loc="upper left", fontsize=8.3, framealpha=0.92, ncol=2)
fig.suptitle("Installed capacity by region, 2025 to 2040",
             fontsize=14, y=0.97, color="#111")
fig.tight_layout(rect=[0, 0, 1, 0.94])
pd.DataFrame(rows).to_csv(OUT / "energy_mix_table.csv", index=False)
fig.savefig(OUT / "fig_energy_mix.png", dpi=190)
print("saved fig_energy_mix.png")
print(pd.DataFrame(rows).to_string(index=False))
