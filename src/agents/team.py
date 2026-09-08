"""Team: roster + tactical controller (AI Level 2) shared by all of its player agents."""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from src.core.enums import AILevel, PlayerRole, Side
from src.ai.positioning import slots_for
from src.ai.tactics import TeamTactics, preset_for
from src.agents.player import Player, generate_attributes

DEFAULT_NAMES = [
    "Carter", "Silva", "Novak", "Rossi", "Dubois", "Muller", "Kowalski", "Tanaka",
    "Okafor", "Santos", "Ivanov", "Garcia", "Larsen", "Costa", "Haddad", "Bergström",
]


@dataclass
class TeamStats:
    passes_attempted: int = 0
    passes_completed: int = 0
    shots: int = 0
    shots_on_target: int = 0
    goals: int = 0
    tackles: int = 0
    tackles_won: int = 0
    interceptions: int = 0
    fouls: int = 0
    possession_ticks: int = 0
    adaptation_events: int = 0


@dataclass
class Team:
    name: str
    side: Side
    color: tuple
    tactics: TeamTactics
    players: List[Player] = field(default_factory=list)
    subs: List[Player] = field(default_factory=list)
    score: int = 0
    stats: TeamStats = field(default_factory=TeamStats)
    ai_level: AILevel = AILevel.FULL_MULTI_AGENT
    adaptation_log: List[str] = field(default_factory=list)
    adaptation_stage: int = 0
    just_lost_possession: bool = False
    tackle_cooldowns: Dict[str, int] = field(default_factory=dict)
    subs_made: int = 0

    def by_id(self, player_id: str) -> Optional[Player]:
        for p in self.players:
            if p.id == player_id:
                return p
        for p in self.subs:
            if p.id == player_id:
                return p
        return None

    def outfield(self) -> List[Player]:
        return [p for p in self.players if not p.is_gk() and p.on_pitch]

    def goalkeeper(self) -> Optional[Player]:
        for p in self.players:
            if p.is_gk() and p.on_pitch:
                return p
        return None

    def is_home(self) -> bool:
        return self.side == Side.HOME


def build_team(name: str, side: Side, color: tuple, tactics: TeamTactics,
               seed: int, ai_level: AILevel = AILevel.FULL_MULTI_AGENT) -> Team:
    """Generate a full 11-man roster (+3 subs) for a given formation/tactics using a seeded RNG
    so rosters (and therefore match outcomes) are reproducible."""
    rng = random.Random(seed)
    team = Team(name=name, side=side, color=color, tactics=tactics, ai_level=ai_level)
    slots = slots_for(tactics.formation)
    id_prefix = "H" if side == Side.HOME else "A"

    numbers = list(range(1, 12))
    names = rng.sample(DEFAULT_NAMES, k=min(11, len(DEFAULT_NAMES)))
    while len(names) < 11:
        names.append(f"Player{len(names) + 1}")

    for i, (role, x_frac, y_frac) in enumerate(slots):
        attrs = generate_attributes(role, rng)
        p = Player(
            id=f"{id_prefix}{i + 1}", number=numbers[i], name=names[i], role=role,
            side=side, attributes=attrs, slot_index=i,
        )
        team.players.append(p)

    # a small bench: one extra of each outfield category for substitutions
    bench_roles = [PlayerRole.CB, PlayerRole.CM, PlayerRole.ST]
    for j, role in enumerate(bench_roles):
        attrs = generate_attributes(role, rng)
        p = Player(id=f"{id_prefix}S{j + 1}", number=12 + j, name=f"Sub{j + 1}", role=role,
                   side=side, attributes=attrs, is_substitute=True, on_pitch=False)
        team.subs.append(p)

    return team


def substitute(team: Team, off_player_id: str, sub_index: int) -> Optional[str]:
    """Swap a fatigued/injured player for a bench player of the same general role bucket.
    Returns a reason string for the event log, or None if the substitution was invalid."""
    off_player = team.by_id(off_player_id)
    if off_player is None or not off_player.on_pitch or sub_index >= len(team.subs):
        return None
    sub = team.subs[sub_index]
    off_player.on_pitch = False
    sub.on_pitch = True
    sub.position = off_player.position.copy()
    sub.home_position = off_player.home_position.copy()
    team.players = [sub if p.id == off_player.id else p for p in team.players]
    team.subs.remove(sub)
    team.subs.append(off_player)
    return f"{team.name}: {off_player.name} ({off_player.stamina:.0f}% stamina) replaced by {sub.name}"
