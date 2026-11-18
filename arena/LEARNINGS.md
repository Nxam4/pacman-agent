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
Tune gate: 71.7% in 60 vs r08cand2; regress 85% (champ_r06 66.7%, ext_rush 75%). Rounds 9-14: nothing promoted.

## Round 14 (cand1 from r11cand1, cand2/3 from tune_1117_1652; nothing promoted)
- **Narrow-border guard (r14cand2, `NARROW_EXITS` 3 / `NARROW_DEEP` 3): inconclusive 52.0% in 300**
  (near-miss, continued next round). On maps with <= 3 border openings the lane-0 agent at home
  with carry 0 runs `_guard` even when not ahead, while an enemy Pacman carries food or is >= 3 deep.
  Diagnosis: **field alley losses are concessions, not deaths** - both agents attack, one invader
  banks 4-5 of 13 dots, then one enemy guard at 3 openings blocks us. Builder, same seed, alley vs
  the 4 field teams that beat us there: 59-3-2 (94%) vs champion 46-3-15 (74%). Gate mirror alley
  now R 11-0-0 / B 8-0-3 (bank 8.0) vs champion-equivalent B 5-0-7. Filter needed: tini4 parks a
  Pacman 1 cell inside our border carrying 0 all game; an unfiltered guard ties 0-0.
  **A field-only gain is nearly invisible in the mirror SPRT** (alley is ~1 game in 16). Watch:
  its RANDOM ties were 20 of 120 vs 12 of 120 in r13cand1's 300 - check the rule on <= 3-opening RANDOMs.
- **Pincer jaw on the intercept (r14cand1 = r11cand1 + teammate takes the carrier's uncovered exit):
  rejected 40.0% in 30** (builder 55.0% vs same-seed control 48.3% in 60 = noise). The jaw fired in
  only 6 of 21 intercepts (teammate usually deep in enemy land) and kills per intercept did not rise
  (0.19 vs 0.22). Third failed intercept variant (r13 release 51.3%, start gate 46.7%): stop
  extending the intercept.
- **EXPLOIT double wall + one raider (r14cand3): 25.8% in 60.** From move 0 the champion wins the
  race to the border and later slips past two guards; the r13 0-0 double-guard standoffs need guards
  ALREADY placed. Traces: (a) champion invaders sit sealed deep in our half with 8-12 dots for 200+
  moves and exit-margin guards never close in (kills 0.12/game); (b) `GUARD_CAPS` parked a guard on
  a capsule far from the border for 50 moves while the invader banked 12 - dropping capsules from
  the exit set cut conceded 15.4 -> 10.6 (8 games); (c) a raider into the champion's empty half
  (no defender while lead < 3) banks ~8/game with 0.15 deaths.
- **Home visibility flicker** (r14cand2 trace, alley vs ananastazi): both our agents 2-cycled at
  home ~500 moves 4-6 cells from an invader carrying 5, because an enemy ghost is visible from one
  cell and not the next (target flips each move). Likely a general standoff/2-cycle cause.
- **Colour split (r14cand2's 300) matches r13:** crowded R 0-0-12 (drop 20.5, conc 56) / B 11-0-1;
  default R 2-0-10; strategic R 0-0-11; office R drop 35; fast R 6-6-0 / B 1-3-8 (9 of 24 tied).

## Round 13 (condensed; nothing promoted)
- Intercept release (r13cand1): 51.3% in 300 (r11cand1 53.3% in 300). Kills per intercept 0.22 ->
  0.12: **a sealed carrier that waits gets caught later - do NOT shorten the seal.** A start gate
  "carrier within 8" killed it (46.7%). The intercept is a real but small edge (~52% over 600).
- Standoff breaker (r13cand2, lone prober): 48.1% in 130. 0-0 RANDOM maps (676694, 683388, 799707)
  are a DOUBLE-GUARD equilibrium at a walled corridor border; once across, soft-cost paths ping-pong.
- Office door depth (r13cand3): 45.0% in 60; door depth >= 10 almost everywhere = global caution. Stop.

## Rounds 9-12 (condensed; all rejected)
- **Recall alarms are dead:** r12 race alarm 32.5%, r11 alarm 33.6%, seal 46.2%, r07 recall 35.0%.
  Pure racing (shallow 5-8 trips) loses to deep carrying. Load-scaled danger (r11cand3) 46.5%.
- Home intercept r11cand1 (`INTERCEPT_*`, `arena/db/progs/r11cand1.py`): home ghost with carry 0 runs
  `_guard` on the top carrier (carry >= 6) when cover margin <= 1, <= 40 moves; fires in ~18% of games.
- `_guard` exit-set tweaks (r11 ranking, r12 real exits 49.3%) are neutral: stop tweaking internals.
- diana_catana: both its agents go Pacman at once; we lose the RACE (our deaths 0), not the fights.
- Fast/default standoff (r10cand1): enemy attacker hovers as a ghost at its border, our agent
  2-cycles in front; HOVER_ON soft cost 47.5% in 80. default opens with a 200-300-move standoff.
- Joint defence playout search (r10cand2) 49.2%, a no-op (fires 0.25/game); border-gap ambush 46.7%.
- Crowded red border ambush (r09): our carrier 1 step from home is eaten by an ENEMY PACMAN that steps
  back and becomes a ghost. LATENT_D (hard, 3.5 cols): 45.0%, office red drop 74. Retry narrow+soft.
- Settled: SMALLMAP guard from move 0 (49.7% in 190); late or sticky turtle (49.6%).

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
- **Mirror colour bias is on almost every fixed map** (r10, r13, r14 splits agree): a per-layout
  result means nothing without the colour split.
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
  everywhere; and r11/r12 alarms 33-34%, r12 seal 46%); load caps (trade drops for bank 1:1); office door depth (r13); decoy role (50.0% in 290); two-invader cover in
  turtle phase (r07cand2, 50.0% in 260); EXIT_ON exit slack (~50% over 330); defender-only playout
  search (r06cand2, 42.5% in 40).

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

## Known failure patterns
- **officeCapture**: the most dots die there (red drop 24-35/game; one 60+ load decides the game).
- **crowdedCapture red**: border ambush, 0-0-12 in the mirror, drop 20-33, conc 55.
- **Rushers (diana_catana)**: we lose the race, not the fights - nobody home while lead < 3. Recall
  alarms fix diana but lose the mirror; racing harder loses to deep carrying.
- **Big maps are decided by one load**: jumbo swings -128..+128 on one seed.
- **Standoffs -> draws** (8-10% of mirror games): fast, default opening, 0-0 RANDOM double-guard borders.
- **alleyCapture vs the field**: concessions while double-attacking (r14cand2 guard: 94% vs 74%).
- **Colour-fixed mirror losses**: strategic red, default red (bank 1.5-6), crowded red, fast blue.
- **Sealed carriers are never killed**: guards hold the seal but do not squeeze (r14cand3 trace).

## Open questions (untested)
- Why the same code loses default/strategic/crowded red every time (lane split / tie-break / route?).
- Visibility-flicker 2-cycles at home: does a short ghost memory remove them (and some standoffs)?
- Squeezing a sealed carrier with the guard itself (keep margin >= 0 while shrinking distance).
- Capsule cover only when the invader can actually reach the capsule first (GUARD_CAPS conditional).
- Shared routes between the two attackers on big maps; simultaneous two-agent crossing.
- Process: same-seed parent control + per-flag ablation; log layout AND colour with kills/conc/bank.
