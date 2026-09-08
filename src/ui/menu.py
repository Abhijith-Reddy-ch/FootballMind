"""Pre-match manager setup screen (section 22): choose formation, tactical style,
mentality, pressing intensity, defensive line and passing risk for the user's team."""
from __future__ import annotations

import random
from dataclasses import dataclass

import pygame

from src.core.enums import Mentality, TacticalStyle
from src.agents.manager import MatchSetupConfig
from src.ai.positioning import FORMATIONS
from src.ui import theme
from src.ui.widgets import Button, OptionSelector, Slider

FORMATION_NAMES = list(FORMATIONS.keys())
STYLE_NAMES = [s.value for s in TacticalStyle]
MENTALITY_NAMES = [m.value for m in Mentality]


def run(display, clock, font, font_bold, font_big) -> "MatchSetupConfig | None":
    screen = display.canvas
    w, h = screen.get_size()
    formation_sel = OptionSelector((60, 140, 260, 70), "FORMATION", FORMATION_NAMES, index=0)
    style_sel = OptionSelector((340, 140, 260, 70), "STYLE", STYLE_NAMES,
                                index=STYLE_NAMES.index(TacticalStyle.BALANCED.value))
    mentality_sel = OptionSelector((620, 140, 260, 70), "MENTALITY", MENTALITY_NAMES,
                                    index=MENTALITY_NAMES.index(Mentality.BALANCED.value))

    press_slider = Slider((60, 270, 300, 50), "PRESSING INTENSITY", 50)
    line_slider = Slider((60, 340, 300, 50), "DEFENSIVE LINE", 50)
    risk_slider = Slider((60, 410, 300, 50), "PASSING RISK", 50)

    start_btn = Button((w - 240, h - 90, 180, 56), "START MATCH")
    away_names = [s.value for s in TacticalStyle if s != TacticalStyle.BALANCED]
    away_style_preview = random.choice(away_names)

    dragging_slider = None
    running = True
    while running:
        dt = clock.tick(60) / 1000.0
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return None
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                return None
            if event.type == pygame.VIDEORESIZE:
                display.handle_resize(event.size)
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                pos = display.to_canvas_pos(event.pos)
                if not (formation_sel.handle_click(pos) or style_sel.handle_click(pos)
                        or mentality_sel.handle_click(pos)):
                    for s in (press_slider, line_slider, risk_slider):
                        if s.handle_click(pos):
                            dragging_slider = s
                            break
                if start_btn.hit(pos):
                    style = TacticalStyle(style_sel.value())
                    mentality = Mentality(mentality_sel.value())
                    return MatchSetupConfig(
                        formation=formation_sel.value(), style=style, mentality=mentality,
                        pressing_intensity=press_slider.value, defensive_line=line_slider.value,
                        passing_risk=risk_slider.value,
                    ), away_style_preview
            if event.type == pygame.MOUSEBUTTONUP:
                dragging_slider = None
            if event.type == pygame.MOUSEMOTION and dragging_slider is not None:
                dragging_slider.handle_click(display.to_canvas_pos(event.pos))

        screen.fill(theme.BG)
        title = font_big.render("FOOTBALLMIND", True, theme.TEXT)
        subtitle = font.render("Set up your team's tactics before kickoff  (Esc to quit)", True, theme.TEXT_DIM)
        screen.blit(title, (60, 40))
        screen.blit(subtitle, (60, 40 + title.get_height() + 4))

        formation_sel.draw(screen, font, font_bold)
        style_sel.draw(screen, font, font_bold)
        mentality_sel.draw(screen, font, font_bold)
        press_slider.draw(screen, font)
        line_slider.draw(screen, font)
        risk_slider.draw(screen, font)

        info_lines = [
            f"Opponent (Away United) will play a contrasting {away_style_preview} style.",
            "Tip: during the match you can issue quick tactical commands and toggle",
            "AI Explanation Mode to see why each player made a decision.",
        ]
        for i, line in enumerate(info_lines):
            screen.blit(font.render(line, True, theme.TEXT_DIM), (60, 480 + i * 22))

        start_btn.draw(screen, font_bold)
        display.present()
    return None
