"""Grouped-bar comparison: capture value with today's grid vs expanded
transmission, North Sea vs Baltic, under National Trends (scheduled buildout).
Replaces the Baltic-only 'grid bracket' line chart (fig_grid_bracket)."""
import matplotlib.pyplot as plt
import matplotlib as mpl

mpl.rcParams.update({
    "font.size": 11, "axes.titlesize": 13, "axes.labelsize": 12,
    "axes.spines.top": False, "axes.spines.right": False,
    "figure.dpi": 220, "savefig.dpi": 220,
})

NS_BLUE = "#2C5985"
BALTIC_RED = "#A63D40"

# National Trends, scheduled buildout; uncorrected model. Today = measured 2023-24.
today = {"NS": 0.879, "BS": 0.883}
y2030 = {"NS_frozen": 0.84, "NS_exp": 0.84, "BS_frozen": 0.79, "BS_exp": 0.79}
y2040 = {"NS_frozen": 0.57, "NS_exp": 0.64, "BS_frozen": 0.47, "BS_exp": 0.66}

fig, ax = plt.subplots(figsize=(9.2, 5.0))
w = 0.65
solid = dict(width=w, edgecolor="none")
openf = dict(width=w, facecolor="white", linewidth=1.8)

bars = []  # (x, height, style)
# Today group: one bar per basin (only one grid exists)
bars += [(0.0, today["NS"], ("solid", NS_BLUE)), (0.75, today["BS"], ("solid", BALTIC_RED))]
# 2030 group
x0 = 2.35
bars += [(x0, y2030["NS_frozen"], ("solid", NS_BLUE)), (x0+0.75, y2030["NS_exp"], ("open", NS_BLUE)),
         (x0+1.7, y2030["BS_frozen"], ("solid", BALTIC_RED)), (x0+2.45, y2030["BS_exp"], ("open", BALTIC_RED))]
# 2040 group
x1 = 6.4
bars += [(x1, y2040["NS_frozen"], ("solid", NS_BLUE)), (x1+0.75, y2040["NS_exp"], ("open", NS_BLUE)),
         (x1+1.7, y2040["BS_frozen"], ("solid", BALTIC_RED)), (x1+2.45, y2040["BS_exp"], ("open", BALTIC_RED))]

for x, h, (kind, col) in bars:
    if kind == "solid":
        ax.bar(x, h, color=col, **solid)
    else:
        ax.bar(x, h, edgecolor=col, **openf)
    ax.text(x, h + 0.015, f"{h:.2f}", ha="center", va="bottom", fontsize=10, color="#333333")

ax.set_xticks([0.375, x0+1.225, x1+1.225])
ax.set_xticklabels(["Today\n(measured, 2023 to 2024)", "2030", "2040"])
ax.set_ylabel("Capture value")
ax.set_ylim(0, 1.02)
ax.set_title("Capture value with today's grid and with expanded transmission")
ax.yaxis.grid(True, color="#DDDDDD", linewidth=0.8)
ax.set_axisbelow(True)

from matplotlib.patches import Patch
legend = [
    Patch(facecolor=NS_BLUE, label="North Sea, grid as today"),
    Patch(facecolor="white", edgecolor=NS_BLUE, linewidth=1.8, label="North Sea, transmission expanded"),
    Patch(facecolor=BALTIC_RED, label="Baltic, grid as today"),
    Patch(facecolor="white", edgecolor=BALTIC_RED, linewidth=1.8, label="Baltic, transmission expanded"),
]
ax.legend(handles=legend, frameon=False, loc="upper right", fontsize=10)

fig.tight_layout()
fig.savefig("9_Thesis_LaTeX/figures/fig_grid_comparison.png", bbox_inches="tight")
print("saved")
