#!/usr/bin/env python3
"""Run one game exactly like `python capture.py ARGS` and also record how it was played.

arena.py calls this instead of capture.py. The engine is not modified (it is the organisers'
code); two hooks are added from outside, in this process only:
  * the null display's update(), which the game loop calls once after every REAL move (agents'
    own generate_successor look-ahead never reaches it - hooking the death rule itself would count
    imagined deaths). Comparing consecutive real states: an agent that jumped more than one cell
    was eaten; if it was a Pacman, the food it carried was dropped.
  * save_score(), called once at the end: reads each agent's banked food (num_returned).
Writes www/contest_<name>/scores/match_<id>_stats.json next to the normal score file:
  {"returned": [a0..a3], "deaths": [...], "dropped": [...], "ghost_eaten": [...], "carrying": [...]}
Agent indices: red = 0, 2; blue = 1, 3. Only for quiet (-q) games; otherwise stats are omitted.
"""
import json
import os
import sys

# Same import path as `python capture.py` run from the contest dir (cwd), not this file's dir.
sys.path[0] = os.getcwd()

import contest.capture as capture  # noqa: E402
import contest.text_display as text_display  # noqa: E402

STATS = {"deaths": [0, 0, 0, 0], "dropped": [0, 0, 0, 0], "ghost_eaten": [0, 0, 0, 0]}
_prev = {}


def _observe(data):
    try:
        for i, s in enumerate(data.agent_states):
            pos = s.configuration.pos if s.configuration else None
            p = _prev.get(i)
            if p is not None and pos is not None and p[0] is not None and i < 4:
                if abs(pos[0] - p[0][0]) + abs(pos[1] - p[0][1]) > 1.5:   # teleported to start: eaten
                    if p[1]:
                        STATS["deaths"][i] += 1
                        STATS["dropped"][i] += p[2]
                    else:
                        STATS["ghost_eaten"][i] += 1
            _prev[i] = (pos, bool(s.is_pacman), int(s.num_carrying))
    except Exception:
        pass


_orig_init = text_display.NullGraphics.initialize
_orig_update = text_display.NullGraphics.update
_orig_save = capture.save_score


def _init(self, state, *args, **kw):
    _observe(state)
    return _orig_init(self, state, *args, **kw)


def _update(self, state):
    _observe(state)
    return _orig_update(self, state)


def _save(games, total_time, **kw):
    try:
        st = games[0].state.data.agent_states
        out = dict(STATS)
        out["returned"] = [int(s.num_returned) for s in st]
        out["carrying"] = [int(s.num_carrying) for s in st]
        folder = "www/contest_%s/scores" % kw.get("contest_name", "default")
        os.makedirs(folder, exist_ok=True)
        with open(os.path.join(folder, "match_%s_stats.json" % kw.get("match_id", 0)), "w") as f:
            json.dump(out, f)
    except Exception as e:  # stats are optional; the game result must never depend on them
        print("run_game: stats not written (%s)" % e, file=sys.stderr)
    return _orig_save(games, total_time, **kw)


text_display.NullGraphics.initialize = _init
text_display.NullGraphics.update = _update
capture.save_score = _save

if __name__ == "__main__":
    capture.run(sys.argv[1:])
