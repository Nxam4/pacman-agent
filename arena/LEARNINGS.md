# Learnings (maintained by the analyst agent)

Champion history: seed (r00) -> r01cand1 (BankingAttacker) -> r02cand1 (soft-cost Dijkstra
attacker + invader snap) -> r04cand1 (+ exit-denial defender `_guard`) -> r05cand1 (+ attacker as
second guard `HELP_ON`, dead-end trap `TRAP_ON`) -> r06cand3 (EXPLOITER: `DOUBLE_ATTACK` +
`LANE_SPLIT` until lead >= `TURTLE_LEAD`, then lane 0 runs `_guard`, lane 1 attacks/helps; not
sticky, NO defender while behind the lead) -> r08cand2 (+ `ROUTE_ON`: trip of up to `ROUTE_K` dots +
return by nearest-neighbour chaining when no visible ghost within `ROUTE_GHOST`) -> **tune_1117_1652**
(SPSA constants on r08cand2: TURTLE_LEAD 3, CARRY_BUDGET 16, CARRY_STEP 0 = carry budget no longer
scales, ROUTE_K 8, ROUTE_FIRST 5, HELP_MAX_CARRY 0, HELP_BORDER 4). Past programs:
`arena/db/progs/<id>.py`; frozen champions `arena/opponents/champ_rNN` = champion at the START of round
NN (champ_r09t = r08cand2, champ_r08 = r06cand3). The tuned champion is the gate opponent.
Tune gate: 71.7% in 60 vs r08cand2; regress 85% (champ_r06 66.7%, ext_rush 75%). Rounds 9-10: nothing promoted.

## Standing facts
- **The mirror over-states progress.** Held-out benchmark (arena/ext_pool, 240 paired games): tuned
  champion 89.2% vs r08cand2 88.8%, paired +0.4 +- 2.6, despite 71.7% head-to-head. Weakest held-out
  opponents: ylmiami 68.8% (7 losses), uripont 81%, rashomonset 83%. Training field: ext_gh_diana_catana
  is the one field team near 50% (4-0-4 and 3-0-5 in two r10 builder runs); the rest >= 75%.
- **EnemyTracker works** (inside my_team.py): best guess off by 3.2 cells on average, true cell in
  the belief 98.5% of the time, ~0.4 ms per update.
- **Builders' own numbers do not replicate, in either direction:** champion vs itself 41.7-54.2%;
  r09: 52.5/55.5/55.8% (builder) -> 45.0/49.7/49.6% (gate); r10: cand1 51.7% in 30 -> 47.5% in 80,
  cand2 52.5% in 100 -> 49.2% in 60, cand3 50.0% in 100 -> 46.7% in 90.
  Rule: under ~100 games trust nothing smaller than ~10 points; under 60, ~20.
- **Mirror colour bias is on almost every fixed map** (r10, 230 pooled gate games of 3 near-copies vs
  the tuned champion): crowded red 0-0-9 (-50, conc 62, drop 32) / blue 8-0-1; alley red 8-0-1 / blue
  0-0-9; default red 1-0-9 / blue 8-0-2; strategic red 0-0-8 / blue 8-0-0; fast red 5-4-0 / blue 0-3-6;
  office blue 1-0-6 (-42); jumbo red 6-0-2. A per-layout result means nothing without the colour split.
- **Most RANDOM maps are fixed mirrors** too. Only games whose result CHANGES carry signal: run the
  parent as a same-seed control, game by game, both colours, never the same `--seed` in two arenas at
  once. Same seed is NOT deterministic: a 60-game same-seed run is +-7 points.
- **Harness traps:** `arena.play()` with a missing path or one not ending in `.py` prints plausible
  0 s all-tie results. Never run two arenas at once (shared `www/` score files -> "UNCLEAN").
- Timing: gate games 3-24 s wall-clock, no warning in ~1500 gate games. A 150-playout defender
  search hit 0.26-0.30 s per move (r06cand2); r10cand2's 0.2 s budget peaked at 0.243 s.

## Round 10 (all three from tune_1117_1652; all rejected)
- **Ties are now rare under the tuned champion: 9 of 230 gate games (4%)**, down from ~14% in r09.
  The standoff lever is small.
- **Standoff cause logged (r10cand1):** on fast, neither side's attackers ever became Pacman in 600
  moves. The enemy attacker hovers as a ghost 0-1 cells from its border, so every lane dot counts as
  guarded; our agent steps up, sees it, steps back, loses sight, steps up: a deterministic 2-cycle on
  both sides. HOVER_ON (a hovering ghost far from us becomes a soft cost, not a threat) was **rejected,
  47.5% in 80**, bank 27.9 / conc 31.6: it cost bank elsewhere. If retried: a livelock breaker that
  fires only after our own position 2-cycles >= 8 moves at home carrying 0, small maps only.
- **Joint defence playout search (r10cand2): rejected, 49.2% in 60 - a NO-OP.** It ran 26 times in
  100 games and never kept the helper in. The trigger (turtle phase AND chased invader AND
  `helper_eligible` AND joint margin 1-4) happens ~0.25 times/game. Defence search is NOT the lever
  while the trigger is this rare; `helper_eligible` blocks most chases in field games.
- **Border ambush exploiter (r10cand3): rejected, 46.7% in 90.** The champion's carrier does not go
  home near the border: it eats deep in our half carrying 20-70 dots on big maps (CARRY_STEP 0), and
  its crossing (min-cost border cell) moves, so a Pacman waiting at one gap rarely strikes (8-11 waits,
  0-1 strikes/game). Wide trigger: kills 0.47/game but 40%. The weakness is the unbounded deep carry
  with nobody at home - a ghost that covers ALL exits (`_guard` margin <= 0) is the untried angle.

## Round 9 (from r08cand2; all rejected)
- **Border ambush on crowded red:** our carrier 1 step from home is eaten by an ENEMY PACMAN that steps
  back over the border and becomes a ghost at the shared middle gap. `_threats` ignores visible enemy
  Pacmen. Still present: crowded red conc 62 / drop 32 per game in r10.
- r09cand1 LATENT_D (every visible enemy Pacman within 3.5 cols of the border = ghost): 45.0% in 130;
  office red 0-0-6, drop 74/game. If retried: only food-carrying enemy Pacmen adjacent to the border,
  soft cost, office drop must not rise.
- Settled: SMALLMAP guard from move 0 (r09cand2, 49.7% in 190); late or sticky turtle (r09cand3, 49.6%).

## Rounds 6-8, condensed
- r08cand2 ROUTE_ON promoted, 57.9% in 170 vs r06cand3: jumbo +20, office +9.8, drops 3.0/game vs 5.2.
- r08cand3 EXPLOIT (both guard from lead >= 3): 52.3% in 300; a single guard from move 0 lost 37.5%:
  the second invader walks home.
- **Rejected, do not retry:** carry-triggered recall while behind (r07cand1, 35.0%: costs bank 3-7
  everywhere); load caps (trade drops for bank 1:1); decoy role (50.0% in 290); two-invader cover in
  turtle phase (r07cand2, 50.0% in 260); EXIT_ON exit slack (~50% over 330).
- Defence playout search: defender-only r06cand2 42.5% in 40; joint r10cand2 no-op (see above).

## Defence: what is established
- **Covering every exit is the lever; chasing is worth nothing.** r04cand1 `_guard`: 71.7% in 30;
  r05cand1 (+ attacker as second jaw, `HELP_ON`): 69.0% in 50 on top. Helper ablation (60 games):
  kills 25 vs 11, conceded 651 vs 1022. Kills happen only when ALL exits are covered.
- `_guard`/`joint_cover` cover ONE invader (the one carrying most); the mirror sends two.
- This defence only runs when lead >= TURTLE_LEAD (3). Kill rate 0.04-0.2/game in every r10 variant.
  Guard exits are every open border cell, not the real crossings. `GUARD_CAPS` never ablated.

## Attacker: what is established
- Planning + banking beat reflex 90% (r01). **Soft costs beat hard safety rules** (r02: 83.3%; again
  r09cand1: making enemy Pacmen hard threats raised deaths).
- **Do not retry:** Monte Carlo checks of the attacker's plan (3 times, 57/39/28%); tracker guess as
  wall, pocket penalty (51.7%); longer trips (41.2%). Win count is what scores, not margin.
- Against one real guard the attacker gets sealed in; a second attacker beat that (r06cand3).
  Trip ordering (ROUTE_ON) beat greedy one-dot choice.

## Known failure patterns
- **officeCapture**: the most dots die there (r10 drop 14/game blue, 34/game red; deaths 0.4-0.9).
- **crowdedCapture red**: border ambush, -50/game in the mirror.
- **Big maps are decided by one load**: jumbo swings -128..+128 on one seed.
- **fast/default standoff**: mutual ghost-hover 2-cycle (r10cand1); rare as ties now.

## Open questions (untested)
- Why diana_catana (training field) and ylmiami (held-out) beat us: log bank/conc/deaths per layout.
- Home intercept: an agent already home with carry 0 cutting off a deep enemy carrier (`_guard` <= 0).
- Office deaths: which situation kills the carrier (log it first).
- Shared routes between the two attackers on big maps.
- Process: same-seed parent control + per-flag ablation is the standard; log layout AND colour next
  to kills / conceded / banked.
