from src.core.enums import PlayerState, Side
from src.core.vector import v
from src.agents.team import build_team
from src.ai.tactics import preset_for, TacticalStyle
from src.ai.coordination import TeamSignals
from src.ai.state_machine import next_state, LOW_STAMINA_THRESHOLD
from src.game.ball import Ball


def make_team():
    return build_team("Home", Side.HOME, (255, 0, 0), preset_for(TacticalStyle.BALANCED), seed=1)


def test_presser_transitions_to_pressing():
    team = make_team()
    player = team.players[3]
    ball = Ball(position=v(10.0, 10.0))
    signals = TeamSignals(presser_id=player.id, presser_ids={player.id})
    state, reasons = next_state(player, team, ball, signals, is_own_possession=False, ball_is_loose=False)
    assert state == PlayerState.PRESSING
    assert reasons


def test_teammate_possession_triggers_support_or_attacking():
    team = make_team()
    player = team.players[8]  # attacking-minded slot
    ball = Ball()
    signals = TeamSignals()
    state, _ = next_state(player, team, ball, signals, is_own_possession=True, ball_is_loose=False)
    assert state in (PlayerState.SUPPORT_ATTACK, PlayerState.ATTACKING, PlayerState.POSITIONING)


def test_low_stamina_forces_recovering():
    team = make_team()
    player = team.players[4]
    player.stamina = LOW_STAMINA_THRESHOLD - 5
    ball = Ball()
    signals = TeamSignals()
    state, reasons = next_state(player, team, ball, signals, is_own_possession=False, ball_is_loose=False)
    assert state == PlayerState.RECOVERING
    assert "Stamina" in reasons[0]


def test_ball_carrier_is_attacking():
    team = make_team()
    player = team.players[2]
    player.has_ball = True
    ball = Ball()
    signals = TeamSignals()
    state, _ = next_state(player, team, ball, signals, is_own_possession=True, ball_is_loose=False)
    assert state == PlayerState.ATTACKING


def test_marked_defender_transitions_to_marking():
    team = make_team()
    player = team.players[2]
    ball = Ball()
    signals = TeamSignals(marking={player.id: "opponent_x"})
    state, reasons = next_state(player, team, ball, signals, is_own_possession=False, ball_is_loose=False)
    assert state == PlayerState.MARKING
    assert any("Marking" in r for r in reasons)
