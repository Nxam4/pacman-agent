# Eutopia Pacman Contest 2026/27 - team repo

We are building a Pacman Capture-the-Flag team (UC Berkeley CS188 framework, refactored by UPF).
The organisers clone this repo and load `my_team.py` from its root. Test round: code frozen
22 Nov 2026 23:59. Final: code frozen 3 Dec 2026 23:59.

## Game rules that matter for strategy
- Map split in halves; on your own side you are a ghost, on the enemy side a Pacman.
- Food is scored only when a Pacman carries it back home (1 point per dot). Eaten Pacman drops it.
- Power capsule: enemy ghosts scared for 40 moves (you can eat them; they respawn).
- You see an enemy's exact position only within 5 Manhattan distance of you or your teammate;
  otherwise you get a noisy distance reading per enemy.
- Game ends when a team returns all but 2 enemy dots, or after 1200 moves (300 per agent).
  Higher score wins; 0 is a tie. Tournament points: win 3, tie 1.

## Hard constraints (breaking these loses games outright)
- **Time:** < 1 s per move (aim for <= 0.5 s - the cluster may be slower than your machine).
  3 warnings or any single move > 3 s forfeits the game. `register_initial_state` may use up to 15 s
  (aim for <= 10 s) - precompute maze distances there.
- **No exceptions.** A crash forfeits. Guard every risky code path.
- **Python 3.8 syntax, standard library only** (the contest environment installs only `frozendict`).
  No `match`, no `list[int]`/`dict[str,int]` annotations evaluated at runtime, no `|` in types, no numpy.
- **Single file.** Keep everything in `my_team.py`. Helper modules risk name collisions with the
  other team's files when both are loaded into one process.
- Keep the `create_team(first_index, second_index, is_red, first=..., second=..., num_training=0)`
  signature and return two `CaptureAgent` subclasses.
- Never edit anything under `pacman-contest/` - the organisers use their own copy.

## Tooling
- Run a visible game (from `pacman-contest/src/contest/`):
  `python capture.py -r ../../../my_team.py -b baseline_team`
- Evaluate a team file: `python3 arena/arena.py <team.py> [--quick] [--opponents a.py b.py] [--games N]`
  Prints W/T/L, points %, crashes and timeout ("slow") counts per opponent, plus per-game play
  stats (bank/conc = food returned by us/them, died/drop = our Pacman deaths/food dropped, kill).
  Results are noisy: under ~30 games, only trust large differences.
- Numeric constants live in top-level `NAME = number` lines; `arena/tune.py` tunes them (SPSA).
- `arena/opponents/exploit_*` and `ext_*` are league opponents of a different style (not our lineage).
- `arena/opponents/champ_*/my_team.py` are frozen past champions; a new version must not regress
  against them.
- `arena/LEARNINGS.md` - accumulated findings. Read it before changing strategy.
