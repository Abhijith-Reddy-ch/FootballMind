"""Formation templates and dynamic positional anchor computation.

Each formation is a set of *relative* anchors (fraction of pitch length/width, expressed
from the home team's attacking direction). `anchor_position` converts a relative anchor
into a live meter position that deforms with tactics (defensive line, width) and the
ball's location, so the same "4-3-3" looks different when parked deep vs pressing high.
"""
from __future__ import annotations

from typing import List, Tuple

from src.core.enums import PlayerRole
from src.core.vector import Vec2, v, clamp
from src.ai.tactics import TeamTactics
from src.game import pitch

Slot = Tuple[PlayerRole, float, float]  # role, x_frac (0=own goal), y_frac (0..1 across width)

FORMATIONS: dict[str, List[Slot]] = {
    "4-3-3": [
        (PlayerRole.GK, 0.04, 0.50),
        (PlayerRole.CB, 0.18, 0.35), (PlayerRole.CB, 0.18, 0.65),
        (PlayerRole.FB, 0.22, 0.10), (PlayerRole.FB, 0.22, 0.90),
        (PlayerRole.CDM, 0.42, 0.50),
        (PlayerRole.CM, 0.52, 0.30), (PlayerRole.CM, 0.52, 0.70),
        (PlayerRole.WING, 0.76, 0.15), (PlayerRole.WING, 0.76, 0.85),
        (PlayerRole.ST, 0.85, 0.50),
    ],
    "4-4-2": [
        (PlayerRole.GK, 0.04, 0.50),
        (PlayerRole.CB, 0.18, 0.35), (PlayerRole.CB, 0.18, 0.65),
        (PlayerRole.FB, 0.20, 0.10), (PlayerRole.FB, 0.20, 0.90),
        (PlayerRole.WING, 0.48, 0.15), (PlayerRole.WING, 0.48, 0.85),
        (PlayerRole.CM, 0.45, 0.38), (PlayerRole.CM, 0.45, 0.62),
        (PlayerRole.ST, 0.80, 0.40), (PlayerRole.ST, 0.80, 0.60),
    ],
    "4-2-3-1": [
        (PlayerRole.GK, 0.04, 0.50),
        (PlayerRole.CB, 0.18, 0.35), (PlayerRole.CB, 0.18, 0.65),
        (PlayerRole.FB, 0.22, 0.10), (PlayerRole.FB, 0.22, 0.90),
        (PlayerRole.CDM, 0.38, 0.38), (PlayerRole.CDM, 0.38, 0.62),
        (PlayerRole.CAM, 0.62, 0.50),
        (PlayerRole.WING, 0.66, 0.15), (PlayerRole.WING, 0.66, 0.85),
        (PlayerRole.ST, 0.85, 0.50),
    ],
    "3-5-2": [
        (PlayerRole.GK, 0.04, 0.50),
        (PlayerRole.CB, 0.16, 0.28), (PlayerRole.CB, 0.16, 0.50), (PlayerRole.CB, 0.16, 0.72),
        (PlayerRole.FB, 0.45, 0.06), (PlayerRole.FB, 0.45, 0.94),
        (PlayerRole.CDM, 0.38, 0.50),
        (PlayerRole.CM, 0.52, 0.32), (PlayerRole.CM, 0.52, 0.68),
        (PlayerRole.ST, 0.82, 0.40), (PlayerRole.ST, 0.82, 0.60),
    ],
    "5-3-2": [
        (PlayerRole.GK, 0.04, 0.50),
        (PlayerRole.CB, 0.16, 0.30), (PlayerRole.CB, 0.16, 0.50), (PlayerRole.CB, 0.16, 0.70),
        (PlayerRole.FB, 0.30, 0.08), (PlayerRole.FB, 0.30, 0.92),
        (PlayerRole.CM, 0.48, 0.35), (PlayerRole.CDM, 0.42, 0.50), (PlayerRole.CM, 0.48, 0.65),
        (PlayerRole.ST, 0.80, 0.40), (PlayerRole.ST, 0.80, 0.60),
    ],
}


def slots_for(formation: str) -> List[Slot]:
    return FORMATIONS[formation]


def anchor_position(slot: Slot, side_is_home: bool, tactics: TeamTactics,
                     ball_x_frac: float) -> Vec2:
    """Compute a live meter-space anchor for a formation slot.

    Deformation rules (section 12):
    - defensive_line shifts the whole outfield block up/down the pitch
    - width stretches/compresses spread across the pitch's y-axis
    - the block also leans a little towards the ball's x position (compactness around play)
    """
    role, x_frac, y_frac = slot
    x_eff = x_frac if side_is_home else 1.0 - x_frac

    if role != PlayerRole.GK:
        line_shift = (tactics.defensive_line - 50) / 100.0 * 0.12
        ball_pull = (ball_x_frac - x_eff) * 0.12
        x_eff = clamp(x_eff + (line_shift if side_is_home else -line_shift) + ball_pull, 0.03, 0.97)

    width_scale = 0.65 + (tactics.width / 100.0) * 0.55
    y_eff = 0.5 + (y_frac - 0.5) * width_scale
    y_eff = clamp(y_eff, 0.03, 0.97)

    return v(x_eff * pitch.LENGTH, y_eff * pitch.WIDTH)


def attacking_push(slot: Slot, side_is_home: bool, mentality_bias: float) -> Vec2:
    """Extra forward push applied to a base anchor when a team's own player has the ball,
    e.g. fullbacks/wingers advance, mentality_bias in [-1,1] (defend..attack)."""
    role, *_ = slot
    push_by_role = {
        PlayerRole.ST: 0.03, PlayerRole.WING: 0.06, PlayerRole.CAM: 0.05,
        PlayerRole.CM: 0.04, PlayerRole.CDM: 0.015, PlayerRole.FB: 0.05,
        PlayerRole.CB: 0.01, PlayerRole.GK: 0.0,
    }
    dx = push_by_role.get(role, 0.02) * mentality_bias * pitch.LENGTH
    return v(dx if side_is_home else -dx, 0.0)
