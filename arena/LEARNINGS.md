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
Tune gate: 71.7% in 60 vs r08cand2; regress 85% (champ_r06 66.7%, ext_rush 75%). Rounds 9-13: nothing promoted.

## Round 13 (all three from tune_1117_1652; nothing promoted)
- **Intercept release (r13cand1 = r11cand1 + end intercept when distance stalls 6 moves / carrier
  drifts 8 away, 30-move cooldown): inconclusive 51.3% in 300** (r11cand1 itself 53.3% in 300; its
  same-seed control 59.2% in 60). Moves per intercept 17 -> 8 but kills per intercept 0.22 -> 0.12:
  **a sealed carrier that waits gets caught later - do NOT shorten the seal.** A start gate "carrier
  within 8" killed the feature (46.7%): intercepts start from afar. The intercept is a real but small
  edge (~52% over 600 games) - too small for the [50, 55] SPRT on its own; it needs more kills.
- **Standoff breaker (r13cand2): 48.1% in 130.** Fast draws vanished in the gate (3-0-3 vs 4-12-4
  in r13cand1's games), but RANDOM ties stayed ~6%. Trace (RANDOM676694): the 0-0 maps are a
  DOUBLE-GUARD equilibrium - both enemy ghosts sit at the openings of a walled corridor border; a lone
  prober cannot pass two guards and, once across, soft-cost paths lead back home (ping-pong).
- **Office door depth (r13cand3, articulation "door" in the food test): 45.0% in 60** (builder 49.5%
  in 100). Literal max(leaf, door) is impossible: on office the door depth is >= 10 almost everywhere,
  i.e. global caution again. Office red drop still 28-32/game. Neutral at best; stop.
- **Colour split in r13cand1's 300 (champion-equivalent; deterministic mirrors):** strategic R 0-0-12 /
  B 12-0-0 (red banks 24.5 vs 35); **default R 0-0-11 (bank 1.5!) / B 9-0-2 (bank 14.7)**; alley
  R 12-0-0 / B 5-0-7; crowded R 2-0-9 (conc 54, drop 8) / B 10-0-1; office R 8-0-4 (drop 32) / B 4-0-8;
  fast 4-12-4; RANDOM R 31-6-23 / B 21-6-33. ~35 games/300 are colour-fixed losses of the same code.
- **alleyCapture is the field's only loss map:** r13cand3 field run (24 games) vs champion (24): every
  loss on BOTH sides is on alley (cand: gilbernardopacheco01_cmyk, tini4; champion: ananastazi,
  germananashkin001), all low-scoring (bank 2-8). Mirror alley blue 5-0-7, bank 4.8, drop 2.3.
- Field (builders, 8 games each): diana_catana 2-0-6, 4-0-4, 6-0-2 - still the one field team near 50%.
- Ties in r13cand1's 300: 24 (8%); fast alone 12 of 24 games tied.

## Rounds 11-12 (condensed; all rejected)
- **Recall alarms are dead:** race alarm (r12cand1) 32.5% in 40 (kills offence on small maps;
  default 0-0-6), r11 alarm 33.6%, seal 46.2%. Pure racing (shallow 5-8 trips) loses to deep carrying.
- Home intercept r11cand1 (`INTERCEPT_*`, `arena/db/progs/r11cand1.py`): an agent home as a ghost with
  carry 0 runs `_guard` on the top carrier (carry >= 6) when cover margin <= 1, <= 40 moves. Fires in
  ~18% of games; kills there ~0.6/game vs 0.04. Continued in r13 (see above).
- Real-exit `_guard` (r12cand2) 49.3% in 140; with r11 GUARD_INTERCEPT two neutral `_guard` exit-set
  tweaks: `_guard` runs too rarely to decide mirror games. Stop tweaking `_guard` internals.
- diana_catana: both its agents go Pacman at once; we lose the RACE (our deaths 0), not the fights.
- Load-scaled danger (r11cand3) 46.5%: global caution costs bank. Office: NO capsules, wide rooms.
- defaultCapture opens with a ~200-300-move border standoff before anyone eats (r12cand3 trace).

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
- **Mirror colour bias is on almost every fixed map** (r10 and r13 splits agree; see Round 13 above).
  A per-layout result means nothing without the colour split.
- **Most RANDOM maps are fixed mirrors** too. Only games whose result CHANGES carry signal: run the
  parent as a same-seed control, game by game, both colours, never the same `--seed` in two arenas at
  once. Same seed is NOT deterministic: a 60-game same-seed run is +-7 points.
- **Harness traps:** `arena.play()` with a missing path or one not ending in `.py` prints plausible
  0 s all-tie results. Never run two arenas at once (shared `www/` score files -> "UNCLEAN").
- Timing: gate games 3-24 s wall-clock, no warning in ~1500 gate games. A 150-playout defender
  search hit 0.26-0.30 s per move (r06cand2); r10cand2's 0.2 s budget peaked at 0.243 s.

## Rounds 9-10, condensed (all rejected)
- **Fast/default standoff (r10cand1):** the enemy attacker hovers as a ghost 0-1 cells from its border,
  our agent 2-cycles in front of it. HOVER_ON soft cost 47.5% in 80 (cost bank elsewhere).
- **Joint defence playout search (r10cand2): 49.2% in 60, a NO-OP** (trigger ~0.25 times/game).
- **Border-gap ambush (r10cand3): 46.7% in 90** - the carrier eats deep, waiting at one gap rarely strikes.
- **Crowded red border ambush (r09):** our carrier 1 step from home is eaten by an ENEMY PACMAN that
  steps back over the border and becomes a ghost. r09cand1 LATENT_D (every enemy Pacman within 3.5
  cols = ghost, hard): 45.0% in 130, office red drop 74/game. If retried: narrow and soft only.
- Settled: SMALLMAP guard from move 0 (49.7% in 190); late or sticky turtle (49.6%).

## Rounds 6-8, condensed
- r08cand2 ROUTE_ON promoted, 57.9% in 170 vs r06cand3: jumbo +20, office +9.8, drops 3.0/game vs 5.2.
- r08cand3 EXPLOIT (both guard from lead >= 3): 52.3% in 300; a single guard from move 0 lost 37.5%:
  the second invader walks home.
- **Rejected, do not retry:** carry-triggered recall while behind (r07cand1, 35.0%: costs bank 3-7
  everywhere; and r11/r12 alarms 33-34%, r12 seal 46%); load caps (trade drops for bank 1:1); office door depth (r13); decoy role (50.0% in 290); two-invader cover in
  turtle phase (r07cand2, 50.0% in 260); EXIT_ON exit slack (~50% over 330); defender-only playout
  search (r06cand2, 42.5% in 40).

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
- **Standoffs -> draws** (8% of mirror games): fast, default opening, 0-0 RANDOM double-guard borders.
- **alleyCapture**: the only map the field beats us on (r13).
- **Colour-fixed mirror losses**: strategic red, default red (bank 1.5), crowded red, alley blue.

## Open questions (untested)
- Opening tempo / double-guard borders: a lone prober failed (r13cand2); a simultaneous two-agent
  crossing at two openings is untested. Also the plausible way to out-race diana.
- Why the same code loses default/strategic red every time (lane split / tie-break / route choice?).
- What loses alleyCapture to field teams (low-scoring, blue side in the mirror).
- Shared routes between the two attackers on big maps; pincer (second jaw) during the r11 intercept.
- Process: same-seed parent control + per-flag ablation; log layout AND colour with kills/conc/bank.
