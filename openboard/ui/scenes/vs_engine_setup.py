"""
openboard.ui.scenes.vs_engine_setup
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
VS Engine match setup scene.
"""

from __future__ import annotations

import random
from typing import Any

import chess
import pygame

from openboard import config
from openboard.core.session import PlayerInfo
from openboard.ui import theme
from openboard.ui.scenes.base import Scene
from openboard.ui.theme import BORDER, CARD, INK, SECONDARY, SHADOW, TINT, draw_panel, draw_text
from openboard.ui.widgets import Button, Chips


class VsEngineSetupScene(Scene):
    """Configuration screen for player versus engine game."""

    name = "vs_engine_setup"

    def on_enter(self, **_kw: Any) -> None:
        self.back_btn = Button((60, 48, 140, 52), "BACK", lambda: self.ctx.scenes.go("opponent_select"), style="secondary")

        pw = 680
        ph = 560
        px = (config.DESIGN_W - pw) // 2
        py = (config.DESIGN_H - ph) // 2
        self.panel_rect = pygame.Rect(px, py, pw, ph)

        # 8 level chips (1-8, default 4 -> index 3)
        level_options = [str(lvl) for lvl in range(1, 9)]
        self.level_chips = Chips(
            (px + 48, py + 120, pw - 96, 56),
            options=level_options,
            selected=3,  # Level 4
            columns=8,
        )

        # Time control selection
        pref_tc = getattr(self.ctx.profile.profile, "preferred_time_control", "rapid")
        tc_keys = list(config.TIME_CONTROLS.keys())
        sel_idx = tc_keys.index(pref_tc) if pref_tc in tc_keys else 1
        options = [tc.label for tc in config.TIME_CONTROLS.values()]

        self.tc_chips = Chips(
            (px + 48, py + 260, pw - 96, 56),
            options=options,
            selected=sel_idx,
            on_change=self._on_tc_change,
        )

        # Start button
        self.start_btn = Button(
            (px + 48, py + ph - 96, pw - 96, 64),
            "START GAME",
            self._start_game,
            style="primary",
        )

    def _on_tc_change(self, idx: int) -> None:
        tc_key = list(config.TIME_CONTROLS.keys())[idx]
        if hasattr(self.ctx.profile, "set_time_control"):
            self.ctx.profile.set_time_control(tc_key)

    def _start_game(self) -> None:
        level = self.level_chips.selected + 1
        level_spec = config.LEVELS[level]
        engine_name = f"Engine ({level_spec.caption})"
        human_name = getattr(self.ctx.profile.profile, "name", "Player 1").strip()

        # Randomize side
        human_color = random.choice([chess.WHITE, chess.BLACK])
        if human_color == chess.WHITE:
            white_info = PlayerInfo(name=human_name, kind="human")
            black_info = PlayerInfo(name=engine_name, kind="engine", engine_level=level)
        else:
            white_info = PlayerInfo(name=engine_name, kind="engine", engine_level=level)
            black_info = PlayerInfo(name=human_name, kind="human")

        tc_key = list(config.TIME_CONTROLS.keys())[self.tc_chips.selected]
        time_control = config.TIME_CONTROLS[tc_key]

        self.ctx.scenes.go(
            "game",
            mode="vs_engine",
            white=white_info,
            black=black_info,
            time_control=time_control,
            level=level,
            player1_color=human_color,
        )

    def handle_event(self, event: pygame.event.Event) -> None:
        if self.back_btn.handle_event(event):
            return

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.ctx.scenes.go("opponent_select")
                return
            if event.key == pygame.K_LEFT:
                self.level_chips.selected = max(0, self.level_chips.selected - 1)
                return
            if event.key == pygame.K_RIGHT:
                self.level_chips.selected = min(7, self.level_chips.selected + 1)
                return
            if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                self._start_game()
                return

        if self.level_chips.handle_event(event):
            return
        if self.tc_chips.handle_event(event):
            return
        self.start_btn.handle_event(event)

    def update(self, dt: float) -> None:
        self.back_btn.update(dt)
        self.start_btn.update(dt)

    def draw(self, surf: pygame.Surface) -> None:
        try:
            bg = self.ctx.assets.background("bg_silhouettes")
            surf.blit(bg, (0, 0))
        except Exception:
            surf.fill(theme.BG)

        draw_panel(surf, self.panel_rect, fill=CARD, border=BORDER, shadow=SHADOW, shadow_color=INK)

        # Panel header
        draw_text(surf, "VS ENGINE SETUP", "heading", INK, (self.panel_rect.centerx, self.panel_rect.y + 36), anchor="midtop")

        # Engine level label & captions
        draw_text(surf, "DIFFICULTY LEVEL", "label", INK, (self.panel_rect.x + 48, self.panel_rect.y + 94), anchor="bottomleft")
        draw_text(surf, "BEGINNER", "small", SECONDARY, (self.panel_rect.x + 48, self.panel_rect.y + 186), anchor="topleft")
        draw_text(surf, "EXPERT", "small", SECONDARY, (self.panel_rect.right - 48, self.panel_rect.y + 186), anchor="topright")

        # Time control label
        draw_text(surf, "TIME CONTROL", "label", INK, (self.panel_rect.x + 48, self.panel_rect.y + 234), anchor="bottomleft")

        self.level_chips.draw(surf)
        self.tc_chips.draw(surf)
        self.start_btn.draw(surf)
        self.back_btn.draw(surf)
