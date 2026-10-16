"""Consulting-style 7-slide segment (Faisal Bindakhil).
1-3  Background as a Morph zoom: Europe -> North Sea -> Baltic (same picture, different crop)
4    Method   5 Results (1/2)   6-7 Results (2/2) + Conclusion (Morph on the vLCOE map)
"""
from pathlib import Path
import math, json
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.dml import MSO_LINE_DASH_STYLE
from lxml import etree

HERE = str(Path(__file__).resolve().parents[2] / "10_Presentation/group_deck_src") + "/"
FIG = str(Path(__file__).resolve().parents[2] / "9_Thesis_LaTeX/figures") + "/"
OUT = HERE + "Group_presentation_Faisal.pptx"

NAVY = RGBColor(0x00, 0x3E, 0x74)
LANE2 = RGBColor(0x4A, 0x7F, 0xB5)
INK = RGBColor(0x22, 0x22, 0x22)
GREY = RGBColor(0x6E, 0x6E, 0x6E)
HAIR = RGBColor(0xC8, 0xC8, 0xC8)
NSBLUE = RGBColor(0x2E, 0x6D, 0xA4)
BALRED = RGBColor(0xB0, 0x3A, 0x2E)
GREEN = RGBColor(0x2E, 0x8B, 0x57)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
SEA = RGBColor(0xE4, 0xEE, 0xF7)
MAPNAVY = RGBColor(0x1F, 0x3A, 0x5F)
MAPMID = RGBColor(0x4A, 0x7F, 0xB5)
FONT = "Calibri"
LIGHT = "Calibri Light"
N_SLIDES = 9
TRACK = ["Background", "Question", "Method", "Results", "Conclusion"]

prs = Presentation()
prs.slide_width = Inches(13.333)
prs.slide_height = Inches(7.5)
BLANK = prs.slide_layouts[6]


# ---------------- helpers ----------------
def run(p, s, size, color=INK, bold=False, italic=False, font=FONT):
    r = p.add_run()
    r.text = s
    f = r.font
    f.name, f.size, f.bold, f.italic = font, Pt(size), bold, italic
    f.color.rgb = color
    return r


def fill_text(tf, lines, size, color, bold=False, italic=False, align=PP_ALIGN.LEFT, space_after=0, font=FONT):
    tf.word_wrap = True
    for i, line in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        p.space_after = Pt(space_after)
        segs = line if isinstance(line, list) else [(line, {})]
        for seg, ov in segs:
            run(p, seg, ov.get("size", size), ov.get("color", color), ov.get("bold", bold),
                ov.get("italic", italic), ov.get("font", font))


def text(slide, x, y, w, h, s, size=14, color=INK, bold=False, italic=False, align=PP_ALIGN.LEFT,
         anchor=MSO_ANCHOR.TOP, name=None, space_after=0, font=FONT):
    box_ = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = box_.text_frame
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = anchor
    fill_text(tf, s if isinstance(s, list) else [s], size, color, bold, italic, align, space_after, font)
    if name:
        box_.name = name
    return box_


def shape(slide, kind, x, y, w, h, fill, line=None, lw=1.0, name=None, rot=0, adj=None, dash=None):
    sh = slide.shapes.add_shape(kind, Inches(x), Inches(y), Inches(w), Inches(h))
    if fill is None:
        sh.fill.background()
    else:
        sh.fill.solid()
        sh.fill.fore_color.rgb = fill
    if line is None:
        sh.line.fill.background()
    else:
        sh.line.color.rgb = line
        sh.line.width = Pt(lw)
        if dash:
            sh.line.dash_style = dash
    sh.shadow.inherit = False
    if rot:
        sh.rotation = rot
    if adj is not None:
        sh.adjustments[0] = adj
    sh.text_frame.text = ""
    if name:
        sh.name = name
    return sh


def rect(slide, x, y, w, h, fill, **kw):
    return shape(slide, MSO_SHAPE.RECTANGLE, x, y, w, h, fill, **kw)


def hline(slide, x1, y1, x2, y2, color=HAIR, width=0.75, dash=None, name=None, arrow_end=False):
    ln = slide.shapes.add_connector(1, Inches(x1), Inches(y1), Inches(x2), Inches(y2))
    ln.line.color.rgb = color
    ln.line.width = Pt(width)
    if dash:
        ln.line.dash_style = dash
    if arrow_end:
        ln_el = ln.line._get_or_add_ln()
        tail = etree.SubElement(ln_el, "{http://schemas.openxmlformats.org/drawingml/2006/main}tailEnd")
        tail.set("type", "triangle")
        tail.set("w", "med")
        tail.set("len", "med")
    if name:
        ln.name = name
    return ln


def picture(slide, path, x, y, w, name=None, border=True):
    p = slide.shapes.add_picture(path, Inches(x), Inches(y), Inches(w))
    if border:
        p.line.color.rgb = HAIR
        p.line.width = Pt(0.5)
    if name:
        p.name = name
    return p


def col_header(slide, x, y, w, s, name=None, color=GREY):
    text(slide, x, y, w, 0.3, s.upper(), size=11, bold=True, color=color, name=name)
    hline(slide, x, y + 0.33, x + w, y + 0.33, name=(name + "_rule") if name else None)


def ladder(slide, x, y, w, rows, num_size=26, row_h=1.05, name=None):
    for i, (numeral, desc, color) in enumerate(rows):
        ry = y + i * row_h
        nm = f"{name}_{i}" if name else None
        text(slide, x, ry, w, num_size / 72 * 1.3, numeral, size=num_size, color=color, font=LIGHT,
             name=(nm + "_n") if nm else None)
        text(slide, x, ry + num_size / 72 * 1.3 + 0.02, w, row_h - num_size / 72 * 1.3 - 0.12, desc,
             size=11.5, color=INK, name=(nm + "_d") if nm else None)
        if i < len(rows) - 1:
            hline(slide, x, ry + row_h - 0.08, x + w, ry + row_h - 0.08, name=(nm + "_r") if nm else None)


def sparkline(slide, x, y, w, h, values, color, lo=None, hi=None, name=None):
    lo = min(values) if lo is None else lo
    hi = max(values) if hi is None else hi
    n = len(values)
    pts = [(x + w * i / (n - 1), y + h - h * (v - lo) / (hi - lo)) for i, v in enumerate(values)]
    for (ax, ay), (bx, by) in zip(pts, pts[1:]):
        hline(slide, ax, ay, bx, by, color=color, width=1.75, name=name)
    ex, ey = pts[-1]
    shape(slide, MSO_SHAPE.OVAL, ex - 0.05, ey - 0.05, 0.1, 0.1, color, name=name)


def turbine(slide, cx, base_y, s, color=NAVY, offset=0):
    hy = base_y - s
    tw = 0.075 * s
    rect(slide, cx - tw / 2, hy, tw, s, color)
    L, t = 0.62 * s, 0.085 * s
    for a in (-90 + offset, 30 + offset, 150 + offset):
        rad = math.radians(a)
        bx, by = cx + (L / 2) * math.cos(rad), hy + (L / 2) * math.sin(rad)
        shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, bx - L / 2, by - t / 2, L, t, color, rot=a, adj=0.5)
    d = 0.16 * s
    shape(slide, MSO_SHAPE.OVAL, cx - d / 2, hy - d / 2, d, d, color)


def frame(slide, n, ttl, track_idx, source):
    segs = []
    for i, t in enumerate(TRACK):
        segs.append((t, {"bold": i == track_idx, "color": NAVY if i == track_idx else GREY}))
        if i < len(TRACK) - 1:
            segs.append(("   ›   ", {"color": HAIR}))
    text(slide, 0.5, 0.22, 9, 0.3, [segs], size=11, name="!!track")
    text(slide, 0.5, 0.52, 11.4, 0.95, ttl, size=22, bold=True, color=NAVY, name="!!title")
    picture(slide, FIG + "Imperial_College_London_crest.png", 12.2, 0.3, 0.62, name="!!crest", border=False)
    if source:
        text(slide, 0.5, 6.62, 8.0, 0.28, "Source: " + source, size=9.5, color=GREY, name="!!source")
    hline(slide, 0.5, 6.93, 12.83, 6.93, name="!!footrule")
    text(slide, 0.5, 7.0, 9.0, 0.3,
         "Faisal Bindakhil  |  MSc Thesis  |  Offshore wind cannibalisation in the Baltic and North Sea",
         size=10, color=GREY, name="!!footer")
    text(slide, 11.3, 7.0, 1.53, 0.3, f"{n} / {N_SLIDES}", size=10, color=GREY, align=PP_ALIGN.RIGHT, name="!!pageno")


def notes(slide, s):
    slide.notes_slide.notes_text_frame.text = s


def add_morph(slide, dur_ms):
    xml = f'''<mc:AlternateContent xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006"
        xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
      <mc:Choice xmlns:p14="http://schemas.microsoft.com/office/powerpoint/2010/main" Requires="p14">
        <p:transition spd="slow" p14:dur="{dur_ms}">
          <p159:morph xmlns:p159="http://schemas.microsoft.com/office/powerpoint/2015/09/main" option="byObject"/>
        </p:transition>
      </mc:Choice>
      <mc:Fallback><p:transition spd="slow"><p:fade/></p:transition></mc:Fallback>
    </mc:AlternateContent>'''
    ns = {"p": "http://schemas.openxmlformats.org/presentationml/2006/main"}
    slide._element.find("p:clrMapOvr", ns).addnext(etree.fromstring(xml))


# =========================================================
# Map zoom sequence: shared geometry
# =========================================================
CROPS = json.load(open(HERE + "crops.json"))["crops"]
EXT = dict(lon0=-13.0, lon1=33.0, lat0=48.0, lat1=64.0)
MAP_IMG = HERE + "europe_map_rgb.png"
MX, MY, MW = 0.5, 1.6, 7.7
RX, RW = 8.6, 4.23


def merc_y(lat):
    return math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))


def frac(lon, lat):
    fx = (lon - EXT["lon0"]) / (EXT["lon1"] - EXT["lon0"])
    fy = (merc_y(EXT["lat1"]) - merc_y(lat)) / (merc_y(EXT["lat1"]) - merc_y(EXT["lat0"]))
    return fx, fy


def sea_map(slide, view):
    """The same basemap picture, cropped to a view; Morph animates the zoom between slides."""
    c = CROPS[view]
    h = MW / c["aspect"]
    p = slide.shapes.add_picture(MAP_IMG, Inches(MX), Inches(MY), Inches(MW), Inches(h))
    p.crop_left, p.crop_right, p.crop_top, p.crop_bottom = c["left"], c["right"], c["top"], c["bottom"]
    p.line.color.rgb = HAIR
    p.line.width = Pt(0.5)
    p.name = "!!seamap"
    return p, h


def map_legend(slide, x, y):
    rect(slide, x, y, 0.22, 0.22, MAPNAVY, name="!!lg1")
    text(slide, x + 0.3, y - 0.03, 1.7, 0.3, "operating", size=10.5, name="!!lg1t")
    rect(slide, x + 2.1, y, 0.22, 0.22, MAPMID, name="!!lg2")
    text(slide, x + 2.4, y - 0.03, 1.9, 0.3, "approved or building", size=10.5, name="!!lg2t")
    rect(slide, x, y + 0.36, 0.22, 0.22, None, line=MAPMID, lw=0.75, dash=MSO_LINE_DASH_STYLE.DASH, name="!!lg3")
    text(slide, x + 0.3, y + 0.33, 1.7, 0.3, "planned", size=10.5, name="!!lg3t")
    shape(slide, MSO_SHAPE.OVAL, x + 2.1, y + 0.36, 0.22, 0.22, None, line=NSBLUE, lw=1.5, name="!!lg4")
    text(slide, x + 2.4, y + 0.33, 1.9, 0.3, "one of the 31 study farms", size=10.5, name="!!lg4t")


SRC_MAP = "EMODnet Human Activities wind-farm layer (2026 update); ENTSO-E; own analysis"

# ----- 1  Europe -----
s = prs.slides.add_slide(BLANK)
frame(s, 1, "Europe's offshore wind sits in two seas: one crowded, one about to be built", 0, SRC_MAP)
_, mh = sea_map(s, "europe")
for label, lon, lat, col in (("NORTH SEA", 2.0, 57.2, NSBLUE), ("BALTIC SEA", 19.6, 58.0, BALRED)):
    fx, fy = frac(lon, lat)
    text(s, MX + fx * MW - 0.9, MY + fy * mh - 0.15, 1.8, 0.3, label, size=11, bold=True, color=col,
         align=PP_ALIGN.CENTER, name="!!lbl_" + label[:5])
map_legend(s, RX, 1.65)
col_header(s, RX, 2.45, RW, "Why prices fall as farms multiply", name="!!hdr")
BASE = 4.75
for px, label, many, bar_h, val in ((RX, "One farm", False, 1.2, "100"), (RX + 2.2, "Many farms", True, 0.6, "50")):
    text(s, px, 2.95, 1.9, 0.3, label, size=11.5, bold=True, color=NAVY, align=PP_ALIGN.CENTER)
    rect(s, px, BASE, 1.9, 0.16, SEA)
    if not many:
        turbine(s, px + 0.65, BASE, 0.95)
    else:
        for dx, off in ((0.28, 0), (0.66, 60), (1.04, 0)):
            turbine(s, px + dx, BASE, 0.55, offset=off)
    hline(s, px + 1.3, BASE - 1.2, px + 1.9, BASE - 1.2, color=GREY, width=1, dash=MSO_LINE_DASH_STYLE.DASH)
    rect(s, px + 1.45, BASE - bar_h, 0.32, bar_h, NSBLUE)
    text(s, px + 1.45, BASE - bar_h + 0.05, 0.32, 0.25, val, size=10, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
text(s, RX, 5.05, RW, 1.4, [
    "Farms in one sea generate in the same hours, so supply peaks together and the price every farm earns falls.",
    "",
    [("Capture value", {"bold": True}), (" = the share of the average market price a farm actually receives.", {})],
], size=11.5, color=INK)
notes(s, "Europe's offshore wind sits in two seas. Every filled shape on this map is an operating wind farm, every "
         "dashed outline is a planned one. The mechanism I study is simple: farms in one sea generate in the same "
         "hours, so when they produce, supply peaks together and the price they all sell at falls. The share of the "
         "average market price a farm actually receives is its capture value. Let us zoom in.")

# ----- 2  North Sea (Morph) -----
s = prs.slides.add_slide(BLANK)
frame(s, 2, "The North Sea is crowded: new farms are pushed further offshore and the price they earn keeps falling",
      0, "EMODnet wind-farm layer (2026 update): status, capacity, distance to shore; ENTSO-E; own analysis")
sea_map(s, "northsea")
map_legend(s, RX, 1.65)
col_header(s, RX, 2.45, RW, "North Sea", name="!!hdr", color=NSBLUE)
ladder(s, RX, 2.95, RW, [
    ("130 farms · 36 GW", "operating today, with 157 GW more approved, under construction or planned", NSBLUE),
    ("13 → 45 km", "average distance to shore, farms built before 2012 vs since 2019: the near-shore sites are taken", NSBLUE),
    ("0.95 → 0.87", "capture value 2017 to 2024: more farms in the same wind hours, a lower price for all", NSBLUE),
], num_size=24, row_h=1.2, name="!!kf")
sparkline(s, RX + 2.6, 5.4, 1.55, 0.42, [0.950, 0.965, 0.951, 0.893, 0.920, 0.907, 0.888, 0.868], NSBLUE,
          lo=0.80, hi=0.98, name="!!spark")
notes(s, "The North Sea first. One hundred and thirty operating farms, thirty-six gigawatts, and another hundred and "
         "fifty-seven approved, under construction or planned. The near-shore sites are taken: farms built before 2012 "
         "sat thirteen kilometres from shore on average, those built since 2019 sit forty-five kilometres out. And the "
         "price they earn keeps falling: capture value went from 0.95 to 0.87 in eight years.")
add_morph(s, 2000)

# ----- 3  Baltic (Morph) -----
s = prs.slides.add_slide(BLANK)
frame(s, 3, "The Baltic is where the next wave goes: open sea space, shallow water and a market that has barely begun",
      0, SRC_MAP + "; BEMIP 2024 for technical potential")
sea_map(s, "baltic")
map_legend(s, RX, 1.65)
col_header(s, RX, 2.45, RW, "Baltic Sea", name="!!hdr", color=BALRED)
ladder(s, RX, 2.95, RW, [
    ("18 farms · 6 GW", "operating today, a sixth of the North Sea; 99 GW approved or planned, nineteen-fold growth by 2040", BALRED),
    ("93 GW", "technical potential in shallow, fixed-bottom water with strong, steady winds", BALRED),
    ("0.88", "capture value today, level with the North Sea at a tenth of the buildout: cannibalisation has barely begun", BALRED),
], num_size=24, row_h=1.08, name="!!kf")
hline(s, RX, 6.12, RX + RW, 6.12, color=NAVY, width=1.0, name="!!rqrule")
text(s, RX, 6.18, RW, 0.45, [[("Research question  ", {"bold": True, "italic": False, "color": NAVY}),
                             ("Will the Baltic lose value the way the North Sea did, and how much of that can be designed away?", {})]],
     size=11, italic=True, color=NAVY, name="!!rq")
notes(s, "Now the Baltic. Eighteen operating farms, six gigawatts, a sixth of the North Sea, but ninety-nine gigawatts "
         "approved or planned and ninety-three gigawatts of technical potential in shallow water with strong winds. "
         "And today its farms capture the same share of the market price as the North Sea's, at a tenth of the "
         "buildout: cannibalisation has barely begun. So my question: will the Baltic lose value the way the North Sea "
         "did once its fleet is built, and how much of that can be designed away?")
add_morph(s, 2000)

# =========================================================
# 4  Research question: deliberately plain
# =========================================================
s = prs.slides.add_slide(BLANK)
frame(s, 4, "Research question", 1, "")
text(s, 0.5, 2.0, 12.3, 1.6,
     "Will the Baltic lose value the way the North Sea did once its planned fleet is built, and how much of that "
     "loss can be avoided by building the surrounding system differently?",
     size=26, color=NAVY, font=LIGHT)
hline(s, 0.5, 3.95, 12.83, 3.95)
for x, num, q, needs in (
        (0.5, "1", "How do the two seas compare in capture value today, and how will they compare once the "
                   "planned fleet is built?",
         "needs the observed record, and a market for 2040 that does not yet exist"),
        (6.9, "2", "What causes the loss of value, and how much of it can be avoided by building the surrounding "
                   "system differently?",
         "needs a market that can be rebuilt from its parts and run under a different grid")):
    text(s, x, 4.2, 0.5, 0.6, num, size=26, color=HAIR, font=LIGHT)
    text(s, x + 0.55, 4.28, 5.35, 1.0, q, size=14, color=INK)
    text(s, x + 0.55, 5.35, 5.35, 0.6, needs, size=11.5, italic=True, color=GREY)
notes(s, "So the question this thesis asks. Will the Baltic lose value the way the North Sea did once its planned "
         "fleet is built, and how much of that loss can be avoided by building the surrounding system differently? "
         "That splits into two. First, how do the two seas compare today and once the fleet is built: that needs the "
         "observed record and a market for 2040 that does not yet exist. Second, what causes the loss and how much can "
         "be avoided: that needs a market I can rebuild from its parts and run under a different grid. Those two needs "
         "are the method.")

# =========================================================
# 5  Method: two lanes of chevrons
# =========================================================
s = prs.slides.add_slide(BLANK)
frame(s, 5, "Two models: one learns from eight years of observed prices, the other rebuilds the 2040 market "
            "from its parts", 2, "ENTSO-E; PyPSA-Eur (open power-system model); ENTSO-E TYNDP 2030 and 2040 scenarios")
CH_W, CH_H, OVER = 3.75, 1.15, 0.25
LANE_X = 2.35
lanes = [
    ("Observed record", NAVY, 1.85, [
        ("Eight years of hourly prices", "31 farms, 7 bidding zones, 2017 to 2024"),
        ("Statistical model", "panel regression; R² 0.80 out of sample"),
        ("Capture value today", "observed baseline for both seas"),
    ]),
    ("Power-system model", LANE2, 3.95, [
        ("PyPSA-Eur", "plants, grid and demand, hour by hour"),
        ("Two 2040 grid cases", "today's grid vs expanded at least cost"),
        ("Value-adjusted LCOE", "= cost / capture value: break-even price"),
    ]),
]
for lane_name, col, ly, steps in lanes:
    text(s, 0.5, ly + 0.3, 1.75, 0.6, lane_name, size=13, bold=True, color=col)
    for k, (head, sub) in enumerate(steps):
        x = LANE_X + k * (CH_W - OVER)
        kind = MSO_SHAPE.PENTAGON if k == 0 else MSO_SHAPE.CHEVRON
        ch = shape(s, kind, x, ly, CH_W, CH_H, col)
        tf = ch.text_frame
        tf.margin_left = Inches(0.45 if k else 0.25)
        tf.margin_right = Inches(0.35)
        tf.margin_top = tf.margin_bottom = Inches(0.05)
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        fill_text(tf, [[(head, {"bold": True, "size": 13, "color": WHITE})], [(sub, {"size": 11, "color": WHITE})]],
                  12, WHITE)
bx = LANE_X + 2 * (CH_W - OVER) + CH_W / 2
hline(s, bx, 1.85 + CH_H, bx, 3.95, color=GREY, width=1.25, dash=MSO_LINE_DASH_STYLE.DASH)
rect(s, bx - 1.45, 3.08, 2.9, 0.56, WHITE)
text(s, bx - 1.45, 3.1, 2.9, 0.55, ["Cross-checked on 2023", "agree within 0.5 percentage points"],
     size=10.5, color=INK, align=PP_ALIGN.CENTER)
col_header(s, 0.5, 5.35, 5.9, "What the observed record gives")
text(s, 0.5, 5.75, 5.9, 0.8, "What has already happened, and a check that the system model reproduces it.",
     size=12.5, color=INK)
col_header(s, 6.9, 5.35, 5.93, "What the system model adds")
text(s, 6.9, 5.75, 5.93, 0.8, "A market that can be run under a grid that does not yet exist: same wind, same farms, "
                              "different cables.", size=12.5, color=INK)
notes(s, "Two models. The top lane is statistical: a panel regression trained on eight years of hourly prices at 31 "
         "farms; it explains about eighty per cent of the out-of-sample variation in capture value and tells me what has "
         "already happened. The bottom lane is PyPSA-Eur, a power-system model that rebuilds the market from its parts, "
         "every plant, cable and demand centre, hour by hour, under the official 2040 scenarios. Because it rebuilds the "
         "market, I can run 2040 twice, once with today's grid and once with the grid expanded, and read off the "
         "break-even price. The two models are cross-checked on 2023 and agree within half a percentage point.")

# =========================================================
# 6  Results 1/2: hand-drawn bar chart with annotations on the bars
# =========================================================
s = prs.slides.add_slide(BLANK)
frame(s, 6, "Today the two seas are equal; by 2040 the Baltic loses almost half its value unless the grid is expanded",
      3, "PyPSA-Eur, ENTSO-E TYNDP scenarios; observed 2023 to 2024 from ENTSO-E; own analysis")
text(s, 0.5, 1.6, 7.6, 0.3, "Capture value, share of the average market price", size=11, italic=True, color=GREY)
PX0, PX1 = 0.9, 7.9
BASE_Y, SCALE = 5.75, 3.55
groups = [("Today, observed", 0.88, 0.88), ("2040, today's grid", 0.57, 0.47), ("2040, grid expanded", 0.64, 0.66)]
BW = 0.72
GAPB = 0.08
centers = [PX0 + (PX1 - PX0) * (i + 0.5) / 3 for i in range(3)]
hline(s, PX0 - 0.2, BASE_Y, PX1 + 0.2, BASE_Y, color=GREY, width=1)
hline(s, PX0 - 0.2, BASE_Y - 0.88 * SCALE, PX1 + 0.2, BASE_Y - 0.88 * SCALE, color=GREY, width=1,
      dash=MSO_LINE_DASH_STYLE.DASH)
text(s, PX1 - 1.4, BASE_Y - 0.88 * SCALE - 0.28, 1.6, 0.26, "today's level, 0.88", size=10, italic=True,
     color=GREY, align=PP_ALIGN.RIGHT)
tops = {}
for gi, (label, nsv, bal) in enumerate(groups):
    cx = centers[gi]
    for si, (val, col) in enumerate(((nsv, NSBLUE), (bal, BALRED))):
        x = cx - BW - GAPB / 2 + si * (BW + GAPB)
        h = val * SCALE
        rect(s, x, BASE_Y - h, BW, h, col)
        text(s, x - 0.1, BASE_Y - h - 0.3, BW + 0.2, 0.28, f"{val:.2f}", size=12, bold=True, color=col,
             align=PP_ALIGN.CENTER)
        tops[(gi, si)] = (x, BASE_Y - h)
    text(s, cx - 1.2, BASE_Y + 0.1, 2.4, 0.3, label, size=12, color=INK, align=PP_ALIGN.CENTER)
lx = PX0 - 0.2
rect(s, lx, 6.2, 0.18, 0.18, NSBLUE)
text(s, lx + 0.26, 6.17, 1.2, 0.26, "North Sea", size=11, color=INK)
rect(s, lx + 1.4, 6.2, 0.18, 0.18, BALRED)
text(s, lx + 1.66, 6.17, 1.0, 0.26, "Baltic", size=11, color=INK)
ref_y = BASE_Y - 0.88 * SCALE
for si, (val, col, lab) in enumerate(((0.57, NSBLUE, "−35%"), (0.47, BALRED, "−47%"))):
    x, top = tops[(1, si)]
    ax = x + BW / 2
    hline(s, ax, ref_y + 0.05, ax, top - 0.34, color=col, width=1.25, arrow_end=True)
    mid_y = ref_y + (top - 0.34 - ref_y) / 2 - 0.15
    if si == 0:
        text(s, ax - 0.75, mid_y, 0.68, 0.3, lab, size=12, bold=True, color=col, align=PP_ALIGN.RIGHT)
    else:
        text(s, ax + 0.08, mid_y, 0.7, 0.3, lab, size=12, bold=True, color=col, align=PP_ALIGN.LEFT)
x2, top2 = tops[(1, 1)]
x3, top3 = tops[(2, 1)]
hline(s, x2 + BW + 0.05, top2, x3 + BW + 0.32, top2, color=GREEN, width=1, dash=MSO_LINE_DASH_STYLE.SQUARE_DOT)
hline(s, x3 + BW + 0.2, top2, x3 + BW + 0.2, top3 + 0.02, color=GREEN, width=1.5, arrow_end=True)
text(s, x3 + BW + 0.3, top3 + (top2 - top3) / 2 - 0.15, 0.7, 0.3, "+0.19", size=12, bold=True, color=GREEN)
ladder(s, 8.7, 1.7, 4.1, [
    ("0.88 = 0.88", "today both seas capture the same share of the market price: no Baltic penalty yet", NAVY),
    ("½", "of the Baltic loss under today's grid is congestion in the grid, not the wind resource", BALRED),
    ("0.66 vs 0.64", "with transmission expanded the Baltic is level with the North Sea again", GREEN),
], num_size=26, row_h=1.45)
notes(s, "First result. Today the two seas are equal: both capture about 88 per cent of the average price. By 2040 with "
         "the planned fleet and today's grid, the North Sea falls to 57 and the Baltic to 47, almost half its present "
         "value gone. Expand the grid and the Baltic recovers to 66, level with the North Sea. Decomposing the loss, "
         "about half of the Baltic's extra erosion is congestion, not the wind itself.")

# =========================================================
# 7  Value-adjusted LCOE: the concept, before the maps
# =========================================================
s = prs.slides.add_slide(BLANK)
frame(s, 7, "Combine capture value with LCOE and you get the price a farm must earn, not just the cost it must beat",
      3, "PyPSA-Eur 2040, grid frozen at today's network; LCOE from the model's cost assumptions; medians across the seabed studied")
EQ_Y = 2.95
for x, w, head, sub in ((0.5, 3.3, "LCOE", "what it costs to produce one MWh"),
                        (4.75, 3.3, "capture value", "the share of the market price the farm actually receives"),
                        (8.95, 3.9, "value-adjusted LCOE", "the market price a farm needs to break even")):
    text(s, x, EQ_Y, w, 0.65, head, size=30, color=NAVY, font=LIGHT)
    text(s, x, EQ_Y + 0.72, w, 0.6, sub, size=12, color=GREY)
text(s, 3.85, EQ_Y - 0.1, 0.85, 0.85, "÷", size=40, color=GREY, font=LIGHT, align=PP_ALIGN.CENTER)
text(s, 8.05, EQ_Y - 0.1, 0.85, 0.85, "=", size=40, color=GREY, font=LIGHT, align=PP_ALIGN.CENTER)
text(s, 0.5, 5.2, 12.3, 0.8,
     "Between 2025 and 2040 the median site gets cheaper to build, 74 → 66 EUR/MWh, yet needs a higher price "
     "to break even, 87 → 121, because capture value falls faster than cost.",
     size=14, italic=True, color=NAVY)
notes(s, "Before the maps, one idea. LCOE tells you what it costs to produce a megawatt hour. Capture value tells you "
         "what share of the market price you actually get for it. Divide one by the other and you get the price a farm "
         "must earn on average to break even: the value-adjusted LCOE. Between 2025 and 2040 the median site gets "
         "cheaper to build, 74 down to 66, but its break-even price rises from 87 to 121, because capture value falls "
         "faster than cost. The share of seabed that still clears seventy euros collapses from a third to under one "
         "per cent. The next two maps show that break-even price across the sea.")

# =========================================================
# 8 and 9  Results 2/2 and Conclusion: spatial vLCOE, Morph
# =========================================================
MAP_W = 8.0
MAP_H = MAP_W * 576 / 1222
MAP_X, MAP_Y = 0.5, 1.6
CB_W = 5.0
CB_H = CB_W * 82 / 1065
RX2, RW2 = 8.85, 3.98


def map_base(slide, img, sublabel, show_def=True):
    text(slide, MAP_X, MAP_Y - 0.02, MAP_W, 0.3, sublabel, size=11, italic=True, color=GREY, name="!!maplabel")
    picture(slide, HERE + img, MAP_X, MAP_Y + 0.3, MAP_W, name="!!map")
    picture(slide, HERE + "colourbar.png", MAP_X + (MAP_W - CB_W) / 2, MAP_Y + 0.3 + MAP_H + 0.08, CB_W,
            name="!!colourbar", border=False)
    text(slide, MAP_X, MAP_Y + 0.3 + MAP_H + 0.08 + CB_H, MAP_W, 0.3,
         "Value-adjusted LCOE, EUR per MWh   (dashed contour at 70)", size=10.5, color=GREY,
         align=PP_ALIGN.CENTER, name="!!cblabel")
    rect(slide, RX2, MAP_Y + 0.3, 0.26, 0.26, GREEN, name="!!chipg")
    text(slide, RX2 + 0.36, MAP_Y + 0.27, 3.5, 0.32, "bankable: below 70 EUR/MWh", size=11, name="!!chipgl")
    rect(slide, RX2, MAP_Y + 0.7, 0.26, 0.26, BALRED, name="!!chipr")
    text(slide, RX2 + 0.36, MAP_Y + 0.67, 3.5, 0.32, "does not pay back", size=11, name="!!chiprl")
    if show_def:
        text(slide, RX2, MAP_Y + 1.15, RW2, 0.75, [
            [("Value-adjusted LCOE", {"bold": True, "color": NAVY}),
             (" = LCOE ÷ capture value: the average market price a farm needs to pay itself back.", {})]],
             size=11, color=GREY, name="!!def")
        hline(slide, RX2, MAP_Y + 2.0, RX2 + RW2, MAP_Y + 2.0, name="!!defrule")


s = prs.slides.add_slide(BLANK)
frame(s, 8, "Under today's grid the central Baltic has the highest value-adjusted LCOE in the region by 2040",
      3, "PyPSA-Eur 2040, grid frozen at today's network; LCOE from the model's cost assumptions; own analysis")
map_base(s, "vlcoe_frozen.png", "Value-adjusted LCOE (break-even price) for offshore wind in 2040, today's grid")
ladder(s, RX2, MAP_Y + 2.2, RW2, [
    ("87 → 121", "EUR/MWh: median value-adjusted LCOE across the seabed studied, 2025 to 2040. Cost falls, capture value falls faster.", BALRED),
    ("0.47", "Baltic capture value in 2040 under today's grid, against 0.57 in the North Sea", BALRED),
], num_size=28, row_h=1.35, name="!!kf")
notes(s, "Second result, in space. This is the price a wind farm would need to break even in 2040 once you account for "
         "the fact that it only captures part of the market price. Green is bankable, red is not. Technology cost keeps "
         "falling, yet under today's grid the Baltic break-even price rises from 87 to 121 euros per megawatt hour, "
         "because value falls faster than cost. The central Baltic is deep red.")

s = prs.slides.add_slide(BLANK)
frame(s, 9, "Expanding the grid turns the Baltic green: cannibalisation is a design choice, not a fate",
      4, "PyPSA-Eur 2040, transmission expanded at least cost; own analysis")
map_base(s, "vlcoe_optimal.png", "Value-adjusted LCOE (break-even price) for offshore wind in 2040, grid expanded",
         show_def=False)
col_header(s, RX2, MAP_Y + 1.2, RW2, "Conclusion", name="!!conchdr", color=NAVY)
text(s, RX2, MAP_Y + 1.62, RW2, 1.0,
     "The Baltic's extra loss of value is grid congestion, not the sea itself: expand transmission and Baltic "
     "farms earn as much as North Sea farms.", size=13, color=NAVY, name="!!conclusion")
ladder(s, RX2, MAP_Y + 2.7, RW2, [
    ("−33 EUR/MWh", "Baltic value-adjusted LCOE with the grid expanded; Polish and Danish waters fall below 70", GREEN),
    ("0.47 → 0.66", "Baltic capture value, level with the North Sea again", NAVY),
], num_size=24, row_h=1.0, name="!!kf")
hline(s, RX2, MAP_Y + 4.62, RX2 + RW2, MAP_Y + 4.62, color=NAVY, width=1.0, name="!!handrule")
text(s, RX2, MAP_Y + 4.7, RW2, 0.6, [
    [("Next, Markos  ", {"bold": True, "color": NAVY, "italic": False}),
     ("given this price risk, how much of a farm's output should be sold forward under a PPA, and how much "
      "left to the market?", {})]], size=11.5, italic=True, color=INK, name="!!handover")
notes(s, "Now expand the transmission. Same wind, same farms, same year. The Baltic turns green: interconnection lowers "
         "its break-even price by about 33 euros per megawatt hour, and Polish and Danish waters become some of the "
         "best sites in the region. Capture value recovers from 0.47 to 0.66, level with the North Sea. So the extra "
         "erosion the Baltic suffers is congestion, not a property of the sea. Cannibalisation is a design choice.\n\n"
         "Handover: Baltic wind farms earn less for their power than North Sea ones, and better interconnection removes "
         "most of that difference. So my work tells you what price the market will pay a developer, and how uncertain "
         "that price is. Markos picks up from there. Once you know that price is uncertain, the developer has a choice "
         "to make: sell some of the output forward under a PPA at a fixed price, or stay exposed to the market and hope "
         "for the upside. Markos will show how a developer should split between the two, and where the banks will let "
         "them draw that line.")
add_morph(s, 2000)

prs.save(OUT)
print("saved", OUT)
