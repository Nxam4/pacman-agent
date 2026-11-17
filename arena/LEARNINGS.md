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
Tune gate: 71.7% in 60 vs r08cand2; regress 85% (champ_r06 66.7%, ext_rush 75%). Rounds 9-12: nothing promoted.

## Round 12 (all three from tune_1117_1652; all rejected)
- **Race alarm (r12cand1): 32.5% in 40, the worst result in rounds.** Trigger: our dots left - 2 <=
  ALARM_RACE (4) with enemies carrying, or both enemies Pacmen carrying >= 5 before move 150. On SMALL
  maps it kills offence: default 0-0-6, distant 0-0-4 (bank 6-10 vs conc 18), RANDOM red 1-1-6.
  Builder's own SPRT said 48.7% in 80 - did not replicate. vs diana only +1 win in 16 (fires at move
  300-570, too late). **Three alarm variants now lost the mirror (r11 33.6%, r12 32.5%): drop
  "send someone home when enemies carry/race".** diana needs something else (see open questions).
- **Real-exit `_guard` (r12cand2, REAL_EXITS): 49.3% in 140, kill 0.14 (unchanged).** With
  r11 GUARD_INTERCEPT (49.1%) that is two neutral `_guard` exit-set tweaks: `_guard` runs too rarely
  (turtle phase / defender only) to decide mirror games. Stop tweaking `_guard` internals.
- **Exploiter (r12cand3): pure racing LOSES to the champion** (shallow 5-8-dot trips 0-0-8 twice;
  bank 11-15 vs conc 19-21): deep carrying is the faster eater with nobody home. A "seal" (both go
  home when we lead >= 1 and they carry >= 6) 46.2% in 40 - recalls cost bank, chasing gets no kills.
  Its trace: defaultCapture opens with a ~200-300-move border standoff before anyone eats.
- **Draws are common and come from standoffs:** fast 3-6-3 and three RANDOM seeds (683388, 676694,
  799707) 0-0 in BOTH colours in r12cand2's 140 games; ~10% of mirror games. Each is 1 point, not 3.
- Colour split in r12cand2's 140 (champion-equivalent): crowded R 2-0-4 (drop 10.7) / B 6-0-0;
  office B 0-0-4 (-44, conc 128); strategic R 0-0-5; default R 1-0-5; distant R 1-0-5; jumbo R 1-0-3.

## Round 11 (condensed; from tune_1117_1652)
- **Home intercept (r11cand1, `INTERCEPT_*`): inconclusive 53.3% in 300 - best since the tune; never
  continued (r12's last builder was the exploiter).** An agent already home as a ghost carrying 0 runs
  `_guard` on the top enemy carrier (carry >= 6) when its cover margin <= 1, for <= 40 moves. Fires in
  ~18% of games; kills there ~0.6/game vs 0.04; office red 7-0-5. Many intercepts seal the carrier
  without catching it and burn all 40 moves. Program: `arena/db/progs/r11cand1.py`.
- **diana_catana is a rusher we lose a RACE to** (both Pacman at once, nobody of ours home, our deaths 0).
- `_guard` parks on one minimax border cell with a deep invader (r11cand2 bug) - fixing it did nothing.
- Load-scaled danger (r11cand3) 46.5% / 43.3%: global caution costs bank. Office: NO capsules, wide
  single-door rooms (leaf `depth` = 0 inside), -127 games die carrying 62-69 when sandwiched.

## Standing facts
- **The mirror over-states progress.** Held-out benchmark (arena/ext_pool, 240 paired games): tuned
  champion 89.2% vs r08cand2 88.8%, paired +0.4 +- 2.6, despite 71.7% head-to-head. Weakest held-out
  opponents: ylmiami 68.8% (7 losses), uripont 81%, rashomonset 83%. Training field: ext_gh_diana_catana
  is the one field team near 50% (4-0-4, 3-0-5, 4-0-4, 10-0-6 in builder runs); the rest >= 75%.
- **EnemyTracker works** (inside my_team.py): best guess off by 3.2 cells on average, true cell in
  the belief 98.5% of the time, ~0.4 ms per update.
- **Builders' own numbers do not replicate, in either direction:** champion vs itself 41.7-54.2%;
  r09: 52.5/55.5/55.8% (builder) -> 45.0/49.7/49.6% (gate); r10: cand1 51.7% in 30 -> 47.5% in 80,
  cand2 52.5% in 100 -> 49.2% in 60, cand3 50.0% in 100 -> 46.7% in 90; r12cand1 48.7% in 80 -> 32.5%.
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

## Rounds 9-10, condensed (all rejected)
- **Fast/default standoff (r10cand1):** a deterministic 2-cycle - the enemy attacker hovers as a ghost
  0-1 cells from its border, our agent steps up, sees it, steps back, loses sight. HOVER_ON (hovering
  ghost = soft cost) 47.5% in 80, cost bank elsewhere. Ties are rare now (4% of gate games).
- **Joint defence playout search (r10cand2): 49.2% in 60, a NO-OP** - its trigger (turtle AND chased
  invader AND `helper_eligible` AND margin 1-4) happens ~0.25 times/game.
- **Border-gap ambush (r10cand3): 46.7% in 90.** The champion's carrier eats deep carrying 20-70
  (CARRY_STEP 0) and its crossing moves, so waiting at one gap rarely strikes.
- **Crowded red border ambush (r09):** our carrier 1 step from home is eaten by an ENEMY PACMAN that
  steps back over the border and becomes a ghost. r09cand1 LATENT_D (every enemy Pacman within 3.5
  cols = ghost, hard): 45.0% in 130, office red drop 74/game. If retried: narrow and soft only.
- Settled: SMALLMAP guard from move 0 (49.7% in 190); late or sticky turtle (49.6%).

## Rounds 6-8, condensed
- r08cand2 ROUTE_ON promoted, 57.9% in 170 vs r06cand3: jumbo +20, office +9.8, drops 3.0/game vs 5.2.
- r08cand3 EXPLOIT (both guard from lead >= 3): 52.3% in 300; a single guard from move 0 lost 37.5%:
  the second invader walks home.
- **Rejected, do not retry:** carry-triggered recall while behind (r07cand1, 35.0%: costs bank 3-7
  everywhere; and r11/r12 alarms 33-34%, r12 seal 46%); load caps (trade drops for bank 1:1); decoy role (50.0% in 290); two-invader cover in
  turtle phase (r07cand2, 50.0% in 260); EXIT_ON exit slack (~50% over 330).
- Defence playout search: defender-only r06cand2 42.5% in 40; joint r10cand2 no-op (see above).

## Defence: what is established
- **Covering every exit is the lever; chasing is worth nothing.** r04cand1 `_guard`: 71.7% in 30;
  r05cand1 (+ attacker as second jaw, `HELP_ON`): 69.0% in 50 on top. Helper ablation (60 games):
  kills 25 vs 11, conceded 651 vs 1022. Kills happen only when ALL exits are covered.
- `_guard`/`joint_cover` cover ONE invader (the one carrying most); the mirror sends two.
- This defence only runs when lead >= TURTLE_LEAD (3). Kill rate 0.04-0.2/game in every r10 variant.
  Exit-set tweaks (intercept ranking r11, real exits r12) are neutral. `GUARD_CAPS` never ablated.
  The only defence signal since r05: r11cand1's opportunistic home intercept (53.3% in 300).

## Attacker: what is established
- Planning + banking beat reflex 90% (r01). **Soft costs beat hard safety rules** (r02: 83.3%; again
  r09cand1: making enemy Pacmen hard threats raised deaths).
- **Do not retry:** Monte Carlo checks of the attacker's plan (3 times, 57/39/28%); tracker guess as
  wall, pocket penalty (51.7%); longer trips (41.2%). Win count is what scores, not margin.
- Against one real guard the attacker gets sealed in; a second attacker beat that (r06cand3).
  Trip ordering (ROUTE_ON) beat greedy one-dot choice.

## Known failure patterns
- **officeCapture**: the most dots die there (r11 drop 24/game red; one 60+ load decides the game).
- **crowdedCapture red**: border ambush, -36..-50/game in the mirror (r11: 0-0-11, drop 33).
- **Rushers (diana_catana)**: we lose the race, not the fights - nobody home while lead < 3. Recall
  alarms fix diana but lose the mirror; racing harder loses to deep carrying.
- **Big maps are decided by one load**: jumbo swings -128..+128 on one seed.
- **Standoffs -> draws**: fast, default opening (200-300 moves), several RANDOM seeds 0-0 both colours.

## Open questions (untested)
- Opening tempo: skip the 200-300-move border standoff (default/fast/0-0 RANDOMs) - also the most
  plausible way to out-race diana without recalling anyone.
- Office sandwich in single-door rooms: a room-door (articulation) depth instead of leaf depth.
- Shared routes between the two attackers on big maps.
- Process: same-seed parent control + per-flag ablation is the standard; log layout AND colour next
  to kills / conceded / banked.
