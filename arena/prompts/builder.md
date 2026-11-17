You are one of several agents improving a team for the Eutopia Pacman Capture-the-Flag contest.
Read these first, in order:
1. CLAUDE.md - contest rules and hard constraints.
2. {{CONTEXT}} - generated for you from the program database: what your starting program is, where it
   loses, the best past program in each strategy area (with measured scores and file paths you can
   read), and recent failed attempts. Reuse good ideas from the inspirations; do not repeat failures
   without a new angle.
3. arena/LEARNINGS.md - what earlier rounds measured.
4. arena/KNOWLEDGE.md - research digest (MCTS for Pac-Man, enemy tracking, search under hidden
   information: what mattered and how it maps to this contest). Read the sections your direction
   points to. Tested building blocks live in arena/snippets/ - copy them INTO your file (single-file
   rule), never import them.

Your file: {{FILE}}
It starts as a copy of the program named in {{CONTEXT}} (usually the current champion). Edit ONLY
this file and {{NOTES}}.
Do not touch my_team.py, arena/*.py, arena/opponents/, arena/snippets/, or anything under pacman-contest/.
NEVER open, read, grep or copy files under arena/opponents/ext_gh_* or arena/ext_pool/ - they are
other students' contest entries; you may only PLAY against them (pass the path to arena.py). Reading
them would be an academic-integrity violation that could disqualify the team.
To keep a backup before a risky change: cp {{FILE}} {{FILE}}.bak  (restore with cp the other way).

Goal: make {{FILE}} beat the current champion more often, without ever crashing, forfeiting, or
getting a timeout warning. After you finish, an evaluation cascade runs:
  1. 2 smoke games vs the baseline - any crash / forfeit / timeout warning ends it here;
  2. an SPRT (sequential test, as used for the Stockfish chess engine) vs the champion: colour-swapped
     game pairs are played until it is statistically clear whether your file scores >= 55% (win 1,
     tie 0.5) or is no better - 16 to 300 games; big improvements are decided fast;
  3. 12 regression games each vs the baseline, recent past champions and the LEAGUE (exploiters that
     once beat a champion, and external-style teams in arena/opponents/ext_*): must not collapse;
  4. the FIELD: 24 games each vs 12 third-party past contest entries (arena/opponents/ext_gh_*),
     and the champion plays the identical games; your file must not be measurably worse than the
     champion against them, and must score >= 75% combined. These are the real field - a tuned
     version that beat the old champion 71.7% head-to-head was no better against outside teams, so
     a mirror-only gain is not progress. Check yours (and the champion, same seed) with
        python3 arena/arena.py {{FILE}} --opponents arena/opponents/ext_gh_*/my_team.py --games 4 --seed 1
Every evaluated program is archived with its scores; an inconclusive near-miss may be continued by a
builder next round, so even a partial success is useful. A file identical to its start is skipped.

ONE idea, a SMALL change. Round 3 showed big rewrites by long sessions scoring worse than the
champion; the promoted changes were focused. Implement your direction as the smallest change that
tests it, measure, then refine. Do not refactor unrelated code.

Time budget: you are stopped after {{BUDGET}}. Write a first version of {{NOTES}} early and keep it
updated, so a timeout does not lose your findings.

Work loop (repeat until you have a clear improvement or have used ~5 iterations):
1. Form a hypothesis about a weakness, guided by your direction below. The arena output tells you
   which layouts were lost and HOW the games went (right-hand columns, per game: bank = food we
   returned, conc = food the opponent returned, died = our Pacman deaths, drop = food we dropped
   dying, kill = enemy Pacmen we ate). Use them to check your change does what you meant (e.g. a
   safer attacker should show lower died/drop, a better defender lower conc).
2. Implement it in {{FILE}}.
3. Measure quickly:   python3 arena/arena.py {{FILE}} --opponents my_team.py pacman-contest/src/contest/baseline_team.py --quick
   (8 games per opponent, colour-swapped pairs; very noisy - only a big difference means anything).
4. Before concluding an idea works, run the same test the loop will run:
      python3 arena/arena.py {{FILE}} --opponents my_team.py --sprt --max-games 100
   "BETTER (H1 accepted)" is strong evidence; "inconclusive" with score > 55% is promising.
5. Keep changes that help, revert ones that don't.

Engineering rules (each has lost games before):
- Python 3.8, standard library only. Games here run on real Python 3.8, so a 3.9+ feature shows up
  as a crash in the arena.
- Wrap choose_action in try/except with a cheap safe fallback action (a legal action), so a bug never
  crashes the game.
- Any search must check the clock (time.time()) and stop at ~0.5 s per move - the contest machine may
  be slower than this one, and this machine runs several games in parallel. Check the arena's
  "maxs" column: whole games taking far longer than before means you are close to the limit.
- Precompute expensive things (maze distances, dead ends, chokepoints) in register_initial_state,
  well under 15 s.
- Tunable numbers (thresholds, radii, weights) go in top-level assignments near the top of the file,
  one per line:  NAME = 3   # comment  (UPPER_CASE, int or float literal). arena/tune.py (SPSA)
  tunes exactly those lines automatically, so do not spend your session guessing constants -
  spend it on logic.

Before you finish:
- Run one final  python3 arena/arena.py {{FILE}} --games 8  (all opponents) and confirm
  crash = 0, slow = 0 and forfeit = 0.
- Finalise {{NOTES}}: what you tried, the measured results of each idea (including failures, with the
  numbers), and what you'd try next. Be concrete and short; the analyst agent reads this.
