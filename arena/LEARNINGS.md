# Learnings (maintained by the analyst agent)

Champion history: seed (r00: tracker defender + nearest-food reflex attacker) -> r01cand1
(BankingAttacker, hard safety rules) -> r02cand1 (soft-cost Dijkstra attacker + invader snap) ->
r03: nothing -> **r04cand1** (r02cand1 attacker byte-for-byte + exit-denial defender `_guard` with
capsule cover). Past programs: `arena/db/progs/<id>.py`; frozen champions `arena/opponents/champ_r*`.
Champion gate: 71.7% vs r02cand1; 11-1-0 vs baseline, 12-0-0 vs champ_r01, 10-1-1 vs champ_r02.

## Standing facts
- **EnemyTracker works** (inside my_team.py). Best guess of a hidden enemy is off by 3.2 cells on
  average (12.1 for "last seen"); true cell inside the belief 98.5% of the time; ~0.4 ms per update.
- The gate is SPRT on score% (win 1, tie 0.5) vs the champion, then a regression check vs baseline
  and older champions. **Builders' own numbers do not replicate; mirror games are very noisy:**
  - A file identical in behaviour to the champion got 48.3% in 30 gate games (swings -22..+28);
    the unchanged champion scored 37.5% and 75% in two builders' 16-game runs. That is the noise.
  - Builder vs gate: r03cand2 55-69% -> 41.2%; r04cand3 57.5% in 60 -> 51.7% in 30; r04cand2
    60.8% in 60 -> 67.5% in 40; r04cand1 68.8% in 56 -> 71.7% in 30. Different seeds = different
    random maps = different results.
  - Rule: under ~60 games trust nothing smaller than ~20 points. 10 games per map is +-16 points.
- Games are nearly deterministic per (layout, colour, pairing): replaying the same game adds little.
  Test on more layouts and both colours. Never run two arenas with the same `--seed` at once.
- **Harness trap (r04cand1):** `arena.play()` with a candidate path that does not exist printed
  plausible scores (0.6 s per game) and no error. Check that the path exists and "secs" looks real.
- Maps are colour-asymmetric. Always compare colour-swapped pairs. In the r04 gate all three
  candidates lost RANDOM668017 as blue (-11/-4/-12, red +12/+8/+12) and RANDOM977952 as blue.
- Timing is not a constraint yet: gate games 3-12 s wall-clock, no warning in ~600 gate games over
  three rounds; r04 defence code (exit margins, joint 5x5 move search) added nothing measurable.

## Round 4: defence was the lever (all three candidates started from r02cand1, same gate maps)
- **r04cand1 DEFENSE-EXIT: promoted, 19-5-6, 71.7% in 30 games, avg margin +7.4.** `_guard`:
  stand where we reach every exit (our border cells with an open enemy-side neighbour) no later
  than the invader, then close in; falls back to the r00 defender on None/exception. Two additions:
  a scared defender keeps blocking at distance 2 (`SCARED_GAP`), and while chasing our capsules
  count as extra exits (`GUARD_CAPS`). The capsule part came from a trace: on RANDOM404807 vs seed
  the guard held a 26-dot invader inside for ~100 moves and it got out only after eating our
  capsule. Not ablated (builder's 60.0% without vs 68.8% with used different seeds).
- **r04cand2 DEFENSE-PINCER: also passed the gate, not chosen: 24-6-10, 67.5% in 40, avg +3.5**
  (regress: 12-0-0 baseline, 10-2-0 champ_r01, 9-1-2 champ_r02). What worked was again exit cover:
  choose the move minimising max over exits (border cells + our capsules) of (our arrival - invader
  arrival), clipped at -2 visible / -4 hidden, tie-break distance to the invader; the attacker
  joins a joint 5x5 move search when at home or <= 6 from the border, carrying <= 2, and the invader
  carries >= 3 or is within 8. Plus: wait at the mouth of a dead end the invader is in; scared
  defender shadows at distance 2.
  **Its first version - cut the invader's shortest way home and chase from behind (the literal
  KNOWLEDGE sec. 3 pincer) - was neutral** (16 games 7-2-7; kills 15 vs 12, conceded 353 vs 336
  with it off). Reason: an attacker like ours only takes paths it reaches before any visible
  defender, so blocking one path just sends it home by another. Kills happen only when ALL exits
  are covered. Chasing is worth nothing; covering exits is worth ~+20 points of score%.
  Not known: how much the attacker-helper and the dead-end trap add (no `HELP_ON=False` run), and
  whether any of it adds to r04cand1 (both are exit cover, so the gains will not sum).
- **r04cand3 OFFENSE-CORRIDOR: rejected, 10-11-9, 51.7% in 30, avg -0.1.** Soft penalty (1.5 x P x
  carried, only when carrying >= 4) for dots in single-exit pockets, P from the full tracker belief
  mass at the pocket exit. The pocket map itself is good and cheap (<0.15 s): remove a cell,
  flood-fill, small cut-off components = pocket; it finds rooms with one door that leaf-stripping
  misses (all office deaths had leaf depth 0). Builder death log on office: control lost 6 loads /
  57 dots (5 of 6 inside a pocket), candidate 3 loads / 9 dots. But the gate shows no win gain:
  7 of 15 colour pairs were +x/-x mirrors or 0/0. Fewer pocket deaths did not turn into wins.
  Fourth attacker-safety idea in a row with no gate gain.

## Attacker: what is established (rounds 1-4)
- A planning attacker that banks food beat the reflex attacker 90% (r01).
- **Soft costs beat hard "provably safe" rules** (r02: 83.3% in 30). Tracker guess as a wall: no
  gain. Hard safe-return filter: 60% vs 83% without; `SAFE_RETURN = False` stays.
- **Sampled-world (Monte Carlo) checks of the attacker's plan do not help - tested three times**
  (57.1% in 120; 39.1% in 32; 28.1% in 16). Deaths come from a hidden defender the samples missed
  or from a corridor where every plan already dies; pessimistic models go home too often. Do not
  retry without a new source of information.
- **Longer trips (r03cand2): rejected, 41.2% in 40, yet avg margin +2.1.** Bigger loads raise the
  margin on a few maps (crowded +35..+45) and lose more close games. Win count is what scores.
- The carry budget has no cap in dense fields: one jumbo death with 60 carried (-82), outside any
  pocket (r04cand3 log). Untested fix; load changes swing margins (see above), measure separately.
- **The attacker waiting at the border is a de facto second defender (r03cand3 trace).** Any
  visible enemy ghost near the border hard-blocks all dots, so both attackers oscillate there on
  small maps. Stall-aggression scored 20-30% on fast/alleyCapture (10 games each); late gamble and
  "lead lock" were neutral. No sign that more aggression wins small maps.
- The attacker already takes a capsule when a defender is close and awake; invader snap (at home,
  carrying 0, invader within 3) is in the champion, never separately proven.

## Known failure patterns
- **Small maps are coin flips near 0.** r04cand1 vs r02cand1: alleyCapture -1/0/0/+2, fastCapture
  +2/+1/0/+1, distantCapture 0/+2; r04cand2 and r04cand3 lost alley, fast and default games too.
  r04cand3's gate had 11 ties in 30 (mostly 0-0). With a guard defender on both sides, expect
  many 0-0 mirror games: the next gains must come from scoring the first dot or from never leaking.
- **RANDOM404807 (2-wide border pipe, joined to each half only at top and bottom) is half fixed.**
  r04cand1 vs seed: blue +28, red still -18; vs baseline -15/-13 (was -19/-18). Guard exits are
  all 14 pipe cells, not the two real crossings. Reproduce:
  `cd pacman-contest/src/contest && python capture.py -r ../../../my_team.py -b ../../../arena/db/progs/seed.py -l RANDOM404807 -q`
- RANDOM880570 vs champ_r02: lost by both r04cand1 (blue -4) and r04cand2 (red -1) in regress.
- **One death with a big load decides big maps** (jumbo, crowded, office): mirror swings -22..+28;
  r04cand1's gate had jumbo +100/+24. Nothing on the attacker side has fixed this in four rounds.
- Enemy attackers in mirror games carry 20-50 dots at a time; trapping one is a large swing.

## Open questions (untested)
- r04cand2's attacker-helper (joint exit cover) and dead-end mouth trap on top of r04cand1.
- Attacking INTO an exit-denial defender: the mirror opponent now has `_guard`. Our attacker has
  no model of a defender that covers exits instead of chasing; the capsule is the known way out.
- Guard exits on pipe/choke maps (real crossings only); where the defender waits with no invader.
- Second agent never attacks, even when no invader exists for a long time (0-0 small-map games).
- Search for the defender (playouts with an invader model) - never built. Attacker-side MCTS is a
  low-odds bet after four failed safety ideas.
- Treating a visible enemy that is not hunting (their attacker on its way out) as a soft threat.
- Process: all three r04 builders finished with clean files and honest notes in ~10 minutes; they
  had time left. Spend it on a same-seed ablation of each new flag (60 games), not on more ideas.
