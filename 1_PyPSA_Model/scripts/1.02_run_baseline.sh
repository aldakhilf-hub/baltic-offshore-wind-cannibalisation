#!/usr/bin/env bash
# 1.02_run_baseline.sh — run a PyPSA-Eur historical baseline end-to-end.
# All caching is handled by Snakemake — re-running this skips whatever's
# already up to date. Use --forcerun <rule> to invalidate a step.
#
# Usage:
#   ./1.02_run_baseline.sh 2019                      # 2019 baseline (incremental)
#   ./1.02_run_baseline.sh 2023                      # 2023 baseline (headline year)
#   ./1.02_run_baseline.sh 2023 --forcerun solve_network
#   ./1.02_run_baseline.sh 2019 --dry-run            # show what would run

set -euo pipefail

YEAR="${1:?usage: 1.02_run_baseline.sh <2019|2023|2024> [extra snakemake args...]}"
shift
case "$YEAR" in 2019|2023|2024) ;; *) echo "year must be 2019, 2023 or 2024" >&2; exit 1;; esac

REPO="$HOME/pypsa-eur"
ENV_PY="$HOME/miniforge3-arm64/envs/pypsa-eur-arm64/bin"
CONFIG="config/config.faisal-${YEAR}.yaml"
TARGET="results/faisal-${YEAR}/networks/base_s_30_elec_.nc"
LOG="$HOME/Desktop/pypsa_${YEAR}_run_$(date +%Y%m%d_%H%M%S).log"

cd "$REPO"

echo "Logging to: $LOG"
echo "Snakemake target: $TARGET"
echo "Config: $CONFIG"
echo

# -c all already implies all cores; caffeinate keeps the Mac awake for the solve.
caffeinate -i nohup "$ENV_PY/snakemake" \
    -call "$TARGET" \
    --configfile "$CONFIG" \
    "$@" \
    > "$LOG" 2>&1 &

PID=$!
disown
echo "Running in background — PID $PID"
echo "Tail the log with:  tail -f $LOG"
echo "Check status with:  ps -p $PID -o pid,stat,etime,%cpu,%mem"
