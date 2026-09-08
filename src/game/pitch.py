"""Pitch geometry constants and spatial helpers (105m x 68m regulation-scale pitch)."""
from __future__ import annotations

from src.core.vector import Vec2, v, clamp

LENGTH = 105.0   # meters, x-axis: 0 (home goal line) .. LENGTH (away goal line)
WIDTH = 68.0     # meters, y-axis: 0 .. WIDTH
GOAL_WIDTH = 7.32
GOAL_Y_MIN = WIDTH / 2 - GOAL_WIDTH / 2
GOAL_Y_MAX = WIDTH / 2 + GOAL_WIDTH / 2
CENTER = v(LENGTH / 2, WIDTH / 2)

PENALTY_AREA_DEPTH = 16.5
PENALTY_AREA_WIDTH = 40.32
PENALTY_Y_MIN = WIDTH / 2 - PENALTY_AREA_WIDTH / 2
PENALTY_Y_MAX = WIDTH / 2 + PENALTY_AREA_WIDTH / 2

GOAL_AREA_DEPTH = 5.5
GOAL_AREA_WIDTH = 18.32
GOAL_AREA_Y_MIN = WIDTH / 2 - GOAL_AREA_WIDTH / 2
GOAL_AREA_Y_MAX = WIDTH / 2 + GOAL_AREA_WIDTH / 2

CENTER_CIRCLE_RADIUS = 9.15


def home_goal_center() -> Vec2:
    return v(0.0, WIDTH / 2)


def away_goal_center() -> Vec2:
    return v(LENGTH, WIDTH / 2)


def goal_center_for(attacking_side_is_home: bool) -> Vec2:
    """The goal a team with the given side is attacking towards."""
    return away_goal_center() if attacking_side_is_home else home_goal_center()


def own_goal_center_for(side_is_home: bool) -> Vec2:
    return home_goal_center() if side_is_home else away_goal_center()


def clamp_to_pitch(pos: Vec2) -> Vec2:
    return v(clamp(pos[0], 0.0, LENGTH), clamp(pos[1], 0.0, WIDTH))


def is_in_penalty_area(pos: Vec2, home_side: bool) -> bool:
    if home_side:
        return pos[0] <= PENALTY_AREA_DEPTH and PENALTY_Y_MIN <= pos[1] <= PENALTY_Y_MAX
    return pos[0] >= LENGTH - PENALTY_AREA_DEPTH and PENALTY_Y_MIN <= pos[1] <= PENALTY_Y_MAX


def is_out_of_bounds(pos: Vec2) -> bool:
    return not (0.0 <= pos[0] <= LENGTH and 0.0 <= pos[1] <= WIDTH)


def is_goal(pos: Vec2, home_side_goal: bool) -> bool:
    """True if pos has crossed the given goal's line within the goal mouth."""
    x = pos[0]
    within_y = GOAL_Y_MIN <= pos[1] <= GOAL_Y_MAX
    if home_side_goal:
        return x <= 0.0 and within_y
    return x >= LENGTH and within_y
