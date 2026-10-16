"""Build the A1 poster, version 4: two columns, prose next to every figure,
numbered figures and table, Results and Conclusions sections, References.

Left column: Background, Objective, Methodology (paragraph + Figure 2 flow
chart), References. Right column: Results (Figures 3 to 5, Table 1) and
Conclusions. Units are millimetres on the 594 x 841 mm sheet; all text is Arial.
"""
import copy
import json
from pathlib import Path

from lxml import etree
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE, PP_PLACEHOLDER
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Emu, Pt

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = Path.home() / "Downloads/Poster template - new brand.pptx"
FIGS = ROOT / "12_Poster/figures"
OUT = ROOT / "12_Poster/Poster_Bindakhil_A1.pptx"

BLUE, NAVY, ORANGE, GREEN = "0000CD", "000080", "FF4500", "006400"
INK, MUTED, TILE, WHITE, GREY, PALE = "1F1F1F", "5B6170", "F5F5F5", "FFFFFF", "C9CED8", "C9CFF7"
NAVY_T, GREEN_T = "E4E6F4", "E3EFE3"
FONT = "Arial"
NBH = "‑"  # non-breaking hyphen

OV = json.load(open(FIGS / "observed_values.json"))

L, LW = 22, 268
R, RW = 302, 270


def mm(v):
    return Emu(int(round(v * 36000)))


def rgb(h):
    return RGBColor.from_string(h)


prs = Presentation(TEMPLATE)
sld = prs.slides._sldIdLst
for s in list(sld):
    prs.part.drop_rel(s.rId)
    sld.remove(s)
layout = prs.slide_layouts[1]
slide = prs.slides.add_slide(layout)
for ph in list(slide.placeholders):
    ph._element.getparent().remove(ph._element)
for ph in layout.placeholders:
    if ph.placeholder_format.type == PP_PLACEHOLDER.FOOTER:
        slide.shapes._spTree.append(copy.deepcopy(ph._element))


# ------------------------------------------------------------------ helpers
def _run(p, text, size, bold=False, color=INK, italic=False):
    r = p.add_run()
    r.text = text
    f = r.font
    f.name = FONT
    f.size = Pt(size)
    f.bold = bold
    f.italic = italic
    f.color.rgb = rgb(color)
    return r


def text(x, y, w, h, paras, size=16, bold=False, color=INK, align=PP_ALIGN.LEFT,
         anchor=MSO_ANCHOR.TOP, spacing=1.05, after=0, pad=0, numbered=False, skip_first=False):
    tb = slide.shapes.add_textbox(mm(x), mm(y), mm(w), mm(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = mm(pad)
    tf.vertical_anchor = anchor
    for i, para in enumerate(paras):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        p.line_spacing = spacing
        p.space_after = Pt(after)
        if numbered and not (skip_first and i == 0):
            pPr = p._p.get_or_add_pPr()
            pPr.set("marL", str(mm(7)))
            pPr.set("indent", str(-mm(7)))
            bu = etree.SubElement(pPr, qn("a:buAutoNum"))
            bu.set("type", "arabicPeriod")
        runs = [(para, {})] if isinstance(para, str) else para
        for t, o in runs:
            _run(p, t, o.get("size", size), o.get("bold", bold), o.get("color", color), o.get("italic", False))
    return tb


def rect(x, y, w, h, fill=None, line=None, line_w=0.75, dash=False, shape=MSO_SHAPE.RECTANGLE):
    shp = slide.shapes.add_shape(shape, mm(x), mm(y), mm(w), mm(h))
    shp.shadow.inherit = False
    if fill:
        shp.fill.solid()
        shp.fill.fore_color.rgb = rgb(fill)
    else:
        shp.fill.background()
    if line:
        shp.line.color.rgb = rgb(line)
        shp.line.width = Pt(line_w)
        if dash:
            shp.line.dash_style = 4
    else:
        shp.line.fill.background()
    shp.text_frame.text = ""
    return shp


def picture(name, x, y, w, h):
    return slide.shapes.add_picture(str(FIGS / name), mm(x), mm(y), mm(w), mm(h))


def heading(n, x, y, w, txt, lines=1, size=28):
    chip = rect(x, y + 0.5, 12, 12, fill=BLUE)
    tf = chip.text_frame
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    _run(p, str(n), 20, True, WHITE)
    text(x + 16, y - 1.5, w - 16, 13.5 * lines + 2, [txt], size=size, bold=True, color=BLUE, spacing=1.0)


def claim(x, y, w, txt, lines=1):
    text(x, y, w, 7 * lines + 1, [txt], size=17, bold=True, color=NAVY, spacing=1.0)


def caption(x, y, w, h, label, body):
    text(x, y, w, h, [[(label + " ", {"bold": True, "color": INK}), (body, {})]], size=12, color=MUTED, spacing=1.03)


def para(x, y, w, h, runs, size=14.5):
    text(x, y, w, h, [runs] if isinstance(runs, list) else [runs], size=size, color=INK, spacing=1.06)


def box(x, y, w, h, title, body, fill=None, line=None, title_color=NAVY, body_color=INK,
        size=14, title_size=15, align=PP_ALIGN.LEFT):
    rect(x, y, w, h, fill=fill, line=line, line_w=1.25)
    paras = []
    if title:
        paras.append([(title, {"bold": True, "color": title_color, "size": title_size})])
    if body:
        paras.append(body if isinstance(body, list) else [(body, {})])
    text(x + 3, y + 1.5, w - 6, h - 3, paras, size=size, color=body_color,
         anchor=MSO_ANCHOR.MIDDLE, spacing=1.03, align=align, after=1.2)


def down_arrow(xc, y, h=10, w=8, color=BLUE):
    shp = slide.shapes.add_shape(MSO_SHAPE.DOWN_ARROW, mm(xc - w / 2), mm(y), mm(w), mm(h))
    shp.shadow.inherit = False
    shp.fill.solid()
    shp.fill.fore_color.rgb = rgb(color)
    shp.line.fill.background()
    return shp


def cell(x, y, w, h, paras, size=13, bold=False, color=INK, fill=WHITE, align=PP_ALIGN.LEFT):
    rect(x, y, w, h, fill=fill, line=GREY, line_w=0.6)
    text(x + 2, y + 0.8, w - 4, h - 1.6, paras, size=size, bold=bold, color=color,
         anchor=MSO_ANCHOR.MIDDLE, spacing=1.02, align=align)


# ------------------------------------------------------------------ header
text(22, 57, 44, 62, ["00"], size=96, bold=True, color=BLUE, spacing=0.9)
text(68, 58, 318, 64,
     [[("Offshore wind cannibalisation in the Baltic and North Sea: ", {"bold": True, "color": NAVY}),
       ("how much value is lost depends on the grid built alongside the farms", {"bold": False, "color": BLUE})]],
     size=37, spacing=1.0)
text(393, 60, 179, 60,
     [[("Faisal Bindakhil", {"bold": True, "color": NAVY, "size": 26})],
      "MSc Sustainable Energy Futures, Imperial College London",
      "Supervisor: Dr Ruslan Galimov, RWE"],
     size=17, color=INK, spacing=1.05, after=2)

# ================================================================== LEFT COLUMN
# 1 Background
Y = 136
heading(1, L, Y, LW, "Background")
para(L, Y + 18, LW, 50,
     [("Europe's next wave of offshore wind moves from the mature North Sea into the enclosed Baltic Sea. "
       "Wind farms in one sea generate in the same hours, so when they all produce the price falls, and a farm sells most of its output when prices are low. "
       "The share of the average market price a farm actually receives is its ", {}),
      ("capture value", {"bold": True}),
      (" [1]. It falls as more wind is built, an effect known as cannibalisation. Figure 1 shows the decline observed since 2017. "
       "The Baltic is the test case because its planned buildout is far larger than today's fleet and its grid is weakly connected to its neighbours. "
       "This work extends two earlier Imperial theses on the topic [6].", {})])
picture("fig_p_observed.png", L, Y + 70, LW, 62)
caption(L, Y + 134, LW, 12, "Figure 1:",
        f"Monthly capture value of the observed farms, 2017 to 2024, with a 24{NBH}month mean for each sea (thick lines). "
        f"North Sea {OV['North Sea'][0]:.2f} to {OV['North Sea'][1]:.2f}, Baltic {OV['Baltic'][0]:.2f} to {OV['Baltic'][1]:.2f}. Data: ENTSO{NBH}E [5].")
for i, (big, col, body) in enumerate([
        ("×9", NAVY, [("North Sea", {"bold": True, "color": NAVY}),
                      (": 18.5 GW today to 165 GW by 2040. Open sea, many neighbours.", {})]),
        ("×19", ORANGE, [("Baltic", {"bold": True, "color": ORANGE}),
                         (": 2.6 GW to 50 GW. Enclosed sea, weakly interconnected.", {})])]):
    tx = L + i * 138
    rect(tx, Y + 150, 130, 28, fill=TILE)
    text(tx + 3, Y + 151, 34, 26, [big], size=32, bold=True, color=col, anchor=MSO_ANCHOR.MIDDLE)
    text(tx + 39, Y + 152, 89, 24, [body], size=12.5, color=INK, anchor=MSO_ANCHOR.MIDDLE, spacing=1.03)

# 2 Objective
Y = 322
heading(2, L, Y, LW, "Objective")
text(L, Y + 18, LW, 52,
     [[("Measure how much of its value offshore wind loses as the planned fleets are built, and answer three questions:", {"bold": True, "color": NAVY})],
      "How do the two seas compare today, and how will they compare once the planned farms are built?",
      "What causes the loss of value, and how much of it can be avoided by building the grid differently?",
      "Can a model trained on the past project this future, or must the market be rebuilt from its parts?"],
     size=15.5, color=INK, spacing=1.05, after=2, numbered=True, skip_first=True)

# 3 Methodology
Y = 400
heading(3, L, Y, LW, "Methodology")
para(L, Y + 18, LW, 46,
     [("Two models estimate capture value from different inputs (Figure 2). The ", {}),
      ("statistical model", {"bold": True, "color": NAVY}),
      (" is a regression fitted to eight years of hourly prices at 31 farms [5], with each farm's output reconstructed from ERA5 weather [2]. "
       "It learns how market conditions such as gas prices, renewable share and interconnection map to capture value. The ", {}),
      ("power‑system model", {"bold": True, "color": GREEN}),
      (", PyPSA‑Eur [3], rebuilds every hour's price from the plants, transmission grid and demand of the whole of Europe, "
       "under the official ENTSO‑E scenarios for 2030 and 2040 [4]. Both are compared with observed 2023 prices before either is trusted.", {})],
     size=14.5)
cy = Y + 68
LX, RX, BW = L, L + 140, 128
lc, rc = LX + BW / 2, RX + BW / 2
box(L, cy, LW, 26, "ERA5 weather reanalysis [2], shared by both models",
    "hourly wind speeds, converted into the hourly output of every wind farm", fill=TILE)
cy += 26
for xc in (lc, rc):
    down_arrow(xc, cy + 1)
cy += 12
box(LX, cy, BW, 52, "What happened",
    f"day{NBH}ahead prices at 31 farms, 2017 to 2024 (ENTSO{NBH}E [5]), and the market conditions behind them",
    fill=TILE)
box(RX, cy, BW, 52, "How the system is built",
    f"plants, grid and demand for all of Europe (PyPSA{NBH}Eur [3]), and the 2030 and 2040 expansion plans (TYNDP [4])",
    fill=TILE, title_color=GREEN)
cy += 52
down_arrow(lc, cy + 1, color=NAVY)
down_arrow(rc, cy + 1, color=GREEN)
cy += 12
box(LX, cy, BW, 34, "Statistical model", "learns how market conditions map to capture value",
    fill=NAVY, title_color=WHITE, body_color=WHITE)
box(RX, cy, BW, 34, "Power‑system model", "solves every hour's dispatch and price for the whole grid",
    fill=GREEN, title_color=WHITE, body_color=WHITE)
cy += 34
down_arrow(lc, cy + 1, color=NAVY)
down_arrow(rc, cy + 1, color=GREEN)
cy += 12
box(LX, cy, BW, 38, "Output: capture value today and in the near term",
    "and which conditions drive it", line=NAVY)
box(RX, cy, BW, 38, "Output: capture value in 2030 and 2040",
    "with today's grid, and with the grid expanded", line=GREEN, title_color=GREEN)
cy += 38
down_arrow(lc, cy + 1)
down_arrow(rc, cy + 1)
cy += 12
box(L, cy, LW, 40, "Same output, checked the same way",
    [("Capture value = a farm's average selling price ÷ the market's average price. Both models are compared with observed 2023 prices before either is trusted, and they agree within 0.5 percentage points.", {})],
    line=BLUE, title_color=BLUE)
cy += 42
caption(L, cy, LW, 8, "Figure 2:", "The two models, their inputs and their common output.")
cy += 14
text(L, cy, LW, 8, ["References"], size=13, bold=True, color=BLUE)
refs = [
    "[1] L. Hirth. The market value of variable renewables. Energy Economics, 38:218–236, 2013.",
    "[2] L. Hayes, M. Stocks and A. Blakers. Accurate long‑term power generation model for offshore wind farms in Europe using ERA5 reanalysis. Energy, 229:120603, 2021.",
    "[3] J. Hörsch, F. Hofmann, D. Schlachtberger and T. Brown. PyPSA‑Eur: an open optimisation model of the European transmission system. Energy Strategy Reviews, 22:207–215, 2018.",
    "[4] ENTSO‑E and ENTSOG. TYNDP 2024 Scenarios Report, final version, January 2025.",
    "[5] ENTSO‑E Transparency Platform. Day‑ahead prices and generation data, 2017 to 2024.",
    "[6] P. Jacquet (2024) and M. Efthymiadou (2025). MSc theses, Imperial College London, on offshore wind cannibalisation in Northern Europe and in the UK.",
]
text(L, cy + 9, LW, 790 - (cy + 9), refs, size=9.5, color=INK, spacing=1.02, after=1)

# ================================================================== RIGHT COLUMN
# 4 Results
Y = 136
heading(4, R, Y, RW, "Results")
claim(R, Y + 17, RW, "Capture value falls in both seas, and the Baltic falls furthest unless the grid is expanded", lines=2)
picture("fig_p_arc.png", R, Y + 33, RW, 92)
caption(R, Y + 127, RW, 12, "Figure 3:",
        "Capture value observed to 2024 and projected to 2040 under the National Trends scenario, with the grid as today (dashed) and with transmission expanded (dotted).")
tiles = [
    ([("0.88", {"color": NAVY}), (" = ", {"color": MUTED, "size": 18}), ("0.88", {"color": NAVY})], "today, both seas"),
    ([("0.47", {"color": ORANGE}), (" vs ", {"color": MUTED, "size": 18}), ("0.57", {"color": NAVY})], "2040, today's grid: Baltic vs North Sea"),
    ([("0.66", {"color": GREEN})], "2040, grid expanded: Baltic"),
]
for i, (big, body) in enumerate(tiles):
    tx = R + i * 93
    rect(tx, Y + 141, 84, 25, fill=TILE)
    text(tx + 3, Y + 142, 78, 12, [big], size=28, bold=True, spacing=0.95)
    text(tx + 3, Y + 155, 78, 10, [body], size=11, color=INK, spacing=1.0)
para(R, Y + 170, RW, 26,
     [("Both seas start level. Under the planned buildout and today's grid the Baltic loses almost half of its present value by 2040, against a third in the North Sea. "
       "With transmission expanded the Baltic recovers and is level with the North Sea again, so its extra loss comes from the grid around the sea, which Figure 4 separates into its parts.", {})],
     size=13.5)

Y = 338
claim(R, Y, RW, "Regression is better for the short term, the power‑system model for the long term", lines=2)
para(R, Y + 16, RW, 20,
     [("Table 1 compares the two models on the tasks the thesis needs. The statistical model is closer on the record it was fitted to, but gives almost the same answer whichever future it is shown, "
       "so the 2040 projections come from the power‑system model, which responds to the buildout and the grid.", {})],
     size=13.5)
cols = [(R, 88), (R + 88, 91), (R + 179, 91)]
ty = Y + 38
cell(cols[0][0], ty, cols[0][1], 11, [""], fill=NAVY)
cell(cols[1][0], ty, cols[1][1], 11, ["Statistical model"], size=13, bold=True, color=WHITE, fill=NAVY, align=PP_ALIGN.CENTER)
cell(cols[2][0], ty, cols[2][1], 11, ["Power‑system model"], size=13, bold=True, color=WHITE, fill=NAVY, align=PP_ALIGN.CENTER)
rows = [
    ("Today and the near term", ("better: error 0.01 on the record", True), ("error 0.05, growing with congestion", False)),
    ("2030 and 2040", ("same answer whichever future it is shown", False), ("better: responds to the buildout and the grid", True)),
    ("Congestion, or a different grid", ("cannot represent them", False), ("better: a price at every grid node", True)),
    ("Negative prices, the most cannibalised zone", ("better: learned from the record", True), ("cannot produce them", False)),
]
rh = 12
for i, (lab, sm, pm) in enumerate(rows):
    ry = ty + 11 + i * rh
    cell(cols[0][0], ry, cols[0][1], rh, [lab], size=12.5, bold=True, color=NAVY, fill=TILE)
    for (cx, cw), (txt, win), col, tint in [(cols[1], sm, NAVY, NAVY_T), (cols[2], pm, GREEN, GREEN_T)]:
        cell(cx, ry, cw, rh, [txt], size=12.5, bold=win, color=col if win else INK, fill=tint if win else WHITE)
caption(R, ty + 11 + 4 * rh + 1.5, RW, 7, "Table 1:", "Which model is better for which task, from the comparison of both with observed prices.")

Y = 452
claim(R, Y, RW, "Half of the Baltic's extra loss is grid congestion")
picture("fig_p_decomposition.png", R, Y + 9, RW, 46)
caption(R, Y + 56, RW, 12, "Figure 4:",
        "The 2040 loss of capture value split into the buildout itself, which no grid removes, and grid congestion, which transmission removes.")
para(R, Y + 69, RW, 20,
     [("The Baltic loses 0.19 to congestion, three times the North Sea's 0.06, while its loss from the buildout alone, 0.22, is no larger than the North Sea's 0.25. "
       "Removing the congestion is what lifts the Baltic from 0.47 to 0.66.", {})],
     size=13.5)

Y = 544
claim(R, Y, RW, "In money: the grid makes Baltic sites bankable")
picture("fig_p_maps.png", R, Y + 9, RW, 150)
caption(R, Y + 160, RW, 24, "Figure 5:",
        f"Break{NBH}even price for a new offshore wind farm in 2040 (its cost of energy divided by its capture value), with today's grid and with transmission expanded. "
        f"Below the dashed 70 EUR/MWh line a farm pays itself back. With today's grid the Baltic break{NBH}even price rises from 87 to 121 EUR/MWh between 2025 and 2040, "
        "because value falls faster than cost. Expanding the grid lowers it by 33 EUR/MWh, and Polish and Danish waters fall below 70.")

# 5 Conclusions
Y = 730
heading(5, R, Y, RW, "Conclusions")
rect(R, Y + 17, RW, 790 - (Y + 17), fill=NAVY)
text(R + 5, Y + 20, RW - 36, 28,
     ["The planned Baltic wind farms are worth what the grid built alongside them allows.",
      "Half of the Baltic's loss is a design choice: transmission removes it.",
      "Even with an expanded grid the Baltic captures a quarter less than today, a loss that belongs in auction and PPA pricing."],
     size=12.5, color=WHITE, spacing=1.03, after=1.5, numbered=True)
text(R + 5, Y + 47, RW - 36, 12,
     [[("Limitations: ", {"bold": True, "color": PALE}),
       ("the power‑system model produces no negative prices and uses a simplified grid, so the DK2 zone is set aside, and the figures are for the National Trends scenario. Full thesis and model: scan the code.", {})]],
     size=10.5, color=PALE, spacing=1.02)
qr = rect(R + RW - 25, Y + 25, 20, 20, line=PALE, line_w=1.0, dash=True)
tf = qr.text_frame
tf.vertical_anchor = MSO_ANCHOR.MIDDLE
tf.margin_left = tf.margin_right = 0
p = tf.paragraphs[0]
p.alignment = PP_ALIGN.CENTER
_run(p, "QR", 10, False, PALE)

prs.save(OUT)
print("saved", OUT)
