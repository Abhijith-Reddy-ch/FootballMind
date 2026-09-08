"""Defensive AI: threat assessment, marking assignment, press/tackle decisions.

    ThreatLevel = OpponentGoalDanger + BallProgression + PlayerQuality + SpaceAvailable
"""
from __future__ import annotations

import random
from typing import Dict, List, Optional

from src.core.enums import ActionType
from src.core.vector import distance, clamp
from src.ai.utility_ai import ActionCandidate
from src.ai.spatial import goal_progress, nearest_opponent_distance
from src.game import pitch


def threat_level(opponent, defending_team, ball_carrier_id: Optional[str]) -> float:
    """Higher = more dangerous opponent to leave unattended, from the defending team's goal."""
    own_goal = pitch.own_goal_center_for(defending_team.is_home())
    danger = clamp(40.0 - distance(opponent.position, own_goal) * 0.7, 0.0, 34.0)
    progression = clamp(goal_progress(opponent.position, not defending_team.is_home()) * 0.18, 0.0, 16.0)
    quality = (opponent.attributes.shooting + opponent.attributes.dribbling) / 2.0
    quality_value = (quality - 50) / 50.0 * 10.0
    space = clamp(nearest_opponent_distance(opponent.position, defending_team.outfield()) * 1.5, 0.0, 12.0)
    has_ball_bonus = 20.0 if opponent.id == ball_carrier_id else 0.0
    return danger + progression + quality_value + space + has_ball_bonus


def assign_marking(defending_team, attacking_team, ball_carrier_id: Optional[str]) -> Dict[str, str]:
    """Greedy highest-threat-first assignment of one defender per dangerous opponent.
    Returns {defender_id: opponent_id}."""
    defenders = [p for p in defending_team.outfield()]
    opponents = sorted(attacking_team.outfield(),
                        key=lambda o: threat_level(o, defending_team, ball_carrier_id), reverse=True)
    assignment: Dict[str, str] = {}
    used_defenders = set()
    for opp in opponents:
        if not defenders:
            break
        available = [d for d in defenders if d.id not in used_defenders]
        if not available:
            break
        nearest = min(available, key=lambda d: distance(d.position, opp.position))
        assignment[nearest.id] = opp.id
        used_defenders.add(nearest.id)
    return assignment


def evaluate_tackle(defender, ball_carrier, opp_team) -> ActionCandidate:
    dist = distance(defender.position, ball_carrier.position)
    closing_value = clamp(6.0 - dist, -6.0, 6.0)
    skill_edge = (defender.attributes.tackling - ball_carrier.attributes.dribbling) / 100.0 * 14.0
    fatigue_penalty = defender.fatigue_ratio() * 6.0
    components = {
        "Proximity": closing_value,
        "SkillEdge": skill_edge,
        "Fatigue": -fatigue_penalty,
    }
    utility = sum(components.values())
    return ActionCandidate(action=ActionType.TACKLE, utility=utility, target_id=ball_carrier.id,
                            components=components, reasons=["Within tackling range"] if dist < 2.0 else [])


def tackle_success_probability(defender, attacker) -> float:
    skill = (defender.attributes.tackling - attacker.attributes.dribbling) / 100.0
    fatigue_factor = 1.0 - defender.fatigue_ratio() * 0.3
    return clamp(0.45 + skill * 0.5, 0.05, 0.9) * fatigue_factor


def resolve_tackle(defender, attacker, rng: random.Random) -> str:
    """Returns 'WON' (defender wins ball), 'FOUL', or 'EVADED' (attacker keeps ball)."""
    p_win = tackle_success_probability(defender, attacker)
    roll = rng.random()
    if roll < p_win:
        return "WON"
    if roll < p_win + 0.12:
        return "FOUL"
    return "EVADED"
