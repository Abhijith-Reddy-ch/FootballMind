"""Shooting AI: shot-worthiness utility and an expected-goals (xG) style probability model.

    ShotScore = DistanceToGoal + AngleToGoal + PlayerShootingAbility + SpaceAvailable
                - DefenderPressure - GoalkeeperDifficulty
"""
from __future__ import annotations

import math
import random
from typing import Optional

from src.core.enums import ActionType
from src.core.vector import distance, clamp, angle_between, v as vec2
from src.ai.utility_ai import ActionCandidate
from src.ai.spatial import nearest_opponent_distance, pressure_on
from src.game import pitch

MAX_SHOOT_RANGE = 32.0


def _goal_angle_deg(pos, goal_center, home_attacking: bool) -> float:
    """Angle (degrees) subtended by the goal mouth from `pos` - wider angle = easier chance.

    Uses the dot-product angle between the two goal-post vectors (angle_between clamps to
    0-180 via acos) rather than subtracting raw atan2 values, which wrap incorrectly once
    either post vector crosses the +-180 degree seam behind the shooter's shooting line.
    """
    y_min, y_max = pitch.GOAL_Y_MIN, pitch.GOAL_Y_MAX
    v1 = vec2(goal_center[0] - pos[0], y_min - pos[1])
    v2 = vec2(goal_center[0] - pos[0], y_max - pos[1])
    return angle_between(v1, v2)


def evaluate_shot(shooter, own_team, opp_team) -> Optional[ActionCandidate]:
    goal = pitch.goal_center_for(own_team.is_home())
    dist = distance(shooter.position, goal)
    if dist > MAX_SHOOT_RANGE:
        return None

    angle = _goal_angle_deg(shooter.position, goal, own_team.is_home())
    opponents = opp_team.outfield()
    gk = opp_team.goalkeeper()

    distance_value = clamp(24.0 - dist * 0.75, -14.0, 22.0)
    angle_value = clamp((angle - 10.0) * 0.55, -8.0, 20.0)
    ability_value = (shooter.attributes.shooting - 50) / 50.0 * 12.0
    space_value = clamp(nearest_opponent_distance(shooter.position, opponents) * 2.0, 0.0, 14.0)
    pressure_value = pressure_on(shooter.position, opponents) * 16.0

    gk_difficulty = 0.0
    if gk is not None:
        gk_to_goal_gap = distance(gk.position, goal)
        gk_difficulty = clamp((gk.attributes.positioning / 100.0) * 8.0 - gk_to_goal_gap * 0.4, -4.0, 8.0)

    components = {
        "DistanceToGoal": distance_value,
        "AngleToGoal": angle_value,
        "ShootingAbility": ability_value,
        "SpaceAvailable": space_value,
        "DefenderPressure": -pressure_value,
        "GoalkeeperDifficulty": -gk_difficulty,
    }
    utility = sum(components.values())

    xg = compute_xg(dist, angle, shooter, pressure_value / 16.0, gk)

    reasons = [f"Distance {dist:.0f}m", f"Angle {angle:.0f}°"]
    reasons.append("Low pressure" if pressure_value < 4 else "Under pressure")

    cand = ActionCandidate(action=ActionType.SHOOT, utility=utility, target_position=goal.copy(),
                            components=components, reasons=reasons)
    cand.components["_xg"] = xg
    cand.components["_distance_m"] = dist
    cand.components["_angle_deg"] = angle
    return cand


def compute_xg(dist: float, angle_deg: float, shooter, pressure_0_1: float, gk) -> float:
    """A logistic-style expected-goal model (not deterministic goal/no-goal by itself)."""
    base = 0.9 / (1.0 + math.exp((dist - 11.0) / 4.2))
    angle_factor = clamp(angle_deg / 40.0, 0.15, 1.15)
    skill_factor = 0.6 + (shooter.attributes.shooting / 100.0) * 0.8
    pressure_factor = 1.0 - pressure_0_1 * 0.45
    gk_factor = 1.0
    if gk is not None:
        gk_factor = 1.0 - (gk.attributes.positioning / 100.0) * 0.25
    xg = base * angle_factor * skill_factor * pressure_factor * gk_factor
    return clamp(xg, 0.01, 0.95)


def resolve_shot_outcome(xg: float, gk, rng: random.Random) -> str:
    """Returns 'GOAL', 'SAVE', 'BLOCKED', or 'MISS'."""
    roll = rng.random()
    if roll < xg:
        return "GOAL"
    save_reflex = (gk.attributes.defending / 100.0) if gk is not None else 0.4
    on_target_prob = 0.35 + save_reflex * 0.15
    if roll < xg + on_target_prob:
        return "SAVE"
    if roll < xg + on_target_prob + 0.15:
        return "BLOCKED"
    return "MISS"
