#!/usr/bin/env python3
"""SPSA tuning of a team's numeric constants (as Stockfish's fishtest tunes its engine).

Builders change how the agent thinks; this sets the numbers. It plays games only - no Claude usage.

Tunable parameters = top-level lines of the form   NAME = <int or float>   # optional comment
(UPPER_CASE name, no indentation). Booleans, strings, game facts and on/off switches (SKIP, *_ON)
are ignored. Ints stay ints.

Each SPSA step k: draw a random +-1 direction delta for every parameter, build theta+ = theta + c_k*delta
and theta- = theta - c_k*delta, play them, result = how much better theta+ did (-2..2), then
    theta += step_k * result * delta
  * self-play steps: a colour-swapped game pair theta+ vs theta- (most information per game);
  * pool steps (--pool-frac of them): theta+ and theta- each play the same opponent in both colours
    (4 games), so the tuning is not only for the mirror match. Opponents are picked by PFSP
    (AlphaStar): weight p(1-p) of our score p against them, so 50% opponents are used most and
    ones we always beat are nearly skipped (they carry no gradient).
A variant that crashes, forfeits or gets a timeout warning loses the step.

Step sizes come from a NOISE BUDGET: game results are noisy, so every step is partly a random walk.
step_k is scaled so that the random walk over the whole run is about --noise (default 1) "c units"
(1 for ints, ~10% of the value for floats); a real effect adds up linearly with the number of steps
and stands out by ~sqrt(steps). (The first version used fixed fishtest-like rates and its random walk
was ~10x larger: parameters wandered to their bounds within 500 steps.)

  python3 arena/tune.py --list                          # what would be tuned, with ranges
  python3 arena/tune.py --hours 8 --pool auto --gate    # overnight: tune, then run the full gate
  python3 arena/tune.py --hours 8 --pool auto --gate --promote   # ... and promote if it passes
  python3 arena/tune.py --pairs 3000                    # fixed number of steps instead of a time budget
  python3 arena/tune.py --resume ...                    # continue a stopped run (same file only)

Output in arena/tune/ (git-ignored): state.json (resumable), log.txt, tuned.py, REPORT.md, gate/.
A running loop has priority: if arena/loop.sh starts, the tuner saves its state and exits
(--wait-loop instead makes a starting tuner wait until no loop is running).
Gate (--gate) = the loop's promotion rules: SPRT vs the champion [0.50, 0.55], then 12 regression
games each vs the baseline, the 2 most recent champions (>= 30%) and the league (>= 20%).
--promote (only when tuning my_team.py): if the gate passes, freeze the old champion as
arena/opponents/champ_rNNt, copy tuned.py to my_team.py, record it in the program DB and commit.
"""
import argparse
import glob
import hashlib
import json
import math
import os
import random
import re
import shutil
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import arena  # noqa: E402

ROOT = arena.ROOT
OUT = os.path.join(ROOT, "arena", "tune")
OPP_DIR = os.path.join(ROOT, "arena", "opponents")
SKIP = {"SIGHT_RANGE", "SONAR_HALF", "DEBUG",    # game facts, not strategy
        "DOUBLE_ATTACK", "LANE_SPLIT"}            # on/off switches (0/1): structure, not a number
SWITCH_SUFFIXES = ("_ON",)                        # ROUTE_ON, HELP_ON, ...: also switches
LINE = re.compile(r"^([A-Z][A-Z0-9_]*)(\s*=\s*)(-?\d+(?:\.\d*)?)(\s*(?:#.*)?)$")
ALPHA, GAMMA = 0.602, 0.101                       # standard SPSA gain exponents
RESULT_SD = 1.2                                   # sd of one step's result (-2..2), measured-ish
GATE_RESERVE = 1800                               # seconds kept free for the gate in --hours mode


def find_params(src, only=None, skip=()):
    out = []
    for i, line in enumerate(src.splitlines()):
        m = LINE.match(line)
        if not m or m.group(1) in SKIP or m.group(1) in skip or m.group(1).endswith(SWITCH_SUFFIXES):
            continue
        if only and m.group(1) not in only:
            continue
        txt = m.group(3)
        is_int = "." not in txt
        v = float(txt)
        c_end = 1.0 if is_int else max(0.1 * abs(v), 0.05)
        if v >= 0:
            lo = math.floor(v / 3.0) if is_int else v / 3.0
            hi = max(3 * v, v + 4 * c_end, 1.0)
        else:
            lo, hi = 3 * v, v / 3.0
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


def loop_running():
    try:
        return subprocess.run(["pgrep", "-f", "arena/loop.sh"], capture_output=True).returncode == 0
    except Exception:
        return False


def auto_pool():
    """Recent champions + league (same opponents the loop's regression stage uses)."""
    champs = sorted(glob.glob(os.path.join(OPP_DIR, "champ_*", "my_team.py")))[-3:]
    exps = sorted(glob.glob(os.path.join(OPP_DIR, "exploit_*", "my_team.py")))[-3:]
    exts = sorted(glob.glob(os.path.join(OPP_DIR, "ext_*", "my_team.py")))
    return champs + exps + exts


class Gains(object):
    """c_k and step_k for a run of n steps with a total random-walk budget of `noise` c-units."""

    def __init__(self, n, noise):
        self.n = max(1, n)
        self.big_a = 0.1 * self.n
        ss = sum(self.shape(k) ** 2 for k in range(self.n))
        self.scale = noise / (RESULT_SD * math.sqrt(ss))

    def shape(self, k):           # a_k / c_k up to a constant: big early, small late
        return (k + 1) ** GAMMA / (k + 1 + self.big_a) ** ALPHA

    def c(self, k, p):
        return p["c_end"] * (self.n / float(min(k, self.n - 1) + 1)) ** GAMMA

    def step(self, k, p):
        return p["c_end"] * self.scale * self.shape(min(k, self.n - 1))


def run_cmd(cmd, log):
    log("$ " + " ".join(os.path.relpath(c, ROOT) if c.startswith(ROOT) else c for c in cmd))
    p = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT)
    tail = [l for l in p.stdout.splitlines() if l.strip()]
    for l in tail[-8:]:
        log("  " + l)
    return p


def gate(tuned_src, champion, a, log):
    """The loop's promotion rules. Returns (qualified, gate_dir)."""
    gd = os.path.join(OUT, "gate")
    shutil.rmtree(gd, ignore_errors=True)
    os.makedirs(gd)
    cand = os.path.join(gd, "my_team.py")
    open(cand, "w").write(tuned_src)
    py = a.python
    ar = os.path.join(ROOT, "arena", "arena.py")
    run_cmd([py, ar, cand, "--opponents", champion, "--sprt", "--seed", "4242",
             "--json", os.path.join(gd, "sprt.json")], log)
    dec = subprocess.run([py, os.path.join(ROOT, "arena", "pick.py"), "--sprt", os.path.join(gd, "sprt.json")],
                         capture_output=True, text=True).stdout.strip()
    log("SPRT decision: %s" % dec)
    if dec != "H1":
        return False, gd
    champs = sorted(glob.glob(os.path.join(OPP_DIR, "champ_*", "my_team.py")))[-2:]
    exps = sorted(glob.glob(os.path.join(OPP_DIR, "exploit_*", "my_team.py")))[-3:]
    exts = sorted(glob.glob(os.path.join(OPP_DIR, "ext_*", "my_team.py")))
    field = [x for x in exts if arena.is_ext_gh(x)]
    league = [x for x in exts if not arena.is_ext_gh(x)]
    pk = os.path.join(ROOT, "arena", "pick.py")
    core = os.path.join(gd, "regress_core.json")
    run_cmd([py, ar, cand, "--opponents", arena.BASELINE] + champs + exps + league +
            ["--games", "12", "--seed", "777", "--json", core], log)
    extra = []
    if field:
        # field stage (as in loop.sh): candidate and champion on identical games vs the ext_gh_* teams
        cf = os.path.join(gd, "champion_field.json")
        for who, out in ((champion, cf), (cand, os.path.join(gd, "field.json"))):
            run_cmd([py, ar, who, "--opponents"] + field + ["--games", "24", "--seed", "4343", "--json", out], log)
        subprocess.run([py, pk, "--merge", os.path.join(gd, "regress.json"), core, os.path.join(gd, "field.json")])
        extra = ["--champ-field", cf]
    else:
        shutil.copy(core, os.path.join(gd, "regress.json"))
    sel = subprocess.run([py, pk, "--select", "30", "--league-min", "20", "--field-min", "75"] + extra + [gd],
                         capture_output=True, text=True)
    for l in sel.stderr.splitlines():
        log("  " + l)
    return bool(sel.stdout.strip()), gd


def promote(gd, src_path, log):
    """Freeze the old champion, install the tuned file, record + commit (like a loop promotion)."""
    py = sys.executable
    db = os.path.join(ROOT, "arena", "db.py")
    last = subprocess.run([py, db, "last-round"], capture_output=True, text=True).stdout.strip() or "0"
    tag = "r%02dt" % int(last)
    frozen = os.path.join(OPP_DIR, "champ_" + tag)
    n = 2
    while os.path.exists(frozen):
        frozen = os.path.join(OPP_DIR, "champ_%s%d" % (tag, n)); n += 1
    os.makedirs(frozen)
    shutil.copy(src_path, os.path.join(frozen, "my_team.py"))
    shutil.copy(os.path.join(gd, "my_team.py"), src_path)
    rid = "tune_" + time.strftime("%m%d_%H%M")
    parent = ""
    try:
        parent = open(os.path.join(ROOT, "arena", "db", "champion.txt")).read().strip()
    except IOError:
        pass
    subprocess.run([py, db, "add", rid, last, "passed", src_path, "--area", "TUNE",
                    "--direction", "SPSA-tuned constants (arena/tune.py)", "--model", "spsa",
                    "--parent", parent, "--sprt", os.path.join(gd, "sprt.json"),
                    "--regress", os.path.join(gd, "regress.json")])
    subprocess.run([py, db, "promote", rid])
    log("promoted: %s -> my_team.py (old champion frozen in %s, db id %s)"
        % (os.path.relpath(gd, ROOT), os.path.relpath(frozen, ROOT), rid))
    git = ["git", "-c", "core.autocrlf=input"]
    ok = (subprocess.run(["git", "config", "user.email"], capture_output=True, cwd=ROOT).returncode == 0 and
          subprocess.run(["git", "config", "user.name"], capture_output=True, cwd=ROOT).returncode == 0)
    if ok:
        subprocess.run(git + ["add", "--", src_path, frozen], cwd=ROOT)
        r = subprocess.run(git + ["commit", "-qm", "SPSA tuning: promote %s" % rid], cwd=ROOT)
        log("committed" if r.returncode == 0 else "WARNING: git commit failed")
    else:
        log("WARNING: no git identity - promotion not committed")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file", nargs="?", default=os.path.join(ROOT, "my_team.py"))
    ap.add_argument("--params", help="comma list: tune only these")
    ap.add_argument("--skip", default="", help="comma list: never tune these")
    ap.add_argument("--pairs", type=int, default=0, help="total SPSA steps (default: from --hours)")
    ap.add_argument("--hours", type=float, default=0, help="time budget incl. the gate (default 2 h "
                                                           "if --pairs is not given)")
    ap.add_argument("--noise", type=float, default=1.0,
                    help="random-walk budget of the whole run, in c units (1 = one int step)")
    ap.add_argument("--pool", nargs="*", help="opponent files for pool steps, or 'auto' "
                                              "(recent champions + exploiters + ext_*)")
    ap.add_argument("--pool-frac", type=float, default=0.5, help="share of steps played vs the pool")
    ap.add_argument("--workers", type=int,
                    default=int(os.environ.get("ARENA_WORKERS", 0)) or max(1, (os.cpu_count() or 2) - 1))
    ap.add_argument("--batch", type=int, default=0, help="steps per batch (default: workers // 2)")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--resume", action="store_true", help="continue from arena/tune/state.json")
    ap.add_argument("--list", action="store_true", help="print the tunable parameters and exit")
    ap.add_argument("--gate", action="store_true", help="run the loop's promotion gate at the end")
    ap.add_argument("--promote", action="store_true", help="promote + commit if the gate passes")
    ap.add_argument("--wait-loop", action="store_true", help="wait (instead of exit) while a loop runs")
    ap.add_argument("--python", default=sys.executable)
    a = ap.parse_args()

    # Wait BEFORE reading the file: a loop running now may promote a new champion, and tuning (and
    # then promoting over) the old one would undo the loop's work.
    waited = False
    while loop_running():
        if not a.wait_loop:
            print("arena/loop.sh is running - not tuning now (use --wait-loop to wait for it)")
            return 3
        if not waited:
            print("%s  waiting for arena/loop.sh to finish" % time.strftime("%F %T"), flush=True)
            waited = True
        time.sleep(60)
    if waited:
        print("%s  loop finished, starting" % time.strftime("%F %T"), flush=True)

    src_path = os.path.abspath(a.file)
    src = open(src_path).read()
    src_lines = src.splitlines()
    sha = hashlib.sha1(src.encode()).hexdigest()
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
    if a.promote and src_path != arena.CHAMPION:
        print("--promote only works when tuning my_team.py")
        return 2

    os.makedirs(OUT, exist_ok=True)
    logf = open(os.path.join(OUT, "log.txt"), "a")

    def log(s):
        print(s, flush=True)
        logf.write(s + "\n"); logf.flush()

    state_path = os.path.join(OUT, "state.json")
    names = [p["name"] for p in params]
    theta = [p["start"] for p in params]
    k, opp_stats = 0, {}
    if a.resume and os.path.exists(state_path):
        st = json.load(open(state_path))
        if st.get("names") == names and st.get("sha") == sha:
            theta, k, opp_stats = st["theta"], st["k"], st.get("opp_stats", {})
            log("resumed at step %d" % k)
        else:
            log("state.json is for another file version / parameter set - starting fresh")

    pool = []
    if a.pool:
        pool = auto_pool() if a.pool == ["auto"] else [os.path.abspath(x) for x in a.pool]
        pool = [x for x in pool if os.path.exists(x)]
    batch = a.batch or max(1, a.workers // 2)
    t0 = time.time()
    hours = a.hours or (0 if a.pairs else 2.0)
    deadline = t0 + hours * 3600 - (GATE_RESERVE if a.gate else 0) if hours else None
    n_total = a.pairs or max(k + 1, int(hours * 3600 / 3.0))   # provisional (~20 steps/min)
    gains = Gains(n_total, a.noise)
    calibrated = bool(a.pairs)
    k0 = k
    cal_at = [120] + [f * (deadline - t0) for f in (0.10, 0.25, 0.50, 0.75)] if deadline else []
    cal_at = sorted(x for x in cal_at if x >= 120)
    rng = random.Random(a.seed + k)
    work = os.path.join(OUT, "work")
    os.makedirs(work, exist_ok=True)
    log("=== %s  tuning %d parameters of %s: %s" % (time.strftime("%F %T"), len(params),
                                                    os.path.relpath(src_path, ROOT), ", ".join(names)))
    log("budget: %s, batch %d, workers %d, noise %.2f, pool %s"
        % ("%d steps" % n_total if a.pairs else "%.1f h" % hours, batch, a.workers, a.noise,
           "%d opponents, %.0f%% of steps" % (len(pool), 100 * a.pool_frac) if pool else "none (self-play)"))

    def pick_opp():
        # PFSP on a margin-aware score: a game won by 1 point counts ~0.55, by 20+ points ~1.0, so
        # fortresses we beat narrowly every time still get played (pure win-rate would skip them).
        def w(o):
            s = opp_stats.get(o, [0.0, 0])
            soft = s[2] if len(s) > 2 else s[0]
            p = (soft + 1.0) / (s[1] + 2.0)
            return p * (1 - p) + 0.02
        ws = [w(o) for o in pool]
        x = rng.random() * sum(ws)
        for o, wo in zip(pool, ws):
            x -= wo
            if x <= 0:
                return o
        return pool[-1]

    played = unclean = 0
    stop_reason = "done"
    try:
        while k < n_total:
            if deadline and time.time() > deadline:
                stop_reason = "time budget reached"
                break
            if loop_running():
                stop_reason = "arena/loop.sh started - yielding (resume later with --resume)"
                break
            steps, jobs, gid = [], [], 0
            for s in range(min(batch, n_total - k)):
                step = k + s
                delta = [rng.choice((-1, 1)) for _ in params]
                plus = [clamp(p, t + gains.c(step, p) * d) for p, t, d in zip(params, theta, delta)]
                minus = [clamp(p, t - gains.c(step, p) * d) for p, t, d in zip(params, theta, delta)]
                fp = os.path.join(work, "s%d_plus.py" % s)
                fm = os.path.join(work, "s%d_minus.py" % s)
                open(fp, "w").write(render(src_lines, params, plus))
                open(fm, "w").write(render(src_lines, params, minus))
                layout = arena.pair_layout(step, a.seed, rng)
                first = len(jobs)
                opp = pick_opp() if pool and rng.random() < a.pool_frac else None
                if opp:
                    for f in (fp, fm):
                        jobs.append((f, opp, True, layout, gid)); jobs.append((f, opp, False, layout, gid + 1))
                        gid += 2
                else:
                    jobs.append((fp, fm, True, layout, gid)); jobs.append((fp, fm, False, layout, gid + 1))
                    gid += 2
                steps.append((step, delta, first, opp))
            res = arena.run_jobs(jobs, a.workers, a.python)
            for step, delta, first, opp in steps:
                if opp:
                    gp, gm = res[first:first + 2], res[first + 2:first + 4]
                    bad_p = not all(side_ok(r, True) for r in gp)
                    bad_m = not all(side_ok(r, True) for r in gm)
                    result = (sum(map(game_points, gp)) - sum(map(game_points, gm))) / 2.0
                    st = opp_stats.setdefault(opp, [0.0, 0, 0.0])
                    if len(st) < 3:
                        st.append(st[0])
                    for r in gp + gm:
                        st[0] += 1.0 if r["cand_score"] > 0 else (0.5 if r["cand_score"] == 0 else 0.0)
                        st[1] += 1
                        st[2] += 0.5 + 0.5 * math.tanh(r["cand_score"] / 10.0)
                    g = gp + gm
                else:
                    g = res[first:first + 2]
                    bad_p = not all(side_ok(r, True) for r in g)
                    bad_m = not all(side_ok(r, False) for r in g)
                    result = float(sum(map(game_points, g)))
                if any(r.get("no_score") for r in g) and not (bad_p or bad_m):
                    unclean += 1
                    continue                     # harness problem, not the parameters
                if bad_p != bad_m:
                    unclean += 1
                    result = -2.0 if bad_p else 2.0
                elif bad_p and bad_m:
                    unclean += 1
                    continue
                for j, p in enumerate(params):
                    theta[j] = clamp(p, theta[j] + gains.step(step, p) * result * delta[j])
                played += 1
            k += len(steps)
            # Calibrate the step count to the budget after 2 min, then re-measure at 10/25/50/75% of
            # it: the first minutes run slower (5 h run on 2026-11-17 finished ~1 h early otherwise).
            el = time.time() - t0
            if not calibrated and deadline and cal_at and el > cal_at[0]:
                while cal_at and el > cal_at[0]:
                    cal_at.pop(0)
                rate = (k - k0) / el                              # steps per second, measured
                new_total = max(k + 1, int(k + rate * (deadline - time.time())))
                if abs(new_total - n_total) > 0.02 * n_total:
                    n_total = new_total
                    gains = Gains(n_total, a.noise)
                log("calibrated: %.1f steps/min -> %d steps in the budget" % (rate * 60, n_total))
            json.dump({"file": src_path, "sha": sha, "names": names, "theta": theta, "k": k,
                       "n_total": n_total, "opp_stats": opp_stats}, open(state_path, "w"))
            open(os.path.join(OUT, "tuned.py"), "w").write(render(src_lines, params, theta))
            if k % (batch * 10) < batch or k >= n_total:
                log("step %5d/%d  %s  (%.0f min, unclean %d)" % (
                    k, n_total, " ".join("%s=%.3g" % (n, t) for n, t in zip(names, theta)),
                    (time.time() - t0) / 60, unclean))
    except KeyboardInterrupt:
        stop_reason = "interrupted (state saved; continue with --resume)"
    finally:
        shutil.rmtree(work, ignore_errors=True)

    log("stopped at step %d/%d: %s" % (k, n_total, stop_reason))
    if pool:
        log("pool scores of the tuned team (PFSP weights favour ~50%%): %s" % ", ".join(
            "%s %.0f%% of %d" % (os.path.relpath(os.path.dirname(o), OPP_DIR), 100 * s[0] / max(1, s[1]), s[1])
            for o, s in sorted(opp_stats.items())))
    changes = []
    for p, t in zip(params, theta):
        new = int(round(t)) if p["int"] else float("%.4g" % t)
        changes.append((p["name"], p["start"], new))
        log("  %-18s %8g -> %s" % (p["name"], p["start"], new))
    tuned_src = render(src_lines, params, theta)
    report = ["# SPSA tuning report (%s)" % time.strftime("%F %T"), "",
              "File: `%s`, %d steps, stop: %s" % (os.path.relpath(src_path, ROOT), k, stop_reason), "",
              "| parameter | start | tuned |", "|---|---|---|"]
    report += ["| %s | %g | %s |" % c for c in changes]
    verdict = "gate not run"
    if a.gate and stop_reason in ("done", "time budget reached"):
        if tuned_src == src.rstrip("\n") + "\n" or all(c[1] == c[2] for c in changes):
            verdict = "no parameter changed - nothing to test"
        else:
            ok, gd = gate(tuned_src, src_path, a, log)
            verdict = "PASSED the promotion gate" if ok else "did not pass the gate (champion kept)"
            report += ["", "Gate reports: `arena/tune/gate/` (sprt.json, regress.json)"]
            if ok and a.promote:
                promote(gd, src_path, log)
                verdict += " - PROMOTED to my_team.py"
            elif ok:
                verdict += " - promote by hand: cp arena/tune/gate/my_team.py my_team.py"
    report += ["", "**Verdict: %s**" % verdict]
    open(os.path.join(OUT, "REPORT.md"), "w").write("\n".join(report) + "\n")
    log("verdict: %s  (arena/tune/REPORT.md)" % verdict)
    return 0


if __name__ == "__main__":
    sys.exit(main())
