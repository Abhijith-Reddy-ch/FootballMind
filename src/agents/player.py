"""Player agent: attributes, mutable match state, and per-tick physical update.

Decision-making itself (state transitions, utility scoring) lives in src/ai/* and is
invoked by Match; this module only holds agent state and the low-level physical model
(movement, stamina drain/regen) that every decision ultimately acts through.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from src.core.enums import ActionType, PlayerRole, PlayerState, Side
from src.core.vector import Vec2, v, distance, normalize, clamp

MAX_STAMINA = 100.0


@dataclass
class Attributes:
    speed: int = 60
    acceleration: int = 60
    stamina: int = 60          # max stamina / endurance rating
    passing: int = 60
    shooting: int = 60
    dribbling: int = 60
    tackling: int = 60
    defending: int = 60
    vision: int = 60
    decision_making: int = 60
    positioning: int = 60
    strength: int = 60

    def get(self, name: str) -> float:
        return float(getattr(self, name))


# Base attribute templates per role archetype (before individual random variance).
ROLE_TEMPLATES: Dict[PlayerRole, Attributes] = {
    PlayerRole.GK: Attributes(speed=50, acceleration=50, stamina=70, passing=55, shooting=20,
                               dribbling=30, tackling=40, defending=75, vision=60,
                               decision_making=70, positioning=85, strength=65),
    PlayerRole.CB: Attributes(speed=62, acceleration=58, stamina=75, passing=58, shooting=25,
                               dribbling=45, tackling=82, defending=85, vision=55,
                               decision_making=68, positioning=80, strength=80),
    PlayerRole.FB: Attributes(speed=75, acceleration=74, stamina=82, passing=65, shooting=35,
                               dribbling=62, tackling=72, defending=70, vision=60,
                               decision_making=64, positioning=68, strength=62),
    PlayerRole.CDM: Attributes(speed=65, acceleration=62, stamina=85, passing=72, shooting=40,
                                dribbling=58, tackling=78, defending=75, vision=68,
                                decision_making=72, positioning=75, strength=72),
    PlayerRole.CM: Attributes(speed=68, acceleration=66, stamina=82, passing=78, shooting=52,
                               dribbling=68, tackling=60, defending=58, vision=75,
                               decision_making=74, positioning=68, strength=62),
    PlayerRole.CAM: Attributes(speed=70, acceleration=70, stamina=72, passing=82, shooting=68,
                                dribbling=80, tackling=42, defending=38, vision=88,
                                decision_making=80, positioning=65, strength=52),
    PlayerRole.WING: Attributes(speed=86, acceleration=85, stamina=78, passing=68, shooting=64,
                                 dribbling=82, tackling=38, defending=35, vision=68,
                                 decision_making=66, positioning=58, strength=52),
    PlayerRole.ST: Attributes(speed=80, acceleration=78, stamina=70, passing=58, shooting=85,
                               dribbling=72, tackling=30, defending=28, vision=62,
                               decision_making=68, positioning=78, strength=68),
}


def generate_attributes(role: PlayerRole, rng: random.Random, variance: int = 8) -> Attributes:
    base = ROLE_TEMPLATES[role]
    kwargs = {}
    for field_name in base.__dataclass_fields__:
        val = getattr(base, field_name)
        noisy = int(clamp(val + rng.randint(-variance, variance), 1, 99))
        kwargs[field_name] = noisy
    return Attributes(**kwargs)


@dataclass
class DecisionRecord:
    """A single explainable AI decision, kept for the AI Explanation UI / event log."""
    tick: int
    player_id: str
    state: PlayerState
    action: ActionType
    utility: float
    reasons: List[str] = field(default_factory=list)
    components: Dict[str, float] = field(default_factory=dict)
    target_id: Optional[str] = None
    target_position: Optional[Vec2] = None


@dataclass
class Player:
    id: str
    number: int
    name: str
    role: PlayerRole
    side: Side
    attributes: Attributes

    position: Vec2 = field(default_factory=lambda: v(0.0, 0.0))
    velocity: Vec2 = field(default_factory=lambda: v(0.0, 0.0))
    home_position: Vec2 = field(default_factory=lambda: v(0.0, 0.0))  # current formation anchor
    target_position: Vec2 = field(default_factory=lambda: v(0.0, 0.0))

    slot_index: int = 0  # index into the team's formation slot list (src/ai/positioning.py)

    stamina: float = MAX_STAMINA
    state: PlayerState = PlayerState.IDLE
    current_action: ActionType = ActionType.HOLD_POSITION
    has_ball: bool = False
    marking_target_id: Optional[str] = None

    yellow_cards: int = 0
    red_carded: bool = False
    is_substitute: bool = False
    on_pitch: bool = True

    distance_covered: float = 0.0
    last_decision: Optional[DecisionRecord] = None

    # per-match counters used by analytics
    stats: Dict[str, int] = field(default_factory=lambda: {
        "passes_attempted": 0, "passes_completed": 0, "shots": 0, "goals": 0,
        "tackles": 0, "tackles_won": 0, "interceptions": 0, "fouls": 0,
    })

    def effective_speed(self) -> float:
        """Top speed (m/s) scaled by attribute rating and current stamina fatigue."""
        base = 4.0 + (self.attributes.speed / 100.0) * 4.5  # ~4-8.5 m/s
        fatigue_factor = 0.55 + 0.45 * (self.stamina / MAX_STAMINA)
        if self.red_carded or not self.on_pitch:
            return 0.0
        return base * fatigue_factor

    def move_towards(self, target: Vec2, dt: float, sprint: bool = True) -> None:
        to_target = target - self.position
        dist = float((to_target ** 2).sum() ** 0.5)
        if dist < 1e-3:
            self.velocity = v(0.0, 0.0)
            return
        speed = self.effective_speed() * (1.0 if sprint else 0.6)
        step = min(dist, speed * dt)
        direction = normalize(to_target)
        self.velocity = direction * speed
        self.position = self.position + direction * step
        self.distance_covered += step
        self._drain_stamina(step, sprint, dt)

    def _drain_stamina(self, distance_moved: float, sprint: bool, dt: float) -> None:
        endurance = 0.6 + (self.attributes.stamina / 100.0) * 0.8  # higher stamina attr -> less drain
        rate = (2.6 if sprint else 1.1) / endurance
        self.stamina = max(0.0, self.stamina - distance_moved * rate * 0.35)

    def regen_stamina(self, dt: float, intensity: float = 0.0) -> None:
        """Slow recovery when not sprinting; intensity in [0,1] reduces regen (e.g. holding a press)."""
        endurance = 0.6 + (self.attributes.stamina / 100.0) * 0.8
        regen_rate = 0.9 * endurance * (1.0 - 0.6 * intensity)
        self.stamina = min(MAX_STAMINA, self.stamina + regen_rate * dt)

    def fatigue_ratio(self) -> float:
        return 1.0 - (self.stamina / MAX_STAMINA)

    def is_gk(self) -> bool:
        return self.role == PlayerRole.GK
