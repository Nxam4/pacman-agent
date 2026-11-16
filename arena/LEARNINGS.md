# Learnings (maintained by the analyst agent)

Champion history: seed (r00: tracker defender + nearest-food reflex attacker) -> r01cand1
(BankingAttacker with hard safety guarantees) -> **r02cand1** (r01cand2's soft-cost Dijkstra attacker
+ try/except defender + invader snap). Defender logic is still the r00 one.
Past programs: `arena/db/progs/<id>.py`.

## Standing facts
- **EnemyTracker works** (inside my_team.py). Best guess of a hidden enemy is off by 3.2 cells on
  average (12.1 for "last seen"); true cell inside the belief 98.5% of the time; ~0.4 ms per update.
- **Tracker-driven defender (r00)**: with no invader visible it heads for the tracker's most likely
  invader cell / the border cell nearest the likely enemy. Beat the starter (56.4%, SPRT H1) but is
  now the weakest part of the team (see round 2 and failure patterns).
- The gate is SPRT on score% (win 1, tie 0.5) vs the champion, then a regression check vs baseline
  and older champions. **Builders' own numbers do not replicate**: r02cand3 reported "SPRT H1, 68.8%
  in 32 games"; the gate measured 57.1% in 120 games (inconclusive). Under ~60 games trust nothing
  smaller than ~15 points.
- Ties are rare once attackers bank food (r01 gate: 0/64; r02 gates: 2/30, 7/40, 15/120 - the ties
  that remain are on fastCapture/alleyCapture). Games are decided by margin: food banked vs conceded.
- Timing is not a constraint yet: champion games take ~3-7 s wall-clock in total, no warnings in
  any gate game this round (310 games). The MC candidate ran ~2x slower (max 12.4 s), still clean.

## Round 1 (2026-11-16) - attacker round
- A planning attacker that banks food is a huge step over the reflex attacker: two independent
  designs both scored 18-0-2 (90%) vs the seed and 12-0-0 vs the baseline.
- r01cand1 (promoted): time-aware safe BFS (enemy cell usable only if no defender - visible, or the
  tracker's most-likely cell when hidden - can reach it first; eat only if a safe way home remains),
  fixed carry caps 2/5/1. r01cand2: Dijkstra with hard block only vs visible defenders, soft cost
  near top-8 belief cells, cluster bonus, carry budget max(2, 12 - 2*carried), no carry limit while
  defenders are scared. Same 90% vs seed, larger margins.

## Round 2 (2026-11-16) - attacker round, gate results (all vs r01cand1)
- **r02cand1 (promoted, OFFENSE-PATH): 24-2-4, 83.3% in 30 games, avg +6.4**; regression 12-0-0 vs
  baseline (avg +19.8) and 12-0-0 vs champ_r01 (avg +18.2). It is r01cand2's attacker taken whole.
- **Hard "provably safe" rules cost more than they save** (builder ablations, 24 games each, same
  layouts, consistent in direction and the final design confirmed by the gate):
  - porting carry budget + cluster bonus + belief soft cost into the r01 safe-BFS attacker while
    keeping hidden defenders a hard threat: 45.8% - no gain. Carry budget and cluster bonus are NOT
    what matters head-to-head.
  - same port with hidden defenders never a hard threat: 62.5%. Treating the tracker's guess as a
    wall makes the attacker retreat/idle.
  - r01cand2 attacker + "safe-return" filter (eat only if no visible defender can cut the way home):
    60% in 60 games, collapsed on big maps (jumboCapture -14/+36/-5/-14 vs +66/+70 without it;
    officeCapture all negative). Filter off: 83.3%. The filter assumes a perfect defender that knows
    our route; real defenders do not, so far-from-home food never passes and we go home empty.
  - `SAFE_RETURN = False` is still in the champion - do not switch it back on as it is.
- **Invader snap** (attacker at home, carrying 0, invader within 3 steps -> step toward it): neutral
  to slightly positive, not separately proven (72.9% without vs 83.3% with, 24 games each = noise).
- **r02cand3 (SEARCH, inconclusive): plan-level Monte Carlo on top of the r01 attacker, 61-15-44,
  57.1% in 120 games, avg +2.85.** Not a tree: after the rule plan, 7 nearest foods + capsules + "go
  home" are each scored over 24 sampled defender worlds (hidden ones from EnemyTracker; defenders
  chase within 10 with p=.85, else random); replaces the rule action only if better by 0.25. A real
  but small gain over the OLD champion, far below what dropping the hard rules gave (83%). Untested
  on the new champion. Its results are very swingy on big maps: jumboCapture 27/61/-36/-11/-9/-35/
  30/37, crowdedCapture 9/35/-33/17/26/33/0/8, and it loses distantCapture (sum -22 over 10 games).
  Full junction-tree MCTS (KNOWLEDGE sec. 2) is still untested.
- **r02cand2 (not chosen, 24-7-9, 68.8% in 40 games, avg +4.4) did NOT do its OFFENSE-CHOKE
  direction.** It left the r01 attacker as is and added a defender "exit denial" guard (`_guard`:
  stand where we reach every border cell no later than the invader, close in from there; the
  attacker joins from home when an invader carries >= 4 and both of us together can cover all
  exits). So **a defence-only change was worth +19 points of score% vs r01** - the first measured
  evidence that the defender is a big lever. Caveats: regression lost distantCapture vs champ_r01
  (+1/-3) and margins vs baseline were lower than r02cand1's (+15.8 vs +19.8); a debug print to
  stderr every 6 moves was left in (`# DBGLINE`); NOTES were never written (usage limit). Not yet
  combined with the r02 attacker. Code: `arena/db/progs/r02cand2.py`.
- Builders again hit the usage limit (cand2 had no notes, cand3 skipped per-move timing). Write
  working code first, keep NOTES current, remove debug output before finishing.

## Known failure patterns
- **RANDOM404807 (solid border wall, two crossings, each a long corridor) is still lost - now it
  is a defence problem.** Analyst re-check of champion r02cand1, one game each: vs seed -15 as red
  and -15 as blue, vs baseline -19 as red; the opponent's plain reflex attacker returned all 28
  dots in ~1/3 of the game while we banked ~9-13. Our attacker no longer idles (it beat r01cand1
  here by +17); the game is lost because the r00 defender does not hold two crossings and because
  the game ends as soon as one side has returned all but 2 dots - it is a race we lose.
  Reproduce: `cd pacman-contest/src/contest && python capture.py -r ../../../my_team.py -b ../../../arena/db/progs/seed.py -l RANDOM404807 -q`
- **Small maps are coin flips.** fastCapture: every r02 candidate scored within -2..+2 vs r01
  (cand1 -1/2/1/1, cand2 0/0/-1/2/0/0, cand3 twelve games in -2..2); champion vs champ_r01 +3/+2,
  vs baseline +9/+6. alleyCapture the same (-1/0/1/1). Few dots are reachable, so one conceded dot
  decides the game; attacker changes so far do not move these maps.
- **One death with a big load decides big maps** (jumboCapture, crowdedCapture, officeCapture):
  swings of 60-70 points between games of the same pairing. The champion has no check on the return
  trip at all; the hard check was too pessimistic (above). A middle way is untested.
- defaultCapture vs r01: the champion still lost one of six (-6); RANDOM856825 was lost by all
  three candidates as one colour (-3) - likely a colour-asymmetric map, low priority.

## Open questions (untested)
- A *milder* return-trip check: only when carrying >= ~4, defender must be 2+ steps faster, or
  expected loss from sampled defender worlds (cand3's machinery) instead of a worst-case proof.
- Does MC plan evaluation / junction MCTS add anything on top of the r02 attacker?
- r02cand2's exit-denial defender combined with the r02cand1 attacker (expected to help most on
  choke maps and small maps; held back by the attacker curriculum).
- Mirror matches of the new champion: who banks faster, clock/score-aware risk (never tested).
- Second agent never attacks, even when no invader exists (two attackers would win the race on
  maps where the opponent has no real defence).
