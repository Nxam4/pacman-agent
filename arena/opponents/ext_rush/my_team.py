# External-style sparring partner (not our lineage): BOTH agents attack (two starter reflex
# attackers). Tests whether our defence holds against two simultaneous invaders.
# Local test opponent only - never part of the submitted my_team.py.
from contest.baseline_team import OffensiveReflexAgent


def create_team(first_index, second_index, is_red, first='', second='', num_training=0):
    return [OffensiveReflexAgent(first_index), OffensiveReflexAgent(second_index)]
