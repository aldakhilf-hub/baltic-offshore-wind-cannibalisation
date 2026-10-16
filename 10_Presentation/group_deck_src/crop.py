from pathlib import Path
from PIL import Image
FIG = str(Path(__file__).resolve().parents[2] / "9_Thesis_LaTeX/figures") + "/"
HERE = str(Path(__file__).resolve().parents[2] / "10_Presentation/group_deck_src") + "/"
im = Image.open(FIG + "fig_vlcoe_grid_2040.png").convert("RGB")
im.crop((26, 401, 1248, 977)).save(HERE + "vlcoe_frozen.png")
im.crop((1298, 401, 2520, 977)).save(HERE + "vlcoe_optimal.png")
im.crop((740, 1266, 1805, 1348)).save(HERE + "colourbar.png")
f = Image.open(FIG + "fig_study_farms.png").convert("RGB")
f.crop((21, 63, 1679, 738)).save(HERE + "farms.png")
print("crops ok")
