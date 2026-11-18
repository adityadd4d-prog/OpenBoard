"""
openboard.ui.scenes.opponent_select
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Opponent selection scene: Pass & Play or VS Engine.
"""

from __future__ import annotations

from typing import Any

import pygame

from openboard import config
from openboard.ui import theme
from openboard.ui.scenes.base import Scene
from openboard.ui.theme import CARD, INK, PURPLE, draw_panel, draw_text, ease_out_cubic
from openboard.ui.widgets import Button


class OpponentSelectScene(Scene):
    """Opponent selection with animated tilted cards."""

    name = "opponent_select"

    def on_enter(self, **_kw: Any) -> None:
        self.focused_idx: int = -1  # 0: Pass & Play, 1: VS Engine, -1: resting
        self.back_btn = Button(
            (64, 48, 128, 52),
            "BACK",
            lambda: self.ctx.scenes.go("main_menu"),
            style="secondary",
            shadow=8,
        )

        # Exact Figma coordinates matching assets/reference/opponent.png
        self.cards = [
            {
                "name": "PASS & PLAY",
                "asset": "card_pass_play",
                "dest": "pass_play_setup",
                "x": 290,
                "y": 203,
                "w": 460,
                "h": 504,
                "hover_t": 0.0,
            },
            {
                "name": "VS ENGINE",
                "asset": "card_vs_engine",
                "dest": "vs_engine_setup",
                "x": 865,
                "y": 252,
                "w": 460,
                "h": 504,
                "hover_t": 0.0,
            },
        ]

    def _choose_selected(self) -> None:
        if self.focused_idx in (0, 1):
            dest = self.cards[self.focused_idx]["dest"]
            self.ctx.scenes.go(dest)

    def handle_event(self, event: pygame.event.Event) -> None:
        if self.back_btn.handle_event(event):
            return

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.ctx.scenes.go("main_menu")
                return
            if event.key in (pygame.K_LEFT, pygame.K_a):
                self.focused_idx = 0
                return
            if event.key in (pygame.K_RIGHT, pygame.K_d):
                self.focused_idx = 1
                return
            if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                if self.focused_idx == -1:
                    self.focused_idx = 0
                self._choose_selected()
                return

        if event.type == pygame.MOUSEMOTION:
            hovered_any = False
            for idx, c in enumerate(self.cards):
                r = pygame.Rect(c["x"], c["y"], c["w"], c["h"])
                if r.collidepoint(event.pos):
                    self.focused_idx = idx
                    hovered_any = True
                    break
            if not hovered_any and self.focused_idx != -1:
                self.focused_idx = -1

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for idx, c in enumerate(self.cards):
                r = pygame.Rect(c["x"], c["y"], c["w"], c["h"])
                if r.collidepoint(event.pos):
                    self.focused_idx = idx
                    self._choose_selected()
                    return

    def update(self, dt: float) -> None:
        self.back_btn.update(dt)

        for idx, c in enumerate(self.cards):
            target = 1.0 if idx == self.focused_idx else 0.0
            speed = 1.0 / 0.12  # 120ms ease
            if c["hover_t"] < target:
                c["hover_t"] = min(target, c["hover_t"] + dt * speed)
            elif c["hover_t"] > target:
                c["hover_t"] = max(target, c["hover_t"] - dt * speed)

    def draw(self, surf: pygame.Surface) -> None:
        surf.fill(theme.BG)

        # Large purple diagonal panel on the left side
        poly_pts = [
            (0, 0),
            (939, 0),
            (700, config.DESIGN_H),
            (0, config.DESIGN_H),
        ]
        pygame.draw.polygon(surf, PURPLE, poly_pts)
        pygame.draw.aaline(surf, INK, (939, 0), (700, config.DESIGN_H))

        # Title
        draw_text(surf, "PLAY", "title", INK, (263, 56), anchor="topleft")

        # Back button
        self.back_btn.draw(surf)

        # Draw cards
        for idx, c in enumerate(self.cards):
            t = ease_out_cubic(c["hover_t"])
            lift = t * 12.0

            try:
                card_img = self.ctx.assets.image(c["asset"])
                surf.blit(card_img, (c["x"], int(c["y"] - lift)))
            except Exception:
                pass
