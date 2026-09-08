# Experiments Guide

## Why experiment mode exists

A single match is anecdotal - a 1-0 win could be luck. Experiment mode
(`src/simulation/experiments.py`) runs many *headless* matches (no rendering, ticked as
fast as the CPU allows - typically 200+ ticks/sec) with different random seeds and
aggregates the results, which is what turns "the AI seems to work" into an actual
reportable result for a project write-up.

## Running an experiment

```bash
# Tactics experiment: Team A's style vs Team B's style (default: Possession vs Counter Attack)
python -m src.simulation.experiments --matches 50

# Choose specific styles (possession | counter_attack | high_press | defensive | balanced)
python -m src.simulation.experiments --matches 50 --a-style high_press --b-style defensive

# AI sophistication comparison: RANDOM / RULE_BASED / UTILITY_BASED each vs FULL_MULTI_AGENT
python -m src.simulation.experiments --matches 50 --ai-comparison
```

Each run prints a console summary and writes every individual match's full metric row to
`results/tactics_experiment.csv` or `results/ai_level_comparison.csv` (all fields of
`src/simulation/metrics.py::MatchMetrics` - score, possession, passes, shots, tackles,
interceptions, fouls, adaptation events, average stamina, distance covered, decision
count/latency).

## Worked example (5 matches, for illustration - use --matches 50+ for a real report)

```
=== Possession (4-3-3) vs Counter Attack (4-4-2) ===
Matches: 5
Team A wins: 2   Draws: 2   Team B wins: 1
Average Goals:      Team A 2.00   Team B 1.60
Average Possession: Team A 50.6%   Team B 49.4%
Average Pass Acc.:  Team A 48.0%   Team B 46.0%
Average decision latency: 6.500 ms/tick
```

**How to read it:** win/draw/loss counts and average goals answer "which configuration
wins more"; average possession and pass accuracy answer "does the tactical style produce
the expected *style* of play, independent of the scoreline" (a possession team should
show higher pass accuracy and a more even-to-higher possession share); decision latency
is a performance sanity check (should stay in the low single-digit milliseconds per
simulation tick across 22 agents).

## AI sophistication comparison (interpreting the gradient)

Running `--ai-comparison` pits `RANDOM`, `RULE_BASED` and `UTILITY_BASED` policies (each
still gets full team coordination/defence - only the ball-carrier decision policy
changes) against the `FULL_MULTI_AGENT` policy on identical tactics/formation. In a
sample 4-match run:

```
Random/Basic vs Full Multi-Agent:  Random wins 2, Full wins 2, but Random's possession
                                    share was only 19% vs Full's 81% - random decisions
                                    lose the ball far more often even when goal counts
                                    are close by chance in a tiny sample.
Rule-Based vs Full Multi-Agent:    Full wins 3 of 4, draws 1 - fixed if/then rules are a
                                    clear step up from random but still lose more often.
Utility-Based vs Full Multi-Agent: 4 draws - utility scoring alone gets most of the way
                                    to the full system; the remaining gap is dynamic
                                    tactical adaptation to score/time, which matters most
                                    in close, late-game situations that a 4-match sample
                                    rarely captures.
```

**Recommendation for a project report:** run at least 50, ideally 100+, matches per
comparison (`--matches 100`) so win/draw/loss counts and averages are statistically
stable, and note that possession share is a more sensitive/faster-converging signal than
goals (goals are rare, discrete events with high variance; possession accumulates every
tick of every match).

## A note on match-to-match variance

Possession share swings widely between individual matches (e.g. 15%/85% is not unusual)
even between two teams on identical formation and tactical style. This was checked
deliberately: a 10-match Balanced-vs-Balanced control (home/away swapped, same style
both sides) averaged 46% home possession across the sample - close to the unbiased 50%
expected, confirming there's no systematic home/away code bias - but individual matches
ranged from 11% to 89%. This is because each side's roster is generated with independent
random attribute variance (+/-8 per player around its role template); a modest random
skill edge compounds over 90 minutes of possession battles into a large swing, similar to
how real football possession dominance is often lopsided even between similarly-rated
sides. **Implication for experiment design:** always compare *averages over many
matches* (25+, ideally 50-100), never a single match, and prefer possession/pass-accuracy
trends over single-match win/loss when judging whether a tactical change "worked."

## Extending experiments

`run_experiment(label, team_a: TeamConfig, team_b: TeamConfig, matches, seed_base)` in
`src/simulation/experiments.py` is the reusable entry point - `TeamConfig` takes any
formation, `TacticalStyle` and `AILevel`, so new comparisons (e.g. formation vs
formation, or a specific style at every AI level) just need a new `TeamConfig` pairing
and a call to `run_experiment` plus `export_csv`.
