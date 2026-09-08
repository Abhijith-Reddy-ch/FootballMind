# System Architecture

## Layered / hierarchical AI design

FootballMind implements the classic three-level hierarchical control structure used in
academic multi-agent game AI:

```
Level 1  ENVIRONMENT        src/game/match.py, ball.py, pitch.py
Level 2  TEAM AI (tactics)  src/ai/tactics.py, coordination.py
Level 3  PLAYER AGENTS      src/agents/player.py + src/ai/{state_machine,utility_ai,
                             passing,shooting,dribbling,defending,positioning,
                             pathfinding}.py
```

Each level only depends on the level(s) below it plus shared primitives in `src/core/`
(enums and vector math) - there are no upward dependencies, which keeps the AI modular
and independently testable (see `tests/`).

### Level 1: Environment (`Match`)

`Match` owns the objective, shared truth of the simulation: `Ball`, two `Team` objects
(each with 11 `Player`s), the clock/phase, score, and a chronological `MatchEvent` log.
It exposes one method, `tick(dt)`, which is called once per simulation step by either the
pygame UI (`main.py`) or the headless simulator (`src/simulation/simulator.py`). Nothing
outside `Match` mutates positions, score or possession directly - every change is a
consequence of an AI decision resolved inside `tick`.

`tick()` order of operations:

1. `_apply_dynamic_adaptation()` - Level 2, score/time-based tactics shift
2. `_compute_coordination()` - Level 2, shared signals for Level 3 to read
3. `_update_off_ball_players()` - Level 3, FSM + movement for every player without the ball
4. `_handle_ball_carrier()` - Level 3, utility-scored action for whoever has the ball
5. `_handle_tackles()` - Level 3, opportunistic tackle attempts near the carrier
6. `ball.update()` - simple physics integration (friction, boundary clamp)
7. `_resolve_loose_ball()` - possession changes, goal detection

### Level 2: Team AI

`TeamTactics` (`src/ai/tactics.py`) is an immutable snapshot of a team's playing
parameters: formation, style, mentality, pressing intensity, defensive line, passing
risk, width, tempo. Two things can change it during a match:

- **Dynamic adaptation** (`dynamic_adaptation`): a pure function of
  `(tactics, minute, own_score, opp_score)` that automatically raises attacking
  intensity when losing late, or lowers risk when winning late (section 14 of the spec).
- **Manager intervention** (`apply_manager_override`, exposed via
  `src/agents/manager.py::ManagerController`): the user's live quick-tactic buttons.

`compute_signals` (`src/ai/coordination.py`) is the Level 2 -> Level 3 bridge: once per
tick it designates a single presser (nearest defender to the ball), a set of cover
players, a greedy threat-based marking assignment, and (for the attacking team) one
support runner. Every player's Level 3 decision reads these signals rather than
recomputing them individually - this is what prevents 11 players from independently
converging on the ball (see `docs/agent_design.md` for why this produces emergent team
shape instead of a "blob").

### Level 3: Player Agents

Every player runs the same decision pipeline each tick:

```
game state --> FSM (state_machine.next_state) --> phase state
            --> positioning.anchor_position + coordination signals --> movement target
            --> [if ball carrier] utility_ai across passing/shooting/dribbling/
                defending evaluators --> chosen action --> probabilistic resolution
```

Pathfinding (`src/ai/pathfinding.py`) sits underneath movement: a direct line to the
target is used unless `is_congested()` finds 2+ obstacles within 2m of that line, in
which case a coarse-grid A* search produces a waypoint, cached per player and only
recomputed when the target moves more than 3m or after ~0.75s.

## Data flow diagram

```
┌────────────┐    tick(dt)    ┌──────────────────────────┐
│  main.py /  │───────────────▶│         Match             │
│ simulator.py│                │  (environment / Level 1)  │
└────────────┘                └─────────────┬─────────────┘
                                             │
                     ┌───────────────────────┼───────────────────────┐
                     ▼                       ▼                       ▼
             TeamTactics (HOME)      Ball physics/possession    TeamTactics (AWAY)
                     │                                                 │
                     ▼                                                 ▼
           coordination signals                             coordination signals
                     │                                                 │
        ┌────────────┼────────────┐                     ┌──────────────┼────────────┐
        ▼            ▼            ▼                     ▼              ▼             ▼
   Player 1 FSM  Player 2 FSM ... Player 11 FSM    Player 1 FSM   Player 2 FSM ... Player 11 FSM
        │            │            │                     │              │             │
        ▼ (if carrier) utility AI: pass/shoot/dribble/clear/cross, then probabilistic resolution
```

## Why this design is defensible as "real AI"

- No player behaviour is `if near_ball: chase_ball()`. Every action - including simple
  positioning - is derived from a scored evaluation of the current game state (see
  `docs/ai_algorithms.md` for the exact formulas) or a deterministic FSM transition keyed
  to possession/coordination/stamina, never a random or fixed rule tied only to distance.
- Outcomes are probabilistic, not scripted: a "good" pass can still be intercepted, a
  "good" shot can still be saved, because success is sampled from a probability derived
  from the same features that produced the utility score.
- The system is deterministic given a fixed seed (`Match(seed=...)`), which is what
  makes `tests/test_match.py::test_deterministic_with_fixed_seed` possible and lets
  experiment mode produce reproducible A/B comparisons.
