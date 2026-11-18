# Learnings (maintained by the analyst agent)

Champion history: seed (r00) -> r01cand1 (BankingAttacker) -> r02cand1 (soft-cost Dijkstra
attacker + invader snap) -> r04cand1 (+ exit-denial defender `_guard`) -> r05cand1 (+ attacker as
second guard `HELP_ON`, dead-end trap `TRAP_ON`) -> r06cand3 (EXPLOITER: `DOUBLE_ATTACK` +
`LANE_SPLIT` until lead >= `TURTLE_LEAD`, then lane 0 runs `_guard`, lane 1 attacks/helps; not
sticky, NO defender while behind the lead) -> r08cand2 (+ `ROUTE_ON`: trip of up to `ROUTE_K` dots +
return by nearest-neighbour chaining when no visible ghost within `ROUTE_GHOST`) -> **tune_1117_1652**
(SPSA constants on r08cand2: TURTLE_LEAD 3, CARRY_BUDGET 16, CARRY_STEP 0 = carry budget no longer
scales, ROUTE_K 8, ROUTE_FIRST 5, HELP_MAX_CARRY 0, HELP_BORDER 4) -> **r15cand2** (+ ghost memory,
`GHOST_MEM` 4 / `GHOST_MEM_NEAR` 2: `EnemyTracker.remembered()` + `MemState` proxy, every decision
reads remembered enemies). Past programs: `arena/db/progs/<id>.py`; frozen champions
`arena/opponents/champ_rNN` = champion at the START of round NN (champ_r09t = r08cand2, champ_r08 =
r06cand3). Rounds 9-14: nothing promoted.

## Round 15 (cand1/2 from tune_1117_1652, cand3 from r14cand2) - r15cand2 PROMOTED
- **Ghost memory (r15cand2): BETTER, 57.8% in 180**; regress 85% (champ_r08 66.7, champ_r09t 58.3);
  field 88.3% pts vs champion 88.8% paired = **no field gain** (mirror-only, like the tune). An enemy
  that leaves sight stays "visible" for 4 enemy moves at the tracker guess (if within 2) or the
  sighting cell (if out of our sight). Builder: 2-cycles >= 20 moves 42 -> 23 events per 60 games.
  Gains are the old colour-fixed losses: **crowded R 7-0-1** (was 0-0-12), default R 4-0-2 (2-0-10),
  office R 7-0-0, distant R 6-0-1, fast R 4-2-0. Unchanged: **strategic R 1-0-7**, alley B 0-0-6
  (bank 0), distant B 1-0-6; RANDOM 29-7-36 (slightly < 50%). So the "colour-fixed" losses were
  largely flicker, not code asymmetry. Field: diana 14-0-10 (champion 15-0-9), fast 18-3-3 (21-2-1),
  office deaths 0.79/game (1.50).
- **Red tie-break mirroring (r15cand1, LANE_MIRROR + TIE_MIRROR): rejected 47.1% in 190** (builder
  57.5% in 100). It made red's code an exact mirror of blue for ~22 moves; strategic red stayed
  1-0-8 - **the strategic red loss arises at first border contact, where red moves first** (rule
  asymmetry, not code). Crowded red improved less (3-0-5) than ghost memory did. Do not retry.
- **Narrow guard + attacker-only ghost memory (r15cand3 on r14cand2): rejected 48.9% in 190**;
  crowded drop 15-20/game, jumbo R 1-0-6. The narrow guard is dead in the mirror, and **alley is not
  in the field gate's layout set** (field = RANDOM, crowded, default, distant, fast, office,
  strategic), so its field gain cannot pass either. Drop it.
- **diana_catana remains the only field team near 50%**: in 7 of 24 games we bank 0 and concede
  28 (= it returns all but 2 dots and ends the game before our first bank). That's a lost race to
  the END condition, not a fight.

## Rounds 13-14 (condensed; nothing promoted)
- Narrow-border guard (r14cand2) 52.0% in 300: field alley 94% vs 74%, invisible in the mirror.
- Intercept variants are dead: release 51.3%, start gate 46.7%, pincer jaw 40.0% (jaw fired in 6 of
  21 intercepts). **A sealed carrier that waits gets caught later - do NOT shorten the seal.**
- EXPLOIT double wall + raider (r14cand3) 25.8%: the champion wins the race to the border. Traces:
  sealed invaders sit 200+ moves with 8-12 dots while exit-margin guards never close in (kills
  0.12/game); `GUARD_CAPS` parked a guard on a far capsule 50 moves while the invader banked 12
  (no capsules in exit set: conceded 15.4 -> 10.6 in 8 games); a raider into our empty half banks ~8.
- Standoff breaker (r13cand2, lone prober) 48.1% in 130: 0-0 RANDOMs are a double-guard
  equilibrium at a walled corridor border. Fast standoffs are a guard PERMANENTLY in sight (not
  flicker; ghost memory did not touch them). Office door depth (r13cand3) 45.0%.

## Rounds 9-12 (condensed; all rejected)
- **Recall alarms are dead:** r12 race alarm 32.5%, r11 alarm 33.6%, seal 46.2%, r07 recall 35.0%.
  Pure racing (shallow 5-8 trips) loses to deep carrying. Load-scaled danger (r11cand3) 46.5%.
- Home intercept r11cand1 (`INTERCEPT_*`, `arena/db/progs/r11cand1.py`): home ghost with carry 0 runs
  `_guard` on the top carrier (carry >= 6) when cover margin <= 1, <= 40 moves; fires in ~18% of games.
- `_guard` exit-set tweaks (r11 ranking, r12 real exits 49.3%) are neutral: stop tweaking internals.
- Fast standoff HOVER_ON soft cost (r10cand1) 47.5% in 80; joint defence playout search (r10cand2)
  49.2%, a no-op (fires 0.25/game); border-gap ambush 46.7%.
- Crowded red border ambush (r09, LATENT_D hard rule) 45.0%; crowded red was later fixed by ghost memory.
- Settled: SMALLMAP guard from move 0 (49.7% in 190); late or sticky turtle (49.6%).

## Standing facts
- **The mirror over-states progress.** Held-out benchmark (arena/ext_pool, 240 paired games): tuned
  champion 89.2% vs r08cand2 88.8%, paired +0.4 +- 2.6, despite 71.7% head-to-head. Weakest held-out
  opponents: ylmiami 68.8% (7 losses), uripont 81%, rashomonset 83%. Training field: ext_gh_diana_catana
  is the one field team near 50% (4-0-4, 3-0-5, 4-0-4, 10-0-6 in builder runs); the rest >= 75%.
- **EnemyTracker works** (inside my_team.py): best guess off by 3.2 cells on average, true cell in
  the belief 98.5% of the time, ~0.4 ms per update.
- **Builders' own numbers do not replicate:** champion vs itself 41.7-54.2%; r09 52-56% -> 45-50%
  (gate); r15cand1 57.5% in 100 -> 47.1% in 190. Under ~100 games trust nothing below ~10 points.
- **Mirror colour bias is on almost every fixed map** (r10, r13, r14 splits agree): a per-layout
  result means nothing without the colour split. Much of it was visibility flicker (r15cand2).
- **Field gate vs mirror:** both promotions since r08 (tune, ghost memory) were mirror-only gains
  (field +-1 point). A field win must show up on the field layouts (no alley there).
- **Most RANDOM maps are fixed mirrors** too. Only games whose result CHANGES carry signal: run the
  parent as a same-seed control, game by game, both colours, never the same `--seed` in two arenas at
  once. Same seed is NOT deterministic: a 60-game same-seed run is +-7 points.
- **Harness traps:** `arena.play()` with a missing path or one not ending in `.py` prints plausible
  0 s all-tie results. Never run two arenas at once (shared `www/` score files -> "UNCLEAN").
- Timing: gate games 3-24 s wall-clock, no warning in ~1500 gate games. A 150-playout defender
  search hit 0.26-0.30 s per move (r06cand2); r10cand2's 0.2 s budget peaked at 0.243 s.

## Rounds 6-8, condensed
- r08cand2 ROUTE_ON promoted, 57.9% in 170 vs r06cand3: jumbo +20, office +9.8, drops 3.0/game vs 5.2.
- r08cand3 EXPLOIT (both guard from lead >= 3) 52.3% in 300; one guard from move 0 37.5%; r14 double wall 25.8%.
- **Rejected, do not retry:** carry-triggered recall while behind (r07cand1, 35.0%: costs bank 3-7
  everywhere; r11/r12 alarms 33-34%, r12 seal 46%); load caps; office door depth (r13); red
  tie-break mirroring (r15); narrow alley guard (r14/r15); decoy role (50.0%); two-invader turtle
  cover (50.0%); EXIT_ON exit slack (~50%); defender-only playout search (42.5%).

## Defence: what is established
- **Covering every exit is the lever; chasing is worth nothing.** r04cand1 `_guard`: 71.7% in 30;
  r05cand1 (+ attacker as second jaw, `HELP_ON`): 69.0% in 50 on top. Helper ablation (60 games):
  kills 25 vs 11, conceded 651 vs 1022. Kills happen only when ALL exits are covered.
- `_guard`/`joint_cover` cover ONE invader (the one carrying most); the mirror sends two.
- Runs only when lead >= TURTLE_LEAD (3); kills 0.04-0.2/game. Signals since r05: r11 intercept
  (53.3% in 300) and r14cand2 narrow guard (52.0% in 300). `GUARD_CAPS` never ablated in the champion.

## Attacker: what is established
- Planning + banking beat reflex 90% (r01). **Soft costs beat hard safety rules** (r02: 83.3%; again
  r09cand1: making enemy Pacmen hard threats raised deaths).
- **Do not retry:** Monte Carlo checks of the attacker's plan (3 times, 57/39/28%); tracker guess as
  wall, pocket penalty (51.7%); longer trips (41.2%). Win count is what scores, not margin.
- Against one real guard the attacker gets sealed in; a second attacker beat that (r06cand3).
  Trip ordering (ROUTE_ON) beat greedy one-dot choice.

## Known failure patterns (as of r15cand2)
- **officeCapture**: the most dots die there (mirror drop up to 27/game; one 60+ load decides it).
- **Rushers (diana_catana)**: it ends the game (returns all but 2) before we bank - bank 0 / conc 28
  in 7 of 24 field games. Recall alarms fix diana but lose the mirror (they fire on every attacker).
- **Big maps are decided by one load**: jumbo swings -128..+128 on one seed (r15cand2 jumbo R drop 12.8).
- **Standoffs -> draws**: fast (permanent visible guard at the border), 0-0 RANDOM double-guard borders.
- **Colour-fixed mirror losses left**: strategic red (1-0-7..0-0-9 for every program; first border
  contact, red moves first), alley blue (0-0-6, bank 0), distant blue (1-0-6).
- **Sealed carriers are never killed**: guards hold the seal but do not squeeze (r14cand3 trace).

## Open questions (untested)
- Squeezing a sealed carrier with the guard itself (keep margin >= 0 while shrinking distance).
- Endgame race: block when an enemy carrier can END the game by returning (our food left - carry <= 2).
- First border contact: wait one move instead of committing first (strategic red).
- Capsule cover only when the invader can actually reach the capsule first (GUARD_CAPS conditional).
- Shared routes between the two attackers on big maps; simultaneous two-agent crossing.
- Process: same-seed parent control + per-flag ablation; log layout AND colour with kills/conc/bank.
