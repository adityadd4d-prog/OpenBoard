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
from openboard.ui.theme import BORDER, CARD, INK, PURPLE, WORDMARK_PURPLE, draw_panel, draw_text, font
from openboard.ui.widgets import Button


def _render_tracked(f: pygame.font.Font, text: str, color: tuple[int, int, int], tracking: int = 0) -> pygame.Surface:
    """Render text with specified tracking (letter-spacing adjustment)."""
    try:
        surfs = [f.render(ch, True, color) for ch in text]
        advances = [f.metrics(ch)[0][4] + tracking for ch in text]
        total_w = sum(advances[:-1]) + surfs[-1].get_width()
        h = max(s.get_height() for s in surfs)
        surf = pygame.Surface((total_w, h), pygame.SRCALPHA)
        x = 0
        for i, s in enumerate(surfs):
            surf.blit(s, (x, 0))
            if i < len(advances):
                x += advances[i]
        return surf
    except Exception:
        return f.render(text, True, color)


class MainMenuScene(Scene):
    """Main menu of OpenBoard with wordmark, navigation buttons, and isometric illustration."""

    name = "main_menu"

    def on_enter(self, **_kw: Any) -> None:
        self._is_active: bool = True

        # Left column layout matching Figma reference
        bx = 224
        btn_w = 370
        btn_h = 64
        gap = 24
        start_y = 340

        self.buttons: list[Button] = [
            Button((bx, start_y + 0 * (btn_h + gap), btn_w, btn_h), "PLAY", lambda: self.ctx.scenes.go("opponent_select"), align="left", padding_x=30, style="secondary"),
            Button((bx, start_y + 1 * (btn_h + gap), btn_w, btn_h), "EVALUATE", lambda: self.ctx.scenes.go("evaluate"), align="left", padding_x=30, style="secondary"),
            Button((bx, start_y + 2 * (btn_h + gap), btn_w, btn_h), "PROFILE", lambda: self.ctx.scenes.go("profile"), align="left", padding_x=30, style="secondary"),
            Button((bx, start_y + 3 * (btn_h + gap), btn_w, btn_h), "ABOUT", lambda: self.ctx.scenes.go("about"), align="left", padding_x=30, style="secondary"),
            Button((bx, start_y + 4 * (btn_h + gap), btn_w, btn_h), "QUIT", self._on_quit_click, align="left", padding_x=30, style="secondary"),
        ]

        # Gear button in top-right: 80x80 box at (1456, 48) with 8px shadow
        self.gear_btn = Button(
            (1456, 48, 80, 80),
            "",
            lambda: self.ctx.scenes.push("settings"),
            style="secondary",
            shadow=8,
        )

        self.focused_idx: int = 0
        self._update_focus()

    def _update_focus(self) -> None:
        for idx, btn in enumerate(self.buttons):
            btn.focused = idx == self.focused_idx
            btn.fill_override = PURPLE if btn.focused else CARD

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
        open_surf = _render_tracked(wordmark_f, "Open", INK, -15)
        board_surf = _render_tracked(wordmark_f, "Board", WORDMARK_PURPLE, -11)

        surf.blit(open_surf, (32, 10))
        surf.blit(board_surf, (225, 148))

        # Isometric board illustration on the right (static, no motion/animation)
        try:
            illus = self.ctx.assets.image("illus_iso_board")
            surf.blit(illus, (738, 178))
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
