import random

from src.core.enums import Side
from src.core.vector import v
from src.agents.team import build_team
from src.ai.tactics import preset_for, TacticalStyle
from src.ai import shooting


def make_teams():
    home = build_team("Home", Side.HOME, (255, 0, 0), preset_for(TacticalStyle.BALANCED), seed=1)
    away = build_team("Away", Side.AWAY, (0, 0, 255), preset_for(TacticalStyle.BALANCED), seed=2)
    for p in away.players:
        p.position = v(5.0, 5.0)  # keep defenders out of the way for pure distance/angle tests
    return home, away


def test_xg_decreases_with_distance():
    shooter = make_teams()[0].players[10]
    close_xg = shooting.compute_xg(dist=6.0, angle_deg=40.0, shooter=shooter, pressure_0_1=0.0, gk=None)
    far_xg = shooting.compute_xg(dist=28.0, angle_deg=40.0, shooter=shooter, pressure_0_1=0.0, gk=None)
    assert close_xg > far_xg


def test_xg_increases_with_shooting_skill():
    home, _ = make_teams()
    shooter = home.players[10]
    shooter.attributes.shooting = 30
    low_skill_xg = shooting.compute_xg(dist=15.0, angle_deg=30.0, shooter=shooter, pressure_0_1=0.0, gk=None)
    shooter.attributes.shooting = 90
    high_skill_xg = shooting.compute_xg(dist=15.0, angle_deg=30.0, shooter=shooter, pressure_0_1=0.0, gk=None)
    assert high_skill_xg > low_skill_xg


def test_xg_decreases_under_pressure():
    home, _ = make_teams()
    shooter = home.players[10]
    no_pressure = shooting.compute_xg(dist=12.0, angle_deg=35.0, shooter=shooter, pressure_0_1=0.0, gk=None)
    high_pressure = shooting.compute_xg(dist=12.0, angle_deg=35.0, shooter=shooter, pressure_0_1=1.0, gk=None)
    assert no_pressure > high_pressure


def test_goal_angle_widens_closer_to_goal():
    from src.game import pitch
    close_pos = v(2.0, pitch.WIDTH / 2)
    far_pos = v(30.0, pitch.WIDTH / 2)
    goal = pitch.home_goal_center()
    close_angle = shooting._goal_angle_deg(close_pos, goal, True)
    far_angle = shooting._goal_angle_deg(far_pos, goal, True)
    assert close_angle > far_angle
    assert 0.0 <= far_angle <= 180.0


def test_evaluate_shot_none_outside_max_range():
    home, away = make_teams()
    shooter = home.players[10]
    from src.game import pitch
    shooter.position = v(5.0, pitch.WIDTH / 2)  # far from the away goal at x=105
    assert shooting.evaluate_shot(shooter, home, away) is None


def test_resolve_shot_outcome_valid_labels():
    outcomes = {shooting.resolve_shot_outcome(0.3, None, random.Random(i)) for i in range(50)}
    assert outcomes.issubset({"GOAL", "SAVE", "BLOCKED", "MISS"})
