#!/usr/bin/env bash
# Autonomous improvement loop for the Eutopia Pacman contest (AlphaEvolve-style, see arena/README.md).
#
#  program DB -> N builders (parallel)  -> evaluation cascade                         -> promote -> analyst
#  parent +      each edits its own copy   smoke (2 games vs baseline, must be clean)    + commit    LEARNINGS.md
#  CONTEXT.md    with diverse inspirations -> SPRT vs champion (sequential, 16-120 games)            + directions
#                                          -> regression (fixed games vs baseline + recent champs)
#
# Run from the repo root, inside WSL/Linux, with the Python 3.8 venv active:
#   source venv/bin/activate && ROUNDS=4 BUILDERS=3 bash arena/loop.sh
# Stop early:   touch arena/STOP   (finishes the current round)
set -euo pipefail
shopt -s nullglob
cd "$(dirname "$0")/.."

ROUNDS=${ROUNDS:-5}
BUILDERS=${BUILDERS:-3}
MODEL=${MODEL:-claude-fable-5-2}
BUILDER_MODELS=${BUILDER_MODELS:-$MODEL}  # comma list, builder i uses entry i (cycled): fast+strong ensemble
ANALYST_MODEL=${ANALYST_MODEL:-$MODEL}
SMOKE_GAMES=${SMOKE_GAMES:-2}         # stage 1: games vs baseline, must be clean
SPRT_S0=${SPRT_S0:-0.50}              # stage 2: SPRT vs champion on score (win 1, tie 0.5); H0 = equal
SPRT_S1=${SPRT_S1:-0.60}              #   H1 = this much better; lower it later for finer gains (costs games)
SPRT_ALPHA=${SPRT_ALPHA:-0.05}        #   P(promote | not better)
SPRT_BETA=${SPRT_BETA:-0.10}          #   P(reject | really s1-good)
SPRT_MAX=${SPRT_MAX:-120}             #   max games, then "inconclusive" (a near-miss, may be continued)
REGRESS_GAMES=${REGRESS_GAMES:-12}    # stage 3: games per regression opponent (baseline + recent champs)
REGRESS_MIN=${REGRESS_MIN:-30}        #   score % needed vs each (loose: catches collapse; a 50% team
                                      #   falls below 30% in 12 games only ~2% of the time, below 40% ~16%)
CHAMPS_IN_GATE=${CHAMPS_IN_GATE:-2}   # most recent frozen champions in the regression stage
FOCUS_BASELINE=${FOCUS_BASELINE:-75}  # curriculum focus (arena/focus.txt) is released once the champion
FOCUS_STALL=${FOCUS_STALL:-2}         #   scores this % vs baseline, or after this many rounds w/o promotion
FOCUS_MIN_ROUNDS=${FOCUS_MIN_ROUNDS:-3}  # the baseline goal can release the focus only after this many rounds
                                      #   (the baseline is weak: round 1 already reached 100% vs it)
BUILDER_TIMEOUT=${BUILDER_TIMEOUT:-90m}
ANALYST_TIMEOUT=${ANALYST_TIMEOUT:-20m}
PUSH=${PUSH:-0}                       # 1 = git push after each promotion (that's what the organisers pull!)
PY=${PY:-python3}
NCPU=$(nproc 2>/dev/null || echo 4)
BUILDER_WORKERS=${BUILDER_WORKERS:-$(( NCPU / BUILDERS > 0 ? NCPU / BUILDERS : 1 ))}
IFS=',' read -r -a MODELS <<< "$BUILDER_MODELS"

# Headless Claude Code. Edits are auto-accepted; shell access is limited to a few commands.
# Kept as an array: an unquoted string would be glob-expanded (and, with nullglob, deleted).
if [ -n "${CLAUDE_FLAGS:-}" ]; then
  set -f; read -r -a CF <<< "$CLAUDE_FLAGS"; set +f
else
  CF=(--permission-mode acceptEdits
      --allowedTools "Read,Edit,Write,Glob,Grep,Bash(python3:*),Bash(python:*),Bash(cp:*),Bash(diff:*)")
fi

# ---- preflight ---------------------------------------------------------------------------
die() { echo "preflight: $*" >&2; exit 1; }
command -v claude >/dev/null || die "claude CLI not found on PATH (install Claude Code inside WSL and run 'claude' once to log in)"
command -v timeout >/dev/null || die "coreutils 'timeout' missing"
$PY -c 'import sys; assert sys.version_info[:2] == (3, 8), sys.version' 2>/dev/null \
  || die "$PY is not Python 3.8 - run 'source venv/bin/activate' first"
$PY -c 'import contest' 2>/dev/null || die "contest package not installed in this venv"
GIT=(git -c core.autocrlf=input)      # repo is shared with Windows; never commit CRLF from WSL
HAVE_GIT=0
if git rev-parse --git-dir >/dev/null 2>&1; then
  if git config user.email >/dev/null && git config user.name >/dev/null; then HAVE_GIT=1
  else echo "WARNING: git user.name/user.email not set - promotions will NOT be committed" >&2; fi
fi
commit() {   # commit "message" paths...  (never kills the loop)
  [ "$HAVE_GIT" = 1 ] || return 0
  local msg=$1; shift
  "${GIT[@]}" add -- "$@" 2>/dev/null || true
  "${GIT[@]}" diff --cached --quiet && return 0
  "${GIT[@]}" commit -qm "$msg" || { echo "WARNING: git commit failed" >&2; return 0; }
  if [ "$PUSH" = 1 ]; then git push -q || echo "WARNING: git push failed" >&2; fi
}
# Only the CLI's own error line counts (anchored at line start). The agents' text often mentions
# "usage limit" (e.g. the analyst summarising a limited round), which must not trigger this.
limit_hit() { [ -f "$1" ] && grep -qE "^(You've hit your|You have hit your|You've reached your) .*limit|^Credit balance is too low|^API Error: (429|529)" "$1"; }
run_analyst() {   # run_analyst ROUND_TAG WINNER FOCUS_BLOCK
  cp arena/directions.txt "arena/work/$1/directions_before.txt"
  local prompt
  prompt="$(sed -e "s|{{ROUND_DIR}}|arena/work/$1|g" -e "s|{{WINNER}}|$2|g" \
                -e "s|{{BUILDERS}}|$BUILDERS|g" arena/prompts/analyst.md)

CURRICULUM:
$3"
  timeout --kill-after=60 "$ANALYST_TIMEOUT" \
    claude -p "$prompt" --model "$ANALYST_MODEL" "${CF[@]}" > "arena/logs/${1}_analyst.log" 2>&1 || true
}
syntax_ok() { $PY -c "import ast,sys; ast.parse(open(sys.argv[1]).read(), feature_version=(3,8))" "$1" 2>/dev/null; }
db() { $PY arena/db.py "$@"; }

mkdir -p arena/opponents arena/logs arena/work
[ -f arena/LEARNINGS.md ] || echo "# Learnings (maintained by the analyst agent)" > arena/LEARNINGS.md
[ -f arena/directions.txt ] || cat > arena/directions.txt <<'EOF'
OFFENSE-BANK: make the attacker bank food instead of dying with it - return home when carried food x danger is high (danger from visible defenders AND EnemyTracker beliefs of hidden ones, see arena/KNOWLEDGE.md sec. 5) or when the moves left barely cover the trip home; precompute home distance and dead-end depth, never enter a dead end deeper than the margin to the nearest defender, safe-move test from KNOWLEDGE sec. 2.6; take 1-2 dots early to break 0-0 ties.
OFFENSE-PATH: danger-aware path planning for the attacker - A*/BFS where each cell's cost grows with defender proximity (visible + tracker belief mass), pick food clusters far from defenders rather than the nearest dot, capsule timing per KNOWLEDGE sec. 2.5 (eat it when a defender is near, then go deep for 40 moves), cross the border at the entry point least likely to be guarded.
SEARCH: junction-graph MCTS attacker per arena/KNOWLEDGE.md sec. 2 + 6 - own lightweight simulator over precomputed maze distances, tree over junctions with depth limited by path length, strategic epsilon-greedy ghost playouts (chase within 10, pincer front/rear junctions), reward = food-goal x survival rate with maximum backpropagation, hidden defenders root-sampled from the EnemyTracker belief (copy arena/snippets/enemy_tracker.py in), hard 0.4 s budget, reflex fallback.
DEFENSE: belief-driven pincer defence per arena/KNOWLEDGE.md sec. 3 + 5 - copy arena/snippets/enemy_tracker.py in (tested: 3.2 vs 12.1 cells error), defender patrols toward the most likely invader / the border cell it will most likely cross, intercepts at the front junction of its corridor while the other agent covers the rear when both are home, never both in one corridor, keep distance 2 when scared.
COORDINATION: role switching - both agents attack when ahead on time/score conditions and the enemy has no invaders, the defender returns when an invader is detected; split food targets so the two attackers never chase the same cluster.
EOF

focus_block() {   # focus_block ROUND_TAG -> prints the CURRICULUM text; may release the focus
  if [ ! -f arena/focus.txt ]; then
    echo "No curriculum focus is active: choose the most promising areas freely."; return
  fi
  local fs
  fs=$(db focus-status "$FOCUS_BASELINE" "$FOCUS_STALL" "$FOCUS_MIN_ROUNDS")
  if [ "$fs" = keep ]; then
    cat arena/focus.txt
    echo "ENFORCED: the first $BUILDERS lines of directions.txt must each start with one of the PREFIXES above
followed by an optional -SUBAREA and a colon (e.g. OFFENSE-BANK:). Use distinct subareas. Lines that
break this are moved down or your file is replaced by the previous one. The focus is released
automatically after at least $FOCUS_MIN_ROUNDS rounds once the champion scores >= ${FOCUS_BASELINE}% vs the
baseline, or after $FOCUS_STALL rounds without a promotion."
  else
    echo ">>> focus released ($fs)" >&2
    mv arena/focus.txt "arena/work/$1/focus_released.txt"
    echo "The curriculum focus was just released ($fs). Rebalance directions across areas:
the next most important weakness first, but keep at least one line improving what was in focus."
  fi
}
analyst_step() {   # analyst_step ROUND_TAG WINNER
  local fb
  fb=$(focus_block "$1")
  run_analyst "$1" "$2" "$fb"
  if limit_hit "arena/logs/${1}_analyst.log"; then
    echo ">>> analyst for $1 hit the usage limit - directions unchanged; it is retried on the next start."
    return 1
  fi
  if [ -f arena/focus.txt ]; then   # enforce the focus mechanically, don't just trust the prompt
    local pre
    pre=$(sed -n 's/^PREFIXES:[[:space:]]*//p' arena/focus.txt | tr ' ' '|')
    $PY - "$pre" "$BUILDERS" "arena/work/$1/directions_before.txt" <<'EOF' || echo "WARNING: focus check failed"
import re, shutil, sys
pre, n, backup = sys.argv[1], int(sys.argv[2]), sys.argv[3]
pat = re.compile(r"^\s*(%s)(-[A-Za-z0-9_]+)?\s*:" % pre)
lines = [l for l in open("arena/directions.txt").read().splitlines() if l.strip()]
inside = [l for l in lines if pat.match(l)]
if len(inside) >= n:
    open("arena/directions.txt", "w").write("\n".join(inside + [l for l in lines if not pat.match(l)]) + "\n")
    print("focus check: ok (%d in-focus lines)" % len(inside))
else:
    shutil.copy(backup, "arena/directions.txt")
    print("focus check: analyst wrote only %d in-focus lines (< %d) - previous directions restored" % (len(inside), n))
EOF
  fi
  commit "Round $1: learnings" arena/LEARNINGS.md arena/directions.txt
}

echo "models=${BUILDER_MODELS} analyst=$ANALYST_MODEL builders=$BUILDERS workers/builder=$BUILDER_WORKERS smoke=$SMOKE_GAMES sprt=[$SPRT_S0,$SPRT_S1] a=$SPRT_ALPHA b=$SPRT_BETA max=$SPRT_MAX regress=${REGRESS_GAMES}@${REGRESS_MIN}%"
db seed my_team.py
done_rounds=(arena/work/r*/)
start_round=${#done_rounds[@]}
if [ "$start_round" -gt 0 ]; then   # catch up an analyst that never ran (usage limit, crash, Ctrl-C)
  P=$(printf "r%02d" "$start_round")
  if [ ! -s "arena/logs/${P}_analyst.log" ] || limit_hit "arena/logs/${P}_analyst.log"; then
    echo ">>> catching up the analyst for $P"
    pw=$(db info "$(cat arena/db/champion.txt)" round)
    [ "$pw" = "$start_round" ] && pwin="arena/work/$P (promoted: $(cat arena/db/champion.txt))" || pwin=none
    analyst_step "$P" "$pwin" || { echo "still limited - stopping."; exit 0; }
  fi
fi
for ((r = start_round + 1; r <= start_round + ROUNDS; r++)); do
  [ -f arena/STOP ] && { echo "STOP file found"; break; }
  R=$(printf "r%02d" "$r")
  echo "================ round $R  $(date '+%F %T') ================"

  # ---- 1. builders, in parallel: parent + context from the program database -------------
  mapfile -t DIRS < <(grep -v '^\s*$' arena/directions.txt | head -n "$BUILDERS")
  pids=()
  for i in "${!DIRS[@]}"; do
    n=$((i + 1)); w="arena/work/$R/cand_$n"; mkdir -p "$w"
    dir=${DIRS[$i]}; area=$(printf '%s' "${dir%%:*}" | tr -cd 'A-Za-z_-' | cut -c1-24); [ -n "$area" ] || area=MISC
    model=${MODELS[$(( i % ${#MODELS[@]} ))]}
    read -r pid ppath < <(db parent "$n" "${#DIRS[@]}" "$r")
    if [ "$ppath" != "$PWD/my_team.py" ]; then   # island step: continue a near-miss lineage
      area=$(db info "$pid" area)
      dir="CONTINUE $area: finish near-miss $pid (see CONTEXT.md) - its idea was: $(db info "$pid" direction) -- Find what kept it below the promotion bar (its lost games, timing, bugs) and fix that; keep what worked."
    fi
    cp "$ppath" "$w/my_team.py"; cp "$ppath" "$w/parent.py"
    printf '%s\n' "$pid" > "$w/parent_id"; printf '%s\n' "$area" > "$w/area"
    printf '%s\n' "$dir" > "$w/direction"; printf '%s\n' "$model" > "$w/model"
    db context "$pid" "$area" "$w/CONTEXT.md"
    prompt="$(sed -e "s|{{FILE}}|$w/my_team.py|g" -e "s|{{NOTES}}|$w/NOTES.md|g" \
                  -e "s|{{CONTEXT}}|$w/CONTEXT.md|g" -e "s|{{BUDGET}}|$BUILDER_TIMEOUT|g" arena/prompts/builder.md)

YOUR DIRECTION FOR THIS ROUND:
${dir}"
    echo "builder $n: model=$model parent=$pid area=$area"
    ARENA_WORKERS=$BUILDER_WORKERS timeout --kill-after=60 "$BUILDER_TIMEOUT" \
      claude -p "$prompt" --model "$model" "${CF[@]}" > "arena/logs/${R}_cand_$n.log" 2>&1 &
    pids+=($!)
  done
  for p in "${pids[@]}"; do wait "$p" || echo "builder $p exited non-zero or timed out (continuing)"; done
  limited=0
  for i in "${!DIRS[@]}"; do limit_hit "arena/logs/${R}_cand_$((i + 1)).log" && limited=1; done
  if [ "$limited" = 1 ]; then
    changed=0
    for w in arena/work/$R/cand_*; do cmp -s "$w/my_team.py" "$w/parent.py" || changed=1; done
    if [ "$changed" = 0 ]; then
      echo ">>> Claude usage limit hit and no builder produced anything - round $R discarded, stopping."
      echo "    $(grep -hioE 'resets [^.]*' arena/logs/${R}_cand_*.log | head -1)"
      rm -rf "arena/work/$R"; rm -f arena/logs/${R}_*
      break
    fi
    echo ">>> Claude usage limit hit mid-round - evaluating what the builders produced, then stopping."
  fi

  # ---- 2. evaluation cascade: smoke -> SPRT vs champion -> regression --------------------
  past=(arena/opponents/*/my_team.py)
  recent=("${past[@]: -$CHAMPS_IN_GATE}")
  [ "${#past[@]}" -le "$CHAMPS_IN_GATE" ] && recent=("${past[@]}")
  passed=()
  for w in arena/work/$R/cand_*; do
    if cmp -s "$w/my_team.py" "$w/parent.py"; then status=unchanged
    elif ! syntax_ok "$w/my_team.py"; then status=invalid
    else
      $PY arena/arena.py "$w/my_team.py" --opponents pacman-contest/src/contest/baseline_team.py \
          --games "$SMOKE_GAMES" --seed "$r" --json "$w/smoke.json" > "$w/smoke.txt" || true
      if ! $PY arena/pick.py --clean "$w/smoke.json"; then status=smoke_fail
      else
        echo "$w: SPRT vs champion"
        $PY arena/arena.py "$w/my_team.py" --opponents my_team.py --sprt --s0 "$SPRT_S0" --s1 "$SPRT_S1" \
            --alpha "$SPRT_ALPHA" --beta "$SPRT_BETA" --max-games "$SPRT_MAX" --seed $((r * 100)) \
            --json "$w/sprt.json" | tee "$w/sprt.txt" || true
        case "$($PY arena/pick.py --sprt "$w/sprt.json")" in
          H1) status=passed ;;
          H0) status=rejected ;;
          inconclusive) status=inconclusive ;;
          *) status=unclean ;;
        esac
      fi
    fi
    if [ "$status" = passed ]; then
      $PY arena/arena.py "$w/my_team.py" --opponents pacman-contest/src/contest/baseline_team.py "${recent[@]}" \
          --games "$REGRESS_GAMES" --seed $((r + 500)) --json "$w/regress.json" | tee "$w/regress.txt" || true
      passed+=("$w")
    fi
    echo "$w: $status"
    printf '%s\n' "$status" > "$w/status"
  done
  winner=""
  [ "${#passed[@]}" -gt 0 ] && winner=$($PY arena/pick.py --select "$REGRESS_MIN" "${passed[@]}" || true)

  # ---- 3. archive every candidate in the program DB, promote the winner --------------------
  for w in arena/work/$R/cand_*; do
    st=$(cat "$w/status")
    if [ "$st" = passed ]; then
      if [ -n "$winner" ] && [ "$(dirname "$winner")" = "$w" ]; then st=passed
      elif $PY arena/pick.py --select "$REGRESS_MIN" "$w" 2>/dev/null | grep -q .; then st=not_chosen
      else st=regress_fail; fi
    fi
    db add "${R}$(basename "$w" | tr -d '_')" "$r" "$st" "$w/my_team.py" \
       --area "$(cat "$w/area")" --direction "$(cat "$w/direction")" --model "$(cat "$w/model")" \
       --parent "$(cat "$w/parent_id")" --smoke "$w/smoke.json" --sprt "$w/sprt.json" \
       --regress "$w/regress.json" --notes "$w/NOTES.md" || echo "WARNING: db add failed for $w"
  done
  if [ -n "$winner" ]; then
    echo ">>> promoting $winner"
    mkdir -p "arena/opponents/champ_$R"; cp my_team.py "arena/opponents/champ_$R/my_team.py"   # freeze old champ
    cp "$winner" my_team.py
    db promote "${R}$(basename "$(dirname "$winner")" | tr -d '_')"
    commit "Round $R: promote $(basename "$(dirname "$winner")")" my_team.py arena/opponents
  else
    echo ">>> no candidate beat the champion this round"
  fi

  # ---- 4+5. curriculum focus, then analyst (skipped if the usage limit is already hit) ------
  if [ "$limited" = 1 ]; then
    echo ">>> analyst for $R deferred (usage limit): it runs first thing on the next start."
    echo "    $(grep -hioE 'resets [^.]*' arena/logs/${R}_cand_*.log | head -1)"
    break
  fi
  analyst_step "$R" "${winner:-none}" || break
done
echo "done. champion = my_team.py"
