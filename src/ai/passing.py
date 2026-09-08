"""Passing AI: candidate selection, utility scoring and probabilistic outcome resolution.

    PassScore = PassingLaneQuality + ReceiverPosition + DistanceAdvantage + TacticalValue
                - InterceptionRisk - OpponentPressure
"""
from __future__ import annotations

import random
from typing import List, Optional

from src.core.enums import ActionType
from src.core.vector import distance, point_segment_distance, clamp
from src.ai.utility_ai import ActionCandidate
from src.ai.spatial import attacking_dir, goal_progress, nearest_opponent_distance, pressure_on
from src.ai.tactics import TeamTactics

MAX_PASS_RANGE = 42.0


def find_teammates_in_range(passer, teammates: List, max_range: float = MAX_PASS_RANGE) -> List:
    return [t for t in teammates if t.id != passer.id and t.on_pitch
            and distance(passer.position, t.position) <= max_range]


def interception_risk_pct(passer, receiver, opponents: List) -> float:
    """Estimated % chance an opponent cuts the pass out, from how close any opponent gets
    to the straight-line passing lane."""
    if not opponents:
        return 4.0
    min_lane_dist = min(point_segment_distance(o.position, passer.position, receiver.position)
                         for o in opponents)
    risk = clamp(52.0 - min_lane_dist * 7.5, 3.0, 88.0)
    return risk


def evaluate_pass(passer, receiver, own_team, opp_team, tactics: TeamTactics) -> ActionCandidate:
    opponents = opp_team.outfield() + ([opp_team.goalkeeper()] if opp_team.goalkeeper() else [])
    side_is_home = own_team.is_home()

    lane_risk = interception_risk_pct(passer, receiver, opponents)
    lane_quality = clamp(30.0 - lane_risk * 0.32, -10.0, 26.0)

    receiver_space = clamp(nearest_opponent_distance(receiver.position, opponents) * 2.2, 0.0, 22.0)

    progress = (goal_progress(receiver.position, side_is_home)
                - goal_progress(passer.position, side_is_home))
    distance_advantage = clamp(progress * 0.55, -16.0, 24.0)

    forward_bonus = 6.0 if progress > 4.0 else (0.0 if progress > -4.0 else -6.0)
    risk_appetite = (tactics.passing_risk - 50) / 50.0  # -1..1
    tactical_value = forward_bonus + risk_appetite * clamp(progress * 0.15, -6, 6)

    pass_dist = distance(passer.position, receiver.position)
    range_penalty = clamp((pass_dist - 25.0) * 0.6, 0.0, 14.0)

    passer_pressure = pressure_on(passer.position, opponents) * 14.0

    skill_bonus = (passer.attributes.passing - 50) / 50.0 * 8.0 + (receiver.attributes.vision - 50) / 50.0 * 3.0

    components = {
        "PassingLaneQuality": lane_quality,
        "ReceiverSpace": receiver_space,
        "DistanceAdvantage": distance_advantage,
        "TacticalValue": tactical_value,
        "SkillBonus": skill_bonus,
        "InterceptionRisk": -lane_risk * 0.48,
        "OpponentPressure": -passer_pressure,
        "RangePenalty": -range_penalty,
    }
    utility = sum(components.values())

    reasons = []
    if lane_risk < 20:
        reasons.append("High-quality passing lane")
    elif lane_risk > 55:
        reasons.append("Contested passing lane")
    if receiver_space > 12:
        reasons.append("Receiver in space")
    if progress > 6:
        reasons.append("Strong tactical progression")
    elif progress < -6:
        reasons.append("Backward safety pass")
    if passer_pressure > 0.4 * 14:
        reasons.append("Passer under pressure")

    cand = ActionCandidate(action=ActionType.PASS, utility=utility, target_id=receiver.id,
                            target_position=receiver.position.copy(), components=components,
                            reasons=reasons)
    cand.components["_interception_risk_pct"] = lane_risk
    return cand


def best_pass(passer, own_team, opp_team) -> Optional[ActionCandidate]:
    teammates = find_teammates_in_range(passer, own_team.players)
    if not teammates:
        return None
    candidates = [evaluate_pass(passer, t, own_team, opp_team, own_team.tactics) for t in teammates]
    return max(candidates, key=lambda c: c.utility)


def evaluate_cross(carrier, own_team, opp_team) -> Optional[ActionCandidate]:
    """A cross is only considered from a wide attacking channel, targeting a central
    attacker making a run into the box - modelled as a higher-risk variant of a pass."""
    from src.core.enums import PlayerRole, ActionType as _AT
    from src.game import pitch as _pitch

    side_is_home = own_team.is_home()
    x_frac = goal_progress(carrier.position, side_is_home) / _pitch.LENGTH
    wide = abs(carrier.position[1] - _pitch.WIDTH / 2) > 15.0
    if x_frac < 0.72 or not wide:
        return None

    targets = [t for t in own_team.players if t.role in (PlayerRole.ST, PlayerRole.CAM, PlayerRole.WING)
               and t.id != carrier.id and t.on_pitch]
    if not targets:
        return None
    box_goal = _pitch.goal_center_for(side_is_home)
    target = min(targets, key=lambda t: distance(t.position, box_goal))

    base = evaluate_pass(carrier, target, own_team, opp_team, own_team.tactics)
    base.action = _AT.CROSS
    base.components["CrossRiskAdjustment"] = -8.0
    base.utility -= 8.0
    base.reasons.append("Whipped cross into the box")
    return base


def evaluate_clear(carrier, own_team, opp_team) -> Optional[ActionCandidate]:
    """A defender under pressure deep in their own third clears the ball long, prioritising
    safety (removing danger) over retaining possession."""
    from src.core.enums import PlayerRole, ActionType as _AT

    side_is_home = own_team.is_home()
    if carrier.role not in (PlayerRole.GK, PlayerRole.CB, PlayerRole.FB):
        return None
    danger_zone = goal_progress(carrier.position, side_is_home) < 24.0
    if not danger_zone:
        return None
    opponents = opp_team.outfield()
    pressure = pressure_on(carrier.position, opponents)
    if pressure < 0.25:
        return None

    urgency = pressure * 20.0 + (24.0 - goal_progress(carrier.position, side_is_home)) * 0.6
    components = {"DangerZone": urgency, "SafetyFirst": 10.0}
    target = carrier.position.copy()
    target[0] += attacking_dir(side_is_home) * 35.0
    cand = ActionCandidate(action=_AT.CLEAR_BALL, utility=sum(components.values()),
                            target_position=target, components=components,
                            reasons=["Clearing danger under pressure"])
    return cand


def resolve_pass_outcome(passer, receiver, interception_risk_pct: float, opp_team,
                          rng: random.Random) -> str:
    """Returns 'COMPLETE', 'INTERCEPTED', or 'OUT_OF_PLAY'.

    Success probability blends passer skill, distance and the pre-computed lane risk so a
    pass is never a scripted guarantee - a good pass by a poor passer can still fail.
    """
    dist = distance(passer.position, receiver.position)
    skill = passer.attributes.passing / 100.0
    distance_penalty = clamp(dist / 70.0, 0.0, 0.35)
    base_success = 0.68 + skill * 0.28 - distance_penalty
    success_prob = clamp(base_success - (interception_risk_pct / 100.0) * 0.42, 0.05, 0.97)
    roll = rng.random()
    if roll < success_prob:
        return "COMPLETE"
    if roll < success_prob + (interception_risk_pct / 100.0) * 0.6:
        return "INTERCEPTED"
    return "OUT_OF_PLAY"
