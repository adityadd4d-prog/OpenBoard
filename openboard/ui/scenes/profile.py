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
from openboard.storage.history import MatchRecord
from openboard.ui import theme
from openboard.ui.scenes.base import Scene
from openboard.ui.theme import (
    ACCENT,
    BG,
    BORDER,
    CARD,
    CARD_BORDER,
    DANGER,
    INK,
    PURPLE,
    SECONDARY,
    draw_panel,
    draw_text,
    draw_wrapped_text,
    fit_text,
    font,
)
from openboard.ui.widgets import Button, ScrollList, TextInput

log = logging.getLogger("openboard.ui.scenes.profile")


class ProfileScene(Scene):
    """User profile screen showing player crest, editable name, stats, and match history."""

    name = "profile"

    def on_enter(self, **_kw: Any) -> None:
        self.back_btn = Button(
            (64, 48, 128, 52),
            "BACK",
            lambda: self.ctx.scenes.go("main_menu"),
            style="secondary",
            shadow=8,
        )

        # Central 3-column card matching Figma reference (180, 250, 1240, 429)
        self.panel_rect = pygame.Rect(180, 250, 1240, 429)
        self._col2_cx = 728  # Horizontal center of middle column (524..932)

        # Name edit state
        self._editing_name: bool = False
        curr_name = getattr(self.ctx.profile.profile, "name", "Player 1")
        self.name_input = TextInput(
            (self._col2_cx - 150, 551, 240, 46),
            text=curr_name,
            max_len=config.NAME_MAX,
            on_submit=self._save_name,
        )
        self._name_error: str | None = None

        # Square neo-brutalist pencil button (48x48, shadow=8)
        self.pencil_btn = Button(
            (775, 550, 48, 48),
            "",
            self._toggle_edit_name,
            style="secondary",
            shadow=8,
        )
        self._layout_name_row()

        # Time control filter & preferred time control clickable caption below name
        self._tc_filter_keys: list[str] = ["all", *config.TIME_CONTROLS.keys()]
        self._tc_filter: str = "all"
        self._tc_rect = pygame.Rect(self._col2_cx - 105, 614, 210, 30)
        self._tc_hovered: bool = False

        # Stats & match history queries
        self.stats = self.ctx.history.stats()
        self._all_matches: list[MatchRecord] = self.ctx.history.recent(limit=200)
        self.matches: list[MatchRecord] = list(self._all_matches)

        # Borderless scrollable match history list (Column 3: x=932..1420, fits 3 clean rows)
        self.history_list = ScrollList(
            (956, 354, 444, 276),
            item_height=92,
            draw_item=self._draw_history_row,
            items=self.matches,
            borderless=True,
        )
        self._apply_history_filter()

    def _current_name_display(self) -> str:
        raw = getattr(self.ctx.profile.profile, "name", "Player 1")
        return fit_text(raw.upper(), "heading", 220)

    def _layout_name_row(self) -> None:
        """Center the [NAME + PENCIL] or [INPUT + PENCIL] pair in column 2."""
        cx = self._col2_cx
        if self._editing_name:
            inp_w = 240
            gap = 12
            btn_w = 48
            total_w = inp_w + gap + btn_w
            start_x = cx - total_w // 2
            self.name_input.rect = pygame.Rect(start_x, 551, inp_w, 46)
            self.pencil_btn.rect = pygame.Rect(start_x + inp_w + gap, 550, btn_w, 48)
        else:
            name_disp = self._current_name_display()
            name_w = font("heading").size(name_disp)[0]
            gap = 16
            btn_w = 48
            total_w = name_w + gap + btn_w
            start_x = cx - total_w // 2
            self._name_x = start_x
            self.pencil_btn.rect = pygame.Rect(start_x + name_w + gap, 550, btn_w, 48)

    def _current_tc_label(self) -> str:
        if self._tc_filter == "all":
            return "ALL"
        tc = config.TIME_CONTROLS.get(self._tc_filter, config.TIME_CONTROLS["rapid"])
        if tc.minutes <= 0:
            return tc.label
        parts = tc.label.split(None, 1)
        return f"{parts[0]} · {parts[1]}" if len(parts) == 2 else tc.label

    @staticmethod
    def _matches_tc_filter(item: MatchRecord, tc_key: str) -> bool:
        if tc_key == "all":
            return True
        raw = (item.time_control or "").strip().upper()
        if tc_key == "blitz":
            return raw.startswith("BLITZ")
        if tc_key == "rapid":
            return raw.startswith("RAPID")
        if tc_key == "unlimited":
            return raw in ("NO CLOCK", "UNLIMITED") or raw.startswith("NO CLOCK")
        tc = config.TIME_CONTROLS.get(tc_key)
        return tc is not None and raw == tc.label.upper()

    def _apply_history_filter(self) -> None:
        self.matches = [m for m in self._all_matches if self._matches_tc_filter(m, self._tc_filter)]
        self.history_list.set_items(self.matches)
        self.history_list.scroll_y = 0

    def _cycle_time_control(self) -> None:
        keys = self._tc_filter_keys
        idx = keys.index(self._tc_filter) if self._tc_filter in keys else 0
        self._tc_filter = keys[(idx + 1) % len(keys)]
        if self._tc_filter != "all" and hasattr(self.ctx.profile, "set_time_control"):
            self.ctx.profile.set_time_control(self._tc_filter)
        self._apply_history_filter()

    def _toggle_edit_name(self) -> None:
        if self._editing_name:
            self._save_name(self.name_input.text)
        else:
            self._editing_name = True
            self.name_input.set_text(getattr(self.ctx.profile.profile, "name", "Player 1"), notify=False)
            self.name_input.focused = True
            self._name_error = None
            self._layout_name_row()

    def _save_name(self, text: str) -> None:
        try:
            self.ctx.profile.rename(text)
            self._editing_name = False
            self._name_error = None
            self.name_input.invalid = False
            self._layout_name_row()
        except ValueError as err:
            self._name_error = str(err)
            self.name_input.invalid = True

    def _draw_history_row(
        self,
        surf: pygame.Surface,
        item: MatchRecord,
        rect: pygame.Rect,
        idx: int,
        hovered: bool,
    ) -> None:
        if hovered:
            pygame.draw.rect(surf, BG, rect)

        # Opponent title matching reference ("Alex", "Engine · Level 4")
        if item.mode == "vs_engine" and item.engine_level is not None:
            opp_str = f"Engine · Level {item.engine_level}"
        else:
            opp_str = item.opponent or "Unknown"

        # Subtitle matching reference ("Rapid · 32 moves", "Blitz · 58 moves", "No Clock · 24 moves")
        raw_tc = (item.time_control or "Rapid").strip()
        if raw_tc.upper() in ("NO CLOCK", "UNLIMITED"):
            tc_short = "No Clock"
        else:
            tc_short = raw_tc.split()[0].title()
        move_word = "move" if item.moves == 1 else "moves"
        sub_str = f"{tc_short} · {item.moves} {move_word}"

        text_max_w = max(80, rect.width - 125)
        draw_text(surf, fit_text(opp_str, "body", text_max_w), "body", INK, (rect.x + 16, rect.y + 18), anchor="topleft")
        draw_text(surf, fit_text(sub_str, "small", text_max_w), "small", SECONDARY, (rect.x + 16, rect.y + 48), anchor="topleft")

        # Result badge ("WON" in purple ACCENT, "LOST" & "DRAWN" in INK)
        res = (item.result or "").upper()
        res_col = ACCENT if res == "WON" else INK
        draw_text(surf, res, "coord", res_col, (rect.right - 20, rect.y + 20), anchor="topright")

    def handle_event(self, event: pygame.event.Event) -> None:
        if self.back_btn.handle_event(event):
            return

        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            if self._editing_name:
                self._editing_name = False
                self._name_error = None
                self._layout_name_row()
                return
            self.ctx.scenes.go("main_menu")
            return

        if self._editing_name:
            if self.name_input.handle_event(event):
                return

        if self.pencil_btn.handle_event(event):
            return

        # Clickable preferred time control text
        if event.type == pygame.MOUSEMOTION:
            self._tc_hovered = self._tc_rect.collidepoint(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self._tc_rect.collidepoint(event.pos):
                self._cycle_time_control()
                return

        # Let scroll list handle scrollbar drag & wheel events first
        if self.history_list.handle_event(event):
            return

        # Check clicks on match history rows
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            inner = self.history_list._inner_rect()
            if inner.collidepoint(event.pos) and event.pos[0] < inner.right - 16:
                rel_y = event.pos[1] - inner.y + self.history_list.scroll_y
                idx = rel_y // self.history_list.item_height
                if 0 <= idx < len(self.matches):
                    match_rec = self.matches[idx]
                    self.ctx.scenes.go("evaluate", pgn=match_rec.pgn, return_to="profile")
                    return

    def update(self, dt: float) -> None:
        self.back_btn.update(dt)
        self.pencil_btn.update(dt)
        if self._editing_name:
            self.name_input.update(dt)

    def draw(self, surf: pygame.Surface) -> None:
        try:
            bg = self.ctx.assets.background("bg_profile")
            surf.blit(bg, (0, 0))
        except Exception:
            surf.fill(theme.BG)

        # Top bar: BACK button & PROFILE title
        self.back_btn.draw(surf)
        draw_text(surf, "PROFILE", "title", INK, (263, 52), anchor="topleft")

        # Central card
        draw_panel(surf, self.panel_rect, fill=CARD, border=BORDER, shadow=8, shadow_color=INK)

        # Vertical column dividers
        pygame.draw.line(surf, CARD_BORDER, (524, 282), (524, 647), 2)
        pygame.draw.line(surf, CARD_BORDER, (932, 282), (932, 647), 2)

        # ---------------- Column 1: STATS (2x2 grid) ----------------
        draw_text(surf, "STATS", "heading", INK, (220, 284), anchor="topleft")

        grid_stats = [
            (220, 366, str(self.stats.played), "PLAYED", INK),
            (372, 366, str(self.stats.won), "WON", ACCENT),
            (220, 502, str(self.stats.lost), "LOST", INK),
            (372, 502, str(self.stats.drawn), "DRAWN", INK),
        ]
        for gx, gy, val, label, val_col in grid_stats:
            draw_text(surf, val, "number", val_col, (gx, gy), anchor="topleft")
            draw_text(surf, label, "small", SECONDARY, (gx, gy + 78), anchor="topleft")

        # ---------------- Column 2: CREST, NAME & TIME CONTROL ----------------
        cx = self._col2_cx
        try:
            crest_img = self.ctx.assets.image("player_crest")
            surf.blit(crest_img, (cx - crest_img.get_width() // 2, 323))
        except Exception:
            pygame.draw.rect(surf, PURPLE, (cx - 98, 323, 196, 196))

        if self._editing_name:
            self.name_input.draw(surf)
            if self._name_error:
                draw_wrapped_text(
                    surf,
                    self._name_error,
                    "small",
                    DANGER,
                    (cx, 600),
                    max_w=360,
                    anchor="midtop",
                    max_lines=1,
                )
        else:
            name_disp = self._current_name_display()
            draw_text(surf, name_disp, "heading", INK, (self._name_x, 574), anchor="midleft")

        # Square pencil button with centered icon
        self.pencil_btn.draw(surf)
        btn_offset = (self.pencil_btn.shadow - 1) if self.pencil_btn.pressed else (-1 if self.pencil_btn.hovered else 0)
        icon_center = (self.pencil_btn.rect.centerx + btn_offset, self.pencil_btn.rect.centery + btn_offset)
        try:
            pencil_icon = self.ctx.assets.image("icon_pencil")
            surf.blit(
                pencil_icon,
                (icon_center[0] - pencil_icon.get_width() // 2, icon_center[1] - pencil_icon.get_height() // 2),
            )
        except Exception:
            draw_text(surf, "✎", "heading", INK, icon_center, anchor="center")

        # Preferred time control caption (clickable to toggle Rapid / Blitz)
        tc_col = ACCENT if self._tc_hovered else INK
        tc_rect = draw_text(surf, self._current_tc_label(), "small", tc_col, (cx, 629), anchor="center")
        if self._tc_hovered:
            pygame.draw.line(surf, ACCENT, (tc_rect.left, tc_rect.bottom + 2), (tc_rect.right, tc_rect.bottom + 2), 1)

        # ---------------- Column 3: MATCH HISTORY ----------------
        draw_text(surf, "MATCH HISTORY", "heading", INK, (972, 284), anchor="topleft")

        if not self.matches:
            empty_msg = "No games yet." if not self._all_matches else "No matching games."
            draw_text(surf, empty_msg, "body", SECONDARY, (1176, 480), anchor="center")
        else:
            self.history_list.draw(surf)
