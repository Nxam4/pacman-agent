#!/usr/bin/env bash
# Held-out benchmark: plays team A (default my_team.py) and team B (default: the most recently frozen
# champion) against the `bench` teams of arena/ext_teams.txt - teams the loop and the tuner never
# see - on identical games (same layouts, seeds and colours), and prints both scores plus the paired
# difference. Use it to detect overfitting (training/gate scores up, benchmark flat or down), e.g.
# nightly or before each push. Never use it to choose between candidates, or it stops being held out.
#   bash arena/benchmark.sh [A.py] [B.py]       GAMES=24 per opponent (even), SEED=2026
# Results: arena/bench/<time>_{a,b}.json, one line per run appended to arena/bench/history.tsv.
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
python3 - "arena/bench/${ts}_a.json" "arena/bench/${ts}_b.json" "$A" "$B" "$ts" <<'EOF'
import json, math, os, sys
ja, jb = (json.load(open(p)) for p in sys.argv[1:3])
A, B, ts = sys.argv[3:6]
pts = lambda r: 1.0 if r["cand_score"] > 0 else (0.5 if r["cand_score"] == 0 else 0.0)
sa, sb = ja["summary"]["by_opponent"], jb["summary"]["by_opponent"]
sc = lambda s: s.get("clean_score_pct") if s.get("clean_score_pct") is not None else s.get("score_pct", 0)
print("score % over games the opponent did not crash/forfeit (oppX = games it did, in A's run)")
print("%-26s %8s %8s %7s %5s   %s" % ("held-out opponent", "A score", "B score", "A-B", "oppX", "A avg margin / bank / conc"))
for k in sa:
    a, b = sa[k], sb.get(k, {})
    pa = a.get("play") or {}
    print("%-26s %7.1f%% %7.1f%% %+6.1f %5s   %+6.1f / %s / %s" % (
        k.split("/")[-1], sc(a), sc(b), sc(a) - sc(b), a.get("opp_crashes", "-"),
        a["avg_score"], pa.get("banked", "-"), pa.get("conceded", "-")))
def opp_failed(r):   # opponent crashed / forfeited: free win, not a measurement
    me = {0, 2} if r.get("cand_red") else {1, 3}
    return bool(r.get("blue_crash") if r.get("cand_red") else r.get("red_crash")) or \
        any(a not in me for a in r.get("forfeits", []))
pairs = list(zip(ja["games"], jb["games"]))
d = [pts(x) - pts(y) for x, y in pairs if not (opp_failed(x) or opp_failed(y))]
print("(%d of %d games skipped: opponent crashed or forfeited)" % (len(pairs) - len(d), len(pairs)))
n = len(d); m = sum(d) / n
se = math.sqrt(sum((x - m) ** 2 for x in d) / max(1, n - 1) / n)
ta, tb = ja["summary"]["total"], jb["summary"]["total"]
print("%-26s %7.1f%% %7.1f%% %+6.1f   (paired: %+.1f +- %.1f points, 95%% CI %+.1f..%+.1f)" % (
    "TOTAL", sc(ta), sc(tb), sc(ta) - sc(tb),
    100 * m, 100 * se, 100 * (m - 1.96 * se), 100 * (m + 1.96 * se)))
bad = [(lbl, t) for lbl, t in (("A", ta), ("B", tb)) if t["crashes"] or t["timeouts"] or t.get("forfeits")]
for lbl, t in bad:
    print("!! %s not clean: crashes %s, slow %s, forfeits %s" % (lbl, t["crashes"], t["timeouts"], t.get("forfeits")))
verdict = ("A better" if m - 1.96 * se > 0 else "A worse" if m + 1.96 * se < 0 else "no clear difference")
print("verdict:", verdict)
h = "arena/bench/history.tsv"
new = not os.path.exists(h)
with open(h, "a") as f:
    if new:
        f.write("time\tA\tB\tgames\tA_score\tB_score\tpaired_diff\tse\tverdict\n")
    f.write("%s\t%s\t%s\t%d\t%.1f\t%.1f\t%+.1f\t%.1f\t%s\n" % (
        ts, A, B, n, sc(ta), sc(tb), 100 * m, 100 * se, verdict))
EOF
