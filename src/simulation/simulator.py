"""Headless match runner (no pygame) used by experiments and by anything that needs a
full match simulated as fast as possible, with wall-clock decision-latency measurement."""
from __future__ import annotations

import time
from dataclasses import dataclass

from src.core.enums import AILevel, MatchPhase, Side, TacticalStyle
from src.agents.team import build_team
from src.ai.tactics import preset_for
from src.game.match import Match
from src.simulation.metrics import MatchMetrics, extract

SIM_DT = 1 / 20
MAX_TICKS = 25000  # safety cap so a stuck match can't loop forever


@dataclass
class TeamConfig:
    name: str
    formation: str = "4-3-3"
    style: TacticalStyle = TacticalStyle.BALANCED
    ai_level: AILevel = AILevel.FULL_MULTI_AGENT
    color: tuple = (200, 60, 60)


def run_match(team_a: TeamConfig, team_b: TeamConfig, seed: int) -> MatchMetrics:
    home_tactics = preset_for(team_a.style, team_a.formation)
    away_tactics = preset_for(team_b.style, team_b.formation)
    home = build_team(team_a.name, Side.HOME, team_a.color, home_tactics, seed=seed * 2 + 1,
                       ai_level=team_a.ai_level)
    away = build_team(team_b.name, Side.AWAY, team_b.color, away_tactics, seed=seed * 2 + 2,
                       ai_level=team_b.ai_level)
    match = Match(home=home, away=away, seed=seed)

    start = time.perf_counter()
    for _ in range(MAX_TICKS):
        match.tick(SIM_DT)
        if match.phase == MatchPhase.HALFTIME:
            match.start_second_half()
        if match.is_over():
            break
    elapsed_ms = (time.perf_counter() - start) * 1000.0
    latency_ms = elapsed_ms / max(1, match.tick_count)

    return extract(match, latency_ms)
