#!/usr/bin/env python3
"""SPSA tuning of a team's numeric constants (as Stockfish's fishtest tunes its engine).

Builders change how the agent thinks; this sets the numbers. It plays games only - no Claude usage.

Tunable parameters = top-level lines of the form   NAME = <int or float>   # optional comment
(UPPER_CASE name, no indentation). Booleans and strings are ignored, and so are game facts listed
in SKIP. Ints stay ints.

Each SPSA step k: draw a random +-1 direction delta for every parameter, build theta+ = theta + c_k*delta
and theta- = theta - c_k*delta, play a colour-swapped game pair theta+ vs theta- on one layout
(self-play, as in fishtest), result = (wins - losses) of theta+ in that pair (-2..2), then
    theta += a_k / c_k * result * delta          (a_k, c_k shrink over time, standard SPSA gains)
A variant that crashes, forfeits or gets a timeout warning loses the pair, which pushes the
parameters away from slow settings. Many pairs run in parallel (one batch shares one theta).

  python3 arena/tune.py                          # tune my_team.py, 2000 pairs (~1-2 h on 12 cores)
  python3 arena/tune.py --pairs 6000 --resume    # continue a stopped run (overnight)
  python3 arena/tune.py --params HIDDEN_W,CARRY_BUDGET --vs arena/opponents/exploit_r06/my_team.py
  python3 arena/tune.py --list                   # show what would be tuned

Output in arena/tune/ (git-ignored): state.json (resumable), log.txt, tuned.py (the file with the
current tuned values). Stop any time with Ctrl-C: state.json is saved after every batch.
Afterwards verify before promoting - tuned values are only better if the SPRT says so:
  python3 arena/arena.py arena/tune/tuned.py --opponents my_team.py --sprt
  python3 arena/arena.py arena/tune/tuned.py --games 12          # no collapse vs everyone else
  (or --verify to run the SPRT automatically at the end). Promote by hand: cp arena/tune/tuned.py my_team.py
"""
import argparse
import json
import math
import os
import random
import re
import shutil
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import arena  # noqa: E402

ROOT = arena.ROOT
OUT = os.path.join(ROOT, "arena", "tune")
SKIP = {"SIGHT_RANGE", "SONAR_HALF", "DEBUG"}   # game facts / switches, not strategy
LINE = re.compile(r"^([A-Z][A-Z0-9_]*)(\s*=\s*)(-?\d+(?:\.\d*)?)(\s*(?:#.*)?)$")
ALPHA, GAMMA = 0.602, 0.101                       # standard SPSA gain exponents


def find_params(src, only=None, skip=()):
    out = []
    for i, line in enumerate(src.splitlines()):
        m = LINE.match(line)
        if not m or m.group(1) in SKIP or m.group(1) in skip:
            continue
        if only and m.group(1) not in only:
            continue
        txt = m.group(3)
        is_int = "." not in txt
        v = float(txt)
        c_end = 1.0 if is_int else max(0.1 * abs(v), 0.05)
        lo = 0.0 if v >= 0 else 3 * v
        hi = max(3 * abs(v), v + 4 * c_end, 1.0)
        out.append({"name": m.group(1), "line": i, "int": is_int, "start": v, "c_end": c_end,
                    "lo": lo, "hi": hi})
    return out


def render(src_lines, params, theta):
    lines = list(src_lines)
    for p, v in zip(params, theta):
        m = LINE.match(lines[p["line"]])
        val = str(int(round(v))) if p["int"] else ("%.4g" % v if abs(v) >= 1e-4 else "0.0")
        if not p["int"] and "." not in val and "e" not in val:
            val += ".0"
        lines[p["line"]] = m.group(1) + m.group(2) + val + m.group(4)
    return "\n".join(lines) + "\n"


def clamp(p, v):
    return min(max(v, p["lo"]), p["hi"])


def side_ok(r, cand_side):
    """Was the given side (True = candidate of this job) clean in this game?"""
    if cand_side:
        return not (r["cand_crash"] or r["cand_forfeit"] or r["cand_timeouts"])
    idx = {1, 3} if r["cand_red"] else {0, 2}
    opp_crash = r["blue_crash"] if r["cand_red"] else r["red_crash"]
    opp_forfeit = any(a in idx for a in r.get("forfeits", []))
    opp_slow = any(a in idx for a in r.get("timeout_warnings", []))
    return not (opp_crash or opp_forfeit or opp_slow)


def game_points(r):   # candidate's view: +1 win, 0 tie, -1 loss
    return (r["cand_score"] > 0) - (r["cand_score"] < 0)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file", nargs="?", default=os.path.join(ROOT, "my_team.py"))
    ap.add_argument("--params", help="comma list: tune only these")
    ap.add_argument("--skip", default="", help="comma list: never tune these")
    ap.add_argument("--pairs", type=int, default=2000, help="total SPSA steps (game pairs)")
    ap.add_argument("--r-end", type=float, default=0.05,
                    help="final learning rate a_end/c_end^2 (fishtest uses ~0.002 with 100k+ games; "
                         "we have thousands, so larger)")
    ap.add_argument("--vs", help="tune against this fixed opponent instead of self-play "
                                 "(4 games per step: theta+ and theta- each play it in both colours)")
    ap.add_argument("--workers", type=int,
                    default=int(os.environ.get("ARENA_WORKERS", 0)) or max(1, (os.cpu_count() or 2) - 1))
    ap.add_argument("--batch", type=int, default=0, help="steps per batch (default: workers // 2)")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--resume", action="store_true", help="continue from arena/tune/state.json")
    ap.add_argument("--list", action="store_true", help="print the tunable parameters and exit")
    ap.add_argument("--verify", action="store_true", help="run the SPRT of tuned.py vs my_team.py at the end")
    ap.add_argument("--python", default=sys.executable)
    a = ap.parse_args()

    src_path = os.path.abspath(a.file)
    src = open(src_path).read()
    src_lines = src.splitlines()
    only = set(a.params.split(",")) if a.params else None
    params = find_params(src, only, set(x for x in a.skip.split(",") if x))
    if not params:
        print("no tunable top-level NAME = number lines found")
        return 1
    if a.list:
        for p in params:
            print("%-18s %-6s start %-8g range [%g, %g]  c_end %g" % (
                p["name"], "int" if p["int"] else "float", p["start"], p["lo"], p["hi"], p["c_end"]))
        return 0

    os.makedirs(OUT, exist_ok=True)
    state_path = os.path.join(OUT, "state.json")
    names = [p["name"] for p in params]
    theta = [p["start"] for p in params]
    k = 0
    if a.resume and os.path.exists(state_path):
        st = json.load(open(state_path))
        if st.get("names") == names and st.get("file") == src_path:
            theta, k = st["theta"], st["k"]
            print("resumed at step %d" % k)
        else:
            print("state.json is for another file / parameter set - starting fresh")
    n_total = max(a.pairs, k + 1)
    big_a = 0.1 * n_total
    batch = a.batch or max(1, a.workers // (4 if a.vs else 2))
    rng = random.Random(a.seed + k)
    work = os.path.join(OUT, "work")
    os.makedirs(work, exist_ok=True)
    log = open(os.path.join(OUT, "log.txt"), "a")
    opp = os.path.abspath(a.vs) if a.vs else None
    print("tuning %d parameters of %s: %s" % (len(params), os.path.relpath(src_path, ROOT), ", ".join(names)))
    print("%d steps, batch %d, %s, workers %d" % (n_total, batch, "vs " + a.vs if a.vs else "self-play", a.workers))

    def gains(step, p):
        c = p["c_end"] * n_total ** GAMMA / (step + 1) ** GAMMA
        a_end = a.r_end * p["c_end"] ** 2
        ak = a_end * (n_total + big_a) ** ALPHA / (step + 1 + big_a) ** ALPHA
        return ak, c

    t0 = time.time()
    played = unclean = 0
    try:
        while k < n_total:
            steps = []
            jobs = []
            gid = 0
            for s in range(min(batch, n_total - k)):
                step = k + s
                delta = [rng.choice((-1, 1)) for _ in params]
                cs = [gains(step, p)[1] for p in params]
                plus = [clamp(p, t + c * d) for p, t, c, d in zip(params, theta, cs, delta)]
                minus = [clamp(p, t - c * d) for p, t, c, d in zip(params, theta, cs, delta)]
                fp = os.path.join(work, "s%d_plus.py" % s)
                fm = os.path.join(work, "s%d_minus.py" % s)
                open(fp, "w").write(render(src_lines, params, plus))
                open(fm, "w").write(render(src_lines, params, minus))
                layout = arena.pair_layout(step, a.seed, rng)
                first = len(jobs)
                if opp:
                    for f in (fp, fm):
                        jobs.append((f, opp, True, layout, gid)); jobs.append((f, opp, False, layout, gid + 1))
                        gid += 2
                else:
                    jobs.append((fp, fm, True, layout, gid)); jobs.append((fp, fm, False, layout, gid + 1))
                    gid += 2
                steps.append((step, delta, first))
            res = arena.run_jobs(jobs, a.workers, a.python)
            for step, delta, first in steps:
                if opp:
                    gp, gm = res[first:first + 2], res[first + 2:first + 4]
                    bad_p = not all(side_ok(r, True) for r in gp)
                    bad_m = not all(side_ok(r, True) for r in gm)
                    result = (sum(map(game_points, gp)) - sum(map(game_points, gm))) / 2.0
                else:
                    g = res[first:first + 2]
                    bad_p = not all(side_ok(r, True) for r in g)
                    bad_m = not all(side_ok(r, False) for r in g)
                    result = float(sum(map(game_points, g)))
                if any(r.get("no_score") for r in res[first:first + (4 if opp else 2)]) and not (bad_p or bad_m):
                    unclean += 1
                    continue                     # harness problem, not the parameters
                if bad_p != bad_m:
                    unclean += 1
                    result = -2.0 if bad_p else 2.0
                elif bad_p and bad_m:
                    unclean += 1
                    continue
                for j, p in enumerate(params):
                    ak, c = gains(step, p)
                    theta[j] = clamp(p, theta[j] + ak / c * result * delta[j])
                played += 1
            k += len(steps)
            json.dump({"file": src_path, "names": names, "theta": theta, "k": k}, open(state_path, "w"))
            open(os.path.join(OUT, "tuned.py"), "w").write(render(src_lines, params, theta))
            line = "step %5d/%d  %s  (%.0fs, unclean %d)" % (
                k, n_total, " ".join("%s=%.3g" % (n, t) for n, t in zip(names, theta)), time.time() - t0, unclean)
            print(line, flush=True)
            log.write(line + "\n"); log.flush()
    except KeyboardInterrupt:
        print("\nstopped - state saved; continue with --resume")
    finally:
        shutil.rmtree(work, ignore_errors=True)

    print("\nstart -> tuned:")
    for p, t in zip(params, theta):
        print("  %-18s %8g -> %s" % (p["name"], p["start"], int(round(t)) if p["int"] else "%.4g" % t))
    tuned = os.path.join(OUT, "tuned.py")
    print("written: %s\nverify:  python3 arena/arena.py %s --opponents my_team.py --sprt"
          % (os.path.relpath(tuned, ROOT), os.path.relpath(tuned, ROOT)))
    if a.verify:
        os.execv(a.python, [a.python, os.path.join(ROOT, "arena", "arena.py"), tuned,
                            "--opponents", os.path.join(ROOT, "my_team.py"), "--sprt",
                            "--json", os.path.join(OUT, "verify.json")])
    return 0


if __name__ == "__main__":
    sys.exit(main())
