# Viva Questions and Answers

### 1. Why is this a multi-agent system?

There are 22 independent decision-making entities (players) sharing one environment
(the pitch, ball, clock), each perceiving state and acting to affect that shared state,
with only indirect coordination (shared blackboard signals, not direct messaging). That
is the definition of a multi-agent system, as opposed to a single controller driving 22
puppets.

### 2. What makes a player an autonomous agent, specifically?

Each `Player` independently perceives game state (position, ball, teammates, opponents,
tactics, stamina), decides an action via its own FSM state and (when relevant) its own
utility evaluation using its own attributes, and acts by mutating its own
position/possession. No central process decides for all 22 players at once - `Match.tick`
just calls each player's decision pipeline in turn.

### 3. Why use utility-based AI instead of a decision tree or scripted behaviour?

A utility function can smoothly combine several continuous, competing factors (distance,
angle, pressure, teammate quality, risk) into one comparable score, and always produces
a "least bad" choice even when no option is clearly good - a hand-written rule tree
either can't express these trade-offs cleanly or grows combinatorially as more factors
are added, and tends to have undefined behaviour in edge cases the author didn't
anticipate.

### 4. Why use a finite state machine as well, rather than utility AI alone?

The *phase* of play (broadly: am I attacking, defending, marking, recovering?) is a
naturally discrete, low-frequency-changing property that benefits from explicit,
inspectable states and deterministic transition rules - it's cheaper to reason about and
to display ("State: PRESSING") than re-deriving it from a utility score every tick. The
FSM handles *what mode am I in*; utility AI handles *which specific action within that
mode*.

### 5. How does tactical adaptation work?

`dynamic_adaptation(tactics, minute, own_score, opp_score)` in `src/ai/tactics.py` is a
pure function: if losing with under 15 (or 5) minutes left, it raises pressing intensity,
defensive line, passing risk and tempo; if winning, it lowers them. It's gated by a
per-team `adaptation_stage` so each threshold only fires once, and every firing is logged
with its reasons to the match event feed - fully deterministic and explainable, not
random.

### 6. How is coordination achieved without direct agent-to-agent communication?

Through a shared "blackboard": once per team per tick, `coordination.compute_signals`
computes `TeamSignals` (one presser, a cover set, a greedy marking assignment, one
support runner) from the team's own state. Every player then reads these signals as
inputs to its own FSM/utility decision. This is indirect coordination - no player ever
sends another player a message - but it still prevents duplicated effort (e.g. three
players all pressing the ball at once).

### 7. Where is planning used in this system?

Two places: (a) A* pathfinding plans a multi-step route around congestion rather than
reacting frame-by-frame; (b) the manager's pre-match tactical setup is a short-horizon
plan (formation + style) that constrains every subsequent per-tick decision for the
whole match, and dynamic adaptation is a simple time-horizon plan ("if still losing at
minute 75, become more attacking").

### 8. Where is pathfinding used, and why not use it for every movement?

`src/ai/pathfinding.py` implements A* over a coarse 3.5m grid. It's only invoked when
`is_congested()` detects 2+ opponents within 2m of the direct line to a target - most
open-field movement just steers straight there, which is both cheaper and looks more
natural. When it is used, the resulting path is cached per player and only recomputed
when the target moves significantly, to avoid recomputing A* every tick for 22 players.

### 9. What is the difference between rule-based and utility-based AI in this project?

`AILevel.RULE_BASED` (`Match._decide_ball_action`) uses fixed if/then priority: shoot if
in range and lightly pressured, else pass if a teammate scores above a fixed threshold,
else dribble. `AILevel.UTILITY_BASED`/`FULL_MULTI_AGENT` score every candidate action on
a continuous weighted formula and take the maximum - it can, for example, choose a
mediocre pass over a slightly-better-but-still-poor shot when both are bad options, which
a rule-based cutoff cannot express.

### 10. What happens if two agents want the same position or resource (e.g. the ball)?

The ball: `Match._resolve_loose_ball` always resolves to a single nearest eligible
player across both teams (`_nearest_to_ball`), so possession never splits or duplicates.
Marking: `defending.assign_marking` is a greedy algorithm with a `used_defenders` set, so
no defender is assigned twice and no dangerous opponent goes unmarked while a
lower-threat opponent gets two markers. Pressing: only the single nearest defender is
given the `PRESSING` state per tick; others fall back to covering.

### 11. How do you measure AI performance?

`src/simulation/metrics.py::MatchMetrics` tracks, per match: goals, possession share,
pass attempts/completions (-> pass accuracy), shots, tackles/tackles won, interceptions,
fouls, tactical adaptation events, average stamina, distance covered, total AI decisions
logged, and average per-tick decision latency (wall-clock ms). Experiment mode
(`src/simulation/experiments.py`) aggregates these across N matches into win/draw/loss
counts and averages, exported to CSV for offline analysis.

### 12. What makes the team's behaviour "emergent" rather than scripted?

No code states "form a back four" or "the fullback should overlap." Those shapes result
from formation anchors deforming with live tactics/ball position, coordination
preventing duplicate effort, and each player independently optimising its own utility
function given its own attributes and role. Two different tactical style presets produce
visibly different, unscripted team shapes and passing patterns from the exact same
underlying code.

### 13. Why is the simulation deterministic given a fixed seed, and why does that matter?

`Match.rng = random.Random(seed)` and roster generation both derive from the passed
seed, and every probabilistic resolution (pass/shot/tackle outcomes, random-baseline
action choice) draws from that single RNG stream in a fixed call order. This lets
`tests/test_match.py::test_deterministic_with_fixed_seed` prove reproducibility, and lets
experiment mode compare configurations fairly (each match still gets a distinct seed, but
re-running the whole experiment is reproducible end-to-end).

### 14. How does the passing AI decide who to pass to?

`passing.best_pass` evaluates every teammate within range with `evaluate_pass`, which
scores passing-lane quality (distance from the nearest opponent to the straight-line
lane), space around the receiver, forward progress, a tactics-driven bonus/penalty for
risk appetite, passer/receiver skill, and penalises interception risk, opponent pressure
on the passer, and excessive distance. The highest-scoring teammate is chosen; success is
then resolved probabilistically, not guaranteed.

### 15. How does the shooting AI decide whether to shoot?

`shooting.evaluate_shot` only considers shooting within `MAX_SHOOT_RANGE` (32m), scores
distance, the true geometric shooting angle, shooter skill, space, defender pressure and
goalkeeper positioning into a utility, and separately computes an xG-style probability
(`compute_xg`) used to resolve GOAL/SAVE/BLOCKED/MISS. A high utility means the shot is
worth taking relative to alternatives; xG independently governs whether it goes in.

### 16. How does defensive marking decide who marks whom?

`defending.threat_level` scores every opponent by proximity to the defended goal, ball
progression, shooting/dribbling quality, space, and a bonus if they hold the ball.
`assign_marking` sorts opponents by that score (most dangerous first) and greedily
assigns each the nearest still-unassigned defender.

### 17. How does stamina affect decisions, not just visuals?

`Player.effective_speed()` scales top speed down as stamina drops (fatigue factor).
Below `LOW_STAMINA_THRESHOLD` (18%) the FSM forces `RECOVERING`, which reduces movement
intensity and stamina drain rate. Fatigue is also a direct negative term in
`dribbling.evaluate_dribble`'s `BallLossRisk` component and in
`defending.tackle_success_probability`, so a tired player is measurably more likely to
lose the ball while dribbling and less likely to win a tackle - not just slower on
screen.

### 18. How are player attributes actually used, beyond flavour text?

See the attribute-usage table in `docs/agent_design.md`: every one of the twelve
attributes feeds at least one concrete formula (e.g. `shooting` -> xG, `tackling` vs
opponent `dribbling` -> tackle probability, `vision` -> pass skill bonus,
`stamina` -> endurance/drain rate). None are decorative.

### 19. How do formations "dynamically deform" instead of being fixed grids?

`positioning.anchor_position` converts a formation's *relative* slot (x/y fractions) into
a live meter position that shifts with `defensive_line` (whole block up/down the pitch),
`width` (spread across the pitch), and the ball's current x-position (a small pull
towards the ball for compactness) - so the same "4-3-3" looks different when parked deep
versus pressing high, and compacts around wherever the ball currently is.

### 20. What's the difference between the four AI levels used in experiments?

`RANDOM` picks uniformly among legal actions; `RULE_BASED` uses fixed priority rules;
`UTILITY_BASED` uses full weighted-utility scoring but no dynamic tactical adaptation;
`FULL_MULTI_AGENT` adds dynamic adaptation to score/time. All four still get full
coordination (pressing/marking/covering) so even the weakest baseline has a working
defence - the differentiator is decision *quality* with the ball and adaptiveness over
the match, which experiment mode is designed to surface as a measurable performance
gradient.

### 21. Why is A* run on a coarse grid rather than the exact pitch coordinates?

A grid at true (sub-meter) resolution over 105x68m would be tens of thousands of cells,
expensive to search 22 times a tick. A 3.5m cell grid (~30x20 cells) is coarse enough to
be searched cheaply while still being fine enough to route around clusters of players,
and is only searched when actually congested, further limiting cost.

### 22. How is a pass or shot's success actually resolved - is it ever guaranteed?

Never guaranteed. `resolve_pass_outcome`/`resolve_shot_outcome`/`resolve_tackle` each
compute a probability from skill/distance/pressure/risk, then draw one `Match.rng.random()`
sample against it. A very high-utility action is very likely, not certain, to succeed -
which is what lets a weaker team occasionally score against a stronger one.

### 23. Why does the ball carrier's dribble target recompute every tick instead of planning ahead?

`dribbling.evaluate_dribble` proposes a point ~6m ahead in the attacking direction each
tick, scored by the space actually available there right now - since defenders are also
moving every tick, a longer-horizon dribble plan would go stale almost immediately; a
locally-optimal, frequently-recomputed target is more robust here than a stale multi-step
plan, and is still constrained by the same utility competition against passing/shooting
each tick (so a player won't blindly keep dribbling into a closing gap if a pass scores
higher).

### 24. How does the goalkeeper differ from an outfield player?

Same `Player` class and same underlying decision framework, but two specialised
functions swap in when `player.is_gk()`: `gk_home_position` (an arc between the ball and
the goal centre instead of a formation anchor) and `choose_distribution` (reuses
`passing.best_pass`, falling back to a long clearance if no safe pass scores above a
threshold) instead of the outfield dribble/shoot/cross action set.

### 25. What are the known limitations, and why were they accepted?

No offside, no set-piece restarts (throw-ins/corners are simplified to an "open contest"
for the stopped ball), and pass/shot success rates are tuned for a legible, watchable
match rather than calibrated to real-world statistics. These were accepted deliberately
per the project's own priority ordering (section 38/39 of the brief): a simplified but
functional simulation that demonstrates genuine AI decision-making is more valuable,
academically, than a physically exhaustive rules engine with weaker AI.

### 26. Why is possession tracked in ticks rather than distinct "possessions"?

`TeamStats.possession_ticks` increments once per simulation tick for whichever team's
player currently holds the ball; the percentage is simply
`team_ticks / (team_ticks + opponent_ticks)`. This is simpler and more granular than
counting discrete possession phases, and matches how real match-analysis possession
percentages are typically computed (time-based, not event-based).

### 27. How would you extend this system to add a new tactical style?

Add a new `TacticalStyle` enum value and a corresponding `TeamTactics` preset in
`STYLE_PRESETS` (`src/ai/tactics.py`) - every existing evaluator (positioning, passing,
dribbling) already reads `defensive_line`/`width`/`passing_risk`/`pressing_intensity`
generically, so a new preset immediately produces different emergent behaviour with no
other code changes. This is the direct payoff of keeping tactics as data (a dataclass of
numeric parameters) rather than style-specific branching code.
