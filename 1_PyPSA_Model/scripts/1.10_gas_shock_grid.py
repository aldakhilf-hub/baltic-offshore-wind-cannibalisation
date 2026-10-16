"""
10_gas_shock_grid.py

Gas-shock x buildout grid. Re-solves the canonical v3 scenario machinery
(script 07's run()) across a grid of gas prices crossed with buildout
scenarios that span the Baltic penetration range -- to measure how offshore
capture value RESPONDS to gas-price shocks, and whether that response differs
between the North Sea and the (increasingly saturated) Baltic.

Reuses 07.run() with gas_override so there is ZERO duplication of the
modelling logic; writes shocked networks to a SEPARATE directory so the
canonical scenarios_tyndp_v3/ networks are never touched.

  buildout (penetration low -> high):
      2030-NT-balticBaseline   (~0.25 Baltic offshore penetration)
      2040-NT-balticBaseline   (~0.50)
      2040-NT-balticHigh       (~0.94)
  gas grid (EUR/MWh, calm -> 2022-crisis):  15, 30, 50, 80, 120

Output networks:  ~/pypsa-eur/results/gas_shock/<scenario>__gas<g>.nc
Capture values are read off afterwards by 11_gas_shock_capture_values.py.

Usage:
  python 10_gas_shock_grid.py --pilot          # one solve (time it first)
  python 10_gas_shock_grid.py                   # full grid (15 solves)
  python 10_gas_shock_grid.py 2040-NT-balticHigh 80   # one specific cell
"""
import sys
import time
import importlib.util
from pathlib import Path

# import 07's run()/SCENARIOS without duplicating logic (filename starts w/ digit)
_spec = importlib.util.spec_from_file_location(
    "scen07", Path(__file__).resolve().parent / "1.07_run_scenarios.py")
scen07 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(scen07)

GAS_DIR = Path.home() / "pypsa-eur/results/gas_shock"
GAS_GRID = [15, 30, 50, 80, 120]
BUILDOUT = ["2030-NT-balticBaseline", "2040-NT-balticBaseline", "2040-NT-balticHigh"]


def solve_cell(scenario, gas):
    # gas must be an integer: the filename encodes int(gas), so a fractional
    # value would silently collide with the integer cell's cache (audit fix)
    if float(gas) != int(gas):
        raise SystemExit(f"gas price must be an integer EUR/MWh (got {gas}) — "
                         f"the cache filename encodes whole euros")
    name = f"{scenario}__gas{int(gas):03d}"
    if (GAS_DIR / f"{name}.nc").exists():
        print(f"  cached: {name}")
        return
    t0 = time.time()
    # 1.07's run() now checks solver status and exports atomically, so a
    # killed/suboptimal solve can never leave a poisoned cache file behind.
    scen07.run(name, scen07.SCENARIOS[scenario], gas_override=gas, out_dir=GAS_DIR)
    print(f"  >>> {name} solved in {(time.time() - t0) / 60:.1f} min")


def check_completeness():
    """Verify every (scenario, gas) cell exists — a silently missing cell
    truncated the 2040-NT-balticBaseline slope fit (audit finding)."""
    missing = [(s, g) for s in BUILDOUT for g in GAS_GRID
               if not (GAS_DIR / f"{s}__gas{g:03d}.nc").exists()]
    if missing:
        print(f"\nWARNING: grid INCOMPLETE — {len(missing)} missing cell(s):")
        for s, g in missing:
            print(f"  python 1.10_gas_shock_grid.py {s} {g}")
    else:
        print(f"\nGrid complete: {len(BUILDOUT) * len(GAS_GRID)} cells in {GAS_DIR}")
    return missing


def main():
    args = sys.argv[1:]
    if args == ["--pilot"]:
        cells = [("2030-NT-balticBaseline", 50)]
    elif len(args) == 2:
        if args[0] not in scen07.SCENARIOS:
            raise SystemExit(f"unknown scenario '{args[0]}' — choose from: "
                             f"{', '.join(scen07.SCENARIOS)}")
        cells = [(args[0], float(args[1]))]
    elif len(args) == 0:
        cells = [(s, g) for s in BUILDOUT for g in GAS_GRID]
    else:
        # malformed argv used to silently launch the full 15-solve grid (audit fix)
        raise SystemExit("usage: 1.10_gas_shock_grid.py [--pilot | <scenario> <gas>]\n"
                         "       (no args = full grid)")
    print(f"Gas-shock grid: {len(cells)} solve(s) -> {GAS_DIR}")
    t0 = time.time()
    for s, g in cells:
        solve_cell(s, g)
    print(f"\nAll {len(cells)} done in {(time.time() - t0) / 60:.1f} min total.")
    check_completeness()


if __name__ == "__main__":
    main()
