"""Ball entity with simplified kinematics (friction deceleration, no bounce physics)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from src.core.vector import Vec2, v, distance
from src.game import pitch

FRICTION = 1.6  # m/s^2 deceleration while rolling
MAX_SPEED = 30.0  # m/s cap for a struck ball
POSSESSION_RADIUS = 1.1  # meters: a player this close to a loose/slow ball can pick it up


@dataclass
class Ball:
    position: Vec2 = field(default_factory=lambda: pitch.CENTER.copy())
    velocity: Vec2 = field(default_factory=lambda: v(0.0, 0.0))
    owner_id: Optional[str] = None
    in_flight_target: Optional[Vec2] = None  # set while a pass/shot is airborne, for lane visuals

    def kick(self, direction: Vec2, speed: float) -> None:
        from src.core.vector import normalize
        speed = min(speed, MAX_SPEED)
        self.velocity = normalize(direction) * speed
        self.owner_id = None

    def update(self, dt: float) -> None:
        speed = float((self.velocity ** 2).sum() ** 0.5)
        if speed > 1e-6:
            decel = min(speed, FRICTION * dt)
            from src.core.vector import normalize
            self.velocity = self.velocity - normalize(self.velocity) * decel
        new_position = self.position + self.velocity * dt
        clamped = pitch.clamp_to_pitch(new_position)
        if (clamped != new_position).any():
            self.velocity = v(0.0, 0.0)  # hit the boundary -> dead ball, ready to be picked up
        self.position = clamped

    def is_loose(self) -> bool:
        return self.owner_id is None

    def attach(self, player_id: str, position: Vec2) -> None:
        self.owner_id = player_id
        self.position = position.copy()
        self.velocity = v(0.0, 0.0)
        self.in_flight_target = None

    def nearest_pickup_distance(self, pos: Vec2) -> float:
        return distance(self.position, pos)
