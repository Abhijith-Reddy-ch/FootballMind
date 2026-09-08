from src.core.enums import Side
from src.core.vector import v
from src.agents.team import build_team
from src.ai.tactics import preset_for, TacticalStyle
from src.ai import defending


def make_teams():
    home = build_team("Home", Side.HOME, (255, 0, 0), preset_for(TacticalStyle.BALANCED), seed=1)
    away = build_team("Away", Side.AWAY, (0, 0, 255), preset_for(TacticalStyle.BALANCED), seed=2)
    return home, away


def test_ball_carrier_has_higher_threat_than_non_carrier():
    home, away = make_teams()
    opp1, opp2 = away.players[8], away.players[9]
    opp1.position = v(90.0, 34.0)
    opp2.position = v(90.0, 40.0)
    t_carrier = defending.threat_level(opp1, home, ball_carrier_id=opp1.id)
    t_other = defending.threat_level(opp2, home, ball_carrier_id=opp1.id)
    assert t_carrier > t_other


def test_threat_increases_closer_to_defended_goal():
    home, away = make_teams()
    close_opp = away.players[8]
    far_opp = away.players[9]
    close_opp.position = v(8.0, 34.0)  # near home's own goal at x=0
    far_opp.position = v(55.0, 34.0)
    close_threat = defending.threat_level(close_opp, home, ball_carrier_id=None)
    far_threat = defending.threat_level(far_opp, home, ball_carrier_id=None)
    assert close_threat > far_threat


def test_assign_marking_gives_each_defender_at_most_one_opponent():
    home, away = make_teams()
    assignment = defending.assign_marking(home, away, ball_carrier_id=None)
    defenders = list(assignment.keys())
    assert len(defenders) == len(set(defenders))
    assert all(home.by_id(d) is not None for d in defenders)
    assert all(away.by_id(o) is not None for o in assignment.values())


def test_tackle_success_probability_favours_better_tackler():
    home, away = make_teams()
    defender = home.players[2]
    attacker = away.players[9]
    defender.attributes.tackling = 90
    attacker.attributes.dribbling = 30
    strong_defender_prob = defending.tackle_success_probability(defender, attacker)

    defender.attributes.tackling = 30
    attacker.attributes.dribbling = 90
    weak_defender_prob = defending.tackle_success_probability(defender, attacker)

    assert strong_defender_prob > weak_defender_prob
