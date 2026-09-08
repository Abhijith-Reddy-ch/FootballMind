"""Dribbling AI: whether to carry the ball forward vs pass/shoot/hold.

    DribbleScore = SpaceAhead + DribblingAbility + GoalProgress - DefenderPressure - BallLossRisk
"""
from __future__ import annotations

from src.core.enums import ActionType
from src.core.vector import clamp, normalize, v
from src.ai.utility_ai import ActionCandidate
from src.ai.spatial import attacking_dir, nearest_opponent_distance, pressure_on


def evaluate_dribble(player, own_team, opp_team) -> ActionCandidate:
    opponents = opp_team.outfield()
    direction = v(attacking_dir(own_team.is_home()), 0.0)
    ahead_point = player.position + direction * 6.0

    space_ahead = clamp(nearest_opponent_distance(ahead_point, opponents) * 2.5, 0.0, 22.0)
    ability = (player.attributes.dribbling - 50) / 50.0 * 14.0
    goal_progress_value = 6.0  # dribbling always nudges forward; magnitude tuned vs pass/shoot elsewhere
    pressure = pressure_on(player.position, opponents) * 18.0
    fatigue_penalty = player.fatigue_ratio() * 8.0
    loss_risk = clamp(pressure * 0.6 + fatigue_penalty * 0.4, 0.0, 20.0)

    components = {
        "SpaceAhead": space_ahead,
        "DribblingAbility": ability,
        "GoalProgress": goal_progress_value,
        "DefenderPressure": -pressure,
        "BallLossRisk": -loss_risk,
    }
    utility = sum(components.values())
    reasons = []
    if space_ahead > 12:
        reasons.append("Space to run into")
    if pressure > 8:
        reasons.append("Defender closing down")
    return ActionCandidate(action=ActionType.DRIBBLE, utility=utility,
                            target_position=ahead_point, components=components, reasons=reasons)
