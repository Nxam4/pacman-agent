# Learnings (maintained by the analyst agent)

Champion history: seed (r00: tracker defender + nearest-food reflex attacker) -> **r01cand1**
(BankingAttacker, defender unchanged). Past programs: `arena/db/progs/<id>.py`.

## Standing facts
- **EnemyTracker works** (inside my_team.py). Best guess of a hidden enemy is off by 3.2 cells on
  average (12.1 for "last seen"); true cell inside the belief 98.5% of the time; ~0.4 ms per update.
- **Tracker-driven defender (r00)**: with no invader visible it heads for the tracker's most likely
  invader cell / the border cell nearest the likely enemy. Enough to beat the starter (56.4%, SPRT H1).
- The gate is SPRT on score% (win 1, tie 0.5) vs the champion, then a regression check vs baseline
  and older champions. Builders' own --quick numbers are small samples; do not rely on them.
- Ties were 60-85% between the reflex-level teams. That is over once an attacker banks food:
  r01 gate games had **0 ties in 64 games**. From now on the margin comes from how much food is
  banked and how much the defender concedes, not from breaking 0-0.

## Round 1 (2026-11-16) - attacker round, gate results
- **A provably-safe planning attacker is a huge step.** Two independent implementations both scored
  18-0-2 (90%) vs the seed in 20 SPRT games and 12-0-0 vs the baseline, no crashes, no timeouts.
  Common core: a time-aware search in which an enemy-side cell is usable only if no defender
  (visible position, or tracker most-likely cell when hidden) can reach it before us; eat a dot
  only if a safe way home or to a capsule still exists afterwards; go home when moves left barely
  cover the trip.
- **r01cand1 (promoted, OFFENSE-BANK)**: safe BFS + fixed carry caps (2 on the first trip, 5 later,
  1 with a defender within 5). Average margin +20.3 vs seed, +18.8 vs baseline.
- **r01cand2 (not chosen only by tie-break, OFFENSE-PATH)**: Dijkstra with hard block + soft
  proximity cost, hidden defenders as soft cost from the top-8 belief cells, cluster bonus for food
  choice, carry budget that shrinks with carried food (12 - 2*carrying), capsule only when a
  defender is within 6 and unlimited carry while defenders are scared. Same 90% but **larger and
  steadier margins: +27.95 vs seed, +22.2 vs baseline**; on the same layouts it beat cand1's margin
  on strategicCapture (31 vs 18), crowdedCapture (60 vs 44, cand1 had one +9 game), fastCapture
  (8 vs 2.5). Games ran ~35% slower in wall-clock (still no warnings). These features are NOT in
  the champion - porting them is the cheapest known gain (`arena/db/progs/r01cand2.py`).
- **Fixed carry caps leave food on the table**: cand1's cap of 5 vs cand2's distance/danger budget
  is the most likely cause of the margin gap (inference from the two designs, not an ablation).
- **SEARCH (junction MCTS) was never tested.** The builder hit the usage limit before writing any
  code (status unchanged). No evidence for or against; retry.
- All three builders were cut off by the usage limit (cand1's NOTES still say "measurements
  pending"). Builders should write working code to my_team.py early and improve in small steps.

## Known failure patterns
- **RANDOM404807: both candidates lost BOTH colours to the seed by 15-20 points** (cand1 -20/-19,
  cand2 -15/-15), the only losses of the round. The map has a solid wall along the border with only
  two crossings (top row and bottom row), each a long corridor. Two things go wrong at once:
  (a) the safe planner finds no provably safe entry and idles at home - in the champion the
  stalemate branch only slides along the border and relaxes the safety test by at most 4 steps
  (`stuck // 8`, capped), so it banks about nothing; (b) the unchanged defender concedes ~15-20
  dots to a plain nearest-food reflex attacker on this map. Reproduce:
  `cd pacman-contest/src/contest && python capture.py -r ../../../my_team.py -b ../../../arena/db/progs/seed.py -l RANDOM404807 -q`
- **Low-margin layouts for the champion**: fastCapture vs baseline (+2, +3), distantCapture vs seed
  (+13, +1). Small maps / long trips: few banked dots, so one conceded dot flips the game.
- A dumb attacker that just walks in can still outscore a careful one when the defender is weak:
  "never take a risk" is wrong when carrying 0 (dying with nothing costs only the walk back).

## Open questions (untested)
- Mirror matches (champion vs a near-copy) have not been played yet: expect ties and narrow games
  to return, decided by the defender and by who banks faster. Margins vs seed/baseline say little
  about that.
- Whether search (MCTS / playouts, KNOWLEDGE sec. 2 + 6) beats the rule-based safe planner.
- Second agent: the defender never attacks, even when no invader exists (held back by curriculum).
