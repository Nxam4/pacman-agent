# my_team.py
# ---------------
# Licensing Information: Please do not distribute or publish solutions to this
# project. You are free to use and extend these projects for educational
# purposes. The Pacman AI projects were developed at UC Berkeley, primarily by
# John DeNero (denero@cs.berkeley.edu) and Dan Klein (klein@cs.berkeley.edu).
# For more info, see http://inst.eecs.berkeley.edu/~cs188/sp09/pacman.html

import random
import heapq
import contest.util as util

DEBUG = False
HIDDEN_W = 3.0      # soft cost per unit of hidden-defender belief proximity
CLUSTER_W = 0.5     # bonus per neighbouring dot when choosing a food target
CARRY_BUDGET = 12   # max path cost to the next dot when carrying nothing
CARRY_STEP = 2      # ... shrinks by this per carried dot
SAFE_RETURN = False  # eat a dot only if a safe way home / to a capsule exists afterwards
INVADER_SNAP = True # at home with nothing carried: eat an invader within 3 steps

from contest.capture_agents import CaptureAgent
from contest.game import Directions
from contest.util import nearest_point


#################
# Enemy tracking #
#################
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




#################
# Team creation #
#################

def create_team(first_index, second_index, is_red,
                first='OffensiveReflexAgent', second='DefensiveReflexAgent', num_training=0):
    """
    This function should return a list of two agents that will form the
    team, initialized using firstIndex and secondIndex as their agent
    index numbers.  isRed is True if the red team is being created, and
    will be False if the blue team is being created.

    As a potentially helpful development aid, this function can take
    additional string-valued keyword arguments ("first" and "second" are
    such arguments in the case of this function), which will come from
    the --red_opts and --blue_opts command-line arguments to capture.py.
    For the nightly contest, however, your team will be created without
    any extra arguments, so you should make sure that the default
    behavior is what you want for the nightly contest.
    """
    return [eval(first)(first_index), eval(second)(second_index)]


##########
# Agents #
##########

class ReflexCaptureAgent(CaptureAgent):
    """
    A base class for reflex agents that choose score-maximizing actions
    """

    def __init__(self, index, time_for_computing=.1):
        super().__init__(index, time_for_computing)
        self.start = None

    def register_initial_state(self, game_state):
        self.start = game_state.get_agent_position(self.index)
        CaptureAgent.register_initial_state(self, game_state)

    def choose_action(self, game_state):
        """
        Picks among the actions with the highest Q(s,a).
        """
        actions = game_state.get_legal_actions(self.index)

        # You can profile your evaluation time by uncommenting these lines
        # start = time.time()
        values = [self.evaluate(game_state, a) for a in actions]
        # print 'eval time for agent %d: %.4f' % (self.index, time.time() - start)

        max_value = max(values)
        best_actions = [a for a, v in zip(actions, values) if v == max_value]

        food_left = len(self.get_food(game_state).as_list())

        if food_left <= 2:
            best_dist = 9999
            best_action = None
            for action in actions:
                successor = self.get_successor(game_state, action)
                pos2 = successor.get_agent_position(self.index)
                dist = self.get_maze_distance(self.start, pos2)
                if dist < best_dist:
                    best_action = action
                    best_dist = dist
            return best_action

        return random.choice(best_actions)

    def get_successor(self, game_state, action):
        """
        Finds the next successor which is a grid position (location tuple).
        """
        successor = game_state.generate_successor(self.index, action)
        pos = successor.get_agent_state(self.index).get_position()
        if pos != nearest_point(pos):
            # Only half a grid position was covered
            return successor.generate_successor(self.index, action)
        else:
            return successor

    def evaluate(self, game_state, action):
        """
        Computes a linear combination of features and feature weights
        """
        features = self.get_features(game_state, action)
        weights = self.get_weights(game_state, action)
        return features * weights

    def get_features(self, game_state, action):
        """
        Returns a counter of features for the state
        """
        features = util.Counter()
        successor = self.get_successor(game_state, action)
        features['successor_score'] = self.get_score(successor)
        return features

    def get_weights(self, game_state, action):
        """
        Normally, weights do not depend on the game state.  They can be either
        a counter or a dictionary.
        """
        return {'successor_score': 1.0}


class OffensiveReflexAgent(ReflexCaptureAgent):
    """Danger-aware attacker.  One Dijkstra per move over the maze where
       - a cell on the enemy side is BLOCKED if a visible, active defender can reach it no later
         than we do (so every path found is one the defender cannot intercept),
       - hidden defenders add a soft cost from the shared EnemyTracker belief,
    then it picks the cheapest food (cluster bonus, dead-end test), a capsule when a defender is
    close, or the way home when carrying enough / threatened / out of time."""

    def register_initial_state(self, game_state):
        ReflexCaptureAgent.register_initial_state(self, game_state)
        self.ready = False
        try:
            self.tracker = EnemyTracker.for_agent(self, game_state)
        except Exception:
            self.tracker = None
        try:
            self._precompute(game_state)
            self.ready = True
        except Exception:
            self.ready = False

    def _precompute(self, game_state):
        walls = game_state.get_walls()
        W, H = walls.width, walls.height
        self.W, self.H = W, H
        self.mid = W // 2
        cells = [(x, y) for x in range(W) for y in range(H) if not walls[x][y]]
        cset = set(cells)
        self.nb = {}
        for (x, y) in cells:
            lst = []
            for a, (dx, dy) in ((Directions.NORTH, (0, 1)), (Directions.SOUTH, (0, -1)),
                                (Directions.EAST, (1, 0)), (Directions.WEST, (-1, 0))):
                c = (x + dx, y + dy)
                if c in cset:
                    lst.append((a, c))
            self.nb[(x, y)] = lst
        hx = self.mid - 1 if self.red else self.mid
        ex = self.mid if self.red else self.mid - 1
        self.border = [(hx, y) for y in range(H) if (hx, y) in cset and (ex, y) in cset]
        if not self.border:
            self.border = [(hx, y) for y in range(H) if (hx, y) in cset]
        self.enemy_cells = [c for c in cells if not self._home(c)]
        # dead-end depth: strip leaves repeatedly; depth = distance to the remaining core
        deg = dict((c, len(self.nb[c])) for c in cells)
        removed = set()
        queue = [c for c in cells if deg[c] <= 1]
        while queue:
            c = queue.pop()
            if c in removed:
                continue
            removed.add(c)
            for _, n in self.nb[c]:
                if n not in removed:
                    deg[n] -= 1
                    if deg[n] <= 1:
                        queue.append(n)
        self.depth = dict((c, 0) for c in cells)
        if len(removed) < len(cells):
            frontier = [c for c in cells if c not in removed]
            seen = set(frontier)
            d = 0
            while frontier:
                nxt = []
                d += 1
                for c in frontier:
                    for _, n in self.nb[c]:
                        if n not in seen:
                            seen.add(n)
                            self.depth[n] = d
                            nxt.append(n)
                frontier = nxt

    def _home(self, c):
        return (c[0] < self.mid) if self.red else (c[0] >= self.mid)

    # ------------------------------------------------------------------------------------
    def choose_action(self, game_state):
        legal = game_state.get_legal_actions(self.index)
        try:
            if self.tracker is not None:
                try:
                    self.tracker.update(self, game_state)
                except Exception:
                    pass
            if self.ready:
                a = self._choose(game_state)
                if a in legal:
                    return a
        except Exception:
            if DEBUG:
                import traceback
                traceback.print_exc()
        try:
            return ReflexCaptureAgent.choose_action(self, game_state)
        except Exception:
            return random.choice(legal) if legal else Directions.STOP

    def _threats(self, game_state):
        """visible: [(pos, delay)] active defenders we can see (delay = scared moves left).
           hidden: [(pos, prob, delay)] belief cells of unseen defenders."""
        visible, hidden = [], []
        for e in self.get_opponents(game_state):
            st = game_state.get_agent_state(e)
            p = game_state.get_agent_position(e)
            delay = int(st.scared_timer)
            if p is not None:
                if not st.is_pacman:
                    visible.append(((int(p[0]), int(p[1])), delay))
                continue
            if st.is_pacman or self.tracker is None:
                continue
            b = self.tracker.belief.get(e)
            if not b:
                continue
            top = sorted(b.items(), key=lambda kv: -kv[1])[:8]
            z = sum(pr for _, pr in top)
            if z <= 0:
                continue
            for c, pr in top:
                hidden.append((c, pr / z, delay))
        return visible, hidden

    def _search(self, start, visible, soft, hard=True):
        """Dijkstra from start. Returns (cost, steps, parent) dicts. Enemy-side cells that a visible
        defender reaches no later than us are blocked (hard) or very expensive (not hard)."""
        dist = self.get_maze_distance
        home = self._home
        cost = {start: 0.0}
        steps = {start: 0}
        parent = {start: None}
        heap = [(0.0, 0, start)]
        done = set()
        while heap:
            c0, t, c = heapq.heappop(heap)
            if c in done:
                continue
            done.add(c)
            t1 = t + 1
            for _, n in self.nb[c]:
                if n in done:
                    continue
                extra = 0.0
                if not home(n):
                    blocked = False
                    for gp, delay in visible:
                        dg = dist(gp, n)
                        m = dg + delay - t1      # defender's slack: <= 0 means it gets there first
                        if m <= 0:
                            blocked = True
                            if hard:
                                break
                            extra += 60.0 if (dg > 1 or delay > 0) else 500.0
                        elif m <= 3:
                            extra += (8.0, 4.0, 1.5)[m - 1]
                    if blocked and hard:
                        continue
                    extra += soft.get(n, 0.0)
                nc = c0 + 1.0 + extra
                if n not in cost or nc < cost[n]:
                    cost[n] = nc
                    steps[n] = t1
                    parent[n] = c
                    heapq.heappush(heap, (nc, t1, n))
        return cost, steps, parent

    def _safe_return(self, src, t0, visible, caps):
        """Champion's time-expanded safe BFS: standing on src at time t0, is there a route home
        (or to a capsule) on which no visible defender can be at a cell by the time we are?"""
        home = self._home
        if home(src) or not visible:
            return True
        dist = self.get_maze_distance
        seen = set([src])
        frontier = [src]
        t = t0
        while frontier:
            t += 1
            nxt = []
            for c in frontier:
                for _, n in self.nb[c]:
                    if n in seen:
                        continue
                    if home(n):
                        return True
                    bad = False
                    for gp, delay in visible:
                        if delay <= t and dist(gp, n) <= t:
                            bad = True
                            break
                    if bad:
                        continue
                    if n in caps:
                        return True
                    seen.add(n)
                    nxt.append(n)
            frontier = nxt
        return False

    def _first_action(self, start, target, parent):
        c = target
        guard = 0
        while parent.get(c) is not None and parent[c] != start and guard < 5000:
            c = parent[c]
            guard += 1
        if parent.get(c) is None:
            return None
        for a, n in self.nb[start]:
            if n == c:
                return a
        return None

    def _choose(self, game_state):
        dist = self.get_maze_distance
        p = game_state.get_agent_position(self.index)
        pos = (int(p[0]), int(p[1]))
        st = game_state.get_agent_state(self.index)
        carrying = st.num_carrying
        food = self.get_food(game_state).as_list()
        caps = list(self.get_capsules(game_state))
        moves_left = game_state.data.timeleft // 4
        at_home = self._home(pos)
        visible, hidden = self._threats(game_state)

        # cheap defence (from the champion): eat an invader that is right next to us
        if INVADER_SNAP and at_home and st.scared_timer == 0 and carrying == 0:
            best_inv, best_d = None, 4
            for e in self.get_opponents(game_state):
                es = game_state.get_agent_state(e)
                ep = game_state.get_agent_position(e)
                if ep is not None and es.is_pacman:
                    q = (int(ep[0]), int(ep[1]))
                    d = dist(pos, q)
                    if d < best_d:
                        best_inv, best_d = q, d
            if best_inv is not None:
                for a, n in self.nb[pos]:
                    if self._home(n) and dist(n, best_inv) < best_d:
                        return a

        # soft danger from hidden defenders (belief mass near a cell)
        soft = {}
        if hidden:
            for c in self.enemy_cells:
                s = 0.0
                for b, pr, delay in hidden:
                    if delay > 8:
                        continue
                    d = dist(b, c)
                    if d <= 5:
                        s += pr * (6 - d)
                if s > 0:
                    soft[c] = s * HIDDEN_W
        cost, steps, parent = self._search(pos, visible, soft, True)

        d_home = 0 if at_home else min(dist(pos, b) for b in self.border)
        near_threat = None
        for gp, delay in visible:
            d = dist(pos, gp)
            if delay <= d + 2 and (near_threat is None or d < near_threat):
                near_threat = d
        min_delay = min([dl for _, dl in visible] + [dl for _, _, dl in hidden] + [999])
        powered = min_delay > 3 and min_delay != 999

        # ---- candidate food ------------------------------------------------------------
        best_food, best_val, best_cost = None, None, None
        fset = set(food)
        cands = []
        for f in food:
            if f not in cost:
                continue
            tf = steps[f]
            dep = self.depth.get(f, 0)
            ok = True
            for gp, delay in visible:
                if dist(gp, f) + delay <= tf + 2 * dep:
                    ok = False
                    break
            if not ok:
                continue
            v = cost[f]
            if dep > 0:
                for b, pr, delay in hidden:
                    if dist(b, f) + delay <= tf + 2 * dep:
                        v += pr * 4.0 * dep
            near = 0
            for dx in (-2, -1, 0, 1, 2):
                for dy in (-2, -1, 0, 1, 2):
                    if (dx or dy) and (f[0] + dx, f[1] + dy) in fset:
                        near += 1
            v -= CLUSTER_W * min(near, 5)
            # must still be able to walk home afterwards
            if tf + min(dist(f, b) for b in self.border) + 2 >= moves_left:
                continue
            cands.append((v, f))
        if cands:
            cands.sort()
            if SAFE_RETURN and visible:
                capset = set(caps)
                for v, f in cands[:12]:
                    if self._safe_return(f, steps[f], visible, capset):
                        best_food, best_val, best_cost = f, v, cost[f]
                        break
            else:
                best_val, best_food = cands[0]
                best_cost = cost[best_food]

        home_cells = [b for b in self.border if b in cost]
        best_home = min(home_cells, key=lambda b: cost[b]) if home_cells else None
        rc = [c for c in caps if c in cost]
        best_cap = min(rc, key=lambda c: cost[c]) if rc else None

        target = None
        if not at_home:
            go_home = False
            if carrying > 0:
                if len(food) <= 2 or moves_left <= d_home + 6:
                    go_home = True
                elif best_food is None:
                    go_home = True
                elif powered:
                    go_home = best_cost + d_home + 4 >= min_delay and best_cost > 2
                else:
                    budget = max(2, CARRY_BUDGET - CARRY_STEP * carrying)
                    if near_threat is not None and near_threat <= 5:
                        budget = min(budget, 2)
                    if best_cost > budget:
                        go_home = True
            # capsule when a defender is close and awake (KNOWLEDGE 2.5)
            if best_cap is not None and not powered and near_threat is not None and near_threat <= 6:
                target = best_cap
            elif go_home:
                if best_home is not None:
                    target = best_home
                elif best_cap is not None:
                    target = best_cap
                else:
                    return self._escape(game_state, pos, visible, soft)
        if target is None:
            if best_food is not None:
                target = best_food
            elif not at_home:
                if best_home is not None:
                    target = best_home
                elif best_cap is not None:
                    target = best_cap
                else:
                    return self._escape(game_state, pos, visible, soft)
            else:
                # at home, every food is guarded: slide along the border away from the defenders
                if visible:
                    cands = [b for b in self.border if b in cost]
                    if cands:
                        target = max(cands, key=lambda b: min(dist(b, gp) for gp, _ in visible)
                                     - 0.3 * dist(pos, b))
                if target is None or target == pos:
                    return self._escape(game_state, pos, visible, soft)
        if target == pos:
            return Directions.STOP
        a = self._first_action(pos, target, parent)
        if a is None:
            return self._escape(game_state, pos, visible, soft)
        return a

    def _escape(self, game_state, pos, visible, soft):
        """No guaranteed-safe plan: take the least bad route home (or just keep away)."""
        dist = self.get_maze_distance
        if not self._home(pos):
            cost, steps, parent = self._search(pos, visible, soft, False)
            cands = [b for b in self.border if b in cost]
            caps = [c for c in self.get_capsules(game_state) if c in cost]
            tgt = None
            if cands:
                tgt = min(cands, key=lambda b: cost[b])
            if caps:
                c = min(caps, key=lambda q: cost[q])
                if tgt is None or cost[c] < cost[tgt]:
                    tgt = c
            if tgt is not None and tgt != pos:
                a = self._first_action(pos, tgt, parent)
                if a is not None:
                    return a
        best, best_v = Directions.STOP, None
        for a, n in self.nb[pos] + [(Directions.STOP, pos)]:
            v = 0.0
            if not self._home(n):
                for gp, delay in visible:
                    if delay <= 1:
                        v += min(dist(n, gp), 8)
                v -= 2.0 * self.depth.get(n, 0)
            else:
                v += 20.0
            if best_v is None or v > best_v:
                best, best_v = a, v
        return best


class _OldOffensiveReflexAgent(ReflexCaptureAgent):
    """
  A reflex agent that seeks food. This is an agent
  we give you to get an idea of what an offensive agent might look like,
  but it is by no means the best or only way to build an offensive agent.
  """

    def get_features(self, game_state, action):
        features = util.Counter()
        successor = self.get_successor(game_state, action)
        food_list = self.get_food(successor).as_list()
        features['successor_score'] = -len(food_list)  # self.getScore(successor)

        # Compute distance to the nearest food

        if len(food_list) > 0:  # This should always be True,  but better safe than sorry
            my_pos = successor.get_agent_state(self.index).get_position()
            min_distance = min([self.get_maze_distance(my_pos, food) for food in food_list])
            features['distance_to_food'] = min_distance
        return features

    def get_weights(self, game_state, action):
        return {'successor_score': 100, 'distance_to_food': -1}


class DefensiveReflexAgent(ReflexCaptureAgent):
    """Reflex defender that, when no invader is visible, moves toward where the EnemyTracker
    believes the invader (or the nearest enemy's likely crossing point) is."""

    def register_initial_state(self, game_state):
        ReflexCaptureAgent.register_initial_state(self, game_state)
        self.tracker = EnemyTracker.for_agent(self, game_state)
        walls = game_state.get_walls()
        x = walls.width // 2 - 1 if self.red else walls.width // 2
        self.border = [(x, y) for y in range(walls.height) if not walls[x][y]]

    def choose_action(self, game_state):
        try:
            self.tracker.update(self, game_state)
            self._targets = self._belief_targets(game_state)
        except Exception:
            self._targets = None
        try:
            return ReflexCaptureAgent.choose_action(self, game_state)
        except Exception:
            legal = game_state.get_legal_actions(self.index)
            return legal[0] if legal else Directions.STOP

    def _belief_targets(self, game_state):
        hidden_invaders, others = [], []
        for e in self.get_opponents(game_state):
            st = game_state.get_agent_state(e)
            if game_state.get_agent_position(e) is not None:
                continue
            guess = self.tracker.most_likely(e)
            (hidden_invaders if st.is_pacman else others).append(guess)
        if hidden_invaders:
            return ("invader", hidden_invaders)
        if others and self.border:
            # guard the border cell closest to where the nearest enemy probably is
            best = min(self.border, key=lambda b: min(self.get_maze_distance(b, g) for g in others))
            return ("border", [best])
        return None

    def get_features(self, game_state, action):
        features = util.Counter()
        successor = self.get_successor(game_state, action)

        my_state = successor.get_agent_state(self.index)
        my_pos = my_state.get_position()

        features['on_defense'] = 1
        if my_state.is_pacman: features['on_defense'] = 0

        enemies = [successor.get_agent_state(i) for i in self.get_opponents(successor)]
        invaders = [a for a in enemies if a.is_pacman and a.get_position() is not None]
        features['num_invaders'] = len(invaders)
        if len(invaders) > 0:
            dists = [self.get_maze_distance(my_pos, a.get_position()) for a in invaders]
            features['invader_distance'] = min(dists)
        else:
            t = getattr(self, "_targets", None)
            if t:
                d = min(self.get_maze_distance(my_pos, c) for c in t[1])
                features['belief_invader_distance' if t[0] == "invader" else 'patrol_distance'] = d

        if action == Directions.STOP: features['stop'] = 1
        rev = Directions.REVERSE[game_state.get_agent_state(self.index).configuration.direction]
        if action == rev: features['reverse'] = 1

        return features

    def get_weights(self, game_state, action):
        return {'num_invaders': -1000, 'on_defense': 100, 'invader_distance': -10, 'stop': -100,
                'reverse': -2, 'belief_invader_distance': -5, 'patrol_distance': -1}
