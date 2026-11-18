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
from openboard.ui.theme import BORDER, CARD, DANGER, INK, SECONDARY, SHADOW, draw_panel, draw_text, draw_wrapped_text
from openboard.ui.widgets import Button, Chips, Toggle

log = logging.getLogger("openboard.ui.scenes.settings")

_ENGINE_MODE_OPTIONS: list[tuple[str, str]] = [
    ("auto", "AUTO"),
    ("custom", "CUSTOM ENGINE"),
    ("stockfish", "STOCKFISH"),
]


class SettingsScene(Scene):
    """Modal-style settings dialog pushed on top of the main menu."""

    name = "settings"
    is_modal = True

    def on_enter(self, **_kw: Any) -> None:
        self.back_btn = Button((60, 48, 140, 52), "BACK", lambda: self.ctx.scenes.pop(), style="secondary")

        pw = 800
        ph = 668
        px = 400
        py = 140
        self.panel_rect = pygame.Rect(px, py, pw, ph)

        # Settings state
        audio_on = getattr(self.ctx.settings, "audio", True)
        book_on = getattr(self.ctx.settings, "use_book", True)
        raw_mode = getattr(self.ctx.settings, "engine_mode", None)
        if raw_mode not in ("auto", "custom", "stockfish"):
            raw_mode = "auto" if getattr(self.ctx.settings, "smart_engine", True) else "custom"

        # Check Stockfish availability
        caps = self.ctx.engines.capabilities()
        self.sf_available = caps.stockfish_available

        # 1. Audio toggle
        y1 = py + 78
        self.audio_toggle = Toggle(
            (px + pw - 180, y1, 130, 40),
            on=audio_on,
            on_change=lambda on: self._update_setting("audio", on),
        )

        # 2. Opening book toggle
        y2 = y1 + 70
        self.book_toggle = Toggle(
            (px + pw - 180, y2, 130, 40),
            on=book_on,
            on_change=lambda on: self._update_setting("use_book", on),
        )

        # 3. Smart select engine mode chips: Auto / Custom Engine / Stockfish
        mode_keys = [k for k, _ in _ENGINE_MODE_OPTIONS]
        mode_labels = [lbl for _, lbl in _ENGINE_MODE_OPTIONS]
        if not self.sf_available:
            sel_mode_idx = mode_keys.index("custom")
        else:
            sel_mode_idx = mode_keys.index(raw_mode) if raw_mode in mode_keys else 0

        y3 = y2 + 70
        self.engine_chips = Chips(
            (px + 48, y3 + 50, pw - 96, 46),
            options=mode_labels,
            selected=sel_mode_idx,
            on_change=self._on_engine_mode_change,
        )
        if not self.sf_available:
            self.engine_chips.enabled = False

        # 4. Custom engine max depth before switching to Stockfish
        depth_opts = list(config.CUSTOM_MAX_DEPTH_OPTIONS)
        curr_depth = getattr(self.ctx.settings, "custom_max_depth", config.PY_EVAL_MAX_DEPTH)
        sel_depth_idx = depth_opts.index(curr_depth) if curr_depth in depth_opts else depth_opts.index(config.PY_EVAL_MAX_DEPTH)

        y4 = y3 + 118
        self.depth_chips = Chips(
            (px + 48, y4 + 50, pw - 96, 46),
            options=[str(d) for d in depth_opts],
            selected=sel_depth_idx,
            on_change=self._on_depth_change,
        )
        self._sync_depth_chips_enabled()

        # 5. Frame rate chips
        fps_opts = [str(f) for f in config.FPS_OPTIONS]
        curr_fps = getattr(self.ctx.settings, "fps", config.DEFAULT_FPS)
        sel_fps_idx = config.FPS_OPTIONS.index(curr_fps) if curr_fps in config.FPS_OPTIONS else 1

        y5 = y4 + 118
        self.fps_chips = Chips(
            (px + 48, y5 + 28, pw - 96, 46),
            options=fps_opts,
            selected=sel_fps_idx,
            on_change=self._on_fps_change,
        )

        # Done button
        self.done_btn = Button(
            (px + 48, py + ph - 88, pw - 96, 54),
            "DONE",
            lambda: self.ctx.scenes.pop(),
            style="primary",
        )

    def _update_setting(self, key: str, val: Any) -> None:
        if hasattr(self.ctx.settings, "set"):
            self.ctx.settings.set(**{key: val})

    def _sync_depth_chips_enabled(self) -> None:
        mode_key = _ENGINE_MODE_OPTIONS[self.engine_chips.selected][0]
        # Disabled only when Stockfish is explicitly forced
        self.depth_chips.enabled = not (self.sf_available and mode_key == "stockfish")

    def _on_engine_mode_change(self, idx: int) -> None:
        mode_key = _ENGINE_MODE_OPTIONS[idx][0]
        if not self.sf_available and mode_key != "custom":
            self.engine_chips.selected = 1
            mode_key = "custom"
        self._update_setting("engine_mode", mode_key)
        self._sync_depth_chips_enabled()

    def _on_depth_change(self, idx: int) -> None:
        depth_val = config.CUSTOM_MAX_DEPTH_OPTIONS[idx]
        self._update_setting("custom_max_depth", depth_val)

    def _on_fps_change(self, idx: int) -> None:
        fps_val = config.FPS_OPTIONS[idx]
        self._update_setting("fps", fps_val)

    def _engine_mode_subtitle(self) -> tuple[str, tuple[int, int, int]]:
        if not self.sf_available:
            return ("Stockfish not found — Custom Engine only", DANGER)
        mode_key = _ENGINE_MODE_OPTIONS[self.engine_chips.selected][0]
        if mode_key == "custom":
            return ("Always uses the built-in Custom Engine", SECONDARY)
        if mode_key == "stockfish":
            return ("Always uses Stockfish for play and evaluation", SECONDARY)
        return ("Automatically switches between Custom Engine and Stockfish", SECONDARY)

    def _depth_subtitle(self) -> str:
        depth_val = config.CUSTOM_MAX_DEPTH_OPTIONS[self.depth_chips.selected]
        mode_key = _ENGINE_MODE_OPTIONS[self.engine_chips.selected][0]
        if self.sf_available and mode_key == "stockfish":
            return "Not used while Stockfish is selected"
        if not self.sf_available or mode_key == "custom":
            return f"Maximum search depth for Custom Engine evaluations (depth {depth_val})"
        return f"Use Custom Engine up to depth {depth_val}, then switch to Stockfish"

    def handle_event(self, event: pygame.event.Event) -> None:
        if self.back_btn.handle_event(event):
            return

        if event.type == pygame.KEYDOWN and event.key in (pygame.K_ESCAPE, pygame.K_RETURN):
            self.ctx.scenes.pop()
            return

        if self.audio_toggle.handle_event(event):
            return
        if self.book_toggle.handle_event(event):
            return
        if self.engine_chips.handle_event(event):
            return
        if self.depth_chips.handle_event(event):
            return
        if self.fps_chips.handle_event(event):
            return
        self.done_btn.handle_event(event)

    def update(self, dt: float) -> None:
        self.back_btn.update(dt)
        self.done_btn.update(dt)
        if not self.sf_available:
            caps = self.ctx.engines.capabilities()
            if caps.stockfish_available:
                self.sf_available = True
                self.engine_chips.enabled = True
                raw_mode = getattr(self.ctx.settings, "engine_mode", None)
                if raw_mode not in ("auto", "custom", "stockfish"):
                    raw_mode = "auto" if getattr(self.ctx.settings, "smart_engine", True) else "custom"
                mode_keys = [k for k, _ in _ENGINE_MODE_OPTIONS]
                self.engine_chips.selected = mode_keys.index(raw_mode) if raw_mode in mode_keys else 0
                self._sync_depth_chips_enabled()

    def draw(self, surf: pygame.Surface) -> None:
        surf.fill(theme.BG)

        # Title and back button
        draw_text(surf, "SETTINGS", "title", INK, (314, 74), anchor="center")
        self.back_btn.draw(surf)

        draw_panel(surf, self.panel_rect, fill=CARD, border=BORDER, shadow=SHADOW, shadow_color=INK)
        px, py, pw, _ = self.panel_rect

        # Header
        draw_text(surf, "SETTINGS", "heading", INK, (self.panel_rect.centerx, py + 26), anchor="midtop")

        sub_max_w = pw - 245

        # 1. Audio toggle
        y1 = py + 78
        draw_text(surf, "AUDIO EFFECTS", "label", INK, (px + 48, y1), anchor="topleft")
        draw_wrapped_text(surf, "Play move, capture, check and clock sounds", "small", SECONDARY, (px + 48, y1 + 22), max_w=sub_max_w, max_lines=2)
        self.audio_toggle.draw(surf)

        # 2. Opening book toggle
        y2 = y1 + 70
        draw_text(surf, "USE OPENING BOOK", "label", INK, (px + 48, y2), anchor="topleft")
        draw_wrapped_text(surf, "Built-in polyglot opening book responses", "small", SECONDARY, (px + 48, y2 + 22), max_w=sub_max_w, max_lines=2)
        self.book_toggle.draw(surf)

        # 3. Smart select engine mode
        y3 = y2 + 70
        draw_text(surf, "SMART SELECT", "label", INK, (px + 48, y3), anchor="topleft")
        sub_text, sub_col = self._engine_mode_subtitle()
        draw_wrapped_text(surf, sub_text, "small", sub_col, (px + 48, y3 + 22), max_w=pw - 96, max_lines=2)
        self.engine_chips.draw(surf)

        # 4. Custom engine max depth before switching to Stockfish
        y4 = y3 + 118
        draw_text(surf, "CUSTOM ENGINE MAX DEPTH", "label", INK, (px + 48, y4), anchor="topleft")
        draw_wrapped_text(surf, self._depth_subtitle(), "small", SECONDARY, (px + 48, y4 + 22), max_w=pw - 96, max_lines=2)
        self.depth_chips.draw(surf)

        # 5. Frame rate chips
        y5 = y4 + 118
        draw_text(surf, "TARGET FRAME RATE", "label", INK, (px + 48, y5), anchor="topleft")
        self.fps_chips.draw(surf)

        # Done button
        self.done_btn.draw(surf)
