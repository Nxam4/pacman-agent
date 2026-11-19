#!/usr/bin/env bash
# Unattended switch-off tests + failure miner (Windows Task Scheduler, via arena/keep_awake.ps1).
# No Claude usage. Waits for a running loop/tuner, then: arena/ablate.py (HOURS budget, default 6),
# then arena/mine.py --record 6 (loss patterns + example replays).
# Output: arena/logs/ablate_<timestamp>.log, arena/ablate/REPORT.md, arena/mine/REPORT.md.
cd "$(dirname "$0")/.." || exit 1
# shellcheck disable=SC1091
source venv/bin/activate || exit 1
mkdir -p arena/logs
log="arena/logs/ablate_$(date '+%Y%m%d_%H%M').log"
{
  echo "start_ablate: $(date '+%F %T')  HOURS=${HOURS:-6} SEEDS=${SEEDS:-4}"
  python3 arena/ablate.py --hours "${HOURS:-6}" --seeds "${SEEDS:-4}"
  echo "start_ablate: ablation finished $(date '+%F %T'); mining losses"
  python3 arena/mine.py --record "${RECORD:-6}"
  echo "start_ablate: finished $(date '+%F %T')"
} > "$log" 2>&1
