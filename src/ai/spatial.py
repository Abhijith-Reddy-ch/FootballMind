"""Small shared spatial helpers used by several AI evaluators (avoids duplication)."""
from __future__ import annotations

from typing import List

from src.core.vector import Vec2, distance
from src.game import pitch


def attacking_dir(side_is_home: bool) -> float:
    """+1 if attacking towards x=LENGTH (home), -1 if attacking towards x=0 (away)."""
    return 1.0 if side_is_home else -1.0


def goal_progress(pos: Vec2, side_is_home: bool) -> float:
    """Meters advanced towards the opponent's goal (0 at own goal line, LENGTH at opponent's)."""
    return pos[0] if side_is_home else (pitch.LENGTH - pos[0])


def nearest_opponent_distance(pos: Vec2, opponents: List) -> float:
    if not opponents:
        return 999.0
    return min(distance(pos, o.position) for o in opponents)


def pressure_on(pos: Vec2, opponents: List, radius: float = 6.0) -> float:
    """0..1 pressure score: how many/close opponents are converging on this point."""
    score = 0.0
    for o in opponents:
        d = distance(pos, o.position)
        if d < radius:
            score += (radius - d) / radius
    return min(1.0, score / 2.0)
