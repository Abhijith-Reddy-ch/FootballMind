"""Regression tests for the pressing_intensity/tempo wiring bug: these tactical dials
were being set by the menu/manager/dynamic-adaptation but never actually consulted by
any decision function, so several manager commands had no visible effect in play."""
from dataclasses import replace

from src.core.enums import Mentality, Side, TacticalStyle
from src.core.vector import v
from src.agents.team import build_team
from src.ai.tactics import preset_for
from src.ai.coordination import compute_signals
from src.agents.manager import ManagerController
from src.game.ball import Ball


def make_teams(pressing_intensity=50):
    tactics = replace(preset_for(TacticalStyle.BALANCED), pressing_intensity=pressing_intensity)
    home = build_team("Home", Side.HOME, (255, 0, 0), tactics, seed=1)
    away = build_team("Away", Side.AWAY, (0, 0, 255), preset_for(TacticalStyle.BALANCED), seed=2)
    return home, away


def test_higher_pressing_intensity_commits_more_players():
    ball = Ball(position=v(52.5, 34.0))

    low_press_home, away = make_teams(pressing_intensity=0)
    for p in low_press_home.outfield():
        p.position = v(45.0, 34.0)  # all bunched near the ball -> only intensity gates the count
    low_signals = compute_signals(low_press_home, away, ball, marking={}, just_lost_possession=False)

    high_press_home, away2 = make_teams(pressing_intensity=100)
    for p in high_press_home.outfield():
        p.position = v(45.0, 34.0)
    high_signals = compute_signals(high_press_home, away2, ball, marking={}, just_lost_possession=False)

    assert len(high_signals.presser_ids) > len(low_signals.presser_ids)


def test_low_pressing_team_does_not_engage_far_from_own_goal():
    # Home defends the goal at x=0; put the ball deep in the away half (x~95) where a
    # low-pressing team should NOT commit multiple players, but a high-pressing team should.
    ball = Ball(position=v(95.0, 34.0))

    low_press_home, away = make_teams(pressing_intensity=5)
    for p in low_press_home.outfield():
        p.position = v(90.0, 34.0)
    low_signals = compute_signals(low_press_home, away, ball, marking={}, just_lost_possession=False)
    assert len(low_signals.presser_ids) == 1

    high_press_home, away2 = make_teams(pressing_intensity=100)
    for p in high_press_home.outfield():
        p.position = v(90.0, 34.0)
    high_signals = compute_signals(high_press_home, away2, ball, marking={}, just_lost_possession=False)
    assert len(high_signals.presser_ids) > 1


def test_manager_attack_command_moves_numeric_dials_not_just_mentality():
    home, _ = make_teams(pressing_intensity=50)
    manager = ManagerController(home)
    before = home.tactics
    manager.quick_command("ATTACK")
    after = home.tactics

    assert after.mentality == Mentality.ATTACK
    assert after.pressing_intensity > before.pressing_intensity
    assert after.defensive_line > before.defensive_line
    assert after.passing_risk > before.passing_risk
    assert after.tempo > before.tempo


def test_manager_defend_command_moves_numeric_dials_down():
    home, _ = make_teams(pressing_intensity=50)
    manager = ManagerController(home)
    before = home.tactics
    manager.quick_command("DEFEND")
    after = home.tactics

    assert after.mentality == Mentality.DEFEND
    assert after.pressing_intensity < before.pressing_intensity
    assert after.defensive_line < before.defensive_line


def test_manager_high_press_command_actually_changes_pressing_behaviour():
    home, away = make_teams(pressing_intensity=30)
    manager = ManagerController(home)
    ball = Ball(position=v(95.0, 34.0))
    for p in home.outfield():
        p.position = v(90.0, 34.0)

    before_signals = compute_signals(home, away, ball, marking={}, just_lost_possession=False)
    manager.quick_command("HIGH_PRESS")
    after_signals = compute_signals(home, away, ball, marking={}, just_lost_possession=False)

    assert home.tactics.style == TacticalStyle.HIGH_PRESS
    assert len(after_signals.presser_ids) >= len(before_signals.presser_ids)
