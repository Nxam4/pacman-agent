#!/usr/bin/env bash
# Unattended SPSA tuning run (Windows Task Scheduler "PacmanTune", via arena/keep_awake.ps1):
# waits until no loop is running, tunes my_team.py's constants for HOURS (default 8, the gate
# included), then runs the loop's promotion gate; with PROMOTE=1 a tuned version that passes is
# promoted and committed. A loop started meanwhile stops the tuner (state saved).
# Output: arena/logs/tune_<timestamp>.log, arena/tune/REPORT.md.
cd "$(dirname "$0")/.." || exit 1
# shellcheck disable=SC1091
source venv/bin/activate || exit 1
mkdir -p arena/logs
log="arena/logs/tune_$(date '+%Y%m%d_%H%M').log"
{
  echo "start_tune: $(date '+%F %T')  HOURS=${HOURS:-8} PROMOTE=${PROMOTE:-1}"
  promote=(); [ "${PROMOTE:-1}" = 1 ] && promote=(--promote)
  python3 arena/tune.py --hours "${HOURS:-8}" --pool auto --gate "${promote[@]}" --wait-loop
  echo "start_tune: finished $(date '+%F %T')"
} > "$log" 2>&1
