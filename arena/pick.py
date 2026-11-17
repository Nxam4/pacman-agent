#!/usr/bin/env python3
"""Promotion gate helpers for loop.sh.

  pick.py --clean REPORT.json
      Exit 0 if no crash, forfeit, timeout warning or unscored game (smoke stage).

  pick.py --sprt REPORT.json
      Print the SPRT decision of an  arena.py --sprt  report: H1 / H0 / inconclusive / unclean.

  pick.py --merge OUT.json A.json B.json
      Combine two arena reports (e.g. regression + field run) into one (summary recomputed).

  pick.py --paired A.json B.json
      Paired comparison of two arena runs on identical games (same opponents, --games, --seed):
      prints "diff se n" in score points (win 1, tie 0.5) per game, A minus B.

  pick.py --select REGRESS_MIN [--league-min L] [--field-min F] [--champ-field CF.json] CAND_DIR ...
      With --champ-field: CAND_DIR/field.json (the candidate vs the ext_gh_* teams) is compared
      game by game with the champion's run on the same games; the candidate must not be measurably
      worse vs the field (95% interval of the paired difference not entirely below 0). Added after
      the 2026-11-17 benchmark: a tuned version scoring 71.7% vs the old champion was +0.4 +- 2.6
      points vs held-out teams - the mirror match alone over-states progress.
      Each CAND_DIR may hold sprt.json (arena --sprt vs the champion) and regress.json (fixed games vs
      baseline + recent champions + league). A candidate qualifies if its SPRT accepted H1 (better
      than the champion) and its regression run is clean with score% >= REGRESS_MIN against the
      baseline and every past champion (a loose sanity bound: no collapse against older teams), and
      >= L (default 20) against league opponents (arena/opponents/exploit_* and our ext_*: they may
      legitimately beat the champion, so only a collapse counts). The third-party training teams
      (arena/opponents/ext_gh_*, few games each) are judged together: combined score% >= F
      (default 75; the champion scores ~88% vs them). Prints the qualifier with the highest SPRT
      score, or nothing.

Why SPRT instead of a fixed "24 games >= 55% contest points": contest points % depends on the
tie rate, so with the ~60% ties we see, a genuinely better team (60% score) passed the old gate
only ~10% of the time in simulation; SPRT on the symmetric score (win 1, tie 0.5) keeps false
promotions near alpha (5%) at any tie rate and stops early when the answer is clear.
"""
import json
import os
import sys


def load(path):
    with open(path) as f:
        return json.load(f)


def clean(t):
    return (t["crashes"] == 0 and t["timeouts"] == 0 and t.get("forfeits", 0) == 0
            and t.get("no_score", 0) == 0)


def cmd_clean(path):
    try:
        t = load(path)["summary"]["total"]
    except Exception as e:
        print(f"clean: unreadable {path} ({e})", file=sys.stderr)
        return 1
    ok = clean(t)
    print(f"smoke: crashes={t['crashes']} slow={t['timeouts']} forfeits={t.get('forfeits', 0)} "
          f"no_score={t.get('no_score', 0)} -> {'pass' if ok else 'FAIL'}", file=sys.stderr)
    return 0 if ok else 1


def sprt_decision(path):
    try:
        s = load(path).get("sprt") or {}
        return s.get("decision", "missing"), s
    except Exception:
        return "missing", {}


def is_field(opp):
    """Third-party training teams (arena/opponents/ext_gh_*): judged as one group."""
    return "/ext_gh_" in opp


def is_league(opp):
    """Exploiters / external teams: they may beat the champion, so they get a lower floor."""
    return ("/exploit_" in opp or "/ext_" in opp) and not is_field(opp)


def field_score(by_opp):
    """Combined score% over the ext_gh_* opponents, or None if there are none."""
    g = [(v.get("games", 0), v.get("score_pct", 0)) for k, v in by_opp.items() if is_field(k)]
    n = sum(x for x, _ in g)
    return round(sum(x * s for x, s in g) / n, 1) if n else None


def game_pts(r):
    return 1.0 if r["cand_score"] > 0 else (0.5 if r["cand_score"] == 0 else 0.0)


def paired(a_path, b_path):
    """(mean diff, standard error, n) of A minus B over games paired by order (identical games)."""
    ga, gb = load(a_path)["games"], load(b_path)["games"]
    if len(ga) != len(gb) or not ga or any(x["opponent"] != y["opponent"] or x["layout"] != y["layout"]
                                           for x, y in zip(ga, gb)):
        raise ValueError("runs are not on identical games")
    d = [game_pts(x) - game_pts(y) for x, y in zip(ga, gb)]
    n = len(d)
    m = sum(d) / n
    var = sum((x - m) ** 2 for x in d) / max(1, n - 1)
    return m, (var / n) ** 0.5, n


def cmd_merge(out, a_path, b_path):
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import arena
    a, b = load(a_path), load(b_path)
    games = a["games"] + b["games"]
    with open(out, "w") as f:
        json.dump({"candidate": a.get("candidate"), "summary": arena.summarise(games), "sprt": None,
                   "games": games}, f, indent=1)
    return 0


def cmd_select(regress_min, dirs, league_min, field_min=75.0, champ_field=None):
    best, best_score = None, -1.0
    for d in dirs:
        name = os.path.basename(d.rstrip("/"))
        dec, s = sprt_decision(os.path.join(d, "sprt.json"))
        if dec != "H1":
            print(f"{name}: sprt={dec} -> rejected", file=sys.stderr)
            continue
        try:
            reg = load(os.path.join(d, "regress.json"))["summary"]
        except Exception:
            print(f"{name}: sprt=H1 but no regression report -> rejected", file=sys.stderr)
            continue
        bo = reg["by_opponent"]
        core = [v.get("score_pct", 0) for k, v in bo.items() if not is_league(k) and not is_field(k)]
        lg = [v.get("score_pct", 0) for k, v in bo.items() if is_league(k)]
        worst = min(core or [0])
        lworst = min(lg) if lg else None
        field = field_score(bo)
        ok = (clean(reg["total"]) and worst >= regress_min and (lworst is None or lworst >= league_min)
              and (field is None or field >= field_min))
        fpair = "-"
        if champ_field:
            try:
                m, se, n = paired(os.path.join(d, "field.json"), champ_field)
                fpair = f"{100 * m:+.1f}+-{100 * se:.1f} ({n} paired)"
                ok = ok and m + 1.96 * se >= 0
            except Exception as e:
                fpair = f"missing ({e})"
                ok = False
        print(f"{name}: sprt=H1 score={100 * s.get('score', 0):.1f}% games={s.get('games')} "
              f"regression worst={worst}% league worst={lworst if lworst is not None else '-'}% "
              f"field={field if field is not None else '-'}% vs champion on field {fpair} "
              f"clean={clean(reg['total'])} -> {'OK' if ok else 'rejected'}", file=sys.stderr)
        if ok and s.get("score", 0) > best_score:
            best, best_score = os.path.join(d, "my_team.py"), s.get("score", 0)
    if best:
        print(best)
    return 0


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    if mode == "--clean":
        sys.exit(cmd_clean(sys.argv[2]))
    if mode == "--sprt":
        print(sprt_decision(sys.argv[2])[0])
        sys.exit(0)
    if mode == "--select":
        rest = sys.argv[3:]
        lmin, fmin, cf = 20.0, 75.0, None
        while rest[:1] in (["--league-min"], ["--field-min"], ["--champ-field"]):
            if rest[0] == "--league-min":
                lmin = float(rest[1])
            elif rest[0] == "--field-min":
                fmin = float(rest[1])
            else:
                cf = rest[1]
            rest = rest[2:]
        sys.exit(cmd_select(float(sys.argv[2]), rest, lmin, fmin, cf))
    if mode == "--merge":
        sys.exit(cmd_merge(*sys.argv[2:5]))
    if mode == "--paired":
        m, se, n = paired(sys.argv[2], sys.argv[3])
        print("%.4f %.4f %d" % (m, se, n))
        sys.exit(0)
    print(__doc__)
    sys.exit(2)
