# Autonomous builder loop

```
pacman-agent/
  my_team.py            <- champion; this is what the organisers load
  CLAUDE.md             <- rules + constraints every agent reads
  arena/
    arena.py            <- evaluator (parallel games, colour-swapped pairs, crash/timeout/forfeit
                           counts, SPRT, per-game play statistics)
    run_game.py         <- runs one game like capture.py and records banked/conceded food, deaths
    pick.py             <- promotion gate
    db.py               <- program database (every candidate + scores, builder context)
    tune.py             <- SPSA tuner for the champion's numeric constants (games only, no Claude)
    loop.sh             <- the loop
    prompts/builder.md, prompts/exploiter.md, prompts/analyst.md
    opponents/champ_*/  <- frozen past champions (created by the loop)
    opponents/exploit_*/ <- league: exploiters that beat a champion (created by the loop)
    opponents/ext_*/    <- league: teams of a different style (ext_rush, ext_turtle; add your own)
    opponents/ext_gh_*/ <- the FIELD: 12 third-party past contest entries (gitignored, fetch_ext.sh)
    ext_teams.txt, fetch_ext.sh, benchmark.sh, bench_report.py  <- train/bench split of third-party teams, held-out benchmark (pooled across runs)
    LEARNINGS.md, directions.txt (created by the loop, rewritten by the analyst)
```

## Setup (Windows: everything runs inside WSL Ubuntu)
The contest engine needs Linux (`signal.SIGALRM` timeouts, symlinks), so run all of this in WSL.
```bash
cd /mnt/c/<path-to>/pacman-agent
sudo add-apt-repository -y ppa:deadsnakes/ppa && sudo apt-get install -y python3.8 python3.8-venv python3.8-distutils
python3.8 -m venv venv && source venv/bin/activate
git submodule update --init --remote
(cd pacman-contest && pip install -e . && pip install -r requirements.txt)
python3 arena/arena.py my_team.py --quick      # sanity check: should print a W/T/L table
```
Claude Code must be installed **inside WSL** (the Windows `claude.exe` would run builders' commands
with Windows Python, which cannot play games): `curl -fsSL https://claude.ai/install.sh | bash`,
then run `claude` once interactively to log in.
Git identity inside WSL (otherwise promotions are not committed):
`git config --global user.name ...; git config --global user.email ...`

## Run
```bash
source venv/bin/activate
ROUNDS=4 BUILDERS=3 bash arena/loop.sh                    # model defaults to claude-opus-5-5
ANALYST_MODEL=claude-fable-5-2 ROUNDS=4 bash arena/loop.sh
PUSH=1 ROUNDS=4 bash arena/loop.sh                        # push every promotion to GitHub
touch arena/STOP                                          # finish the current round, then stop
```
Ctrl-C is safe too: a round interrupted before its evaluation is discarded and redone on the next
start, and a missing analyst run is caught up. The next round number comes from the program
database, so deleting `arena/work/rNN` by hand never makes the loop reuse a round number.

## How a round works
1. **Program database** (`arena/db.py`, after AlphaEvolve). Every candidate is archived with its
   scores. Builder i gets a `CONTEXT.md` describing its starting program and where that program
   loses, the best past program per strategy area ("inspirations"), the league opponents, and
   recent failures. With 3 or more normal builders, the last one continues the previous round's best
   near-miss (an island step) instead of starting from the champion.
2. **Builders** (parallel Claude sessions) each edit their own copy, following one line of
   `directions.txt`: one idea, implemented as a small change. They also read `arena/KNOWLEDGE.md`
   (the research digest) and can copy tested code from `arena/snippets/`.
   **Exploiter** (after AlphaStar's league): every `EXPLOIT_EVERY`-th round (2) the last builder
   slot gets `prompts/exploiter.md`. Its only goal is to beat the champion, with any strategy; it
   can read the champion's source. The analyst can steer it with a line starting `EXPLOIT:`.
3. **Evaluation cascade**, cheap to expensive:
   - smoke: 2 games vs the baseline, which must have no crash, timeout or forfeit;
   - **SPRT vs the champion**: colour-swapped game pairs until the result is statistically decided,
     16-300 games, bounds [50%, 55%];
   - regression: 12 games each vs the baseline, the 2 most recent past champions (score >= 30%
     against each) and the league: the 3 most recent exploiters and every `ext_*` team (>= 20%:
     they may beat the champion legitimately, so only a collapse counts);
   - **field**: 24 games each vs the 12 third-party training teams (`ext_gh_*`). The champion
     plays the identical games once per round. The candidate must not be measurably worse (the
     paired 95% interval may not be entirely below 0) and must score >= 75% combined. This stage
     exists because, on 2026-11-17, a tuned version that beat the old champion 71.7% head-to-head
     was +0.4 +- 2.6 points against held-out teams.
4. **Promote** the passing candidate with the best SPRT score: freeze the old champion and commit.
   An exploiter whose SPRT beat the champion (and was not itself promoted) is frozen into
   `arena/opponents/exploit_rNN/` with its NOTES: from then on every candidate plays it.
5. **Analyst** updates `LEARNINGS.md` and rewrites `directions.txt` (the evolving meta-prompt).
   If `arena/focus.txt` exists (a curriculum focus), the first BUILDERS lines must use its prefixes.
   The loop enforces this after the analyst runs, reordering lines or restoring the previous file.
   The focus is released automatically after `FOCUS_STALL` (1) round without a promotion, not
   before round `FOCUS_MIN_ROUNDS` (3). (The old release rule, "champion beats the baseline by
   75%", was useless: round 1 already scored 100%.) Delete the file to drop the focus by hand, or
   write a new one to start another.

## How games are measured
Every game also records, from the candidate's side (via `arena/run_game.py`, which watches the
real game states without modifying the engine): **bank** food returned, **conc** food the opponent
returned, **died** our Pacman deaths, **drop** food dropped on those deaths, **kill** enemy Pacmen
eaten. Per game, score = bank - conc exactly. The arena tables show per-game averages, and the
JSON reports keep each game's numbers. Builders, the analyst and the database all see them, so a
loss can be explained ("dies carrying 6 dots on fastCapture") rather than only counted.

Why SPRT: contest points % depends on the tie rate. In simulation, at the ~60% tie rate we see, the
old fixed gate (24 games at 55% points, plus confirmation) promoted a truly better team (60% score)
only 10% of the time. The SPRT keeps false promotions near 5% at any tie rate. Simulated with
bounds [0.50, 0.55] and 300 games max: equal candidate promoted 3-4%, a 57% one 67-81% (it was
38-48% with [0.50, 0.60] and 120 games), a 60% one 95-98%. A no-better candidate costs ~200 games,
a few minutes of CPU: cheap next to a builder session.

## Tuning constants (SPSA, no Claude usage)
`arena/tune.py` tunes every top-level `NAME = number` line of a team (builders are told to keep
tunable constants in that form) with SPSA, as Stockfish's fishtest does. It uses self-play game
pairs, theta+ vs theta-, with shrinking steps. A variant that crashes or gets a timeout warning
loses its pair.
```bash
python3 arena/tune.py --list                     # what would be tuned, with ranges
python3 arena/tune.py --pairs 3000               # ~1 h on 12 cores; Ctrl-C keeps state
python3 arena/tune.py --pairs 6000 --resume      # continue (e.g. overnight)
python3 arena/arena.py arena/tune/tuned.py --opponents my_team.py --sprt   # MUST pass before use
python3 arena/arena.py arena/tune/tuned.py --games 12                      # no collapse elsewhere
cp arena/tune/tuned.py my_team.py                # promote by hand, then commit
```
Do not run it while the loop runs, because both use all cores and slow moves become timeout
warnings. Run it between loop runs, for example while the Claude usage limit resets.

## Knobs
- `SPRT_S0`/`SPRT_S1`: H0 and H1 score per game (win 1, tie 0.5), defaults 0.50/0.55.
- `SPRT_ALPHA`/`SPRT_BETA`: 0.05/0.10. `SPRT_MAX`: 300 games.
- `REGRESS_GAMES`/`REGRESS_MIN`: 12 games, 30% score vs the baseline and each recent champion.
  This is a collapse check, not a strength test. `REGRESS_LEAGUE_MIN`: 20% vs league opponents.
  `FIELD_GAMES`/`REGRESS_FIELD_MIN`: 24 paired games per `ext_gh_*` team, 75% combined.
- `CHAMPS_IN_GATE`: recent champions in the regression stage, 2. `LEAGUE_EXPLOITS`: recent
  exploiters in it, 3.
- `EXPLOIT_EVERY`: exploiter every Nth round, 2 (0 = off; needs BUILDERS >= 2).
- `NEAR_MISS`: SPRT score % that makes a candidate worth continuing, 52.
- `MODEL` (claude-opus-5-5), `BUILDER_MODELS`: comma list, builder i uses entry i.
  `ANALYST_MODEL`: defaults to MODEL.
- `BUILDER_TIMEOUT`: 45m. `ANALYST_TIMEOUT`: 20m.
- `FOCUS_STALL`/`FOCUS_MIN_ROUNDS`: 1/3.
- `BUILDER_WORKERS`: arena workers per builder, default nproc/BUILDERS.
- `CLAUDE_FLAGS`: replaces the permission flags; `--model` is always passed separately.

## Outside opponents: training set and held-out benchmark
26 public forks of the UPF template hold past contest entries in the same API. `arena/ext_teams.txt`
splits them, by strength and style (one of each matched pair per side), into:
- **train** (11): `bash arena/fetch_ext.sh` downloads every team into `arena/ext_pool/` (pinned to a
  commit) and installs these as `arena/opponents/ext_gh_*`. The loop's field stage plays all of
  them. The tuner splits them each day into two halves of similar strength: its pool plays one
  half, and its gate's field stage plays only the other (48 games each), so the gate checks teams
  the tuner did not optimise against (`--field-split off` turns this off).
- **bench** (9): the held-out benchmark. The loop and the tuner never play them.
  `bash arena/benchmark.sh` plays the champion and the previous champion on identical games
  (24 per team) and prints both scores and the paired difference with a 95% interval. Repeat runs
  with another seed (`SEED=2027 bash arena/benchmark.sh`) are pooled game by game for the same pair
  of files (matched by md5): read the POOLED line, since one run (about ±2.5 points) rarely settles
  a 1-2 point difference. `python3 arena/bench_report.py --pool` prints it without playing. If the
  gate and tuner scores rise while the benchmark stays flat or drops, the loop is overfitting. Run
  it nightly or before a push, and never use it to choose between candidates.
- **drop** (6): 4 beaten by 30+ points (no signal), 2 that crash in most games. Games in which an
  opponent crashes or forfeits (the `oppX` column) are free wins and are left out of every
  field and benchmark comparison.

Rules: their code is gitignored and never committed, copied or read (builder, exploiter and analyst
prompts forbid it). We only play against them. The repos have no licence and the organisers can
compare submissions with earlier years' entries.

**Switch-off tests** (`arena/ablate.py`, unattended: `arena/start_ablate.sh`): flips one switch
or constant of the champion at a time (HELP_ON, TRAP_ON, GUARD_CAPS, INVADER_SNAP, ROUTE_ON,
LANE_SPLIT, DOUBLE_ATTACK, GHOST_MEM, TURTLE_LEAD 1 → 3, SAFE_RETURN on) and plays it paired with the
champion against the training field. Racing: variants that are clearly worse stop after one seed,
and the close ones get more. Verdicts are NEEDED, NOT MEASURABLE (a removal candidate) or OFF IS
BETTER. Report: `arena/ablate/REPORT.md`. No Claude usage.

**Failure miner** (`arena/mine.py`): groups the champion lineage's losses against outside teams by
pattern (OUT_RACED, DIED_LOADED, OUT_SCORED, STARVED, CLOSE), opponent, layout and colour, from
reports already on disk. `--record N` re-plays the worst cells and saves replays to
`arena/mine/replays/`. The loop refreshes `arena/mine/REPORT.md` before every analyst run, and the
analyst reads it.

You can still add any team by hand at `arena/opponents/ext_<name>/my_team.py`: it joins the league.
After the test round (23 Nov), the teams and layouts we lost to are the best additions.

Manual SPRT of any file against the champion:
`python3 arena/arena.py FILE --opponents my_team.py --sprt`

Logs per agent: `arena/logs/rNN_cand_i.log`, `arena/logs/rNN_analyst.log`.
Each candidate's notes and gate report: `arena/work/rNN/cand_i/`.
