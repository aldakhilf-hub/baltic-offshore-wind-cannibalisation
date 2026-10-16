"""Build the A1 poster, version 6, on the Imperial 'new brand' template.

Plain headings (no chips, no stat tiles), all poster text Arial 24 pt or
larger except the reference list. Two figures: an annotated capture-value
chart 2017 to 2040 and the break-even maps. A rounded-box flow chart for the
method, a three-row table, explicit answers to the three questions under
Conclusions, and an 'Ask me about' panel as a conversation starter.
Units are millimetres on the 594 x 841 mm sheet.
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
INK, MUTED, WHITE, GREY, LAV = "1F1F1F", "5B6170", "FFFFFF", "C9CED8", "E6E6FA"
NAVY_T, GREEN_T = "E4E6F4", "E3EFE3"
FONT = "Arial"
NBH = "‑"
BODY = 24

HERO = json.load(open(FIGS / "hero_values.json"))
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


def text(x, y, w, h, paras, size=BODY, bold=False, color=INK, align=PP_ALIGN.LEFT,
         anchor=MSO_ANCHOR.TOP, spacing=1.08, after=0, pad=0, numbered=False, skip_first=False):
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
            pPr.set("marL", str(mm(11)))
            pPr.set("indent", str(-mm(11)))
            bu = etree.SubElement(pPr, qn("a:buAutoNum"))
            bu.set("type", "arabicPeriod")
        runs = [(para, {})] if isinstance(para, str) else para
        for t, o in runs:
            _run(p, t, o.get("size", size), o.get("bold", bold), o.get("color", color), o.get("italic", False))
    return tb


def shape(kind, x, y, w, h, fill=None, line=None, line_w=0.75):
    shp = slide.shapes.add_shape(kind, mm(x), mm(y), mm(w), mm(h))
    shp.shadow.inherit = False
    if fill:
        shp.fill.solid()
        shp.fill.fore_color.rgb = rgb(fill)
    else:
        shp.fill.background()
    if line:
        shp.line.color.rgb = rgb(line)
        shp.line.width = Pt(line_w)
    else:
        shp.line.fill.background()
    shp.text_frame.text = ""
    return shp


def rbox(x, y, w, h, paras, fill=LAV, color=NAVY, size=BODY, bold=False, line=None):
    shp = shape(MSO_SHAPE.ROUNDED_RECTANGLE, x, y, w, h, fill=fill, line=line, line_w=1.5)
    shp.adjustments[0] = 0.18
    text(x + 4, y + 2, w - 8, h - 4, paras, size=size, color=color, bold=bold,
         anchor=MSO_ANCHOR.MIDDLE, align=PP_ALIGN.CENTER, spacing=1.05)
    return shp


def arrow_down(xc, y, h=11, w=9, color=BLUE):
    return shape(MSO_SHAPE.DOWN_ARROW, xc - w / 2, y, w, h, fill=color)


def picture(name, x, y, w, h):
    return slide.shapes.add_picture(str(FIGS / name), mm(x), mm(y), mm(w), mm(h))


def heading(x, y, w, txt):
    text(x, y, w, 18, [txt], size=44, bold=True, color=BLUE, spacing=1.0)


def caption(x, y, w, h, label, body):
    text(x, y, w, h, [[(label + " ", {"bold": True, "color": INK}), (body, {})]], size=BODY, color=MUTED, spacing=1.06)


def para(x, y, w, h, runs, size=BODY):
    text(x, y, w, h, [runs] if isinstance(runs, list) else [runs], size=size, color=INK, spacing=1.08)


def cell(x, y, w, h, txt, bold=False, color=INK, fill=WHITE, align=PP_ALIGN.LEFT, size=BODY):
    shape(MSO_SHAPE.RECTANGLE, x, y, w, h, fill=fill, line=GREY, line_w=0.6)
    text(x + 3, y + 1, w - 6, h - 2, [txt], size=size, bold=bold, color=color,
         anchor=MSO_ANCHOR.MIDDLE, align=align, spacing=1.0)


# ------------------------------------------------------------------ header
text(22, 57, 44, 62, ["00"], size=96, bold=True, color=BLUE, spacing=0.9)
text(68, 58, 318, 64,
     [[("Offshore wind cannibalisation in the Baltic and North Sea: ", {"bold": True, "color": NAVY}),
       ("how much value is lost depends on the grid built alongside the farms", {"bold": False, "color": BLUE})]],
     size=37, spacing=1.0)
text(393, 60, 179, 60,
     [[("Faisal Bindakhil", {"bold": True, "color": NAVY, "size": 28})],
      "MSc Sustainable Energy Futures",
      "Imperial College London",
      "Supervisor: Dr Ruslan Galimov, RWE"],
     size=24, color=INK, spacing=1.04, after=1)

# ================================================================== LEFT COLUMN
Y = 136
heading(L, Y, LW, "Background")
para(L, Y + 22, LW, 92,
     [("Europe's next wave of offshore wind moves from the mature North Sea into the enclosed Baltic Sea. "
       "Wind farms in one sea generate in the same hours, so when they all produce the price falls. "
       "The share of the average market price a farm actually receives is its ", {}),
      ("capture value", {"bold": True}),
      (" [1], and it falls as more wind is built. The Baltic fleet grows nineteenfold by 2040, the North Sea's ninefold, "
       "and the Baltic grid is weakly connected to its neighbours.", {})])

Y = 242
heading(L, Y, LW, "Objective")
text(L, Y + 22, LW, 88,
     [[("Measure how much value offshore wind loses as the planned fleets are built, and answer:", {"bold": True, "color": NAVY})],
      "How do the two seas compare, today and once the planned farms are built?",
      "What causes the loss of value, and how much of it can the grid avoid?",
      "Can a model trained on the past project this future, or must the market be rebuilt?"],
     size=BODY, color=INK, spacing=1.08, after=2, numbered=True, skip_first=True)

Y = 358
heading(L, Y, LW, "Methodology")
para(L, Y + 22, LW, 70,
     [("Two models estimate capture value from different inputs. The ", {}),
      ("statistical model", {"bold": True, "color": NAVY}),
      (" is a regression fitted to eight years of prices at 31 farms [5], with wind output from ERA5 weather [2]. The ", {}),
      ("power‑system model", {"bold": True, "color": GREEN}),
      (", PyPSA‑Eur [3], rebuilds every hour's price from Europe's plants, grid and demand under the 2030 and 2040 plans [4]. "
       "Both are checked against 2023 prices.", {})])
cy = Y + 98
LX, RX, BW = L, L + 140, 128
lc, rc = LX + BW / 2, RX + BW / 2
rbox(L, cy, LW, 26, ["ERA5 weather, turned into the hourly output of every wind farm [2]"])
cy += 26
arrow_down(lc, cy + 1)
arrow_down(rc, cy + 1)
cy += 13
rbox(LX, cy, BW, 36, ["Observed prices, 2017 to 2024 [5]"])
rbox(RX, cy, BW, 36, ["Plants, grid and demand, with the 2030 and 2040 plans [3, 4]"])
cy += 36
arrow_down(lc, cy + 1, color=NAVY)
arrow_down(rc, cy + 1, color=GREEN)
cy += 13
rbox(LX, cy, BW, 26, ["Statistical model"], fill=NAVY, color=WHITE, bold=True)
rbox(RX, cy, BW, 26, ["Power‑system model"], fill=GREEN, color=WHITE, bold=True)
cy += 26
arrow_down(lc, cy + 1, color=NAVY)
arrow_down(rc, cy + 1, color=GREEN)
cy += 13
rbox(L, cy, LW, 38, ["Capture value = a farm's average price ÷ the market's average price. Both models agree on 2023 within 0.5 points."],
     fill=WHITE, line=BLUE, color=INK)
cy += 40
caption(L, cy, LW, 22, "Figure 1:", "The two models, their inputs and their common output.")

Y = 660
shp = shape(MSO_SHAPE.ROUNDED_RECTANGLE, L, Y, LW, 60, fill=LAV)
shp.adjustments[0] = 0.12
text(L + 6, Y + 3, LW - 12, 54,
     [[("Ask me about ", {"bold": True, "color": NAVY}),
       ("why Denmark's DK2 zone breaks the power‑system model, who pays for the grid that removes the congestion, "
        "and whether a Baltic farm should sell its power forward.", {})]],
     size=BODY, color=INK, anchor=MSO_ANCHOR.MIDDLE, spacing=1.08)

Y = 728
text(L, Y, LW, 10, ["References"], size=24, bold=True, color=BLUE)
refs = [
    "[1] L. Hirth. The market value of variable renewables. Energy Economics, 38:218–236, 2013.",
    "[2] L. Hayes, M. Stocks and A. Blakers. Accurate long‑term power generation model for offshore wind farms in Europe using ERA5 reanalysis. Energy, 229:120603, 2021.",
    "[3] J. Hörsch, F. Hofmann, D. Schlachtberger and T. Brown. PyPSA‑Eur: an open optimisation model of the European transmission system. Energy Strategy Reviews, 22:207–215, 2018.",
    "[4] ENTSO‑E and ENTSOG. TYNDP 2024 Scenarios Report, final version, January 2025.",
    "[5] ENTSO‑E Transparency Platform. Day‑ahead prices and generation data, 2017 to 2024.",
]
text(L, Y + 11, LW, 790 - (Y + 11), refs, size=12.5, color=INK, spacing=1.02, after=0.5)

# ================================================================== RIGHT COLUMN
Y = 136
heading(R, Y, RW, "Results")
picture("fig_p_hero.png", R, Y + 22, RW, 120)
caption(R, Y + 144, RW, 22, "Figure 2:",
        "Capture value observed to 2024 and projected to 2040, with the grid as today and with transmission expanded.")
para(R, Y + 169, RW, 52,
     [("Both seas are level today. With the planned buildout and today's grid the Baltic falls to 0.47 by 2040 and the North Sea to 0.57. "
       "Expanding the grid lifts the Baltic to 0.66: half of its extra loss is congestion that transmission removes.", {})])

Y = 362
cols = [(R, 68), (R + 68, 101), (R + 169, 101)]
rh = 17
cell(cols[0][0], Y, cols[0][1], rh, "", fill=NAVY)
cell(cols[1][0], Y, cols[1][1], rh, "Statistical model", bold=True, color=WHITE, fill=NAVY, align=PP_ALIGN.CENTER)
cell(cols[2][0], Y, cols[2][1], rh, "Power‑system model", bold=True, color=WHITE, fill=NAVY, align=PP_ALIGN.CENTER)
rows = [
    ("Today's prices", ("closer, error 0.01", True), ("error 0.05", False)),
    ("Any future", ("one answer for all", False), ("responds to the grid", True)),
    ("Congestion", ("an input only", False), ("priced at every node", True)),
]
for i, (lab, sm, pm) in enumerate(rows):
    ry = Y + rh + i * rh
    cell(cols[0][0], ry, cols[0][1], rh, lab, bold=True, color=NAVY, fill=LAV)
    for (cx, cw), (txt, win), col, tint in [(cols[1], sm, NAVY, NAVY_T), (cols[2], pm, GREEN, GREEN_T)]:
        cell(cx, ry, cw, rh, txt, bold=win, color=col if win else INK, fill=tint if win else WHITE)
caption(R, Y + 4 * rh + 3, RW, 22, "Table 1:",
        "The regression is better for today, the power‑system model for the long term, so the 2040 numbers come from it.")

Y = 460
picture("fig_p_maps.png", R, Y, RW, 150)
caption(R, Y + 152, RW, 22, "Figure 3:",
        "Break‑even price of a new farm in 2040, cost ÷ capture value. Below 70 EUR/MWh a farm pays back.")
para(R, Y + 177, RW, 32,
     [("With today's grid the Baltic break‑even price rises from 87 to 121 EUR/MWh by 2040. "
       "Expanding the grid lowers it by 33, and Polish and Danish waters pay back.", {})])

Y = 676
heading(R, Y, RW, "Conclusions")
text(R, Y + 22, RW, 790 - (Y + 22),
     ["Today the seas are equal at 0.88. Once the planned farms are built, with today's grid, the Baltic falls to 0.47 and the North Sea to 0.57.",
      "The buildout costs both seas about the same. The Baltic's extra loss is grid congestion, and transmission removes it: the Baltic recovers to 0.66.",
      "The market must be rebuilt: the model trained on the past gives one answer for every future, so the 2040 numbers come from the power‑system model."],
     size=BODY, color=INK, spacing=1.06, after=3, numbered=True)

prs.save(OUT)
print("saved", OUT)
