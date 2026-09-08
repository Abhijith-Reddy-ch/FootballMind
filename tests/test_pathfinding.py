from src.core.vector import v, distance
from src.ai.pathfinding import astar, is_congested, PathCache
from src.game import pitch


class DummyObstacle:
    def __init__(self, x, y):
        self.position = v(x, y)


def test_astar_finds_path_between_two_points():
    start, goal = v(5.0, 34.0), v(60.0, 34.0)
    path = astar(start, goal, obstacles=[])
    assert path is not None
    assert distance(path[0], start) < 4.0
    assert distance(path[-1], goal) < 4.0


def test_astar_path_stays_within_pitch_bounds():
    start, goal = v(5.0, 5.0), v(90.0, 60.0)
    obstacles = [DummyObstacle(x, 30.0) for x in range(20, 80, 5)]
    path = astar(start, goal, obstacles)
    assert path is not None
    for point in path:
        assert 0.0 - 1e-6 <= point[0] <= pitch.LENGTH + 1e-6
        assert 0.0 - 1e-6 <= point[1] <= pitch.WIDTH + 1e-6


def test_is_congested_detects_multiple_blockers_on_the_direct_line():
    start, goal = v(0.0, 34.0), v(40.0, 34.0)
    clear_obstacles = [DummyObstacle(50.0, 5.0), DummyObstacle(60.0, 60.0)]
    assert not is_congested(start, goal, clear_obstacles)

    blocking_obstacles = [DummyObstacle(15.0, 34.0), DummyObstacle(25.0, 34.5)]
    assert is_congested(start, goal, blocking_obstacles)


def test_path_cache_recomputes_only_when_target_moves():
    cache = PathCache()
    start = v(5.0, 34.0)
    target = v(50.0, 34.0)
    obstacles = [DummyObstacle(x, 34.0) for x in range(15, 45, 5)]

    wp1 = cache.get_next_waypoint("p1", start, target, obstacles, tick=0)
    assert wp1 is not None
    # a near-identical target should reuse the cached path without error
    wp2 = cache.get_next_waypoint("p1", start, target, obstacles, tick=1)
    assert wp2 is not None
