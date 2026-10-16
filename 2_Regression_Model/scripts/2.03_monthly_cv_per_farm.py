"""
03_monthly_cv_per_farm.py

W3 of Strand A: monthly capture value (CV) per wind farm per month, computed
from VWF hourly capacity factors x bidding-zone observed prices.

For each farm and each available year:
  gen_h        = CF_h  (normalised, since rated_MW factors out of the CV ratio)
  capture_price = sum_h(gen_h * price_h) / sum_h(gen_h)         per month
  baseload      = mean_h(price_h)                               per month
  CV_month      = capture_price / baseload

Skips months with <500 hours of overlapping non-null data.

Inputs:
  data/wind_farms_strandA.csv                   (farm -> bidding zone)
  data/vwf/hourly_cf_{year}.csv                 (VWF CFs from script 13)
  data/entsoe_strandA/prices/{zone}/{year}.csv  (observed prices from 12)

Output:
  data/cv_strandA/monthly_cv_per_farm.csv       (long format: farm, year, month, ...)
  data/cv_strandA/fig_paul_fig45_NS.png         (Paul-style trajectories for NS)
"""
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent.parent
SITES = pd.read_csv(ROOT / "data/wind_farms_strandA.csv", comment="#")
SITES = SITES[SITES.lat.notna()].copy()

VWF_DIR = ROOT / "data/vwf"
PRICES_DIR = ROOT / "data/entsoe_strandA/prices"
OUT = ROOT / "data/cv_strandA"
OUT.mkdir(parents=True, exist_ok=True)


def load_year_prices(year):
    """Return dict: zone -> hourly price Series for the year (UTC index)."""
    zone_prices = {}
    pdir = PRICES_DIR
    if not pdir.exists():
        return zone_prices
    for zone_dir in pdir.iterdir():
        if not zone_dir.is_dir():
            continue
        f = zone_dir / f"{year}.csv"
        if not f.exists():
            continue
        df = pd.read_csv(f, index_col=0, parse_dates=True)
        # column name is "price_EURMWh"
        col = "price_EURMWh" if "price_EURMWh" in df.columns else df.columns[0]
        s = df[col].copy()
        if s.index.tz is None:
            s.index = s.index.tz_localize("UTC")
        else:
            s.index = s.index.tz_convert("UTC")
        zone_prices[zone_dir.name] = s
    return zone_prices


def monthly_cv(gen, price):
    """Per-month CV from aligned hourly generation + price series."""
    df = pd.concat([gen.rename("g"), price.rename("p")], axis=1).dropna()
    if df.empty:
        return pd.DataFrame()
    g = df["g"]
    p = df["p"]
    # group by year-month
    grp = df.groupby([df.index.year.rename("year"), df.index.month.rename("month")])
    out = pd.DataFrame({
        "n_hours": grp.size(),
        "capture_price": grp.apply(
            lambda d: (d["g"] * d["p"]).sum() / d["g"].sum() if d["g"].sum() > 0 else np.nan,
            include_groups=False),
        "baseload": grp["p"].mean(),
        "gen_MWh_norm": grp["g"].sum(),     # normalised energy (sum of CF over hours)
    })
    out["CV"] = out["capture_price"] / out["baseload"]
    out = out.reset_index()
    return out


def main():
    print(f"Loaded {len(SITES)} farms from wind_farms_strandA.csv\n")
    available_years = sorted([
        int(f.stem.split("_")[-1])
        for f in VWF_DIR.glob("hourly_cf_*.csv")
    ])
    print(f"VWF years available: {available_years}")
    if not available_years:
        print("No VWF CF files yet. Run 13_pull_era5_and_vwf.py first.")
        return

    all_rows = []
    for year in available_years:
        vwf_path = VWF_DIR / f"hourly_cf_{year}.csv"
        cf = pd.read_csv(vwf_path, index_col=0, parse_dates=True)
        if cf.index.tz is None:
            cf.index = cf.index.tz_localize("UTC")
        zone_prices = load_year_prices(year)
        print(f"\n--- {year}: {cf.shape[1]} farms, {len(zone_prices)} price zones ---")
        for _, s in SITES.iterrows():
            farm = s["name"]
            # Farm CSV writes Danish zones as DK1/DK2; ENTSO-E price folders
            # (like every other zone) use the underscore form DK_1/DK_2.
            zone = {"DK1": "DK_1", "DK2": "DK_2"}.get(s.bidding_zone, s.bidding_zone)
            if farm not in cf.columns or zone not in zone_prices:
                continue
            g = cf[farm]
            p = zone_prices[zone]
            mcv = monthly_cv(g, p)
            if mcv.empty:
                continue
            mcv["farm"] = farm
            mcv["country"] = s.country
            mcv["bidding_zone"] = zone
            mcv["basin"] = s.basin
            all_rows.append(mcv)

    if not all_rows:
        print("No CV rows generated.")
        return
    df = pd.concat(all_rows, ignore_index=True)
    # drop low-coverage months
    df = df[df.n_hours >= 500].copy()
    df["date"] = pd.to_datetime(dict(year=df.year, month=df.month, day=1))
    df = df[["farm", "country", "bidding_zone", "basin", "year", "month", "date",
             "n_hours", "gen_MWh_norm", "capture_price", "baseload", "CV"]]
    out_csv = OUT / "monthly_cv_per_farm.csv"
    df.to_csv(out_csv, index=False)
    print(f"\nSaved {len(df)} monthly-CV rows to {out_csv}")
    print(f"  farms covered: {df.farm.nunique()}")
    print(f"  years covered: {sorted(df.year.unique())}")

    # ---- Paul Figure 45 replication (NS farms) ----
    ns = df[(df.basin == "NS") & (df.gen_MWh_norm > 0)].copy()
    if not ns.empty:
        fig, ax = plt.subplots(figsize=(13, 6))
        for farm, sub in ns.groupby("farm"):
            sub = sub.sort_values("date")
            ax.plot(sub["date"], sub["CV"], "-", lw=1, alpha=0.7, label=farm[:18])
        ax.axhline(1.0, color="k", lw=0.5, ls="--", label="CV=1 (no cannibalisation)")
        ax.set_ylabel("Monthly capture value (offshore wind, NS)")
        ax.set_title("Strand A: monthly CV per NS offshore farm (Paul Fig 45 replication)")
        ax.grid(alpha=0.3)
        ax.legend(fontsize=7, ncol=3, loc="lower left")
        plt.tight_layout()
        plt.savefig(OUT / "fig_paul_fig45_NS.png", dpi=130)
        plt.close()
        print(f"Saved Paul-Fig45 replication: {OUT/'fig_paul_fig45_NS.png'}")

    # quick aggregate summary
    summary = (df.groupby(["basin", "year"])
                 .agg(n_farm_months=("CV", "count"),
                      mean_CV=("CV", "mean"),
                      mean_capture=("capture_price", "mean"),
                      mean_baseload=("baseload", "mean"))
                 .round(3))
    print("\n=== summary by basin x year ===")
    print(summary.to_string())


if __name__ == "__main__":
    main()
