"""Build the A1 poster, two-column version, on the Imperial 'new brand' template.

Left column: background, objective, method (the two models compared).
Right column: results (capture value over the years, where the loss comes
from, the money maps) and conclusions. Units are millimetres on the 594 x 841
mm sheet; all text is Arial.
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


def rect(x, y, w, h, fill=None, line=None, line_w=0.75, dash=False):
    shp = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, mm(x), mm(y), mm(w), mm(h))
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


def cell(x, y, w, h, paras, size=14.5, bold=False, color=INK, fill=None, align=PP_ALIGN.LEFT):
    if fill:
        rect(x, y, w, h, fill=fill)
    text(x + 2.2, y + 1, w - 4.4, h - 2, paras, size=size, bold=bold, color=color,
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
picture("fig_p_mechanism.png", L, Y + 18, LW, 50)
text(L, Y + 70, LW, 13,
     ["Wind farms in one sea produce in the same hours, so supply peaks together and the price every farm receives falls."],
     size=15, color=MUTED, spacing=1.03)
picture("fig_p_observed.png", L, Y + 86, LW, 66)
text(L, Y + 154, LW, 17,
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
    rect(tx, Y + 174, 130, 34, fill=TILE)
    text(tx + 3, Y + 175, 36, 32, [big], size=38, bold=True, color=col, anchor=MSO_ANCHOR.MIDDLE)
    text(tx + 41, Y + 176, 87, 30, [body], size=13.5, color=INK, anchor=MSO_ANCHOR.MIDDLE, spacing=1.03)

# 2 Objective
Y = 352
heading(2, L, Y, LW, "Objective")
text(L, Y + 18, LW, 52,
     [[("Measure how much of its value offshore wind loses as the planned fleets are built, and answer three questions:", {"bold": True, "color": NAVY})],
      "How do the two seas compare today, and how will they compare once the planned farms are built?",
      "What causes the loss of value, and how much of it can be avoided by building the grid differently?",
      "Can a model trained on the past project this future, or must the market be rebuilt from its parts?"],
     size=16, color=INK, spacing=1.05, after=2, numbered=True, skip_first=True)

# 3 Method: two models compared
Y = 426
heading(3, L, Y, LW, "Method: two models, compared")
text(L, Y + 18, LW, 16,
     ["A statistical model trained on eight years of observed prices, and a power‑system model (PyPSA‑Eur) that rebuilds every hour's price from plants, grid and demand. Each task goes to the model that does it better."],
     size=15, color=INK, spacing=1.03)
cols = [(L, 70), (L + 70, 80), (L + 150, 80), (L + 230, 38)]
ty = Y + 36
hdr = ["Task", "Statistical model", "Power‑system model", "Better model"]
for (cx, cw), h in zip(cols, hdr):
    cell(cx, ty, cw, 13, [h], size=15, bold=True, color=WHITE, fill=NAVY)
rows = [
    ("Reproduce capture value observed 2017 to 2024", "average error 0.01", "average error 0.05, growing with congestion", "Statistical"),
    ("The most cannibalised zone: DK2 in 2023, observed 0.78", "0.80", "0.93", "Statistical"),
    ("Hours with prices below zero", "learned from the record", "none, since prices are built from costs", "Statistical"),
    ("Congestion and flows between countries", "only as an input variable", "a price at every grid node", "System"),
    ("Renewable shares beyond the record (four 2040 scenarios)", "answers span 0.008", "answers span 0.43 and follow the buildout", "System"),
    ("A different grid, gas price or flexibility", "nothing inside it to change", "solved again with the change", "System"),
]
rh = 41
for i, (task, sm, pm, win) in enumerate(rows):
    ry = ty + 13 + i * rh
    fill = TILE if i % 2 == 0 else WHITE
    cell(cols[0][0], ry, cols[0][1], rh, [task], size=15.5, bold=True, color=NAVY, fill=fill)
    cell(cols[1][0], ry, cols[1][1], rh, [sm], size=16, fill=fill)
    cell(cols[2][0], ry, cols[2][1], rh, [pm], size=16, fill=fill)
    cell(cols[3][0], ry, cols[3][1], rh, [win], size=15, bold=True,
         color=NAVY if win == "Statistical" else GREEN, fill=fill, align=PP_ALIGN.CENTER)
rect(L, ty, LW, 13 + rh * len(rows), line=GREY, line_w=0.75)
vy = ty + 13 + rh * len(rows) + 6
rect(L, vy, LW, 790 - vy, line=BLUE, line_w=1.5)
text(L + 4, vy + 2, LW - 8, 790 - vy - 4,
     [[("Verdict: the statistical model for today and the near term, the power‑system model for 2030 and 2040. ", {"bold": True, "color": BLUE}),
       ("The statistical model learns from prices that have already occurred, so it is closer on the record but gives almost the same answer whichever future it is shown. "
        "The power‑system model rebuilds each hour's price from the fleet, the grid and demand, so it responds to a scenario that has never occurred. "
        "On 2023 the two agree within 0.5 percentage points.", {})]],
     size=15.5, color=INK, anchor=MSO_ANCHOR.MIDDLE, spacing=1.04)

# ================================================================== RIGHT COLUMN
# 4 Results: capture value over the years
Y = 136
heading(4, R, Y, RW, "Capture value falls in both seas, and the Baltic falls furthest unless the grid is expanded", lines=2)
picture("fig_p_arc.png", R, Y + 32, RW, 130)
tiles = [
    ([("0.88", {"color": NAVY}), (" = ", {"color": MUTED, "size": 24}), ("0.88", {"color": NAVY})],
     "Today: both seas capture the same share of the market price."),
    ([("0.47", {"color": ORANGE}), (" vs ", {"color": MUTED, "size": 24}), ("0.57", {"color": NAVY})],
     "2040 with today's grid: Baltic against North Sea."),
    ([("0.66", {"color": GREEN})],
     "2040 with the grid expanded: the Baltic is level with the North Sea again."),
]
for i, (big, body) in enumerate(tiles):
    tx = R + i * 93
    rect(tx, Y + 166, 84, 40, fill=TILE)
    text(tx + 3, Y + 167, 78, 16, [big], size=38, bold=True, spacing=0.95)
    text(tx + 3, Y + 184, 78, 21, [body], size=12, color=INK, spacing=1.03)

# 5 Where the loss comes from
Y = 350
heading(5, R, Y, RW, "Half of the Baltic's extra loss is grid congestion")
picture("fig_p_decomposition.png", R, Y + 18, RW, 62)
text(R, Y + 82, RW, 18,
     ["The Baltic loses 0.19 to congestion, three times the North Sea's 0.06, while its loss from the buildout itself (0.22) is no larger than the North Sea's (0.25)."],
     size=14, color=MUTED, spacing=1.03)

# 6 In money
Y = 454
heading(6, R, Y, RW, "In money: an expanded grid makes Baltic sites bankable", lines=2)
picture("fig_p_maps.png", R, Y + 32, RW, 190)
ny = Y + 226
for i, (big, col, body) in enumerate([
        ([("87", {"color": ORANGE}), (" to ", {"color": MUTED, "size": 16}), ("121", {"color": ORANGE})],
         ORANGE, f"EUR/MWh: Baltic break{NBH}even price (cost ÷ capture value), 2025 to 2040 with today's grid."),
        ([("−33", {"color": GREEN})], GREEN, "EUR/MWh with the grid expanded. Polish and Danish waters fall below 70.")]):
    tx = R + i * 139
    rect(tx, ny, 131, 26, fill=TILE)
    text(tx + 3, ny + 1, 54, 24, [big], size=28, bold=True, anchor=MSO_ANCHOR.MIDDLE, spacing=0.95)
    text(tx + 58, ny + 2, 71, 22, [body], size=11.5, color=INK, anchor=MSO_ANCHOR.MIDDLE, spacing=1.03)

# conclusions
Y = 710
rect(R, Y, RW, 80, fill=NAVY)
text(R + 6, Y + 4, RW - 12, 11, ["What this means"], size=24, bold=True, color=WHITE)
text(R + 6, Y + 17, RW - 40, 48,
     ["The planned Baltic wind farms are worth what the grid built alongside them allows.",
      "Half of the Baltic's loss is a design choice: transmission removes it.",
      "Even with an expanded grid the Baltic captures a quarter less than today, a loss that belongs in auction and PPA pricing."],
     size=15, color=WHITE, spacing=1.05, after=4, numbered=True)
text(R + 6, Y + 66, RW - 40, 12,
     ["Full thesis and model: scan the code. Open data throughout: ENTSO‑E, PyPSA‑Eur, TYNDP."],
     size=11, color=PALE, spacing=1.03, anchor=MSO_ANCHOR.BOTTOM)
qr = rect(R + RW - 28, Y + 52, 22, 22, line=PALE, line_w=1.0, dash=True)
tf = qr.text_frame
tf.vertical_anchor = MSO_ANCHOR.MIDDLE
tf.margin_left = tf.margin_right = 0
p = tf.paragraphs[0]
p.alignment = PP_ALIGN.CENTER
_run(p, "QR", 11, False, PALE)

prs.save(OUT)
print("saved", OUT)
