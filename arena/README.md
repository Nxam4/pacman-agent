# Autonomous builder loop

```
pacman-agent/
  my_team.py            <- champion; this is what the organisers load
  CLAUDE.md             <- rules + constraints every agent reads
  arena/
    arena.py            <- evaluator (parallel games, colour-swapped pairs, crash/timeout/forfeit counts)
    pick.py             <- promotion gate + confirmation check
    loop.sh             <- the loop
    prompts/builder.md, prompts/analyst.md
    opponents/champ_*/  <- frozen past champions (created by the loop)
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
ROUNDS=4 BUILDERS=3 bash arena/loop.sh                    # model defaults to claude-fable-5-2
MODEL=claude-opus-5-5 ROUNDS=4 bash arena/loop.sh
MODEL=claude-fable-5-2 ANALYST_MODEL=claude-opus-5-5 bash arena/loop.sh
PUSH=1 ROUNDS=4 bash arena/loop.sh                        # push every promotion to GitHub
touch arena/STOP                                          # finish the current round, then stop
```
## How a round works
1. **Program database** (`arena/db.py`, after AlphaEvolve). Every candidate is archived with its
   scores. Builder i gets a `CONTEXT.md` describing its starting program and where that program
   loses, the best past program per strategy area ("inspirations"), and recent failures. With 3 or
   more builders, the last builder continues the previous round's best near-miss (an island step)
   instead of starting from the champion.
2. **Builders** (parallel Claude sessions) each edit their own copy, following one line of
   `directions.txt`. They also read `arena/KNOWLEDGE.md` (the research digest) and can copy tested
   code from `arena/snippets/`.
3. **Evaluation cascade**, cheap to expensive:
   - smoke: 2 games vs the baseline, which must have no crash, timeout or forfeit;
   - **SPRT vs the champion**: colour-swapped game pairs until the result is statistically decided,
     16-120 games;
   - regression: 12 games each vs the baseline and recent past champions.
4. **Promote** the passing candidate with the best SPRT score: freeze the old champion and commit.
5. **Analyst** updates `LEARNINGS.md` and rewrites `directions.txt` (the evolving meta-prompt).
   If `arena/focus.txt` exists (a curriculum focus, currently on the attacker), the first BUILDERS
   lines must use its prefixes. The loop enforces this after the analyst runs, reordering lines or
   restoring the previous file. The focus is released automatically once the champion scores at
   least `FOCUS_BASELINE`% (75) vs the baseline, or after `FOCUS_STALL` (2) rounds with no
   promotion. Delete the file to drop the focus by hand, or write a new one to start another.

Why SPRT: contest points % depends on the tie rate. In simulation, at the ~60% tie rate we see, the
old fixed gate (24 games at 55% points, plus confirmation) promoted a truly better team (60% score)
only 10% of the time. The SPRT keeps false promotions near 5% at any tie rate, and promotes a 60%
team 65-87% of the time and a 65% team 96-99% of the time.

Knobs:
- `SPRT_S0`/`SPRT_S1`: H0 and H1 score per game (win 1, tie 0.5), defaults 0.50/0.60. Lower S1
  (for example 0.55) once the easy gains are gone; that costs more games.
- `SPRT_ALPHA`/`SPRT_BETA`: 0.05/0.10.
- `SPRT_MAX`: 120 games.
- `REGRESS_GAMES`/`REGRESS_MIN`: 12 games, 30% score vs each regression opponent. This is a
  collapse check, not a strength test.
- `CHAMPS_IN_GATE`: recent champions in the regression stage, 2.
- `NEAR_MISS`: SPRT score % that makes a candidate worth continuing, 52.
- `BUILDER_MODELS`: comma list, builder i uses entry i, for example a strong+fast mix
  `claude-fable-5-2,claude-fable-5-2,claude-sonnet-5-5`.
- `BUILDER_TIMEOUT`: 90m. `ANALYST_TIMEOUT`: 20m.
- `BUILDER_WORKERS`: arena workers per builder, default nproc/BUILDERS.
- `CLAUDE_FLAGS`: replaces the permission flags; `--model` is always passed separately.

Manual SPRT of any file against the champion:
`python3 arena/arena.py FILE --opponents my_team.py --sprt`

Logs per agent: `arena/logs/rNN_cand_i.log`, `arena/logs/rNN_analyst.log`.
Each candidate's notes and gate report: `arena/work/rNN/cand_i/`.
