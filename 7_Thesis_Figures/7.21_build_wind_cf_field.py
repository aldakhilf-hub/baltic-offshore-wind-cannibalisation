"""
7.21_build_wind_cf_field.py — build the high-resolution offshore capacity-factor
field over the North Sea + Baltic, ONCE (year-independent wind resource). This is
the spatial 'Layer 1' for the granular revenue-density maps; the per-zone, per-year
value is multiplied on later (7.22).

ERA5 via atlite, 0.25 deg (~25 km). One representative year (2019) is enough for the
mean-CF spatial pattern. Output: a per-cell mean capacity factor field.

Output -> 7_Thesis_Figures/results/wind_cf_field.nc  (+ a quick PNG preview)
"""
from pathlib import Path
import numpy as np
import atlite
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

OUT = Path(__file__).resolve().parents[1] / "7_Thesis_Figures/results"
CUTOUT = Path.home() / "pypsa-eur/cutouts/ns_baltic_2019.nc"
CUTOUT.parent.mkdir(parents=True, exist_ok=True)

print("creating/preparing cutout (downloads ERA5 wind for the region, may take a while)...", flush=True)
cutout = atlite.Cutout(path=str(CUTOUT), module="era5",
                       x=slice(-6, 30), y=slice(46, 63), time="2019")
cutout.prepare(features=["wind"])
print("cutout ready:", dict(cutout.data.sizes), flush=True)

# mean capacity factor per cell (offshore turbine; pattern is robust to turbine choice)
turbine = None
for t in ("NREL_ReferenceTurbine_5MW_offshore", "Vestas_V112_3MW", "Vestas_V90_3MW"):
    try:
        cf = cutout.wind(turbine=t, capacity_factor=True)
        turbine = t
        break
    except Exception as e:
        print(f"  turbine {t} failed: {e}", flush=True)
print("using turbine:", turbine, "cf dims:", dict(cf.sizes), flush=True)

cf_mean = cf.mean("time") if "time" in cf.dims else cf   # capacity_factor=True already time-averages
cf_mean.name = "capacity_factor"
cf_mean.attrs["turbine"] = str(turbine)
cf_mean.to_netcdf(OUT / "wind_cf_field.nc")
print(f"saved wind_cf_field.nc  mean CF {float(cf_mean.mean()):.3f}  range "
      f"{float(cf_mean.min()):.3f}-{float(cf_mean.max()):.3f}", flush=True)

# quick preview
fig, ax = plt.subplots(figsize=(7, 7))
cf_mean.plot(ax=ax, cmap="viridis", cbar_kwargs={"label": "mean capacity factor"})
ax.set_title("Offshore capacity-factor field (ERA5 2019, ~25 km)")
fig.tight_layout(); fig.savefig(OUT / "fig_cf_field_preview.png", dpi=150)
print("saved fig_cf_field_preview.png", flush=True)
