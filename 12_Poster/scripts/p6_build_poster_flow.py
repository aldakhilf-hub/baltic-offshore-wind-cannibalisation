"""Build the A1 poster (two columns) on the Imperial 'new brand' template.

Left column: Background, Objective, Method as a flow chart (ERA5 weather into
both models, different other inputs, the same output). Right column: results,
including a small 'which model for what' table, and conclusions. Units are
millimetres on the 594 x 841 mm sheet; all text is Arial.
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
NAVY_T, GREEN_T = "E4E6F4", "E3EFE3"      # tints for the winning cells
FONT = "Arial"
NBH = "‑"  # non-breaking hyphen

OV = json.load(open(FIGS / "observed_values.json"))

L, LW = 22, 268      # left column
R, RW = 302, 270     # right column


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
            _run(p, t, o.get("size", size), o.get("bold", bold), o.get("color", color))
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


def box(x, y, w, h, title, body, fill=None, line=None, title_color=NAVY, body_color=INK,
        size=15, title_size=16.5, align=PP_ALIGN.LEFT):
    rect(x, y, w, h, fill=fill, line=line, line_w=1.25)
    paras = []
    if title:
        paras.append([(title, {"bold": True, "color": title_color, "size": title_size})])
    if body:
        paras.append(body if isinstance(body, list) else [(body, {})])
    text(x + 3, y + 1.5, w - 6, h - 3, paras, size=size, color=body_color,
         anchor=MSO_ANCHOR.MIDDLE, spacing=1.03, align=align, after=1.5)


def down_arrow(xc, y, h=12, w=9, color=BLUE):
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
picture("fig_p_mechanism.png", L, Y + 18, LW, 52)
text(L, Y + 72, LW, 13,
     ["Wind farms in one sea produce in the same hours, so supply peaks together and the price every farm receives falls."],
     size=15, color=MUTED, spacing=1.03)
picture("fig_p_observed.png", L, Y + 89, LW, 72)
text(L, Y + 163, LW, 17,
     [[("Capture value", {"bold": True, "color": INK}),
       (f" is the share of the average market price a farm actually receives. Both seas slide: North Sea "
        f"{OV['North Sea'][0]:.2f} to {OV['North Sea'][1]:.2f}, Baltic {OV['Baltic'][0]:.2f} to {OV['Baltic'][1]:.2f} "
        f"(24{NBH}month means, 2017 to 2024).", {})]],
     size=15, color=MUTED, spacing=1.03)
for i, (big, col, body) in enumerate([
        ("×9", NAVY, [("North Sea", {"bold": True, "color": NAVY}),
                      (": 18.5 GW today to 165 GW by 2040. Open sea, many neighbours.", {})]),
        ("×19", ORANGE, [("Baltic", {"bold": True, "color": ORANGE}),
                         (": 2.6 GW to 50 GW. Enclosed sea, weakly interconnected.", {})])]):
    tx = L + i * 138
    rect(tx, Y + 184, 130, 34, fill=TILE)
    text(tx + 3, Y + 185, 36, 32, [big], size=38, bold=True, color=col, anchor=MSO_ANCHOR.MIDDLE)
    text(tx + 41, Y + 186, 87, 30, [body], size=13.5, color=INK, anchor=MSO_ANCHOR.MIDDLE, spacing=1.03)

# 2 Objective
Y = 362
heading(2, L, Y, LW, "Objective")
text(L, Y + 18, LW, 60,
     [[("Measure how much of its value offshore wind loses as the planned fleets are built, and answer three questions:", {"bold": True, "color": NAVY})],
      "How do the two seas compare today, and how will they compare once the planned farms are built?",
      "What causes the loss of value, and how much of it can be avoided by building the grid differently?",
      "Can a model trained on the past project this future, or must the market be rebuilt from its parts?"],
     size=16.5, color=INK, spacing=1.05, after=2, numbered=True, skip_first=True)

# 3 Method: flow chart
Y = 434
heading(3, L, Y, LW, "Method: two models, one output")
cy = Y + 20
LX, RX, BW = L, L + 140, 128          # two lanes
lc, rc = LX + BW / 2, RX + BW / 2     # lane centres
box(L, cy, LW, 36, "ERA5 weather reanalysis, shared by both models",
    "hourly wind speeds, converted into the hourly output of every wind farm", fill=TILE, size=15.5)
cy += 36
for xc in (lc, rc):
    down_arrow(xc, cy + 1, h=12)
cy += 14
box(LX, cy, BW, 78, "What happened",
    f"day-ahead prices at 31 farms, 2017 to 2024 (ENTSO{NBH}E), and the market conditions behind them: gas and carbon prices, renewable share, interconnection, flexibility",
    fill=TILE, size=15.5)
box(RX, cy, BW, 78, "How the system is built",
    f"every power plant, transmission line and demand centre in Europe (PyPSA{NBH}Eur), and the official 2030 and 2040 expansion plans (ENTSO{NBH}E TYNDP)",
    fill=TILE, title_color=GREEN, size=15.5)
cy += 78
down_arrow(lc, cy + 1, h=12, color=NAVY)
down_arrow(rc, cy + 1, h=12, color=GREEN)
cy += 14
box(LX, cy, BW, 46, "Statistical model", "a regression that learns how market conditions map to capture value",
    fill=NAVY, title_color=WHITE, body_color=WHITE, size=15.5)
box(RX, cy, BW, 46, "Power‑system model", f"PyPSA{NBH}Eur solves every hour's dispatch and price for the whole grid",
    fill=GREEN, title_color=WHITE, body_color=WHITE, size=15.5)
cy += 46
down_arrow(lc, cy + 1, h=12, color=NAVY)
down_arrow(rc, cy + 1, h=12, color=GREEN)
cy += 14
box(LX, cy, BW, 52, "Output: capture value today and in the near term",
    "and which conditions drive it", line=NAVY, size=15.5, title_size=16.5)
box(RX, cy, BW, 52, "Output: capture value in 2030 and 2040",
    "with today's grid, and with the grid expanded", line=GREEN, title_color=GREEN, size=15.5, title_size=16.5)
cy += 52
down_arrow(lc, cy + 1, h=12)
down_arrow(rc, cy + 1, h=12)
cy += 14
box(L, cy, LW, 56, "Same output, checked the same way",
    [("Capture value = a farm's average selling price ÷ the market's average price. Both models are compared with observed 2023 prices before either is trusted, and they agree within 0.5 percentage points.", {})],
    line=BLUE, title_color=BLUE, size=15.5)

# ================================================================== RIGHT COLUMN
# 4 capture value over the years
Y = 136
heading(4, R, Y, RW, "Capture value falls in both seas, and the Baltic falls furthest unless the grid is expanded", lines=2)
picture("fig_p_arc.png", R, Y + 32, RW, 100)
tiles = [
    ([("0.88", {"color": NAVY}), (" = ", {"color": MUTED, "size": 22}), ("0.88", {"color": NAVY})],
     "Today: both seas capture the same share of the market price."),
    ([("0.47", {"color": ORANGE}), (" vs ", {"color": MUTED, "size": 22}), ("0.57", {"color": NAVY})],
     "2040 with today's grid: Baltic against North Sea."),
    ([("0.66", {"color": GREEN})],
     "2040 with the grid expanded: the Baltic is level with the North Sea again."),
]
for i, (big, body) in enumerate(tiles):
    tx = R + i * 93
    rect(tx, Y + 136, 84, 32, fill=TILE)
    text(tx + 3, Y + 137, 78, 14, [big], size=34, bold=True, spacing=0.95)
    text(tx + 3, Y + 151, 78, 16, [body], size=11.5, color=INK, spacing=1.03)

# 5 which model for what (small table)
Y = 312
heading(5, R, Y, RW, "Regression is better for the short term, the power‑system model for the long term", lines=2)
cols = [(R, 88), (R + 88, 91), (R + 179, 91)]
ty = Y + 32
cell(cols[0][0], ty, cols[0][1], 11, [""], fill=NAVY)
cell(cols[1][0], ty, cols[1][1], 11, ["Statistical model"], size=13, bold=True, color=WHITE, fill=NAVY, align=PP_ALIGN.CENTER)
cell(cols[2][0], ty, cols[2][1], 11, ["Power‑system model"], size=13, bold=True, color=WHITE, fill=NAVY, align=PP_ALIGN.CENTER)
rows = [
    ("Today and the near term", ("better: error 0.01 on the record", True), ("error 0.05, growing with congestion", False)),
    ("2030 and 2040", ("same answer whichever future it is shown", False), ("better: responds to the buildout and the grid", True)),
    ("Congestion, or a different grid", ("cannot represent them", False), ("better: a price at every grid node", True)),
    ("Negative prices, the most cannibalised zone", ("better: learned from the record", True), ("cannot produce them", False)),
]
rh = 12.25
for i, (lab, sm, pm) in enumerate(rows):
    ry = ty + 11 + i * rh
    cell(cols[0][0], ry, cols[0][1], rh, [lab], size=13, bold=True, color=NAVY, fill=TILE)
    for (cx, cw), (txt, win), col, tint in [(cols[1], sm, NAVY, NAVY_T), (cols[2], pm, GREEN, GREEN_T)]:
        cell(cx, ry, cw, rh, [txt], size=13, bold=win, color=col if win else INK, fill=tint if win else WHITE)

# 6 where the loss comes from
Y = 412
heading(6, R, Y, RW, "Half of the Baltic's extra loss is grid congestion")
picture("fig_p_decomposition.png", R, Y + 18, RW, 52)
text(R, Y + 72, RW, 10,
     ["Congestion: Baltic 0.19 against North Sea 0.06. The buildout itself: 0.22 against 0.25."],
     size=13, color=MUTED, spacing=1.0)

# 7 in money
Y = 502
heading(7, R, Y, RW, "In money: the grid makes Baltic sites bankable")
picture("fig_p_maps.png", R, Y + 18, RW, 172)
ny = Y + 194
for i, (big, body) in enumerate([
        ([("87", {"color": ORANGE}), (" to ", {"color": MUTED, "size": 15}), ("121", {"color": ORANGE})],
         f"EUR/MWh: Baltic break{NBH}even price (cost ÷ capture value), 2025 to 2040 with today's grid."),
        ([("−33", {"color": GREEN})], "EUR/MWh with the grid expanded. Polish and Danish waters fall below 70.")]):
    tx = R + i * 139
    rect(tx, ny, 131, 24, fill=TILE)
    text(tx + 3, ny + 1, 52, 22, [big], size=27, bold=True, anchor=MSO_ANCHOR.MIDDLE, spacing=0.95)
    text(tx + 57, ny + 1.5, 72, 21, [body], size=11, color=INK, anchor=MSO_ANCHOR.MIDDLE, spacing=1.02)

# conclusions
Y = 726
rect(R, Y, RW, 64, fill=NAVY)
text(R + 6, Y + 3, RW - 12, 10, ["What this means"], size=22, bold=True, color=WHITE)
text(R + 6, Y + 14, RW - 38, 40,
     ["The planned Baltic wind farms are worth what the grid built alongside them allows.",
      "Half of the Baltic's loss is a design choice: transmission removes it.",
      "Even with an expanded grid the Baltic captures a quarter less than today, a loss that belongs in auction and PPA pricing."],
     size=13, color=WHITE, spacing=1.04, after=2.5, numbered=True)
text(R + 6, Y + 54, RW - 38, 8,
     ["Full thesis and model: scan the code. Open data throughout: ENTSO‑E, PyPSA‑Eur, TYNDP."],
     size=10.5, color=PALE, spacing=1.0, anchor=MSO_ANCHOR.BOTTOM)
qr = rect(R + RW - 26, Y + 40, 20, 20, line=PALE, line_w=1.0, dash=True)
tf = qr.text_frame
tf.vertical_anchor = MSO_ANCHOR.MIDDLE
tf.margin_left = tf.margin_right = 0
p = tf.paragraphs[0]
p.alignment = PP_ALIGN.CENTER
_run(p, "QR", 10, False, PALE)

prs.save(OUT)
print("saved", OUT)
