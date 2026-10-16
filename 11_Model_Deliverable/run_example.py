"""
run_example.py

A guided tour of the Baltic offshore-wind capture-value model. Run it as-is to
see the four things the model is for. Then edit the numbers and re-run.

    python run_example.py

Everything it prints is also saved to ./example_outputs/ (two CSVs, one figure).
"""
from pathlib import Path
import warnings

import pandas as pd

import baltic_wind_model as m

OUT = Path(__file__).resolve().parent / "example_outputs"
OUT.mkdir(exist_ok=True)


def section(title: str) -> None:
    print("\n" + "=" * 70 + f"\n{title}\n" + "=" * 70)


# --------------------------------------------------------------------------- #
# 1. One scenario, every zone. The basic question: "what does CV look like
#    under this build-out?"
# --------------------------------------------------------------------------- #
section("1. ONE SCENARIO, ALL ZONES  (default = 2040 high-buildout)")
per_zone = m.predict()           # defaults to the 2040-NT-balticHigh scenario
print(per_zone.to_string(index=False))
per_zone.to_csv(OUT / "per_zone_default_scenario.csv", index=False)

h = m.headline()
print(f"\n  Enclosed-Baltic mean capture value : {h['enclosed_baltic_cv']}")
print(f"  Core-North-Sea mean capture value  : {h['core_north_sea_cv']}")
print(f"  Cannibalisation asymmetry (NS/Baltic): {h['asymmetry_ns_over_baltic']}x")


# --------------------------------------------------------------------------- #
# 2. The headline experiment: build out the Baltic, watch its value collapse
#    while the North Sea barely moves. This IS the thesis result, made live.
# --------------------------------------------------------------------------- #
section("2. BALTIC BUILD-OUT SWEEP  (the headline cannibalisation result)")
rows = []
for gw in [10, 20, 30, 40, 60, 80, 100, 120, 150]:
    h = m.headline(baltic_offshore_gw=gw, warn=False)
    rows.append({"baltic_offshore_GW": gw,
                 "baltic_CV": h["enclosed_baltic_cv"],
                 "north_sea_CV": h["core_north_sea_cv"],
                 "asymmetry_NS_over_Baltic": h["asymmetry_ns_over_baltic"]})
sweep = pd.DataFrame(rows)
print(sweep.to_string(index=False))
sweep.to_csv(OUT / "baltic_buildout_sweep.csv", index=False)


# --------------------------------------------------------------------------- #
# 3. Gas-price sweep: the model says gas is SECOND-ORDER vs build-out. Watch
#    Baltic CV stay almost flat as gas swings across its whole range.
# --------------------------------------------------------------------------- #
section("3. GAS-PRICE SWEEP  (gas is second-order vs build-out)")
for gas in [15, 30, 50, 75, 100]:
    h = m.headline(gas=gas, warn=False)
    print(f"  gas {gas:3d} EUR/MWh  ->  Baltic CV {h['enclosed_baltic_cv']:.3f}   "
          f"North Sea CV {h['core_north_sea_cv']:.3f}")


# --------------------------------------------------------------------------- #
# 4. Pick a single zone and a custom scenario. This is how you ask the model
#    your own question.
# --------------------------------------------------------------------------- #
section("4. A CUSTOM QUESTION  (Polish zone, low gas, heavy Baltic build-out)")
ans = m.predict(zones=["PL"], gas=18, baltic_offshore_gw=100, year=2040, warn=False)
print(ans.to_string(index=False))


# --------------------------------------------------------------------------- #
# Optional figure of the headline sweep (skipped cleanly if matplotlib absent).
# --------------------------------------------------------------------------- #
try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.plot(sweep.baltic_offshore_GW, sweep.baltic_CV,
            "-o", color="indianred", label="Enclosed Baltic")
    ax.plot(sweep.baltic_offshore_GW, sweep.north_sea_CV,
            "-o", color="steelblue", label="Core North Sea")
    ax.set_xlabel("Baltic offshore wind installed (GW)")
    ax.set_ylabel("Offshore-wind capture value")
    ax.set_title("Baltic value collapses with build-out; North Sea holds")
    ax.grid(alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(OUT / "headline_cannibalisation.png", dpi=150)
    print(f"\nSaved figure -> {OUT / 'headline_cannibalisation.png'}")
except Exception as exc:  # matplotlib missing or headless issue: not fatal
    print(f"\n(figure skipped: {type(exc).__name__})")

print(f"\nAll example outputs saved to: {OUT}")
