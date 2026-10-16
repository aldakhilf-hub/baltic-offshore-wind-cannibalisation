"""
1.21_ntc_correction.py

DK2 diagnosis, route 1: replace THERMAL RATINGS with published MARKET NTCs on the
Danish AC interconnectors, then re-solve the 2023 calibration year.

Why this is a correction and not a tuning knob. PyPSA-Eur sizes AC corridors from
the grid model's thermal ratings, which are an engineering limit. Day-ahead market
coupling clears against far smaller Net Transfer Capacities, which reserve headroom
for reliability. The 2023 network carries:

    DK2 - SE   one AC line at 3396 MW   vs Oresund market NTC  ~1700 MW
    DE  - DK1  three AC lines, 11171 MW vs DK1-DE market NTC   ~2500 MW

The HVDC links are already at their true ratings (Great Belt 600, Kontek 600,
COBRA 700, Skagerrak 1140, Konti-Skan 550), so the defect is confined to the AC
corridors. Slide 12 of the supervisor deck already names this as the reason a
small, well-connected zone has its price pinned to a large neighbour and its local
cannibalisation hidden.

NTC values (symmetric, set to the EXPORT direction, which is the binding one for
surplus wind and the more conservative choice for this test):
    DK2 -> SE4  1700 MW   (Energinet / ENTSO-E; the import direction is ~1300)
    DK1 -> DE   2500 MW   (post-2020 border capacity)
Parallel corridors are scaled proportionally so the corridor total meets the NTC.

The change is applied to line s_nom only. Nothing else is touched: same fleet,
same weather, same fuel prices, same solver settings as the calibration run.

Usage:  python 1.21_ntc_correction.py            (solves, ~10-40 min)
Output: results/ntc_correction/{summary.csv, per_zone.csv} + solved network
"""
import importlib.util, warnings
from pathlib import Path
import numpy as np, pandas as pd, pypsa

warnings.filterwarnings("ignore")
pd.set_option("display.width", 200)

ROOT = Path(__file__).resolve().parents[2]
SRC = Path.home() / "pypsa-eur/results/faisal-2023/networks/base_s_30_elec_.nc"
OUT = ROOT / "1_PyPSA_Model/results/ntc_correction"
OUT.mkdir(parents=True, exist_ok=True)
SOLVED = OUT / "base_s_30_elec_ntc2023.nc"

spec = importlib.util.spec_from_file_location("sur", ROOT / "1_PyPSA_Model/scripts/1.13_surrogate_runs.py")
sur = importlib.util.module_from_spec(spec); spec.loader.exec_module(sur)

NTC = {("DK2", "SE"): 1700.0, ("DE", "DK1"): 2500.0}
ZONES = ["DK2", "DK1", "DE", "NL", "BE", "SE"]
OBS_2023 = {"DK2": 0.784, "DK1": 0.854, "DE": 0.909, "NL": 0.881, "BE": 0.869}


def zone_of(n, bus, dk2, dk1):
    if bus in dk2:
        return "DK2"
    if bus in dk1:
        return "DK1"
    return n.buses.country.get(bus, "?")


def capture(n, zone):
    d = sur.offshore_capture(n, zone)
    return d["CV_raw"], d["energy_GWh"], d["mean_price"]


n = pypsa.Network(str(SRC))
dk2, dk1 = set(sur.zone_buses(n, "DK2")), set(sur.zone_buses(n, "DK1"))

# ---- apply the NTCs to the AC corridors -------------------------------------
rows = []
for (a, b), ntc in NTC.items():
    mask = n.lines.apply(
        lambda r: {zone_of(n, r.bus0, dk2, dk1), zone_of(n, r.bus1, dk2, dk1)} == {a, b}, axis=1)
    corridor = n.lines[mask]
    before = corridor.s_nom.sum()
    if before <= 0:
        continue
    scale = ntc / before
    n.lines.loc[mask, "s_nom"] = corridor.s_nom * scale
    n.lines.loc[mask, "s_nom_max"] = corridor.s_nom * scale
    rows.append(dict(corridor=f"{a}-{b}", n_lines=int(mask.sum()), thermal_MW=before,
                     ntc_MW=ntc, scale=scale))
    print(f"{a}-{b}: {int(mask.sum())} line(s), {before:.0f} MW thermal -> {ntc:.0f} MW NTC "
          f"(x{scale:.2f})")
pd.DataFrame(rows).to_csv(OUT / "corridors_applied.csv", index=False)

# ---- re-solve, same settings as the calibration run -------------------------
print("\nsolving 2023 with corrected NTCs ...")
n.optimize(solver_name="gurobi", method=2, crossover=0, threads=6,
           BarConvTol=1e-6, FeasibilityTol=1e-6)
n.export_to_netcdf(str(SOLVED))

# ---- compare against the uncorrected run and observation --------------------
base = pypsa.Network(str(SRC))
out = []
for z in ZONES:
    cb, eb, pb = capture(base, z)
    cn, en, pn = capture(n, z)
    out.append(dict(zone=z, observed=OBS_2023.get(z, np.nan),
                    CV_thermal=cb, CV_ntc=cn, delta=cn - cb,
                    err_thermal=cb - OBS_2023.get(z, np.nan),
                    err_ntc=cn - OBS_2023.get(z, np.nan),
                    mean_price_thermal=pb, mean_price_ntc=pn, energy_GWh=en))
D = pd.DataFrame(out)
D.to_csv(OUT / "per_zone.csv", index=False)
print("\n=== 2023 capture value: thermal ratings vs corrected NTCs ===")
print(D.round(3).to_string(index=False))

sub = D.dropna(subset=["observed"])
print(f"\nmean |error| thermal {sub.err_thermal.abs().mean():.3f} "
      f"-> NTC {sub.err_ntc.abs().mean():.3f}")
print(f"DK2 error {sub.set_index('zone').err_thermal['DK2']:+.3f} "
      f"-> {sub.set_index('zone').err_ntc['DK2']:+.3f}")
pd.DataFrame([dict(mae_thermal=sub.err_thermal.abs().mean(),
                   mae_ntc=sub.err_ntc.abs().mean(),
                   dk2_err_thermal=sub.set_index('zone').err_thermal['DK2'],
                   dk2_err_ntc=sub.set_index('zone').err_ntc['DK2'])]).to_csv(
    OUT / "summary.csv", index=False)
