"""
06_parse_tyndp.py

Parses TYNDP 2024 supply (capacity) + demand + price inputs into clean
per-country tables for the scenario engine. Writes:
  tyndp/parsed_capacity.csv   tech, country, trajectory, year, MW
  tyndp/parsed_demand.csv     country, scenario, year, demand_TWh, growth_vs_2019
  tyndp/parsed_prices.csv     year, gas_eurMWh, coal_eurMWh, lignite_eurMWh, oil_eurMWh, co2_eurton

TYNDP node codes are aggregated to 2-letter country (UK->GB). Capacity sheets
have a dynamic LOW / BEST ESTIMATE / HIGH × year column layout, mapped from the
header rows rather than hardcoded.
"""

from pathlib import Path
import pandas as pd
import numpy as np

TY = Path(__file__).resolve().parent.parent / "data" / "tyndp"
SUPPLY = TY / "tyndp2024_supply.xlsx"
DEMAND = TY / "tyndp2024_demand.xlsb"

GJ_PER_MWH = 3.6

# capacity sheet -> PyPSA carrier-ish tech label
CAP_SHEETS = {"1.1.": "solar", "1.2.": "onwind", "1.3.": "offwind", "1.4.": "nuclear"}


def node_to_country(code):
    code = str(code).strip()
    if len(code) < 2:
        return None
    cc = code[:2].upper()
    return {"UK": "GB"}.get(cc, cc)


def parse_capacity_sheet(sheet, tech):
    raw = pd.read_excel(SUPPLY, sheet_name=sheet, header=None)
    # find the row that holds 'Country' (year header row); scenario labels are the row above
    yr_row = None
    for i in range(raw.shape[0]):
        if raw.iloc[i].astype(str).str.contains("Country", case=False, na=False).any():
            yr_row = i
            break
    if yr_row is None:
        return pd.DataFrame()
    scen_row = yr_row - 1
    # forward-fill scenario labels across columns
    scen = raw.iloc[scen_row].ffill()
    years = raw.iloc[yr_row]
    # build (trajectory, year) -> col map
    colmap = {}
    for j in range(raw.shape[1]):
        s = str(scen.iloc[j]).strip().upper()
        y = years.iloc[j]
        # match by prefix so suffixed labels like "BEST ESTIMATE (BE)" (onshore
        # wind sheet) are not silently dropped, which forced a LOW-fleet fallback
        traj = ("LOW" if s.startswith("LOW") else
                "BEST" if s.startswith("BEST ESTIMATE") else
                "HIGH" if s.startswith("HIGH") else None)
        if traj and pd.notna(y):
            try:
                yi = int(float(y))
                colmap[(traj, yi)] = j
            except (ValueError, TypeError):
                pass
    # country code column (the one containing 'Country' header)
    cc_col = raw.iloc[yr_row].astype(str).str.contains("Country", case=False, na=False).idxmax()
    data = raw.iloc[yr_row + 1:]
    rows = []
    for (traj, yr), j in colmap.items():
        for _, r in data.iterrows():
            country = node_to_country(r.iloc[cc_col])
            val = r.iloc[j]
            if country and pd.notna(val):
                try:
                    rows.append({"tech": tech, "country": country, "trajectory": traj,
                                 "year": yr, "MW": float(val)})
                except (ValueError, TypeError):
                    pass
    df = pd.DataFrame(rows)
    if df.empty:
        print(f"  WARNING: sheet {sheet} ({tech}) parsed 0 rows "
              f"(yr_row={yr_row}, colmap keys={list(colmap.keys())[:4]})")
        return df
    # aggregate nodes -> country
    return df.groupby(["tech", "country", "trajectory", "year"], as_index=False).MW.sum()


def parse_prices():
    xl = pd.ExcelFile(SUPPLY)
    ps = [s for s in xl.sheet_names if s.strip().startswith("3.1")][0]
    raw = pd.read_excel(SUPPLY, sheet_name=ps, header=None)
    # header row with 'Fuel' and year columns
    hdr = None
    for i in range(raw.shape[0]):
        if raw.iloc[i].astype(str).str.contains("Fuel", na=False).any():
            hdr = i; break
    years = {}
    for j in range(raw.shape[1]):
        v = raw.iloc[hdr, j]
        try:
            yi = int(float(v))
            if yi in (2030, 2040, 2050):
                years[yi] = j
        except (ValueError, TypeError):
            pass
    label_col = raw.iloc[hdr].astype(str).str.contains("Fuel", na=False).idxmax()

    def price_for(substr, yr):
        for _, r in raw.iloc[hdr+1:].iterrows():
            lbl = str(r.iloc[label_col])
            if substr.lower() in lbl.lower():
                return float(r.iloc[years[yr]])
        return None

    rows = []
    for yr in [2030, 2040, 2050]:
        rows.append({
            "year": yr,
            "gas_eurMWh": price_for("Natural Gas", yr) * GJ_PER_MWH,
            "coal_eurMWh": price_for("Hard coal", yr) * GJ_PER_MWH,
            "lignite_eurMWh": price_for("Lignite G1", yr) * GJ_PER_MWH,
            "oil_eurMWh": price_for("Crude oil", yr) * GJ_PER_MWH,
            "co2_eurton": price_for("CO2 price", yr),
        })
    return pd.DataFrame(rows)


def parse_demand():
    raw = pd.read_excel(DEMAND, engine="pyxlsb", sheet_name="3_DEMAND_OUTPUT", header=None)
    scen = raw.iloc[0]; yrs = raw.iloc[1]
    cols = {c: raw.iloc[1, k] for k, c in enumerate(raw.iloc[1]) if isinstance(c, str)}
    hdr = raw.iloc[1].tolist()
    body = raw.iloc[2:].copy()
    body.columns = hdr
    # scenario-year columns are positional >=10
    sy = {}
    for j in range(10, raw.shape[1]):
        s = str(scen.iloc[j]).strip(); y = yrs.iloc[j]
        try:
            sy[(s, int(float(y)))] = j
        except (ValueError, TypeError):
            pass
    # electricity energy demand only
    mask = (body["ENERGY_CARRIER"].astype(str) == "Electricity") & \
           (body["PARAMETER"].astype(str) == "Energy demand")
    elec = raw.iloc[2:][mask.values]
    rows = []
    for (s, y), j in sy.items():
        agg = {}
        for _, r in elec.iterrows():
            c = str(r.iloc[1])  # COUNTRY col
            v = r.iloc[j]
            if pd.notna(v):
                try:
                    agg[c] = agg.get(c, 0.0) + float(v)
                except (ValueError, TypeError):
                    pass
        for c, tot in agg.items():
            rows.append({"country": c, "scenario": s, "year": y, "demand_TWh": tot})
    d = pd.DataFrame(rows)
    # growth vs REF 2019
    ref = d[(d.scenario == "REF") & (d.year == 2019)].set_index("country").demand_TWh
    d["growth_vs_2019"] = d.apply(
        lambda r: r.demand_TWh / ref[r.country] if r.country in ref.index and ref[r.country] > 0 else np.nan,
        axis=1)
    return d


if __name__ == "__main__":
    caps = pd.concat([parse_capacity_sheet(s, t) for s, t in CAP_SHEETS.items()], ignore_index=True)
    caps.to_csv(TY / "parsed_capacity.csv", index=False)
    print(f"Capacity rows: {len(caps)}")
    print(caps.groupby(["tech", "trajectory"]).year.agg(["min", "max", "count"]).to_string())

    prices = parse_prices()
    prices.to_csv(TY / "parsed_prices.csv", index=False)
    print("\nPrices (€/MWh_th, €/ton):")
    print(prices.round(2).to_string(index=False))

    dem = parse_demand()
    dem.to_csv(TY / "parsed_demand.csv", index=False)
    print(f"\nDemand rows: {len(dem)}; scenario-years: {sorted(dem.groupby(['scenario','year']).groups.keys())}")
    # spot check
    for c in ["DE", "PL", "EE"]:
        sub = dem[dem.country == c]
        print(f"  {c}: " + ", ".join(f"{r.scenario}{r.year}={r.demand_TWh:.0f}TWh(×{r.growth_vs_2019:.2f})"
              for _, r in sub.iterrows() if pd.notna(r.growth_vs_2019) or r.scenario=='REF'))
