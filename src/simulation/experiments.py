"""Experiment mode (sections 28-30): run many automated matches between two AI/tactics
configurations and produce aggregate results + a results.csv export.

Usage:
    python -m src.simulation.experiments
    python -m src.simulation.experiments --matches 50 --a-style possession --b-style counter_attack
    python -m src.simulation.experiments --ai-comparison
"""
from __future__ import annotations

import argparse
import csv
import os
import statistics
from dataclasses import asdict, dataclass
from typing import List

from src.core.enums import AILevel, TacticalStyle
from src.simulation.metrics import MatchMetrics
from src.simulation.simulator import TeamConfig, run_match

RESULTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "results")

STYLE_ALIASES = {
    "possession": TacticalStyle.POSSESSION, "counter_attack": TacticalStyle.COUNTER_ATTACK,
    "high_press": TacticalStyle.HIGH_PRESS, "defensive": TacticalStyle.DEFENSIVE,
    "balanced": TacticalStyle.BALANCED,
}
AI_ALIASES = {
    "random": AILevel.RANDOM, "rule_based": AILevel.RULE_BASED,
    "utility_based": AILevel.UTILITY_BASED, "full": AILevel.FULL_MULTI_AGENT,
}


@dataclass
class ExperimentSummary:
    label: str
    matches: int
    team_a_wins: int
    draws: int
    team_b_wins: int
    team_a_avg_goals: float
    team_b_avg_goals: float
    team_a_avg_possession: float
    team_b_avg_possession: float
    team_a_avg_pass_accuracy: float
    team_b_avg_pass_accuracy: float
    avg_decision_latency_ms: float


def run_experiment(label: str, team_a: TeamConfig, team_b: TeamConfig, matches: int,
                    seed_base: int = 1000) -> tuple[ExperimentSummary, List[MatchMetrics]]:
    results: List[MatchMetrics] = []
    for i in range(matches):
        m = run_match(team_a, team_b, seed=seed_base + i)
        results.append(m)

    a_wins = sum(1 for r in results if r.home_score > r.away_score)
    b_wins = sum(1 for r in results if r.away_score > r.home_score)
    draws = matches - a_wins - b_wins

    def pass_acc(attempted, completed):
        return 100.0 * completed / attempted if attempted else 0.0

    summary = ExperimentSummary(
        label=label, matches=matches, team_a_wins=a_wins, draws=draws, team_b_wins=b_wins,
        team_a_avg_goals=statistics.mean(r.home_score for r in results),
        team_b_avg_goals=statistics.mean(r.away_score for r in results),
        team_a_avg_possession=statistics.mean(r.home_possession_pct for r in results),
        team_b_avg_possession=statistics.mean(r.away_possession_pct for r in results),
        team_a_avg_pass_accuracy=statistics.mean(
            pass_acc(r.home_passes_attempted, r.home_passes_completed) for r in results),
        team_b_avg_pass_accuracy=statistics.mean(
            pass_acc(r.away_passes_attempted, r.away_passes_completed) for r in results),
        avg_decision_latency_ms=statistics.mean(r.decision_latency_ms for r in results),
    )
    return summary, results


def print_summary(summary: ExperimentSummary, team_a_name: str, team_b_name: str) -> None:
    print(f"\n=== {summary.label} ===")
    print(f"Matches: {summary.matches}")
    print(f"{team_a_name} wins: {summary.team_a_wins}   Draws: {summary.draws}   "
          f"{team_b_name} wins: {summary.team_b_wins}")
    print(f"Average Goals:      {team_a_name} {summary.team_a_avg_goals:.2f}   "
          f"{team_b_name} {summary.team_b_avg_goals:.2f}")
    print(f"Average Possession: {team_a_name} {summary.team_a_avg_possession:.1f}%   "
          f"{team_b_name} {summary.team_b_avg_possession:.1f}%")
    print(f"Average Pass Acc.:  {team_a_name} {summary.team_a_avg_pass_accuracy:.1f}%   "
          f"{team_b_name} {summary.team_b_avg_pass_accuracy:.1f}%")
    print(f"Average decision latency: {summary.avg_decision_latency_ms:.3f} ms/tick")


def export_csv(all_results: List[MatchMetrics], path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if not all_results:
        return
    fieldnames = list(asdict(all_results[0]).keys())
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in all_results:
            writer.writerow(asdict(r))
    print(f"\nExported {len(all_results)} match rows to {path}")


def tactics_experiment(matches: int, a_style: TacticalStyle, b_style: TacticalStyle) -> None:
    team_a = TeamConfig(name="Team A", formation="4-3-3", style=a_style, ai_level=AILevel.FULL_MULTI_AGENT)
    team_b = TeamConfig(name="Team B", formation="4-4-2", style=b_style, ai_level=AILevel.FULL_MULTI_AGENT)
    summary, results = run_experiment(f"{a_style.value} (4-3-3) vs {b_style.value} (4-4-2)",
                                       team_a, team_b, matches)
    print_summary(summary, "Team A", "Team B")
    export_csv(results, os.path.join(RESULTS_DIR, "tactics_experiment.csv"))


def ai_level_comparison(matches: int) -> None:
    """Section 29: pit each baseline AI sophistication level against the full multi-agent
    AI (same tactics/formation) to demonstrate that more sophisticated AI performs better."""
    levels = [AILevel.RANDOM, AILevel.RULE_BASED, AILevel.UTILITY_BASED]
    all_rows: List[MatchMetrics] = []
    for level in levels:
        team_a = TeamConfig(name=level.value, formation="4-3-3", style=TacticalStyle.BALANCED,
                             ai_level=level)
        team_b = TeamConfig(name="Full Multi-Agent", formation="4-3-3", style=TacticalStyle.BALANCED,
                             ai_level=AILevel.FULL_MULTI_AGENT)
        summary, results = run_experiment(f"{level.value} vs Full Multi-Agent AI", team_a, team_b, matches)
        print_summary(summary, level.value, "Full Multi-Agent")
        all_rows.extend(results)
    export_csv(all_rows, os.path.join(RESULTS_DIR, "ai_level_comparison.csv"))


def main() -> None:
    parser = argparse.ArgumentParser(description="FootballMind experiment mode")
    parser.add_argument("--matches", type=int, default=20)
    parser.add_argument("--a-style", choices=list(STYLE_ALIASES), default="possession")
    parser.add_argument("--b-style", choices=list(STYLE_ALIASES), default="counter_attack")
    parser.add_argument("--ai-comparison", action="store_true",
                         help="Run the baseline-vs-advanced AI comparison instead of a tactics experiment")
    args = parser.parse_args()

    if args.ai_comparison:
        ai_level_comparison(args.matches)
    else:
        tactics_experiment(args.matches, STYLE_ALIASES[args.a_style], STYLE_ALIASES[args.b_style])


if __name__ == "__main__":
    main()
