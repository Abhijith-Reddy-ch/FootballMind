"""Generic utility-based decision-making framework (Level 3 AI).

Every meaningful player decision is expressed as a set of ActionCandidate objects, each
carrying a numeric utility plus a human-readable breakdown of *why* it scored that way.
`choose_best` just picks the max, but the interesting work happens in the per-action
evaluators (passing.py, shooting.py, defending.py, positioning.py) which combine game
state, spatial reasoning, player ability, tactical objectives and risk into a score:

    Utility(action) = w1*TacticalValue + w2*SpatialValue + w3*PlayerAbility
                       + w4*TeamObjective - w5*Risk - w6*OpponentPressure
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

from src.core.enums import ActionType


@dataclass
class ActionCandidate:
    action: ActionType
    utility: float
    target_id: Optional[str] = None       # e.g. pass receiver id, mark target id
    target_position: Optional[object] = None
    components: Dict[str, float] = field(default_factory=dict)
    reasons: List[str] = field(default_factory=list)

    def explanation_lines(self) -> List[str]:
        lines = [f"{self.action.name} — utility {self.utility:.0f}"]
        for k, val in self.components.items():
            sign = "+" if val >= 0 else "-"
            lines.append(f"  {sign} {k}: {val:+.1f}")
        lines.extend(f"  * {r}" for r in self.reasons)
        return lines


def choose_best(candidates: Sequence[ActionCandidate]) -> Optional[ActionCandidate]:
    if not candidates:
        return None
    return max(candidates, key=lambda c: c.utility)


def weighted_sum(components: Dict[str, float]) -> float:
    return float(sum(components.values()))
