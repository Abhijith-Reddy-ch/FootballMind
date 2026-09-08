"""Minimal reusable pygame widgets: buttons and left/right option selectors."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, List, Optional, Sequence, Tuple

import pygame

from src.ui import theme

Rect = Tuple[int, int, int, int]


@dataclass
class Button:
    rect: Rect
    label: str
    active: bool = False
    enabled: bool = True

    def draw(self, surface, font) -> None:
        x, y, w, h = self.rect
        bg = theme.ACCENT if self.active else theme.PANEL_BG
        fg = (10, 14, 18) if self.active else (theme.TEXT if self.enabled else theme.TEXT_DIM)
        pygame.draw.rect(surface, bg, self.rect, border_radius=6)
        pygame.draw.rect(surface, theme.PANEL_BORDER, self.rect, width=1, border_radius=6)
        label = font.render(self.label, True, fg)
        surface.blit(label, label.get_rect(center=(x + w // 2, y + h // 2)))

    def hit(self, pos) -> bool:
        x, y, w, h = self.rect
        return self.enabled and x <= pos[0] <= x + w and y <= pos[1] <= y + h


@dataclass
class OptionSelector:
    """Label + value with < and > arrow buttons to cycle through `options`."""
    rect: Rect
    label: str
    options: Sequence[str]
    index: int = 0

    def value(self) -> str:
        return self.options[self.index]

    def draw(self, surface, font, font_bold) -> None:
        x, y, w, h = self.rect
        pygame.draw.rect(surface, theme.PANEL_BG, self.rect, border_radius=6)
        pygame.draw.rect(surface, theme.PANEL_BORDER, self.rect, width=1, border_radius=6)
        label_surf = font.render(self.label, True, theme.TEXT_DIM)
        surface.blit(label_surf, (x + 10, y + 6))
        val_surf = font_bold.render(str(self.value()), True, theme.TEXT)
        surface.blit(val_surf, (x + w // 2 - val_surf.get_width() // 2, y + h - val_surf.get_height() - 8))
        arrow_l = font_bold.render("<", True, theme.ACCENT)
        arrow_r = font_bold.render(">", True, theme.ACCENT)
        surface.blit(arrow_l, (x + 8, y + h - val_surf.get_height() - 6))
        surface.blit(arrow_r, (x + w - 20, y + h - val_surf.get_height() - 6))

    def left_rect(self) -> Rect:
        x, y, w, h = self.rect
        return (x, y + h - 26, 26, 26)

    def right_rect(self) -> Rect:
        x, y, w, h = self.rect
        return (x + w - 26, y + h - 26, 26, 26)

    def handle_click(self, pos) -> bool:
        lx, ly, lw, lh = self.left_rect()
        rx, ry, rw, rh = self.right_rect()
        if lx <= pos[0] <= lx + lw and ly <= pos[1] <= ly + lh:
            self.index = (self.index - 1) % len(self.options)
            return True
        if rx <= pos[0] <= rx + rw and ry <= pos[1] <= ry + rh:
            self.index = (self.index + 1) % len(self.options)
            return True
        return False


@dataclass
class Slider:
    rect: Rect
    label: str
    value: int = 50  # 0-100

    def draw(self, surface, font) -> None:
        x, y, w, h = self.rect
        label_surf = font.render(f"{self.label}: {self.value}", True, theme.TEXT_DIM)
        surface.blit(label_surf, (x, y))
        track_y = y + 20
        pygame.draw.rect(surface, theme.PANEL_BORDER, (x, track_y, w, 6), border_radius=3)
        knob_x = x + int((self.value / 100.0) * w)
        pygame.draw.circle(surface, theme.ACCENT, (knob_x, track_y + 3), 8)

    def handle_click(self, pos) -> bool:
        x, y, w, h = self.rect
        track_y = y + 20
        if x - 8 <= pos[0] <= x + w + 8 and track_y - 10 <= pos[1] <= track_y + 10:
            frac = (pos[0] - x) / w
            self.value = int(max(0, min(100, frac * 100)))
            return True
        return False
