# Group presentation deck: rebuild instructions

Current deck (2026-09-06, restyle v2): `10_Presentation/Group_presentation_Faisal.pptx`, 8 slides, Arial only,
titles 28 pt, body 20 pt, captions 16 pt. Morph on slides 1-3 (one basemap, three crops) and 7-8 (vLCOE maps).
Builder: `build8.py` (fresh package each run; keep `build.py` only as the earlier 9-slide version).

1. `make_map.py` renders `europe_map_rgb.png` + `crops.json` from `windfarms.json` (EMODnet WFS, fetched
   2026-09-06) and `2_Regression_Model/data/wind_farms_strandA.csv`. Colours: operating #000080, planned dashed
   navy, study farms ringed (North Sea navy, Baltic #FF4500).
2. `python build8.py` (pypsa-eur-arm64 env) writes the deck. Validate with the pptx skill's validate.py.
3. Visual QA: `open -a "Microsoft PowerPoint" <file>` then AppleScript
   `save presentation "Group_presentation_Faisal.pptx" in (POSIX file x.pdf) as save as PDF`, addressing the
   presentation BY NAME (other decks may be open). Close any stale copy by name first, or PowerPoint exports
   the old in-memory version. Keynote export does not work; there is no LibreOffice.
