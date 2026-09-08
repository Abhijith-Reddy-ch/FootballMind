# Agent Design

## What makes a Player an autonomous agent

Each `Player` (`src/agents/player.py`) satisfies the standard autonomous-agent
properties:

- **Perceives** its environment: on every tick it has access to its own position/
  stamina, the ball, its team's tactics and coordination signals, and (via `Team`/`Match`)
  every teammate's and opponent's position.
- **Decides** independently: `next_state()` and (when it has the ball) the utility
  evaluators run per-player, producing a decision specific to that agent's attributes,
  position and role - two players in the same broad situation with different `dribbling`
  or `passing` ratings will choose differently.
- **Acts** on the environment: movement, passing, shooting, tackling all mutate shared
  state (ball possession, position) that other agents then perceive on the next tick.
- **Is goal-directed but not omniscient**: an agent optimises its own utility function
  given locally-available information plus a small set of team-level shared signals
  (Level 2) - it does not have access to a global optimal plan.

## Player agent internals

```
Player
├── identity: id, number, name, role (PlayerRole), side
├── attributes: Attributes (speed, passing, shooting, dribbling, tackling, defending,
│                            vision, decision_making, positioning, strength, stamina)
├── live state: position, velocity, stamina, PlayerState, has_ball, marking_target_id
├── per-match stats: passes/shots/tackles/interceptions/fouls counters
└── last_decision: DecisionRecord (action, utility, components, reasons, target)
```

`Attributes` are not cosmetic - every one of them is read by at least one AI function:

| Attribute | Used by |
|---|---|
| `speed`, `acceleration` | `effective_speed()` (movement) |
| `stamina` | endurance factor in drain/regen rate |
| `passing`, `vision` | `passing.evaluate_pass` skill bonus, `resolve_pass_outcome` |
| `shooting` | `shooting.compute_xg`, `evaluate_shot` |
| `dribbling` | `dribbling.evaluate_dribble`, opposed against defenders' `tackling` |
| `tackling`, `defending` | `defending.tackle_success_probability`, `threat_level` |
| `positioning` | goalkeeper shot-stopping difficulty |
| `strength` | clearance kick power |

## Team agent (Level 2 controller)

`Team` (`src/agents/team.py`) is not itself an "agent" in the perceive/decide/act sense -
it's a container for a roster plus the `TeamTactics` that every one of its 11 player
agents reads. Its role is to hold the parameters that shape *how* the individual agents
weigh their utility components (e.g. `passing_risk` shifts the pass/dribble balance,
`defensive_line` shifts every outfield player's anchor position).

## Goalkeeper specialisation

`Goalkeeper` behaviour is not a separate class but a set of functions
(`src/agents/goalkeeper.py`) invoked when `player.is_gk()`: arc positioning between the
ball and goal centre (`gk_home_position`) and pass-or-clear distribution logic
(`choose_distribution`) reusing the same `passing.best_pass` utility evaluator as
outfield players.

## Manager (the user's agent)

`ManagerController` (`src/agents/manager.py`) is the interface between the human user and
the Level 2 tactics layer - it never touches player state directly. Pre-match, the user's
choices become a `TeamTactics` via `MatchSetupConfig.to_tactics()`; mid-match, quick
commands (`ATTACK`/`DEFEND`/`HIGH_PRESS`/...) call `apply_manager_override`, exactly the
same function used internally by dynamic adaptation - the manager and the AI's own
adaptation logic modify tactics through one consistent path.

## Handling contention: what happens if two agents want the same thing?

- **Two players wanting the same ball**: whichever player's tick loop processes first
  and gets within `POSSESSION_RADIUS` (1.1m) attaches the ball
  (`Match._resolve_loose_ball` / `_nearest_to_ball` picks the single nearest candidate
  across both teams, so it's always resolved to exactly one agent, never split).
- **Two defenders wanting to mark the same opponent**: `assign_marking` is a greedy
  highest-threat-first assignment with a `used_defenders` set, so no defender is ever
  double-assigned and no opponent gets two markers while another goes free.
- **Two defenders wanting to press**: only the single nearest defender to the ball is
  given the `PRESSING` state; teammates within 12m fall back to `cover_ids`
  (`DEFENDING`, covering a passing lane) instead of also chasing the ball.
- **Two attackers wanting to make the same run**: only one off-ball attacker is
  nominated `support_runner_id` per tick (`coordination.pick_support_runner`); others
  fall back to their formation anchor.

## Emergent behaviour

No code explicitly states "form a back four" or "overlap the fullback" - those shapes
emerge from: (a) formation anchors deforming with tactics and ball position
(`positioning.anchor_position`), (b) the coordination layer preventing duplicate
pressing/marking, and (c) each player's local utility optimisation. The result is that a
POSSESSION-style team visibly holds a compact passing shape while a COUNTER_ATTACK team
visibly sits deeper and breaks forward directly - a property that only holds because the
behaviour is generated, not scripted per formation.
