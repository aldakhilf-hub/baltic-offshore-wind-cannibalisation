"""Poster map pair, stacked for a 270 mm column: break-even price for offshore
wind in 2040 with today's grid (top) and with transmission expanded (bottom),
one shared vertical colour bar. Reads the fields exported by p1."""
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import cartopy.feature as cfeature

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "12_Poster/figures"
MM = 1 / 25.4
REF = 70.0
EXTENT = [3.0, 30.3, 52.0, 61.5]
W_MM, H_MM = 270, 150

plt.rcParams.update({"font.family": "Arial", "font.size": 20})

z = np.load(OUT / "vlcoe_fields_2040.npz")
x, y, vf, vo = z["x"], z["y"], z["vf"], z["vo"]

fig = plt.figure(figsize=(W_MM * MM, H_MM * MM))
gs = fig.add_gridspec(2, 2, width_ratios=[1, 0.045], hspace=0.14, wspace=0.04,
                      left=0.005, right=0.895, top=0.95, bottom=0.01)
axes = [fig.add_subplot(gs[i, 0], projection=ccrs.PlateCarree()) for i in range(2)]
for ax, v, ttl in [(axes[0], vf, "2040, grid as today"), (axes[1], vo, "2040, transmission expanded")]:
    ax.set_extent(EXTENT, crs=ccrs.PlateCarree())
    ax.add_feature(cfeature.LAND.with_scale("50m"), facecolor="#ECECEC", zorder=0)
    mesh = ax.pcolormesh(x, y, np.ma.masked_invalid(v), cmap="RdYlGn_r", vmin=45, vmax=160,
                         shading="auto", transform=ccrs.PlateCarree(), zorder=1, rasterized=True)
    ax.contour(x, y, np.ma.masked_invalid(v), levels=[REF], colors="black", linewidths=1.4,
               linestyles="--", transform=ccrs.PlateCarree(), zorder=3)
    ax.add_feature(cfeature.COASTLINE.with_scale("50m"), lw=0.6, edgecolor="#777777", zorder=4)
    ax.add_feature(cfeature.BORDERS.with_scale("50m"), lw=0.4, edgecolor="#AAAAAA", zorder=4)
    ax.set_title(ttl, fontsize=22, color="#222222", pad=5)
    for sp in ax.spines.values():
        sp.set_edgecolor("#999999")
    ax.text(5.0, 55.8, "North Sea", transform=ccrs.PlateCarree(), fontsize=17, color="#222222",
            style="italic", ha="center", zorder=5)
    ax.text(19.5, 57.4, "Baltic Sea", transform=ccrs.PlateCarree(), fontsize=17, color="#222222",
            style="italic", ha="center", zorder=5)
cax = fig.add_subplot(gs[:, 1])
cb = fig.colorbar(mesh, cax=cax, orientation="vertical", extend="both")
cb.set_label("break-even price, EUR/MWh", fontsize=20)
cb.ax.tick_params(labelsize=19)
fig.savefig(OUT / "fig_p_maps.png", dpi=220, facecolor="white")
w, h = fig.get_size_inches()
print(f"saved fig_p_maps.png: {w*25.4:.0f} x {h*25.4:.0f} mm")
