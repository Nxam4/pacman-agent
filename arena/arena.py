#!/usr/bin/env python3
"""
Arena: plays a candidate team against a gauntlet of opponents and reports win rate.

Each game runs in its own subprocess (so two teams that are both called my_team.py
don't collide), both colours are played, and crashes / timeout warnings are counted.

Usage (from the repo root):
  python3 arena/arena.py my_team.py                      # vs baseline + all frozen champions
  python3 arena/arena.py arena/work/cand_1/my_team.py --quick
  python3 arena/arena.py CAND --opponents my_team.py --games 40 --json out.json
  python3 arena/arena.py CAND --opponents my_team.py --sprt        # play until statistically decided
"""
import argparse
import concurrent.futures as cf
import glob
import json
import math
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONTEST_DIR = os.path.join(ROOT, "pacman-contest", "src", "contest")
BASELINE = os.path.join(CONTEST_DIR, "baseline_team.py")
OPPONENT_DIR = os.path.join(ROOT, "arena", "opponents")
FIXED_LAYOUTS = ["defaultCapture", "alleyCapture", "jumboCapture", "officeCapture",
                 "strategicCapture", "crowdedCapture", "distantCapture", "fastCapture"]
HARNESS_TIMEOUT = 1500


RUN_GAME = os.path.join(ROOT, "arena", "run_game.py")   # capture.py + per-game play statistics
CHAMPION = os.path.join(ROOT, "my_team.py")


def play(red, blue, layout, game_id, workdir, python):
    """Play one game. Returns dict with red-perspective score, problems and play statistics."""
    cmd = [python, RUN_GAME, "-r", red, "-b", blue, "-l", layout, "-q", "-c",
           "--delay-step", "0", "-u", "arena", "-m", str(game_id)]
    t0 = time.time()
    try:
        # 1200 moves at up to ~1 s each plus 2 x 15 s startup: a slow-but-legal game can exceed 20 min.
        p = subprocess.run(cmd, cwd=workdir, capture_output=True, text=True, timeout=HARNESS_TIMEOUT)
        out = p.stdout + p.stderr
    except subprocess.TimeoutExpired:
        return {"layout": layout, "score": 0, "error": "harness timeout", "secs": HARNESS_TIMEOUT,
                "red_crash": False, "blue_crash": False, "timeout_warnings": [], "forfeits": [],
                "load_error": False}
    score = None
    score_file = os.path.join(workdir, "www", "contest_arena", "scores", f"match_{game_id}.json")
    try:
        with open(score_file) as f:
            g = json.load(f)["games"][0]   # (red, blue, layout, |score|, winner, time, id)
        score = g[3] if g[4] == "Red" else (-g[3] if g[4] == "Blue" else 0)
    except Exception:
        pass
    stats = None
    try:
        with open(score_file[:-5] + "_stats.json") as f:
            stats = json.load(f)
    except Exception:
        pass
    problems = {
        "red_crash": "Red agent crashed" in out,
        "blue_crash": "Blue agent crashed" in out,
        "timeout_warnings": [int(a) for a in re.findall(r"Agent (\d) took too long", out)],
        # time forfeits: >3 s on one move, too many warnings, >15 s startup, or total time
        "forfeits": [int(a) for a in re.findall(
            r"Agent (\d) (?:timed out on a single move|exceeded the maximum number of warnings"
            r"|ran out of time)", out)],
        "load_error": "could not be loaded" in out,
    }
    res = {"layout": layout, "score": score if score is not None else 0,
           "secs": round(time.time() - t0, 1), "stats": stats, **problems}
    if score is None:
        res["error"] = out[-1500:]
    return res


def opp_label(opp):
    if opp == BASELINE:
        return "baseline"
    if opp == CHAMPION:
        return "champion"
    return os.path.relpath(os.path.dirname(opp), ROOT)


def pair_layout(p, seed, rng):
    """Layout of game pair p: alternate a fixed layout (cycling through all of them) and a random one."""
    return (FIXED_LAYOUTS[(p // 2 + seed) % len(FIXED_LAYOUTS)] if p % 2 == 0
            else f"RANDOM{rng.randint(1, 10**6)}")


def play_stats(r, cand_is_red):
    """Candidate-perspective play statistics of one game (None if the wrapper wrote none)."""
    s = r.get("stats")
    if not s:
        return None
    me, op = ((0, 2), (1, 3)) if cand_is_red else ((1, 3), (0, 2))
    tot = lambda k, idx: sum(s.get(k, [0, 0, 0, 0])[i] for i in idx)
    return {"banked": tot("returned", me), "conceded": tot("returned", op),
            "deaths": tot("deaths", me), "dropped": tot("dropped", me),
            "kills": tot("deaths", op), "opp_dropped": tot("dropped", op)}


def run_jobs(jobs, workers, python):
    """jobs: (candidate, opponent, cand_is_red, layout, gid). Plays them in parallel, one subprocess
    and one scratch dir per game. Returns results in job order, from the candidate's perspective."""
    # Each game needs its own working dir because capture.py writes www/... relative to cwd.
    tmp_root = tempfile.mkdtemp(prefix="arena_")

    def job(j):
        cand, opp, cand_is_red, layout, gid = j
        red, blue = (cand, opp) if cand_is_red else (opp, cand)
        wd = os.path.join(tmp_root, f"g{gid}")
        os.makedirs(wd)
        # capture.py must run from the contest dir for its imports; copy-free: symlink files
        for name in os.listdir(CONTEST_DIR):
            os.symlink(os.path.join(CONTEST_DIR, name), os.path.join(wd, name))
        r = play(red, blue, layout, gid, wd, python)
        r["opponent"] = opp_label(opp)
        r["cand_red"] = cand_is_red
        r["cand_score"] = r["score"] if cand_is_red else -r["score"]
        cand_idx = {0, 2} if cand_is_red else {1, 3}
        r["cand_crash"] = r["red_crash"] if cand_is_red else r["blue_crash"]
        r["cand_timeouts"] = sum(1 for a in r["timeout_warnings"] if a in cand_idx)
        r["cand_forfeit"] = any(a in cand_idx for a in r.get("forfeits", []))
        r["no_score"] = "error" in r   # harness timeout / unparseable game
        r["play"] = play_stats(r, cand_is_red)
        r.pop("stats", None)
        shutil.rmtree(wd, ignore_errors=True)
        return r

    try:
        with cf.ThreadPoolExecutor(max_workers=workers) as ex:
            return list(ex.map(job, jobs))
    finally:
        shutil.rmtree(tmp_root, ignore_errors=True)


def is_ext_gh(opp):
    """Third-party training opponent (arena/opponents/ext_gh_*)."""
    return os.path.basename(os.path.dirname(opp)).startswith("ext_gh_")


def run(candidate, opponents, games_per_opp, seed, workers, python, ext_games=None):
    rng = random.Random(seed)
    jobs = []
    gid = 0
    for opp in opponents:
        # Games come in colour-swapped pairs on the same layout (cancels map/colour asymmetry).
        # Pairs alternate fixed layout / random layout, cycling through ALL fixed layouts.
        layout = None
        n = ext_games if ext_games and is_ext_gh(opp) else games_per_opp
        for i in range(n):
            if i % 2 == 0:
                layout = pair_layout(i // 2, seed, rng)
            jobs.append((candidate, opp, i % 2 == 0, layout, gid))
            gid += 1
    return run_jobs(jobs, workers, python)


def summarise(results):
    by_opp = {}
    for r in results:
        s = by_opp.setdefault(r["opponent"], {"games": 0, "wins": 0, "ties": 0, "losses": 0,
                                              "score_sum": 0, "crashes": 0, "timeouts": 0,
                                              "forfeits": 0, "no_score": 0, "max_secs": 0})
        s["games"] += 1
        s["score_sum"] += r["cand_score"]
        s["wins"] += r["cand_score"] > 0
        s["ties"] += r["cand_score"] == 0
        s["losses"] += r["cand_score"] < 0
        s["crashes"] += r["cand_crash"]
        s["timeouts"] += r["cand_timeouts"]
        s["forfeits"] += r["cand_forfeit"]
        s["no_score"] += r["no_score"]
        s["max_secs"] = max(s["max_secs"], r["secs"])
    total = {k: sum(v[k] for v in by_opp.values()) for k in
             ["games", "wins", "ties", "losses", "score_sum", "crashes", "timeouts", "forfeits",
              "no_score"]}
    total["max_secs"] = max([v["max_secs"] for v in by_opp.values()] or [0])
    for s in list(by_opp.values()) + [total]:
        # contest-style points: win 3, tie 1
        s["points_pct"] = round(100 * (3 * s["wins"] + s["ties"]) / (3 * s["games"]), 1) if s["games"] else 0
        # symmetric score (win 1, tie 0.5): 50 = equal strength, independent of the tie rate
        s["score_pct"] = round(100 * (s["wins"] + 0.5 * s["ties"]) / s["games"], 1) if s["games"] else 0
        s["avg_score"] = round(s["score_sum"] / s["games"], 2) if s["games"] else 0
    for name, s in list(by_opp.items()) + [("TOTAL", total)]:
        s["play"] = play_summary([r for r in results if name == "TOTAL" or r["opponent"] == name])
    return {"by_opponent": by_opp, "total": total}


PLAY_KEYS = ("banked", "conceded", "deaths", "dropped", "kills")


def play_summary(results):
    """Per-game averages of how the candidate played (food banked / conceded, deaths, food dropped on
    death, kills) plus the share of games in which it died carrying >= 5 dots."""
    ps = [r["play"] for r in results if r.get("play")]
    if not ps:
        return None
    out = {k: round(sum(p[k] for p in ps) / len(ps), 2) for k in PLAY_KEYS}
    out["big_drop_pct"] = round(100 * sum(1 for p in ps if p["dropped"] >= 5) / len(ps), 1)
    out["games"] = len(ps)
    return out


# ------------------------------------------------------------------ SPRT
def game_score(r):
    return 1.0 if r["cand_score"] > 0 else (0.5 if r["cand_score"] == 0 else 0.0)


def sprt_llr(results, s0, s1, var_floor=0.02):
    """Generalised SPRT log-likelihood ratio (normal approximation, as in Fishtest), computed on
    colour-swapped game PAIRS: the pair is the unit, so map/colour luck largely cancels (Fishtest's
    pentanomial idea). H0: expected score per game = s0, H1: = s1."""
    pairs = [(game_score(results[i]) + game_score(results[i + 1])) / 2.0
             for i in range(0, len(results) - 1, 2)]
    n = len(pairs)
    if n == 0:
        return 0.0, 0.5, n
    mean = sum(pairs) / n
    var = sum((x - mean) ** 2 for x in pairs) / n
    var = max(var, var_floor)   # all-tie streaks would otherwise give an infinite LLR
    return n * (s1 - s0) * (2 * mean - s0 - s1) / (2 * var), mean, n


def run_sprt(cand, opp, a):
    """Play colour-swapped pairs in parallel batches until the SPRT decides or max games is hit.
    Clear winners/losers stop early; close calls get more games. Any crash, forfeit, timeout warning
    or unscored game stops the test immediately (decision 'unclean')."""
    lower = math.log(a.beta / (1 - a.alpha))
    upper = math.log((1 - a.beta) / a.alpha)
    batch = max(2, a.workers - a.workers % 2)
    results, k, decision, llr, mean, pairs = [], 0, "inconclusive", 0.0, 0.5, 0
    while len(results) < a.max_games:
        n = min(batch, a.max_games - len(results))
        n -= n % 2
        if n <= 0:
            break
        res = run(cand, [opp], n, a.seed + 7919 * k, a.workers, a.python)
        for r in res:   # gids restart per batch; keep them unique within the report
            r["batch"] = k
        k += 1
        results += res
        if any(r["cand_crash"] or r["cand_forfeit"] or r["cand_timeouts"] or r["no_score"] for r in res):
            decision = "unclean"
            break
        llr, mean, pairs = sprt_llr(results, a.s0, a.s1)
        print(f"  sprt: {len(results):>3} games  score {100 * mean:5.1f}%  LLR {llr:+.2f}  "
              f"bounds [{lower:.2f}, {upper:.2f}]", flush=True)
        if pairs >= a.min_pairs and llr >= upper:
            decision = "H1"
            break
        if pairs >= a.min_pairs and llr <= lower:
            decision = "H0"
            break
    return results, {"decision": decision, "llr": round(llr, 3), "score": round(mean, 4),
                     "games": len(results), "s0": a.s0, "s1": a.s1, "alpha": a.alpha, "beta": a.beta,
                     "lower": round(lower, 3), "upper": round(upper, 3)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("candidate")
    ap.add_argument("--opponents", nargs="*", help="team files (default: baseline + arena/opponents/*.py)")
    ap.add_argument("--games", type=int, default=16, help="games per opponent")
    ap.add_argument("--quick", action="store_true", help="8 games per opponent")
    ap.add_argument("--ext-games", type=int, default=0,
                    help="games per third-party training opponent (arena/opponents/ext_gh_*); default --games")
    ap.add_argument("--seed", type=int, default=0)
    # ARENA_WORKERS lets the loop share the CPU between parallel builders; oversubscribing the
    # CPU inflates move times and produces fake timeout warnings.
    ap.add_argument("--workers", type=int,
                    default=int(os.environ.get("ARENA_WORKERS", 0)) or max(1, (os.cpu_count() or 2) - 1))
    ap.add_argument("--python", default=sys.executable)
    ap.add_argument("--json", help="write full report here")
    sp = ap.add_argument_group("SPRT (sequential test vs ONE opponent, e.g. --opponents my_team.py --sprt)")
    sp.add_argument("--sprt", action="store_true", help="play until statistically decided")
    sp.add_argument("--s0", type=float, default=0.50, help="H0 expected score per game (win 1, tie .5)")
    sp.add_argument("--s1", type=float, default=0.55, help="H1 expected score per game")
    sp.add_argument("--alpha", type=float, default=0.05, help="P(accept H1 | H0 true)")
    sp.add_argument("--beta", type=float, default=0.10, help="P(accept H0 | H1 true)")
    sp.add_argument("--max-games", type=int, default=300)
    # min 8 pairs + variance floor 0.02 keep false promotions of an equal candidate at ~5% (simulated;
    # with 4 pairs / 0.01 the small-sample variance estimate let it reach ~8%)
    sp.add_argument("--min-pairs", type=int, default=8)
    a = ap.parse_args()

    cand = os.path.abspath(a.candidate)
    opps = a.opponents or [BASELINE] + sorted(glob.glob(os.path.join(OPPONENT_DIR, "*", "my_team.py")))
    opps = [os.path.abspath(o) for o in opps]
    print(f"Candidate: {os.path.relpath(cand, ROOT)}", flush=True)
    sprt = None
    if a.sprt:
        if len(opps) != 1:
            ap.error("--sprt needs exactly one opponent")
        results, sprt = run_sprt(cand, opps[0], a)
    else:
        n = 8 if a.quick else a.games
        results = run(cand, opps, n, a.seed, a.workers, a.python, a.ext_games)
    summary = summarise(results)

    print(f"{'opponent':<28}{'W':>4}{'T':>4}{'L':>4}{'pts%':>7}{'score%':>7}{'avg':>7}{'crash':>7}"
          f"{'slow':>6}{'forfeit':>8}{'maxs':>6} | {'bank':>5}{'conc':>5}{'died':>5}{'drop':>5}{'kill':>5}")
    rows = list(summary["by_opponent"].items()) + [("TOTAL", summary["total"])]
    for name, s in rows:
        pl = s.get("play") or {}
        ps = "".join(f"{pl.get(k, '-'):>5}" for k in PLAY_KEYS)
        print(f"{name:<28}{s['wins']:>4}{s['ties']:>4}{s['losses']:>4}{s['points_pct']:>7}{s['score_pct']:>7}"
              f"{s['avg_score']:>7}{s['crashes']:>7}{s['timeouts']:>6}{s['forfeits']:>8}{int(s['max_secs']):>6}"
              f" | {ps}")
    print("  (per game: bank = food we returned, conc = food the opponent returned, died = our Pacman "
          "deaths, drop = food we dropped dying, kill = opponent Pacmen we ate; maxs = longest game in s)")
    if sprt:
        verdict = {"H1": "BETTER (H1 accepted)", "H0": "not better (H0 accepted)",
                   "inconclusive": "inconclusive (max games reached)",
                   "unclean": "UNCLEAN (crash / forfeit / timeout / unscored game)"}[sprt["decision"]]
        print(f"SPRT [{sprt['s0']}, {sprt['s1']}] alpha={sprt['alpha']} beta={sprt['beta']}: {verdict}; "
              f"{sprt['games']} games, score {100 * sprt['score']:.1f}%, LLR {sprt['llr']:+.2f}")
    losses = [r for r in results if r["cand_score"] < 0]
    if losses:
        print("Lost on:", ", ".join(sorted({f"{r['opponent']}@{r['layout']}" for r in losses}))[:600])
    errs = [r for r in results if "error" in r]
    if errs:
        print(f"!! {len(errs)} games produced no score. First error tail:\n{errs[0]['error']}")
    if a.json:
        with open(a.json, "w") as f:
            json.dump({"candidate": cand, "summary": summary, "sprt": sprt, "games": results}, f, indent=1)


if __name__ == "__main__":
    main()
