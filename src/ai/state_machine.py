"""Finite state machine governing each player's high-level phase of play.

Transitions are deterministic functions of game state (possession, role, coordination
signals, stamina) - never random - per section 6. Ball-skill states (DRIBBLING, PASSING,
SHOOTING, TACKLING) are set by the action executor in Match when that action is actually
taken; this module governs the broader off-ball phase (attacking shape, defending shape,
pressing, marking, recovering) that a player sits in the rest of the time.
"""
from __future__ import annotations

from typing import List, Tuple

from src.core.enums import PlayerRole, PlayerState
from src.core.vector import distance
from src.ai.coordination import TeamSignals

LOW_STAMINA_THRESHOLD = 18.0


def next_state(player, own_team, ball, signals: TeamSignals, is_own_possession: bool,
               ball_is_loose: bool) -> Tuple[PlayerState, List[str]]:
    reasons: List[str] = []

    if player.has_ball:
        return PlayerState.ATTACKING, ["In possession"]

    if player.stamina < LOW_STAMINA_THRESHOLD and not ball_is_loose:
        reasons.append(f"Stamina low ({player.stamina:.0f}) - conserving energy")
        return PlayerState.RECOVERING, reasons

    if is_own_possession:
        if signals.support_runner_id == player.id:
            reasons.append("Nominated to make a supporting run")
            return PlayerState.SUPPORT_ATTACK, reasons
        if player.role in (PlayerRole.ST, PlayerRole.WING, PlayerRole.CAM):
            reasons.append("Team in possession - advancing into attacking shape")
            return PlayerState.ATTACKING, reasons
        reasons.append("Team in possession - holding supportive shape")
        return PlayerState.POSITIONING, reasons

    # opponent has the ball, or it is loose
    if player.id in signals.presser_ids:
        if player.id == signals.presser_id:
            reasons.append("Nearest defender to the ball - closing down")
        else:
            reasons.append("Joining the press (high pressing intensity)")
        return PlayerState.PRESSING, reasons
    if player.id in signals.marking:
        marked = signals.marking[player.id]
        reasons.append(f"Marking opponent #{marked}")
        return PlayerState.MARKING, reasons
    if player.id in signals.cover_ids:
        reasons.append("Covering passing lane near presser")
        return PlayerState.DEFENDING, reasons
    reasons.append("Recovering defensive shape")
    return PlayerState.DEFENDING, reasons
