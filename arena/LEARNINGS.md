# Learnings (maintained by the analyst agent)

Champion history: seed (r00: tracker defender + nearest-food reflex attacker) -> r01cand1
(BankingAttacker) -> r02cand1 (soft-cost Dijkstra attacker + invader snap) -> r04cand1 (same
attacker + exit-denial defender `_guard`) -> **r05cand1** (r04cand1 + attacker as second guard
`HELP_ON` + dead-end mouth trap `TRAP_ON`). Past programs: `arena/db/progs/<id>.py`; frozen
champions `arena/opponents/champ_r*`.
Champion gate: 29-11-10, 69.0% in 50 vs r04cand1, avg margin +10.4; regress 12-0-0 baseline,
10-0-2 champ_r02, 9-1-2 champ_r04.

## Standing facts
- **EnemyTracker works** (inside my_team.py). Best guess of a hidden enemy is off by 3.2 cells on
  average (12.1 for "last seen"); true cell inside the belief 98.5% of the time; ~0.4 ms per update.
- The gate is SPRT on score% (win 1, tie 0.5) vs the champion, then a regression check vs baseline
  and older champions. **Builders' own numbers do not replicate, in either direction:**
  - The champion against itself: 45.8% in 60 games (r05cand1's control), 41.7% in 24 (r05cand3's
    control; the SPRT even "accepted H0" for it), 48.3% in 30 gate games (r04).
  - Builder -> gate: r05cand1 55.8% in 120 -> 69.0% in 50; r05cand2 46% in 96 (two H0 verdicts)
    -> 65.0% in 30 (H1); r05cand3 56.2% in 24 -> 48.6% in 70; r03cand2 55-69% -> 41.2%.
  - Rule: under ~60 games trust nothing smaller than ~20 points.
- **Most RANDOM maps are fixed mirrors: red and blue get +x/-x whatever we change.** In the r05
  gate all three candidates scored RANDOM566311 R-12/B+12, RANDOM484028 R-1/B+1, and 0/0 on
  RANDOM145045 / 396019 / 774805 / 836070. Only games whose result CHANGES carry signal. So: run
  the parent as a control on the same seed and compare game by game (r05cand1 and r05cand3 did;
  it was the most useful measurement of the round). Test both colours, never the same `--seed`
  in two arenas at once.
- **Harness trap:** `arena.play()` with a candidate path that does not exist, or that does not
  end in `.py` (e.g. `.bak`), prints plausible scores (0 s games, all ties) and no error. Check
  that "secs" looks real.
- Timing is not a constraint yet: gate games 3-13 s wall-clock, no warning in ~900 gate games over
  four rounds; the 5x5 joint move search costs nothing measurable.

## Round 5 (all three candidates started from r04cand1)
- **r05cand1 COORDINATION-HELPER: promoted, 69.0% in 50.** The attacker joins the exit cover when
  it is at home or <= 6 from the border, carries <= 2, is not scared, and the invader carries >= 3
  or is within 8 (`HELP_NEAR`); both pick moves from a 5x5 joint search minimising max over exits
  of min(d_def, d_att) - d_inv; if both together cannot cover, the attacker goes back to attack.
  Builder's same-seed ablation (60 games each, vs r04cand1; control = 45.8%):
  help only 50.0%, kills 25 vs 11, dots conceded 651 vs 1022, dots scored 800 vs 883;
  trap only 51.7%, kills 7; both 55.8% on two seeds; `HELP_NEAR=0` loses the gain; 12 = 8.
  So: **the helper is what kills invaders (2.3x), and it costs ~10% of our own scoring.** The trap
  adds no kills on its own. Gate games that changed vs the mirror pattern: RANDOM577531 +13/+4
  (others -4/+4), RANDOM616917 +14/+13 (others -13/+10), crowded +33/+51/+35/+51, jumbo 5 of 6
  won. Worse: RANDOM227634 R-3/B-17 (others R+17/B-17), office 0/+12/-11/+2/-9/-6.
- **r05cand2 OFFENSE-ANTIGUARD: passed the gate, not chosen: 17-5-8, 65.0% in 30, avg +4.8**
  (regress 12-0-0 baseline, 10-1-1 champ_r02, 8-1-3 champ_r04). `EXIT_ON`: exit slack = max over
  home-border cells of (located ghost's arrival - ours via the dot); dots with slack < 2 cost more;
  carrying >= 2 and the chosen dot has slack < 1 -> bank first; enter on the side away from the
  defender. **Conflicting evidence:** the builder's own two SPRTs said H0 (47.1% in 52, 45.5% in
  44, seed 501). 126 games together are ~51%. Treat as unproven, not as failed; it is the only
  attacker change since r02 to pass a gate, and it is not in the champion. Its gate signal came
  from office (+27/+53/+38/-9), strategic and crowded; 4 of 6 RANDOM pairs were pure mirrors.
  Solid findings from its diagnostics (16 champion mirror games):
  - **Our attacker rarely dies (2-4 deaths per 16 games). It gets sealed in**: 460-870 attacker
    moves per 16 games with exit slack < 1, carrying ~22 dots, until the game ends. Trace jumbo
    red: carrying 44, oscillating 2 steps from home for 160 moves; same on alley (100-155 moves).
  - The capsule escape almost never fires: the guard covers the capsule too (`GUARD_CAPS`).
  - Banking earlier cut dots-stuck-while-sealed by half, and the builder saw no more wins; its
    reading: a sealed attacker also pins their guard, so leaving frees it.
- **r05cand3 COORDINATION-ROLES: rejected, 25-18-27, 48.6% in 70, avg +0.8.** Defender raids 1-2
  dots when no invader for 8 moves (`RAID_ON`), attacker covers meanwhile (`SWAP_ON`). The raid
  almost never fires: on fastCapture the enemy attacker stands in sight at our border all game
  (belief mass 1.0 for ~250 moves); fastCapture stayed 0/0/0/0 in the gate and default got worse
  (0/+7/-6/-3/-5/-5). **Small maps end in a 2x2 border standoff**: each of our agents faces one
  of theirs, and whoever leaves lets the other in. Opportunistic raiding does not break it.

## Defence: what is established
- **Covering every exit is the lever; chasing is worth nothing.** r04cand1 `_guard` (stand where
  we reach every border exit no later than the invader, then close in): 71.7% in 30. r04cand2
  (same idea, joint with the attacker): 67.5% in 40. r05cand1 (both): 69.0% in 50 on top.
  "Cut the shortest way home and chase from behind" was neutral (16 games 7-2-7): our kind of
  attacker only takes paths it reaches first, so kills happen only when ALL exits are covered.
- `GUARD_CAPS` (our capsules count as exits) and `SCARED_GAP` (scared defender blocks at
  distance 2) came from one trace and were never ablated.
- Never built: any search or playout for the defenders.

## Attacker: what is established (rounds 1-5)
- A planning attacker that banks food beat the reflex attacker 90% (r01). **Soft costs beat hard
  "provably safe" rules** (r02: 83.3% in 30; hard safe-return filter 60%). `SAFE_RETURN = False`.
- **Sampled-world (Monte Carlo) checks of the attacker's plan do not help - tested three times**
  (57.1% in 120; 39.1% in 32; 28.1% in 16). Do not retry without a new source of information.
- Safety ideas with no gate gain: tracker guess as a wall, pocket penalty (r04cand3, 51.7% in 30;
  its cut-cell pocket map `_pockets` is sound and cheap), longer trips (r03cand2: 41.2% in 40 with
  avg margin +2.1 - bigger loads raise the margin on a few maps and lose more close games).
  Win count is what scores, not margin.
- The problem has moved from dying to being sealed in (see r05cand2). Old death-based ideas
  (load cap, pocket penalty) aim at 2-4 deaths per 16 games.
- The attacker waiting at the border is a de facto second defender. Stall-aggression scored
  20-30% on fast/alleyCapture; late gamble and "lead lock" were neutral.

## Known failure patterns
- **Small maps are coin flips near 0** (2x2 standoff above). r05cand1 gate: alley 0/+1/+1/+1,
  distant -3/+7; r05cand3: fast 0/0/0/0. Four rounds, nothing has moved them.
- **Big maps are decided by one load**: jumbo -105/+87 (r05cand2), -77/+78, -47 (r05cand3);
  strategic -32/+22. officeCapture is the champion's weakest fixed map in the gate (3 losses, 1
  tie in 6) and it tied/lost office vs champ_r04 in regress.
- Maps lost in regress by BOTH r05cand1 and r05cand2: RANDOM294127 as red vs champ_r02 (-1, -7)
  and RANDOM493143 as red vs champ_r04 (-2, -10). RANDOM566311 red is -12 for every version.
- RANDOM227634 red: +17 for r04cand1-like teams, -3 with the helper on. Unexplained; trace it:
  `cd pacman-contest/src/contest && python capture.py -r ../../../my_team.py -b ../../../arena/opponents/champ_r04/my_team.py -l RANDOM227634 -q`
- RANDOM404807 (2-wide border pipe joined to each half only at top and bottom): r04cand1 vs seed
  blue +28, red -18; vs baseline -15/-13. Guard exits are all 14 pipe cells, not the two real
  crossings. Not rechecked with the helper.

## Open questions (untested)
- Does `EXIT_ON` (r05cand2) add to r05cand1? The mirror opponent's helper now triggers when our
  invader carries >= 3, so banking at 2 may matter more than it did against r04cand1.
- Helper only when the defender alone cannot cover (solo margin > 0): would it keep the kills
  and give back the lost scoring?
- Breaking a seal with the second agent (their guard follows the bigger load), and an active
  "mark their attacker, then raid on the far side" switch for the 2x2 standoff. Both need two
  agents acting on a shared flag; r05cand3's passive version did not fire.
- Guard exits on pipe/choke maps; where the defender waits with no invader.
- Playout search for the defenders with an invader model (KNOWLEDGE sec. 1 and 3).
- Process: builders finish in good time with honest notes. A same-seed control run of the parent
  plus per-flag ablation is now the standard; log the layout name next to kills/conceded.
