"""Goalkeeper-specific behaviour: arc positioning relative to the ball, and distribution
after a save/pickup (short pass if a safe option exists, otherwise a long clearance)."""
from __future__ import annotations

from src.core.vector import Vec2, v, distance, normalize, clamp
from src.game import pitch
from src.ai.passing import best_pass


def gk_home_position(gk, ball_pos: Vec2, side_is_home: bool) -> Vec2:
    """Keep the keeper on an arc between the ball and the goal centre, biased toward the
    near post line, never straying far off the goal line."""
    goal = pitch.own_goal_center_for(side_is_home)
    to_ball = ball_pos - goal
    dist = float((to_ball ** 2).sum() ** 0.5)
    max_advance = 11.0
    advance = clamp(dist * 0.12, 0.5, max_advance)
    direction = normalize(to_ball) if dist > 1e-3 else v(1.0 if side_is_home else -1.0, 0.0)
    pos = goal + direction * advance
    y = clamp(pos[1], pitch.GOAL_Y_MIN - 3, pitch.GOAL_Y_MAX + 3)
    x = clamp(pos[0], 0.5, pitch.LENGTH - 0.5)
    return v(x, y)


def choose_distribution(gk, own_team, opp_team):
    """After the keeper has the ball: short pass to the best available teammate if one
    scores reasonably, else a long clearance upfield."""
    pass_option = best_pass(gk, own_team, opp_team)
    if pass_option is not None and pass_option.utility > 10:
        return pass_option
    return None
