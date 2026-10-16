"""Build the A1 poster on the Imperial 'new brand' template.

Units are millimetres on the 594 x 841 mm sheet. The master supplies the
IMPERIAL wordmark, the rules and the 'Imperial College London' footer; this
script adds every other element as explicit shapes so nothing depends on a
font the printing machine may lack (all text is Arial).
"""
import copy
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

# Imperial theme colours
BLUE, NAVY, ORANGE, GREEN = "0000CD", "000080", "FF4500", "006400"
INK, MUTED, TILE, WHITE, GREY = "1F1F1F", "5B6170", "F5F5F5", "FFFFFF", "C9CED8"
FONT = "Arial"
import json
OV = json.load(open(FIGS / "observed_values.json"))
CAP_OBS = (" is the share of the average market price a farm actually receives. Both seas slide: "
           f"North Sea {OV['North Sea'][0]:.2f} to {OV['North Sea'][1]:.2f}, Baltic {OV['Baltic'][0]:.2f} to {OV['Baltic'][1]:.2f} "
           "(24‑month means, 2017 to 2024).")


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
# footer 'imperial.ac.uk' (a footer placeholder only renders when the slide carries one)
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


def text(x, y, w, h, paras, size=20, bold=False, color=INK, align=PP_ALIGN.LEFT,
         anchor=MSO_ANCHOR.TOP, spacing=1.05, after=0, pad=0, numbered=False):
    """paras: list of paragraphs; a paragraph is a str or a list of
    (text, {size, bold, color}) run tuples."""
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
        if numbered:
            pPr = p._p.get_or_add_pPr()
            pPr.set("marL", str(mm(8)))
            pPr.set("indent", str(-mm(8)))
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
            shp.line.dash_style = 4  # dash
    else:
        shp.line.fill.background()
    shp.text_frame.text = ""
    return shp


def picture(name, x, y, w, h):
    return slide.shapes.add_picture(str(FIGS / name), mm(x), mm(y), mm(w), mm(h))


def heading(n, y, txt, lines=1):
    chip = rect(22, y + 0.5, 12.5, 12.5, fill=BLUE)
    tf = chip.text_frame
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    _run(p, str(n), 22, True, WHITE)
    text(39, y - 1.5, 533, 14 * lines + 2, [txt], size=30, bold=True, color=BLUE, spacing=1.0)


def arrow(x, y, w=10, h=8):
    shp = slide.shapes.add_shape(MSO_SHAPE.RIGHT_ARROW, mm(x), mm(y), mm(w), mm(h))
    shp.shadow.inherit = False
    shp.fill.solid()
    shp.fill.fore_color.rgb = rgb(BLUE)
    shp.line.fill.background()
    return shp


def lane_box(x, y, w, h, title, body):
    rect(x, y, w, h, fill=TILE)
    text(x + 2.5, y + 1.5, w - 5, h - 3,
         [[(title, {"bold": True, "color": NAVY, "size": 17})], body],
         size=15, color=INK, anchor=MSO_ANCHOR.MIDDLE, spacing=1.0)


# ------------------------------------------------------------------ header
text(22, 57, 44, 62, ["00"], size=96, bold=True, color=BLUE, spacing=0.9)
text(68, 58, 318, 64,
     [[("Offshore wind cannibalisation in the Baltic and North Sea: ", {"bold": True, "color": NAVY}),
       ("how much value is lost depends on the grid built alongside the farms", {"bold": False, "color": BLUE})]],
     size=37, spacing=1.0)
text(393, 60, 179, 60,
     [[("Faisal Bindakhil", {"bold": True, "color": NAVY, "size": 26})],
      "MSc Sustainable Energy Futures, Imperial College London",
      "Supervisor: Prof Adam Hawkes",
      "Project partner: Dr Ruslan Galimov, RWE"],
     size=17, color=INK, spacing=1.05, after=2)

# ------------------------------------------------------------------ band 1
Y = 136
heading(1, Y, "Wind farms in one sea generate together, and cut the price they all sell at")
picture("fig_p_mechanism.png", 22, Y + 18, 168, 60)
text(22, Y + 80, 168, 22,
     ["Farms in a region produce in the same hours, so supply peaks together and the price every farm receives falls."],
     size=16, color=MUTED, spacing=1.05)
picture("fig_p_observed.png", 200, Y + 18, 195, 60)
text(200, Y + 80, 195, 22,
     [[("Capture value", {"bold": True, "color": INK}),
       (CAP_OBS, {})]],
     size=16, color=MUTED, spacing=1.05)
for i, (big, col, body) in enumerate([
        ("×9", NAVY, [("North Sea", {"bold": True, "color": NAVY}),
                      (": 18.5 GW today to 165 GW by 2040. Mature, open sea with many neighbours.", {})]),
        ("×19", ORANGE, [("Baltic", {"bold": True, "color": ORANGE}),
                         (": 2.6 GW to 50 GW. Enclosed sea, weakly interconnected. The question is whether it loses value the way the North Sea did.", {})])]):
    ty = Y + 18 + i * 44
    rect(405, ty, 167, 40, fill=TILE)
    text(409, ty + 1, 44, 38, [big], size=44, bold=True, color=col, anchor=MSO_ANCHOR.MIDDLE)
    text(455, ty + 2, 114, 36, [body], size=16, color=INK, anchor=MSO_ANCHOR.MIDDLE, spacing=1.05)

# ------------------------------------------------------------------ band 2 (hero)
Y = 244
heading(2, Y, "Today the two seas are equal. By 2040 the Baltic loses almost half its value, unless the grid is expanded")
picture("fig_p_arc.png", 22, Y + 18, 350, 162)
tiles = [
    ([("0.88", {"color": NAVY}), (" = ", {"color": MUTED, "size": 34}), ("0.88", {"color": NAVY})],
     [("Today. ", {"bold": True, "color": NAVY}),
      ("Both seas capture the same share of the market price. No Baltic penalty yet.", {})]),
    ([("0.47", {"color": ORANGE}), (" vs ", {"color": MUTED, "size": 34}), ("0.57", {"color": NAVY})],
     [("2040, today's grid. ", {"bold": True, "color": NAVY}),
      ("Baltic against North Sea: the Baltic loses almost half its present value.", {})]),
    ([("0.66", {"color": GREEN})],
     [("2040, grid expanded. ", {"bold": True, "color": NAVY}),
      ("The Baltic recovers and is level with the North Sea again.", {})]),
]
for i, (big, body) in enumerate(tiles):
    ty = Y + 18 + i * 56
    rect(382, ty, 190, 50, fill=TILE)
    text(386, ty + 1, 182, 24, [big], size=60, bold=True, spacing=0.95)
    text(386, ty + 26, 182, 22, [body], size=16, color=INK, spacing=1.05)

# ------------------------------------------------------------------ band 3
Y = 430
heading(3, Y, "Half of the Baltic's extra loss is grid congestion, which transmission removes")
picture("fig_p_decomposition.png", 22, Y + 18, 350, 87)
text(382, Y + 20, 190, 85,
     ["The Baltic loses 0.19 to congestion, three times the North Sea's 0.06. The loss from the buildout itself is no larger in the Baltic (0.22) than in the North Sea (0.25).",
      "Removing congestion takes the Baltic from 0.47 to 0.66, level with the North Sea."],
     size=18, color=INK, spacing=1.08, after=6)

# ------------------------------------------------------------------ band 4
Y = 541
heading(4, Y, "In money: with today's grid most of the Baltic does not pay back, and an expanded grid lowers its break‑even price by 33 EUR/MWh", lines=2)
picture("fig_p_maps.png", 22, Y + 32, 470, 110)
cx = 498
text(cx, Y + 32, 74, 16, [[("87 ", {"color": ORANGE}), ("to", {"color": MUTED, "size": 22}), (" 121", {"color": ORANGE})]],
     size=36, bold=True, spacing=0.95)
text(cx, Y + 48, 74, 26,
     ["EUR/MWh: Baltic break-even price, 2025 to 2040, today's grid. Cost falls, value falls faster."],
     size=14, color=INK, spacing=1.05)
text(cx, Y + 76, 74, 16, [[("−33", {"color": GREEN})]], size=36, bold=True, spacing=0.95)
text(cx, Y + 92, 74, 22,
     ["EUR/MWh with the grid expanded. Polish and Danish waters fall below 70."],
     size=14, color=INK, spacing=1.05)
text(cx, Y + 116, 74, 26,
     [[("Break‑even price", {"bold": True, "color": INK}),
       (" = cost of energy ÷ capture value: the market price a farm needs to pay itself back.", {})]],
     size=14, color=MUTED, spacing=1.05)

# ------------------------------------------------------------------ band 5
Y = 689
heading(5, Y, "How the numbers were made: two models, both checked")
ly = Y + 18
lane_box(22, ly, 104, 26, "Observed record", "hourly prices at 31 farms, 2017 to 2024")
arrow(128, ly + 9)
lane_box(140, ly, 122, 26, "Statistical model", "panel regression, R² 0.80 out of sample")
arrow(264, ly + 9)
lane_box(276, ly, 96, 26, "Today", "observed baseline, both seas")
ly = Y + 49
lane_box(22, ly, 104, 26, "2030 and 2040 scenarios", "official ENTSO-E expansion plans")
arrow(128, ly + 9)
lane_box(140, ly, 122, 26, "Power-system model", "PyPSA-Eur rebuilds prices from plants, grid and demand, hour by hour")
arrow(264, ly + 9)
lane_box(276, ly, 96, 26, "2040, run twice", "today's grid, and expanded at least cost")
rect(22, Y + 80, 350, 21, line=BLUE, line_w=1.5)
text(25, Y + 81, 344, 19,
     [[("Cross-checked on 2023: ", {"bold": True, "color": BLUE}),
       ("the two models agree within 0.5 percentage points. Beyond the observed record the statistical model gives almost the same answer whichever future it is shown, so the 2040 projection comes from the power-system model.", {})]],
     size=15, color=INK, anchor=MSO_ANCHOR.MIDDLE, spacing=1.03)

# conclusions box
rect(382, Y, 190, 101, fill=NAVY)
text(388, Y + 4, 178, 12, ["What this means"], size=24, bold=True, color=WHITE)
text(388, Y + 17, 178, 58,
     ["The planned Baltic wind farms are worth what the grid built alongside them allows.",
      "Half of the Baltic's loss is a design choice: transmission removes it.",
      "Even with an expanded grid the Baltic captures a quarter less than today. That remaining loss belongs in auction and PPA pricing."],
     size=15.5, color=WHITE, spacing=1.05, after=4, numbered=True)
text(388, Y + 78, 120, 20,
     ["Full thesis and model: scan the code.", "Open data throughout: ENTSO-E, PyPSA-Eur, TYNDP."],
     size=12.5, color="C9CFF7", spacing=1.05, anchor=MSO_ANCHOR.BOTTOM)
qr = rect(544, Y + 75, 22, 22, line="C9CFF7", line_w=1.0, dash=True)
tf = qr.text_frame
tf.vertical_anchor = MSO_ANCHOR.MIDDLE
tf.margin_left = tf.margin_right = 0
p = tf.paragraphs[0]
p.alignment = PP_ALIGN.CENTER
_run(p, "QR", 12, False, "C9CFF7")

prs.save(OUT)
print("saved", OUT)
