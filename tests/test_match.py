import random

from src.core.enums import MatchPhase, Side
from src.core.vector import v
from src.agents.team import build_team
from src.ai.tactics import preset_for, TacticalStyle
from src.game import match as match_module
from src.game.match import Match
from src.game import pitch


def make_match(seed=42):
    home = build_team("Home", Side.HOME, (255, 0, 0), preset_for(TacticalStyle.BALANCED), seed=1)
    away = build_team("Away", Side.AWAY, (0, 0, 255), preset_for(TacticalStyle.BALANCED), seed=2)
    return Match(home=home, away=away, seed=seed)


def test_kickoff_places_ball_and_players_sensibly():
    m = make_match()
    assert (m.ball.position == pitch.CENTER).all()
    assert m.ball.owner_id is not None
    for p in m.home.players + m.away.players:
        assert 0.0 <= p.position[0] <= pitch.LENGTH
        assert 0.0 <= p.position[1] <= pitch.WIDTH


def test_tick_advances_clock_and_keeps_players_in_bounds():
    m = make_match()
    for _ in range(300):
        m.tick(1 / 20)
    assert m.minute > 0
    for p in m.home.players + m.away.players:
        assert 0.0 <= p.position[0] <= pitch.LENGTH
        assert 0.0 <= p.position[1] <= pitch.WIDTH


def test_halftime_and_second_half_transition():
    m = make_match()
    for _ in range(20000):
        m.tick(1 / 10)
        if m.phase == MatchPhase.HALFTIME:
            break
    assert m.phase == MatchPhase.HALFTIME
    m.start_second_half()
    assert m.phase == MatchPhase.SECOND_HALF


def test_goal_forces_kickoff_reset_and_increments_score(monkeypatch):
    m = make_match()
    shooter = m.home.players[10]
    shooter.position = v(pitch.LENGTH - 3.0, pitch.WIDTH / 2)
    m.ball.attach(shooter.id, shooter.position)
    shooter.has_ball = True

    monkeypatch.setattr(match_module, "resolve_shot_outcome", lambda xg, gk, rng: "GOAL")

    from src.ai.utility_ai import ActionCandidate
    from src.core.enums import ActionType
    candidate = ActionCandidate(action=ActionType.SHOOT, utility=99.0,
                                 target_position=pitch.away_goal_center(),
                                 components={"_xg": 0.9})
    m._execute_shot(shooter, candidate, m.home, m.away)

    scored = False
    for _ in range(200):
        m.tick(1 / 20)
        if m.home.score == 1:
            scored = True
            break
    assert scored
    # after the goal, kickoff resets the ball to the centre spot
    assert (m.ball.position == pitch.CENTER).all()


def test_game_state_snapshot_is_json_serializable():
    from src.game.state import GameState
    m = make_match()
    for _ in range(50):
        m.tick(1 / 20)
    state = GameState.from_match(m)
    payload = state.to_json()
    assert isinstance(payload, str)
    import json
    parsed = json.loads(payload)
    assert parsed["score"]["HOME"] == 0
    assert len(parsed["players"]) == 22
    assert "ball_position" in parsed and len(parsed["ball_position"]) == 2


def test_deterministic_with_fixed_seed():
    m1 = make_match(seed=123)
    m2 = make_match(seed=123)
    for _ in range(500):
        m1.tick(1 / 20)
        m2.tick(1 / 20)
    assert m1.home.score == m2.home.score
    assert m1.away.score == m2.away.score
    for p1, p2 in zip(m1.home.players, m2.home.players):
        assert abs(p1.position[0] - p2.position[0]) < 1e-6
        assert abs(p1.position[1] - p2.position[1]) < 1e-6
