# Learnings (maintained by the analyst agent)

Champion history: seed (r00: tracker defender + nearest-food reflex attacker) -> r01cand1
(BankingAttacker with hard safety guarantees) -> **r02cand1** (r01cand2's soft-cost Dijkstra attacker
+ try/except defender + invader snap). Round 3 promoted nothing. Defender logic is still the r00 one.
Past programs: `arena/db/progs/<id>.py`. Champion: 100% vs baseline, ~95% vs champ_r01.

## Standing facts
- **EnemyTracker works** (inside my_team.py). Best guess of a hidden enemy is off by 3.2 cells on
  average (12.1 for "last seen"); true cell inside the belief 98.5% of the time; ~0.4 ms per update.
- **The r00 defender is the weakest part of the team**: with no invader visible it heads for the
  tracker's most likely invader cell / the border cell nearest the likely enemy. Three rounds of
  attacker work have not touched it; all three r03 builders independently named it the next lever.
- The gate is SPRT on score% (win 1, tie 0.5) vs the champion, then a regression check vs baseline
  and older champions. **Builders' own numbers do not replicate, and mirror games are very noisy:**
  - r03cand1 shipped a file that behaves exactly like the champion (`MC_ON = False`); the gate gave
    it 13-3-14, 48.3% in 30 games, with single-game swings of -22..+28. That is the noise floor.
  - The same unchanged champion scored 37.5% (16 games) and 75% (16 games) in two builders' runs.
  - r03cand2 measured its final version at 55% in 20 games and 68.8% in 16; gate: 41.2% in 40.
  - r02cand3 reported 68.8% in 32 games; gate 57.1% in 120.
  - Rule: under ~60 games trust nothing smaller than ~20 points. 10 games per map is +-16 points.
- Games are nearly deterministic per (layout, colour, pairing): replaying the same game adds little.
  Test on more layouts and both colours instead. Never run two arenas with the same `--seed` at
  once (they share a score directory; one game lost its score file and looked like a failure).
- Several maps are colour-asymmetric in the mirror (champion vs itself): red wins RANDOM373754
  (+7) and RANDOM300951 (+3); blue wins RANDOM912786 (+8), distantCapture and jumboCapture
  (-15/+28). Always compare colour-swapped pairs, never a single game.
- Ties are rare (r03 gates: 4/70). Games are decided by margin: food banked vs conceded.
- Timing is not a constraint yet: gate games take 3-9 s wall-clock in total, no warnings in 380
  gate games over two rounds. MC checks cost at most 0.07 s per move.

## Attacker: what is established (rounds 1-3)
- A planning attacker that banks food beat the reflex attacker 90% (r01, two independent designs).
- **Soft costs beat hard "provably safe" rules** (r02 gate: r02cand1 83.3% in 30 games vs r01cand1).
  Treating the tracker's guess of a hidden defender as a wall: no gain (45.8% vs 62.5% without).
  A hard safe-return filter: 60% vs 83% without, collapsed on jumbo/officeCapture. `SAFE_RETURN =
  False` stays. Carry budget and cluster bonus are not what matters head-to-head.
- **Sampled-world (Monte Carlo) checks of the attacker's plan do not help - tested three times.**
  r02cand3 on the old attacker: 57.1% in 120 games (inconclusive). r03cand1 on the champion, 24
  worlds, strategic defender models (border cut-off, chase): builder-run SPRT 39.1% in 32 games;
  with defenders that always chase 28.1% in 16 (small samples, but no version showed a gain and
  the builder shipped it disabled). Why (death log): most big-load deaths (8-11 dots,
  mostly officeCapture) show survival 1.00 for every plan until one move before death - the
  defender comes from a hidden cell the samples missed, or we are already in a corridor where
  every plan dies. Pessimistic defender models make it go home too often, the same failure as the
  hard rule. Do not retry without a new source of information.
- **Longer trips / race rule / wider snap (r03cand2, OFFENSE-CHOKE): rejected, 16-1-23, 41.2% in
  40 games, yet avg margin +2.1.** Carry budget += 0.5 x (home distance of next dot - 4), "go home
  when the enemy is about to finish", and chasing an invader carrying >= 5 from 8 steps. It wins
  big on crowdedCapture (+35/+40/+45, champion mirror there: -3/-8/+7/-22) and loses many close
  games: both colours lost on RANDOM626730 (-12/-9), RANDOM466556, RANDOM632611, RANDOM956329,
  alleyCapture; jumbo and office swing +-25. Bigger loads raise the margin on a few maps and lose
  more games. Win count is what scores; do not trade wins for margin. Which of the three parts
  causes the close losses is unknown (builder ablations were 16-24 games each = noise).
- **The attacker that waits at the border is a de facto second defender (r03cand3 trace).** In a
  fastCapture mirror (1-1) both attackers swing at the border from move ~25 on: any visible enemy
  ghost near the border - including the enemy attacker standing on its own side - hard-blocks all
  dots (reach=0); we retreat, it drops out of sight, we advance, repeat. Making our attacker
  aggressive when stalled (soft search, no dead-end margin) scored 20% on fastCapture and 30% on
  alleyCapture in 10 games each: we die with 0-1 dots and their attacker walks past the empty
  border. A late gamble only when tied or behind (last 150 moves) was neutral (50%/50%). An
  explicit "lead lock" (attacker guards when ahead) was not better (30-55%). All small samples,
  but there is no sign that more aggression wins small maps.
- Invader snap (attacker at home, carrying 0, invader within 3 steps -> step toward it) is in the
  champion; neutral to slightly positive, never separately proven.

## Defence: the only measured result
- **r02cand2 (not chosen, 24-7-9, 68.8% in 40 games vs r01cand1)** left the attacker alone and added
  "exit denial" (`_guard`: stand where we reach every border cell no later than the invader, close
  in from there; the attacker joins from home when an invader carries >= 4 and both together can
  cover all exits). A defence-only change worth +19 points of score%. Caveats: lost distantCapture
  vs champ_r01 (+1/-3), lower margins vs baseline than r02cand1 (+15.8 vs +19.8), a stderr debug
  print left in (`# DBGLINE`). **Never combined with the r02 attacker - the top open item.**

## Known failure patterns
- **RANDOM404807 (border is a 2-wide pipe joined to each half only at the top and bottom rows;
  44 moves from start to the enemy side) is lost on defence.** Champion: -15/-15 vs seed, -19 vs
  baseline as red. r03cand2's trip log: no waiting at the border; we make one trip and bank 14
  while the seed's reflex attacker returns all 28 dots by move ~117 and the game ends. Attacker
  changes gave -29/+29 and -9: the attacker alone cannot win this map. Our defender never stops an
  invader that enters through one of two pipe ends. Reproduce:
  `cd pacman-contest/src/contest && python capture.py -r ../../../my_team.py -b ../../../arena/db/progs/seed.py -l RANDOM404807 -q`
- **Small maps are decided by one leak.** Champion vs champ_r01 is already 10-0-0 on fastCapture
  (+1..+5) and alleyCapture (+4..+8); the coin flips are mirror games. One conceded dot decides.
- **One death with a big load decides big maps** (jumbo, crowded, office, strategic): the champion
  mirror shows -22..+28 on these. Hard rules and sampled checks both failed to fix it (above); the
  deaths happen inside corridors entered while a hidden defender was near.
- Enemy attackers in mirror games carry 20-50 dots at a time; killing one is a large swing.

## Open questions (untested)
- r02cand2's exit-denial defender on the r02cand1 attacker (choke maps, small maps, mirror).
- Pincer / trap defence with both agents (KNOWLEDGE sec. 3): no measurement at all yet.
- Choosing *which* corridor to enter using tracker belief mass at its exit (the champion uses only
  the top-8 belief cells with a delay check and a dead-end depth penalty).
- Treating a visible enemy that is not hunting (their attacker on its way out, a ghost moving
  away) as a softer threat than a defender, to break the border oscillation without giving up
  the border.
- Second agent never attacks, even when no invader exists for a long time.
- Full junction-tree MCTS (KNOWLEDGE sec. 2) is untested, but the three failed plan-level MC
  checks make it a low-odds bet for the attacker; a defender-side search has not been tried.
- Process: builders hit usage limits in r01/r02. Write working code first, keep NOTES current,
  remove debug output, and if nothing beats the champion say so (r03cand3 restored the champion
  and kept its experiments in `arena/work/r03/cand_3/my_team_experiments.py.txt`).
