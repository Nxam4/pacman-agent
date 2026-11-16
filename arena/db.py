#!/usr/bin/env python3
"""Program database for the builder loop (after AlphaEvolve, Novikov et al. 2025, sec. 2.5).

Every candidate the loop produces is archived with its evaluation results, whether or not it was
promoted. The database supplies:
  * parents   - most builders start from the champion (exploitation); the last builder of a round
                (with >= 3 builders) may continue a recent near-miss instead (island-style exploration),
                so a promising lineage is not thrown away after one inconclusive test.
  * context   - a per-builder CONTEXT.md with the starting program's measured weaknesses, the best
                past program per strategy area ("inspirations", MAP-Elites style) with scores, and
                recent failures - past programs shown together with their evaluations, as in
                AlphaEvolve prompts.

Storage: arena/db/programs.jsonl (one record per line; later lines override earlier ones with the
same id), arena/db/progs/<id>.py, arena/db/champion.txt.

  db.py seed CHAMPION_FILE
  db.py parent BUILDER_INDEX N_BUILDERS ROUND          -> prints "<id> <path>"
  db.py add ID ROUND STATUS FILE --area A --direction D --model M --parent P
           [--smoke J] [--sprt J] [--regress J] [--notes NOTES.md]
  db.py promote ID
  db.py info ID FIELD                                  -> prints one field of a record
  db.py context PARENT_ID AREA OUT_FILE [--k 3]
  db.py focus-status MIN_BASELINE STALL                -> "keep" or "release: <reason>"

Statuses: unchanged, invalid, smoke_fail, unclean (crash/timeout during SPRT), rejected (SPRT H0),
inconclusive (SPRT ran out of games), regress_fail, not_chosen (passed, another was better),
champion.
"""
import argparse
import json
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(ROOT, "arena", "db")
RECS = os.path.join(DB, "programs.jsonl")
PROGS = os.path.join(DB, "progs")
CHAMP = os.path.join(DB, "champion.txt")
NEAR_MISS = float(os.environ.get("NEAR_MISS", 52))   # SPRT score % vs champion worth continuing


def load():
    out = []
    if os.path.exists(RECS):
        with open(RECS) as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        out.append(json.loads(line))
                    except ValueError:
                        pass
    return out


def latest(recs):
    d = {}
    for r in recs:
        d[r["id"]] = r
    return list(d.values())


def append(rec):
    os.makedirs(PROGS, exist_ok=True)
    with open(RECS, "a") as f:
        f.write(json.dumps(rec) + "\n")


def champion_id():
    try:
        with open(CHAMP) as f:
            return f.read().strip() or "seed"
    except IOError:
        return "seed"


def by_id(recs, rid):
    for r in reversed(recs):
        if r["id"] == rid:
            return r
    return None


def metrics(path):
    """Summarise an arena report (fixed-games or SPRT)."""
    try:
        with open(path) as f:
            rep = json.load(f)
    except Exception:
        return None
    s = rep["summary"]
    t = s["total"]
    m = {"games": t.get("games"), "score_pct": t.get("score_pct"), "crashes": t.get("crashes", 0),
         "timeouts": t.get("timeouts", 0), "forfeits": t.get("forfeits", 0),
         "max_secs": t.get("max_secs", 0),
         "by_opponent": dict((k, v.get("score_pct")) for k, v in s["by_opponent"].items()),
         "lost": sorted({"%s@%s" % (g["opponent"], g["layout"]) for g in rep.get("games", [])
                         if g.get("cand_score", 0) < 0})[:40]}
    if rep.get("sprt"):
        sp = rep["sprt"]
        m["sprt"] = {"decision": sp.get("decision"), "score_pct": round(100 * sp.get("score", 0), 1),
                     "llr": sp.get("llr"), "games": sp.get("games")}
    return m


def fitness(r):
    """SPRT score % vs the champion of its round (50 = equal), LLR as tie-break."""
    m = r.get("sprt")
    if not m or not m.get("sprt"):
        return (-1.0, 0.0)
    if m.get("crashes") or m.get("forfeits") or m.get("timeouts"):
        return (-1.0, 0.0)
    return (float(m["sprt"]["score_pct"]), float(m["sprt"].get("llr") or 0))


def head(path, n=14):
    try:
        with open(path) as f:
            lines = [l.rstrip() for l in f.readlines() if l.strip()]
        return "\n".join(lines[:n])
    except IOError:
        return ""


def fmt(r):
    parts = []
    sp = r.get("sprt")
    if sp and sp.get("sprt"):
        x = sp["sprt"]
        parts.append("SPRT vs champion: %s, score %s%% over %s games (LLR %s)"
                     % (x["decision"], x["score_pct"], x["games"], x["llr"]))
        if sp.get("crashes") or sp.get("forfeits") or sp.get("timeouts"):
            parts.append("crashes %s / forfeits %s / slow %s" % (sp["crashes"], sp["forfeits"], sp["timeouts"]))
        parts.append("slowest game %ss" % int(sp.get("max_secs") or 0))
    rg = r.get("regress")
    if rg:
        parts.append("regression score%% by opponent: %s" % rg.get("by_opponent"))
    sm = r.get("smoke")
    if sm and not parts:
        parts.append("smoke vs baseline: crashes %s, forfeits %s, slow %s"
                     % (sm.get("crashes"), sm.get("forfeits"), sm.get("timeouts")))
    return "; ".join(parts) or "not evaluated"


# ---------------------------------------------------------------- commands
def cmd_seed(a):
    if by_id(load(), "seed"):
        return
    os.makedirs(PROGS, exist_ok=True)
    shutil.copy(a.file, os.path.join(PROGS, "seed.py"))
    append({"id": "seed", "round": 0, "status": "champion", "area": "SEED", "direction": "initial team",
            "model": "", "parent": "", "prog": "arena/db/progs/seed.py", "promoted": True})
    with open(CHAMP, "w") as f:
        f.write("seed")


def cmd_parent(a):
    recs = latest(load())
    champ_path = os.path.join(ROOT, "my_team.py")
    # Island step: the LAST builder (only with >= 3 builders) continues the best near-miss of the
    # previous round - but only if that round kept the champion, since a near-miss score measured
    # against an older champion says little about the current one.
    if a.n >= 3 and a.i == a.n:
        prev = [r for r in recs if r.get("round") == a.round - 1]
        if not any(r.get("promoted") for r in prev):
            cands = [r for r in prev if r.get("status") in ("inconclusive", "not_chosen", "regress_fail")
                     and fitness(r)[0] >= NEAR_MISS]
            if cands:
                best = max(cands, key=fitness)
                p = os.path.join(ROOT, best["prog"])
                if os.path.exists(p):
                    print(best["id"], p)
                    return
    print(champion_id(), champ_path)


def cmd_add(a):
    rec = {"id": a.id, "round": a.round, "status": a.status, "area": a.area, "direction": a.direction,
           "model": a.model, "parent": a.parent, "promoted": False,
           "prog": "arena/db/progs/%s.py" % a.id}
    for key, path in (("smoke", a.smoke), ("sprt", a.sprt), ("regress", a.regress)):
        if path and os.path.exists(path):
            m = metrics(path)
            if m:
                rec[key] = m
    if a.notes:
        rec["notes_head"] = head(a.notes)
    if os.path.exists(a.file):
        os.makedirs(PROGS, exist_ok=True)
        shutil.copy(a.file, os.path.join(PROGS, a.id + ".py"))
    append(rec)


def cmd_promote(a):
    r = by_id(load(), a.id)
    if r:
        r = dict(r)
        r["promoted"] = True
        r["status"] = "champion"
        append(r)
    with open(CHAMP, "w") as f:
        f.write(a.id)


def cmd_info(a):
    r = by_id(load(), a.id)
    print((r or {}).get(a.field, ""))


def cmd_focus_status(a):
    """Decide whether the curriculum focus (arena/focus.txt) still holds. Prints 'keep' or
    'release: <reason>'. Release when the goal is met (the champion's regression score vs the
    baseline >= MIN_BASELINE) or the focus has stalled (STALL consecutive rounds without promotion)."""
    recs = latest(load())
    champ = by_id(recs, champion_id()) or {}
    base = ((champ.get("regress") or {}).get("by_opponent") or {}).get("baseline")
    rounds = sorted({r.get("round", 0) for r in recs if r.get("round", 0) > 0})
    if base is not None and base >= a.min_baseline and len(rounds) >= a.min_rounds:
        print("release: champion %s scores %s%% vs baseline (goal %s%%) after %d rounds"
              % (champion_id(), base, a.min_baseline, len(rounds)))
        return
    stalled = 0
    for rnd in reversed(rounds):
        if any(r.get("promoted") and r.get("round") == rnd for r in recs):
            break
        stalled += 1
    if stalled >= a.stall:
        print("release: %d consecutive rounds without a promotion" % stalled)
        return
    print("keep")


def cmd_context(a):
    recs = latest(load())
    cid = champion_id()
    out = ["# Context for this builder (generated from the program database)", ""]
    out.append("## Your starting program")
    if a.parent == cid:
        out.append("You start from the CURRENT CHAMPION (id `%s`)." % cid)
        champ = by_id(recs, cid)
        if champ and champ.get("sprt"):
            out.append("How it earned promotion: " + fmt(champ))
            if champ["sprt"].get("lost"):
                out.append("Games it lost in that test: " + ", ".join(champ["sprt"]["lost"]))
    else:
        p = by_id(recs, a.parent) or {}
        out.append("You start from NEAR-MISS `%s` (round %s, %s), NOT the champion. It came close to "
                   "promotion; your job is to finish it. Its idea: %s"
                   % (a.parent, p.get("round"), p.get("area"), p.get("direction")))
        out.append("Its evaluation: " + fmt(p))
        if (p.get("sprt") or {}).get("lost"):
            out.append("Games it lost vs the champion: " + ", ".join(p["sprt"]["lost"]))
        if p.get("notes_head"):
            out += ["Its builder's notes (head):", "```", p["notes_head"], "```"]
    out.append("")

    # MAP-Elites-style inspirations: the best evaluated program per strategy area (niche).
    evaluated = [r for r in recs if r["id"] not in ("seed", a.parent) and fitness(r)[0] >= 0]
    elites = {}
    for r in evaluated:
        k = r.get("area", "?")
        if k not in elites or fitness(r) > fitness(elites[k]):
            elites[k] = r
    ranked = sorted(elites.values(), key=fitness, reverse=True)
    same = [r for r in ranked if r.get("area") == a.area][:1]
    picks = (same + [r for r in ranked if r.get("area") != a.area])[:a.k]
    out.append("## Inspirations (best past program per area; score% is vs the champion of its round, "
               "50 = equal) - read the code for ideas, do not copy blindly")
    if not picks:
        out.append("None yet.")
    for r in picks:
        out.append("- `%s` [%s, round %s]%s - %s" % (r["prog"], r.get("area"), r.get("round"),
                                                   " (PROMOTED)" if r.get("promoted") else "",
                                                   r.get("direction", "")[:220]))
        out.append("  " + fmt(r))
    out.append("")

    bad = ("unchanged", "invalid", "smoke_fail", "unclean", "rejected", "regress_fail")
    fails = sorted([r for r in recs if r.get("status") in bad], key=lambda r: r.get("round", 0),
                   reverse=True)[:6]
    out.append("## Recent failures (avoid repeating these without a new angle)")
    if not fails:
        out.append("None yet.")
    for r in fails:
        out.append("- round %s [%s] %s: %s -- %s" % (r.get("round"), r.get("area"), r.get("status"),
                                                   r.get("direction", "")[:160], fmt(r)))
    with open(a.out, "w") as f:
        f.write("\n".join(out) + "\n")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd")
    p = sub.add_parser("seed"); p.add_argument("file")
    p = sub.add_parser("parent"); p.add_argument("i", type=int); p.add_argument("n", type=int)
    p.add_argument("round", type=int)
    p = sub.add_parser("add")
    p.add_argument("id"); p.add_argument("round", type=int); p.add_argument("status"); p.add_argument("file")
    for x in ("--area", "--direction", "--model", "--parent", "--smoke", "--sprt", "--regress", "--notes"):
        p.add_argument(x, default="")
    p = sub.add_parser("promote"); p.add_argument("id")
    p = sub.add_parser("info"); p.add_argument("id"); p.add_argument("field")
    p = sub.add_parser("focus-status"); p.add_argument("min_baseline", type=float)
    p.add_argument("stall", type=int)
    p.add_argument("min_rounds", type=int, nargs="?", default=0)
    p = sub.add_parser("context"); p.add_argument("parent"); p.add_argument("area"); p.add_argument("out")
    p.add_argument("--k", type=int, default=3)
    a = ap.parse_args()
    fn = {"seed": cmd_seed, "parent": cmd_parent, "add": cmd_add, "promote": cmd_promote,
          "info": cmd_info, "context": cmd_context, "focus-status": cmd_focus_status}.get(a.cmd)
    if not fn:
        ap.print_help()
        return 2
    fn(a)
    return 0


if __name__ == "__main__":
    sys.exit(main())
