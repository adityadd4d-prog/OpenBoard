"""
openboard.ui.scenes.settings
~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Settings modal dialog scene.
"""

from __future__ import annotations

import logging
from typing import Any

import pygame

from openboard import config
from openboard.ui import theme
from openboard.ui.scenes.base import Scene
from openboard.ui.theme import BORDER, CARD, DANGER, INK, SHADOW, TINT, draw_panel, draw_text
from openboard.ui.widgets import Button, Chips, Toggle

log = logging.getLogger("openboard.ui.scenes.settings")


class SettingsScene(Scene):
    """Modal-style settings dialog pushed on top of the main menu."""

    name = "settings"
    is_modal = True

    def on_enter(self, **_kw: Any) -> None:
        pw = 680
        ph = 640
        px = (config.DESIGN_W - pw) // 2
        py = (config.DESIGN_H - ph) // 2
        self.panel_rect = pygame.Rect(px, py, pw, ph)

        # Settings state
        audio_on = getattr(self.ctx.settings, "audio", True)
        book_on = getattr(self.ctx.settings, "use_book", True)
        smart_on = getattr(self.ctx.settings, "smart_engine", True)

        # Check stockfish availability
        caps = self.ctx.engines.capabilities()
        self.sf_available = caps.stockfish_available

        # Toggles
        ty = py + 110
        self.audio_toggle = Toggle(
            (px + pw - 180, ty, 130, 40),
            on=audio_on,
            on_change=lambda on: self._update_setting("audio", on),
        )

        ty += 80
        self.book_toggle = Toggle(
            (px + pw - 180, ty, 130, 40),
            on=book_on,
            on_change=lambda on: self._update_setting("use_book", on),
        )

        ty += 80
        self.smart_toggle = Toggle(
            (px + pw - 180, ty, 130, 40),
            on=smart_on if self.sf_available else False,
            on_change=lambda on: self._update_setting("smart_engine", on),
        )
        if not self.sf_available:
            self.smart_toggle.enabled = False

        # Frame rate chips
        fps_opts = [str(f) for f in config.FPS_OPTIONS]
        curr_fps = getattr(self.ctx.settings, "fps", config.DEFAULT_FPS)
        sel_fps_idx = config.FPS_OPTIONS.index(curr_fps) if curr_fps in config.FPS_OPTIONS else 1

        ty += 100
        self.fps_chips = Chips(
            (px + 48, ty, pw - 96, 52),
            options=fps_opts,
            selected=sel_fps_idx,
            on_change=self._on_fps_change,
        )

        # Done button
        self.done_btn = Button(
            (px + 48, py + ph - 80, pw - 96, 56),
            "DONE",
            lambda: self.ctx.scenes.pop(),
            style="primary",
        )

    def _update_setting(self, key: str, val: Any) -> None:
        if hasattr(self.ctx.settings, "set"):
            self.ctx.settings.set(**{key: val})

    def _on_fps_change(self, idx: int) -> None:
        fps_val = config.FPS_OPTIONS[idx]
        self._update_setting("fps", fps_val)

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN and event.key in (pygame.K_ESCAPE, pygame.K_RETURN):
            self.ctx.scenes.pop()
            return

        if self.audio_toggle.handle_event(event):
            return
        if self.book_toggle.handle_event(event):
            return
        if self.smart_toggle.handle_event(event):
            return
        if self.fps_chips.handle_event(event):
            return
        self.done_btn.handle_event(event)

    def update(self, dt: float) -> None:
        self.done_btn.update(dt)

    def draw(self, surf: pygame.Surface) -> None:
        draw_panel(surf, self.panel_rect, fill=CARD, border=BORDER, shadow=SHADOW, shadow_color=INK)
        px, py, pw, _ = self.panel_rect

        # Header
        draw_text(surf, "SETTINGS", "heading", INK, (self.panel_rect.centerx, py + 36), anchor="midtop")

        # 1. Audio toggle
        y1 = py + 110
        draw_text(surf, "AUDIO EFFECTS", "label", INK, (px + 48, y1), anchor="topleft")
        draw_text(surf, "Play move, capture, check and clock sounds", "small", TINT, (px + 48, y1 + 24), anchor="topleft")
        self.audio_toggle.draw(surf)

        # 2. Opening book toggle
        y2 = y1 + 80
        draw_text(surf, "USE OPENING BOOK", "label", INK, (px + 48, y2), anchor="topleft")
        draw_text(surf, "Built-in polyglot opening book responses", "small", TINT, (px + 48, y2 + 24), anchor="topleft")
        self.book_toggle.draw(surf)

        # 3. Smart engine toggle
        y3 = y2 + 80
        draw_text(surf, "SMART ENGINE", "label", INK, (px + 48, y3), anchor="topleft")
        if self.sf_available:
            draw_text(surf, "Switch between built-in engine and Stockfish automatically", "small", TINT, (px + 48, y3 + 24), anchor="topleft")
        else:
            draw_text(surf, "Stockfish not found — built-in engine only", "small", DANGER, (px + 48, y3 + 24), anchor="topleft")
        self.smart_toggle.draw(surf)

        # 4. Frame rate chips
        y4 = y3 + 80
        draw_text(surf, "TARGET FRAME RATE", "label", INK, (px + 48, y4), anchor="topleft")
        self.fps_chips.draw(surf)

        # Done button
        self.done_btn.draw(surf)
