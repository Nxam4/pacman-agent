#!/usr/bin/env python3
"""Failure miner: groups the champion lineage's losses against OUTSIDE teams into patterns, so the
analyst (and you) can aim Claude rounds at what actually loses games instead of guessing.

Reads reports already on disk - no new games needed:
  arena/work/rNN/champion_field.json      the champion of each round vs the training field
  arena/tune/gate/{champion_,}field.json  tuner gate runs
  arena/bench/*_{a,b}.json                held-out benchmark runs (champion and previous champion)
  arena/ablate/runs/champion_*.json       switch-off test champion runs
(--all also adds every candidate's field.json.) Only games vs ext_gh_* / ext_pool teams count;
games the opponent crashed or forfeited are free wins and are left out.

Loss patterns (first match wins; candidate's view, per-game play stats):
  OUR_FAULT    our crash / forfeit / timeout warning
  OUT_RACED    we banked <= 2 and conceded >= 15: the opponent banks (or ends the game) first
  DIED_LOADED  we dropped >= 8 dots dying (a load lost on the way home)
  CLOSE        lost by 1-2 points otherwise
  OUT_SCORED   we banked >= 3 but the opponent banked more (a race lost on volume: look at our
               kills - few kills means our defence let them through)
  STARVED      we banked <= 2 and conceded 3-14: their defence starved us, a low-scoring loss
Ties: STANDOFF (banked + conceded <= 2) or TRADE. Also: colour splits (same opponent and layout,
one colour lost and the other won) and the worst opponent x layout cells.

  python3 arena/mine.py                 # print + write arena/mine/REPORT.md
  python3 arena/mine.py --record 5      # also re-play and record example losses (replays below)
  python3 arena/mine.py --all           # include every candidate's field run, not only champions
Watch a recorded game (needs a display; WSLg works):
  cd pacman-contest/src/contest && python capture.py --replay ../../../arena/mine/replays/<file>.replay
"""
import argparse
import collections
import glob
import os
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import arena  # noqa: E402
import pick  # noqa: E402

ROOT = arena.ROOT
OUT = os.path.join(ROOT, "arena", "mine")
LOSS_KINDS = ["OUR_FAULT", "OUT_RACED", "DIED_LOADED", "OUT_SCORED", "CLOSE", "STARVED"]


def sources(include_all):
    pats = ["arena/work/r*/champion_field.json", "arena/tune/gate/champion_field.json",
            "arena/tune/gate/field.json", "arena/bench/*_a.json", "arena/bench/*_b.json",
            "arena/ablate/runs/champion_*.json"]
    if include_all:
        pats.append("arena/work/r*/cand_*/field.json")
    out = []
    for p in pats:
        out += sorted(glob.glob(os.path.join(ROOT, p)))
    return out


def outside(opp):
    return "/ext_gh_" in opp or "ext_pool/" in opp


def team(opp):
    return opp.rstrip("/").split("/")[-1].replace("ext_gh_", "")


def layout_kind(layout):
    return "RANDOM" if layout.startswith("RANDOM") else layout.replace("Capture", "")


def classify(r):
    p = r.get("play") or {}
    b, c, d = p.get("banked", 0), p.get("conceded", 0), p.get("dropped", 0)
    s = r["cand_score"]
    if s == 0:
        return "STANDOFF" if b + c <= 2 else "TRADE"
    if s > 0:
        return "WIN"
    if r.get("cand_crash") or r.get("cand_forfeit") or r.get("cand_timeouts"):
        return "OUR_FAULT"
    if b <= 2 and c >= 15:
        return "OUT_RACED"
    if d >= 8:
        return "DIED_LOADED"
    if s >= -2:
        return "CLOSE"
    if b >= 3:
        return "OUT_SCORED"
    return "STARVED"


def dropped_teams():
    """Team names marked `drop` in arena/ext_teams.txt (crashers etc.): left out of the report."""
    out = set()
    try:
        for line in open(os.path.join(ROOT, "arena", "ext_teams.txt")):
            p = line.split()
            if len(p) >= 2 and p[0] == "drop":
                out.add(p[1].split("/")[0].lower().replace("-", "_"))
    except IOError:
        pass
    return out


def pct(a, b):
    return 100.0 * a / b if b else 0.0


def record_examples(cells, n, python, log):
    """Re-play the champion in the n worst opponent x layout x colour cells with --record."""
    rdir = os.path.join(OUT, "replays")
    shutil.rmtree(rdir, ignore_errors=True)
    os.makedirs(rdir)
    out = []
    for (opp, layout, red), _ in cells[:n]:
        opp_file = os.path.join(ROOT, opp, "my_team.py")
        if not os.path.exists(opp_file):
            continue
        name = "%s_%s_%s.replay" % (team(opp), layout, "red" if red else "blue")
        r_, b_ = (arena.CHAMPION, opp_file) if red else (opp_file, arena.CHAMPION)
        they = "Blue team wins" if red else "Red team wins"
        for attempt in range(1, 5):           # games vary: re-play until we record a loss
            wd = tempfile.mkdtemp(prefix="mine_")
            try:
                for f in os.listdir(arena.CONTEST_DIR):
                    os.symlink(os.path.join(arena.CONTEST_DIR, f), os.path.join(wd, f))
                p = subprocess.run([python, arena.RUN_GAME, "-r", r_, "-b", b_, "-l", layout, "-q", "-c",
                                    "--delay-step", "0", "-u", "arena", "-m", "1", "--record"],
                                   cwd=wd, capture_output=True, text=True, timeout=arena.HARNESS_TIMEOUT)
                src = os.path.join(wd, "www", "contest_arena", "replays", "match_1.replay")
                score = [l for l in p.stdout.splitlines() if "wins by" in l or "Tie game" in l]
                res = score[-1].strip() if score else "result unknown"
                lost = they in res
                if os.path.exists(src) and (lost or attempt == 4):
                    shutil.copy(src, os.path.join(rdir, name))
                    out.append((name, "%s (%s, attempt %d)" % (res, "a loss" if lost else "no loss in 4 tries", attempt)))
                    log("recorded %s: %s" % (name, out[-1][1]))
                    break
            except Exception as e:
                log("record %s %s failed: %s" % (opp, layout, e))
                break
            finally:
                shutil.rmtree(wd, ignore_errors=True)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--all", action="store_true", help="include every candidate's field run")
    ap.add_argument("--record", type=int, default=0, help="record N example losses")
    ap.add_argument("--python", default=sys.executable)
    ap.add_argument("--quiet", action="store_true", help="write the report, print only its path")
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    lines = []
    log = (lambda s: lines.append(s)) if a.quiet else (lambda s: (print(s), lines.append(s)))

    games, skipped, files = [], 0, 0
    drop = dropped_teams()
    for f in sources(a.all):
        try:
            gs = pick.load(f)["games"]
        except Exception:
            continue
        files += 1
        for r in gs:
            if not outside(r.get("opponent", "")) or team(r["opponent"]) in drop:
                continue
            if pick.opp_failed(r) or r.get("no_score"):
                skipped += 1
                continue
            games.append(r)
    if not games:
        print("no games vs outside teams found")
        return 1
    kinds = collections.Counter(classify(r) for r in games)
    losses = [r for r in games if classify(r) in LOSS_KINDS]
    nl = len(losses)
    log("# Loss patterns vs outside teams")
    log("")
    log("%d games from %d reports (champion lineage%s; %d opponent-crash games left out): "
        "%d wins, %d ties (%d standoff), %d losses." % (
            len(games), files, " + all candidates" if a.all else "", skipped, kinds["WIN"],
            kinds["STANDOFF"] + kinds["TRADE"], kinds["STANDOFF"], nl))
    log("")
    log("## Losses by pattern")
    log("| pattern | losses | share | avg bank / conc / dropped / deaths / kills |")
    log("|---|---|---|---|")
    wins = [r for r in games if r["cand_score"] > 0]
    for k, g in [(k, [r for r in losses if classify(r) == k]) for k in LOSS_KINDS] + [("(wins)", wins)]:
        if g:
            av = lambda key: sum((r.get("play") or {}).get(key, 0) for r in g) / len(g)
            log("| %s | %d | %s | %.1f / %.1f / %.1f / %.2f / %.2f |" % (
                k, len(g), "-" if k == "(wins)" else "%.0f%%" % pct(len(g), nl),
                av("banked"), av("conceded"), av("dropped"), av("deaths"), av("kills")))
    # per opponent
    log("")
    log("## By opponent (losses, and their main pattern)")
    log("| opponent | games | loss % | tie % | main loss pattern |")
    log("|---|---|---|---|---|")
    by_opp = collections.defaultdict(list)
    for r in games:
        by_opp[r["opponent"]].append(r)
    for opp, g in sorted(by_opp.items(), key=lambda kv: -pct(sum(classify(r) in LOSS_KINDS for r in kv[1]), len(kv[1]))):
        lk = collections.Counter(classify(r) for r in g if classify(r) in LOSS_KINDS)
        ties = sum(classify(r) in ("STANDOFF", "TRADE") for r in g)
        main = ", ".join("%s %d" % kv for kv in lk.most_common(2)) or "-"
        log("| %s%s | %d | %.0f%% | %.0f%% | %s |" % (team(opp), " (held-out)" if "ext_pool/" in opp else "",
                                                    len(g), pct(sum(lk.values()), len(g)), pct(ties, len(g)), main))
    # per layout
    log("")
    log("## By layout")
    log("| layout | games | loss % | tie % | main loss pattern |")
    log("|---|---|---|---|---|")
    by_lay = collections.defaultdict(list)
    for r in games:
        by_lay[layout_kind(r["layout"])].append(r)
    for lay, g in sorted(by_lay.items(), key=lambda kv: -pct(sum(classify(r) in LOSS_KINDS for r in kv[1]), len(kv[1]))):
        lk = collections.Counter(classify(r) for r in g if classify(r) in LOSS_KINDS)
        ties = sum(classify(r) in ("STANDOFF", "TRADE") for r in g)
        log("| %s | %d | %.0f%% | %.0f%% | %s |" % (lay, len(g), pct(sum(lk.values()), len(g)), pct(ties, len(g)),
                                                  ", ".join("%s %d" % kv for kv in lk.most_common(2)) or "-"))
    # colour
    red = [r for r in games if r["cand_red"]]
    blue = [r for r in games if not r["cand_red"]]
    log("")
    log("Colour: loss %% as red %.1f%% (%d games), as blue %.1f%% (%d games)." % (
        pct(sum(classify(r) in LOSS_KINDS for r in red), len(red)), len(red),
        pct(sum(classify(r) in LOSS_KINDS for r in blue), len(blue)), len(blue)))
    # worst cells: opponent x fixed layout x colour (RANDOM maps differ every game, so not cells)
    cells = collections.defaultdict(lambda: [0, 0])
    for r in games:
        if r["layout"].startswith("RANDOM"):
            continue
        c = cells[(r["opponent"], r["layout"], r["cand_red"])]
        c[0] += 1
        c[1] += classify(r) in LOSS_KINDS
    worst = sorted(((k, v) for k, v in cells.items() if v[0] >= 3 and v[1] >= 2),
                   key=lambda kv: (-pct(kv[1][1], kv[1][0]), -kv[1][0]))
    log("")
    log("## Worst opponent x layout x colour cells (fixed layouts, >= 3 games)")
    log("| opponent | layout | our colour | lost | patterns |")
    log("|---|---|---|---|---|")
    for (opp, lay, isred), (n, l) in worst[:12]:
        pk = collections.Counter(classify(r) for r in games if r["opponent"] == opp and r["layout"] == lay
                                 and r["cand_red"] == isred and classify(r) in LOSS_KINDS)
        log("| %s | %s | %s | %d of %d | %s |" % (team(opp), lay, "red" if isred else "blue", l, n,
                                                ", ".join("%s %d" % kv for kv in pk.most_common())))
    if a.record:
        log("")
        log("## Recorded example games (champion = my_team.py, re-played now; may differ from the original)")
        rec = record_examples(worst, a.record, a.python, lambda s: None)
        for name, res in rec:
            log("- `arena/mine/replays/%s`: %s" % (name, res))
        log("")
        log("Watch: `cd pacman-contest/src/contest && python capture.py --replay ../../../arena/mine/replays/<file>`")
    open(os.path.join(OUT, "REPORT.md"), "w").write("\n".join(lines) + "\n")
    if a.quiet:
        print("arena/mine/REPORT.md: %d games, %d losses" % (len(games), nl))
    return 0


if __name__ == "__main__":
    sys.exit(main())
