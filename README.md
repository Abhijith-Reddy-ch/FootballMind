# FootballMind

**An Intelligent Multi-Agent Football Manager Using Planning, Decision Making and Tactical AI**

FootballMind is a 2D top-down tactical football simulation in which every one of the 22
players on the pitch is an autonomous AI agent. Nothing is scripted animation: each agent
continuously evaluates its situation (position, teammates, opponents, tactics, stamina,
score, time remaining) and picks an action using a utility-scoring model, a finite state
machine, and team-level coordination signals. The user plays the role of **manager**,
setting formation and tactics before kickoff and issuing live tactical instructions
during the match - the AI controls every player.

## 1. Problem Statement

Traditional football video games rely heavily on predetermined, scripted player
behaviour: canned animations and if-this-then-that rules that don't generalise to novel
game states. FootballMind instead models each player as an autonomous intelligent agent
that makes context-dependent decisions from first principles - utility functions
combining spatial reasoning, player ability, tactical objective and risk - so that
behaviour emerges from the situation rather than from a lookup table.

## 2. Objectives

This project is a case study demonstrating, in a single runnable system:

- **Multi-agent systems** - 22 independent agents sharing an environment and coordinating indirectly through shared game state (`src/ai/coordination.py`).
- **Autonomous agents** - each player perceives (game state), decides (utility AI + FSM) and acts (movement, pass, shot, tackle) every simulation tick.
- **Decision making under uncertainty** - pass/shot/tackle outcomes are resolved probabilistically from skill, distance, pressure and risk, never scripted as guaranteed successes.
- **Utility-based reasoning** - every meaningful action is scored via an explicit weighted formula (`src/ai/utility_ai.py`, `passing.py`, `shooting.py`, `dribbling.py`).
- **Finite state machines** - each player's phase of play (`src/ai/state_machine.py`) transitions deterministically from game conditions.
- **Spatial reasoning / pathfinding** - A* over a coarse pitch grid (`src/ai/pathfinding.py`), invoked only when a straight line is congested.
- **Tactical adaptation** - team tactics shift automatically based on scoreline and time remaining (`src/ai/tactics.py`).
- **Explainability** - every AI decision carries a human-readable breakdown, surfaced live in AI Explanation Mode.

## 3. System Architecture

```
                         ┌───────────────────────────┐
                         │   Level 1: ENVIRONMENT     │
                         │        src/game/match.py   │
                         │  ball, pitch, clock, score, │
                         │  event log, GameState       │
                         └──────────────┬─────────────┘
                                        │ per-tick state
                         ┌──────────────▼─────────────┐
                         │  Level 2: TEAM AI (tactics) │
                         │        src/ai/tactics.py    │
                         │  formation, style, pressing, │
                         │  defensive line, dynamic     │
                         │  adaptation to score/time     │
                         └──────────────┬─────────────┘
                                        │ tactical parameters
                         ┌──────────────▼─────────────┐
                         │ COORDINATION (shared signals)│
                         │     src/ai/coordination.py   │
                         │  presser, cover, marking,    │
                         │  support runner, counter-press│
                         └──────────────┬─────────────┘
                                        │ signals
        ┌───────────────────────────────┼───────────────────────────────┐
        │                Level 3: PLAYER AGENTS (x22)                    │
        │                  src/agents/player.py                          │
        │  ┌─────────────┐   ┌──────────────────┐   ┌─────────────────┐ │
        │  │ FSM          │  │ Utility AI         │  │ Pathfinding      │ │
        │  │ state_machine│─▶│ passing/shooting/  │─▶│ pathfinding.py   │ │
        │  │ .py          │  │ dribbling/defending │  │ (A* when needed) │ │
        │  └─────────────┘   └──────────────────┘   └─────────────────┘ │
        └─────────────────────────────────────────────────────────────┘
```

`Match.tick()` in `src/game/match.py` is the loop that ties all four levels together once
per simulation step: apply dynamic adaptation -> compute coordination signals -> update
every player's FSM state and movement target -> let the ball carrier make a utility
decision -> resolve tackles -> step ball physics -> resolve loose-ball possession/goals.

## 4. AI Algorithms

| Technique | Where | What it's for |
|---|---|---|
| Finite State Machine | `src/ai/state_machine.py` | Deterministic phase-of-play transitions (IDLE, POSITIONING, ATTACKING, DEFENDING, PRESSING, MARKING, RECEIVING, DRIBBLING, PASSING, SHOOTING, TACKLING, RECOVERING, SUPPORT_ATTACK) |
| Utility-based decision making | `src/ai/utility_ai.py` + per-action evaluators | Weighted-sum scoring of every candidate action; highest score wins |
| Probabilistic outcome resolution | `passing.py`, `shooting.py`, `defending.py` | Pass/shot/tackle success is sampled from a probability derived from skill, distance, pressure and risk - never guaranteed |
| A* pathfinding | `src/ai/pathfinding.py` | Grid search around opponents, used only when a straight line is congested (checked before invoking, and cached per player) |
| Multi-agent coordination | `src/ai/coordination.py` | One shared "presser" per defending team, cover players, greedy threat-based marking assignment, a nominated support runner - so players react to teammates' roles instead of duplicating them |
| Dynamic tactical adaptation | `src/ai/tactics.py::dynamic_adaptation` | Pure function of (tactics, minute, own_score, opp_score) that raises/lowers pressing, line, risk and tempo late in a losing/winning match |
| Expected-goals (xG) shot model | `src/ai/shooting.py::compute_xg` | Logistic-style probability of a goal from distance, angle, shooter skill, pressure and goalkeeper quality |

## 5. Agent Architecture

- **Player agent** (`src/agents/player.py`): attributes (speed, passing, shooting, ...),
  live match state (position, stamina, current FSM state, `has_ball`), and a
  `DecisionRecord` of its most recent AI decision (action, utility, component breakdown,
  reasons) used for the explanation UI.
- **Goalkeeper** (`src/agents/goalkeeper.py`): specialised positioning (an arc between
  the ball and the goal centre) and distribution logic (short pass if safe, otherwise a
  long clearance).
- **Team** (`src/agents/team.py`): a roster plus a `TeamTactics` controller (Level 2) and
  running `TeamStats`.
- **Manager** (`src/agents/manager.py`): the user-facing control surface - pre-match
  setup and live quick-tactic commands (ATTACK / BALANCED / DEFEND / HIGH PRESS /
  COUNTER ATTACK).

## 6. Decision-Making Process

Each tick, for the player currently in possession:

1. Gather candidate actions: `DRIBBLE` (always), `PASS`/`CROSS` (if a teammate is in
   range), `SHOOT` (if within shooting range), `CLEAR_BALL` (if a defender is under
   pressure deep in their own third).
2. Score each candidate with its dedicated utility function (see formulas below).
3. Nudge scores by team mentality (attack/defend bias) and passing-risk style
   (possession teams favour passing over dribbling; counter-attack teams favour direct
   running).
4. Pick the maximum-utility candidate (`choose_best`).
5. Resolve the action probabilistically (e.g. `resolve_pass_outcome`), log the event and
   store a `DecisionRecord` with the full reasoning for AI Explanation Mode.

For every off-ball player, the FSM (`state_machine.next_state`) picks a phase from
possession state, coordination signals and stamina, and `positioning.anchor_position`
computes a formation-relative target that deforms with tactics and ball position.

**Utility formulas actually implemented:**

```
PassScore   = PassingLaneQuality + ReceiverSpace + DistanceAdvantage + TacticalValue
              + SkillBonus - InterceptionRisk - OpponentPressure - RangePenalty

ShotScore   = DistanceToGoal + AngleToGoal + ShootingAbility + SpaceAvailable
              - DefenderPressure - GoalkeeperDifficulty

DribbleScore = SpaceAhead + DribblingAbility + GoalProgress
               - DefenderPressure - BallLossRisk

ThreatLevel = OpponentGoalDanger + BallProgression + PlayerQuality + SpaceAvailable
```

## 7. Experiments

`src/simulation/experiments.py` runs many headless matches (no rendering) and aggregates
results, in two modes:

- **Tactics experiment** (default): Team A's style vs Team B's style over N matches -
  win/draw/loss counts, average goals, possession, pass accuracy.
- **AI-level comparison** (`--ai-comparison`): each baseline AI sophistication level
  (`RANDOM`, `RULE_BASED`, `UTILITY_BASED`) plays the full multi-agent AI to demonstrate
  that more sophisticated decision-making produces measurably better outcomes.

Four AI sophistication levels are implemented for this comparison
(`src/core/enums.py::AILevel`):

| Level | Ball-carrier decision policy |
|---|---|
| `RANDOM` | Uniformly random choice among legal actions |
| `RULE_BASED` | Fixed if/then priority rules (shoot if in range & unpressured, else pass if a teammate scores > 5, else dribble) |
| `UTILITY_BASED` | Full weighted utility scoring, but without dynamic in-match tactical adaptation |
| `FULL_MULTI_AGENT` | Utility scoring + dynamic tactical adaptation to score/time |

(Coordination - pressing/marking/covering - is always active for every level, so even
the `RANDOM` baseline has a functioning defence; the differentiator is decision quality
with the ball.)

## 8. Results

Run an experiment and interpret `results/*.csv` (one row per simulated match, all
`src/simulation/metrics.py::MatchMetrics` fields) plus the console summary:

```bash
python -m src.simulation.experiments --matches 50
python -m src.simulation.experiments --matches 50 --ai-comparison
```

See `docs/experiments.md` for a worked example and how to read the output.

## 9. Installation

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
```

Requires Python 3.11+ and no internet access at runtime (no external/paid APIs).

## 10. Usage

Play a match (menu -> live match -> post-match stats):

```bash
python main.py
```

In the pre-match menu: cycle **FORMATION**, **STYLE** and **MENTALITY** with the `<`/`>`
arrows, drag the **PRESSING INTENSITY**, **DEFENSIVE LINE** and **PASSING RISK** sliders,
then click **START MATCH**.

During the match:
- Click any player to inspect their latest AI decision in the **AI EXPLANATION** panel.
- Speed buttons (`0.5x`...`8x`) control simulation speed.
- **ATTACK / BALANCED / DEFEND / HIGH PRESS / COUNTER ATTACK** are live manager
  interventions applied to your team's tactics.
- Toggle **AI EXPLANATION** and **DEBUG PANEL** at the bottom of the screen.
- At halftime and full time, click anywhere to continue.

Run the test suite:

```bash
pytest
```

Run experiments:

```bash
python -m src.simulation.experiments --matches 50
```

## Project Structure

```
footballmind/
├── main.py                  # entry point (menu -> match -> stats)
├── requirements.txt
├── src/
│   ├── core/                # enums, vector math (shared, no circular deps)
│   ├── game/                # pitch, ball, match environment (Level 1)
│   ├── agents/               # player, goalkeeper, team, manager
│   ├── ai/                  # state machine, utility AI, passing, shooting,
│   │                         #   dribbling, defending, positioning, tactics,
│   │                         #   coordination, pathfinding (Levels 2 & 3)
│   ├── simulation/           # headless simulator, experiments, metrics
│   └── ui/                  # pygame menu, match view, panels, explanation
├── data/                    # reference JSON exports of attribute/tactics tables
├── tests/                   # pytest suite (10 files, one per AI subsystem)
├── docs/                    # architecture, AI algorithms, agent design,
│                             #   experiments guide, viva Q&A
└── results/                 # experiment CSV exports
```

## Limitations

- Physics is intentionally simplified (no ball bounce/spin, no offside, no throw-ins or
  corners as distinct restarts - a stopped/out-of-bounds ball is treated as an open
  contest for whoever reaches it first).
- Fouls exist but there is no free-kick set-piece phase; a foul is logged and possession
  usually stays live with a yellow card after repeated fouling.
- Pass completion and shot conversion rates are tuned for legible, watchable matches
  rather than calibrated against real professional statistics.
- The pygame UI favours clarity over visual polish, per the project's stated priority of
  AI correctness and explainability over graphics.
