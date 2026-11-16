# Research knowledge for builders

Stable reference material, curated by hand (the analyst does not rewrite it). LEARNINGS.md records what
*our* experiments showed; this file records what the literature showed. When the two disagree, trust
LEARNINGS.md, because it was measured in this contest.

Sections 1-4: Pepels & Winands, "Enhancements for Monte-Carlo Tree Search in Ms Pac-Man", IEEE CIG 2012.
Section 5: Berkeley CS188 Ghostbusters (HMM inference), with our tested tracker. Section 6: POMCP.
Their MCTS Pac-Man scored an average of 107,561 against the LEGACY2 ghosts, against 66,599 for the best
CIG'11 agent. Each section below says what the paper did (**paper**) and how it maps onto Capture-the-Flag
(**here**). Parameter values are the paper's, found by trial and error. Ours will differ, so treat them
as starting points to tune.

## 1. What mattered (paper's ablation, 100 games each)
| disabled enhancement | avg score | change |
|---|---|---|
| none (full agent) | 107,561 | - |
| strategic playout -> random playout | 44,758 | **-58%** (by far the biggest) |
| variable-depth tree -> fixed 4 ply | 101,836 | -5% |
| Last-Good-Reply | 105,723 | -2% (within noise) |
| endgame tactic | 108,020 | 0% |

**Takeaway:** playout and opponent-model quality outweighs everything else. Search with random
rollouts is barely better than no search. Build a good playout policy first, and add LGR or endgame
tricks only if there is time left over.

## 2. MCTS for the attacker (Pacman on the enemy side)

### 2.1 Search over a junction graph, not over cells
**Paper:** nodes are junctions, edges are corridors between them. A tree move means "travel this
corridor to the next junction". Below the first ply, reverse moves (back to the parent junction) are
not expanded, because they create duplicate paths and need more playouts to tell moves apart.
**Here:** in `register_initial_state`, build the graph. A junction is any non-wall cell with a number
of open neighbours other than 2; dead ends count too. Store each corridor's cell list and length, and
precompute all-pairs maze distances (as `get_maze_distance` / the distancer does). The first ply has
to be a real action (N/S/E/W/Stop) from the current cell, which may be mid-corridor; deeper plies are
junction choices. This cuts the branching factor and the depth sharply compared with cell-level search.

### 2.2 Variable depth: limit by path length, not plies
**Paper:** a leaf is expanded only while the path length from the root stays at most T_path = 55
(maze units). Every root-to-leaf path then covers about the same distance, so rewards are comparable.
This stops "quick fixes" when in danger, where a short corridor and a long one would otherwise count
as one ply each.
**Here:** T_path is about 10-25 steps given our 0.4-0.5 s budget in Python. Tune it.

### 2.3 Tactics and survival-weighted values
**Paper:** each node stores the max and the average of three rewards: survival, pills and ghosts. A
tactic picks the value used in selection and backpropagation:
- *survival tactic* (when the best survival rate is below T_survival = 0.7): v = S_survival
- *pill tactic* (default): v = S_pill x S_survival
- *ghost tactic* (scared ghosts in range and survival above 0.7): v = S_ghost x S_survival

If the active tactic gives no reward (all zero), fall back down that order.
**Here:** use the tactics *collect*, *return home* and *hunt scared ghost*. Food only counts once
returned, and carried food is lost on death, so the natural value is
`v = (returned + carried_at_end) x S_survival`. Switch to *return* when carried food x (1 - survival)
is high or time is short. Survival = the playout ended without being eaten (and not trapped, see 2.6).

### 2.4 Selection and backpropagation
**Paper:** UCT `v_i + C*sqrt(ln n_p / n_i)` with C = 1.5. A child with fewer than **3 visits** is
picked at random, so a path that was unlucky once (non-deterministic opponents) is retried before it
is written off. Backpropagation uses the **maximum** over children, not the average: if "left" always
dies and "down" is always safe, the junction's survival should be 1, not 0.5. The final move goes to
the root child with the highest maximum v.

### 2.5 Long-term goals encoded in the playout reward
- **Clear whole corridors.** The paper adds pill reward only when the last pill on an edge is eaten.
  That stops the agent leaving isolated dots that are expensive to come back for. *Here:* the same,
  or a bonus for finishing a corridor or food cluster.
- **Power pill / capsule timing.** In the paper, eating a power pill without then getting at least
  0.5 ghost score in the playout sets the pill reward to 0. Otherwise the pill reward becomes
  R_pill + R_ghost. The agent learns to *wait until ghosts are close* before eating it. *Here:* a
  capsule scares the defenders for 40 moves. Its value is the deep food you can bank in that window,
  plus defenders eaten (they respawn far away). It is worth nothing if no defender threatens you.
- **Eat scared ghosts early.** The reward per eaten ghost is the remaining scared time, so ghosts
  eaten sooner are worth more.

### 2.6 Playout policies (the 58% component)
**Paper, ghosts (opponent model):** epsilon-greedy with epsilon = 0.05 random moves. Otherwise, in
priority order:
1. take a move that immediately traps Pac-Man;
2. (LGR reply, optional);
3. if within 10 units, step along the shortest path to Pac-Man;
4. if on a junction next to Pac-Man's corridor, enter it;
5. otherwise head for an assigned target: the junction in **front of** or **behind** Pac-Man,
   which produces pincer moves.

Scared ghosts maximise distance from Pac-Man. Two ghosts may not travel the same corridor in the
same direction, which spreads them out.
**Paper, Pac-Man:** a *safe move* leads into a corridor with no approaching ghost, where Pac-Man
reaches the next junction before any ghost. At a junction:
1. safe move into a corridor that still has pills;
2. any safe move;
3. random.

Inside a corridor, reverse only if a ghost is coming head-on or to chase a scared ghost.
**Playout stop conditions:** T_time = 80 steps, death, trapped (every exit blocked), or level end.
Playouts are deliberately short.
**Here:** the defenders are two ghosts. Use the same rules, with targets of front and rear junction.
Our defenders often *stay on their side*, so the playout ghost must never cross the border. Keep
playouts short (about 15-30 steps); in Python, playout count matters more than depth.

### 2.7 Endgame tactic (low value in the paper)
When no reward is within tree range for 5 consecutive moves, set a target (scared ghost > capsule >
nearest food) and reward the normalised distance gained toward it. *Here:* the equivalent is "no food
within T_path", and the fix is a target-distance reward, so the agent does not wander.

## 3. Defence (the paper's ghost team, applied to our defenders)
**Paper:** the MCTS ghost team used the same playout rules with a constant-depth tree (5 nodes).
- **Pincer, not chase.** Two defenders both chasing an invader from the same side lose it at every
  loop. Assign one to the junction ahead of the invader and one to the junction behind. Never let
  both enter the same corridor in the same direction.
- **Trap detection:** an invader is caught when every exit of its corridor is covered. A dead-end
  corridor with one defender at the mouth is a guaranteed kill.
- **Partial observability (our addition; the paper had full state).** See section 5.

## 5. Tracking hidden enemies - USE `arena/snippets/enemy_tracker.py`
Sources: Berkeley CS188 "Ghostbusters" (an HMM forward algorithm, plus particle filtering as the
approximate version). An enemy more than 5 Manhattan distance from both of our agents is hidden, and
we get only `get_agent_distances()`: the true Manhattan distance plus a uniform error from -6 to +6.
`EnemyTracker` does exact forward-algorithm inference and also uses the evidence this engine leaks:
- **negative sight evidence:** hidden means more than 5 from BOTH our agents;
- **side evidence:** `get_agent_state(e).is_pacman` stays visible while the position is hidden;
- **food or capsules vanishing** from our side: the enemy that just moved is exactly there;
- **respawn** after an invader is eaten next to us;
- **sharing:** one tracker serves both our agents, so both sonar readings are used. It advances
  exactly the enemies that moved since its last update, so it stays correct when only one agent
  calls `update()`.

**Measured** (12 games vs the baseline, 10,776 hidden-enemy observations):

| | tracker | naive "last seen" guess |
|---|---|---|
| Mean Manhattan error of the best guess | **3.2** | 12.1 |
| Same, for enemies within 12 of us | **2.5** | 9.1 |
| True cell inside the belief | 98.6% | - |
| Update time | 0.4 ms mean, 10 ms max | - |

Exact inference is cheap enough here, so a particle filter is not needed. Uses:
- the defender intercepts where the invader *probably* is, before it becomes visible;
- the attacker treats hidden defenders as probable threats instead of ignoring them;
- `prob_within(e, cells)` gives a risk score for a capsule, a corridor or the border crossing;
- `sample(e)` feeds search (section 6).

## 6. Search under hidden information: POMCP-lite (Silver & Veness, NeurIPS 2010)
POMCP is MCTS from a *belief state*. Each simulation starts by **sampling a full state from the
belief** (root sampling), then runs ordinary UCT and playouts in that sampled world. The tree is
indexed by our action / observation history, so the belief and the search share one set of samples.
The paper tested it on partially observable Pac-Man.

**What to take, and what not to:**
- *Take root sampling.* In each MCTS iteration of section 2, draw each hidden enemy's position with
  `tracker.sample(e)`. Visible enemies use their true position. Then simulate. Values then average
  over where the defenders probably are, instead of assuming they sit at their last-seen cell or
  ignoring them. This costs a few microseconds per iteration.
- *Keep the tree over OUR moves only* (open-loop). Enemy moves happen inside the playout policy of
  section 2.6. This avoids observation branching.
- *Skip* full POMCP machinery: per-node particle sets, particle reinvigoration, and history-keyed
  observation nodes. Inside a 0.5 s Python budget those cost iterations we need for playouts. The
  exact tracker already maintains the belief.
- Expected order of work: tracker first (it pays off on its own for defence), then section 2 MCTS
  with strategic playouts, then root sampling on top. Measure every step with the SPRT.

## 4. Engineering constraints that shape all of the above
- `game_state.generate_successor` deep-copies the state and is far too slow to run thousands of
  playouts in Python. Write a **lightweight simulator** with plain tuples or ints (positions, carried
  count, a food set or bitmask, scared timers) over precomputed distances and neighbour lists.
- Check the time at least every iteration, stop at about 0.4 s, and always keep a valid fallback move.
  The arena counts per-move time warnings and forfeits.
- Precompute the junction graph, distances, dead-end depth and border cells in
  `register_initial_state` (15 s limit; aim for under 10 s on the biggest layout).
- The noise and the opponents are stochastic, so an improvement shows up only over many games. The
  paper used 100 games per configuration, with 95% confidence intervals. The loop's SPRT
  (`arena.py --sprt`) decides "better or not" with the fewest games that are statistically sound.
