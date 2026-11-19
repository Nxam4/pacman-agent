#!/usr/bin/env python3
"""Switch-off tests: does each feature of the champion still earn its place against the field?

Stockfish keeps code only if it earns it ("simplification" tests with non-regression bounds), and
in 2020 had to revert patches that each passed as improvements but together regressed. Our
promotions since r08 were judged mostly head-to-head against the previous champion, and those
gains mostly did not transfer to outside teams - so whether each switch still helps against the
field is open. No Claude usage: games only.

For each variant (one switch flipped, or one constant reset), the variant and the champion play
the same games against the ext_gh_* training teams; the paired difference (variant minus
champion, win 1 / tie 0.5, opponent crashes left out) decides. Racing (successive halving):
  stage 1: one seed for every variant (24 games x 11 teams);
  stage 2+: only variants not already clearly worse get another seed, so the close ones get the
            most games.  The champion's run for each seed is played once and shared.
Verdicts (95% interval of the paired difference):
  NEEDED          entirely below 0: turning it off hurts - keep it
  NOT MEASURABLE  contains 0: no measurable effect - removal candidate (simpler, fewer risks)
  OFF IS BETTER   entirely above 0: the feature hurts - remove it
A variant that crashes or times out in the smoke test is reported BROKEN (its off-path is dead code).
The held-out benchmark teams are never used (this is a selection decision).

  python3 arena/ablate.py                    # all variants, up to 3 seeds
  python3 arena/ablate.py --only route_off,help_off --seeds 2
  python3 arena/ablate.py --list
Output: arena/ablate/REPORT.md, results.json, runs/*.json (git-ignored).
"""
import argparse
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import arena  # noqa: E402
import pick  # noqa: E402

ROOT = arena.ROOT
OUT = os.path.join(ROOT, "arena", "ablate")
SEEDS = [5151, 5252, 5353, 5454]

# name: ({CONSTANT: new value}, what it tests)
VARIANTS = {
    "help_off": ({"HELP_ON": "False"}, "attacker as second jaw of the exit cover (r05)"),
    "trap_off": ({"TRAP_ON": "False"}, "defender holds the mouth of a dead end (r05)"),
    "guard_caps_off": ({"GUARD_CAPS": "False"}, "defender also covers our capsules"),
    "snap_off": ({"INVADER_SNAP": "False"}, "eat an invader within 3 steps when at home"),
    "route_off": ({"ROUTE_ON": "0"}, "multi-dot trip planning (r08)"),
    "lane_split_off": ({"LANE_SPLIT": "0"}, "food split top/bottom between the attackers (r06)"),
    "double_attack_off": ({"DOUBLE_ATTACK": "0"}, "both agents attack (r06 exploiter)"),
    "ghost_mem_off": ({"GHOST_MEM": "0"}, "ghost memory (r15)"),
    "turtle_lead_3": ({"TURTLE_LEAD": "3"}, "tuner's biggest change: defend from lead 1 (was 3)"),
    "safe_return_on": ({"SAFE_RETURN": "True"}, "the one switch that is OFF: turn it on"),
}


def render(src, changes):
    out = src
    for name, val in changes.items():
        pat = re.compile(r"^(%s\s*=\s*)(\S+)(.*)$" % re.escape(name), re.M)
        if len(pat.findall(out)) != 1:
            raise ValueError("%s: expected exactly one top-level line" % name)
        out = pat.sub(lambda m: m.group(1) + val + m.group(3), out)
    return out


def busy():
    for pat in ("arena/loop.sh", "arena/tune.py"):
        if subprocess.run(["pgrep", "-f", pat], capture_output=True).returncode == 0:
            return pat
    return None


def save(path, results, cand):
    with open(path, "w") as f:
        json.dump({"candidate": cand, "summary": arena.summarise(results), "games": results}, f, indent=1)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", default="", help="comma list of variant names")
    ap.add_argument("--seeds", type=int, default=3, help="max seeds per variant (racing stages)")
    ap.add_argument("--games", type=int, default=24, help="games per field team per seed (even)")
    ap.add_argument("--workers", type=int,
                    default=int(os.environ.get("ARENA_WORKERS", 0)) or max(1, (os.cpu_count() or 2) - 1))
    ap.add_argument("--python", default=sys.executable)
    ap.add_argument("--hours", type=float, default=0, help="start no new run after this many hours")
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args()
    deadline = time.time() + a.hours * 3600 if a.hours else None
    src = open(arena.CHAMPION).read()
    names = [n for n in a.only.split(",") if n] or list(VARIANTS)
    if a.list:
        for n in names:
            print("%-18s %-28s %s" % (n, ", ".join("%s=%s" % kv for kv in VARIANTS[n][0].items()), VARIANTS[n][1]))
        return 0
    while busy():
        print("%s  waiting for %s to finish" % (time.strftime("%F %T"), busy()), flush=True)
        time.sleep(120)
    field = sorted(x for x in glob.glob(os.path.join(arena.OPPONENT_DIR, "ext_*", "my_team.py")) if arena.is_ext_gh(x))
    if not field:
        print("no ext_gh_* training teams (run arena/fetch_ext.sh)")
        return 1
    shutil.rmtree(OUT, ignore_errors=True)
    runs = os.path.join(OUT, "runs")
    os.makedirs(runs)
    champ = os.path.join(OUT, "champion.py")
    shutil.copy(arena.CHAMPION, champ)          # frozen copy: the champion may change during the night
    logf = open(os.path.join(OUT, "log.txt"), "a")

    def log(s):
        print(s, flush=True)
        logf.write(s + "\n"); logf.flush()

    log("=== %s  ablation of %s vs %d field teams, %d games/team/seed, up to %d seeds" % (
        time.strftime("%F %T"), os.path.relpath(arena.CHAMPION, ROOT), len(field), a.games, a.seeds))
    res = {}
    for n in names:
        changes, what = VARIANTS[n]
        f = os.path.join(OUT, n + ".py")
        try:
            open(f, "w").write(render(src, changes))
        except ValueError as e:
            log("%s: skipped (%s)" % (n, e))
            continue
        smoke = arena.run_jobs([(f, arena.BASELINE, True, "defaultCapture", 0),
                                (f, arena.BASELINE, False, "RANDOM7", 1)], 2, a.python)
        bad = [r for r in smoke if r["cand_crash"] or r["cand_timeouts"] or r["cand_forfeit"] or r["no_score"]]
        res[n] = {"changes": changes, "what": what, "diffs": [], "seeds": [], "verdict": None}
        if bad:
            res[n]["verdict"] = "BROKEN"
            log("%s: BROKEN in the smoke test (crash/timeout/forfeit) - its off-path is dead code" % n)
    champ_runs = {}
    alive = [n for n in res if res[n]["verdict"] is None]
    for stage, seed in enumerate(SEEDS[:a.seeds]):
        if not alive:
            break
        if deadline and time.time() > deadline:
            log("time budget reached before stage %d" % (stage + 1))
            break
        if seed not in champ_runs:
            t = time.time()
            r = arena.run(champ, field, a.games, seed, a.workers, a.python)
            p = os.path.join(runs, "champion_s%d.json" % seed)
            save(p, r, champ)
            champ_runs[seed] = p
            log("stage %d seed %d: champion %.1f%% clean (%.0f min)" % (
                stage + 1, seed, arena.summarise(r)["total"]["clean_score_pct"] or 0, (time.time() - t) / 60))
        for n in list(alive):
            if deadline and time.time() > deadline:
                log("time budget reached during stage %d" % (stage + 1))
                break
            t = time.time()
            r = arena.run(os.path.join(OUT, n + ".py"), field, a.games, seed, a.workers, a.python)
            p = os.path.join(runs, "%s_s%d.json" % (n, seed))
            save(p, r, n)
            tot = arena.summarise(r)["total"]
            if tot["crashes"] or tot["forfeits"]:
                res[n]["unclean"] = res[n].get("unclean", 0) + tot["crashes"] + tot["forfeits"]
            res[n]["diffs"] += pick.paired_diffs(p, champ_runs[seed])
            res[n]["seeds"].append(seed)
            m, se, k = pick.mean_se(res[n]["diffs"])
            log("stage %d seed %d: %-18s %+5.1f +- %.1f (%d paired, %.0f min)%s" % (
                stage + 1, seed, n, 100 * m, 100 * se, k, (time.time() - t) / 60,
                "  ours unclean %d" % res[n]["unclean"] if res[n].get("unclean") else ""))
            if m + 1.96 * se < 0:
                alive.remove(n)            # clearly needed: no more games
    rows = []
    for n, v in res.items():
        if v["verdict"] is None and not v["diffs"]:
            v["verdict"] = "NOT RUN (time budget)"
        elif v["verdict"] != "BROKEN":
            m, se, k = pick.mean_se(v["diffs"])
            v.update(mean=m, se=se, n=k)
            v["verdict"] = ("NEEDED" if m + 1.96 * se < 0 else "OFF IS BETTER" if m - 1.96 * se > 0
                            else "NOT MEASURABLE")
            if v.get("unclean"):
                v["verdict"] += " (but %d crash/forfeit of ours)" % v["unclean"]
        rows.append(n)
    rows.sort(key=lambda n: res[n].get("mean", -9))
    rep = ["# Switch-off tests (%s)" % time.strftime("%F %T"), "",
           "Champion: `%s` (frozen copy in arena/ablate/champion.py). Paired vs the champion on identical "
           "games against the %d ext_gh_* training teams, %d games per team per seed; opponent "
           "crashes left out. Variant minus champion, in points (win 1, tie 0.5) per 100 games." % (
               os.path.relpath(arena.CHAMPION, ROOT), len(field), a.games), "",
           "| variant | change | tests | off minus champion | 95% interval | paired games | verdict |",
           "|---|---|---|---|---|---|---|"]
    for n in rows:
        v = res[n]
        ch = ", ".join("%s=%s" % kv for kv in v["changes"].items())
        if "mean" in v:
            rep.append("| %s | %s | %s | %+.1f ± %.1f | %+.1f..%+.1f | %d | %s |" % (
                n, ch, v["what"], 100 * v["mean"], 100 * v["se"], 100 * (v["mean"] - 1.96 * v["se"]),
                100 * (v["mean"] + 1.96 * v["se"]), v["n"], v["verdict"]))
        else:
            rep.append("| %s | %s | %s | - | - | - | %s |" % (n, ch, v["what"], v["verdict"]))
    rep += ["", "NEEDED = turning it off is measurably worse. NOT MEASURABLE = removal candidate: confirm "
            "with a non-regression check before deleting code. OFF IS BETTER = the feature hurts vs the "
            "field. Field only: the mirror and the held-out benchmark are not consulted here."]
    open(os.path.join(OUT, "REPORT.md"), "w").write("\n".join(rep) + "\n")
    json.dump({n: {k: v for k, v in res[n].items() if k != "diffs"} for n in res},
              open(os.path.join(OUT, "results.json"), "w"), indent=1)
    log("\n".join(rep))
    return 0


if __name__ == "__main__":
    sys.exit(main())
