#!/usr/bin/env bash
# Held-out benchmark: plays team A (default my_team.py) and team B (default: the most recently frozen
# champion) against the `bench` teams of arena/ext_teams.txt - teams the loop and the tuner never
# see - on identical games (same layouts, seeds and colours), and prints both scores plus the paired
# difference. Use it to detect overfitting (training/gate scores up, benchmark flat or down), e.g.
# nightly or before each push. Never use it to choose between candidates, or it stops being held out.
#   bash arena/benchmark.sh [A.py] [B.py]       GAMES=24 per opponent (even), SEED=2026
#   SEED=2027 bash arena/benchmark.sh           another run on other layouts: pooled with earlier ones
#   python3 arena/bench_report.py --pool        pooled estimate only, no games
# Results: arena/bench/<time>_{a,b}.json, one line per run appended to arena/bench/history.tsv
# (with md5s of A and B). Runs of the same A/B files on different seeds are pooled game by game -
# read the POOLED line: one run (~200 games, +-2.5 points) rarely settles a 1-2 point difference.
set -euo pipefail
cd "$(dirname "$0")/.."
[ -n "${VIRTUAL_ENV:-}" ] || source venv/bin/activate
GAMES=${GAMES:-24}; SEED=${SEED:-2026}
A=${1:-my_team.py}
B=${2:-$(ls -td arena/opponents/champ_*/ | head -1)my_team.py}   # most recently frozen = previous champion
opps=()
while read -r set repo _; do
  [ "$set" = bench ] || continue
  f=arena/ext_pool/$(echo "${repo%%/*}" | tr 'A-Z-' 'a-z_')/my_team.py
  [ -s "$f" ] && opps+=("$f") || echo "missing $f (run arena/fetch_ext.sh)"
done < arena/ext_teams.txt
[ "${#opps[@]}" -gt 0 ] || { echo "no benchmark teams"; exit 1; }
mkdir -p arena/bench; ts=$(date +%Y%m%d_%H%M)
echo "benchmark: ${#opps[@]} held-out teams x $GAMES games, seed $SEED"
echo "  A = $A"; echo "  B = $B"
python3 arena/arena.py "$A" --opponents "${opps[@]}" --games "$GAMES" --seed "$SEED" --json "arena/bench/${ts}_a.json" > "arena/bench/${ts}_a.txt"
python3 arena/arena.py "$B" --opponents "${opps[@]}" --games "$GAMES" --seed "$SEED" --json "arena/bench/${ts}_b.json" > "arena/bench/${ts}_b.txt"
python3 arena/bench_report.py "$ts" "$A" "$B" "$SEED"
