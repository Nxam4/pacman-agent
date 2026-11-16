# my_team.py
# ---------------
# Licensing Information: Please do not distribute or publish solutions to this
# project. You are free to use and extend these projects for educational
# purposes. The Pacman AI projects were developed at UC Berkeley, primarily by
# John DeNero (denero@cs.berkeley.edu) and Dan Klein (klein@cs.berkeley.edu).
# For more info, see http://inst.eecs.berkeley.edu/~cs188/sp09/pacman.html

import random
import contest.util as util

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
        return ReflexCaptureAgent.choose_action(self, game_state)

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
