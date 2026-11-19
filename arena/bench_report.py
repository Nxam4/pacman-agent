#!/usr/bin/env python3
"""Report of a held-out benchmark run (called by arena/benchmark.sh), plus pooling across runs.

  bench_report.py TS A.py B.py SEED     print the table for arena/bench/TS_{a,b}.json, append a line
                                        to arena/bench/history.tsv, then print the pooled estimate
  bench_report.py --pool [A.py B.py]    pooled estimate only (default A = my_team.py, B = the most
                                        recently frozen champion)

Pooling: every history row whose A and B files had the same content (md5) as the given pair is
combined game by game, one run per seed (the latest; a repeated seed replays the same games, so it
would be counted twice). At ~90% scores, a 1-2 point difference needs several hundred games: one
run (~200 games, +-2.5) rarely settles it, so read the pooled line, not single runs.
"""
import glob
import hashlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pick  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BENCH = os.path.join(ROOT, "arena", "bench")
HIST = os.path.join(BENCH, "history.tsv")
COLS = ["time", "A", "B", "seed", "A_md5", "B_md5", "games", "A_score", "B_score",
        "paired_diff", "se", "verdict"]


def md5(path):
    try:
        return hashlib.md5(open(path, "rb").read()).hexdigest()[:12]
    except IOError:
        return "?"


def sc(s):
    return s.get("clean_score_pct") if s.get("clean_score_pct") is not None else s.get("score_pct", 0)


def verdict(m, se):
    return "A better" if m - 1.96 * se > 0 else "A worse" if m + 1.96 * se < 0 else "no clear difference"


def ci(m, se):
    return "%+.1f +- %.1f points, 95%% CI %+.1f..%+.1f" % (
        100 * m, 100 * se, 100 * (m - 1.96 * se), 100 * (m + 1.96 * se))


def read_hist():
    if not os.path.exists(HIST):
        return []
    lines = open(HIST).read().splitlines()
    head = lines[0].split("\t")
    return [dict(zip(head, l.split("\t"))) for l in lines[1:] if l.strip()]


def append_hist(row):
    new = not os.path.exists(HIST)
    with open(HIST, "a") as f:
        if new:
            f.write("\t".join(COLS) + "\n")
        f.write("\t".join(str(row[c]) for c in COLS) + "\n")


def pooled(a_md5, b_md5):
    """Pooled per-game diffs of all runs of this exact A/B pair, one per seed (latest)."""
    by_seed = {}
    for r in read_hist():
        if r.get("A_md5") == a_md5 and r.get("B_md5") == b_md5 and r.get("seed", "?") != "?":
            by_seed[r["seed"]] = r["time"]                     # rows are in time order: latest wins
    d, used = [], []
    for seed, ts in sorted(by_seed.items()):
        try:
            d += pick.paired_diffs(os.path.join(BENCH, ts + "_a.json"), os.path.join(BENCH, ts + "_b.json"))
            used.append(seed)
        except Exception as e:
            print("  (run %s not pooled: %s)" % (ts, e))
    return d, used


def print_pooled(a_path, b_path):
    a5, b5 = md5(a_path), md5(b_path)
    d, used = pooled(a5, b5)
    if not d:
        print("pooled: no benchmark runs of this A/B pair yet")
        return
    m, se, n = pick.mean_se(d)
    print("POOLED over %d run(s) of this exact A/B pair (seeds %s), %d games: %s -> %s" % (
        len(used), ", ".join(used), n, ci(m, se), verdict(m, se)))


def report(ts, a_path, b_path, seed):
    ja = pick.load(os.path.join(BENCH, ts + "_a.json"))
    jb = pick.load(os.path.join(BENCH, ts + "_b.json"))
    sa, sb = ja["summary"]["by_opponent"], jb["summary"]["by_opponent"]
    print("score % over games the opponent did not crash/forfeit (oppX = games it did, in A's run)")
    print("%-26s %8s %8s %7s %5s   %s" % ("held-out opponent", "A score", "B score", "A-B", "oppX",
                                         "A avg margin / bank / conc"))
    for k in sa:
        a, b = sa[k], sb.get(k, {})
        pa = a.get("play") or {}
        print("%-26s %7.1f%% %7.1f%% %+6.1f %5s   %+6.1f / %s / %s" % (
            k.split("/")[-1], sc(a), sc(b), sc(a) - sc(b), a.get("opp_crashes", "-"),
            a["avg_score"], pa.get("banked", "-"), pa.get("conceded", "-")))
    d = pick.paired_diffs(os.path.join(BENCH, ts + "_a.json"), os.path.join(BENCH, ts + "_b.json"))
    print("(%d of %d games skipped: opponent crashed or forfeited)" % (len(ja["games"]) - len(d), len(ja["games"])))
    m, se, n = pick.mean_se(d)
    ta, tb = ja["summary"]["total"], jb["summary"]["total"]
    print("%-26s %7.1f%% %7.1f%% %+6.1f   (paired, this run: %s)" % (
        "TOTAL", sc(ta), sc(tb), sc(ta) - sc(tb), ci(m, se)))
    for lbl, t in (("A", ta), ("B", tb)):
        if t["crashes"] or t["timeouts"] or t.get("forfeits"):
            print("!! %s not clean: crashes %s, slow %s, forfeits %s" % (lbl, t["crashes"], t["timeouts"], t.get("forfeits")))
    v = verdict(m, se)
    print("verdict (this run):", v)
    append_hist({"time": ts, "A": a_path, "B": b_path, "seed": seed, "A_md5": md5(a_path),
                 "B_md5": md5(b_path), "games": n, "A_score": "%.1f" % sc(ta), "B_score": "%.1f" % sc(tb),
                 "paired_diff": "%+.1f" % (100 * m), "se": "%.1f" % (100 * se), "verdict": v})
    print_pooled(a_path, b_path)


def latest_champ():
    ds = sorted(glob.glob(os.path.join(ROOT, "arena", "opponents", "champ_*", "")), key=os.path.getmtime)
    return os.path.join(ds[-1], "my_team.py")


if __name__ == "__main__":
    os.chdir(ROOT)
    if sys.argv[1:2] == ["--pool"]:
        a = sys.argv[2] if len(sys.argv) > 2 else "my_team.py"
        b = sys.argv[3] if len(sys.argv) > 3 else latest_champ()
        print_pooled(a, b)
    elif len(sys.argv) == 5:
        report(*sys.argv[1:5])
    else:
        print(__doc__)
        sys.exit(2)
