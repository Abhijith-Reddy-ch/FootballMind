"""Team-level tactical settings, style presets, and in-match dynamic adaptation.

This is "Level 2" of the AI hierarchy: it does not move any player directly, it sets the
parameters (defensive line, pressing intensity, risk tolerance, tempo, width) that the
player-level utility functions (src/ai/positioning.py, passing.py, shooting.py) read when
scoring their candidate actions.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import List, Tuple

from src.core.enums import Mentality, TacticalStyle


@dataclass(frozen=True)
class TeamTactics:
    formation: str = "4-3-3"
    style: TacticalStyle = TacticalStyle.BALANCED
    mentality: Mentality = Mentality.BALANCED
    pressing_intensity: int = 50   # 0-100
    defensive_line: int = 50       # 0-100 (100 = very high line)
    passing_risk: int = 50         # 0-100 (100 = riskier, more progressive passes)
    width: int = 50                # 0-100 (100 = very wide)
    tempo: int = 50                # 0-100 (100 = fastest ball circulation)


STYLE_PRESETS = {
    TacticalStyle.POSSESSION: TeamTactics(style=TacticalStyle.POSSESSION, pressing_intensity=45,
                                           defensive_line=55, passing_risk=30, width=55, tempo=45),
    TacticalStyle.COUNTER_ATTACK: TeamTactics(style=TacticalStyle.COUNTER_ATTACK, pressing_intensity=35,
                                               defensive_line=35, passing_risk=65, width=50, tempo=75),
    TacticalStyle.HIGH_PRESS: TeamTactics(style=TacticalStyle.HIGH_PRESS, pressing_intensity=85,
                                           defensive_line=75, passing_risk=55, width=60, tempo=70),
    TacticalStyle.DEFENSIVE: TeamTactics(style=TacticalStyle.DEFENSIVE, pressing_intensity=30,
                                          defensive_line=25, passing_risk=25, width=40, tempo=40),
    TacticalStyle.BALANCED: TeamTactics(style=TacticalStyle.BALANCED, pressing_intensity=50,
                                         defensive_line=50, passing_risk=45, width=50, tempo=50),
}


def preset_for(style: TacticalStyle, formation: str = "4-3-3",
               mentality: Mentality = Mentality.BALANCED) -> TeamTactics:
    base = STYLE_PRESETS[style]
    return replace(base, formation=formation, mentality=mentality)


@dataclass
class AdaptationEvent:
    minute: float
    team_side: str
    reasons: List[str]
    tactics_before: TeamTactics
    tactics_after: TeamTactics


def dynamic_adaptation(tactics: TeamTactics, minute: float, own_score: int, opp_score: int
                        ) -> Tuple[TeamTactics, List[str]]:
    """Section 14: adapt mentality/risk/line based on scoreline and time remaining.

    Returns (possibly-adjusted tactics, list of human-readable reasons). Pure function of
    match state -> deterministic given the same inputs (no randomness), so behaviour is
    reproducible under a fixed seed and explainable in the UI.
    """
    diff = own_score - opp_score
    reasons: List[str] = []
    t = tactics

    late = minute >= 75
    very_late = minute >= 85

    if diff < 0 and late:
        boost = 20 if very_late else 10
        t = replace(t,
                    mentality=Mentality.ATTACK,
                    pressing_intensity=min(100, t.pressing_intensity + boost),
                    defensive_line=min(100, t.defensive_line + boost),
                    passing_risk=min(100, t.passing_risk + boost),
                    tempo=min(100, t.tempo + boost))
        reasons.append(f"Losing by {-diff} with {90 - minute:.0f} min left -> increasing "
                        f"attacking intensity, pressing and risk tolerance")
    elif diff > 0 and late:
        cut = 20 if very_late else 10
        t = replace(t,
                    mentality=Mentality.DEFEND,
                    pressing_intensity=max(0, t.pressing_intensity - cut),
                    defensive_line=max(0, t.defensive_line - cut),
                    passing_risk=max(0, t.passing_risk - cut),
                    tempo=max(0, t.tempo - cut))
        reasons.append(f"Leading by {diff} with {90 - minute:.0f} min left -> protecting the "
                        f"result with a deeper line, slower tempo and safer passing")
    return t, reasons


def apply_manager_override(tactics: TeamTactics, style: TacticalStyle | None = None,
                            mentality: Mentality | None = None) -> TeamTactics:
    """Manual manager intervention (section 23) blends a new style preset over live tactics."""
    if style is not None:
        preset = STYLE_PRESETS[style]
        tactics = replace(tactics, style=style, pressing_intensity=preset.pressing_intensity,
                           defensive_line=preset.defensive_line, passing_risk=preset.passing_risk,
                           tempo=preset.tempo)
    if mentality is not None:
        tactics = replace(tactics, mentality=mentality)
    return tactics
