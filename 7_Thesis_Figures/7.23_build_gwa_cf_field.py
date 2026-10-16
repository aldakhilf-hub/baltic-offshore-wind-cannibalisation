"""
7.23_build_gwa_cf_field.py — high-resolution (Global Wind Atlas, 250 m, mosaicked
to ~2 km) offshore capacity-factor field over the North Sea + Baltic, for the
'full smooth sea' granular maps. Downloads per-country GWA capacity-factor (IEC1)
GeoTIFFs (they include each country's EEZ, so together they tile the sea), then
merges and clips to the region.

Output -> 7_Thesis_Figures/results/gwa_cf_field.nc
"""
from pathlib import Path
import urllib.request, os, glob
import numpy as np
import rasterio
from rasterio.merge import merge
from rasterio.enums import Resampling
import xarray as xr

DIR = "/tmp/gwa"; os.makedirs(DIR, exist_ok=True)
OUT = str(Path(__file__).resolve().parents[1] / "7_Thesis_Figures/results/gwa_cf_field.nc")
# sea-bordering countries whose EEZs tile the North Sea + Baltic
COUNTRIES = ["DNK", "DEU", "NLD", "BEL", "FRA", "GBR", "NOR", "SWE",
             "POL", "EST", "LVA", "LTU", "FIN"]

for iso in COUNTRIES:
    f = f"{DIR}/{iso}_cf.tif"
    if os.path.exists(f) and os.path.getsize(f) > 1e6:
        print(iso, "cached", flush=True); continue
    try:
        print("downloading", iso, "...", flush=True)
        urllib.request.urlretrieve(
            f"https://globalwindatlas.info/api/gis/country/{iso}/capacity-factor_IEC1", f)
        print("  ", iso, round(os.path.getsize(f) / 1e6, 1), "MB", flush=True)
    except Exception as e:
        print("  ", iso, "FAILED", e, flush=True)

files = [rasterio.open(f) for f in sorted(glob.glob(f"{DIR}/*_cf.tif"))]
print("mosaicking", len(files), "files -> ~2 km grid", flush=True)
mosaic, transform = merge(files, bounds=(-6, 46.5, 30, 63.5), res=(0.02, 0.02),
                          nodata=0, resampling=Resampling.average)
arr = np.where(mosaic[0] > 0, mosaic[0], np.nan)
ny, nx = arr.shape
xs = transform.c + transform.a * (np.arange(nx) + 0.5)
ys = transform.f + transform.e * (np.arange(ny) + 0.5)
da = xr.DataArray(arr, coords={"y": ys, "x": xs}, dims=["y", "x"], name="capacity_factor")
da.to_netcdf(OUT)
print(f"saved {OUT}  shape {arr.shape}  CF mean {np.nanmean(arr):.3f} "
      f"max {np.nanmax(arr):.3f}", flush=True)
