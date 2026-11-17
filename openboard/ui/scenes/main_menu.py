"""
openboard.ui.scenes.main_menu
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Main menu scene.
"""

from __future__ import annotations

import math
from typing import Any

import pygame

from openboard import config
from openboard.ui import theme
from openboard.ui.scenes.base import Scene
from openboard.ui.theme import ACCENT, BORDER, CARD, INK, PURPLE, SHADOW, draw_panel, draw_text, font
from openboard.ui.widgets import Button


class MainMenuScene(Scene):
    """Main menu of OpenBoard with wordmark, navigation buttons, and isometric illustration."""

    name = "main_menu"

    def on_enter(self, **_kw: Any) -> None:
        self._bob_t: float = 0.0
        self._is_active: bool = True

        # Left column layout
        bx = 140
        btn_w = 340
        btn_h = 68
        gap = 18
        start_y = 380

        self.buttons: list[Button] = [
            Button((bx, start_y + 0 * (btn_h + gap), btn_w, btn_h), "PLAY", lambda: self.ctx.scenes.go("opponent_select")),
            Button((bx, start_y + 1 * (btn_h + gap), btn_w, btn_h), "EVALUATE", lambda: self.ctx.scenes.go("evaluate")),
            Button((bx, start_y + 2 * (btn_h + gap), btn_w, btn_h), "PROFILE", lambda: self.ctx.scenes.go("profile")),
            Button((bx, start_y + 3 * (btn_h + gap), btn_w, btn_h), "ABOUT", lambda: self.ctx.scenes.go("about")),
            Button((bx, start_y + 4 * (btn_h + gap), btn_w, btn_h), "QUIT", self._on_quit_click, style="secondary"),
        ]

        # Gear button in top-right
        self.gear_btn = Button(
            (config.DESIGN_W - 84, 36, 48, 48),
            "",
            lambda: self.ctx.scenes.push("settings"),
            style="ghost",
        )

        self.focused_idx: int = 0
        self._update_focus()

    def _update_focus(self) -> None:
        for idx, btn in enumerate(self.buttons):
            btn.focused = idx == self.focused_idx

    def _on_quit_click(self) -> None:
        def handle_confirm(yes: bool) -> None:
            if yes:
                self.ctx.scenes.request_quit()

        self.ctx.scenes.push(
            "confirm",
            title="QUIT GAME",
            message="Are you sure you want to quit OpenBoard?",
            yes_label="QUIT",
            no_label="CANCEL",
            on_result=handle_confirm,
        )

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.ACTIVEEVENT:
            if hasattr(event, "gain"):
                self._is_active = bool(event.gain)

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self._on_quit_click()
                return
            if event.key in (pygame.K_UP, pygame.K_w):
                self.focused_idx = (self.focused_idx - 1) % len(self.buttons)
                self._update_focus()
                return
            if event.key in (pygame.K_DOWN, pygame.K_s):
                self.focused_idx = (self.focused_idx + 1) % len(self.buttons)
                self._update_focus()
                return

        for btn in self.buttons:
            if btn.handle_event(event):
                return

        self.gear_btn.handle_event(event)

    def update(self, dt: float) -> None:
        if self._is_active:
            self._bob_t += dt

        for btn in self.buttons:
            btn.update(dt)
        self.gear_btn.update(dt)

    def draw(self, surf: pygame.Surface) -> None:
        # Background
        try:
            bg = self.ctx.assets.background("bg_main")
            surf.blit(bg, (0, 0))
        except Exception:
            surf.fill(theme.BG)

        # Wordmark: 'Open' in INK, 'Board' in vivid purple
        wordmark_f = font("wordmark")
        open_surf = wordmark_f.render("OPEN", True, INK)
        board_surf = wordmark_f.render("BOARD", True, ACCENT)

        surf.blit(open_surf, (140, 110))
        surf.blit(board_surf, (140, 210))

        # Isometric board illustration on the right with idle bob
        try:
            illus = self.ctx.assets.image("illus_iso_board")
            # Bobbing ~4px over 4s sine wave
            bob_offset = 4.0 * math.sin((2.0 * math.pi / 4.0) * self._bob_t)
            ix = 920
            iy = 280 + bob_offset
            surf.blit(illus, (ix, int(iy)))
        except Exception:
            pass

        # Buttons
        for btn in self.buttons:
            btn.draw(surf)

        # Gear icon
        self.gear_btn.draw(surf)
        try:
            gear_icon = self.ctx.assets.image("icon_gear")
            gx = self.gear_btn.rect.centerx - gear_icon.get_width() // 2
            gy = self.gear_btn.rect.centery - gear_icon.get_height() // 2
            surf.blit(gear_icon, (gx, gy))
        except Exception:
            draw_text(surf, "⚙", "heading", INK, self.gear_btn.rect.center, anchor="center")
