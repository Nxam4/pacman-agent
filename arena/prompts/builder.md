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
To keep a backup before a risky change: cp {{FILE}} {{FILE}}.bak  (restore with cp the other way).

Goal: make {{FILE}} beat the current champion more often, without ever crashing, forfeiting, or
getting a timeout warning. After you finish, an evaluation cascade runs:
  1. 2 smoke games vs the baseline - any crash / forfeit / timeout warning ends it here;
  2. an SPRT (sequential test, as used for the Stockfish chess engine) vs the champion: colour-swapped
     game pairs are played until it is statistically clear whether your file scores >= 60% (win 1,
     tie 0.5) or is no better - 16 to 120 games; big improvements are decided fast;
  3. 12 regression games each vs the baseline and recent past champions (must not collapse).
Every evaluated program is archived with its scores; an inconclusive near-miss may be continued by a
builder next round, so even a partial success is useful. A file identical to its start is skipped.

Time budget: you are stopped after {{BUDGET}}. Write a first version of {{NOTES}} early and keep it
updated, so a timeout does not lose your findings. Prefer one well-measured idea over three untested ones.

Work loop (repeat until you have a clear improvement or have used ~6 iterations):
1. Form a hypothesis about a weakness, guided by your direction below. Watching what actually happens
   helps: arena reports which layouts were lost.
2. Implement it in {{FILE}}.
3. Measure quickly:   python3 arena/arena.py {{FILE}} --opponents my_team.py pacman-contest/src/contest/baseline_team.py --quick
   (8 games per opponent, colour-swapped pairs; very noisy - only a big difference means anything).
4. Before concluding an idea works, run the same test the loop will run:
      python3 arena/arena.py {{FILE}} --opponents my_team.py --sprt --max-games 60
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

Before you finish:
- Run one final  python3 arena/arena.py {{FILE}} --games 16  (all opponents) and confirm
  crash = 0, slow = 0 and forfeit = 0.
- Finalise {{NOTES}}: what you tried, the measured results of each idea (including failures, with the
  numbers), and what you'd try next. Be concrete and short; the analyst agent reads this.
