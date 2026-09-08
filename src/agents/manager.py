"""User-facing manager controls (section 22/23): pre-match setup + live intervention."""
from __future__ import annotations

from dataclasses import dataclass, replace

from src.core.enums import Mentality, TacticalStyle
from src.core.vector import clamp
from src.agents.team import Team
from src.ai.tactics import apply_manager_override, preset_for


@dataclass
class MatchSetupConfig:
    formation: str = "4-3-3"
    style: TacticalStyle = TacticalStyle.BALANCED
    mentality: Mentality = Mentality.BALANCED
    pressing_intensity: int = 50
    defensive_line: int = 50
    passing_risk: int = 50

    def to_tactics(self):
        t = preset_for(self.style, self.formation, self.mentality)
        from dataclasses import replace
        return replace(t, pressing_intensity=self.pressing_intensity,
                       defensive_line=self.defensive_line, passing_risk=self.passing_risk)


class ManagerController:
    """Applies live tactical interventions from the user to a Team's TeamTactics."""

    def __init__(self, team: Team):
        self.team = team

    def set_style(self, style: TacticalStyle) -> None:
        self.team.tactics = apply_manager_override(self.team.tactics, style=style)

    def set_mentality(self, mentality: Mentality) -> None:
        self.team.tactics = apply_manager_override(self.team.tactics, mentality=mentality)

    def quick_command(self, label: str) -> None:
        """One of ATTACK / BALANCED / DEFEND / HIGH_PRESS / COUNTER_ATTACK buttons.

        ATTACK/DEFEND directly push the numeric dials (pressing, line, risk, tempo), not
        just the mentality flag - a mentality-only nudge is too small to be visible in
        play; this mirrors how dynamic_adaptation reacts to a losing/winning scoreline.
        """
        t = self.team.tactics
        if label == "ATTACK":
            self.team.tactics = replace(
                t, mentality=Mentality.ATTACK,
                pressing_intensity=int(clamp(t.pressing_intensity + 15, 0, 100)),
                defensive_line=int(clamp(t.defensive_line + 15, 0, 100)),
                passing_risk=int(clamp(t.passing_risk + 15, 0, 100)),
                tempo=int(clamp(t.tempo + 15, 0, 100)))
        elif label == "DEFEND":
            self.team.tactics = replace(
                t, mentality=Mentality.DEFEND,
                pressing_intensity=int(clamp(t.pressing_intensity - 15, 0, 100)),
                defensive_line=int(clamp(t.defensive_line - 15, 0, 100)),
                passing_risk=int(clamp(t.passing_risk - 15, 0, 100)),
                tempo=int(clamp(t.tempo - 15, 0, 100)))
        elif label == "BALANCED":
            self.team.tactics = preset_for(TacticalStyle.BALANCED, t.formation, Mentality.BALANCED)
        elif label == "HIGH_PRESS":
            self.set_style(TacticalStyle.HIGH_PRESS)
            self.set_mentality(Mentality.BALANCED)
        elif label == "COUNTER_ATTACK":
            self.set_style(TacticalStyle.COUNTER_ATTACK)
            self.set_mentality(Mentality.BALANCED)
