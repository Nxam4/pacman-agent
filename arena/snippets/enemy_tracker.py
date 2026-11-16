# Reference implementation - NOT loaded by the contest. Builders copy this class into my_team.py
# (single-file rule) and call it as shown at the bottom. Python 3.8, standard library only.
#
# Exact HMM inference (forward algorithm, as in Berkeley CS188 "Ghostbusters") over enemy positions,
# using every piece of evidence the capture engine leaks:
#   1. noisy sonar: reading = Manhattan(observer, enemy) + U{-6..6}       -> P = 1/13 inside the band
#   2. invisibility: a hidden enemy is > 5 Manhattan from BOTH our agents  -> zero those cells
#   3. side: agent_state.is_pacman stays visible even when the position is hidden
#                                                                         -> zero cells on the wrong half
#   4. food/capsules vanishing from our side: the enemy that just moved is exactly there
#   5. exact sightings collapse the belief; an enemy that vanishes right next to our ghost was eaten
#      and respawns at its start cell
# One tracker is shared by both our agents, so both agents' sonar readings are used. It advances
# exactly the enemies that moved since its previous update, so it is correct whether one or both
# of our agents call update().
import random

SIGHT_RANGE = 5
SONAR_HALF = 6


class EnemyTracker(object):
    _shared = {}   # is_red -> tracker; recreated by the team's first agent at every game start

    @classmethod
    def for_agent(cls, agent, game_state):
        """Call once from register_initial_state. Works whether one or both of our agents use it:
        an agent registering a second time means a new game started in the same process."""
        t = cls._shared.get(agent.red)
        if t is None or agent.index in t.registered:
            t = cls(agent, game_state)
            cls._shared[agent.red] = t
        t.registered.add(agent.index)
        return t

    def __init__(self, agent, game_state):
        walls = game_state.get_walls()
        self.width, self.height = walls.width, walls.height
        self.cells = [(x, y) for x in range(self.width) for y in range(self.height) if not walls[x][y]]
        cell_set = set(self.cells)
        self.nbrs = {}
        for (x, y) in self.cells:
            n = [(x, y)]   # an enemy may also stop
            for c in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if c in cell_set:
                    n.append(c)
            self.nbrs[(x, y)] = n
        self.mid = self.width // 2
        self.red = agent.red
        self.enemies = list(agent.get_opponents(game_state))
        self.start = dict((e, game_state.get_initial_agent_position(e)) for e in self.enemies)
        self.belief = dict((e, {self.start[e]: 1.0}) for e in self.enemies)
        self.last_seen = dict((e, None) for e in self.enemies)
        self.last_was_pacman = {}
        self.registered = set()
        self.last_index = None   # our agent that updated last (to know which enemies moved since)
        self.prev_food = set(agent.get_food_you_are_defending(game_state).as_list()) | \
            set(agent.get_capsules_you_are_defending(game_state))

    # ---- helpers -------------------------------------------------------------------------
    def _on_enemy_home_side(self, cell):
        """True if cell is on the ENEMY's half (where the enemy is a ghost)."""
        return (cell[0] >= self.mid) if self.red else (cell[0] < self.mid)

    def _normalise(self, b):
        z = sum(b.values())
        if z <= 0:
            return None
        return dict((c, p / z) for c, p in b.items() if p > 0)

    def _consistent(self, cell, my_positions, is_pacman):
        for m in my_positions:
            if m is not None and abs(cell[0] - m[0]) + abs(cell[1] - m[1]) <= SIGHT_RANGE:
                return False
        if is_pacman is not None and is_pacman == self._on_enemy_home_side(cell):
            return False
        return True

    # ---- main update, call once at the start of every choose_action ----------------------
    def update(self, agent, game_state):
        my_pos = game_state.get_agent_position(agent.index)
        team_pos = [game_state.get_agent_position(i) for i in agent.get_team(game_state)]
        dists = game_state.get_agent_distances()
        # Enemies that moved since the previous update (by either of our agents): every agent strictly
        # between the last updater and us in turn order. If only one of our agents calls update(),
        # that is both enemies; if both call it, exactly one.
        n = game_state.get_num_agents()
        if self.last_index is None:
            movers = [(agent.index - 1) % n]
        else:
            movers, k = [], (self.last_index + 1) % n
            while k != agent.index:
                movers.append(k)
                k = (k + 1) % n
        self.last_index = agent.index

        food_now = set(agent.get_food_you_are_defending(game_state).as_list()) | \
            set(agent.get_capsules_you_are_defending(game_state))
        eaten_cells = self.prev_food - food_now
        self.prev_food = food_now

        for e in self.enemies:
            st = game_state.get_agent_state(e)
            pos = game_state.get_agent_position(e)
            if pos is not None:
                self.belief[e] = {pos: 1.0}
                self.last_seen[e] = pos
                self.last_was_pacman[e] = st.is_pacman
                continue
            # An invader that vanishes while next to one of our agents was eaten and respawned at its
            # start (it cannot walk out of sight in one step). If instead OUR agent died and teleported,
            # the sonar filter below contradicts the start cell and the belief restarts from evidence.
            ls, was_pac = self.last_seen[e], self.last_was_pacman.get(e)
            self.last_seen[e] = None
            b = self.belief[e]
            eaten = (ls is not None and was_pac and st.is_pacman is False and
                     any(p is not None and abs(ls[0] - p[0]) + abs(ls[1] - p[1]) <= 2 for p in team_pos))
            if eaten:
                b = {self.start[e]: 1.0}
            elif e in movers:                   # elapse time: uniform over legal moves (incl. stop)
                nb = {}
                for c, p in b.items():
                    ns = self.nbrs.get(c, [c])
                    q = p / len(ns)
                    for nc in ns:
                        nb[nc] = nb.get(nc, 0.0) + q
                b = nb
                if eaten_cells and len([m for m in movers if m in self.enemies]) == 1:
                    # exactly one enemy moved, and food/capsule vanished: it is there
                    hit = [c for c in eaten_cells if c in b]
                    if len(hit) == 1:
                        b = {hit[0]: 1.0}
            noisy = dists[e] if dists is not None else None
            out = {}
            for c, p in b.items():
                if not self._consistent(c, team_pos, st.is_pacman):
                    continue
                if noisy is not None and my_pos is not None:
                    d = abs(c[0] - my_pos[0]) + abs(c[1] - my_pos[1])
                    if abs(noisy - d) > SONAR_HALF:
                        continue
                out[c] = p
            nb = self._normalise(out)
            if nb is None:                      # evidence contradicts belief: restart from evidence
                fresh = {}
                for c in self.cells:
                    if not self._consistent(c, team_pos, st.is_pacman):
                        continue
                    if noisy is not None and my_pos is not None and \
                            abs(noisy - (abs(c[0] - my_pos[0]) + abs(c[1] - my_pos[1]))) > SONAR_HALF:
                        continue
                    fresh[c] = 1.0
                nb = self._normalise(fresh) or {self.start[e]: 1.0}
            self.belief[e] = nb

    # ---- queries -------------------------------------------------------------------------
    def most_likely(self, e):
        b = self.belief[e]
        return max(b, key=b.get)

    def sample(self, e, rng=random):
        """One position drawn from the belief - use per MCTS iteration (POMCP-style root sampling)."""
        r, acc = rng.random(), 0.0
        for c, p in self.belief[e].items():
            acc += p
            if acc >= r:
                return c
        return self.most_likely(e)

    def prob_within(self, e, cells):
        """Probability mass on a set of cells (e.g. 'is an invader near our capsule?')."""
        b = self.belief[e]
        return sum(b.get(c, 0.0) for c in cells)


# ---- usage inside a CaptureAgent subclass ------------------------------------------------
#   def register_initial_state(self, game_state):
#       CaptureAgent.register_initial_state(self, game_state)
#       self.tracker = EnemyTracker.for_agent(self, game_state)
#   def choose_action(self, game_state):
#       try:
#           self.tracker.update(self, game_state)
#       except Exception:
#           pass                      # never let tracking crash the move
#       guess = self.tracker.most_likely(enemy_index)
