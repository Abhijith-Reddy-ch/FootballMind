# AI Algorithms

Plain-language explanation of every AI technique used, why it was chosen, and where the
implementation lives.

## 1. Finite State Machine (FSM)

**File:** `src/ai/state_machine.py`

Every player sits in one `PlayerState` at a time (`IDLE`, `POSITIONING`, `ATTACKING`,
`DEFENDING`, `PRESSING`, `MARKING`, `RECEIVING`, `DRIBBLING`, `PASSING`, `SHOOTING`,
`TACKLING`, `RECOVERING`, `SUPPORT_ATTACK`). `next_state()` is a pure function of
`(player, team, ball, coordination_signals, is_own_possession, ball_is_loose)` -
transitions are deterministic, never random, e.g.:

- Ball carrier -> always `ATTACKING` (the actual skill - dribble/pass/shoot - is decided
  by the utility layer and overwrites the state for that tick).
- Stamina below 18% and the ball isn't loose -> `RECOVERING` (work-rate drops).
- Own team has the ball -> `SUPPORT_ATTACK` if nominated as the runner, `ATTACKING` for
  advanced roles, otherwise `POSITIONING`.
- Opponent has the ball -> `PRESSING` if this player is the team's designated presser,
  `MARKING` if assigned an opponent, `DEFENDING` otherwise.

**Why an FSM:** phase-of-play (what a player is broadly trying to do) is naturally
discrete and benefits from explicit, inspectable states - it's what the AI Explanation
panel shows first ("State: MARKING").

## 2. Utility-based decision making

**File:** `src/ai/utility_ai.py` (framework) + `passing.py`, `shooting.py`,
`dribbling.py`, `defending.py` (per-action evaluators)

Within a state (e.g. "I have the ball"), *which specific action* to take is chosen by
scoring every legal candidate and picking the maximum:

```python
ActionCandidate(action, utility, components={...}, reasons=[...])
best = max(candidates, key=lambda c: c.utility)
```

Each evaluator implements a weighted-sum formula over independently meaningful features
(see the exact formulas in the README's Decision-Making Process section). Every
component is retained in `components` and every qualitative reason in `reasons`, which
is exactly what AI Explanation Mode renders - nothing is invented for display, it's the
same numbers that decided the action.

**Why utility-based over pure rules:** a rule tree ("if pressured then pass, else if in
range then shoot...") cannot smoothly trade off multiple continuous factors (distance,
angle, pressure, teammate quality) the way a weighted sum can, and it becomes
combinatorially unmanageable as more factors are added. Utility scoring also degrades
gracefully - if no option is great, the AI still picks the *least bad* one instead of
falling through undefined rule branches.

## 3. Probabilistic outcome resolution

**Files:** `passing.py::resolve_pass_outcome`, `shooting.py::resolve_shot_outcome`,
`defending.py::resolve_tackle`

A high utility score means an action is *worth attempting*, not that it will *succeed*.
Success is sampled from `random.Random` (seeded via `Match.rng`) using a probability
built from the same underlying features:

```
pass success   = f(passer.passing skill, distance, interception risk)
shot outcome   = GOAL if roll < xG, else SAVE/BLOCKED/MISS by remaining probability mass
tackle outcome = WON if roll < f(tackling skill - dribbling skill, fatigue)
```

This keeps the simulation credible under repeated play - a fixed seed reproduces an
identical match (tested in `tests/test_match.py`), but different seeds produce
meaningfully different, non-scripted outcomes.

## 4. Expected Goals (xG) model

**File:** `src/ai/shooting.py::compute_xg`

A logistic-ish function of distance and the geometric shooting angle (computed correctly
via the dot-product angle between the two goalpost vectors, `core/vector.py::angle_between`,
which avoids the naive-atan2-subtraction wraparound bug that would otherwise misreport a
narrow angle as 180 degrees), scaled by shooter skill, defensive pressure and goalkeeper
positioning. This is the same modelling approach (though simplified) used in real
football analytics to estimate chance quality independent of the actual outcome.

## 5. A* pathfinding

**File:** `src/ai/pathfinding.py`

A coarse 3.5m grid over the 105x68m pitch. `is_congested()` first checks whether 2+
opponents sit within 2m of the straight line to a player's target; only then is
`astar()` invoked, and its result is cached per player (`PathCache`) until the target
moves >3m or ~0.75 simulated seconds pass. This satisfies the "use A* intelligently, not
every frame" requirement - most players most of the time just steer directly, which is
both cheaper and more natural-looking than grid-snapped movement everywhere.

## 6. Multi-agent coordination

**File:** `src/ai/coordination.py`

Players don't communicate directly (no message passing); they coordinate *indirectly*
through the shared `TeamSignals` computed once per team per tick:

- `presser_id`: the single nearest defender to the ball - everyone else stands down from
  pressing so the team doesn't send three players at one attacker.
- `cover_ids`: teammates near the presser who shift to cover passing lanes instead.
- `marking`: a greedy highest-threat-first assignment (`assign_marking` in
  `defending.py`) so each dangerous opponent gets exactly one marker.
- `support_runner_id`: one nominated attacker (not the ball carrier) told to make a
  forward run, so attackers spread out instead of clustering on the ball.

This is a blackboard-style coordination pattern: a single shared data structure that
every agent reads, rather than N^2 pairwise negotiation, which is both simpler to reason
about and cheap enough to recompute every tick for 22 players.

## 7. Dynamic tactical adaptation

**File:** `src/ai/tactics.py::dynamic_adaptation`

A pure function `(tactics, minute, own_score, opp_score) -> (new_tactics, reasons)`.
Losing with under 15 minutes left raises pressing/line/risk/tempo (more with under 5
minutes left); winning does the opposite. It's gated to fire once per "stage" per team
(`Team.adaptation_stage`) so it doesn't spam identical adjustments every tick, and every
firing is both logged to the match event feed and counted in `TeamStats.adaptation_events`
for the post-match "Tactical Adaptation Events" stat.

## 8. Spatial/threat reasoning for defence

**File:** `src/ai/defending.py::threat_level`

Every opponent is scored by proximity to the defended goal, how far they've progressed
the ball forward, their shooting/dribbling quality, and how much space they have - plus a
flat bonus if they currently hold the ball. `assign_marking` sorts opponents by this score
and greedily assigns the nearest free defender to each, most dangerous first, so defensive
attention concentrates on genuine threats rather than a fixed marking scheme.
