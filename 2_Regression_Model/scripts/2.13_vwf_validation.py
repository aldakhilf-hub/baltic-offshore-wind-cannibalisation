"""
2.13_vwf_validation.py — validate the Virtual Wind Farm against OBSERVED
offshore generation.

Neither predecessor thesis validated its synthetic wind output directly against
metered generation (Jacquet cites Hayes's UK calibration). We can: ENTSO-E
observed offshore generation per zone (cached by Track 1's 1.04) vs the VWF
output of this project's registry farms aggregated to the same zones.

The VWF covers a SUBSET of each zone's fleet (registry farms, capacity-weighted,
commissioned <= year), so the comparison is on SHAPE, not level: hourly/daily/
monthly Pearson correlations, plus a normalised monthly-energy overlay figure.
High shape correlation is what matters — capture value is generation-WEIGHTED
price, so CV accuracy needs the timing right, not the absolute MW.

Outputs -> results/08_vwf_validation/: vwf_validation_metrics.csv,
fig_vwf_vs_observed.png

Usage: python 2.13_vwf_validation.py   (cached data only; ~1 min)
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
PV = ROOT.parent / "1_PyPSA_Model"
OUT = ROOT / "results" / "08_vwf_validation"
OUT.mkdir(parents=True, exist_ok=True)

ZMAP = {"DE_LU": "DE", "NL": "NL", "BE": "BE", "DK1": "DK1", "DK2": "DK2",
        "DK_1": "DK1", "DK_2": "DK2"}
YEARS = [2019, 2023, 2024]  # 2024 added 2026-06-12 (observed generation cached by 1.04)

sites = pd.read_csv(ROOT / "data/wind_farms_strandA.csv", comment="#")
sites["zone"] = sites.bidding_zone.map(ZMAP)
sites = sites[sites.zone.notna() & (sites.status == "operational")]

rows, panels = [], {}
for year in YEARS:
    obs_f = PV / f"data/observed_generation/offwind_gen_{year}.csv"
    vwf_f = ROOT / f"data/vwf/hourly_cf_{year}.csv"
    if not (obs_f.exists() and vwf_f.exists()):
        print(f"  missing cached data for {year}, skipping")
        continue
    g = pd.read_csv(obs_f, parse_dates=["timestamp_utc"])
    g["timestamp_utc"] = pd.to_datetime(g.timestamp_utc, utc=True)
    obs = g.pivot(index="timestamp_utc", columns="zone", values="gen_MW")
    cf = pd.read_csv(vwf_f, index_col=0, parse_dates=True)
    if cf.index.tz is None:
        cf.index = cf.index.tz_localize("UTC")
    for zone in ["DE", "NL", "BE", "DK1", "DK2"]:
        if zone not in obs.columns:
            continue
        sub = sites[(sites.zone == zone) & (sites.commissioning_year <= year)]
        farms = [f for f in sub.name if f in cf.columns]
        if not farms:
            continue
        caps = sub.set_index("name").loc[farms, "capacity_MW"]
        vwf = (cf[farms] * caps).sum(axis=1)
        d = pd.concat([obs[zone].rename("obs"), vwf.rename("vwf")], axis=1).dropna()
        d = d[d.obs >= 0]
        if len(d) < 1000:
            continue
        daily = d.resample("D").mean()
        monthly = d.resample("MS").sum()
        rows.append({"zone": zone, "year": year,
                     "n_hours": len(d),
                     "vwf_capacity_MW": float(caps.sum()),
                     "r_hourly": d.obs.corr(d.vwf),
                     "r_daily": daily.obs.corr(daily.vwf),
                     "r_monthly": monthly.obs.corr(monthly.vwf)})
        if year == 2023:
            panels[zone] = monthly / monthly.mean()   # normalised shape overlay

res = pd.DataFrame(rows)
res.round(3).to_csv(OUT / "vwf_validation_metrics.csv", index=False)
print("VWF vs observed offshore generation (shape validation):")
print(res.round(3).to_string(index=False))
print(f"\nmedian hourly r = {res.r_hourly.median():.3f}, "
      f"median monthly r = {res.r_monthly.median():.3f}")

fig, axes = plt.subplots(1, len(panels), figsize=(2.9 * len(panels), 4.0),
                         sharey=True)
for ax, (zone, m) in zip(np.atleast_1d(axes), panels.items()):
    ax.plot(m.index, m.obs, "k-", lw=1.8, label="observed (ENTSO-E)")
    ax.plot(m.index, m.vwf, "-", color="#c0392b", lw=1.8, label="VWF (registry farms)")
    r = res[(res.zone == zone) & (res.year == 2023)].r_hourly.iloc[0]
    ax.set_title(f"{zone} 2023 (hourly r = {r:.2f})", fontsize=11)
    ax.tick_params(labelsize=8, rotation=45)
    ax.grid(alpha=0.3)
np.atleast_1d(axes)[0].set_ylabel("monthly energy (normalised)")
np.atleast_1d(axes)[0].legend(fontsize=9)
fig.suptitle("Virtual wind farm vs observed offshore generation", fontsize=13)
fig.tight_layout()
fig.savefig(OUT / "fig_vwf_vs_observed.png", dpi=200)
print(f"\nSaved -> {OUT}/")
