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
from openboard.ui.theme import BORDER, CARD, INK, PURPLE, SHADOW, TINT, draw_panel, draw_text
from openboard.ui.widgets import Button, Chips, TextInput


class PassPlaySetupScene(Scene):
    """Configuration screen for local two-player pass and play."""

    name = "pass_play_setup"

    def on_enter(self, **_kw: Any) -> None:
        self.back_btn = Button(
            (64, 48, 128, 52),
            "BACK",
            lambda: self.ctx.scenes.go("opponent_select"),
            style="secondary",
            shadow=8,
        )

        # Center modal card matching assets/reference/pass_play.png
        self.panel_rect = pygame.Rect(400, 196, 800, 560)

        # Player 2 name input
        self.p2_input = TextInput(
            (656, 284, 504, 64),
            text="Alex",
            max_len=config.NAME_MAX,
            placeholder="Enter Player 2 name",
            on_change=self._validate_input,
            on_submit=lambda _: self._start_game(),
            fill=TINT,
            shadow=0,
            border_color=INK,
        )

        # Time control selection
        pref_tc = getattr(self.ctx.profile.profile, "preferred_time_control", "rapid")
        tc_keys = list(config.TIME_CONTROLS.keys())
        sel_idx = tc_keys.index(pref_tc) if pref_tc in tc_keys else 1
        options = [tc.label for tc in config.TIME_CONTROLS.values()]

        self.tc_chips = Chips(
            (656, 482, 504, 64),
            options=options,
            selected=sel_idx,
            on_change=self._on_tc_change,
            font_role="label",
            shadow=8,
            spacing=15,
            chip_w=158,
            text_color=INK,
        )

        # Start button
        self.start_btn = Button(
            (440, 628, 720, 64),
            "START GAME",
            self._start_game,
            style="primary",
            shadow=8,
            text_color_override=INK,
            font_role="heading",
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

        # Back button
        self.back_btn.draw(surf)

        # Top bar title
        draw_text(surf, "PASS & PLAY", "title", INK, (263, 56), anchor="topleft")

        # Modal panel
        draw_panel(surf, self.panel_rect, fill=CARD, border=BORDER, shadow=8, shadow_color=INK)

        # Section heading
        draw_text(surf, "PLAYERS", "heading", INK, (440, 230), anchor="topleft")

        # Player 2 row
        draw_text(surf, "PLAYER 2", "heading", INK, (440, 302), anchor="topleft")
        self.p2_input.draw(surf)

        # Helper text
        draw_text(
            surf,
            "Player 1 from profile · Colors assigned randomly",
            "body",
            INK,
            (440, 390),
            anchor="topleft",
        )

        # Time row
        draw_text(surf, "TIME", "heading", INK, (440, 502), anchor="topleft")
        self.tc_chips.draw(surf)

        # Start button
        self.start_btn.draw(surf)
