"""Spatial pathfinding: A* over a coarse pitch grid, used only when a straight line to a
target is congested with opponents; otherwise players steer directly (cheap, used every
tick). This keeps A* off the hot path per section 17's guidance.
"""
from __future__ import annotations

import heapq
from typing import List, Optional, Tuple

from src.core.vector import Vec2, v, distance, point_segment_distance
from src.game import pitch

CELL_SIZE = 3.5  # meters per grid cell
GRID_W = int(pitch.LENGTH // CELL_SIZE) + 1
GRID_H = int(pitch.WIDTH // CELL_SIZE) + 1


def _to_cell(pos: Vec2) -> Tuple[int, int]:
    return int(pos[0] // CELL_SIZE), int(pos[1] // CELL_SIZE)


def _to_world(cell: Tuple[int, int]) -> Vec2:
    return v((cell[0] + 0.5) * CELL_SIZE, (cell[1] + 0.5) * CELL_SIZE)


def is_congested(start: Vec2, goal: Vec2, obstacles: List, clearance: float = 2.0) -> bool:
    """True if 2+ obstacles sit close enough to the direct line to plausibly block it."""
    if distance(start, goal) < 3.0:
        return False
    blockers = sum(1 for o in obstacles if point_segment_distance(o.position, start, goal) < clearance)
    return blockers >= 2


def astar(start: Vec2, goal: Vec2, obstacles: List, obstacle_radius: float = 2.2
          ) -> Optional[List[Vec2]]:
    """Grid A* avoiding cells within `obstacle_radius` of any obstacle position."""
    start_cell, goal_cell = _to_cell(start), _to_cell(goal)
    blocked = set()
    for o in obstacles:
        cx, cy = _to_cell(o.position)
        r = int(obstacle_radius // CELL_SIZE) + 1
        for dx in range(-r, r + 1):
            for dy in range(-r, r + 1):
                cell = (cx + dx, cy + dy)
                if distance(_to_world(cell), o.position) <= obstacle_radius:
                    blocked.add(cell)
    blocked.discard(start_cell)
    blocked.discard(goal_cell)

    def neighbors(c):
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)):
            n = (c[0] + dx, c[1] + dy)
            if 0 <= n[0] < GRID_W and 0 <= n[1] < GRID_H and n not in blocked:
                yield n, (1.414 if dx and dy else 1.0)

    def heuristic(c):
        return ((c[0] - goal_cell[0]) ** 2 + (c[1] - goal_cell[1]) ** 2) ** 0.5

    open_heap = [(heuristic(start_cell), 0.0, start_cell)]
    came_from = {}
    g_score = {start_cell: 0.0}
    visited = set()

    while open_heap:
        _, g, current = heapq.heappop(open_heap)
        if current in visited:
            continue
        visited.add(current)
        if current == goal_cell:
            path_cells = [current]
            while current in came_from:
                current = came_from[current]
                path_cells.append(current)
            path_cells.reverse()
            return [_to_world(c) for c in path_cells]
        for n, cost in neighbors(current):
            tentative = g + cost
            if tentative < g_score.get(n, float("inf")):
                g_score[n] = tentative
                came_from[n] = current
                heapq.heappush(open_heap, (tentative + heuristic(n), tentative, n))
    return None  # no path found (fully boxed in) -> caller falls back to direct steering


class PathCache:
    """Per-player path cache: only recompute A* when the target moved a lot or the cached
    path has been exhausted, avoiding per-frame pathfinding cost."""

    def __init__(self):
        self._cache: dict[str, Tuple[Vec2, List[Vec2], int]] = {}

    def get_next_waypoint(self, player_id: str, current_pos: Vec2, target: Vec2,
                           obstacles: List, tick: int, recompute_every: int = 15) -> Vec2:
        cached = self._cache.get(player_id)
        needs_recompute = cached is None or distance(cached[0], target) > 3.0 or \
            (tick - cached[2]) > recompute_every
        if needs_recompute:
            if is_congested(current_pos, target, obstacles):
                path = astar(current_pos, target, obstacles)
            else:
                path = None
            self._cache[player_id] = (target.copy(), path or [], tick)
            cached = self._cache[player_id]

        path = cached[1]
        if not path:
            return target
        while len(path) > 1 and distance(current_pos, path[0]) < CELL_SIZE * 0.6:
            path.pop(0)
        return path[0]
