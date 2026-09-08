import random

from src.core.enums import PlayerRole, Side
from src.core.vector import v
from src.agents.team import build_team
from src.ai.tactics import preset_for, TacticalStyle
from src.ai import passing


def make_teams():
    home = build_team("Home", Side.HOME, (255, 0, 0), preset_for(TacticalStyle.BALANCED), seed=1)
    away = build_team("Away", Side.AWAY, (0, 0, 255), preset_for(TacticalStyle.BALANCED), seed=2)
    return home, away


def test_open_receiver_scores_higher_than_pressured_receiver():
    home, away = make_teams()
    passer = home.players[5]
    passer.position = v(40.0, 34.0)

    open_receiver = home.players[6]
    open_receiver.position = v(55.0, 34.0)
    pressured_receiver = home.players[7]
    pressured_receiver.position = v(45.0, 40.0)

    # surround the pressured receiver with opponents
    away.players[0].position = v(45.0, 39.0)
    away.players[1].position = v(46.0, 41.0)
    for p in away.players[2:]:
        p.position = v(90.0, 5.0)  # push everyone else far away

    open_eval = passing.evaluate_pass(passer, open_receiver, home, away, home.tactics)
    pressured_eval = passing.evaluate_pass(passer, pressured_receiver, home, away, home.tactics)

    assert open_eval.utility > pressured_eval.utility


def test_interception_risk_increases_with_defenders_in_lane():
    home, away = make_teams()
    passer_pos = v(30.0, 34.0)
    receiver_pos = v(60.0, 34.0)
    for p in away.players:
        p.position = v(90.0, 5.0)

    risk_far = passing.interception_risk_pct(
        type("P", (), {"position": passer_pos})(), type("R", (), {"position": receiver_pos})(),
        away.outfield())

    away.players[1].position = v(45.0, 34.0)  # directly on the passing lane (players[0] is the GK)
    risk_near = passing.interception_risk_pct(
        type("P", (), {"position": passer_pos})(), type("R", (), {"position": receiver_pos})(),
        away.outfield())

    assert risk_near > risk_far


def test_best_pass_returns_highest_utility_candidate():
    home, away = make_teams()
    passer = home.players[5]
    passer.position = v(40.0, 34.0)
    for i, p in enumerate(home.players):
        if p.id == passer.id:
            continue
        p.position = v(50.0 + i, 34.0)
    for p in away.players:
        p.position = v(5.0, 5.0)

    candidates = [passing.evaluate_pass(passer, t, home, away, home.tactics)
                  for t in passing.find_teammates_in_range(passer, home.players)]
    best = passing.best_pass(passer, home, away)
    assert best is not None
    assert best.utility == max(c.utility for c in candidates)


def test_resolve_pass_outcome_is_deterministic_given_seed():
    home, away = make_teams()
    passer = home.players[5]
    receiver = home.players[6]
    passer.position = v(40.0, 34.0)
    receiver.position = v(50.0, 34.0)
    for p in away.players:
        p.position = v(5.0, 5.0)

    r1 = random.Random(7)
    r2 = random.Random(7)
    out1 = passing.resolve_pass_outcome(passer, receiver, 10.0, away, r1)
    out2 = passing.resolve_pass_outcome(passer, receiver, 10.0, away, r2)
    assert out1 == out2
    assert out1 in ("COMPLETE", "INTERCEPTED", "OUT_OF_PLAY")
