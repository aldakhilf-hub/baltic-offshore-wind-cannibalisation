"""High-resolution basemap of Europe's two offshore wind seas for the Morph zoom sequence.
Outputs europe_map.png plus crops.json with crop fractions for the Europe / North Sea / Baltic views.
"""
from pathlib import Path
import json, math
import numpy as np, pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import cartopy.feature as cfeature
from cartopy.io import shapereader
from shapely.geometry import shape
from matplotlib.patches import PathPatch
from matplotlib.path import Path
from shapely.geometry import MultiPolygon, Polygon

HERE = str(Path(__file__).resolve().parents[2] / "10_Presentation/group_deck_src") + "/"
R = str(Path(__file__).resolve().parents[2] / "2_Regression_Model") + "/"

LAND, SEAC, COAST, BORDER = "#ECEAE4", "#DCE7F1", "#9C9C9C", "#C4C4C4"
PROD, MID, PLAN = "#000080", "#8080C0", "#000080"
NSBLUE, BALRED = "#000080", "#FF4500"

EXT = dict(lon0=-13.0, lon1=33.0, lat0=48.0, lat1=64.0)     # base extent (Europe view)
VIEWS = {
    "europe": dict(lon0=-12.0, lon1=33.0, lat0=50.7, lat1=61.7),
    "northsea": dict(lon0=-7.0, lon1=15.0, lat0=51.0, lat1=56.7),
    "baltic": dict(lon0=9.0, lon1=31.0, lat0=53.5, lat1=58.9),
}

proj = ccrs.Mercator()
pc = ccrs.PlateCarree()


def xy(lon, lat):
    x, y = proj.transform_point(lon, lat, pc)
    return x, y


x0, y0 = xy(EXT["lon0"], EXT["lat0"])
x1, y1 = xy(EXT["lon1"], EXT["lat1"])
aspect = (x1 - x0) / (y1 - y0)
W_IN = 20.0
fig = plt.figure(figsize=(W_IN, W_IN / aspect), dpi=300)
ax = fig.add_axes([0, 0, 1, 1], projection=proj)
ax.set_extent([EXT["lon0"], EXT["lon1"], EXT["lat0"], EXT["lat1"]], crs=pc)
ax.set_facecolor(SEAC)

# try 10 m detail, fall back to the cached 50 m
res = "10m"
try:
    land_shp = shapereader.natural_earth(res, "physical", "land")
    bord_shp = shapereader.natural_earth(res, "cultural", "admin_0_boundary_lines_land")
    list(shapereader.Reader(land_shp).geometries())
except Exception as e:  # offline: use 50 m
    print("10m unavailable, using 50m:", e)
    res = "50m"
    land_shp = shapereader.natural_earth(res, "physical", "land")
    bord_shp = shapereader.natural_earth(res, "cultural", "admin_0_boundary_lines_land")
ax.add_geometries(shapereader.Reader(land_shp).geometries(), pc, facecolor=LAND, edgecolor=COAST, linewidth=0.5, zorder=1)
ax.add_geometries(shapereader.Reader(bord_shp).geometries(), pc, facecolor="none", edgecolor=BORDER,
                  linewidth=0.45, linestyle=(0, (2, 2)), zorder=2)

# EMODnet farm polygons by status
g = json.load(open(HERE + "windfarms.json"))
groups = {"Planned": [], "Approved": [], "Construction": [], "Production": []}
for f in g["features"]:
    st = f["properties"]["status"]
    if st in groups:
        groups[st].append(shape(f["geometry"]).buffer(0))
style = {
    "Planned": dict(facecolor="none", edgecolor=PLAN, linewidth=0.6, linestyle=(0, (2, 1.5)), zorder=3),
    "Approved": dict(facecolor=MID, edgecolor=MID, linewidth=0.4, alpha=0.55, zorder=4),
    "Construction": dict(facecolor=MID, edgecolor=MID, linewidth=0.4, alpha=0.85, zorder=5),
    "Production": dict(facecolor=PROD, edgecolor=PROD, linewidth=0.4, zorder=6),
}
for st, geoms in groups.items():
    if geoms:
        ax.add_geometries(geoms, pc, **style[st])

# the 31 study farms as rings
sites = pd.read_csv(R + "data/wind_farms_strandA.csv", comment="#")
for _, r in sites.iterrows():
    col = NSBLUE if r.basin == "NS" else BALRED
    ax.plot(r.lon, r.lat, marker="o", markersize=8, markerfacecolor="none", markeredgecolor="white",
            markeredgewidth=3.2, transform=pc, zorder=8)
    ax.plot(r.lon, r.lat, marker="o", markersize=8, markerfacecolor="none", markeredgecolor=col,
            markeredgewidth=1.6, transform=pc, zorder=9)

ax.spines["geo"].set_visible(False)
fig.savefig(HERE + "europe_map.png", dpi=300, facecolor=SEAC)
print("resolution used:", res)

# crop fractions for each view (fractions of the full image from left/top)
crops = {}
for k, v in VIEWS.items():
    vx0, vy0 = xy(v["lon0"], v["lat0"])
    vx1, vy1 = xy(v["lon1"], v["lat1"])
    crops[k] = dict(left=(vx0 - x0) / (x1 - x0), right=(x1 - vx1) / (x1 - x0),
                    top=(y1 - vy1) / (y1 - y0), bottom=(vy0 - y0) / (y1 - y0),
                    aspect=(vx1 - vx0) / (vy1 - vy0))
json.dump(dict(image_aspect=aspect, crops=crops), open(HERE + "crops.json", "w"), indent=1)
print(json.dumps(crops, indent=1))
