#!/usr/bin/env bash
# Unattended start of the loop (e.g. from Windows Task Scheduler when the Claude usage limit resets):
#   wsl -d Ubuntu -- bash /mnt/c/Users/<you>/Projects/pacman-agent/arena/start_loop.sh
# Same environment as an interactive WSL shell: claude on PATH, venv active. All output goes to
# arena/logs/loop_<timestamp>.log. Loop settings can be passed as env vars (ROUNDS, BUILDERS, ...).
cd "$(dirname "$0")/.." || exit 1
export PATH="$HOME/.local/bin:$PATH"
# shellcheck disable=SC1091
source venv/bin/activate || exit 1
mkdir -p arena/logs
# Two scheduled runs may overlap (the previous one still busy): wait for it instead of starting a
# second loop on the same work dirs and program database.
while pgrep -f "bash arena/loop.sh" >/dev/null; do sleep 60; done
log="arena/logs/loop_$(date '+%Y%m%d_%H%M').log"
{
  echo "start_loop: $(date '+%F %T')  ROUNDS=${ROUNDS:-4} BUILDERS=${BUILDERS:-3}"
  ROUNDS=${ROUNDS:-4} BUILDERS=${BUILDERS:-3} bash arena/loop.sh
  echo "start_loop: finished $(date '+%F %T') (exit $?)"
} > "$log" 2>&1
