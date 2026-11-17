"""
openboard.ui.scenes.opponent_select
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Opponent selection scene: Pass & Play or VS Engine.
"""

from __future__ import annotations

import math
from typing import Any

import pygame

from openboard import config
from openboard.ui import theme
from openboard.ui.scenes.base import Scene
from openboard.ui.theme import BORDER, CARD, INK, PURPLE, SHADOW, draw_panel, draw_text, ease_out_cubic
from openboard.ui.widgets import Button


class OpponentSelectScene(Scene):
    """Opponent selection with animated tilted cards."""

    name = "opponent_select"

    def on_enter(self, **_kw: Any) -> None:
        self.focused_idx: int = 0  # 0: Pass & Play, 1: VS Engine
        self.back_btn = Button((60, 48, 140, 52), "BACK", lambda: self.ctx.scenes.go("main_menu"), style="secondary")

        # Card base positions and angles
        # Card 0: Pass & Play (-6 deg)
        # Card 1: VS Engine (+3 deg)
        self.cards = [
            {
                "name": "PASS & PLAY",
                "asset": "card_pass_play",
                "dest": "pass_play_setup",
                "base_x": 450,
                "base_y": 480,
                "angle": -6.0,
                "w": 380,
                "h": 500,
                "hover_t": 0.0,
            },
            {
                "name": "VS ENGINE",
                "asset": "card_vs_engine",
                "dest": "vs_engine_setup",
                "base_x": 1150,
                "base_y": 480,
                "angle": 3.0,
                "w": 380,
                "h": 500,
                "hover_t": 0.0,
            },
        ]

    def _choose_selected(self) -> None:
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
                self._choose_selected()
                return

        if event.type == pygame.MOUSEMOTION:
            for idx, c in enumerate(self.cards):
                # Oriented bounding check
                cx, cy = c["base_x"], c["base_y"]
                w, h = c["w"], c["h"]
                r = pygame.Rect(cx - w // 2, cy - h // 2, w, h)
                if r.collidepoint(event.pos):
                    self.focused_idx = idx

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for idx, c in enumerate(self.cards):
                cx, cy = c["base_x"], c["base_y"]
                w, h = c["w"], c["h"]
                r = pygame.Rect(cx - w // 2, cy - h // 2, w, h)
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
        try:
            bg = self.ctx.assets.background("bg_silhouettes")
            surf.blit(bg, (0, 0))
        except Exception:
            surf.fill(theme.BG)

        # Large purple diagonal panel
        poly_pts = [
            (820, 0),
            (config.DESIGN_W, 0),
            (config.DESIGN_W, config.DESIGN_H),
            (560, config.DESIGN_H),
        ]
        pygame.draw.polygon(surf, PURPLE, poly_pts)
        pygame.draw.lines(surf, INK, False, [(820, 0), (560, config.DESIGN_H)], BORDER)

        # Title
        draw_text(surf, "CHOOSE OPPONENT", "title", INK, (config.DESIGN_W // 2, 70), anchor="center")

        # Draw cards
        for idx, c in enumerate(self.cards):
            t = ease_out_cubic(c["hover_t"])
            lift = t * 16.0
            angle = c["angle"] * (1.0 - t * 0.4)  # Straightens slightly on hover
            shadow_dist = SHADOW + t * 6.0

            w, h = c["w"], c["h"]
            cx = c["base_x"]
            cy = c["base_y"] - lift

            # Create unrotated card surface
            card_surf = pygame.Surface((w, h), pygame.SRCALPHA)
            inner_rect = pygame.Rect(0, 0, w - int(shadow_dist), h - int(shadow_dist))
            draw_panel(
                card_surf,
                inner_rect,
                fill=CARD,
                border=BORDER + (1 if idx == self.focused_idx else 0),
                shadow=int(shadow_dist),
                shadow_color=INK,
            )

            # Draw card artwork
            try:
                card_img = self.ctx.assets.image(c["asset"])
                cw = min(card_img.get_width(), inner_rect.width - 40)
                ch = min(card_img.get_height(), inner_rect.height - 120)
                if card_img.get_width() != cw or card_img.get_height() != ch:
                    card_img = pygame.transform.smoothscale(card_img, (cw, ch))
                card_surf.blit(card_img, (inner_rect.centerx - cw // 2, inner_rect.y + 36))
            except Exception:
                pass

            # Card title
            draw_text(card_surf, c["name"], "heading", INK, (inner_rect.centerx, inner_rect.bottom - 48), anchor="center")

            # Rotate card
            rotated = pygame.transform.rotozoom(card_surf, angle, 1.0)
            rot_rect = rotated.get_rect(center=(int(cx), int(cy)))
            surf.blit(rotated, rot_rect)

        # Back button
        self.back_btn.draw(surf)
