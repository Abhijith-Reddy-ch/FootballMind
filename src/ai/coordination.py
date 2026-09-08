"""Multi-agent coordination: players act on a shared TeamSignals snapshot rather than
independently chasing the ball, producing emergent team behaviour (section 11).

Computed once per team per tick from the shared game state; every player's utility
functions then read these signals as extra inputs (e.g. "a teammate is already the
designated presser, so I should cover the passing lane instead").
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional, Set

from src.core.vector import distance
from src.game import pitch


@dataclass
class TeamSignals:
    presser_id: Optional[str] = None            # nearest player to the ball (primary presser)
    presser_ids: Set[str] = field(default_factory=set)  # every player actively closing the ball down
    cover_ids: Set[str] = field(default_factory=set)   # players covering passing lanes near the presser
    marking: Dict[str, str] = field(default_factory=dict)  # defender_id -> marked opponent_id
    counter_press: bool = False                 # possession just lost -> nearby players swarm to win it back
    support_runner_id: Optional[str] = None      # attacker told to make a run into space


def compute_signals(defending_team, attacking_team, ball, marking: Dict[str, str],
                     just_lost_possession: bool) -> TeamSignals:
    outfield = defending_team.outfield()
    if not outfield:
        return TeamSignals(marking=marking)

    tactics = defending_team.tactics
    own_goal = pitch.own_goal_center_for(defending_team.is_home())
    ball_danger_distance = distance(ball.position, own_goal)

    # pressing_intensity controls both how far up the pitch a team is willing to actively
    # press (engage_radius, measured from their own goal) and how many players commit to
    # winning the ball back at once (num_pressers) - a HIGH_PRESS team hunts the ball
    # anywhere on the pitch with 2-3 players; a DEFENSIVE team only sends extra bodies
    # when the ball is already close to their own goal.
    engage_radius = 15.0 + (tactics.pressing_intensity / 100.0) * 90.0
    num_pressers = 1 + round(tactics.pressing_intensity / 100.0 * 2)  # 1..3

    sorted_outfield = sorted(outfield, key=lambda p: distance(p.position, ball.position))
    primary_presser = sorted_outfield[0]
    if ball_danger_distance <= engage_radius:
        presser_ids = {p.id for p in sorted_outfield[:num_pressers]}
    else:
        presser_ids = {primary_presser.id}

    cover_ids = set()
    for p in outfield:
        if p.id in presser_ids:
            continue
        if distance(p.position, primary_presser.position) < 12.0:
            cover_ids.add(p.id)

    return TeamSignals(
        presser_id=primary_presser.id,
        presser_ids=presser_ids,
        cover_ids=cover_ids,
        marking=marking,
        counter_press=just_lost_possession,
    )


def pick_support_runner(attacking_team, ball) -> Optional[str]:
    """Nominate one off-ball attacker (not the carrier) to make a forward run into space,
    so not every attacker crowds the ball at once."""
    candidates = [p for p in attacking_team.outfield() if p.id != ball.owner_id]
    if not candidates:
        return None
    carrier_x = ball.position[0]
    ahead = [p for p in candidates
             if (p.position[0] > carrier_x) == attacking_team.is_home()]
    pool = ahead if ahead else candidates
    runner = max(pool, key=lambda p: p.attributes.speed)
    return runner.id
