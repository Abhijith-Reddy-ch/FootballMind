"""Pitch + player + ball rendering, and world<->screen coordinate conversion."""
from __future__ import annotations

import math
from typing import Optional, Tuple

import pygame

from src.core.enums import PlayerState, Side
from src.game import pitch as P
from src.ui import theme

Rect = Tuple[int, int, int, int]  # x, y, w, h


def world_to_screen(pos, rect: Rect) -> Tuple[int, int]:
    x0, y0, w, h = rect
    sx = x0 + (pos[0] / P.LENGTH) * w
    sy = y0 + (pos[1] / P.WIDTH) * h
    return int(sx), int(sy)


def scale_len(meters: float, rect: Rect, axis: str = "x") -> float:
    _, _, w, h = rect
    return meters * (w / P.LENGTH if axis == "x" else h / P.WIDTH)


def draw_pitch(surface: pygame.Surface, rect: Rect) -> None:
    x0, y0, w, h = rect
    stripes = 10
    stripe_w = w / stripes
    for i in range(stripes):
        color = theme.PITCH_GREEN_A if i % 2 == 0 else theme.PITCH_GREEN_B
        pygame.draw.rect(surface, color, (x0 + i * stripe_w, y0, stripe_w + 1, h))

    line = theme.PITCH_LINE
    pygame.draw.rect(surface, line, (x0, y0, w, h), width=2)
    mid_x = x0 + w // 2
    pygame.draw.line(surface, line, (mid_x, y0), (mid_x, y0 + h), 2)

    center = world_to_screen(P.CENTER, rect)
    radius = int(scale_len(P.CENTER_CIRCLE_RADIUS, rect, "x"))
    pygame.draw.circle(surface, line, center, radius, 2)
    pygame.draw.circle(surface, line, center, 3)

    for is_home in (True, False):
        pen_depth = scale_len(P.PENALTY_AREA_DEPTH, rect, "x")
        pen_w = scale_len(P.PENALTY_AREA_WIDTH, rect, "y")
        goal_depth = scale_len(P.GOAL_AREA_DEPTH, rect, "x")
        goal_w = scale_len(P.GOAL_AREA_WIDTH, rect, "y")
        pen_y = y0 + (h - pen_w) / 2
        goal_y = y0 + (h - goal_w) / 2
        if is_home:
            pen_x, goal_x = x0, x0
        else:
            pen_x, goal_x = x0 + w - pen_depth, x0 + w - goal_depth
        pygame.draw.rect(surface, line, (pen_x, pen_y, pen_depth, pen_w), 2)
        pygame.draw.rect(surface, line, (goal_x, goal_y, goal_depth, goal_w), 2)

        goal_w_screen = scale_len(P.GOAL_WIDTH, rect, "y")
        goal_y2 = y0 + (h - goal_w_screen) / 2
        gx = x0 if is_home else x0 + w
        pygame.draw.line(surface, (250, 220, 90), (gx, goal_y2), (gx, goal_y2 + goal_w_screen), 5)


STATE_LABELS = {
    PlayerState.IDLE: "", PlayerState.POSITIONING: "POS", PlayerState.ATTACKING: "ATK",
    PlayerState.DEFENDING: "DEF", PlayerState.PRESSING: "PRESS", PlayerState.MARKING: "MARK",
    PlayerState.RECEIVING: "RECV", PlayerState.DRIBBLING: "DRIB", PlayerState.PASSING: "PASS",
    PlayerState.SHOOTING: "SHOT", PlayerState.TACKLING: "TKL", PlayerState.RECOVERING: "TIRED",
    PlayerState.SUPPORT_ATTACK: "SUPP",
}


def draw_player(surface: pygame.Surface, font: pygame.font.Font, pos, color, number: int,
                 state: PlayerState, stamina: float, selected: bool, has_ball: bool,
                 explain: bool) -> None:
    radius = 11
    if selected:
        pygame.draw.circle(surface, theme.ACCENT, pos, radius + 5, 2)
    ring_color = theme.GOOD if stamina > 60 else (theme.WARN if stamina > 30 else theme.BAD)
    pygame.draw.circle(surface, ring_color, pos, radius + 2)
    pygame.draw.circle(surface, color, pos, radius)
    if has_ball:
        pygame.draw.circle(surface, (255, 255, 255), pos, radius + 3, 2)
    label = font.render(str(number), True, (255, 255, 255))
    surface.blit(label, label.get_rect(center=pos))
    if explain:
        st = STATE_LABELS.get(state, "")
        if st:
            tag = font.render(st, True, theme.TEXT_DIM)
            surface.blit(tag, (pos[0] - tag.get_width() // 2, pos[1] + radius + 4))


def draw_ball(surface: pygame.Surface, pos) -> None:
    pygame.draw.circle(surface, (10, 10, 10), (pos[0] + 1, pos[1] + 1), 6)
    pygame.draw.circle(surface, theme.BALL_COLOR, pos, 6)
    pygame.draw.circle(surface, (40, 40, 40), pos, 6, 1)


def draw_explanation_overlay(surface: pygame.Surface, rect: Rect, match, selected_id: Optional[str]) -> None:
    """Highlights the selected player's last decision: the target teammate/space, the
    intended passing lane, and any opponent threatening that lane (section 26)."""
    if selected_id is None:
        return
    player = match.find_player(selected_id)
    if player is None or player.last_decision is None:
        return
    dec = player.last_decision
    p_screen = world_to_screen(player.position, rect)
    pygame.draw.circle(surface, theme.ACCENT, p_screen, 20, 2)

    if dec.target_position is not None:
        t_screen = world_to_screen(dec.target_position, rect)
        pygame.draw.line(surface, theme.ACCENT, p_screen, t_screen, 2)
        pygame.draw.circle(surface, theme.GOOD, t_screen, 8, 2)

    if dec.target_id is not None:
        target_player = match.find_player(dec.target_id)
        if target_player is not None:
            t_screen = world_to_screen(target_player.position, rect)
            pygame.draw.circle(surface, theme.GOOD, t_screen, 18, 2)
