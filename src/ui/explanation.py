"""AI Explanation Mode state: toggle + currently-selected player, and hit-testing to pick
a player under the mouse cursor on the rendered pitch."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from src.ui.match_view import world_to_screen


@dataclass
class ExplanationState:
    enabled: bool = True
    selected_id: Optional[str] = None
    show_debug_panel: bool = True

    def toggle(self) -> None:
        self.enabled = not self.enabled

    def toggle_debug(self) -> None:
        self.show_debug_panel = not self.show_debug_panel

    def pick_player(self, match, rect, mouse_pos, radius: int = 14) -> bool:
        best = None
        best_d2 = radius * radius
        for team in (match.home, match.away):
            for p in team.players:
                if not p.on_pitch:
                    continue
                sx, sy = world_to_screen(p.position, rect)
                d2 = (sx - mouse_pos[0]) ** 2 + (sy - mouse_pos[1]) ** 2
                if d2 <= best_d2:
                    best_d2 = d2
                    best = p.id
        if best is not None:
            self.selected_id = best
            return True
        return False
