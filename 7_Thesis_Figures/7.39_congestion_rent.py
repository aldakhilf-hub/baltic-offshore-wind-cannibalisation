"""
7.39_congestion_rent.py

The third pot of money. Slide 28 weighs the captured-revenue gain from
interconnection against the cost of the new lines, but ignores CONGESTION RENT:
when a branch is congested the price differs across it, and

    rent = flow x (price at the receiving end - price at the sending end)

accrues to the TSOs, not to generators or consumers. Under EU Reg. 2019/943
Art. 19 that income is ring-fenced: it must be spent on maintaining
availability, on grid investment, or on reducing network tariffs. So it is the
natural funding source for the very interconnection this thesis recommends.

Computes, for 2040 NT balticBaseline, frozen vs cost-optimal grid:
  - congestion rent per branch, aggregated by border and by basin
  - the annualised capital cost of the transmission the optimal grid builds
  - the rent that building the grid DESTROYS (prices converge, rent collapses):
    the merchant-transmission paradox, and the honest framing of "self-funding"

Lines are lossless (p1 = -p0), links carry efficiency, so
  line rent = p0 x (price_1 - price_0)
  link rent = p0 x (eff x price_1 - price_0)

Output -> results/congestion_rent.csv + congestion_rent_by_border.csv
"""
import warnings
from pathlib import Path
import numpy as np, pandas as pd, pypsa

warnings.filterwarnings("ignore")
pd.set_option("display.width", 220)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "7_Thesis_Figures" / "results"
FROZEN = Path.home() / "pypsa-eur/results/scenarios_tyndp_v3/2040-NT-balticBaseline.nc"
VOPT = Path.home() / "pypsa-eur/results/scenarios_tyndp_v3_vopt/2040-NT-balticBaseline.nc"

BAL = {"PL", "EE", "LV", "LT"}            # enclosed Baltic (FI excluded, as 7.31)
NS = {"DE", "NL", "BE", "FR"}             # DK handled separately (spans both)
NORDIC = {"SE", "NO", "FI", "DK"}


SCARCE = 390.0    # EUR/MWh, the scarcity threshold used in 1.17


def branch_rent(n, ex_scarcity=False):
    """Per-branch annual congestion rent (EUR) plus endpoint countries.

    ex_scarcity drops hours where either endpoint prices above SCARCE. Frozen-grid
    Poland runs 445 scarcity hours at a 205 EUR/MWh annual mean (1.17), which
    inflates any price-differential measure, so the headline is quoted as a
    bracket rather than a point estimate."""
    w = n.snapshot_weightings.objective
    P = n.buses_t.marginal_price
    rows = []
    for name, df, pt in (("Line", n.lines, n.lines_t), ("Link", n.links, n.links_t)):
        if df.empty:
            continue
        for b in df.index:
            b0, b1 = df.at[b, "bus0"], df.at[b, "bus1"]
            if b0 not in P.columns or b1 not in P.columns or b not in pt.p0.columns:
                continue
            p0 = pt.p0[b]
            eff = df.at[b, "efficiency"] if name == "Link" and "efficiency" in df.columns else 1.0
            keep = ~((P[b0] > SCARCE) | (P[b1] > SCARCE)) if ex_scarcity else slice(None)
            rent = float((p0 * (eff * P[b1] - P[b0]) * w)[keep].sum())
            cap = df.at[b, "s_nom_opt" if name == "Line" else "p_nom_opt"]
            rows.append(dict(branch=b, kind=name,
                             c0=n.buses.at[b0, "country"], c1=n.buses.at[b1, "country"],
                             rent_EUR=rent, cap_MW=cap,
                             util=float((p0.abs() * w).sum()) / (cap * w.sum()) if cap > 0 else np.nan))
    d = pd.DataFrame(rows)
    d["border"] = [" - ".join(sorted([a, b])) if a != b else f"{a} internal"
                   for a, b in zip(d.c0, d.c1)]
    return d


def basin_tag(r):
    cs = {r.c0, r.c1}
    if cs & BAL:
        return "Baltic internal" if cs <= BAL else "Baltic border"
    if cs & NS:
        return "North Sea internal" if cs <= NS else "North Sea border"
    return "Nordic / other"


def grid_cost(nf, nv):
    """Annualised capex of the transmission the optimal grid adds (EUR/yr)."""
    tot = 0.0
    for attr, dff, dfv in (("s_nom", nf.lines, nv.lines), ("p_nom", nf.links, nv.links)):
        if dfv.empty:
            continue
        common = dfv.index.intersection(dff.index)
        added = (dfv.loc[common, f"{attr}_opt"] - dff.loc[common, f"{attr}_opt"]).clip(lower=0)
        tot += float((added * dfv.loc[common, "capital_cost"]).sum())
    return tot


res, bydr = {}, {}
nets = {}
for tag, path in (("frozen", FROZEN), ("optimal", VOPT)):
    n = pypsa.Network(path)
    nets[tag] = n
    d = branch_rent(n)
    d["basin"] = d.apply(basin_tag, axis=1)
    d["grid"] = tag
    res[tag] = d
    bydr[tag] = d.groupby("basin").rent_EUR.sum() / 1e9

D = pd.concat(res.values())
D.to_csv(OUT / "congestion_rent.csv", index=False)

print("=== annual congestion rent, 2040 NT balticBaseline (bn EUR/yr) ===")
tab = pd.DataFrame(bydr).round(3)
tab.loc["TOTAL"] = tab.sum()
print(tab.to_string())

print("\n=== top borders by rent, frozen grid (bn EUR/yr) ===")
tb = (res["frozen"].groupby("border").rent_EUR.sum() / 1e9).sort_values(ascending=False)
to = (res["optimal"].groupby("border").rent_EUR.sum() / 1e9)
comp = pd.DataFrame({"frozen": tb, "optimal": to.reindex(tb.index)}).head(12)
comp["destroyed"] = comp.frozen - comp.optimal
print(comp.round(3).to_string())
comp.round(4).to_csv(OUT / "congestion_rent_by_border.csv")

# ---- ex-scarcity bracket: the same arithmetic with scarcity hours removed ----
ex = {t: branch_rent(nets[t], ex_scarcity=True) for t in nets}
for t in ex:
    ex[t]["basin"] = ex[t].apply(basin_tag, axis=1)
BALSET = ["Baltic internal", "Baltic border"]
print("=== ex-scarcity (hours above 390 EUR/MWh dropped), bn EUR/yr ===")
xt = pd.DataFrame({t: ex[t].groupby("basin").rent_EUR.sum() / 1e9 for t in ex}).round(3)
xt.loc["TOTAL"] = xt.sum()
print(xt.to_string())

cost = grid_cost(nets["frozen"], nets["optimal"]) / 1e9
rows = []
for label, src in (("full", res), ("ex-scarcity", ex)):
    f = src["frozen"].rent_EUR.sum() / 1e9
    o = src["optimal"].rent_EUR.sum() / 1e9
    bf = src["frozen"].groupby("basin").rent_EUR.sum()[BALSET].sum() / 1e9
    bo = src["optimal"].groupby("basin").rent_EUR.sum()[BALSET].sum() / 1e9
    rows.append(dict(case=label, rent_frozen=f, rent_optimal=o, rent_destroyed=f - o,
                     baltic_frozen=bf, baltic_optimal=bo, grid_cost=cost,
                     cover_total=f / cost, cover_baltic=bf / cost))
F = pd.DataFrame(rows)
F.round(2).to_csv(OUT / "congestion_rent_financing.csv", index=False)

print(f"""
=== the financing arithmetic (bn EUR/yr) ===
                                      full     ex-scarcity
congestion rent, frozen grid        {F.rent_frozen[0]:6.2f}      {F.rent_frozen[1]:6.2f}
  of which Baltic-related           {F.baltic_frozen[0]:6.2f}      {F.baltic_frozen[1]:6.2f}
congestion rent, optimal grid       {F.rent_optimal[0]:6.2f}      {F.rent_optimal[1]:6.2f}
  of which Baltic-related           {F.baltic_optimal[0]:6.2f}      {F.baltic_optimal[1]:6.2f}
rent DESTROYED by building          {F.rent_destroyed[0]:6.2f}      {F.rent_destroyed[1]:6.2f}
annualised capex of the new lines   {cost:6.2f}      {cost:6.2f}
Baltic rent / total grid cost       {F.cover_baltic[0]:6.2f}x     {F.cover_baltic[1]:6.2f}x
""")
