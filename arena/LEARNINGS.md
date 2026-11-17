# Learnings (maintained by the analyst agent)

Champion history: seed (r00) -> r01cand1 (BankingAttacker) -> r02cand1 (soft-cost Dijkstra
attacker + invader snap) -> r04cand1 (+ exit-denial defender `_guard`) -> r05cand1 (+ attacker as
second guard `HELP_ON`, dead-end trap `TRAP_ON`) -> **r06cand3** (an EXPLOITER: r05cand1 code with
`DOUBLE_ATTACK` - both agents attack, `LANE_SPLIT` top/bottom food - until our lead >= `TURTLE_LEAD`
(4), then lane 0 goes home and runs r05cand1's `_guard`, lane 1 attacks and helps). The turtle is not
sticky: lead < 4 -> both attack again, with NO defender. Past programs: `arena/db/progs/<id>.py`;
frozen champions `arena/opponents/champ_r*`.
Champion gate: 153-39-108, 57.5% in 300 vs r05cand1, avg +4.35; regress baseline 11-0-1,
champ_r04 7-0-5, champ_r05 7-1-4, ext_rush 12-0-0, ext_turtle 12-0-0.

## Standing facts
- **EnemyTracker works** (inside my_team.py): best guess off by 3.2 cells on average, true cell in
  the belief 98.5% of the time, ~0.4 ms per update.
- The gate is SPRT on score% (win 1, tie 0.5) vs the champion, then regression vs baseline, older
  champions and ext_*. **Builders' own numbers do not replicate, in either direction:**
  - Champion vs itself: 45.8% (60), 41.7% (24), 48.3% (30), 53.3% and 54.2% (60 each, r06cand1).
  - Builder -> gate: r06cand3 51.5% in 100 -> 57.5% in 300; r06cand1 56.3% in 120 -> 45.9% in 110;
    r05cand1 55.8% -> 69.0%; r05cand2 46% -> 65.0%; r05cand3 56.2% -> 48.6%.
  - r07: cand2 53.5% in 100 -> 50.0% in 260; cand3 same-seed 56.7% in 60 -> 50.0% in 290.
  - Rule: under ~100 games trust nothing smaller than ~10 points; under 60, ~20.
- **Most RANDOM maps are fixed mirrors** (red/blue get +x/-x whatever we change). Only games whose
  result CHANGES carry signal: run the parent as a same-seed control and compare game by game, both
  colours, never the same `--seed` in two arenas at once. **Same seed is NOT deterministic**: a
  never-firing NO-OP matched only 35/60 games of its control and scored 3.3 points lower (r07cand1);
  a control rerun gave 52.5% then 46.7% (r07cand2). A 60-game same-seed run is +-7 points.
- **Harness trap:** `arena.play()` with a missing path or one not ending in `.py` prints plausible
  0 s all-tie results and no error. Check that "secs" looks real.
- Timing: gate games 3-24 s wall-clock, no warning in ~1300 gate games. A 150-playout defender
  search hit 0.26-0.30 s per move (r06cand2) - that is the budget scale for playouts.

## Round 7 (all three from r06cand3; nothing promoted)
- **Mirror-match profile** (champion vs itself, 550 gate games of cand2+cand3, ~neutral changes):
  bank = conc ~30, ties ~9% (fast 19 of 36 games tied, bank 0-2), drop 5-6/game but **office drop
  20-29/game, jumbo 16, crowded 15** (loads die on the big maps), kill only 0.26-0.33/game.
  Per layout each map is near 50/50 - the mirror has no fixed weak map, so a gain must come from
  doing something the champion does not.
- **r07cand1 DEFENSE-RECALL (lane goes home when an invader carries >= 4, lead < 4): rejected, 35.0%
  in 30** (bank 24.7 vs conc 29.3; jumbo 0-0-2 -25.5, office -15.8). Builder same-seed: cuts conc on
  office/crowded but costs bank 3-7/game everywhere; without the helper jaw 33%. **While behind or
  level, pulling an attacker home loses - do not retry carry-triggered recall.**
- **r07cand2 TWO_INV (turtle defender + helper each cover a different invader): rejected, 50.0% in
  260** (builder 53.5% in 100). Fires often (~26 calls/game) but only in turtle phase. Neutral.
- **r07cand3 DECOY_ON (one attacker draws the guard, the other banks): rejected, 50.0% in 290.** In
  the mirror there is rarely a real guard (the enemy attacks too until lead >= 4), so "guard closing"
  is mostly an enemy attacker passing through. Its `RUNNER_BANK=8` load cap halved drops (6.8 ->
  3.1 same-seed) but banked fell as much. **Load caps trade drops for bank 1:1 - not a lever.**

## Round 6 (all three from r05cand1)
- **r06cand3 EXPLOIT double attack + turtle: promoted, 57.5% in 300.** Per gate layout (W-T-L, avg,
  bank/conc): crowded 24-0-0 +23 (23/0), jumbo 12-0-8 +25 (73/48), strategic 16-0-6 +8.5,
  distant 15-1-8, default 14-1-9, RANDOM 49-26-45 +1.3 (neutral). **Worse: alley 5-0-17 (bank 3.9,
  conc 6.5), office 12-0-8 but avg -5.2 (conc 34, died 1.65), fast 6-11-7 (bank 1.2).** Blue
  83-21-46, red 70-18-62. It kills little (0.25/game) and drops 6.7 dots/game on 0.6 deaths.
  Regress weak spots: champ_r04 RANDOM 1-0-5 (conc 21.5, died 1.17); champ_r05 jumbo 0-2 (conc 96).
  Reading: a second attacker wins big open maps; with no defender while lead < 4 we concede on
  small / choke maps and to any team with a real guard.
- Builder's weakness analysis (code-verified): `_guard` and `joint_cover` cover ONE invader (the
  max-carry one); a second invader walks home free. The new champion itself sends two invaders, so
  this matters in every mirror game and in its own turtle phase.
- **r06cand1 EXIT_ON merge (r05cand2's attacker exit-slack): rejected, 45.9% in 110** (gate jumbo
  2-0-6 avg -27, office 0-1-5). Builder 120 same-seed games: 22 changed better / 19 worse; drops
  fall (7.6 -> 1.6) but conceded rises; strategic 5 better / 0 worse; turns 0-0 mirrors
  (RANDOM702264, 88995) into losses in both colours. Across ~330 games EXIT_ON is ~50%: **settled,
  do not port again.**
- **r06cand2 defender playout search: rejected, 42.5% in 40.** Defender-only, fired only when the
  invader already had a safe exit (solo margin > 0), playout ghosts chase/intercept (weaker than the
  rule guard), override on 25% of calls. A lone defender cannot turn margin > 0 into a kill. If
  retried: search JOINT moves where joint margin is 1-2, and use the rule guard as playout policy.

## Defence: what is established
- **Covering every exit is the lever; chasing is worth nothing.** r04cand1 `_guard`: 71.7% in 30;
  r05cand1 (+ attacker as second jaw, `HELP_ON`): 69.0% in 50 on top. Helper ablation (60 games):
  kills 25 vs 11, conceded 651 vs 1022, but own scoring 800 vs 883. `HELP_NEAR=0` loses the gain.
  `TRAP_ON` adds no kills on its own. Kills happen only when ALL exits are covered.
- `GUARD_CAPS`, `SCARED_GAP` never ablated. Guard exits are every open border cell (14 on the
  RANDOM404807 pipe map) rather than the real crossings.
- Under the r06 champion, this defence only runs when lead >= 4. Covering two invaders at once in
  that phase is neutral (r07cand2), and a recall while lead < 4 loses (r07cand1).

## Attacker: what is established (rounds 1-6)
- Planning + banking beat reflex 90% (r01). **Soft costs beat hard safety rules** (r02: 83.3%).
- **Do not retry:** Monte Carlo checks of the attacker's plan (3 times, 57/39/28%); EXIT_ON exit-slack
  model (r05cand2 + r06cand1, ~50% over ~330 games); tracker guess as wall, pocket penalty (51.7%);
  longer trips (41.2%). Win count is what scores, not margin.
- Against one real guard our attacker rarely dies but gets sealed in (r05: 460-870 moves per 16
  games with exit slack < 1, carrying ~22). A second attacker is what beat that (r06cand3): the
  guard covers only one of them. The lanes are only food halves; a decoy role was neutral (r07cand3).
  Food choice is still greedy one-dot-at-a-time (no trip/route planning tried yet).

## Known failure patterns
- **Small maps.** Before r06 every version was a coin flip (2x2 standoff: whoever leaves lets the
  other in). With double attack: alley 5-0-17 (lost), fast 6-11-7, still bank ~1-4 per game.
  Opportunistic raiding (r05cand3, 48.6%) and plain aggression (20-30%) failed.
- **officeCapture** is the weakest fixed map for three champions in a row (r06: avg -5.2, conc 34;
  r06cand1 and r06cand2 also lost it to the older champions in their final checks). In the mirror it is even (r07) but the most dots die there (20-29 dropped/game).
- **Big maps are decided by one load**: jumbo swings -105..+87; the r06 champion conceded 96/game
  to champ_r05 there (no defender while lead < 4).
- RANDOM566311 red is -12 for every version; RANDOM294127 red vs champ_r02 and RANDOM493143 red vs
  champ_r04 lost by both r05 candidates; RANDOM227634 red +17 without helper, -3 with it.
- RANDOM404807 (2-wide border pipe): r04cand1 red -18 vs seed, -15/-13 vs baseline. Not rechecked.

## Open questions (untested)
- A small-map gate (r05cand1 guard+attacker structure from move 0 on alley/fast-type maps): alley was
  5-0-17 for double attack vs r05cand1, i.e. the turtle structure beat it there.
- Late-game turtle by score AND time left (ties are ~9% of mirror games).
- Opportunistic kills by an agent that is already home (kill rate is only ~0.3/game) - not a recall.
- Trip planning for the attacker (order several dots + the return as one route).
- Joint-move playout search for defence where joint margin is 1-2 (KNOWLEDGE sec. 1, 3).
- Process: same-seed parent control + per-flag ablation is the standard; log layout next to
  kills / conceded / banked.
