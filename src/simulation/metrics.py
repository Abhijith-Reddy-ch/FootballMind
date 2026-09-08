"""Per-match performance metrics extraction, used by both the post-match stats screen
context and (more importantly) the headless experiment runner for section 30's tracked
metrics: decision count/latency, passes, shots, goals, interceptions, tackles, possession,
average stamina, distance covered, tactical changes, turnovers."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class MatchMetrics:
    home_name: str
    away_name: str
    home_score: int
    away_score: int
    home_style: str
    away_style: str
    home_ai_level: str
    away_ai_level: str

    home_possession_pct: float
    away_possession_pct: float
    home_passes_attempted: int
    home_passes_completed: int
    away_passes_attempted: int
    away_passes_completed: int
    home_shots: int
    away_shots: int
    home_tackles: int
    away_tackles: int
    home_interceptions: int
    away_interceptions: int
    home_fouls: int
    away_fouls: int
    home_adaptations: int
    away_adaptations: int
    home_avg_stamina: float
    away_avg_stamina: float
    home_distance_km: float
    away_distance_km: float

    decision_count: int
    avg_decision_utility: float
    decision_latency_ms: float
    duration_minutes: float


def extract(match, decision_latency_ms: float) -> MatchMetrics:
    home, away = match.home, match.away
    total_poss = max(1, home.stats.possession_ticks + away.stats.possession_ticks)

    def avg_stamina(team):
        players = [p for p in team.players if p.on_pitch]
        return sum(p.stamina for p in players) / len(players) if players else 0.0

    def distance_km(team):
        return sum(p.distance_covered for p in team.players) / 1000.0

    decisions = list(match.decision_log)
    avg_util = sum(d.utility for d in decisions) / len(decisions) if decisions else 0.0

    return MatchMetrics(
        home_name=home.name, away_name=away.name, home_score=home.score, away_score=away.score,
        home_style=home.tactics.style.value, away_style=away.tactics.style.value,
        home_ai_level=home.ai_level.value, away_ai_level=away.ai_level.value,
        home_possession_pct=100.0 * home.stats.possession_ticks / total_poss,
        away_possession_pct=100.0 * away.stats.possession_ticks / total_poss,
        home_passes_attempted=home.stats.passes_attempted, home_passes_completed=home.stats.passes_completed,
        away_passes_attempted=away.stats.passes_attempted, away_passes_completed=away.stats.passes_completed,
        home_shots=home.stats.shots, away_shots=away.stats.shots,
        home_tackles=home.stats.tackles, away_tackles=away.stats.tackles,
        home_interceptions=home.stats.interceptions, away_interceptions=away.stats.interceptions,
        home_fouls=home.stats.fouls, away_fouls=away.stats.fouls,
        home_adaptations=home.stats.adaptation_events, away_adaptations=away.stats.adaptation_events,
        home_avg_stamina=avg_stamina(home), away_avg_stamina=avg_stamina(away),
        home_distance_km=distance_km(home), away_distance_km=distance_km(away),
        decision_count=len(decisions), avg_decision_utility=avg_util,
        decision_latency_ms=decision_latency_ms, duration_minutes=match.minute,
    )
