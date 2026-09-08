"""Match: Level 1 of the AI hierarchy - the environment. Owns ball, teams, clock, score
and the event log, and drives one simulation step (`tick`) per fixed timestep.

`tick` is the heart of the whole project: each call it (1) applies dynamic tactical
adaptation, (2) computes team coordination signals, (3) updates every player's FSM state
and movement target, (4) lets the ball carrier make a utility-scored decision
(pass/shoot/dribble/cross/clear), (5) resolves tackles, (6) steps ball physics, and
(7) resolves loose-ball possession changes and goals.
"""
from __future__ import annotations

import random
from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Dict, List, Optional

from src.core.enums import ActionType, AILevel, Mentality, MatchPhase, PlayerRole, PlayerState, Side
from src.core.vector import Vec2, v, distance, normalize, clamp, point_segment_distance
from src.agents.team import Team, substitute as substitute_player
from src.agents.player import DecisionRecord, Player
from src.agents.goalkeeper import gk_home_position, choose_distribution
from src.game.ball import Ball, POSSESSION_RADIUS
from src.game import pitch
from src.ai.positioning import slots_for, anchor_position, attacking_push, FORMATIONS
from src.ai.tactics import dynamic_adaptation
from src.ai.state_machine import next_state
from src.ai.coordination import compute_signals, pick_support_runner, TeamSignals
from src.ai.defending import assign_marking, evaluate_tackle, resolve_tackle
from src.ai.passing import best_pass, evaluate_cross, evaluate_clear, resolve_pass_outcome
from src.ai.shooting import evaluate_shot, resolve_shot_outcome
from src.ai.dribbling import evaluate_dribble
from src.ai.pathfinding import PathCache
from src.ai.utility_ai import ActionCandidate, choose_best

HALF_LENGTH_MIN = 45.0
MENTALITY_BIAS = {Mentality.ATTACK: 1.0, Mentality.BALANCED: 0.0, Mentality.DEFEND: -1.0}
TACKLE_RANGE = 2.3
TACKLE_COOLDOWN_TICKS = 20
PENDING_TIMEOUT_TICKS = 150
PICKUP_COOLDOWN_TICKS = 14  # prevents a player instantly re-collecting their own failed kick


@dataclass
class MatchEvent:
    minute: float
    text: str
    reason: Optional[str] = None


@dataclass
class Match:
    home: Team
    away: Team
    seed: int = 42
    ball: Ball = field(default_factory=Ball)
    minute: float = 0.0
    phase: MatchPhase = MatchPhase.KICKOFF
    events: List[MatchEvent] = field(default_factory=list)
    tick_count: int = 0
    rng: random.Random = field(default=None)
    minutes_per_sim_second: float = 0.55

    home_signals: TeamSignals = field(default_factory=TeamSignals)
    away_signals: TeamSignals = field(default_factory=TeamSignals)
    pending_pass: Optional[dict] = None
    decision_log: Deque[DecisionRecord] = field(default_factory=lambda: deque(maxlen=400))
    path_cache: PathCache = field(default_factory=PathCache)
    last_possession_side: Optional[Side] = None
    pickup_cooldowns: Dict[str, int] = field(default_factory=dict)

    def __post_init__(self):
        if self.rng is None:
            self.rng = random.Random(self.seed)
        self._place_kickoff(kicking_off=Side.HOME)
        self.phase = MatchPhase.FIRST_HALF
        self.log(0.0, "Kickoff - First Half begins")

    # ---- setup / restarts -------------------------------------------------
    def _place_kickoff(self, kicking_off: Side) -> None:
        for team in (self.home, self.away):
            slots = slots_for(team.tactics.formation)
            for player in team.players:
                slot = slots[player.slot_index]
                anchor = anchor_position(slot, team.is_home(), team.tactics, ball_x_frac=0.5)
                player.home_position = anchor
                player.position = anchor.copy()
                player.target_position = anchor.copy()
                player.state = PlayerState.POSITIONING
                player.has_ball = False
            team.adaptation_stage = 0
            team.just_lost_possession = False
        self.ball.position = pitch.CENTER.copy()
        self.ball.velocity = v(0.0, 0.0)
        self.ball.owner_id = None
        self.pending_pass = None
        kicker_team = self.home if kicking_off == Side.HOME else self.away
        striker = min(kicker_team.outfield(), key=lambda p: distance(p.position, pitch.CENTER))
        striker.position = pitch.CENTER.copy()
        self.ball.attach(striker.id, striker.position)
        striker.has_ball = True
        self.last_possession_side = kicking_off

    def log(self, minute: float, text: str, reason: Optional[str] = None) -> None:
        self.events.append(MatchEvent(minute=minute, text=text, reason=reason))

    def team_for(self, side: Side) -> Team:
        return self.home if side == Side.HOME else self.away

    def other_team(self, team: Team) -> Team:
        return self.away if team.side == Side.HOME else self.home

    def find_player(self, player_id: Optional[str]) -> Optional[Player]:
        if player_id is None:
            return None
        return self.home.by_id(player_id) or self.away.by_id(player_id)

    # ---- main loop ----------------------------------------------------------
    def tick(self, dt_real_seconds: float) -> None:
        if self.phase in (MatchPhase.HALFTIME, MatchPhase.FULL_TIME):
            return
        self.minute += dt_real_seconds * self.minutes_per_sim_second
        self.tick_count += 1
        dt = dt_real_seconds

        carrier = self.find_player(self.ball.owner_id)
        possession_side = carrier.side if carrier else None

        self._apply_dynamic_adaptation()
        self._compute_coordination(possession_side)
        self._update_off_ball_players(dt, carrier, possession_side)
        if carrier is not None:
            self._handle_ball_carrier(carrier, dt)
        self._handle_tackles(carrier)

        self.ball.update(dt)
        self._track_possession(possession_side)
        self._resolve_loose_ball()
        if self.tick_count % 30 == 0:
            self._check_auto_substitutions()

        self._advance_clock()

    # ---- tactics / coordination -------------------------------------------
    def _apply_dynamic_adaptation(self) -> None:
        for team in (self.home, self.away):
            if team.ai_level != AILevel.FULL_MULTI_AGENT:
                continue
            opp = self.other_team(team)
            diff = team.score - opp.score
            stage = 0
            if diff != 0 and self.minute >= 85:
                stage = 2
            elif diff != 0 and self.minute >= 75:
                stage = 1
            if stage > team.adaptation_stage:
                new_tactics, reasons = dynamic_adaptation(team.tactics, self.minute, team.score, opp.score)
                if reasons:
                    team.tactics = new_tactics
                    team.adaptation_stage = stage
                    team.stats.adaptation_events += 1
                    team.adaptation_log.extend(reasons)
                    for r in reasons:
                        self.log(self.minute, f"{team.name} tactical shift", reason=r)

    def _compute_coordination(self, possession_side: Optional[Side]) -> None:
        carrier_id = self.ball.owner_id
        home_marking = assign_marking(self.home, self.away, carrier_id)
        away_marking = assign_marking(self.away, self.home, carrier_id)

        self.home_signals = compute_signals(self.home, self.away, self.ball, home_marking,
                                             self.home.just_lost_possession)
        self.away_signals = compute_signals(self.away, self.home, self.ball, away_marking,
                                             self.away.just_lost_possession)

        if possession_side == Side.HOME:
            self.home_signals.support_runner_id = pick_support_runner(self.home, self.ball)
        elif possession_side == Side.AWAY:
            self.away_signals.support_runner_id = pick_support_runner(self.away, self.ball)

        self.home.just_lost_possession = False
        self.away.just_lost_possession = False

    def _signals_for(self, team: Team) -> TeamSignals:
        return self.home_signals if team.side == Side.HOME else self.away_signals

    # ---- off-ball movement --------------------------------------------------
    def _update_off_ball_players(self, dt: float, carrier: Optional[Player],
                                  possession_side: Optional[Side]) -> None:
        for team in (self.home, self.away):
            opp = self.other_team(team)
            signals = self._signals_for(team)
            is_own_possession = possession_side == team.side
            ball_is_loose = self.ball.is_loose()
            for player in team.players:
                if not player.on_pitch or player.id == (carrier.id if carrier else None):
                    continue
                state, reasons = next_state(player, team, self.ball, signals, is_own_possession,
                                             ball_is_loose)
                player.state = state
                target = self._movement_target(player, team, opp, signals, is_own_possession, state)
                sprint = state in (PlayerState.PRESSING, PlayerState.ATTACKING,
                                    PlayerState.SUPPORT_ATTACK, PlayerState.RECEIVING)
                obstacles = [o for o in (team.players + opp.players)
                             if o.id != player.id and o.on_pitch]
                if distance(player.position, target) > 8.0:
                    waypoint = self.path_cache.get_next_waypoint(player.id, player.position,
                                                                   target, obstacles, self.tick_count)
                else:
                    waypoint = target
                player.target_position = pitch.clamp_to_pitch(waypoint)
                player.move_towards(player.target_position, dt, sprint=sprint)
                player.regen_stamina(dt, intensity=0.75 if sprint else 0.2)
                player.last_decision = DecisionRecord(tick=self.tick_count, player_id=player.id,
                                                        state=state, action=ActionType.HOLD_POSITION,
                                                        utility=0.0, reasons=reasons)

    def _movement_target(self, player: Player, team: Team, opp: Team, signals: TeamSignals,
                          is_own_possession: bool, state: PlayerState) -> Vec2:
        if player.is_gk():
            return gk_home_position(player, self.ball.position, team.is_home())

        slot = FORMATIONS[team.tactics.formation][player.slot_index]
        anchor = anchor_position(slot, team.is_home(), team.tactics,
                                  ball_x_frac=self.ball.position[0] / pitch.LENGTH)
        if is_own_possession:
            bias = MENTALITY_BIAS[team.tactics.mentality]
            anchor = anchor + attacking_push(slot, team.is_home(), bias)

        if state == PlayerState.PRESSING:
            return self.ball.position.copy()
        if state == PlayerState.MARKING:
            marked = opp.by_id(signals.marking.get(player.id))
            if marked is not None:
                own_goal = pitch.own_goal_center_for(team.is_home())
                dirv = normalize(own_goal - marked.position)
                return marked.position + dirv * 2.0
        return anchor

    # ---- ball carrier decision ----------------------------------------------
    def _handle_ball_carrier(self, carrier: Player, dt: float) -> None:
        team = self.team_for(carrier.side)
        opp = self.other_team(team)

        if carrier.is_gk():
            self._handle_gk_carrier(carrier, team, opp)
            return

        candidate = self._decide_ball_action(carrier, team, opp)
        if candidate is None:
            candidate = evaluate_dribble(carrier, team, opp)

        if candidate.action == ActionType.SHOOT:
            self._execute_shot(carrier, candidate, team, opp)
        elif candidate.action in (ActionType.PASS, ActionType.CROSS):
            self._execute_pass(carrier, candidate, team, opp)
        elif candidate.action == ActionType.CLEAR_BALL:
            self._execute_clear(carrier, candidate, team)
        else:  # DRIBBLE
            carrier.state = PlayerState.DRIBBLING
            target = candidate.target_position if candidate.target_position is not None else carrier.position
            carrier.target_position = pitch.clamp_to_pitch(target)
            carrier.move_towards(carrier.target_position, dt, sprint=True)
            carrier.regen_stamina(dt, intensity=0.7)
            self.ball.position = carrier.position.copy()
            record = DecisionRecord(tick=self.tick_count, player_id=carrier.id,
                                     state=PlayerState.DRIBBLING, action=ActionType.DRIBBLE,
                                     utility=candidate.utility, reasons=candidate.reasons,
                                     components=candidate.components,
                                     target_position=candidate.target_position)
            carrier.last_decision = record
            self.decision_log.append(record)

    def _decide_ball_action(self, carrier: Player, team: Team, opp: Team) -> Optional[ActionCandidate]:
        level = team.ai_level

        if level == AILevel.RANDOM:
            options: List[ActionCandidate] = [evaluate_dribble(carrier, team, opp)]
            pass_c = best_pass(carrier, team, opp)
            if pass_c:
                options.append(pass_c)
            shot_c = evaluate_shot(carrier, team, opp)
            if shot_c:
                options.append(shot_c)
            chosen = self.rng.choice(options)
            chosen.reasons = ["Baseline random policy"]
            return chosen

        if level == AILevel.RULE_BASED:
            shot_c = evaluate_shot(carrier, team, opp)
            if shot_c and shot_c.components.get("_xg", 0) > 0.18 and shot_c.components["DefenderPressure"] > -6:
                shot_c.reasons = ["Rule: within range and low pressure -> shoot"]
                return shot_c
            pass_c = best_pass(carrier, team, opp)
            if pass_c and pass_c.utility > 5:
                pass_c.reasons = ["Rule: open teammate available -> pass"]
                return pass_c
            d = evaluate_dribble(carrier, team, opp)
            d.reasons = ["Rule: no better option -> dribble forward"]
            return d

        # UTILITY_BASED and FULL_MULTI_AGENT: full weighted scoring across all actions
        candidates: List[ActionCandidate] = [evaluate_dribble(carrier, team, opp)]
        pass_c = best_pass(carrier, team, opp)
        if pass_c:
            candidates.append(pass_c)
        shot_c = evaluate_shot(carrier, team, opp)
        if shot_c:
            candidates.append(shot_c)
        cross_c = evaluate_cross(carrier, team, opp)
        if cross_c:
            candidates.append(cross_c)
        clear_c = evaluate_clear(carrier, team, opp)
        if clear_c:
            candidates.append(clear_c)

        bias = MENTALITY_BIAS[team.tactics.mentality]
        style_bias = (50 - team.tactics.passing_risk) / 50.0  # + for possession, - for direct/counter styles
        tempo_bias = (team.tactics.tempo - 50) / 50.0  # + for fast circulation, - for slower/holding play
        for c in candidates:
            if c.action == ActionType.SHOOT:
                c.utility += bias * 4.0
            elif c.action == ActionType.DRIBBLE:
                c.utility += bias * 3.0 - style_bias * 4.0 - tempo_bias * 3.0
            elif c.action in (ActionType.PASS, ActionType.CROSS):
                c.utility += style_bias * 3.0 + tempo_bias * 3.0
        return choose_best(candidates)

    def _handle_gk_carrier(self, gk: Player, team: Team, opp: Team) -> None:
        gk.state = PlayerState.PASSING
        dist_option = choose_distribution(gk, team, opp)
        if dist_option is not None:
            self._execute_pass(gk, dist_option, team, opp)
        else:
            target = v(pitch.LENGTH * (0.55 if team.is_home() else 0.45), pitch.WIDTH / 2)
            clear = ActionCandidate(action=ActionType.CLEAR_BALL, utility=0.0, target_position=target,
                                     reasons=["No safe pass - goalkeeper clears long"])
            self._execute_clear(gk, clear, team)

    # ---- action execution -----------------------------------------------------
    def _label(self, team: Team) -> str:
        return "HOME" if team.is_home() else "AWAY"

    def _execute_pass(self, passer: Player, candidate: ActionCandidate, team: Team, opp: Team) -> None:
        receiver = team.by_id(candidate.target_id)
        if receiver is None:
            receiver = team.outfield()[0]
        risk = candidate.components.get("_interception_risk_pct", 25.0)
        outcome = resolve_pass_outcome(passer, receiver, risk, opp, self.rng)
        team.stats.passes_attempted += 1
        passer.stats["passes_attempted"] += 1
        is_cross = candidate.action == ActionType.CROSS
        verb = "crosses" if is_cross else "passes"

        if outcome == "COMPLETE":
            team.stats.passes_completed += 1
            passer.stats["passes_completed"] += 1
            target_pos = receiver.position.copy()
            pending_target_id = receiver.id
            self.log(self.minute, f"{self._label(team)} #{passer.number} {verb} to #{receiver.number}",
                      reason="; ".join(candidate.reasons))
        elif outcome == "INTERCEPTED":
            opponents = opp.outfield()
            interceptor = min(opponents, key=lambda o: point_segment_distance(
                o.position, passer.position, receiver.position)) if opponents else None
            opp.stats.interceptions += 1
            if interceptor is not None:
                interceptor.stats["interceptions"] += 1
                target_pos = interceptor.position.copy()
                pending_target_id = interceptor.id
                self.log(self.minute,
                          f"{self._label(opp)} #{interceptor.number} intercepts", reason="Cut out the pass")
            else:
                target_pos = receiver.position.copy()
                pending_target_id = None
        else:  # OUT_OF_PLAY
            overhit_dir = normalize(receiver.position - passer.position)
            target_pos = pitch.clamp_to_pitch(receiver.position + overhit_dir * 6.0)
            pending_target_id = None
            self.log(self.minute, f"{self._label(team)} #{passer.number} pass strays out of play")

        speed = (12.0 + passer.attributes.passing / 100.0 * 10.0) * (0.85 + team.tactics.tempo / 100.0 * 0.3)
        self.ball.kick(target_pos - passer.position, speed)
        passer.has_ball = False
        passer.state = PlayerState.PASSING
        self.pickup_cooldowns[passer.id] = self.tick_count + PICKUP_COOLDOWN_TICKS
        self.pending_pass = {"target_player_id": pending_target_id, "kind": "pass",
                              "start_tick": self.tick_count}
        record = DecisionRecord(tick=self.tick_count, player_id=passer.id, state=PlayerState.PASSING,
                                 action=candidate.action, utility=candidate.utility,
                                 reasons=candidate.reasons, components=candidate.components,
                                 target_id=receiver.id, target_position=target_pos)
        passer.last_decision = record
        self.decision_log.append(record)

    def _execute_shot(self, shooter: Player, candidate: ActionCandidate, team: Team, opp: Team) -> None:
        xg = candidate.components.get("_xg", 0.1)
        gk = opp.goalkeeper()
        outcome = resolve_shot_outcome(xg, gk, self.rng)
        team.stats.shots += 1
        shooter.stats["shots"] += 1
        target = candidate.target_position.copy()
        pending_target_id = None

        if outcome == "GOAL":
            team.stats.shots_on_target += 1
            target_y = clamp(target[1] + self.rng.uniform(-1.5, 1.5),
                              pitch.GOAL_Y_MIN + 0.3, pitch.GOAL_Y_MAX - 0.3)
            target = v(target[0], target_y)
        elif outcome == "SAVE":
            team.stats.shots_on_target += 1
            if gk is not None:
                target = gk.position.copy()
                pending_target_id = gk.id
        elif outcome == "BLOCKED":
            defenders = opp.outfield()
            if defenders:
                blocker = min(defenders, key=lambda d: distance(d.position, shooter.position))
                target = blocker.position.copy()
                pending_target_id = blocker.id
        else:  # MISS
            miss_x = target[0] + (4.0 if team.is_home() else -4.0)
            miss_y = clamp(target[1] + self.rng.uniform(-7.0, 7.0), 0.0, pitch.WIDTH)
            target = pitch.clamp_to_pitch(v(miss_x, miss_y))

        speed = 20.0 + shooter.attributes.shooting / 100.0 * 10.0
        self.ball.kick(target - shooter.position, speed)
        shooter.has_ball = False
        shooter.state = PlayerState.SHOOTING
        self.pickup_cooldowns[shooter.id] = self.tick_count + PICKUP_COOLDOWN_TICKS
        self.pending_pass = {"target_player_id": pending_target_id, "kind": "shot", "outcome": outcome,
                              "shooter_side": team.side, "start_tick": self.tick_count}
        self.log(self.minute, f"{self._label(team)} #{shooter.number} shoots (xG {xg:.2f}) -> {outcome}",
                  reason="; ".join(candidate.reasons))
        record = DecisionRecord(tick=self.tick_count, player_id=shooter.id, state=PlayerState.SHOOTING,
                                 action=ActionType.SHOOT, utility=candidate.utility,
                                 reasons=candidate.reasons, components=candidate.components,
                                 target_position=target)
        shooter.last_decision = record
        self.decision_log.append(record)

    def _execute_clear(self, carrier: Player, candidate: ActionCandidate, team: Team) -> None:
        target = candidate.target_position if candidate.target_position is not None else carrier.position
        speed = 18.0 + carrier.attributes.strength / 100.0 * 8.0
        self.ball.kick(pitch.clamp_to_pitch(target) - carrier.position, speed)
        carrier.has_ball = False
        carrier.state = PlayerState.PASSING
        self.pickup_cooldowns[carrier.id] = self.tick_count + PICKUP_COOLDOWN_TICKS
        self.pending_pass = {"target_player_id": None, "kind": "clear", "start_tick": self.tick_count}
        self.log(self.minute, f"{self._label(team)} #{carrier.number} clears the ball",
                  reason="; ".join(candidate.reasons))
        record = DecisionRecord(tick=self.tick_count, player_id=carrier.id, state=PlayerState.PASSING,
                                 action=ActionType.CLEAR_BALL, utility=candidate.utility,
                                 reasons=candidate.reasons, components=candidate.components,
                                 target_position=candidate.target_position)
        carrier.last_decision = record
        self.decision_log.append(record)

    # ---- defensive tackles ------------------------------------------------
    def _handle_tackles(self, carrier: Optional[Player]) -> None:
        if carrier is None:
            return
        team = self.team_for(carrier.side)
        opp = self.other_team(team)
        for defender in opp.outfield():
            if not defender.on_pitch:
                continue
            cooldown = opp.tackle_cooldowns.get(defender.id, 0)
            if cooldown > 0:
                opp.tackle_cooldowns[defender.id] = cooldown - 1
                continue
            if distance(defender.position, carrier.position) > TACKLE_RANGE:
                continue
            cand = evaluate_tackle(defender, carrier, opp)
            if cand.utility <= -2.0:
                continue
            opp.tackle_cooldowns[defender.id] = TACKLE_COOLDOWN_TICKS
            opp.stats.tackles += 1
            defender.stats["tackles"] += 1
            outcome = resolve_tackle(defender, carrier, self.rng)
            defender.state = PlayerState.TACKLING
            if outcome == "WON":
                opp.stats.tackles_won += 1
                defender.stats["tackles_won"] += 1
                carrier.has_ball = False
                self.ball.attach(defender.id, defender.position)
                defender.has_ball = True
                team.just_lost_possession = True
                self.log(self.minute, f"{self._label(opp)} #{defender.number} wins the ball",
                          reason=f"Tackling {defender.attributes.tackling} vs dribbling {carrier.attributes.dribbling}")
            elif outcome == "FOUL":
                defender.stats["fouls"] += 1
                defender.yellow_cards += (1 if defender.stats["fouls"] % 3 == 0 else 0)
                card_txt = " (YELLOW CARD)" if defender.yellow_cards and defender.stats["fouls"] % 3 == 0 else ""
                self.log(self.minute, f"Foul by {self._label(opp)} #{defender.number}{card_txt}")
            return  # only one tackle attempt resolves per tick to avoid a pile-on

    # ---- possession / loose ball -------------------------------------------
    def _track_possession(self, possession_side: Optional[Side]) -> None:
        if possession_side == Side.HOME:
            self.home.stats.possession_ticks += 1
        elif possession_side == Side.AWAY:
            self.away.stats.possession_ticks += 1

    def _all_on_pitch_players(self) -> List[Player]:
        return [p for p in (self.home.players + self.away.players) if p.on_pitch]

    def _attach_ball(self, player: Player) -> None:
        self.ball.attach(player.id, player.position)
        player.has_ball = True
        player.state = PlayerState.RECEIVING
        self.pending_pass = None

    def _resolve_loose_ball(self) -> None:
        if not self.ball.is_loose():
            return

        if self.pending_pass is not None:
            kind = self.pending_pass["kind"]
            if kind == "shot" and self.pending_pass.get("outcome") == "GOAL":
                shooter_side: Side = self.pending_pass["shooter_side"]
                home_line = shooter_side == Side.AWAY
                stuck = (self.tick_count - self.pending_pass["start_tick"]) > PENDING_TIMEOUT_TICKS
                if pitch.is_goal(self.ball.position, home_line) or stuck:
                    scoring = self.team_for(shooter_side)
                    conceding = self.other_team(scoring)
                    scoring.score += 1
                    scoring.stats.goals += 1
                    self.log(self.minute, f"GOAL! {self._label(scoring)} scores - "
                                           f"{self.home.name} {self.home.score} - {self.away.score} {self.away.name}")
                    self._place_kickoff(kicking_off=conceding.side)
                    return
                return  # ball is a confirmed goal in flight - no one can intercept it early

            target_player = self.find_player(self.pending_pass.get("target_player_id"))
            timed_out = (self.tick_count - self.pending_pass["start_tick"]) > PENDING_TIMEOUT_TICKS

            if target_player is not None and target_player.on_pitch:
                reached_target = distance(self.ball.position, target_player.position) < 1.9
                if reached_target or timed_out:
                    self._attach_ball(target_player)
                return  # still travelling to its intended recipient

            # No specific intended recipient (stray pass, clearance, deflection, miss): it's
            # an open contest - whoever (either team) reaches it first collects it.
            nearest = self._nearest_to_ball(radius=POSSESSION_RADIUS)
            if nearest is not None:
                self._attach_ball(nearest)
                return
            if timed_out:
                fallback = self._nearest_to_ball()
                if fallback is not None:
                    self._attach_ball(fallback)
                self.pending_pass = None
            return

        nearest = self._nearest_to_ball(radius=POSSESSION_RADIUS)
        if nearest is not None:
            self._attach_ball(nearest)

    def _nearest_to_ball(self, radius: Optional[float] = None) -> Optional[Player]:
        players = [p for p in self._all_on_pitch_players()
                   if self.tick_count >= self.pickup_cooldowns.get(p.id, 0)]
        if not players:
            return None
        candidates = players
        if radius is not None:
            candidates = [p for p in players if distance(p.position, self.ball.position) <= radius]
            if not candidates:
                return None
        return min(candidates, key=lambda p: distance(p.position, self.ball.position))

    # ---- substitutions -------------------------------------------------------
    MAX_SUBS_PER_TEAM = 3
    CRITICAL_STAMINA = 8.0

    def _check_auto_substitutions(self) -> None:
        """Section 14/22: an exhausted player is a tactical liability - if the bench has
        a fresh replacement, the manager (AI) makes the call automatically rather than
        leaving a player stranded at near-zero stamina for the rest of the match."""
        for team in (self.home, self.away):
            if team.subs_made >= self.MAX_SUBS_PER_TEAM or not team.subs:
                continue
            exhausted = [p for p in team.players
                         if p.on_pitch and not p.is_gk() and p.stamina < self.CRITICAL_STAMINA
                         and p.id != self.ball.owner_id]
            if not exhausted:
                continue
            worst = min(exhausted, key=lambda p: p.stamina)
            reason = substitute_player(team, worst.id, 0)
            if reason is not None:
                team.subs_made += 1
                self.log(self.minute, "Substitution", reason=reason)

    # ---- clock -------------------------------------------------------------
    def _advance_clock(self) -> None:
        if self.minute >= HALF_LENGTH_MIN and self.phase == MatchPhase.FIRST_HALF:
            self.phase = MatchPhase.HALFTIME
            self.log(self.minute, "Halftime")
        elif self.minute >= HALF_LENGTH_MIN * 2 and self.phase == MatchPhase.SECOND_HALF:
            self.phase = MatchPhase.FULL_TIME
            self.log(self.minute, f"Full Time: {self.home.name} {self.home.score} - "
                                   f"{self.away.score} {self.away.name}")

    def start_second_half(self) -> None:
        if self.phase != MatchPhase.HALFTIME:
            return
        self.phase = MatchPhase.SECOND_HALF
        self._place_kickoff(kicking_off=Side.AWAY)
        self.log(self.minute, "Second Half begins")

    def is_over(self) -> bool:
        return self.phase == MatchPhase.FULL_TIME
