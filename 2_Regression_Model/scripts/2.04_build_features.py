"""
04_build_features.py

W4 stage 1: assemble the monthly regression dataset for Strand A.

For each (farm, year, month) row we produce:
  - Target: CV_month  (from script 14)
  - Paul's 7 features (Sec 3.3), at the farm's MARKET AREA resolution:
        1. Correlation_VRE   = monthly Pearson(asset hourly gen, area VRE hourly gen)
        2. Correlation_Load  = monthly Pearson(asset hourly gen, area load hourly)
        3. VRE_MarketShare   = (E_solar + E_onwind + E_offwind) / E_load per month
        4. Gas_Price         = TTF monthly avg                      [external, stub]
        5. Carbon_Price     = EU ETS monthly avg                   [external, stub]
        6. Flexibility_Index = (battery + DSR + PHS) cap / VRE cap  [stub]
        7. Interconnection_Index = Cap_inter / Cap_VRE * (1 - Corr(VRE_area, VRE_neighbours))

LEVER C (2026-06-11) — bidding-zone resolution. The MARKET AREA of a farm is
its bidding ZONE wherever zone-resolved data exists (DK_1, DK_2, SE_4 — pulled
by `2.01 --zones-only` + 2.05), and the country otherwise (single-zone
countries are unchanged: area == country). This delivers the lit-review
commitment that system variables resolve at the level prices actually form:
the 7 Danish farms now see DK1-vs-DK2 penetration, correlations, flexibility
and interconnection instead of a Denmark-wide blur. Each row carries a
`feature_resolution` column ("zone" / "country"). The pre-lever-C dataset is
preserved as features_monthly_v1_country.csv for the before/after comparison.
  - Lina's additions:
        8.  Country-wide Normalised_Flow = sum_h|Flow_h| / (Cap_inter * hours_month)
        9.  Link_Specific_Normalised_Flow_<partner>  (one column per partner)
        10. Synchronicity_<partner> = monthly Pearson(VRE_country, VRE_partner)

Stubs are filled in W4 stage 2 (gas/CO2 history pull + capacities).

Inputs:
  data/cv_strandA/monthly_cv_per_farm.csv               (target)
  data/vwf/hourly_cf_{year}.csv                         (asset gen profile)
  data/entsoe_strandA/{prices,load,generation,flows}/   (system signals)
  data/wind_farms_strandA.csv                           (farm -> country/zone)

Output:
  data/features_strandA/features_monthly.csv            (long: one row per farm-month)
"""
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
SITES = pd.read_csv(ROOT / "data/wind_farms_strandA.csv", comment="#")
SITES = SITES[SITES.lat.notna()].copy()

CV = pd.read_csv(ROOT / "data/cv_strandA/monthly_cv_per_farm.csv", parse_dates=["date"])
ENTSOE = ROOT / "data/entsoe_strandA"
VWF_DIR = ROOT / "data/vwf"
OUT = ROOT / "data/features_strandA"
OUT.mkdir(parents=True, exist_ok=True)

# Yearly installed capacity per country (script 05), indexed by integer year.
CAP_DIR = ENTSOE / "installed_capacity"
def _load_capacity(country):
    f = CAP_DIR / f"{country}.csv"
    if not f.exists():
        return None
    return pd.read_csv(f, index_col=0)
CAP = {c: _load_capacity(c) for c in SITES.country.unique()}

# ---- Lever C: market-area resolution -------------------------------------
# Farm bidding zones in the registry use DK1/DK2; ENTSO-E folders use DK_1/DK_2.
ZONE_NORM = {"DK1": "DK_1", "DK2": "DK_2"}
# zone -> parent country, for capacity fallback when a zone file is missing
AREA_FALLBACK = {"DK_1": "DK", "DK_2": "DK", "SE_4": "SE"}
for _z in AREA_FALLBACK:
    CAP[_z] = _load_capacity(_z)   # zone capacity from 2.05 (None if not pulled)


def market_area(bidding_zone, country):
    """The resolution at which a farm's system features are computed: its
    bidding ZONE when zone-resolved load data exists (DK_1/DK_2/SE_4, pulled
    by `2.01 --zones-only`), else the country. Single-zone countries fall
    back to the country (identical to the pre-lever-C behaviour)."""
    z = ZONE_NORM.get(bidding_zone, bidding_zone)
    if z != country and (ENTSOE / "load" / z).exists():
        return z
    return country


def _cap_table(area):
    """Installed-capacity table for an area, falling back zone -> country."""
    df = CAP.get(area)
    if df is None and area in AREA_FALLBACK:
        return CAP.get(AREA_FALLBACK[area])
    return df

# Gas + carbon historical (curated CSV from ICE/EU ETS Data Viewer; see comments).
_gc_path = ROOT / "data/external/gas_co2_monthly.csv"
GAS_CO2 = (pd.read_csv(_gc_path, comment="#").set_index(["year", "month"])
           if _gc_path.exists() else None)

# Partners we consider for synchronicity + link-specific metrics. Derived from
# the flow folder structure (border pairs we pulled).
def discover_partner_set():
    pairs = []
    if (ENTSOE / "flows").exists():
        for d in (ENTSOE / "flows").iterdir():
            if d.is_dir() and "__" in d.name:
                a, b = d.name.split("__", 1)
                pairs.append((a, b))
    return pairs


# ---- per-year-per-country helpers ----------------------------------------
def load_country_load(country, year):
    f = ENTSOE / "load" / country / f"{year}.csv"
    if not f.exists():
        return None
    df = pd.read_csv(f, index_col=0, parse_dates=True)
    s = df["load_MW"] if "load_MW" in df.columns else df.iloc[:, 0]
    if s.index.tz is None:
        s.index = s.index.tz_localize("UTC")
    return s


# Per-zone VRE-generation correction (data-integrity pass, 2026-06-03).
# Implied-CF check (gen / installed cap) flagged NL VRE as badly under-reported
# in ENTSO-E -- solar CF 0.003 vs ~0.11 (the Paul-documented "Dutch solar off by
# orders of magnitude" error), plus low NL onshore/offshore. We rescale each
# affected VRE tech so its annual implied CF hits a physical target (reference
# from well-behaved neighbours), preserving the hourly SHAPE (Paul's Ember-style
# fix). Affects NL's VRE_MarketShare + Corr_VRE features (not the CV target,
# which uses the VWF).
GEN_CF_TARGET = {"Solar": 0.11, "Wind Onshore": 0.26, "Wind Offshore": 0.40}
GEN_CORRECT_ZONES = {"NL"}


def load_country_generation(country, year):
    f = ENTSOE / "generation" / country / f"{year}.csv"
    if not f.exists():
        return None
    df = pd.read_csv(f, index_col=0, parse_dates=True)
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")
    if (country in GEN_CORRECT_ZONES and CAP.get(country) is not None
            and year in CAP[country].index):
        cap_row, hrs = CAP[country].loc[year], len(df)
        for tech, target in GEN_CF_TARGET.items():
            if tech in df.columns and tech in cap_row and cap_row[tech] > 50:
                obs_cf = df[tech].sum() / (cap_row[tech] * hrs)
                if obs_cf > 0:
                    df[tech] = df[tech] * (target / obs_cf)
    return df


def country_vre_hourly(country, year):
    """Sum Solar + Wind Onshore + Wind Offshore hourly (MW) for the country."""
    df = load_country_generation(country, year)
    if df is None:
        return None
    vre_cols = [c for c in df.columns if any(k in c for k in ["Solar", "Wind"])]
    if not vre_cols:
        return None
    return df[vre_cols].sum(axis=1)


def load_flow(from_zone, to_zone, year):
    f = ENTSOE / "flows" / f"{from_zone}__{to_zone}" / f"{year}.csv"
    if not f.exists():
        return None
    df = pd.read_csv(f, index_col=0, parse_dates=True)
    s = df["flow_MW"] if "flow_MW" in df.columns else df.iloc[:, 0]
    if s.index.tz is None:
        s.index = s.index.tz_localize("UTC")
    return s


# ---- core feature engineering --------------------------------------------
COUNTRY_PARTNER_MAP = {
    "DE": ["DK_1", "DK_2", "PL", "NL", "FR", "BE"],
    "DK": ["DE_LU", "NL", "GB", "SE_4"],
    "NL": ["DE_LU", "GB", "BE", "DK_1", "NO_2"],
    "BE": ["DE_LU", "FR", "GB", "NL"],
    "FR": ["DE_LU", "BE", "GB", "IE_SEM"],
    "GB": ["FR", "NL", "DK_1", "NO_2", "BE"],
    "PL": ["DE_LU", "SE_4", "LT"],
    "EE": ["FI", "LV"],
    "LV": ["EE", "LT"],
    "LT": ["LV", "PL", "SE_4"],
    "FI": ["EE", "SE_3", "NO_4"],
    "SE": ["FI", "DE_LU", "DK_2", "PL", "LT"],
    "NO": ["DK_1", "GB", "NL"],
    "IE": ["GB", "FR"],
}


def country_zone(country):
    """Canonical zone code used in flows for a country."""
    return {"DE": "DE_LU", "FR": "FR", "BE": "BE", "NL": "NL", "GB": "GB",
            "IE": "IE_SEM", "DK": "DK_1", "PL": "PL", "EE": "EE",
            "LV": "LV", "LT": "LT", "FI": "FI", "SE": "SE_4", "NO": "NO_2"}[country]


# ---- features 6 + 7: installed-capacity-based annual indices (Paul Sec 3.3) --
def _cap_sum(country, year, names):
    """Sum installed capacity (MW) of columns whose name contains any of
    `names`, for a given area-year (zone capacity preferred, country fallback)."""
    df = _cap_table(country)
    if df is None or year not in df.index:
        return np.nan
    row = df.loc[year]
    vals = [row[c] for c in df.columns
            if any(n in c for n in names) and pd.notna(row[c])]
    return float(sum(vals)) if vals else 0.0


def cap_vre(country, year):
    """Cap_VRE = Solar + Wind Onshore + Wind Offshore installed (MW)."""
    v = _cap_sum(country, year, ["Solar", "Wind Onshore", "Wind Offshore"])
    return v if (pd.notna(v) and v > 0) else np.nan


def flexibility_index(country, year):
    """Feature 6 = (Pumped Storage + Battery + Energy storage) / Cap_VRE.

    Paul's battery + DSR came from proprietary sources; ENTSO-E reports only
    pumped-hydro (+ battery for a few country-years). DSR omitted -- see
    script 05 docstring. Numerator is 0 where a country has no reported
    storage (e.g. DK), which is physically correct."""
    cv = cap_vre(country, year)
    if not (pd.notna(cv) and cv > 0):
        return np.nan
    flex = _cap_sum(country, year, ["Pumped Storage", "Battery", "Energy storage"])
    return (flex if pd.notna(flex) else 0.0) / cv


# country -> its ENTSO-E bidding zones (DK and the Nordics span several).
COUNTRY_ZONES = {
    "DE": ["DE_LU"], "FR": ["FR"], "BE": ["BE"], "NL": ["NL"], "GB": ["GB"],
    "IE": ["IE_SEM"], "DK": ["DK_1", "DK_2"], "PL": ["PL"], "EE": ["EE"],
    "LV": ["LV"], "LT": ["LT"], "FI": ["FI"],
    "SE": ["SE_1", "SE_2", "SE_3", "SE_4"],
    "NO": ["NO_1", "NO_2", "NO_3", "NO_4", "NO_5"],
}
_FLOW_DIR = ENTSOE / "flows"


def _country_border_files(country):
    """Discover every external border of `country` from the flow folders.
    Returns {frozenset(zoneA, zoneB): [folder names]} where exactly one
    endpoint is one of the country's own zones -- so DK picks up both DK_1
    and DK_2 links (the dual-zone case the old single-zone map mishandled),
    and the Nordics pick up all their zones."""
    own = set(COUNTRY_ZONES.get(country, [country]))
    borders = {}
    if not _FLOW_DIR.exists():
        return borders
    for d in _FLOW_DIR.iterdir():
        if not (d.is_dir() and "__" in d.name):
            continue
        a, b = d.name.split("__", 1)
        if (a in own) ^ (b in own):   # external border: exactly one endpoint ours
            borders.setdefault(frozenset((a, b)), []).append(d.name)
    return borders


def _border_flow_year(folders, year):
    """Combined hourly |flow| across all direction-files of one border for a
    year (None if no file exists for that year)."""
    parts = []
    for name in folders:
        f = _FLOW_DIR / name / f"{year}.csv"
        if not f.exists():
            continue
        df = pd.read_csv(f, index_col=0, parse_dates=True)
        s = df["flow_MW"] if "flow_MW" in df.columns else df.iloc[:, 0]
        if s.index.tz is None:
            s.index = s.index.tz_localize("UTC")
        parts.append(s.abs())
    return pd.concat(parts, axis=1).sum(axis=1) if parts else None


def _nearest_years(year, lo=2017, hi=2024):
    """year, then year+1, year-1, year+2, ... within [lo, hi] -- to fill a
    year whose cross-border flow files are missing (NTC is slowly varying,
    so this mirrors the installed-capacity backfill in script 05)."""
    order = [year]
    for d in range(1, (hi - lo) + 1):
        for y in (year + d, year - d):
            if lo <= y <= hi:
                order.append(y)
    return order


def cap_interconnect(country, year):
    """Cap_Interconnect = sum over the country's external borders of the
    yearly-max |flow| on that border (Paul: yearly maximum of observed
    flows). Auto-discovers borders (handles DK1+DK2); falls back to the
    nearest year for any border whose file for `year` is missing."""
    borders = _country_border_files(country)
    if not borders:
        return np.nan
    total, found = 0.0, False
    for folders in borders.values():
        for y in _nearest_years(year):
            s = _border_flow_year(folders, y)
            if s is not None and len(s):
                total += float(s.max())
                found = True
                break
    return total if found else np.nan


def country_flow_monthly(country, year):
    """Lina country-wide cross-border exchange: monthly sum of |flow| over all
    external borders, nearest-year fallback per border. Series keyed by
    (year, month), stamped to the requested year regardless of fill-year."""
    borders = _country_border_files(country)
    monthly = None
    for folders in borders.values():
        s = None
        for y in _nearest_years(year):
            s = _border_flow_year(folders, y)
            if s is not None and len(s):
                break
        if s is None:
            continue
        ms = s.groupby(s.index.month).sum()
        ms.index = pd.MultiIndex.from_arrays(
            [[year] * len(ms), ms.index.values], names=["year", "month"])
        monthly = ms if monthly is None else monthly.add(ms, fill_value=0)
    return monthly if monthly is not None else pd.Series(dtype=float)


def area_partners(area):
    """Partner zones across an area's external borders. Countries use the
    static map; zone areas (lever C) discover partners from the flow folders
    (e.g. DK_2 -> DE_LU + SE_4)."""
    if area in COUNTRY_PARTNER_MAP:
        return COUNTRY_PARTNER_MAP[area]
    partners = set()
    for pair in _country_border_files(area):
        partners |= set(pair) - {area}
    return sorted(partners)


def vre_neighbour_corr(area, year, vre_lookup):
    """Annual Pearson(VRE_area, sum of neighbour VRE) -- the decorrelation
    term inside the Interconnection Index. Neighbour VRE prefers a
    zone-resolved series when one exists (e.g. SE_4), else the country."""
    vi = vre_lookup.get(area)
    if vi is None:
        return np.nan
    series = []
    seen = set()
    for p in area_partners(area):
        key = p if p in vre_lookup else p.split("_")[0]
        if key in seen:
            continue
        seen.add(key)
        s = vre_lookup.get(key)
        if s is not None:
            series.append(s)
    if not series:
        return np.nan
    neigh = pd.concat(series, axis=1).sum(axis=1)
    df = pd.concat([vi.rename("i"), neigh.rename("n")], axis=1).dropna()
    if len(df) < 100:
        return np.nan
    return df["i"].corr(df["n"])


def interconnection_index(country, year, vre_lookup=None):
    """Feature 7 = realised interconnection UTILISATION: annual mean |cross-border
    flow| divided by interconnection capacity, summed over the area's external
    borders (capacity proxied by each border's yearly-max flow). This is
    Efthymiadou's metric -- realised utilisation, not installed capacity, is what
    dampens price volatility and so lifts capture value.

    It replaces the previous (Cap_inter / Cap_VRE) x (1 - synchronicity) index,
    which divided border capacity by the renewable FLEET: high-VRE Germany scored
    ~0.01, the Baltic ranked as MORE interconnected than the North Sea (0.131 vs
    0.113), and the feature carried the wrong sign (corr with CV -0.07). The
    utilisation form ranks the basins correctly and is positively signed for
    OPERATIONAL farms in both basins (current panel: corr with CV +0.32 NS,
    +0.36 Baltic). The protective sign is operational-subset-specific, however:
    in the enclosed-Baltic price-zone rows (planned/under-construction PL, FI, EE,
    LV, LT) the correlation is about -0.12, so the full-Baltic correlation nets to
    roughly zero (-0.03). The Baltic reading of this feature therefore reflects the
    operational North Sea/Baltic farms, not the price-anchored enclosed zones --
    a limitation flagged in Chapter 5. The synchronicity multiplier degraded the
    signal and is dropped. vre_lookup is unused (kept for call compatibility)."""
    borders = _country_border_files(country)
    if not borders:
        return np.nan
    cap_sum, flow_sum, found = 0.0, 0.0, False
    for folders in borders.values():
        for y in _nearest_years(year):
            s = _border_flow_year(folders, y)
            if s is not None and len(s):
                cap_sum += float(s.max()); flow_sum += float(s.mean()); found = True
                break
    return (flow_sum / cap_sum) if (found and cap_sum > 0) else np.nan


def _ym_keys(idx):
    """Named (year, month) keys for groupby so multi-series can align/add."""
    return [idx.year.rename("year"), idx.month.rename("month")]


def monthly_corr(a, b):
    """Per-month Pearson correlation of two hourly series, returns Series with (year, month) MultiIndex."""
    df = pd.concat([a.rename("a"), b.rename("b")], axis=1).dropna()
    if df.empty:
        return pd.Series(dtype=float)
    grp = df.groupby(_ym_keys(df.index))
    return grp.apply(lambda d: d["a"].corr(d["b"]) if len(d) > 24 else np.nan,
                     include_groups=False)


def main():
    print(f"Loaded {len(SITES)} farms; {len(CV)} CV rows to enrich")
    years = sorted(CV.year.unique())
    print(f"Years to process: {years}")

    feature_rows = []
    for year in years:
        print(f"\n=== {year} ===")
        cf_path = VWF_DIR / f"hourly_cf_{year}.csv"
        if not cf_path.exists():
            print(f"  no VWF for {year}, skip")
            continue
        cf = pd.read_csv(cf_path, index_col=0, parse_dates=True)
        if cf.index.tz is None:
            cf.index = cf.index.tz_localize("UTC")

        # market areas this year: countries + any zone-resolved areas (lever C)
        farm_areas = {market_area(s.bidding_zone, s.country) for _, s in SITES.iterrows()}
        area_set = sorted(set(SITES.country.unique()) | farm_areas)

        # cache per-area signals once (zones and countries share the loaders —
        # they only differ in which ENTSOE subfolder they read)
        area_vre = {}
        area_load = {}
        for a in area_set:
            area_load[a] = load_country_load(a, year)
            area_vre[a] = country_vre_hourly(a, year)
        # cache partner VRE (country-level)
        partner_vre = {}
        for c, partners in COUNTRY_PARTNER_MAP.items():
            for p in partners:
                pcc = p.split("_")[0]
                if pcc not in partner_vre:
                    partner_vre[pcc] = area_vre.get(pcc) if pcc in area_vre else country_vre_hourly(pcc, year)

        # Features 6 + 7 are annual (installed capacity is yearly) -> compute
        # once per area and reuse for all 12 months. If a zone has NO
        # zone-level capacity table (ENTSO-E does not publish SE_4 capacity),
        # BOTH capacity features fall back to the country as a consistent
        # pair — never zone borders over country VRE cap.
        vre_lookup = {**partner_vre, **area_vre}
        flex_by_area, ic_by_area, flow_by_area = {}, {}, {}
        for a in area_set:
            cap_area = a if CAP.get(a) is not None else AREA_FALLBACK.get(a, a)
            if cap_area != a:
                print(f"  note: {a} has no zone capacity table — features 6+7 at {cap_area} level")
            flex_by_area[a] = flexibility_index(cap_area, year)
            ic_by_area[a] = interconnection_index(cap_area, year, vre_lookup)
            flow_by_area[a] = country_flow_monthly(a, year)

        for _, s in SITES.iterrows():
            farm = s["name"]
            country = s.country
            if farm not in cf.columns:
                continue
            area = market_area(s.bidding_zone, s.country)
            asset_h = cf[farm]
            vre_h = area_vre.get(area)
            load_h = area_load.get(area)

            # 1+2 monthly Pearson correlations
            corr_vre = monthly_corr(asset_h, vre_h) if vre_h is not None else pd.Series(dtype=float)
            corr_load = monthly_corr(asset_h, load_h) if load_h is not None else pd.Series(dtype=float)

            # 3. VRE market share per month
            if vre_h is not None and load_h is not None:
                mh = pd.concat([vre_h.rename("vre"), load_h.rename("load")], axis=1).dropna()
                ms = (mh.groupby(_ym_keys(mh.index))
                        .apply(lambda d: d["vre"].sum() / d["load"].sum()
                               if d["load"].sum() > 0 else np.nan,
                               include_groups=False))
            else:
                ms = pd.Series(dtype=float)

            # 8. Area-wide normalised flow (Lina) -- robust border discovery
            #    + nearest-year fallback (precomputed per area above).
            country_flow = flow_by_area.get(area, pd.Series(dtype=float))

            # 9 + 10 per-partner link metrics (Lina link-specific). These keep
            #    the partner-resolved view; the country-wide aggregate (#8) is
            #    the robust one used for the headline feature.
            partners = COUNTRY_PARTNER_MAP.get(country, [])
            country_z = country_zone(country)
            link_norm_flow = {}
            sync_per_partner = {}
            for p in partners:
                # bidirectional flow magnitude: |flow(country->p)| + |flow(p->country)|
                f1 = load_flow(country_z, p, year)
                f2 = load_flow(p, country_z, year)
                fmag = None
                if f1 is not None:
                    fmag = f1.abs().fillna(0)
                if f2 is not None:
                    fmag = (fmag if fmag is not None else 0) + f2.abs().fillna(0)
                if fmag is not None and hasattr(fmag, "groupby"):
                    link_norm_flow[p] = fmag.groupby(_ym_keys(fmag.index)).mean()
                # synchronicity: VRE correlation country vs partner
                pcc = p.split("_")[0]
                partner_v = partner_vre.get(pcc)
                if partner_v is not None and vre_h is not None:
                    sync_per_partner[p] = monthly_corr(vre_h, partner_v)

            # assemble rows
            for (yr, mo), cv_row in CV[(CV.farm == farm) & (CV.year == year)].set_index(["year", "month"]).iterrows():
                row = {
                    "farm": farm, "country": country,
                    "bidding_zone": s.bidding_zone, "basin": s.basin,
                    "market_area": area,
                    "feature_resolution": "zone" if area != country else "country",
                    "year": yr, "month": mo,
                    "CV": cv_row.CV,
                    "capture_price": cv_row.capture_price,
                    "baseload": cv_row.baseload,
                    "feature_1_Corr_VRE": corr_vre.get((yr, mo), np.nan),
                    "feature_2_Corr_Load": corr_load.get((yr, mo), np.nan),
                    "feature_3_VRE_MarketShare": ms.get((yr, mo), np.nan),
                    "feature_4_Gas_Price": (GAS_CO2.loc[(yr, mo), "gas_TTF_EURMWh"]
                                            if GAS_CO2 is not None and (yr, mo) in GAS_CO2.index else np.nan),
                    "feature_5_Carbon_Price": (GAS_CO2.loc[(yr, mo), "carbon_EUA_EURtCO2"]
                                               if GAS_CO2 is not None and (yr, mo) in GAS_CO2.index else np.nan),
                    "feature_6_Flexibility_Index": flex_by_area.get(area, np.nan),
                    "feature_7_Interconnection_Index": ic_by_area.get(area, np.nan),
                    # 8 Area-wide summed |flow| (Lina; raw MWh — NOT normalised)
                    "lina_country_NormalisedFlow_MW": country_flow.get((yr, mo), np.nan),
                }
                # 9 + 10 per partner
                for p, ser in link_norm_flow.items():
                    row[f"lina_link_NormFlow_MW__{p}"] = ser.get((yr, mo), np.nan)
                for p, ser in sync_per_partner.items():
                    row[f"lina_Synchronicity__{p}"] = ser.get((yr, mo), np.nan)
                feature_rows.append(row)

        n_rows_this_year = sum(1 for r in feature_rows if r["year"] == year)
        print(f"  rows assembled: {n_rows_this_year}")

    df = pd.DataFrame(feature_rows)
    out = OUT / "features_monthly.csv"
    df.to_csv(out, index=False)
    print(f"\nSaved {len(df)} rows x {df.shape[1]} cols -> {out}")
    if len(df):
        print(f"Coverage: {df.farm.nunique()} farms, years {sorted(df.year.unique())}")
        if "feature_resolution" in df.columns:
            res = df.groupby("feature_resolution").farm.nunique()
            print(f"Feature resolution (lever C): "
                  f"{res.get('zone', 0)} farms at ZONE level, "
                  f"{res.get('country', 0)} at country level")
            print(f"  zone areas: {sorted(df[df.feature_resolution=='zone'].market_area.unique())}")
        print(f"\nFeature non-null counts:")
        for c in ["feature_1_Corr_VRE", "feature_2_Corr_Load", "feature_3_VRE_MarketShare",
                  "feature_4_Gas_Price", "feature_5_Carbon_Price",
                  "feature_6_Flexibility_Index", "feature_7_Interconnection_Index",
                  "lina_country_NormalisedFlow_MW"]:
            if c in df.columns:
                print(f"  {c:42s}: {df[c].notna().sum()}/{len(df)} non-null")


if __name__ == "__main__":
    main()
