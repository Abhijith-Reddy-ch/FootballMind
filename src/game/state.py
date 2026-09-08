"""Structured, serializable snapshot of the match state (section 18).

Live AI decisions read directly from `Match`/`Team`/`Player` objects each tick for
performance (22 agents x several evaluators/tick would otherwise re-serialize the whole
match every frame for no benefit) - but the project explicitly calls for a structured
GameState representation that *could* drive decisions and can be persisted/inspected
independently of the live object graph. `GameState.from_match` builds exactly that: a
plain-data snapshot (dicts/lists/floats/strings) suitable for `json.dumps`, used by
save/replay tooling, debugging, and anything that wants match state without importing
the simulation classes.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Dict, List, Optional


@dataclass
class PlayerSnapshot:
    id: str
    number: int
    role: str
    side: str
    position: List[float]
    state: str
    stamina: float
    has_ball: bool


@dataclass
class GameState:
    ball_position: List[float]
    ball_velocity: List[float]
    possession_team: Optional[str]
    player_positions: Dict[str, List[float]]
    player_states: Dict[str, str]
    formations: Dict[str, str]
    score: Dict[str, int]
    time_minutes: float
    stamina: Dict[str, float]
    cards: Dict[str, int]
    tactical_settings: Dict[str, dict]
    players: List[PlayerSnapshot] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict())

    @staticmethod
    def from_match(match) -> "GameState":
        all_players = match.home.players + match.away.players
        owner = match.find_player(match.ball.owner_id) if match.ball.owner_id else None

        return GameState(
            ball_position=[float(match.ball.position[0]), float(match.ball.position[1])],
            ball_velocity=[float(match.ball.velocity[0]), float(match.ball.velocity[1])],
            possession_team=owner.side.value if owner else None,
            player_positions={p.id: [float(p.position[0]), float(p.position[1])] for p in all_players},
            player_states={p.id: p.state.name for p in all_players},
            formations={"HOME": match.home.tactics.formation, "AWAY": match.away.tactics.formation},
            score={"HOME": match.home.score, "AWAY": match.away.score},
            time_minutes=match.minute,
            stamina={p.id: p.stamina for p in all_players},
            cards={p.id: p.yellow_cards for p in all_players if p.yellow_cards},
            tactical_settings={
                "HOME": {"style": match.home.tactics.style.value, "mentality": match.home.tactics.mentality.value,
                         "pressing_intensity": match.home.tactics.pressing_intensity,
                         "defensive_line": match.home.tactics.defensive_line,
                         "passing_risk": match.home.tactics.passing_risk},
                "AWAY": {"style": match.away.tactics.style.value, "mentality": match.away.tactics.mentality.value,
                         "pressing_intensity": match.away.tactics.pressing_intensity,
                         "defensive_line": match.away.tactics.defensive_line,
                         "passing_risk": match.away.tactics.passing_risk},
            },
            players=[PlayerSnapshot(id=p.id, number=p.number, role=p.role.value, side=p.side.value,
                                     position=[float(p.position[0]), float(p.position[1])],
                                     state=p.state.name, stamina=p.stamina, has_ball=p.has_ball)
                     for p in all_players],
        )
