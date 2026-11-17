# Learnings (maintained by the analyst agent)

Champion history: seed (r00) -> r01cand1 (BankingAttacker) -> r02cand1 (soft-cost Dijkstra
attacker + invader snap) -> r04cand1 (+ exit-denial defender `_guard`) -> r05cand1 (+ attacker as
second guard `HELP_ON`, dead-end trap `TRAP_ON`) -> r06cand3 (EXPLOITER: `DOUBLE_ATTACK` +
`LANE_SPLIT` until lead >= `TURTLE_LEAD` (4), then lane 0 runs `_guard`, lane 1 attacks/helps; not
sticky, NO defender while lead < 4) -> **r08cand2** (+ `ROUTE_ON`: attacker orders a trip of up to
`ROUTE_K` dots + return by nearest-neighbour chaining when no visible ghost within `ROUTE_GHOST`;
replanned every move, only the dot ORDER changes, go-home rule unchanged). Past programs:
`arena/db/progs/<id>.py`; frozen champions `arena/opponents/champ_rNN` = the champion at the START of
round NN (champ_r08 = r06cand3, champ_r06 = r05cand1); the current champion r08cand2 is the gate opponent.
Champion gate: 87-23-60, 57.9% in 170 vs r06cand3; regress baseline 11-0-1, champ_r05 8-1-3,
champ_r06 7-0-5, ext_rush 12-0-0, ext_turtle 12-0-0. Round 9: nothing promoted.

## Standing facts
- **EnemyTracker works** (inside my_team.py): best guess off by 3.2 cells on average, true cell in
  the belief 98.5% of the time, ~0.4 ms per update.
- The gate is SPRT on score% (win 1, tie 0.5) vs the champion, then regression vs baseline, older
  champions and ext_*. **Builders' own numbers do not replicate, in either direction:**
  - Champion vs itself: 45.8% (60), 41.7% (24), 48.3% (30), 53.3% and 54.2% (60 each, r06cand1).
  - Builder -> gate: r06cand3 51.5% in 100 -> 57.5% in 300; r06cand1 56.3% in 120 -> 45.9% in 110;
    r05cand1 55.8% -> 69.0%; r05cand2 46% -> 65.0%; r05cand3 56.2% -> 48.6%.
  - r07: cand2 53.5% in 100 -> 50.0% in 260; cand3 same-seed 56.7% in 60 -> 50.0% in 290.
  - r09: cand1 52.5% in 100 -> 45.0% in 130; cand2 55.5% in 100 -> 49.7% in 190; cand3 55.8% in 60
    -> 49.6% in 230. Builders' own SPRT runs capped at 100 games are no better than any other sample.
  - Rule: under ~100 games trust nothing smaller than ~10 points; under 60, ~20.
- **Mirror colour bias:** against the champion, near-copies win crowded as RED and lose it as BLUE
  (r09, 3 candidates: red 18-0-3 +14..+25, blue 6-0-15 -12..-18). distantCapture is the same (red 16-0-3,
  blue 4-0-15). A per-layout result on these maps means nothing without the colour split.
- **Most RANDOM maps are fixed mirrors** (red/blue get +x/-x whatever we change). Only games whose
  result CHANGES carry signal: run the parent as a same-seed control and compare game by game, both
  colours, never the same `--seed` in two arenas at once. **Same seed is NOT deterministic**: a
  never-firing NO-OP matched only 35/60 games of its control and scored 3.3 points lower (r07cand1);
  a control rerun gave 52.5% then 46.7% (r07cand2). A 60-game same-seed run is +-7 points.
- **Harness trap:** `arena.play()` with a missing path or one not ending in `.py` prints plausible
  0 s all-tie results and no error. Check that "secs" looks real.
- Timing: gate games 3-24 s wall-clock, no warning in ~1300 gate games. A 150-playout defender
  search hit 0.26-0.30 s per move (r06cand2) - that is the budget scale for playouts.

## Round 9 (all three from r08cand2; all rejected)
- **Cause of r08's crowded-red collapse found (r09cand1):** it is specific to r06cand3 (vs champ_r06
  crowded red is +19 every game). Not the route, not dead ends. Our Pacman carrying 16, 1 step from
  home, is eaten by an ENEMY PACMAN carrying 24 that steps back over the border and becomes a ghost
  at the shared middle gap. `_threats` ignores visible enemy Pacmen.
- **r09cand1 LATENT_D (visible enemy Pacman within 3.5 cols of the border counted as a ghost):
  rejected, 45.0% in 130.** It fixed crowded red vs r06cand3 (-47 -> +5 in 8) but in the mirror office
  red went 0-0-6 -31 (deaths 2.5, drop 74/game), and overall drop 8.3/game vs 2.3-3.6 for the other
  candidates. Treating every enemy Pacman near the border as a wall makes the carrier take worse paths
  and die. If retried: count only enemy Pacmen that CARRY food and are adjacent to the border, and
  require office drop not to rise.
- **r09cand2 SMALLMAP port onto ROUTE: rejected, 49.7% in 190.** Gate small maps: alley 5-1-6 (bank
  6.5 / conc 6.6), fast 4-6-2. r08cand1's alley 18-0-4 against r06cand3 did not carry over to the ROUTE
  mirror. Settled: a guard from move 0 on small maps is not a lever against the champion.
- **r09cand3 sticky turtle + late turtle: rejected, 49.6% in 230.** Late turtle with 150 moves left
  lost whole trips on jumbo; with 50 moves it rarely fires (~4/30 games); hysteresis is neutral.
  Settled: neither late-game nor sticky turtling is a lever in the mirror.
- **Ties are standoffs where nobody scores, not lost leads.** defaultCapture 27 of 30 tied (cand2+3) with
  bank ~1-3 per side, fast 15 of 28 tied with bank 0-2; tiny red tied 0-0 6/6 (cand2 notes). Ties are
  ~14% of gate games; a turtle cannot convert them, only banking 1-2 more dots on these maps can.
- Kill rate stays 0.20-0.25/game in every r09 variant; office red still dies 0.75-1.2 times/game.

## Rounds 6-8, condensed
- **r08cand2 ROUTE_ON promoted, 57.9% in 170** vs r06cand3: jumbo 10-0-4 +20, office 9-0-3 +9.8,
  drops 3.0/game vs 5.2. Its crowded-red losses (-43..-56) were the border ambush above.
- r08cand1 SMALLMAP: 52.0% in 300 vs r06cand3 (alley 18-0-4); did not carry over to ROUTE (r09cand2).
- r08cand3 EXPLOIT (double attack, then BOTH guard from lead >= 3): 52.3% in 300; crowded 1-0-23,
  kills 0.17. A single guard from move 0 lost 37.5%: the second invader walks home.
- **Mirror profile** (r07, 550 games): bank = conc ~30, office drop 20-29/game, jumbo 16, crowded
  15; kill 0.26-0.33/game; no fixed weak map (apart from the colour bias above).
- **Rejected, do not retry:** carry-triggered recall while lead < 4 (r07cand1, 35.0%: costs bank 3-7
  everywhere); load caps (r07cand3 `RUNNER_BANK`, trade drops for bank 1:1); decoy role (50.0% in
  290); two-invader cover in turtle phase (r07cand2, 50.0% in 260); EXIT_ON exit slack (~50% over 330).
- r06cand2 defender-only playout search: 42.5% in 40 (fired only when a lone defender could not
  cover; 0.26-0.30 s/move). Never retried as JOINT search where the joint margin is 1-2.
- Harness: never run two arenas at once (shared `www/` score files -> "UNCLEAN").

## Defence: what is established
- **Covering every exit is the lever; chasing is worth nothing.** r04cand1 `_guard`: 71.7% in 30;
  r05cand1 (+ attacker as second jaw, `HELP_ON`): 69.0% in 50 on top. Helper ablation (60 games):
  kills 25 vs 11, conceded 651 vs 1022. Kills happen only when ALL exits are covered.
- `_guard`/`joint_cover` cover ONE invader (the one carrying most); the mirror sends two.
- Under the r06+ champions this defence only runs when lead >= 4. Guard exits are every open border
  cell (14 on the RANDOM404807 pipe map), not the real crossings. `GUARD_CAPS`, `SCARED_GAP` never ablated.

## Attacker: what is established
- Planning + banking beat reflex 90% (r01). **Soft costs beat hard safety rules** (r02: 83.3%; again
  r09cand1: making enemy Pacmen hard threats raised deaths).
- **Do not retry:** Monte Carlo checks of the attacker's plan (3 times, 57/39/28%); tracker guess as
  wall, pocket penalty (51.7%); longer trips (41.2%). Win count is what scores, not margin.
- Against one real guard the attacker gets sealed in; a second attacker beat that (r06cand3).
  Trip ordering (ROUTE_ON) beat greedy one-dot choice.

## Known failure patterns
- **Standoff maps (default, fast, tiny):** both sides bank 0-3, most games tie. Before r06 every
  version was a coin flip there; opportunistic raiding (48.6%), aggression (20-30%), SMALLMAP guard
  (r09) all failed. The cause of the zero banking has never been logged.
- **officeCapture**: the most dots die there (drop 20-74/game, deaths 0.75-2.5 as red).
- **Big maps are decided by one load**: jumbo swings -105..+87.
- **Border ambush**: a returning enemy Pacman steps home next to our carrier and eats it (r06cand3
  does it on crowded). Only a soft, narrow fix is worth trying (see r09cand1).
- Old (not rechecked under ROUTE): RANDOM566311 red -12 for every version; RANDOM404807 (2-wide
  border pipe) red -18 for r04cand1.

## Open questions (untested)
- Why defaultCapture/fast bank ~1: which rule stops our attackers crossing (log it first).
- Opportunistic kills by an agent that is already home (kill rate 0.2-0.3/game), not a recall.
- Joint-move playout search for defence where joint margin is 1-2 (KNOWLEDGE sec. 1, 3).
- Shared routes between the two attackers on big maps.
- Process: same-seed parent control + per-flag ablation is the standard; log layout AND colour next
  to kills / conceded / banked.
