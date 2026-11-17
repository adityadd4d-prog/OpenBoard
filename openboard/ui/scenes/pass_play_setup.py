"""
openboard.ui.scenes.pass_play_setup
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Pass & Play match configuration scene.
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
from openboard.ui.theme import BORDER, CARD, INK, SHADOW, TINT, draw_panel, draw_text
from openboard.ui.widgets import Button, Chips, TextInput


class PassPlaySetupScene(Scene):
    """Configuration screen for local two-player pass and play."""

    name = "pass_play_setup"

    def on_enter(self, **_kw: Any) -> None:
        self.back_btn = Button((60, 48, 140, 52), "BACK", lambda: self.ctx.scenes.go("opponent_select"), style="secondary")

        pw = 640
        ph = 560
        px = (config.DESIGN_W - pw) // 2
        py = (config.DESIGN_H - ph) // 2
        self.panel_rect = pygame.Rect(px, py, pw, ph)

        # Player 2 name input
        self.p2_input = TextInput(
            (px + 48, py + 120, pw - 96, 56),
            text="Player 2",
            max_len=config.NAME_MAX,
            placeholder="Enter Player 2 name",
            on_change=self._validate_input,
            on_submit=lambda _: self._start_game(),
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

        self._validate_input(self.p2_input.text)

    def _validate_input(self, text: str) -> None:
        cleaned = text.strip()
        is_valid = 1 <= len(cleaned) <= config.NAME_MAX
        self.p2_input.invalid = not is_valid
        self.start_btn.enabled = is_valid

    def _on_tc_change(self, idx: int) -> None:
        tc_key = list(config.TIME_CONTROLS.keys())[idx]
        if hasattr(self.ctx.profile, "set_time_control"):
            self.ctx.profile.set_time_control(tc_key)

    def _start_game(self) -> None:
        if not self.start_btn.enabled:
            return

        p1_name = getattr(self.ctx.profile.profile, "name", "Player 1").strip()
        p2_name = self.p2_input.text.strip()
        if p1_name == p2_name:
            p2_name = f"{p2_name} (2)"

        # Randomize colors
        p1_color = random.choice([chess.WHITE, chess.BLACK])
        if p1_color == chess.WHITE:
            white_info = PlayerInfo(name=p1_name, kind="human")
            black_info = PlayerInfo(name=p2_name, kind="human")
        else:
            white_info = PlayerInfo(name=p2_name, kind="human")
            black_info = PlayerInfo(name=p1_name, kind="human")

        tc_key = list(config.TIME_CONTROLS.keys())[self.tc_chips.selected]
        time_control = config.TIME_CONTROLS[tc_key]

        self.ctx.scenes.go(
            "game",
            mode="pass_play",
            white=white_info,
            black=black_info,
            time_control=time_control,
            player1_color=p1_color,
        )

    def handle_event(self, event: pygame.event.Event) -> None:
        if self.back_btn.handle_event(event):
            return

        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.ctx.scenes.go("opponent_select")
            return

        if self.p2_input.handle_event(event):
            return
        if self.tc_chips.handle_event(event):
            return
        self.start_btn.handle_event(event)

    def update(self, dt: float) -> None:
        self.back_btn.update(dt)
        self.p2_input.update(dt)
        self.start_btn.update(dt)

    def draw(self, surf: pygame.Surface) -> None:
        try:
            bg = self.ctx.assets.background("bg_silhouettes")
            surf.blit(bg, (0, 0))
        except Exception:
            surf.fill(theme.BG)

        draw_panel(surf, self.panel_rect, fill=CARD, border=BORDER, shadow=SHADOW, shadow_color=INK)

        # Panel header
        draw_text(surf, "PASS & PLAY SETUP", "heading", INK, (self.panel_rect.centerx, self.panel_rect.y + 36), anchor="midtop")

        # Player 2 input label & helper
        draw_text(surf, "PLAYER 2 NAME", "label", INK, (self.panel_rect.x + 48, self.panel_rect.y + 94), anchor="bottomleft")
        p1_name = getattr(self.ctx.profile.profile, "name", "Player 1")
        helper_msg = f"Player 1: {p1_name} · Colors assigned randomly"
        draw_text(surf, helper_msg, "small", TINT, (self.panel_rect.x + 48, self.panel_rect.y + 186), anchor="topleft")

        # Time control label
        draw_text(surf, "TIME CONTROL", "label", INK, (self.panel_rect.x + 48, self.panel_rect.y + 234), anchor="bottomleft")

        self.p2_input.draw(surf)
        self.tc_chips.draw(surf)
        self.start_btn.draw(surf)
        self.back_btn.draw(surf)
