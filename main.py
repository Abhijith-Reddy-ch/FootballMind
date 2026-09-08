"""FootballMind entry point: menu -> live match -> post-match statistics, one command:

    python main.py
"""
from __future__ import annotations

import sys

import pygame

from src.core.enums import AILevel, Mentality, Side, TacticalStyle
from src.agents.manager import ManagerController, MatchSetupConfig
from src.agents.team import build_team
from src.ai.tactics import preset_for
from src.game.match import Match
from src.ui import menu, panels
from src.ui.explanation import ExplanationState
from src.ui.match_view import draw_ball, draw_explanation_overlay, draw_pitch, draw_player, world_to_screen
from src.ui.widgets import Button

WINDOW_W, WINDOW_H = 1500, 900
PITCH_RECT = (20, 76, 950, 615)
FIXED_SIM_DT = 1 / 30
SPEED_OPTIONS = [0.5, 1, 2, 4, 8]


class Display:
    """Runs a real fullscreen surface at the desktop's native resolution, while every
    draw_*() function keeps drawing onto a fixed WINDOW_W x WINDOW_H canvas (so none of
    the hand-placed UI layout has to change) - the canvas is scaled and letterboxed onto
    the real screen once per frame, and mouse positions are mapped back the other way."""

    def __init__(self, fullscreen: bool = True):
        pygame.init()
        pygame.display.set_caption("FootballMind")
        if fullscreen:
            self.real_screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        else:
            self.real_screen = pygame.display.set_mode((WINDOW_W, WINDOW_H), pygame.RESIZABLE)
        self._recompute()
        self.canvas = pygame.Surface((WINDOW_W, WINDOW_H))

    def _recompute(self) -> None:
        real_w, real_h = self.real_screen.get_size()
        self.scale = max(0.1, min(real_w / WINDOW_W, real_h / WINDOW_H))
        self.scaled_w = int(WINDOW_W * self.scale)
        self.scaled_h = int(WINDOW_H * self.scale)
        self.offset_x = (real_w - self.scaled_w) // 2
        self.offset_y = (real_h - self.scaled_h) // 2

    def handle_resize(self, size) -> None:
        self.real_screen = pygame.display.set_mode(size, pygame.RESIZABLE)
        self._recompute()

    def to_canvas_pos(self, pos):
        return ((pos[0] - self.offset_x) / self.scale, (pos[1] - self.offset_y) / self.scale)

    def present(self) -> None:
        self.real_screen.fill((0, 0, 0))
        if abs(self.scale - 1.0) < 1e-6:
            scaled_surf = self.canvas
        else:
            scaled_surf = pygame.transform.smoothscale(self.canvas, (self.scaled_w, self.scaled_h))
        self.real_screen.blit(scaled_surf, (self.offset_x, self.offset_y))
        pygame.display.flip()


def new_match(setup: MatchSetupConfig, away_style: TacticalStyle, seed: int = None) -> Match:
    import random
    seed = seed if seed is not None else random.randrange(1_000_000)
    home_tactics = setup.to_tactics()
    away_tactics = preset_for(away_style, formation="4-4-2")
    home = build_team("Home FC", Side.HOME, (214, 69, 65), home_tactics, seed=seed + 1)
    away = build_team("Away United", Side.AWAY, (69, 120, 214), away_tactics, seed=seed + 2)
    return Match(home=home, away=away, seed=seed)


def build_control_buttons():
    speed_buttons = [Button((20, 705, 70, 34), f"{s}x") for s in SPEED_OPTIONS]
    manager_labels = ["ATTACK", "BALANCED", "DEFEND", "HIGH_PRESS", "COUNTER_ATTACK"]
    manager_buttons = [Button((20 + i * 130, 750, 120, 34), lbl.replace("_", " "))
                        for i, lbl in enumerate(manager_labels)]
    toggle_explain = Button((20, 795, 200, 34), "AI EXPLANATION: ON")
    toggle_debug = Button((230, 795, 200, 34), "DEBUG PANEL: ON")
    return speed_buttons, manager_labels, manager_buttons, toggle_explain, toggle_debug


MANAGER_ACTIVE_CHECK = {
    "ATTACK": lambda t: t.mentality == Mentality.ATTACK,
    "DEFEND": lambda t: t.mentality == Mentality.DEFEND,
    "BALANCED": lambda t: t.style == TacticalStyle.BALANCED and t.mentality == Mentality.BALANCED,
    "HIGH_PRESS": lambda t: t.style == TacticalStyle.HIGH_PRESS,
    "COUNTER_ATTACK": lambda t: t.style == TacticalStyle.COUNTER_ATTACK,
}


def draw_match_frame(screen, match, fonts, explain_state: ExplanationState,
                      speed_buttons, speed_index, manager_labels, manager_buttons,
                      toggle_explain, toggle_debug) -> None:
    font, font_bold, font_big = fonts
    screen.fill(theme_bg())
    panels.draw_hud(screen, (0, 0, WINDOW_W, 60), match, font_big, font)

    draw_pitch(screen, PITCH_RECT)
    for team in (match.home, match.away):
        for p in team.players:
            if not p.on_pitch:
                continue
            pos = world_to_screen(p.position, PITCH_RECT)
            draw_player(screen, font, pos, team.color, p.number, p.state, p.stamina,
                        selected=(p.id == explain_state.selected_id), has_ball=p.has_ball,
                        explain=explain_state.enabled)
    draw_ball(screen, world_to_screen(match.ball.position, PITCH_RECT))
    if explain_state.enabled:
        draw_explanation_overlay(screen, PITCH_RECT, match, explain_state.selected_id)

    right_x = PITCH_RECT[0] + PITCH_RECT[2] + 20
    right_w = WINDOW_W - right_x - 20
    panels.draw_explanation_panel(screen, (right_x, 66, right_w, 250), match,
                                   explain_state.selected_id, font, font_bold)
    if explain_state.show_debug_panel:
        panels.draw_debug_panel(screen, (right_x, 326, right_w, 210), match, font, font_bold)
        panels.draw_event_log(screen, (right_x, 546, right_w, WINDOW_H - 566), match, font, font_bold)
    else:
        panels.draw_event_log(screen, (right_x, 326, right_w, WINDOW_H - 346), match, font, font_bold)

    for i, b in enumerate(speed_buttons):
        b.active = i == speed_index
        b.draw(screen, font_bold)
    home_tactics = match.home.tactics
    for lbl, b in zip(manager_labels, manager_buttons):
        b.active = MANAGER_ACTIVE_CHECK[lbl](home_tactics)
        b.draw(screen, font)
    readout = (f"YOUR TACTICS -> Style: {home_tactics.style.value}   Mentality: {home_tactics.mentality.value}   "
               f"Press: {home_tactics.pressing_intensity}  Line: {home_tactics.defensive_line}  "
               f"Risk: {home_tactics.passing_risk}  Tempo: {home_tactics.tempo}")
    from src.ui import theme
    screen.blit(font.render(readout, True, theme.ACCENT), (690, 762))
    toggle_explain.label = f"AI EXPLANATION: {'ON' if explain_state.enabled else 'OFF'}"
    toggle_explain.active = explain_state.enabled
    toggle_debug.label = f"DEBUG PANEL: {'ON' if explain_state.show_debug_panel else 'OFF'}"
    toggle_debug.active = explain_state.show_debug_panel
    toggle_explain.draw(screen, font)
    toggle_debug.draw(screen, font)

    if match.phase.name == "HALFTIME":
        draw_overlay_message(screen, fonts, "HALFTIME - click anywhere to start the second half")
    elif match.is_over():
        draw_overlay_message(screen, fonts, "FULL TIME - click anywhere to view match statistics")


def theme_bg():
    from src.ui import theme
    return theme.BG


def draw_overlay_message(screen, fonts, text: str) -> None:
    font, font_bold, font_big = fonts
    overlay = pygame.Surface((WINDOW_W, WINDOW_H), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 160))
    screen.blit(overlay, (0, 0))
    surf = font_big.render(text, True, (255, 255, 255))
    screen.blit(surf, surf.get_rect(center=(WINDOW_W // 2, WINDOW_H // 2)))


def draw_stats_screen(screen, match, fonts) -> Button:
    from src.ui import theme
    font, font_bold, font_big = fonts
    screen.fill(theme.BG)
    title = font_big.render("MATCH RESULT", True, theme.TEXT)
    screen.blit(title, (60, 40))
    result = font_big.render(
        f"{match.home.name} {match.home.score} - {match.away.score} {match.away.name}", True, theme.ACCENT)
    screen.blit(result, (60, 90))

    home, away = match.home, match.away
    total_poss = max(1, home.stats.possession_ticks + away.stats.possession_ticks)
    home_pct = round(100 * home.stats.possession_ticks / total_poss)

    def pct(n, d):
        return round(100 * n / d) if d else 0

    home_dist = sum(p.distance_covered for p in home.players) / 1000.0
    away_dist = sum(p.distance_covered for p in away.players) / 1000.0

    rows = [
        ("Possession", f"{home_pct}%", f"{100 - home_pct}%"),
        ("Shots", home.stats.shots, away.stats.shots),
        ("Shots on Target", home.stats.shots_on_target, away.stats.shots_on_target),
        ("Pass Accuracy", f"{pct(home.stats.passes_completed, home.stats.passes_attempted)}%",
         f"{pct(away.stats.passes_completed, away.stats.passes_attempted)}%"),
        ("Tackles", home.stats.tackles, away.stats.tackles),
        ("Interceptions", home.stats.interceptions, away.stats.interceptions),
        ("Fouls", home.stats.fouls, away.stats.fouls),
        ("Distance Covered", f"{home_dist:.1f} km", f"{away_dist:.1f} km"),
        ("Tactical Adaptations", home.stats.adaptation_events, away.stats.adaptation_events),
    ]

    y = 160
    screen.blit(font_bold.render("HOME", True, theme.TEXT), (500, y))
    screen.blit(font_bold.render("AWAY", True, theme.TEXT), (700, y))
    y += 30
    for label, hval, aval in rows:
        screen.blit(font.render(label, True, theme.TEXT_DIM), (60, y))
        screen.blit(font.render(str(hval), True, theme.TEXT), (500, y))
        screen.blit(font.render(str(aval), True, theme.TEXT), (700, y))
        y += 30

    y += 20
    screen.blit(font_bold.render("AI PERFORMANCE", True, theme.ACCENT), (60, y))
    y += 28
    if match.decision_log:
        avg_util = sum(d.utility for d in match.decision_log) / len(match.decision_log)
    else:
        avg_util = 0.0
    ai_lines = [
        f"Average decision utility (confidence proxy): {avg_util:.1f}",
        f"Passing efficiency: HOME {pct(home.stats.passes_completed, home.stats.passes_attempted)}%"
        f"   AWAY {pct(away.stats.passes_completed, away.stats.passes_attempted)}%",
        f"Defensive efficiency (tackles won): HOME {pct(home.stats.tackles_won, home.stats.tackles)}%"
        f"   AWAY {pct(away.stats.tackles_won, away.stats.tackles)}%",
        f"Total AI decisions logged: {len(match.decision_log)}",
    ]
    for line in ai_lines:
        screen.blit(font.render(line, True, theme.TEXT), (60, y))
        y += 22

    again_btn = Button((WINDOW_W - 260, WINDOW_H - 90, 220, 56), "BACK TO MENU")
    again_btn.draw(screen, font_bold)
    return again_btn


def main() -> None:
    display = Display(fullscreen=True)
    screen = display.canvas
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("consolas,couriernew,monospace", 14)
    font_bold = pygame.font.SysFont("consolas,couriernew,monospace", 15, bold=True)
    font_big = pygame.font.SysFont("consolas,couriernew,monospace", 26, bold=True)
    fonts = (font, font_bold, font_big)

    app_state = "MENU"
    match: Match = None
    explain_state = ExplanationState()
    speed_index = SPEED_OPTIONS.index(1)
    tick_accumulator = 0.0
    speed_buttons, manager_labels, manager_buttons, toggle_explain, toggle_debug = build_control_buttons()
    manager: ManagerController = None
    stats_back_btn: Button = None

    while True:
        if app_state == "MENU":
            result = menu.run(display, clock, font, font_bold, font_big)
            if result is None:
                pygame.quit()
                sys.exit(0)
            setup, away_style_str = result
            away_style = TacticalStyle(away_style_str)
            match = new_match(setup, away_style)
            manager = ManagerController(match.home)
            explain_state = ExplanationState()
            speed_index = SPEED_OPTIONS.index(1)
            tick_accumulator = 0.0
            app_state = "MATCH"
            continue

        dt = clock.tick(60) / 1000.0

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit(0)
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                pygame.quit()
                sys.exit(0)
            if event.type == pygame.VIDEORESIZE:
                display.handle_resize(event.size)
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                pos = display.to_canvas_pos(event.pos)
                if app_state == "STATS":
                    if stats_back_btn is not None and stats_back_btn.hit(pos):
                        app_state = "MENU"
                    continue
                if app_state == "MATCH":
                    if match.phase.name == "HALFTIME":
                        match.start_second_half()
                        continue
                    if match.is_over():
                        app_state = "STATS"
                        continue
                    handled = False
                    for i, b in enumerate(speed_buttons):
                        if b.hit(pos):
                            speed_index = i
                            handled = True
                    for lbl, b in zip(manager_labels, manager_buttons):
                        if b.hit(pos):
                            manager.quick_command(lbl)
                            handled = True
                    if toggle_explain.hit(pos):
                        explain_state.toggle()
                        handled = True
                    if toggle_debug.hit(pos):
                        explain_state.toggle_debug()
                        handled = True
                    if not handled:
                        explain_state.pick_player(match, PITCH_RECT, pos)

        if app_state == "MATCH" and not match.is_over() and match.phase.name != "HALFTIME":
            tick_accumulator += SPEED_OPTIONS[speed_index]
            while tick_accumulator >= 1.0:
                match.tick(FIXED_SIM_DT)
                tick_accumulator -= 1.0

        if app_state == "MATCH":
            draw_match_frame(screen, match, fonts, explain_state, speed_buttons, speed_index,
                              manager_labels, manager_buttons, toggle_explain, toggle_debug)
        elif app_state == "STATS":
            stats_back_btn = draw_stats_screen(screen, match, fonts)

        display.present()


if __name__ == "__main__":
    main()
