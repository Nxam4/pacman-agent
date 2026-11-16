#!/usr/bin/env python3
"""Promotion gate helpers for loop.sh.

  pick.py --clean REPORT.json
      Exit 0 if no crash, forfeit, timeout warning or unscored game (smoke stage).

  pick.py --sprt REPORT.json
      Print the SPRT decision of an  arena.py --sprt  report: H1 / H0 / inconclusive / unclean.

  pick.py --select REGRESS_MIN CAND_DIR [CAND_DIR ...]
      Each CAND_DIR may hold sprt.json (arena --sprt vs the champion) and regress.json (fixed games vs
      baseline + recent champions). A candidate qualifies if its SPRT accepted H1 (better than the
      champion) and its regression run is clean with score% >= REGRESS_MIN against every opponent
      (a loose sanity bound: no collapse against older teams). Prints the qualifier with the
      highest SPRT score, or nothing.

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


def cmd_select(regress_min, dirs):
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
        worst = min([v.get("score_pct", 0) for v in reg["by_opponent"].values()] or [0])
        ok = clean(reg["total"]) and worst >= regress_min
        print(f"{name}: sprt=H1 score={100 * s.get('score', 0):.1f}% games={s.get('games')} "
              f"regression worst={worst}% clean={clean(reg['total'])} -> {'OK' if ok else 'rejected'}",
              file=sys.stderr)
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
        sys.exit(cmd_select(float(sys.argv[2]), sys.argv[3:]))
    print(__doc__)
    sys.exit(2)
