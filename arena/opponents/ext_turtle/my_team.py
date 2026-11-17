# External-style sparring partner (not our lineage): BOTH agents defend (two starter reflex
# defenders). Tests whether our attacker can still bank food against a double guard.
# Local test opponent only - never part of the submitted my_team.py.
from contest.baseline_team import DefensiveReflexAgent


def create_team(first_index, second_index, is_red, first='', second='', num_training=0):
    return [DefensiveReflexAgent(first_index), DefensiveReflexAgent(second_index)]
