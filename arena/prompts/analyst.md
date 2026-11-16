You are the analyst for an autonomous loop that improves a Pacman Capture-the-Flag team.
Read CLAUDE.md for the contest rules.

This round's material is in {{ROUND_DIR}}/cand_*/ : each has my_team.py, NOTES.md (the builder's own
account), CONTEXT.md (what it was given), direction, model, parent_id, and status - the evaluation
cascade outcome: unchanged / invalid / smoke_fail (crash or timeout vs baseline, see smoke.txt) /
unclean (crash or timeout during the SPRT) / rejected (SPRT vs champion accepted H0: not better) /
inconclusive (SPRT hit its game limit - a near-miss if its score is above 52%) / regress_fail (better
than the champion but collapsed vs the baseline or an older champion, see regress.txt) / not_chosen
(qualified, another candidate scored higher) / passed (the winner). sprt.txt shows the sequential
test (score% with win 1 / tie 0.5, 50 = equal; LLR trajectory); the json files hold per-game
layouts and scores. SPRT results are reliable (~5% false positives); builders' own --quick numbers
are not.
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
