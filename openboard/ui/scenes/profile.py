"""
openboard.ui.scenes.profile
~~~~~~~~~~~~~~~~~~~~~~~~~~~
Player profile and match history scene.
"""

from __future__ import annotations

import logging
from typing import Any

import pygame

from openboard import config
from openboard.core.results import Reason
from openboard.storage.history import MatchRecord
from openboard.ui import theme
from openboard.ui.scenes.base import Scene
from openboard.ui.theme import ACCENT, BORDER, CARD, CARD_BORDER, DANGER, INK, PURPLE, SHADOW, TINT, draw_panel, draw_text
from openboard.ui.widgets import Button, ScrollList, TextInput

log = logging.getLogger("openboard.ui.scenes.profile")


class ProfileScene(Scene):
    """User profile screen showing player crest, editable name, stats, and match history."""

    name = "profile"

    def on_enter(self, **_kw: Any) -> None:
        self.back_btn = Button((60, 48, 140, 52), "BACK", lambda: self.ctx.scenes.go("main_menu"), style="secondary")

        # Three-column layout inside a central panel
        pw = 1440
        ph = 720
        px = (config.DESIGN_W - pw) // 2
        py = 120
        self.panel_rect = pygame.Rect(px, py, pw, ph)

        # Name edit state
        self._editing_name: bool = False
        curr_name = getattr(self.ctx.profile.profile, "name", "Player 1")
        self.name_input = TextInput(
            (px + 460, py + 340, 320, 52),
            text=curr_name,
            max_len=config.NAME_MAX,
            on_submit=self._save_name,
        )
        self._name_error: str | None = None

        # Pencil button
        self.pencil_btn = Button(
            (px + 790, py + 340, 52, 52),
            "",
            self._toggle_edit_name,
            style="ghost",
        )

        # Time control cycle button
        self.tc_btn = Button(
            (px + 460, py + 410, 380, 48),
            "",
            self._cycle_time_control,
            style="secondary",
        )
        self._update_tc_button_label()

        # Stats query
        self.stats = self.ctx.history.stats()

        # Match history query
        self.matches: list[MatchRecord] = self.ctx.history.recent(limit=50)

        # History scroll list (Column 3)
        hist_x = px + 920
        hist_w = 480
        hist_y = py + 90
        hist_h = ph - 130
        self.history_list = ScrollList(
            (hist_x, hist_y, hist_w, hist_h),
            item_height=70,
            draw_item=self._draw_history_row,
            items=self.matches,
        )

    def _update_tc_button_label(self) -> None:
        pref = getattr(self.ctx.profile.profile, "preferred_time_control", "rapid")
        tc = config.TIME_CONTROLS.get(pref, config.TIME_CONTROLS["rapid"])
        self.tc_btn.label = f"PREF: {tc.label}"

    def _cycle_time_control(self) -> None:
        pref = getattr(self.ctx.profile.profile, "preferred_time_control", "rapid")
        new_pref = "blitz" if pref == "rapid" else "rapid"
        self.ctx.profile.set_time_control(new_pref)
        self._update_tc_button_label()

    def _toggle_edit_name(self) -> None:
        if self._editing_name:
            self._save_name(self.name_input.text)
        else:
            self._editing_name = True
            self.name_input.text = getattr(self.ctx.profile.profile, "name", "Player 1")
            self.name_input.focused = True
            self._name_error = None

    def _save_name(self, text: str) -> None:
        try:
            self.ctx.profile.rename(text)
            self._editing_name = False
            self._name_error = None
        except ValueError as err:
            self._name_error = str(err)
            self.name_input.invalid = True

    def _draw_history_row(self, surf: pygame.Surface, item: MatchRecord, rect: pygame.Rect, idx: int, hovered: bool) -> None:
        # Hover effect
        if hovered:
            pygame.draw.rect(surf, CARD_BORDER, rect)

        # Opponent & mode
        opp_str = item.opponent or "Unknown"
        mode_str = f"{item.mode.replace('_', ' ').title()} · {item.moves} moves"

        draw_text(surf, opp_str, "heading", INK, (rect.x + 12, rect.y + 12), anchor="topleft")
        draw_text(surf, mode_str, "small", TINT, (rect.x + 12, rect.bottom - 12), anchor="bottomleft")

        # Result badge
        res = (item.result or "").upper()
        res_col = ACCENT if res == "WON" else (DANGER if res == "LOST" else INK)
        draw_text(surf, res, "heading", res_col, (rect.right - 24, rect.centery), anchor="midright")
        pygame.draw.line(surf, CARD_BORDER, (rect.x, rect.bottom - 1), (rect.right, rect.bottom - 1), 1)

    def handle_event(self, event: pygame.event.Event) -> None:
        if self.back_btn.handle_event(event):
            return

        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            if self._editing_name:
                self._editing_name = False
                self._name_error = None
                return
            self.ctx.scenes.go("main_menu")
            return

        if self._editing_name:
            if self.name_input.handle_event(event):
                return

        if self.pencil_btn.handle_event(event):
            return
        if self.tc_btn.handle_event(event):
            return

        # Check clicks on match history
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.history_list.rect.collidepoint(event.pos):
                rel_y = event.pos[1] - self.history_list.rect.y + self.history_list.scroll_y
                idx = rel_y // self.history_list.item_height
                if 0 <= idx < len(self.matches):
                    match_rec = self.matches[idx]
                    # Go to evaluate if pgn available
                    if match_rec.pgn:
                        self.ctx.scenes.go("evaluate", moves=match_rec.pgn.split(), start_fen=None)
                    else:
                        self.ctx.scenes.go("evaluate")
                    return

        self.history_list.handle_event(event)

    def update(self, dt: float) -> None:
        self.back_btn.update(dt)
        self.pencil_btn.update(dt)
        self.tc_btn.update(dt)
        if self._editing_name:
            self.name_input.update(dt)

    def draw(self, surf: pygame.Surface) -> None:
        try:
            bg = self.ctx.assets.background("bg_profile")
            surf.blit(bg, (0, 0))
        except Exception:
            surf.fill(theme.BG)

        self.back_btn.draw(surf)

        # Central big card
        draw_panel(surf, self.panel_rect, fill=CARD, border=BORDER, shadow=SHADOW, shadow_color=INK)

        px, py, pw, ph = self.panel_rect

        # ---------------- Column 1: Stats ----------------
        stat_x = px + 48
        draw_text(surf, "STATS", "heading", INK, (stat_x, py + 36), anchor="topleft")

        stats_data = [
            ("PLAYED", str(self.stats.played), INK),
            ("WON", str(self.stats.won), ACCENT),
            ("LOST", str(self.stats.lost), DANGER),
            ("DRAWN", str(self.stats.drawn), INK),
        ]

        sy = py + 100
        for label, val, col in stats_data:
            draw_text(surf, val, "clock", col, (stat_x, sy), anchor="topleft")
            draw_text(surf, label, "small", TINT, (stat_x, sy + 70), anchor="topleft")
            sy += 125

        # ---------------- Column 2: Crest & Name ----------------
        mid_x = px + 440
        crest_center = (mid_x + 190, py + 180)
        try:
            crest_img = self.ctx.assets.image("player_crest")
            cx = crest_center[0] - crest_img.get_width() // 2
            cy = crest_center[1] - crest_img.get_height() // 2
            surf.blit(crest_img, (cx, cy))
        except Exception:
            pygame.draw.circle(surf, PURPLE, crest_center, 80)

        if self._editing_name:
            self.name_input.draw(surf)
            if self._name_error:
                draw_text(surf, self._name_error, "small", DANGER, (self.name_input.rect.x, self.name_input.rect.bottom + 4), anchor="topleft")
        else:
            name_str = getattr(self.ctx.profile.profile, "name", "Player 1")
            draw_text(surf, name_str, "heading", INK, (mid_x + 160, py + 366), anchor="center")

        # Pencil icon
        self.pencil_btn.draw(surf)
        try:
            pencil_icon = self.ctx.assets.image("icon_pencil")
            surf.blit(pencil_icon, self.pencil_btn.rect.topleft)
        except Exception:
            draw_text(surf, "✎", "heading", INK, self.pencil_btn.rect.center, anchor="center")

        self.tc_btn.draw(surf)

        # ---------------- Column 3: Match History ----------------
        hist_x = px + 920
        draw_text(surf, "MATCH HISTORY", "heading", INK, (hist_x, py + 36), anchor="topleft")

        if not self.matches:
            draw_text(surf, "No games yet.", "body", TINT, (hist_x + 200, py + 260), anchor="center")
        else:
            self.history_list.draw(surf)
