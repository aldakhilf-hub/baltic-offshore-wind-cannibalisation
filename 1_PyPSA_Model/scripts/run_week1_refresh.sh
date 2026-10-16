#!/usr/bin/env bash
# run_week1_refresh.sh — Week-1 refresh chain (2026-06-11).
#
# Re-solves EVERYTHING under the fixed configs (frozen transmission v1.0,
# year-correct renewable fleets) and the repaired scenario engine (solver
# parity, demand rebase, no silent truncation), then regenerates every
# downstream result: calibration, projections, bias fit, gas grid, Track 2,
# the three-way comparison, and the surrogate.
#
# Old (vopt) networks are backed up to results/_backup_vopt_2026-06-11 first —
# nothing is lost, and the thesis can report a frozen-vs-optimal-grid
# sensitivity from the backup.
#
# Run:  caffeinate -i bash run_week1_refresh.sh   (or via nohup; ~5-8 h total)
set -euo pipefail

ENV="$HOME/miniforge3-arm64/envs/pypsa-eur-arm64/bin"
PY="$ENV/python"
T="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"   # repo root, resolved from this script
S1="$T/1_PyPSA_Model/scripts"
S2="$T/2_Regression_Model/scripts"
S3="$T/3_Comparison"
PE="$HOME/pypsa-eur"
BK="$PE/results/_backup_vopt_2026-06-11"

stage() { echo; echo "##### [$(date '+%F %T')] $*"; }

verify_baseline() {
  "$PY" - "$1" <<'PYEOF'
import sys
from pathlib import Path
import pypsa
y = sys.argv[1]
n = pypsa.Network(Path.home() / f"pypsa-eur/results/faisal-{y}/networks/base_s_30_elec_.nc")
gc = n.global_constraints
ok = ("lv_limit" in gc.index) or (len(gc) > 0 and gc.type.astype(str).str.contains("transmission").any())
print(f"  {y}: global constraints = {list(gc.index)}")
sys.exit(0 if ok else 1)
PYEOF
}

solve_baseline() {
  local year=$1
  stage "S1 snakemake baseline $year (frozen grid v1.0, fleet year $year)"
  (cd "$PE" && "$ENV/snakemake" -call "results/faisal-$year/networks/base_s_30_elec_.nc" \
      --configfile "config/config.faisal-$year.yaml")
  if ! verify_baseline "$year"; then
    echo "  transmission limit not in solved network — forcing add_electricity cascade"
    (cd "$PE" && "$ENV/snakemake" -call "results/faisal-$year/networks/base_s_30_elec_.nc" \
        --configfile "config/config.faisal-$year.yaml" --forcerun add_electricity)
    verify_baseline "$year" || { echo "FATAL: v1.0 limit still absent after forced rerun"; exit 1; }
  fi
}

stage "S0 backup old (vopt) networks + clear stale caches"
mkdir -p "$BK"
for d in faisal-2019 faisal-2023 scenarios_tyndp_v3 gas_shock; do
  if [ -d "$PE/results/$d" ] && [ ! -e "$BK/$d" ]; then
    cp -R "$PE/results/$d" "$BK/$d"
    echo "  backed up $d"
  fi
done
# stale caches must go: 1.10 caches by file existence, and the old networks
# were solved under vopt with the old solver setup
rm -f "$PE"/results/gas_shock/*.nc
rm -f "$PE"/results/scenarios_tyndp_v3/*.nc

solve_baseline 2023
solve_baseline 2019

stage "S2 verify the two baselines carry year-correct, DIFFERENT fleets"
"$PY" - <<'PYEOF'
from pathlib import Path
import pypsa
p = {}
for y in (2019, 2023):
    n = pypsa.Network(Path.home() / f"pypsa-eur/results/faisal-{y}/networks/base_s_30_elec_.nc")
    off = n.generators[n.generators.carrier.str.startswith("offwind")]
    p[y] = off.groupby(off.bus.map(n.buses.country)).p_nom.sum().round(0)
    print(f"{y} offshore fleet (MW):")
    print(p[y].to_string())
assert not p[2019].equals(p[2023]), \
    "2019 and 2023 offshore fleets are identical — fleet-year fix did not take"
print("OK: fleets differ by year")
PYEOF

stage "S3 calibration metrics + capture values + baseline analysis (both years)"
for y in 2019 2023; do
  "$PY" "$S1/1.03_calibration_error_metrics.py" "$y"
  "$PY" "$S1/1.04_observed_capture_values.py" "$y"
  "$PY" "$S1/1.05_analyse_baseline.py" "$y"
done

stage "S4 1.07 — six TYNDP scenarios (solver parity, demand rebase, full targets)"
"$PY" "$S1/1.07_run_scenarios.py"

stage "S5 1.08 + 1.09 — projections + bias fit (consistent axis, clamped, CI)"
"$PY" "$S1/1.08_projected_capture_values.py"
"$PY" "$S1/1.09_bias_correction_fit.py"

stage "S6 gas-shock grid (15 cells incl. previously-missing gas120) + read-off"
"$PY" "$S1/1.10_gas_shock_grid.py"
"$PY" "$S1/1.11_gas_shock_capture_values.py"

stage "S7 Track 2 refresh (fit + OOF export + projection + SHAP)"
"$PY" "$S2/2.06_fit_regression.py"
"$PY" "$S2/2.07_project_capture_values.py"
"$PY" "$S2/2.08_mechanism_decomposition.py"

stage "S8 three-way comparison (OOF regression column)"
"$PY" "$S3/3.01_compare_three_way.py"

stage "S9 surrogate refresh (harvest new networks + 50 LHS @3-hourly + fit)"
SR="$T/1_PyPSA_Model/results/surrogate"
mkdir -p "$SR/_stale_2026-06-11"
for f in run_outputs.csv run_summary.csv; do
  if [ -f "$SR/$f" ]; then mv "$SR/$f" "$SR/_stale_2026-06-11/$f"; fi
done
"$PY" "$S1/1.13_surrogate_runs.py" --harvest
"$PY" "$S1/1.13_surrogate_runs.py" --every 3
"$PY" "$S1/1.14_surrogate_fit.py"
"$PY" "$S1/1.15_surrogate_sensitivity.py"

stage "DONE — week-1 refresh complete. All results regenerated."
