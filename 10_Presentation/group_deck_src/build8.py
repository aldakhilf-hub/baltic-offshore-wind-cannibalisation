"""In-place restyle of the existing deck (no rebuild): 10 slides -> 8.
Deletes the empty slide and the old method slide, rebuilds every remaining slide's shapes,
keeps slide parts (and their Morph transitions) in place. Arial only, body 20 pt, captions 16 pt, titles 28 pt.
"""
from pathlib import Path
import math, json, copy
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.dml import MSO_LINE_DASH_STYLE
from lxml import etree
import matplotlib
matplotlib.use("Agg")
from matplotlib import cm

HERE = str(Path(__file__).resolve().parents[2] / "10_Presentation/group_deck_src") + "/"
FIG = str(Path(__file__).resolve().parents[2] / "9_Thesis_LaTeX/figures") + "/"
DECK = str(Path(__file__).resolve().parents[2] / "10_Presentation/Group_presentation_Faisal.pptx")

HEAD = RGBColor(0x00, 0x00, 0xCD)      # headings, Imperial blue
NS = RGBColor(0x00, 0x00, 0x80)        # North Sea and statistical model, navy
BAL = RGBColor(0xFF, 0x45, 0x00)       # Baltic, orange-red
PSM = RGBColor(0x00, 0x64, 0x00)       # power-system model, dark green
TINT = RGBColor(0xE6, 0xE6, 0xFA)      # method boxes
INK = RGBColor(0x1A, 0x1A, 0x1A)
GREY = RGBColor(0x59, 0x59, 0x59)
HAIR = RGBColor(0xBF, 0xBF, 0xBF)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
FONT = "Arial"
N = 8
TRACK = ["Background", "Question and method", "Results", "Conclusion"]

prs = Presentation()
prs.slide_width = Inches(13.333)
prs.slide_height = Inches(7.5)
_BLANK = prs.slide_layouts[6]
for _ in range(8):
    prs.slides.add_slide(_BLANK)


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


# ---------------- helpers ----------------
def run(p, s, size, color=INK, bold=False, italic=False):
    r = p.add_run()
    r.text = s
    f = r.font
    f.name, f.size, f.bold, f.italic = FONT, Pt(size), bold, italic
    f.color.rgb = color
    return r


def text(slide, x, y, w, h, s, size=20, color=INK, bold=False, italic=False, align=PP_ALIGN.LEFT,
         anchor=MSO_ANCHOR.TOP, name=None, space_after=6):
    box_ = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = box_.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = anchor
    lines = s if isinstance(s, list) else [s]
    for i, line in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        p.space_after = Pt(space_after)
        segs = line if isinstance(line, list) else [(line, {})]
        for seg, ov in segs:
            run(p, seg, ov.get("size", size), ov.get("color", color), ov.get("bold", bold), ov.get("italic", italic))
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


def line(slide, x1, y1, x2, y2, color=HAIR, width=1.0, dash=None, name=None, arrow=False):
    ln = slide.shapes.add_connector(1, Inches(x1), Inches(y1), Inches(x2), Inches(y2))
    ln.line.color.rgb = color
    ln.line.width = Pt(width)
    if dash:
        ln.line.dash_style = dash
    if arrow:
        ln_el = ln.line._get_or_add_ln()
        tail = etree.SubElement(ln_el, "{http://schemas.openxmlformats.org/drawingml/2006/main}tailEnd")
        tail.set("type", "triangle")
        tail.set("w", "med")
        tail.set("len", "med")
    if name:
        ln.name = name
    return ln


def picture(slide, path, x, y, w, h=None, name=None, border=True):
    p = slide.shapes.add_picture(path, Inches(x), Inches(y), Inches(w), Inches(h) if h else None)
    if border:
        p.line.color.rgb = HAIR
        p.line.width = Pt(0.5)
    else:
        p.line.fill.background()
    if name:
        p.name = name
    return p


def clear(slide):
    tree = slide.shapes._spTree
    for el in list(tree):
        if el.tag.endswith("}sp") or el.tag.endswith("}pic") or el.tag.endswith("}cxnSp") or el.tag.endswith("}grpSp") or el.tag.endswith("}graphicFrame"):
            tree.remove(el)


def delete_slide(prs, idx):
    sldIdLst = prs.slides._sldIdLst
    sld = list(sldIdLst)[idx]
    prs.part.drop_rel(sld.rId)
    sldIdLst.remove(sld)


def frame(slide, n, ttl, track_idx, source):
    segs = []
    for i, t in enumerate(TRACK):
        segs.append((t, {"bold": i == track_idx, "color": HEAD if i == track_idx else GREY}))
        if i < len(TRACK) - 1:
            segs.append(("   ›   ", {"color": HAIR}))
    text(slide, 0.5, 0.18, 10, 0.3, [segs], size=12, name="!!track", space_after=0)
    text(slide, 0.5, 0.42, 11.4, 1.0, ttl, size=28, bold=True, color=HEAD, name="!!title", space_after=0)
    picture(slide, FIG + "Imperial_College_London_crest.png", 12.2, 0.3, 0.62, name="!!crest", border=False)
    if source:
        text(slide, 0.5, 6.62, 9.5, 0.28, "Source: " + source, size=12, color=GREY, name="!!source", space_after=0)
    line(slide, 0.5, 6.93, 12.83, 6.93, name="!!footrule")
    text(slide, 0.5, 7.0, 9.0, 0.3, "Faisal Bindakhil  |  MSc Thesis  |  Offshore wind cannibalisation in the Baltic and North Sea",
         size=12, color=GREY, name="!!footer", space_after=0)
    text(slide, 11.3, 7.0, 1.53, 0.3, f"{n} / {N}", size=12, color=GREY, align=PP_ALIGN.RIGHT, name="!!pageno", space_after=0)


def notes(slide, s):
    slide.notes_slide.notes_text_frame.text = s


# ---------------- map geometry ----------------
CROPS = json.load(open(HERE + "crops.json"))["crops"]
EXT = dict(lon0=-13.0, lon1=33.0, lat0=48.0, lat1=64.0)
VIEWS = {"europe": dict(lon0=-12.0, lon1=33.0, lat0=50.7, lat1=61.7),
         "northsea": dict(lon0=-7.0, lon1=15.0, lat0=51.0, lat1=56.7),
         "baltic": dict(lon0=9.0, lon1=31.0, lat0=53.5, lat1=58.9)}
MAP_IMG = HERE + "europe_map_rgb.png"
MAP_Y, MAP_BOTTOM = 1.45, 6.5
MAP_H = MAP_BOTTOM - MAP_Y


def merc(lat):
    return math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))


def sea_map(slide, view):
    c = CROPS[view]
    w = MAP_H * c["aspect"]
    x = (13.333 - w) / 2
    p = slide.shapes.add_picture(MAP_IMG, Inches(x), Inches(MAP_Y), Inches(w), Inches(MAP_H))
    p.crop_left, p.crop_right, p.crop_top, p.crop_bottom = c["left"], c["right"], c["top"], c["bottom"]
    p.line.color.rgb = HAIR
    p.line.width = Pt(0.5)
    p.name = "!!seamap"
    return x, w


def at(view, x0, w, lon, lat):
    """Slide position of a lon/lat inside the displayed view."""
    v = VIEWS[view]
    fx = (lon - v["lon0"]) / (v["lon1"] - v["lon0"])
    fy = (merc(v["lat1"]) - merc(lat)) / (merc(v["lat1"]) - merc(v["lat0"]))
    return x0 + fx * w, MAP_Y + fy * MAP_H


def translucent(sh, alpha_pct):
    """Set fill transparency on a solid-filled shape (alpha_pct = opacity, 0-100)."""
    srgb = sh.fill._xPr.find(".//{http://schemas.openxmlformats.org/drawingml/2006/main}srgbClr")
    a = etree.SubElement(srgb, "{http://schemas.openxmlformats.org/drawingml/2006/main}alpha")
    a.set("val", str(int(alpha_pct * 1000)))


def map_legend(slide, x, y):
    back = rect(slide, x - 0.15, y - 0.12, 3.25, 1.75, WHITE, name="!!lgback")
    translucent(back, 78)
    rect(slide, x, y + 0.04, 0.24, 0.24, NS, name="!!lg1")
    text(slide, x + 0.34, y, 2.0, 0.35, "operating", size=16, name="!!lg1t", space_after=0)
    rect(slide, x, y + 0.44, 0.24, 0.24, RGBColor(0x80, 0x80, 0xC0), name="!!lg2")
    text(slide, x + 0.34, y + 0.4, 2.6, 0.35, "approved or building", size=16, name="!!lg2t", space_after=0)
    rect(slide, x, y + 0.84, 0.24, 0.24, None, line=NS, lw=0.75, dash=MSO_LINE_DASH_STYLE.DASH, name="!!lg3")
    text(slide, x + 0.34, y + 0.8, 2.0, 0.35, "planned", size=16, name="!!lg3t", space_after=0)
    shape(slide, MSO_SHAPE.OVAL, x, y + 1.24, 0.24, 0.24, WHITE, line=BAL, lw=1.5, name="!!lg4")
    text(slide, x + 0.34, y + 1.2, 2.6, 0.35, "one of the 31 study farms", size=16, name="!!lg4t", space_after=0)


S8 = list(prs.slides)
slides = [S8[0], S8[1], S8[2], None, S8[3], None, S8[4], S8[5], S8[6], S8[7]]   # keep old index mapping
SRC_MAP = "EMODnet wind-farm dataset, 2026 update. ENTSO-E. Own analysis."

# ================= 1 Europe =================
s = slides[0]
clear(s)
frame(s, 1, "Europe's offshore wind sits in a crowded North Sea and an almost empty Baltic", 0, SRC_MAP)
x0, w = sea_map(s, "europe")
lx, ly = at("europe", x0, w, -11.6, 61.4)
map_legend(s, lx + 0.1, ly + 0.1)
for label, lon, lat, col in (("NORTH SEA", 2.0, 56.9, NS), ("BALTIC SEA", 19.6, 57.4, BAL)):
    px, py = at("europe", x0, w, lon, lat)
    text(s, px - 1.2, py - 0.2, 2.4, 0.4, label, size=20, bold=True, color=col, align=PP_ALIGN.CENTER, space_after=0)
tx, ty = at("europe", x0, w, 12.3, 53.9)
text(s, tx, ty, 5.4, 1.3, "Farms in one sea generate in the same hours, so the price falls for all of them. "
                          "Capture value is the share of the average market price a farm receives.", size=20)
notes(s, "Europe's offshore wind sits in two seas. Every filled shape is an operating wind farm and every dashed "
         "outline is a planned one. The mechanism behind my work is simple. Farms in one sea generate in the same "
         "hours, so when they produce the price falls for all of them. The share of the average market price a farm "
         "receives is its capture value.")

# ================= 2 North Sea =================
s = slides[1]
clear(s)
frame(s, 2, "North Sea farms are being pushed offshore and capture a falling share of the price", 0,
      "EMODnet wind-farm dataset, 2026 update, operating farms with a known commissioning year. ENTSO-E. Own analysis.")
x0, w = sea_map(s, "northsea")
tx, ty = at("northsea", x0, w, -3.9, 52.65)
text(s, tx, ty, 3.1, 0.9, ["130 farms and 36 GW", "operate here today."], size=20, color=NS, bold=True, space_after=0)
tx, ty = at("northsea", x0, w, 7.2, 53.3)
text(s, tx, ty, 4.6, 1.9, "New farms sit 45 km offshore on average. Farms from before 2012 sat 13 km out. "
                          "Farms captured 0.87 of the average price in 2024, down from 0.95 in 2017.", size=20)
notes(s, "The North Sea first. One hundred and thirty operating farms, thirty-six gigawatts. The near-shore sites are "
         "taken: farms built since 2019 sit forty-five kilometres from shore on average, against thirteen for farms "
         "built before 2012. And the share of the price they capture keeps falling, from 0.95 in 2017 to 0.87 in 2024.")

# ================= 3 Baltic =================
s = slides[2]
clear(s)
frame(s, 3, "The Baltic has the space, the shallow water and a market where cannibalisation has barely begun", 0,
      "EMODnet wind-farm dataset, 2026 update. BEMIP 2024 for technical potential. ENTSO-E. Own analysis.")
x0, w = sea_map(s, "baltic")
tx, ty = at("baltic", x0, w, 12.6, 58.4)
text(s, tx, ty, 2.6, 1.0, ["18 farms and 6 GW", "operate here today."], size=20, color=BAL, bold=True, space_after=0)
tx, ty = at("baltic", x0, w, 23.4, 57.0)
text(s, tx, ty, 4.0, 2.6, "Another 99 GW is approved or planned. The technical potential is 93 GW, in shallow water "
                          "with strong winds. Baltic farms capture 0.88 of the average price today, the same share "
                          "as North Sea farms.", size=20)
notes(s, "Now the Baltic. Eighteen operating farms, six gigawatts, a sixth of the North Sea, but ninety-nine gigawatts "
         "approved or planned and ninety-three gigawatts of technical potential in shallow water with strong winds. "
         "Today its farms capture the same share of the market price as North Sea farms, at a tenth of the buildout.")

# ================= 4 Question and method (rebuilt on the old question slide) =================
s = slides[4]
clear(s)
frame(s, 4, "The question needs a record of the past and a model of a grid that does not yet exist", 1,
      "ENTSO-E Transparency Platform. ERA5 reanalysis. PyPSA-Eur. ENTSO-E TYNDP 2030 and 2040 scenarios.")
text(s, 0.5, 1.45, 12.3, 0.8,
     "Will the Baltic lose value the way the North Sea did once its planned fleet is built, and how much of that "
     "loss can be avoided by building the surrounding system differently?", size=20, color=HEAD, italic=True)
BX, BW, BH = [0.5, 4.7, 8.9], 3.93, 0.95


def mbox(slide, x, y, s_, color=INK, w=BW, h=BH, size=20):
    b = shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, x, y, w, h, TINT, adj=0.12)
    tf = b.text_frame
    tf.margin_left = tf.margin_right = Inches(0.12)
    tf.margin_top = tf.margin_bottom = Inches(0.04)
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    tf.word_wrap = True
    lines = s_ if isinstance(s_, list) else [s_]
    for i, ln in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = PP_ALIGN.CENTER
        segs = ln if isinstance(ln, list) else [(ln, {})]
        for seg, ov in segs:
            run(p, seg, ov.get("size", size), ov.get("color", color), ov.get("bold", ov.get("bold", False)))
    return b


R1, R2, R3 = 2.55, 4.05, 5.55
mbox(s, BX[0], R1, "ENTSO-E hourly prices, 31 farms, 2017 to 2024", size=18)
mbox(s, BX[1], R1, "ERA5 hourly weather", size=18)
mbox(s, BX[2], R1, "Plants, grid, demand and 2040 scenarios", size=18)
mbox(s, BX[0], R2, [[("Statistical model", {"bold": True, "color": NS})], [("for today", {"size": 16})]], color=NS)
mbox(s, BX[2], R2, [[("Power-system model, PyPSA-Eur", {"bold": True, "color": PSM})], [("for 2040 under two grids", {"size": 16})]], color=PSM)
mbox(s, BX[1], R3, "Capture value, both seas, today and 2040", size=18)
# arrows
cx = [x + BW / 2 for x in BX]
line(s, cx[0], R1 + BH, cx[0], R2, color=GREY, width=1.5, arrow=True)                    # prices -> statistical
line(s, cx[2], R1 + BH, cx[2], R2, color=GREY, width=1.5, arrow=True)                    # system inputs -> PSM
line(s, cx[1] - 0.3, R1 + BH, cx[0] + 0.9, R2, color=GREY, width=1.5, arrow=True)         # ERA5 -> statistical
line(s, cx[1] + 0.3, R1 + BH, cx[2] - 0.9, R2, color=GREY, width=1.5, arrow=True)         # ERA5 -> PSM
line(s, cx[0] + 0.9, R2 + BH, cx[1] - 0.4, R3, color=GREY, width=1.5, arrow=True)         # statistical -> CV
line(s, cx[2] - 0.9, R2 + BH, cx[1] + 0.4, R3, color=GREY, width=1.5, arrow=True)         # PSM -> CV
text(s, BX[1], R2 + 0.12, BW, 0.75, "Both reproduce 2023 within 0.5 percentage points.", size=16, color=GREY,
     italic=True, align=PP_ALIGN.CENTER)
notes(s, "The question splits in two: how do the two seas compare today and once the fleet is built, and what causes "
         "the loss and how much can be avoided. The first needs the observed record, the second needs a market I can "
         "rebuild under a grid that does not yet exist. So there are two models. Both take ERA5 weather. The "
         "statistical model learns from eight years of ENTSO-E prices at 31 farms and is the right tool for today. The "
         "power-system model, PyPSA-Eur, rebuilds the market from plants, grid and demand under the official scenarios "
         "and is the right tool for 2040, because I can run it under two grids. Both reproduce 2023 within half a "
         "percentage point, and both produce the same output, capture value.")

# ================= 5 Capture value bars (rebuilt on the old bars slide) =================
s = slides[6]
clear(s)
frame(s, 5, "The Baltic loses almost half its value by 2040 under today's grid and recovers it when the grid is expanded",
      2, "PyPSA-Eur under ENTSO-E TYNDP scenarios. Observed 2023 to 2024 from ENTSO-E. Own analysis.")
PX0, PX1 = 1.3, 12.0
BASE_Y, SCALE = 5.35, 3.4
groups = [("Today, observed", 0.88, 0.88), ("2040, today's grid", 0.57, 0.47), ("2040, grid expanded", 0.64, 0.66)]
BW_, GAPB = 1.05, 0.12
centers = [PX0 + (PX1 - PX0) * (i + 0.5) / 3 for i in range(3)]
line(s, PX0 - 0.3, BASE_Y, PX1 + 0.3, BASE_Y, color=GREY, width=1)
ref_y = BASE_Y - 0.88 * SCALE
line(s, PX0 - 0.3, ref_y, PX1 + 0.3, ref_y, color=GREY, width=1, dash=MSO_LINE_DASH_STYLE.DASH)
text(s, PX1 - 2.6, ref_y - 0.32, 2.9, 0.3, "today's share, 0.88", size=16, italic=True, color=GREY, align=PP_ALIGN.RIGHT, space_after=0)
tops = {}
for gi, (label, nsv, bal) in enumerate(groups):
    c = centers[gi]
    for si, (val, col) in enumerate(((nsv, NS), (bal, BAL))):
        x = c - BW_ - GAPB / 2 + si * (BW_ + GAPB)
        h = val * SCALE
        rect(s, x, BASE_Y - h, BW_, h, col)
        text(s, x - 0.2, BASE_Y - h - 0.38, BW_ + 0.4, 0.35, f"{val:.2f}", size=20, bold=True, color=col, align=PP_ALIGN.CENTER, space_after=0)
        tops[(gi, si)] = (x, BASE_Y - h)
    text(s, c - 1.6, BASE_Y + 0.08, 3.2, 0.35, label, size=20, color=INK, align=PP_ALIGN.CENTER, space_after=0)
# legend inline, top left
rect(s, PX0 - 0.3, 1.55, 0.24, 0.24, NS)
text(s, PX0 + 0.04, 1.5, 1.6, 0.35, "North Sea", size=16, space_after=0)
rect(s, PX0 + 1.5, 1.55, 0.24, 0.24, BAL)
text(s, PX0 + 1.84, 1.5, 1.2, 0.35, "Baltic", size=16, space_after=0)
# loss arrows with labels beside them
for si, (val, col, lab) in enumerate(((0.57, NS, "−35%"), (0.47, BAL, "−47%"))):
    x, top = tops[(1, si)]
    ax = x + BW_ / 2
    line(s, ax, ref_y + 0.05, ax, top - 0.42, color=col, width=1.5, arrow=True)
    mid = ref_y + (top - 0.42 - ref_y) / 2 - 0.18
    if si == 0:
        text(s, ax - 1.0, mid, 0.9, 0.35, lab, size=18, bold=True, color=col, align=PP_ALIGN.RIGHT, space_after=0)
    else:
        text(s, ax + 0.1, mid, 0.9, 0.35, lab, size=18, bold=True, color=col, align=PP_ALIGN.LEFT, space_after=0)
x2, top2 = tops[(1, 1)]
x3, top3 = tops[(2, 1)]
line(s, x2 + BW_ + 0.05, top2, x3 + BW_ + 0.45, top2, color=PSM, width=1, dash=MSO_LINE_DASH_STYLE.SQUARE_DOT)
line(s, x3 + BW_ + 0.3, top2, x3 + BW_ + 0.3, top3 + 0.02, color=PSM, width=1.5, arrow=True)
text(s, x3 + BW_ + 0.42, top3 + (top2 - top3) / 2 - 0.18, 1.0, 0.35, "+0.19", size=18, bold=True, color=PSM, space_after=0)
text(s, 0.5, 5.85, 12.3, 0.7,
     "About half of the Baltic loss under today's grid comes from congestion in the grid. With the grid expanded "
     "the Baltic share recovers to 0.66, level with the North Sea.", size=20)
notes(s, "First result. Today both seas capture 0.88 of the average price. By 2040 with the planned fleet and "
         "today's grid the North Sea falls to 0.57 and the Baltic to 0.47, almost half its value. About half of the "
         "Baltic loss is congestion in the grid. Expand the grid and the Baltic recovers to 0.66, level with the "
         "North Sea.")

# ================= 6 Equation (rebuilt on the old equation slide) =================
s = slides[7]
clear(s)
frame(s, 6, "Dividing LCOE by capture value gives the market price a farm needs to break even", 2,
      "PyPSA-Eur 2040, grid frozen at today's network. Medians across the seabed studied.")
EQ_Y = 2.75
for x, w_, head, sub in ((0.5, 2.9, "LCOE", "what it costs to produce one MWh"),
                         (4.25, 3.4, "capture value", "the share of the market price a farm receives"),
                         (8.45, 4.4, "value-adjusted LCOE", "the market price a farm needs to break even")):
    text(s, x, EQ_Y, w_, 0.7, head, size=30, color=HEAD, space_after=0)
    text(s, x, EQ_Y + 0.85, w_, 1.0, sub, size=20, color=GREY)
text(s, 3.45, EQ_Y - 0.1, 0.8, 0.9, "÷", size=40, color=GREY, align=PP_ALIGN.CENTER, space_after=0)
text(s, 7.7, EQ_Y - 0.1, 0.75, 0.9, "=", size=40, color=GREY, align=PP_ALIGN.CENTER, space_after=0)
text(s, 0.5, 5.0, 12.3, 1.2,
     "By 2040 the median site costs 66 EUR/MWh to build, less than in 2025. Its break-even price rises to "
     "121 EUR/MWh, because capture value falls faster than cost.", size=20, color=HEAD)
notes(s, "Before the maps, one idea. LCOE is what it costs to produce a megawatt hour. Capture value is the share "
         "of the market price you receive for it. Divide one by the other and you get the price a farm must earn on "
         "average to break even, the value-adjusted LCOE. By 2040 the median site is cheaper to build, 66 euros, "
         "down from 74, yet its break-even price rises to 121, up from 87, because capture value falls faster than cost.")

# ================= 7 and 8: vLCOE maps =================
MW = 9.2
MH = MW * 576 / 1222
MX = (13.333 - MW) / 2
MY = 1.45
cmap = cm.get_cmap("RdYlGn_r")


def colourbar(slide, x, y, w, name):
    n = 24
    lo, hi = 45, 165
    seg = w / n
    for i in range(n):
        v = lo + (hi - lo) * (i + 0.5) / n
        r, g, b, _ = cmap((v - 45) / 120)
        rect(slide, x + i * seg, y, seg + 0.01, 0.28, RGBColor(int(r * 255), int(g * 255), int(b * 255)), name=f"{name}_{i}")
    for t in (60, 80, 100, 120, 140, 160):
        px = x + w * (t - lo) / (hi - lo)
        line(slide, px, y + 0.28, px, y + 0.36, color=GREY, width=1)
        text(slide, px - 0.4, y + 0.38, 0.8, 0.3, str(t), size=16, color=INK, align=PP_ALIGN.CENTER, space_after=0)
    text(slide, x, y + 0.72, w + 1.5, 0.3, "value-adjusted LCOE, EUR per MWh", size=16, color=INK, space_after=0)


def vmap(slide, img):
    picture(slide, HERE + img, MX, MY, MW, MH, name="!!map")
    colourbar(slide, MX + 0.35, MY + MH - 1.25, 3.6, "!!cb")


s = slides[8]
clear(s)
frame(s, 7, "Under today's grid most of the seabed studied cannot pay back by 2040", 2,
      "PyPSA-Eur 2040, grid frozen at today's network. LCOE from the model's cost assumptions. Own analysis.")
vmap(s, "vlcoe_frozen.png")
text(s, MX + 0.58 * MW, MY + 0.6 * MH, 0.41 * MW, 1.9,
     "In 2040 the median site needs 121 EUR/MWh to break even under today's grid. Less than 1 per cent of the "
     "seabed clears 70 EUR/MWh.", size=20)
notes(s, "This is the break-even price across the sea in 2040 with today's grid. In 2040 the median site needs 121 "
         "euros per megawatt hour to break even, and less than one per cent of the seabed clears seventy. The central "
         "Baltic is the most exposed part of the region.")

s = slides[9]
clear(s)
frame(s, 8, "Expanding the grid lets most of the Baltic seabed pay back by 2040", 3,
      "PyPSA-Eur 2040, transmission expanded at least cost. Own analysis.")
vmap(s, "vlcoe_optimal.png")
text(s, MX + 0.58 * MW, MY + 0.62 * MH, 0.41 * MW, 1.6,
     "With the grid expanded the Baltic break-even price falls by 33 EUR/MWh and Polish and Danish waters "
     "drop below 70.", size=20)
text(s, 0.5, MY + MH + 0.1, 12.3, 0.6, [[("The extra Baltic loss is congestion, and transmission removes it.  ", {}),
                                          ("Next, Markos ", {"bold": True, "color": HEAD}),
                                          ("takes this price risk into the contracting decision.  ", {}),
                                          ("Ask me about ", {"bold": True, "color": HEAD}),
                                          ("who pays under CfDs, congestion rent and the DK2 dispatch puzzle.", {})]],
     size=16, color=INK, space_after=0)
notes(s, "Now expand the transmission. Same wind, same farms, same year. The Baltic break-even price falls by 33 "
         "euros per megawatt hour, and Polish and Danish waters drop below seventy. The extra loss the Baltic "
         "suffers comes from congestion in the grid, and transmission removes it. Cannibalisation is a design "
         "outcome.\n\nHandover: my work tells you what price the market will pay a developer and how uncertain that "
         "price is. Markos takes that price risk into the contracting decision: how much of a farm's output to sell "
         "forward under a PPA and how much to leave to the market.\n\nAsk me about: who pays for the lost value under "
         "CfDs (the grid moves the exposure onto investors, from 18.5 to 33 per cent of hours); whether congestion "
         "rent of 4 to 12 billion euros a year can fund a 2.7 billion a year grid; why the dispatch model overshoots "
         "in DK2 while the regression does not.")

add_morph(S8[1], 2000)
add_morph(S8[2], 2000)
add_morph(S8[7], 2000)
prs.save(DECK)
print("saved in place:", DECK, "| slides:", len(prs.slides))
