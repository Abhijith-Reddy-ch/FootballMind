"""Side/bottom UI panels: AI debug analytics, match event log, and the explanation panel
for whichever player is currently selected."""
from __future__ import annotations

from typing import List, Optional, Tuple

import pygame

from src.core.enums import Side
from src.ui import theme

Rect = Tuple[int, int, int, int]


def _panel_bg(surface: pygame.Surface, rect: Rect, title: str, font_bold: pygame.font.Font) -> int:
    x, y, w, h = rect
    pygame.draw.rect(surface, theme.PANEL_BG, rect, border_radius=6)
    pygame.draw.rect(surface, theme.PANEL_BORDER, rect, width=1, border_radius=6)
    label = font_bold.render(title, True, theme.ACCENT)
    surface.blit(label, (x + 10, y + 8))
    return y + 8 + label.get_height() + 6


def draw_debug_panel(surface, rect: Rect, match, font, font_bold) -> None:
    y = _panel_bg(surface, rect, "AI DEBUG", font_bold)
    x = rect[0] + 10
    home, away = match.home, match.away
    total_poss = max(1, home.stats.possession_ticks + away.stats.possession_ticks)
    home_pct = round(100 * home.stats.possession_ticks / total_poss)
    lines = [
        f"Possession   HOME {home_pct}%  AWAY {100 - home_pct}%",
        "",
        f"Passes       {home.stats.passes_attempted:>3} / {away.stats.passes_attempted:<3}"
        f"  ({home.stats.passes_completed} ok / {away.stats.passes_completed} ok)",
        f"Shots        {home.stats.shots:>3} / {away.stats.shots:<3}",
        f"Tackles      {home.stats.tackles:>3} / {away.stats.tackles:<3}"
        f"  (won {home.stats.tackles_won}/{away.stats.tackles_won})",
        f"Interceptions{home.stats.interceptions:>3} / {away.stats.interceptions:<3}",
        f"Adaptations  {home.stats.adaptation_events:>3} / {away.stats.adaptation_events:<3}",
        "",
        f"Agents active: {sum(1 for p in home.players + away.players if p.on_pitch)}",
        f"Decisions logged: {len(match.decision_log)}",
        f"Sim tick: {match.tick_count}",
    ]
    for i, line in enumerate(lines):
        surf = font.render(line, True, theme.TEXT)
        surface.blit(surf, (x, y + i * 18))


def draw_event_log(surface, rect: Rect, match, font, font_bold) -> None:
    y = _panel_bg(surface, rect, "MATCH EVENTS", font_bold)
    x = rect[0] + 10
    max_lines = (rect[1] + rect[3] - y) // 16
    events = list(match.events)[-max_lines:]
    for i, e in enumerate(events):
        text = f"{e.minute:5.1f}'  {e.text}"
        color = theme.GOOD if "GOAL" in e.text else theme.TEXT
        surf = font.render(text, True, color)
        surface.blit(surf, (x, y + i * 16))


def draw_explanation_panel(surface, rect: Rect, match, selected_id: Optional[str], font, font_bold) -> None:
    y = _panel_bg(surface, rect, "AI EXPLANATION", font_bold)
    x = rect[0] + 10
    if selected_id is None:
        surf = font.render("Click a player to inspect their latest AI decision.", True, theme.TEXT_DIM)
        surface.blit(surf, (x, y))
        return
    player = match.find_player(selected_id)
    if player is None:
        return
    header = f"#{player.number} {player.name}  ({player.role.value})  side {player.side.value}"
    surface.blit(font_bold.render(header, True, theme.TEXT), (x, y))
    y += 22
    surface.blit(font.render(f"State: {player.state.name}   Stamina: {player.stamina:.0f}%", True,
                              theme.TEXT_DIM), (x, y))
    y += 20
    dec = player.last_decision
    if dec is None:
        surface.blit(font.render("No decision recorded yet.", True, theme.TEXT_DIM), (x, y))
        return
    surface.blit(font_bold.render(f"Decision: {dec.action.name}"
                                   + (f" (utility {dec.utility:.0f})" if dec.components else ""),
                                   True, theme.ACCENT), (x, y))
    y += 20
    for comp, val in dec.components.items():
        if comp.startswith("_"):
            continue
        sign = "+" if val >= 0 else "-"
        color = theme.GOOD if val >= 0 else theme.BAD
        surface.blit(font.render(f"  {sign} {comp}: {val:+.1f}", True, color), (x, y))
        y += 16
    y += 4
    for r in dec.reasons:
        surface.blit(font.render(f"  * {r}", True, theme.TEXT), (x, y))
        y += 16


def draw_hud(surface, rect: Rect, match, font_big, font) -> None:
    x, y, w, h = rect
    pygame.draw.rect(surface, theme.PANEL_BG, rect)
    pygame.draw.rect(surface, theme.PANEL_BORDER, rect, width=1)
    title = font_big.render("FOOTBALLMIND", True, theme.TEXT)
    surface.blit(title, (x + 16, y + h // 2 - title.get_height() // 2))

    score_text = f"{match.home.name}  {match.home.score} - {match.away.score}  {match.away.name}"
    score_surf = font_big.render(score_text, True, theme.TEXT)
    surface.blit(score_surf, (x + w // 2 - score_surf.get_width() // 2, y + h // 2 - score_surf.get_height() // 2))

    minute = min(match.minute, 90.0)
    clock_text = f"{int(minute):02d}:{int((minute % 1) * 60):02d}   {match.phase.value}"
    clock_surf = font.render(clock_text, True, theme.TEXT_DIM)
    surface.blit(clock_surf, (x + w - clock_surf.get_width() - 16, y + h // 2 - clock_surf.get_height() // 2))
