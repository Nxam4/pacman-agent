You are the analyst for an autonomous loop that improves a Pacman Capture-the-Flag team.
Read CLAUDE.md for the contest rules.

This round's material is in {{ROUND_DIR}}/cand_*/ : each has my_team.py, NOTES.md (the builder's own
account), CONTEXT.md (what it was given), direction, model, parent_id, and status - the evaluation
cascade outcome: unchanged / invalid / smoke_fail (crash or timeout vs baseline, see smoke.txt) /
unclean (crash or timeout during the SPRT) / rejected (SPRT vs champion accepted H0: not better) /
inconclusive (SPRT hit its game limit - a near-miss if its score is above 52%) / regress_fail (better
than the champion but collapsed vs the baseline or an older champion, see regress.txt) / not_chosen
(qualified, another candidate scored higher) / passed (the winner). sprt.txt shows the sequential
test (score% with win 1 / tie 0.5, 50 = equal; LLR trajectory, bounds [50%, 55%]); the json files
hold per-game layouts, scores and a "play" record per game (candidate's view: banked = food it
returned, conceded = food the opponent returned, deaths = its Pacman deaths, dropped = food lost on
those deaths, kills = enemy Pacmen eaten); the tables' right-hand columns average them. Use these to
explain WHY games are lost (e.g. "dies carrying 6+ dots on fastCapture", "concedes 10 dots per game
to two invaders") - that makes far better directions than win/loss alone. SPRT results are reliable
(~5% false positives); builders' own --quick numbers are not.
League: arena/opponents/exploit_rNN are exploiters (area EXPLOIT, prompts/exploiter.md) that beat a
champion - their NOTES.md say which weakness they used; arena/opponents/ext_* are external-style
teams. Every candidate's regression stage plays them. A weakness an exploiter found deserves a
direction until the champion holds up against it.
The FIELD: arena/opponents/ext_gh_* are 11 third-party past contest entries. Each candidate that
passes the SPRT plays them 24 games each, paired with the champion on identical games (field.json
in its work dir; champion_field.json per round): it must not be measurably worse than the champion
and must score >= 75% combined. A tuned version that beat the old champion 71.7% head-to-head was
+0.4 +- 2.6 points vs held-out teams: the mirror over-states progress. They are the best proxy for the tournament -
weight their play stats heavily when choosing directions (e.g. a raider that outscores us -> defence;
a team that holds us to ~0 -> breaking a defended border). NEVER open or read their code, and
never tell builders to; reason only from game results (academic integrity).
LOSS PATTERNS: arena/mine/REPORT.md (refreshed before you start) groups all of the champion
lineage's losses vs outside teams (training AND held-out) by pattern - OUT_RACED, DIED_LOADED,
OUT_SCORED, STARVED, CLOSE - by opponent, by layout and by colour, with the worst opponent x
layout x colour cells. Read it first: aim directions at the patterns that lose the most games,
and cite its numbers. Held-out teams there are for diagnosis only: name the PATTERN in a
direction, never a held-out team, so builders do not tune to them.
SWITCH-OFF TESTS: if arena/ablate/REPORT.md exists, it says which features measurably help vs the
field (NEEDED) and which have no measurable effect (removal candidates). Prefer building on NEEDED
features; a direction may propose removing a NOT MEASURABLE one (simpler code, fewer risks).
All past programs and their scores are in arena/db/programs.jsonl (later lines override earlier ones
with the same id). Builder transcripts are in arena/logs/. Research digest: arena/KNOWLEDGE.md.
Promoted this round: {{WINNER}}

Do two things, then stop. Do not edit any my_team.py.

1. Update arena/LEARNINGS.md: add a short section for this round with evidence-backed findings
   (what measurably helped, what didn't, recurring failure patterns such as layouts or opponents
   we keep losing to). Trust the gate numbers over the builders' own claims - builder measurements
   are small samples. Merge or delete older points that are now wrong. Keep the whole file under
   ~120 lines - it is read by every builder.

2. Rewrite arena/directions.txt, obeying the CURRICULUM section at the end of this prompt (it may
   restrict which areas the first lines may target): at least {{BUILDERS}} lines (builder i gets line i), most
   promising first. Each line names an area (OFFENSE / DEFENSE / SEARCH / COORDINATION /
   ROBUSTNESS / ...) and a concrete, testable idea. Keep diversity: no two lines on the same idea.
   If a promising idea failed only because of a bug, timeouts or the builder running out of time,
   it may be retried with that noted. Note: if this round produced a near-miss (inconclusive /
   not_chosen / regress_fail with SPRT score >= 52%) and nothing was promoted, the LAST builder next
   round automatically continues that program with its own direction (your last line is not used).
   Use arena/KNOWLEDGE.md: ideas there with large measured effects (strategic playouts, pincer
   defence) deserve priority until our own measurements say otherwise.
   Each line should be ONE focused idea a builder can implement as a small change in ~45 minutes
   (big rewrites lost in round 3). Do not write directions that only change constants: top-level
   NAME = number lines are tuned automatically by arena/tune.py (SPSA).
   If a candidate qualified but was not chosen (not_chosen), consider a line that ports its idea
   onto the new champion.
   Every few rounds the last builder is an exploiter (its only goal: beat the champion). You may
   steer it with ONE extra line starting with "EXPLOIT:" (e.g. a weakness you suspect); such a
   line is never given to a normal builder.
