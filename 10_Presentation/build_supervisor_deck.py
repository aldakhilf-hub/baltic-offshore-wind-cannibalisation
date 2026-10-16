#!/usr/bin/env python
"""Builds the supervisor presentation: minimal slides (title + a few points + one
figure), with speaker notes written as a full first-principles script. RQ-led
structure. Run with the pypsa-eur env python (has python-pptx + PIL)."""
from pathlib import Path
import os
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from PIL import Image

ROOT = str(Path(__file__).resolve().parents[1])
FIG = ROOT + "/9_Thesis_LaTeX/figures"
DECK_FIG = ROOT + "/10_Presentation/figures"      # newer presentation figures live here
OUT = ROOT + "/10_Presentation/Supervisor_presentation.pptx"

def figpath(fig):
    """Resolve a figure name against the deck-figures dir first, then the thesis dir."""
    for d in (DECK_FIG, FIG):
        p = os.path.join(d, fig)
        if os.path.exists(p):
            return p
    return os.path.join(FIG, fig)

NAVY = RGBColor(0x14, 0x29, 0x3D)
INK  = RGBColor(0x22, 0x2B, 0x33)
BLUE = RGBColor(0x2E, 0x6E, 0x9E)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
BAND = RGBColor(0xEC, 0xF1, 0xF6)   # light row banding

prs = Presentation()
prs.slide_width = Inches(13.333)
prs.slide_height = Inches(7.5)
BLANK = prs.slide_layouts[6]

# Running record of (title, bullets, table, note) so the .txt script stays in sync.
SCRIPT = []

def title_box(slide, text):
    tb = slide.shapes.add_textbox(Inches(0.55), Inches(0.28), Inches(12.2), Inches(1.0))
    tf = tb.text_frame; tf.word_wrap = True
    p = tf.paragraphs[0]; r = p.add_run(); r.text = text
    r.font.size = Pt(29); r.font.bold = True; r.font.color.rgb = NAVY
    r.font.name = "Calibri"
    return tb

def bullets_box(slide, bullets, x, y, w, h, size):
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame; tf.word_wrap = True
    for i, b in enumerate(bullets):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.space_after = Pt(10)
        r = p.add_run(); r.text = "•  " + b
        r.font.size = Pt(size); r.font.color.rgb = INK; r.font.name = "Calibri"
    return tb

def add_figure(slide, path, top, max_w, max_h):
    iw, ih = Image.open(path).size
    ar = iw / ih
    box_ar = max_w / max_h
    if ar >= box_ar:
        w = max_w; h = max_w / ar
    else:
        h = max_h; w = max_h * ar
    x = (13.333 - w) / 2
    slide.shapes.add_picture(path, Inches(x), Inches(top), Inches(w), Inches(h))

def notes(slide, text):
    slide.notes_slide.notes_text_frame.text = text

def text_slide(title, bullets, note, size=22):
    s = prs.slides.add_slide(BLANK)
    title_box(s, title)
    bullets_box(s, bullets, 0.85, 1.65, 11.6, 5.2, size)
    notes(s, note)
    SCRIPT.append((title, bullets, None, note))
    return s

def figure_slide(title, bullets, fig, note):
    s = prs.slides.add_slide(BLANK)
    title_box(s, title)
    if bullets:
        bullets_box(s, bullets, 0.65, 1.2, 12.0, 1.15, 16)
        add_figure(s, figpath(fig), 2.5, 9.4, 4.6)
    else:
        add_figure(s, figpath(fig), 1.4, 10.0, 5.6)
    notes(s, note)
    SCRIPT.append((title, bullets, None, note))
    return s

def _style_cell(cell, text, fill, color, bold, size, align):
    cell.fill.solid(); cell.fill.fore_color.rgb = fill
    cell.vertical_anchor = MSO_ANCHOR.MIDDLE
    cell.margin_top = Pt(2); cell.margin_bottom = Pt(2)
    cell.margin_left = Pt(7); cell.margin_right = Pt(7)
    tf = cell.text_frame; tf.word_wrap = True
    p = tf.paragraphs[0]; p.alignment = align
    r = p.add_run(); r.text = text
    r.font.size = Pt(size); r.font.bold = bold
    r.font.color.rgb = color; r.font.name = "Calibri"

def table_slide(title, lead, headers, data, footnote, note):
    s = prs.slides.add_slide(BLANK)
    title_box(s, title)
    if lead:
        bullets_box(s, lead, 0.85, 1.45, 11.6, 1.1, 17)
    ncols, nrows = len(headers), len(data) + 1
    tw = 11.0; x = (13.333 - tw) / 2; top = 2.85
    gfx = s.shapes.add_table(nrows, ncols, Inches(x), Inches(top), Inches(tw), Inches(0.62 * nrows))
    tbl = gfx.table
    tbl.first_row = False; tbl.horz_banding = False
    tbl.columns[0].width = Inches(5.9)
    for c in range(1, ncols):
        tbl.columns[c].width = Inches((tw - 5.9) / (ncols - 1))
    for c, h in enumerate(headers):
        _style_cell(tbl.cell(0, c), h, NAVY, WHITE, True, 18,
                    PP_ALIGN.LEFT if c == 0 else PP_ALIGN.CENTER)
    for ri, row in enumerate(data, start=1):
        fill = WHITE if ri % 2 else BAND
        for c, val in enumerate(row):
            _style_cell(tbl.cell(ri, c), str(val), fill, INK, False, 18,
                        PP_ALIGN.LEFT if c == 0 else PP_ALIGN.CENTER)
    for ri in range(nrows):
        tbl.rows[ri].height = Inches(0.62)
    if footnote:
        fb = s.shapes.add_textbox(Inches(x), Inches(top + 0.62 * nrows + 0.12), Inches(tw), Inches(0.8))
        ftf = fb.text_frame; ftf.word_wrap = True
        fp = ftf.paragraphs[0]; fr = fp.add_run(); fr.text = footnote
        fr.font.size = Pt(13); fr.font.italic = True
        fr.font.color.rgb = BLUE; fr.font.name = "Calibri"
    notes(s, note)
    SCRIPT.append((title, lead, (headers, data, footnote), note))
    return s

# ============================================================ SLIDES
# 1 TITLE
s = prs.slides.add_slide(BLANK)
tb = s.shapes.add_textbox(Inches(0.8), Inches(2.4), Inches(11.7), Inches(2.2))
tf = tb.text_frame; tf.word_wrap = True
p = tf.paragraphs[0]; r = p.add_run()
r.text = "The Market Value of Offshore Wind:\nThe North Sea and the Baltic to 2040"
r.font.size = Pt(34); r.font.bold = True; r.font.color.rgb = NAVY; r.font.name = "Calibri"
p2 = tf.add_paragraph(); p2.space_before = Pt(18)
r2 = p2.add_run(); r2.text = "Faisal Al-Dakhil   ·   MSc Thesis   ·   Supervisor presentation"
r2.font.size = Pt(18); r2.font.color.rgb = BLUE; r2.font.name = "Calibri"
_t1 = (
"Good morning, and thank you for the time. This is my thesis on the market value of offshore "
"wind: how it differs between the open North Sea and the enclosed Baltic, and what happens to "
"it as the offshore buildout moves east toward 2040. I will start with the three research "
"questions, because everything maps back to them. Then I will build the method from first "
"principles, state the assumptions, and present the results, describing each figure and tying "
"it back to the questions. It runs about twenty minutes, and please stop me at any point.")
notes(s, _t1)
SCRIPT.append(("The Market Value of Offshore Wind: The North Sea and the Baltic to 2040",
               [], None, _t1))

# 2 RESEARCH QUESTIONS
text_slide("Research questions",
 ["RQ1. How does Baltic offshore value compare with the North Sea today, and how does it evolve under the buildout to 2030 and 2040?",
  "RQ2. Which market mechanisms set how fast value erodes, and do they differ between an enclosed and an open basin?",
  "RQ3. Can a model trained on history project these futures, or is a system model needed, and how should the two combine?"],
"Three questions frame the whole thesis. RQ1 is the core comparison: how does the market value "
"of offshore wind in the Baltic compare with the North Sea today, and how does it evolve as the "
"planned buildout proceeds to 2030 and 2040. RQ2 asks why: which market mechanisms determine how "
"fast capture value erodes, and crucially whether they differ between an enclosed sea like the "
"Baltic and an open one like the North Sea. RQ3 is methodological: can an empirical model "
"anchored on historical data credibly project these futures, or do we need a physical system "
"model, and how should the two be combined. I will answer each explicitly at the end. The "
"objective throughout is to do this on open, reproducible data, which neither of the two "
"predecessor theses, both reliant on confidential commercial Aurora data, were able to do.", size=20)

# 3 THE PUZZLE
text_slide("The puzzle: theory expects the Baltic to be favourable",
 ["A wind farm earns the price in the hours it generates, not the average",
  "When wind blows, all farms flood the market together and depress that price",
  "Capture value = the fraction of the average price a farm actually earns",
  "Theory (hydro premium, low buildout) says the Baltic should hold value better"],
"Let me start from first principles, because the whole thesis turns on one idea. A wind farm "
"does not earn the average electricity price. It earns the price in the specific hours it "
"generates. And because wind is correlated across a region, when it is windy for one farm it is "
"windy for all of them, so they pour power into the market at the same time and push the price "
"down in exactly those hours. The fraction of the average price a farm actually captures is its "
"capture value: 1.0 means it earns the average, and below 1 means its own output is depressing "
"its price. That erosion is called cannibalisation, and it deepens as more wind is built. Now, "
"the textbook expectation, from Hirth, is that the Baltic should be the favourable basin: it "
"sits next to Nordic hydro that can store surplus and smooth prices, and it has almost no "
"offshore built yet, so little self-cannibalisation. The thesis tests whether that holds.")

# 4 CAPTURE VALUE
figure_slide("Capture value is the number that matters",
 ["Revenue per MW = capacity factor × price level × capture value",
  "Capacity factor flat over time; price level shared; only capture value diverges"],
 "fig_revenue_decomp.png",
"This figure makes capture value concrete and shows why it, and not the headline price, is the "
"right thing to study. Revenue per megawatt is capacity factor times the price level times "
"capture value. The left panel shows the capacity factor is essentially flat over time. The "
"middle panel is the price level, which is dominated by the 2022 gas-crisis spike and is shared "
"by both basins. Only the right panel, capture value, drifts structurally down, and the Baltic "
"basin average drifts further than the North Sea. So the revenue story lives entirely in capture "
"value. Formally it is the generation-weighted price divided by the time-average price, and it is "
"the single common currency that lets me put the two models and the observed record on one axis. "
"Concretely, on the historical side I measure it monthly for each of the 31 study farms, sixteen "
"in the North Sea and fifteen in the Baltic, by weighting each zone's observed day-ahead prices by "
"that farm's validated virtual-farm output, which is the construction I show on the next slide.")

# 5 SCOPE AND GROUPING
text_slide("Scope: three groups of bidding zones",
 ["Unit = the bidding zone (the area where one price is set)",
  "North Sea (open): DE, NL, BE, Danish DK1, FR",
  "Baltic under-built: Poland, Estonia, Latvia, Lithuania",
  "Baltic built-out (the preview): Danish DK2, Swedish SE4",
  "Excluded: Finland (nuclear collapse), GB (Brexit), Norway (hydro)"],
"This slide is central, so let me be precise about how the comparison is organised. The unit of "
"analysis is the bidding zone, the area within which a single electricity price is set each hour. "
"I sort the zones into three groups. The North Sea is the open, mature reference: Germany, the "
"Netherlands, Belgium, Danish zone DK1, and France. The Baltic then splits by how far each zone "
"has travelled down its buildout. The under-built zones, Poland, Estonia, Latvia, Lithuania, "
"have their offshore pipeline still to come. The built-out zones, Danish DK2 and Swedish SE4, "
"already have offshore in the water, so they are the present-day preview of where the buildout "
"leads. Finland is excluded, set aside from the Baltic averages, "
"because its low capture value comes from a nuclear price collapse when the Olkiluoto-3 reactor "
"started in 2023, not from wind cannibalisation, so including it would distort the picture. Two "
"zones are excluded entirely: Great Britain, whose prices decoupled from the continent after "
"Brexit, and Norway, which is hydro-dominated and which the system model does not price well. "
"This grouping is a space-for-time device, and it is also what removes the earlier over-reliance "
"on any single zone: the built-out zones are simply the future of the under-built ones.")

# 6 THE DESIGN
text_slide("The design: two instruments, one validation",
 ["Regression: measures the past, where data is dense",
  "PyPSA system model: projects the future, where there is no data",
  "The validation triangle: checks both agree where reality can be observed",
  "A deliberate division of labour (this is RQ3)"],
"The design answers RQ3 directly, so I will set it up now. I need two different things. I need to "
"measure value where it has actually happened, the past, where there is data. And I need to "
"project it where it has not, in 2030 and 2040, where there is none. No single method does both "
"well. A statistical model learns patterns from history but cannot be trusted outside the range "
"of conditions it has seen. A physical system model can simulate any future, but it is an "
"approximation that has to be checked against reality before it is believed. So I use two "
"instruments: an empirical regression that measures the past and explains the mechanism, and "
"PyPSA, a power-system model, that carries the future. And a third step, the validation triangle, checks that in the recent "
"past, where both can be evaluated, they agree with each other and with the observed record. "
"This is a deliberate division of labour, not redundancy, and I will show that the regression "
"provably cannot extrapolate, which is exactly why the system model has to carry the future.")

# 7 VWF
figure_slide("The data: a virtual wind farm from weather",
 ["ERA5 wind → hub height → power curve → hourly output, for every zone",
  "Validated against metered generation: r = 0.88 hourly, 0.95 monthly"],
 "fig_vwf_vs_observed.png",
"Both instruments need a consistent hourly generation profile for an offshore farm in every "
"zone, including zones that have no farm yet, and built only from open data. I build it from "
"weather. I take ERA5 reanalysis wind speeds, which are a physically consistent reconstruction "
"of past weather, at 10 and 100 metres for each farm's grid cell. I extrapolate those to the "
"150-metre hub height of a modern offshore turbine using a logarithmic wind profile. Then I "
"convert wind speed to electrical output with the IEA 15-megawatt reference turbine power curve, "
"adjusted by the Hayes method, a smoothing and a shift that together stand in for wake losses "
"inside a farm and the spread of many turbines. The output is an hourly capacity factor for each "
"site. This figure validates it: where real offshore farms exist, the virtual farm's monthly "
"output, in red, tracks the metered output, in black, closely. The hourly correlation is 0.88 "
"and the monthly 0.95. Neither predecessor validated this step, and it is what lets me price a "
"realistic farm in a zone that has prices but no turbines yet.")

# 8 REGRESSION
figure_slide("Instrument 1: the regression, trained and tested blind",
 ["Input: the 7 market features for one farm-month  →  output: that farm-month's capture value",
  "Scored leave-farm-out: every prediction is for a farm the model never trained on (R² 0.69; every enclosed Baltic zone predicted blind)"],
 "fig_F_leverC_before_after.png",
"The empirical instrument is a regression, and let me be exact about what it learns. The training "
"unit is one farm-month. The input is seven features describing that farm in that month; the output, "
"the single number it predicts, is that farm-month's capture value. The seven features are how "
"correlated the farm's output is with the rest of the system's "
"wind, with demand, the renewable share of the market, the gas and carbon prices that set the "
"thermal backdrop, storage flexibility, and interconnection. I train five algorithms and "
"gradient boosting wins. The validation is the important part: I test it out-of-fold, meaning I "
"split the farms into groups, train on some, and predict the others completely blind, so the "
"score measures how it does on farms it never saw, which is 0.69. The recent upgrade, which this "
"figure quantifies, is that capture value is a property of prices, and prices exist for every "
"Baltic zone, so I price the same validated virtual farm in all seven enclosed Baltic zones, not "
"just the one with an operational farm. In the figure, each pair of bars is one validation test: "
"the left bar uses country-level features, the right uses zone-level, and the bar height is the "
"out-of-fold R-squared; resolving to the zone lifts every one. And the decisive test: the model predicts six of the seven Baltic zones "
"blind, within 0.07; only Finland misses, and correctly, because its low value is nuclear, not a "
"wind-market feature. And the strongest cross-check: a model trained only on the North Sea, never "
"shown a Baltic farm, still transfers to the Baltic with an R-squared of about 0.38. So the model "
"is general, not memorising one zone.")

# 8b INSIDE THE REGRESSION (parallel to inside PyPSA)
figure_slide("Inside the regression: inputs, the model, and how it projects",
 None,
 "fig_regression_pipeline.png",
"This is the empirical instrument opened up, the mirror of the PyPSA box. On the left are the inputs, "
"seven market features for each farm-month, built from the virtual wind farm and the ENTSO-E market "
"data: how crowded the farm is, its correlation with the rest of the system's wind, its correlation "
"with demand, the renewable market share, the gas and carbon prices, and the buffering from "
"flexibility and interconnection. In the middle is the model, gradient boosting, the winner of the "
"five-algorithm comparison: four hundred shallow trees, each fitting the error the ensemble still "
"makes, summed into the prediction, which captures the nonlinear feature interactions without being "
"told them; trained on operational farms and scored leave-farm-out, so every number is for a farm it "
"never saw. Out the right comes the capture value, by the same formula as PyPSA and the observations, "
"validated blind at R-squared 0.69. The bottom band is the honest part, how it projects: the tree "
"abstains, because every future leaves its training range, so it returns its boundary value and "
"flat-lines at about 0.82; Jacquet's analytical closed form does extrapolate, but penetration enters "
"it linearly, so it projects only a gentle decline, to 0.79 and 0.72; and because that sits above "
"PyPSA's 0.57 and 0.47, the gap being exactly the convex collapse the linear form cannot see, PyPSA "
"carries the 2040 headline while the regression measures the present and the mechanism.")

# 9 PYPSA
text_slide("Instrument 2: PyPSA, the power-system model",
 ["Open model: grid, generators, storage, demand, solved hourly",
  "14 countries, ~30 nodes, frozen 2020 grid, year-correct fleets",
  "Wholesale price = the hourly shadow price at each node",
  "Future built from official TYNDP 2030/2040 scenarios"],
"The system instrument is PyPSA-Eur, an open-source model of the European power system. It "
"represents the transmission grid, every generator and its cost, storage, and demand, and it "
"solves a least-cost optimisation: meet every hour's demand at the lowest cost subject to "
"physics, line limits and generator capacities. The hourly shadow price at each node, the cost "
"of supplying one more megawatt-hour there, is the model's wholesale price, and from prices and "
"generation I compute capture value exactly as before. The build chain runs through a workflow "
"tool called snakemake: it extracts the grid, builds a weather year from ERA5, computes "
"renewable profiles, clusters the network to about thirty nodes so it solves in reasonable time, "
"adds the year-correct fleet, and solves all 8,760 hours of the year with a commercial solver. "
"It covers fourteen countries. The grid is deliberately frozen at its 2020 state, because the "
"question is what today's grid does under tomorrow's fleet, and I bracket that assumption later. "
"For the future I overlay the official European grid-planning scenarios, the TYNDP, for 2030 and "
"2040, with a set of documented corrections, and re-solve. I keep the grid frozen for the headline "
"and then test, on the robustness slide, whether expanding it is the mitigating factor.")

# 9b PYPSA PIPELINE (inputs -> equations -> outputs, and why it differs from the regression)
figure_slide("Inside PyPSA: inputs, the dispatch it solves, and the outputs",
 None,
 "fig_pypsa_pipeline.png",
"This slide opens the box. On the left are the inputs I supply: the grid as about thirty nodes "
"with line limits, the full fleet by carrier which is the energy mix, the ERA5 weather that sets "
"each wind and solar plant's hourly availability, the hourly demand, and the fuel and carbon "
"prices that fix every plant's marginal cost. In the middle is what the solver actually does: it "
"minimises total system cost over all 8,760 hours subject to four constraints, and the one that "
"matters is supply equals demand at every node and hour, whose shadow price is the wholesale "
"price. In a windy hour zero-cost wind is marginal and the price falls toward zero; in a still "
"hour gas sets it. Out the right come the hourly prices and generation, and from them the capture "
"value, by the same formula as observed. The bottom band is the punchline for the supervisor's "
"question: PyPSA and the regression compute the same capture-value formula but get the price from "
"different places. The regression has no grid and penetration enters it linearly, so it cannot see "
"congestion or the convex collapse; that is exactly why the two diverge in the Baltic, and why "
"relaxing the grid moves PyPSA from 0.47 to 0.66 while the residual gap to the regression's 0.77 "
"is the collapse only the market-clearing model finds.")

# 11 TRIANGLE
figure_slide("The validation triangle",
 ["Three independent estimates: observed, PyPSA, regression (blind)",
  "The blind regression lands within 0.014 of observed; PyPSA's congestion bias shows in DK1 and DK2"],
 "fig_validation_triangle_2023.png",
"This is the validation crescendo and part of the answer to RQ3. It puts three independent "
"estimates of the same quantity side by side for each zone: the observed capture value from real "
"generation and prices, PyPSA's value from the simulation, and the regression's value, predicted "
"blind, having never trained on that zone's farms. The strict test is the regression, and it lands "
"within 0.014 of the observed value in every zone in 2023, and within 0.025 across all three "
"years; that is the agreement that matters, because it was predicted blind, by a route entirely "
"independent of PyPSA. PyPSA matches the uncongested open zones almost exactly, Germany and the "
"Netherlands within a few thousandths, but it carries its congestion bias on the constrained "
"zones, growing with congestion and largest at DK2 at about 0.14, with DK1 in between. So where "
"the three diverge, it is the system model on the congested zones, by the very mechanism the "
"calibration measured and the projection corrects. No predecessor confronted a statistical and a "
"physical model against observation like this; it is one of the contributions of the work.")

# 13 RQ1 RESULT: heat maps, today -> 2040
figure_slide("RQ1: the market value of offshore wind today",
 None, "fig_heatmap_2025.png",
"This is the direct answer to RQ1, shown as a map. Each zone's offshore sea area is shaded by its "
"capture value, the share of the average price an offshore farm earns. Today the whole map is "
"green: the under-built Baltic, Poland and the Baltic states, sits at 0.85 to 0.92, level with the "
"North Sea's 0.85 to 0.90. So the Baltic does not start behind. "
"Finland is excluded throughout as a nuclear-driven outlier.")

figure_slide("RQ1: by 2030 the Baltic begins to fade",
 None, "fig_heatmap_2030.png",
"By 2030 the first build-out has landed. The North Sea and the under-built Baltic are still mostly "
"green, in the high 0.7s to 0.8s, but the Baltic zones are starting to fade as their own correlated "
"wind begins to crowd their price. Estonia is grey here because it has no offshore in the water yet "
"at this horizon.")

figure_slide("RQ1: by 2040 the Baltic erodes well past the North Sea",
 ["At parity today (~0.89); by 2040 the Baltic falls to about 0.47, the North Sea holds about 0.57"],
 "fig_heatmap_2040.png",
"By 2040 the map has split. The Baltic has turned red-orange, Poland 0.49, Latvia 0.42, Estonia "
"0.39, while the North Sea holds amber, Germany 0.59, the Netherlands 0.57, about 0.57 as a basin. "
"So the basin that began at parity ends in a clear discount: the Baltic loses roughly 47 percent of "
"its value, the North Sea about 35 percent. The build-out, not the starting point, is what does it. "
"Why the Baltic falls faster is the mechanism section that follows; whether building the grid "
"changes the answer is two slides on, and the answer there is the surprising part.")

# 13b THE BUILD-OUT BEHIND IT (energy mix)
figure_slide("The build-out behind the result: the full energy mix",
 None, "fig_energy_mix.png",
"Before the mechanism, the build-out that produces this, because the natural question is whether it "
"is realistic. These are the installed fleets, the full energy mix, North Sea and Baltic, today and "
"to 2040. The North Sea offshore grows from about 19 to 165 gigawatt; the Baltic Sea from under 3 to "
"about 50, of which the enclosed Baltic states make up nothing today rising to about 25, a quarter of "
"regional demand. And note that this is the complete mix: gas and oil persist "
"at about 80 and 9 gigawatt right through 2040, nuclear and hydro stay, only German and Polish coal "
"winds down. So the fossil backbone does not disappear, it is still there setting the price in the "
"low-wind hours, which is exactly the mechanism that makes capture value fall.")

# 15 RQ1: THE GRID REVERSAL
figure_slide("Does the Baltic still erode faster if we build the grid? No, it reverses",
 ["Frozen grid (today's): the Baltic erodes faster, 2040 Baltic 0.47 vs North Sea 0.57",
  "Cost-optimal grid: the ordering REVERSES, Baltic 0.66, above the North Sea 0.64",
  "So the Baltic's faster erosion is a grid story: open the export valve and its advantage returns",
  "Interconnection is the single highest-leverage lever on Baltic value"],
 "fig_grid_reversal.png",
"This is the slide that reframes the whole result. The obvious objection is the frozen grid: surely "
"fifteen years of new transmission would change the answer. So I tested it directly. I removed the "
"volume limit on the grid, let the model build the cost-optimal amount of new transmission paying "
"its capital cost, and re-solved. The solid lines are today's frozen grid: the Baltic, in red, "
"erodes faster than the North Sea, ending 2040 at about 0.47 against 0.57. The dashed lines are the "
"optimal grid, and they cross: the Baltic recovers to about 0.66, above the North Sea's 0.64. Every "
"Baltic zone recovers, Poland from 0.49 to 0.74. So the answer to whether the "
"Baltic still erodes faster with an optimal grid is no, the opposite. The Baltic's faster erosion is "
"entirely a frozen-grid effect: it is an enclosed sea with a weak export valve, so when its "
"correlated wind floods the market the surplus cannot escape and the price collapses. Build the "
"transmission and the Baltic's real advantage returns, less of its own buildout and the Nordic hydro "
"next door, which is exactly what the offshore community expects of the Baltic. The North Sea, with "
"177 gigawatt of its own offshore, keeps cannibalising either way. One honest detail: at 2030, at "
"low penetration, the optimal grid is marginally below frozen, because more interconnection mostly "
"adds price competition until congestion actually binds; it only becomes a help at the high 2040 "
"buildout. The policy headline is that interconnection is the highest-leverage lever there is, "
"ahead of any market mechanism.")

# 15c CONGESTION vs ENCLOSURE DECOMPOSITION (his ask: why is CV falling, congestion or closed)
figure_slide("Congestion or enclosure? Decomposing the Baltic's fall",
 ["Each basin's 2040 fall split in two: structural buildout (the grid cannot fix) and congestion (an optimal grid removes)",
  "Both start at parity ~0.89; on the frozen grid the Baltic falls to 0.47, the North Sea to 0.57",
  "The Baltic's congestion penalty (0.19) is 3x the North Sea's (0.06); its structural fall is SMALLER (0.22 vs 0.25)",
  "So the enclosure shows up as congestion the grid removes, not a permanent penalty: build it and the Baltic ends ABOVE the North Sea"],
 "fig_cv_decomposition.png",
"Decomposition answering the congestion-versus-enclosure question directly. Each basin's fall from "
"parity is split into a structural buildout part, the cannibalisation that survives "
"an optimal grid, and a congestion part, the value an optimal grid recovers. The North Sea is 80 "
"percent structural and only 20 percent congestion. The Baltic is the opposite balance: "
"its congestion penalty is three times the North Sea's, while its structural fall is actually "
"smaller. So the enclosure does not act as an intrinsic penalty; it acts as congestion, because a "
"flooded enclosed basin cannot export its surplus on a frozen grid. Build the grid and that part "
"is removed, which is why the Baltic ends above the North Sea.")

# 15 RQ2 RESULT
figure_slide("RQ2: what sets the severity, and it is steeper in the Baltic",
 ["Strip out the 2022 fuel-crisis signal and crowding leads (32%); carbon and gas are a time artefact, not a farm-to-farm driver",
  "Same mechanisms in both basins, but steeper in the enclosed Baltic: the same buildout cannibalises about twice as hard"],
 "fig_shap_demeaned.png",
"RQ2 asks which mechanisms set the severity and whether they differ between basins. The honest way "
"to ask it is cross-sectional: why does one farm earn less than another in the same month. Two of "
"the seven features cannot answer that, because carbon and gas are Europe-wide monthly prices, "
"identical across every zone, so they carry no information about why zones differ. Their apparent "
"weight in the raw data is just the 2022 fuel crisis, a signal shared by everyone. This figure "
"removes that shared time signal: the grey bars are the raw ranking, where carbon leads at 29 "
"percent; the red bars are the cross-sectional ranking, and carbon collapses to 4 percent while "
"crowding, a farm's correlation with the rest of the system's wind, rises to the front at 32 "
"percent, with the buffering features, interconnection and flexibility, carrying nearly as much. "
"So the thing that decides which farm cannibalises hardest is crowding behind a weak export valve, "
"exactly the enclosure story. Now whether the basins differ: I fit the analytical cannibalisation "
"equation to each basin, and the pattern-penalty exponent is 0.74 for the Baltic against 0.37 for "
"the North Sea, so the same buildout cannibalises harder in the enclosed basin. The mechanisms are "
"shared; the Baltic's are steeper. A word on the equation's constants, since I may be asked. The "
"pattern-penalty exponent, the 0.74 against 0.37, is the headline: it sets how sharply the penalty "
"escalates as a farm's wind lines up with the system's. Two others matter. The cannibalisation "
"scale, B, is the overall strength of the effect: it multiplies the whole crowding-times-"
"penetration term, so a larger B means a given amount of crowding and penetration eats more value. "
"And delta is the buffering exponent: the penalty is divided by interconnection plus flexibility "
"raised to delta, so delta sets how strongly those escape valves cushion the erosion, a larger "
"delta meaning more protection per unit of interconnection and storage. I do not lean on any single "
"constant, because they trade off inside the shared terms; I compare the basins by what they "
"jointly produce, the implied slope of capture value against penetration, which is steeper in the "
"Baltic on both the exponent and that combined slope.")

# 16 RQ2: enclosed-basin correlation
figure_slide("RQ2: the enclosed basin blows together",
 ["Under-built Baltic states correlate at 0.61; the North Sea at 0.44; the two basins decouple (0.28)",
  "As those zones build out, their correlated wind floods the enclosed market together, the congestion the grid relieves"],
 "fig_basin_correlation.png",
"This figure is the geographic root of why the Baltic is steeper, and it gives the why behind "
"RQ2. It is built the way Jacquet built his: on the left, every cell is the correlation of two "
"farms' hourly output, with no prices and no market labels, and the farms are reordered by "
"clustering so co-varying farms fall into the small numbered boxes down the diagonal; on the "
"right, those same numbered clusters are circled on the map, so the statistical blocks are tied to "
"real geography. Read it like this: the North Sea farms spread across several looser clusters, "
"correlating at 0.44 on average, a diverse fleet; the Baltic farms collapse into a few tight, dark "
"clusters, the built-out DK2 and SE4 the tightest at 0.87 and the under-built states close behind "
"at 0.61, well above the North Sea. Crucially, those under-built zones are exactly the ones about "
"to build out. So when they do, their tightly-correlated wind will flood the enclosed market at "
"the same hours; and because the two basins are largely decoupled, at 0.28, they cannot lean on "
"the North Sea to absorb the surplus. Correlated wind behind a weak export valve is the enclosure "
"mechanism that makes the Baltic's cannibalisation steeper. The North Sea, more spatially diverse, "
"escapes it. To put the why plainly, in the model and in the world at once: the Baltic cannibalises "
"harder because its wind is more crowded, correlation with system wind being the top cross-sectional "
"driver, and its market is less buffered, weak interconnection being the second lever, so its "
"tightly-correlated output floods a small, enclosed market in the same hours and the local price "
"collapses exactly when the farm is generating most.")

# 18 RQ3 RESULT
figure_slide("RQ3: the regression abstains, so PyPSA carries the future",
 ["Every future scenario leaves the model's training range (carbon)",
  "The tree model flat-lines out of support, by proof; a time-split test fails"],
 "fig_E_carbon_flatline.png",
"RQ3 asks whether an empirical model can project these futures or whether a system model is "
"indispensable. The answer is that the regression provably cannot, and that is by design, not "
"failure. This figure plots the model's predicted capture value against carbon price, with the "
"training range shaded. Every future scenario sits to the right of that shaded band, beyond the "
"training range, and the tree model simply flat-lines there: you can see the line go flat to the "
"right of the shaded band, because a tree returns its boundary value and cannot extrapolate. A "
"separate time-split test, training through 2022 and predicting 2023 to 2024, gives a negative "
"R-squared of about minus 0.03, so it also fails. So the regression formally abstains from the projection, "
"and PyPSA carries it, with the triangle proving the hand-off is sound. This division of labour, "
"with a measurable, proven abstention rather than an assumed one, is itself a methodological "
"contribution and the answer to RQ3: you need both, combined this way.")

# 18b RQ3: capture-value evolution, every instrument on one chart
figure_slide("Capture value to 2040: every instrument on one chart",
 ["PyPSA frozen finds the convex collapse (North Sea 0.57, Baltic 0.47); the optimal grid recovers it (0.64, 0.66)",
  "The regression cannot see it: the tree abstains (flat ~0.82), the analytical form projects only gently (0.79, 0.72)",
  "That 2040 gap IS the convex cannibalisation the linear empirical form misses, so PyPSA carries the headline",
  "Agree to 2030 (trust either); part at 2040 (only the market-clearing model is right)"],
 "fig_capture_value_evolution.png",
"This puts every instrument on one chart, North Sea left, Baltic right, so the hand-off is visible. "
"The two PyPSA lines are the headline: the frozen grid finds the convex cannibalisation collapse, the "
"North Sea to 0.57 and the Baltic to 0.47, and the optimal grid recovers it to 0.64 and 0.66. The two "
"regression lines stay high: the gradient-boosting tree abstains, flat-lining at about 0.82 because it "
"cannot leave its training range, and Jacquet's analytical closed form projects only a gentle decline "
"to 0.79 and 0.72, because penetration enters it linearly, so it subtracts a proportional penalty but "
"has no term for the windy-hour price crash. The vertical gap at 2040, about 0.22 in the North Sea and "
"0.25 in the Baltic, is exactly that convex collapse the empirical form cannot see. So the RQ3 rule is "
"visible: to 2030, where the instruments agree, trust either; at 2040, where they part, only the model "
"that clears the market hour by hour finds the real floor, which is why PyPSA carries the headline.")

# ============================================================ PART 4: THE ECONOMICS
# E1 does it pay? net value
figure_slide("Does offshore wind pay? From capture value to net value",
 ["Net value per MW = revenue (resource x capture value x price) minus depth- and distance-driven cost",
  "2025: ~48% of the shelf is merchant-profitable (green); by 2040 cannibalisation shrinks it to ~12% even as turbines get cheaper",
  "WHY it shrinks: cannibalisation erodes the captured price faster than cheaper turbines cut cost",
  "WHY the green is the shallow North Sea: best wind + shallow + near-shore stack the most cost margin; deep water never clears the floating-foundation cost"],
 "fig_netvalue_2040.png",
"Capture value is not the whole story; what matters to an investor is whether it pays. Net value "
"per megawatt is revenue, resource times capture value times price, minus cost, which rises with "
"water depth and distance to shore, built from the Global Wind Atlas and GEBCO bathymetry. In 2025 "
"about 48 percent of the buildable shelf is merchant-profitable, the green, shallow windy areas like "
"the German Bight. By 2040, even though turbines get cheaper, cannibalisation shrinks that profitable "
"area to about 12 percent. The buildable sea is shrinking, not because building gets dearer but "
"because the market eats the price.")

# E2 the value-adjusted LCOE (the novelty)
figure_slide("A new metric: the value-adjusted LCOE (cannibalisation undoes the learning)",
 ["Value-adjusted LCOE = LCOE / capture value = the wholesale price a site needs to break even",
  "Raw LCOE FALLS with technology (74 to 66 EUR/MWh); the value-adjusted LCOE RISES (87 to 121), because cannibalisation overruns learning",
  "Robust: costs would have to fall 36% by 2040 (3x the DEA's 12%) just to hold it flat, in all 27 cases tested"],
 "fig_vlcoe_2040.png",
"This is the methodological contribution. Levelised cost, the field's default yardstick, is blind "
"to the fact that offshore wind earns less than the average price, and increasingly so. So I fold "
"capture value into it: the value-adjusted LCOE is the ordinary LCOE divided by capture value, the "
"wholesale price a site actually needs to break even. The result is the headline, and it is "
"counterintuitive: the raw LCOE falls with technology, 74 to 66 euros, but the value-adjusted LCOE "
"rises, 87 to 121, because cannibalisation erodes the value of each megawatt-hour faster than "
"learning cuts its cost. The cannibalisation undoes the learning. And it is robust, I swept cost, "
"discount rate and learning rate, and it rises in all 27 cases; costs would have to fall 36 percent "
"by 2040, three times the projected twelve, just to hold it flat. No one has mapped this spatially.")

# E3 interconnection, in money
figure_slide("Interconnection is the lever, in money",
 ["Interconnection lowers the enclosed Baltic's value-adjusted LCOE by EUR 33/MWh, 4x the core North Sea's EUR 8",
  "Worth ~EUR 1.2 bn/yr in captured revenue to Baltic offshore alone, about 55% of the cost of ALL the new lines",
  "The recommendation: the cost-optimal grid makes Baltic offshore viable; without it, it needs subsidy"],
 "fig_vlcoe_grid_2040.png",
"And this ties the whole thesis into one number. Because the value-adjusted LCOE is LCOE over "
"capture value, and interconnection raises capture value, interconnection lowers the break-even "
"price. It lowers the enclosed Baltic's value-adjusted LCOE by 33 euros per megawatt-hour, four "
"times the core North Sea's eight, because the enclosed Baltic is where the cannibalisation it "
"relieves is concentrated. In money that uplift is worth about 1.3 billion euros a year to Baltic "
"offshore alone, roughly 55 percent of the cost of all the new transmission across fourteen "
"countries. The optimal grid is not an open cost problem, the model builds a specific cost-optimal "
"amount, 133 gigawatt of new lines at 2.2 billion a year, and stops. So the recommendation is sharp: "
"build the grid; it makes Baltic offshore viable, and it is a break-even reduction aimed exactly at "
"the basin with the problem.")

# E4 site ranking: does capture value change the ranking? (objective 4)
figure_slide("Does capture value change where to build?",
 ["Rank candidate areas by cost alone (LCOE) versus with capture value added (value-adjusted LCOE)",
  "2025 the two rankings agree (0.99); by 2040 they diverge (0.90), so the value dimension increasingly reorders site choice",
  "The cheap-but-cannibalised eastern Baltic (Estonia, Latvia) drops; the value-resilient Danish North Sea rises; the German Bight stays number one",
  "So ranking on cost alone is fine today but increasingly misleads toward 2040"],
 "fig_site_ranking.png",
"This answers the fourth objective directly: does folding capture value into the assessment change "
"which sites you would build. I rank ten candidate development areas two ways, on levelised cost "
"alone, the standard spatial metric, and on the value-adjusted LCOE that adds capture value. In 2025 "
"the two rankings are almost identical, a rank correlation of 0.99, because capture value is near "
"parity everywhere, so adding it changes nothing. By 2040 they pull apart to 0.90, and the movers "
"tell the story: the shallow, cheap-to-build eastern Baltic, Estonia and Latvia, look attractive on "
"cost but their capture value has collapsed, so they drop two places; the expensive deep-water Danish "
"North Sea, whose value holds, rises. The German Bight stays first throughout, strongest on both. So "
"the practical message is that ranking sites on cost alone is harmless today but increasingly "
"misleads as the buildout proceeds, which is exactly the case for the value-adjusted metric.")

# E5 two-metric site ranking + recommendation
figure_slide("Where to build: many sites, two lenses",
 ["169 candidate sites across both shelves, ranked two ways: cheapest break-even (value for money) and largest profit per MW (net value)",
  "Both reward the shallow, windy, value-resilient shelf; the German Bight tops both lenses",
  "Value-for-money tilts to the cheap shallow western Baltic (Poland, DK2); absolute money tilts to the high-resource open North Sea",
  "Recommendation: German Bight and the shallow western Baltic first; the cheap eastern-Baltic sites are a value trap by 2040"],
 "fig_site_ranking_2metric.png",
"And here it is at finer resolution, from the investor's two points of view. 169 candidate sites "
"across both shelves, each ranked by the value-adjusted LCOE, the cheapest break-even price, on the "
"left, and by net value per megawatt, the largest absolute profit, on the right; green is best. The "
"two lenses agree on the big picture, the shallow, windy, value-resilient shelf wins and the German "
"Bight tops both. Where they differ is instructive: the cheapest break-even sites tilt toward the "
"shallow, low-cost western Baltic, Poland and the Danish DK2 zone, because a low build cost offsets a "
"lower capture value; the largest absolute profit tilts toward the high-resource open North Sea, "
"where stronger wind delivers more value-weighted energy. The recommendation across both is the same "
"first move, build out the German Bight and the shallow western Baltic, and the same warning, the "
"cheap eastern-Baltic sites that look good on cost are a value trap once cannibalisation lands by 2040.")

# E6 objective 5: diversification / portfolio value
figure_slide("Is it worth spreading across both basins?",
 ["Cannibalisation hedge (YES): all-North-Sea craters; spreading the optimal ~12% to the Baltic lifts aggregate 2040 capture value about a third (planned split near-optimal)",
  "Risk hedge (NO): the wind decorrelates (0.28) but capture value co-moves (0.80) on shared European prices, so no volatility cut",
  "So the portfolio payoff is on the MEAN (less cannibalisation), not the variance",
  "The low correlation that motivates diversification lives in the wind, not the value"],
 "fig_diversification.png",
"The fifth objective: is there a portfolio benefit to spreading offshore wind across both basins rather "
"than concentrating in the North Sea. Two candidate benefits, and they split cleanly. On the left, the "
"cannibalisation hedge, real and large: pour a fixed total all into the North Sea and you drive it to "
"high penetration where its capture value craters; spread the optimal twelve percent into the Baltic, "
"which starts earlier on its curve, and the portfolio's aggregate capture value rises by about a third, "
"with the actually-planned split sitting right on that optimum. On the right, the classic risk hedge, "
"and it does not hold: the textbook argument is that low correlation cuts volatility, but the low "
"correlation is in the wind, 0.28, while capture value co-moves at 0.80 because both basins ride the "
"same European gas and price signal, and the North Sea is both higher-value and lower-volatility, so a "
"mixed portfolio adds risk rather than cutting it. So the honest answer refines the premise: spreading "
"pays, but on the mean through less cannibalisation, not on the variance, because the low wind "
"correlation does not survive into capture value.")

# 17 WHAT IT MEANS
text_slide("What it means, against the three questions",
 ["RQ1: at parity today; the Baltic falls to about 0.47 by 2040 vs the North Sea's 0.57, but with grid expansion it recovers to 0.66, above the North Sea",
  "RQ2: same mechanisms, steeper in the enclosed Baltic (weak export valve, correlated wind)",
  "RQ3: regression measures and explains; PyPSA carries the far future; the triangle validates the hand-off",
  "Economics: the value-adjusted LCOE RISES despite cheaper turbines; interconnection lowers the Baltic's by EUR 33/MWh, worth ~EUR 1.2 bn/yr",
  "Policy: interconnection is THE lever, it decides whether the Baltic erodes or thrives; subsidy design must price the structural fall"],
"Pulling it together against the three questions. RQ1: the Baltic is at parity with the North Sea "
"today, and on today's grid the buildout takes it to about 0.47 by 2040, far more loss than the "
"North Sea at 0.57; but the decisive caveat is that if the grid is built out the Baltic recovers to "
"0.68, above the North Sea, so the erosion is a consequence of the grid, not of the basin. RQ2: the same mechanisms operate in both basins, but the "
"enclosed Baltic's are steeper, because its wind blows together behind a weaker export valve. RQ3: "
"no single model can do both jobs, so the regression measures the present, explains the mechanism, "
"and even forecasts through its analytical form as a cross-check, while PyPSA carries the far future "
"where the empirical form provably breaks, and the triangle validates the hand-off between them. On "
"the economics, folding capture value into the levelised cost gives the value-adjusted LCOE, and it "
"rises even as turbines get cheaper, because cannibalisation overruns the learning; interconnection "
"is the one lever that lowers it, by 33 euros per megawatt-hour in the enclosed Baltic, worth about "
"1.3 billion a year. For policy, two things follow: "
"interconnection is the highest-leverage lever, and contract-for-difference and subsidy design "
"need to price this structural decline in value, not just the crisis-era price spike. And because "
"the whole thing runs on open data, it is reproducible, which sets it apart from the two "
"predecessor theses.")

# 18 CONCLUSION
text_slide("Conclusion",
 ["The enclosed Baltic does not start behind, but on today's grid the buildout cannibalises it faster",
  "Build the grid and it reverses: the Baltic recovers above the North Sea, and the erosion is a policy choice, not fate",
  "New metric, the value-adjusted LCOE, rises despite cheaper turbines; interconnection lowers the Baltic's most (EUR 33/MWh, ~EUR 1.2 bn/yr)",
  "Contribution: two validated instruments, a proven hand-off, a value-adjusted cost map, on open data  ·  Thank you · questions"],
"To conclude. The enclosed Baltic does not start behind the North Sea, but on today's frozen grid, "
"as it builds out, it cannibalises its own wind value faster, and the already-built-out DK2 shows "
"where that curve leads. The single most important caveat is the grid: build the transmission and "
"the result reverses, the Baltic recovers above the North Sea, so this erosion is a policy choice "
"and not the basin's fate. The contribution is threefold: a validated two-instrument method, confronted by a triangle and "
"with a proven hand-off from the empirical to the physical model; a value-adjusted LCOE that maps "
"break-even cost rather than raw cost, and shows it rising even as turbines get cheaper; and the "
"finding that interconnection is the lever that lowers it most, exactly where the Baltic is "
"enclosed, all on open and reproducible "
"data. Thank you very much, and I am happy to take any questions.")

# ============================================================ SPEAKER NOTES
# Terse points to HIGHLIGHT per slide (not a script). One list per slide, in order.
# Overwrites the prose notes set during slide building. No em dashes; EUR not the symbol.
HIGHLIGHTS = [
 # 1 TITLE
 ["Thesis: market value of offshore wind, open North Sea vs enclosed Baltic, out to 2040",
  "Order: three research questions, then method from first principles, then results",
  "About 20 minutes; please interrupt at any point"],
 # 2 RESEARCH QUESTIONS
 ["RQ1: how does Baltic value compare with the North Sea today, and under the 2030/2040 buildout",
  "RQ2: which mechanisms set the erosion, and do they differ enclosed vs open",
  "RQ3: can a history-trained model project the future, or is a system model needed",
  "All on open data; both predecessor theses relied on confidential Aurora data"],
 # 3 THE PUZZLE
 ["A farm earns the price in its windy hours, not the average",
  "Correlated wind means all farms flood the market together and push that price down (cannibalisation)",
  "Capture value = fraction of the average price actually earned; below 1 = self-depressing",
  "Textbook (Hirth) expects the Baltic to hold value better (Nordic hydro, little built); we test it"],
 # 4 CAPTURE VALUE
 ["Revenue/MW = capacity factor x price level x capture value",
  "CF is flat, price level is shared (gas spike); only capture value diverges, Baltic further",
  "So the whole revenue story lives in capture value: our common currency across both models",
  "Measured monthly for 31 study farms (16 North Sea, 15 Baltic)"],
 # 5 SCOPE
 ["Unit of analysis = the bidding zone (one price per area per hour)",
  "North Sea (open): DE, NL, BE, DK1, FR",
  "Baltic under-built: PL, EE, LV, LT; built-out preview: DK2, SE4",
  "Excluded: Finland (nuclear), GB (Brexit), Norway (hydro)",
  "Space-for-time: the built-out zones are the future of the under-built ones"],
 # 6 THE DESIGN
 ["Need to MEASURE the past (data-rich) and PROJECT the future (no data); no single method does both",
  "Regression measures the past and explains the mechanism",
  "PyPSA carries the future; the validation triangle checks they agree where reality is observable",
  "Deliberate division of labour; the regression provably cannot extrapolate"],
 # 7 VIRTUAL WIND FARM
 ["Need a consistent hourly profile for every zone, including zones with no farm yet, from open data",
  "Built from weather: ERA5 wind, lifted to 150 m hub height, through a 15 MW turbine power curve",
  "Validated vs metered output: r = 0.88 hourly, 0.95 monthly",
  "Neither predecessor validated this; it lets us price farms in zones with prices but no turbines"],
 # 8 REGRESSION
 ["Unit = one farm-month; 7 features in, that month's capture value out",
  "Scored leave-farm-out (blind): R2 = 0.69",
  "Capture value is a property of prices, so I price the validated farm in all 7 enclosed Baltic zones",
  "Predicts the enclosed Baltic zones blind within 0.07 (general, not memorising one zone)",
  "A North-Sea-only model still transfers to the Baltic (R2 ~0.38): general, not memorising"],
 # 8b INSIDE THE REGRESSION
 ["The empirical instrument opened up (the mirror of the PyPSA box)",
  "Inputs: 7 market features per farm-month (crowding, demand, penetration, fuel, buffering) from the VWF + ENTSO-E",
  "Model: gradient boosting, 400 shallow trees summed; trained operational, scored leave-farm-out (R2 0.69)",
  "How it projects: the tree ABSTAINS (flat ~0.82); the analytical form extrapolates gently (0.79, 0.72) but linearly",
  "That sits above PyPSA's 0.57/0.47 (the convex collapse it cannot see), so PyPSA carries 2040"],
 # 10 PYPSA
 ["Open model: grid, generators, storage, demand, solved least-cost every hour",
  "Wholesale price = hourly shadow price at each node, then capture value by the same formula",
  "14 countries, ~30 nodes, grid FROZEN at 2020 (today's grid under tomorrow's fleet, on purpose)",
  "Future built from official TYNDP 2030/2040 scenarios; the frozen grid is bracketed later"],
 # 11 INSIDE PYPSA (pipeline)
 ["Inputs: grid nodes, full fleet, ERA5 weather, hourly demand, fuel and carbon prices",
  "Solves: minimise system cost over 8,760 hours; the supply=demand shadow price is the wholesale price",
  "Windy hour: wind is marginal, price falls toward zero; still hour: gas sets it",
  "Supervisor's question: same capture-value formula as the regression, but price from a grid the regression cannot see"],
 # 13 VALIDATION TRIANGLE
 ["Three independent estimates per zone: observed, PyPSA, regression (blind)",
  "Blind regression within 0.014 of observed (2023), 0.025 across 3 years, by a route independent of PyPSA",
  "PyPSA exact on open zones, carries its congestion bias on DK1 and DK2",
  "No predecessor confronted a statistical model, a physical model, and observation like this"],
 # 15 RQ1 TODAY
 ["Direct answer to RQ1, as a map; shading = capture value",
  "Today the map is all green: under-built Baltic 0.85 to 0.92, level with the North Sea 0.85 to 0.90",
  "So the Baltic does NOT start behind"],
 # 16 RQ1 2030
 ["First buildout has landed; North Sea and under-built Baltic still mostly green (high 0.7s to 0.8s)",
  "Baltic starting to fade as its own correlated wind begins to crowd its price",
  "Estonia grey: no offshore in the water yet at this horizon"],
 # 17 RQ1 2040
 ["Map splits: Baltic red-orange (PL 0.49, LV 0.42, EE 0.39); North Sea holds about 0.57",
  "Parity today (~0.89) to Baltic ~0.47 vs North Sea ~0.57; Baltic loses ~47%, North Sea ~35%",
  "The buildout, not the starting point, is what does it",
  "Why it falls faster, and whether the grid changes it, are the next sections"],
 # 18 ENERGY MIX
 ["The buildout behind the result; the natural question is whether it is realistic",
  "North Sea offshore ~19 to 165 GW; Baltic Sea ~3 to 50 GW (of which the enclosed states 0 to ~25, a quarter of regional demand)",
  "Full mix: gas and oil persist (~80 and 9 GW) through 2040, nuclear and hydro stay, only DE/PL coal winds down",
  "The fossil backbone still sets the low-wind price, which is exactly what erodes capture value"],
 # 20 GRID REVERSAL
 ["The reframe: I removed the grid limit, let the model build the cost-optimal transmission and pay for it",
  "Frozen (solid): Baltic erodes faster, 0.47 vs North Sea 0.57",
  "Optimal (dashed) CROSSES: Baltic recovers to 0.66, above the North Sea 0.64 (PL 0.49 to 0.74)",
  "So the faster Baltic erosion is a frozen-grid effect; open the export valve and its advantage returns",
  "Policy headline: interconnection is the highest-leverage lever",
  "Honest detail: at 2030 (low penetration) optimal is marginally below frozen; it only helps once congestion binds"],
 # 21 CONGESTION vs ENCLOSURE DECOMPOSITION
 ["Answers his question directly: of the CV fall, how much is congestion (grid-fixable) vs structural enclosure",
  "Both basins start at parity ~0.89; frozen 2040: Baltic 0.47, North Sea 0.57",
  "North Sea fall = 80% structural, 20% congestion; Baltic = 54% structural, 46% congestion",
  "Baltic congestion penalty (0.19) is 3x the North Sea's (0.06); its STRUCTURAL fall is smaller (0.22 vs 0.25)",
  "So the enclosure is really congestion: build the grid and the Baltic ends ABOVE the North Sea (0.66 vs 0.64)"],
 # 22 RQ2 SHAP
 ["Cross-sectional question: why does one farm earn less than another in the same month",
  "Strip the shared 2022 fuel-crisis time signal: carbon collapses from 29% to 4%",
  "Crowding (correlation with system wind) leads at 32%; buffering (interconnection, flexibility) close behind",
  "Basins differ: the same buildout cannibalises about twice as steeply in the enclosed Baltic (analytical penalty 0.74 vs 0.37)"],
 # 23 ENCLOSED-BASIN CORRELATION
 ["Geographic root of why the Baltic is steeper (built like Jacquet: cluster the farms, circle them on the map)",
  "Under-built Baltic correlate at 0.61 vs North Sea 0.44; built-out DK2/SE4 tightest at 0.87",
  "Those under-built zones are exactly the ones about to build out",
  "The two basins are decoupled (0.28), so the Baltic cannot lean on the North Sea to absorb its surplus"],
 # 27 RQ3 ABSTAIN
 ["Can an empirical model project these futures? Provably no, and that is by design",
  "Every future scenario sits beyond the training range (carbon); the tree flat-lines out of support",
  "Time-split test (train through 2022, predict 2023 to 2024) fails: R2 about minus 0.03",
  "So the regression abstains and PyPSA carries it; the triangle proves the hand-off (a methodological contribution)"],
 # 28b CAPTURE VALUE EVOLUTION (all instruments)
 ["Every instrument on one chart (North Sea left, Baltic right), 2025 to 2040",
  "PyPSA frozen finds the collapse (NS 0.57, Baltic 0.47); the optimal grid recovers it (0.64, 0.66)",
  "Regression stays high: tree abstains (flat ~0.82), analytical projects gently (0.79, 0.72)",
  "The 2040 gap (~0.22 NS, 0.25 Baltic) IS the convex collapse the linear form misses, so PyPSA carries it",
  "Agree to 2030 (trust either); part at 2040 (only the market-clearing model is right)"],
 # 31 E1 NET VALUE
 ["Does it PAY? Net value/MW = resource (CF) x capture value x price, minus depth/distance cost (GWA + GEBCO)",
  "2025: ~48% of the shelf profitable (green); 2040: ~12% - the profitable area collapses",
  "WHY it shrinks: cannibalisation erodes capture value, so revenue drops below cost across more of the sea; cheaper turbines (~12%) cannot keep up with the value lost",
  "WHY the shallow North Sea stays green: it stacks all three - best wind (CF ~0.5), shallow water, near shore - so the most cost margin to absorb the erosion",
  "WHY the deep water (Norwegian trench) is always red: floating foundations add ~EUR 1m/MW, so even strong wind cannot break even there",
  "WHY it still beats the Baltic despite the capture-value reversal: net value is set by resource + cost, and the North Sea's ~20% CF edge outweighs the Baltic's higher capture value",
  "Takeaway: build EARLY (value highest before cannibalisation) and SHALLOW (cost margin); late and deep both lose"],
 # 32 E2 VALUE-ADJUSTED LCOE (novelty)
 ["The contribution: value-adjusted LCOE = LCOE / capture value = the price a site needs to break even",
  "Raw LCOE FALLS with technology (74 to 66 EUR/MWh); the value-adjusted LCOE RISES (87 to 121)",
  "Cannibalisation undoes the learning; the competitive area (under ~70) collapses from 35% to under 1%",
  "Robust: costs must fall 36% by 2040 (3x the DEA's 12%) just to hold it flat, in all 27 cases",
  "No one has mapped this spatially before"],
 # 33 E3 INTERCONNECTION IN MONEY
 ["Value-adjusted LCOE = LCOE/CV, and interconnection raises CV, so it lowers the break-even price",
  "Enclosed Baltic falls EUR 33/MWh, four times the core North Sea's EUR 8 (Danish transit EUR 48)",
  "Worth about EUR 1.2 bn/yr to Baltic offshore alone, roughly 55% of the cost of ALL the new lines",
  "Not an open cost problem: the model builds a specific 133 GW at EUR 2.2 bn/yr and stops",
  "Recommendation: build the grid; it is a break-even cut aimed exactly at the basin with the problem"],
 # E4 SITE RANKING (does value change it)
 ["Objective 4: does adding capture value change which sites to build?",
  "Rank candidate areas by cost (LCOE) vs value-adjusted (vLCOE): 2025 agree (0.99), 2040 diverge (0.90)",
  "Movers: cheap-but-cannibalised Estonia + Latvia DROP; value-resilient Danish North Sea RISES; German Bight stays #1",
  "So cost-only ranking is fine today but increasingly misleads toward 2040: the value dimension matters"],
 # E5 SITE RANKING TWO METRICS
 ["169 candidate sites, two lenses: cheapest break-even (value for money) vs largest profit/MW (net value)",
  "Both reward the shallow windy value-resilient shelf; German Bight tops both",
  "Value-for-money tilts to the cheap shallow western Baltic (PL, DK2); absolute money tilts to the high-resource North Sea",
  "Recommendation: German Bight + shallow western Baltic first; cheap eastern Baltic (EE, LV) is a value trap by 2040"],
 # E6 DIVERSIFICATION (objective 5)
 ["Objective 5: portfolio value of spreading across both basins vs concentrating in the North Sea",
  "Cannibalisation hedge YES: all-NS craters; spreading ~12% to the Baltic lifts aggregate 2040 CV about a third; planned split near-optimal",
  "Risk hedge NO: wind decorrelates (0.28) but capture value co-moves (0.80), so no volatility cut; NS is lower-risk AND higher-value",
  "Payoff is on the MEAN (less cannibalisation), not the variance; the low correlation lives in the wind, not the value"],
 # 34 WHAT IT MEANS
 ["RQ1: parity today, Baltic about 0.47 by 2040 vs North Sea 0.57; with grid it recovers to 0.66 (above)",
  "RQ2: same mechanisms, steeper in the enclosed Baltic (correlated wind, weak export valve)",
  "RQ3: regression measures and explains; PyPSA carries the future; the triangle validates the hand-off",
  "Economics: value-adjusted LCOE rises despite cheaper turbines; interconnection lowers the Baltic's EUR 33/MWh (~EUR 1.2 bn/yr)",
  "Policy: interconnection is THE lever; subsidy and CfD design must price the structural fall"],
 # 35 CONCLUSION
 ["The Baltic does not start behind, but on today's grid the buildout cannibalises it faster",
  "Build the grid and it reverses: the Baltic recovers above the North Sea; the erosion is a policy choice, not fate",
  "Novel metric: value-adjusted LCOE rises despite cheaper turbines; interconnection lowers the Baltic's most (EUR 33/MWh, ~EUR 1.2 bn/yr)",
  "Contribution: two validated instruments, a proven hand-off, a value-adjusted cost map, all on open data",
  "Thank you; happy to take questions"],
]

def set_bullet_notes(slide, points):
    tf = slide.notes_slide.notes_text_frame
    tf.clear()
    for i, pt in enumerate(points):
        para = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        para.text = "•  " + pt

assert len(HIGHLIGHTS) == len(prs.slides), (len(HIGHLIGHTS), len(prs.slides._sldIdLst))
for _slide, _points in zip(prs.slides, HIGHLIGHTS):
    set_bullet_notes(_slide, _points)

prs.save(OUT)
print("WROTE", OUT, "-", len(prs.slides._sldIdLst), "slides")

# Dump the speaker script alongside the deck so the .txt never drifts from the .pptx.
SCRIPT_OUT = ROOT + "/10_Presentation/_deck_script.txt"
lines = []
for i, (title, bullets, table, note) in enumerate(SCRIPT, start=1):
    lines.append("=== SLIDE %d: %s ===" % (i, title))
    if bullets:
        lines.append("  " + " | ".join("•  " + b for b in bullets))
    if table:
        headers, data, footnote = table
        lines.append("TABLE:")
        lines.append("  " + "  |  ".join(headers))
        for row in data:
            lines.append("  " + "  |  ".join(str(c) for c in row))
        if footnote:
            lines.append("  (" + footnote + ")")
    lines.append("NOTES (points to highlight):")
    for pt in HIGHLIGHTS[i - 1]:
        lines.append("  •  " + pt)
    lines.append("")
with open(SCRIPT_OUT, "w") as fh:
    fh.write("\n".join(lines))
print("WROTE", SCRIPT_OUT, "-", len(SCRIPT), "slides")
