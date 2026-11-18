"""
openboard.ui.scenes.about
~~~~~~~~~~~~~~~~~~~~~~~~~
About screen displaying controls and external repository links.
"""

from __future__ import annotations

import logging
import webbrowser
from typing import Any

import pygame

from openboard import config
from openboard.ui import theme
from openboard.ui.scenes.base import Scene
from openboard.ui.theme import (
    BORDER,
    CARD,
    CARD_BORDER,
    INK,
    SECONDARY,
    draw_panel,
    draw_text,
    draw_wrapped_text,
    fit_text,
)
from openboard.ui.widgets import Button

log = logging.getLogger("openboard.ui.scenes.about")


class AboutScene(Scene):
    """About screen with app info, controls reference, and repository links."""

    name = "about"

    def on_enter(self, **_kw: Any) -> None:
        self.back_btn = Button(
            (64, 48, 128, 52),
            "BACK",
            lambda: self.ctx.scenes.go("main_menu"),
            style="secondary",
            shadow=8,
        )

        # Central card matching the neo-brutalist reference layout
        self.panel_rect = pygame.Rect(350, 210, 900, 560)

        # Two repository link buttons flush with inner margins (x=390..1210)
        self.github_btn = Button(
            (390, 682, 396, 52),
            "GITHUB REPO ↗",
            self._open_github,
            style="secondary",
            shadow=6,
        )
        self.stockfish_btn = Button(
            (814, 682, 396, 52),
            "STOCKFISH SOURCE ↗",
            self._open_stockfish,
            style="secondary",
            shadow=6,
        )

        self._controls: list[tuple[str, str]] = [
            ("MOVE", "Piece → square"),
            ("PLAY", "Blitz 3 + 2  /  Rapid 10 + 0  /  No Clock"),
            ("EVALUATE", "FEN  /  Interactive board"),
        ]

    def _open_github(self) -> None:
        try:
            webbrowser.open(config.GITHUB_URL)
        except Exception as exc:
            log.warning("Could not open GitHub link: %s", exc)

    def _open_stockfish(self) -> None:
        try:
            webbrowser.open(config.STOCKFISH_SOURCE_URL)
        except Exception as exc:
            log.warning("Could not open Stockfish link: %s", exc)

    def handle_event(self, event: pygame.event.Event) -> None:
        if self.back_btn.handle_event(event):
            return

        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.ctx.scenes.go("main_menu")
            return

        if self.github_btn.handle_event(event):
            return
        if self.stockfish_btn.handle_event(event):
            return

    def update(self, dt: float) -> None:
        self.back_btn.update(dt)
        self.github_btn.update(dt)
        self.stockfish_btn.update(dt)

    def draw(self, surf: pygame.Surface) -> None:
        try:
            bg = self.ctx.assets.background("bg_about")
            surf.blit(bg, (0, 0))
        except Exception:
            surf.fill(theme.BG)

        # Top bar: BACK button & ABOUT title
        self.back_btn.draw(surf)
        draw_text(surf, "ABOUT", "title", INK, (263, 52), anchor="topleft")

        # Central card
        draw_panel(surf, self.panel_rect, fill=CARD, border=BORDER, shadow=8, shadow_color=INK)

        # Emblem & header
        try:
            emblem = self.ctx.assets.image("emblem")
            surf.blit(emblem, (398, 250))
        except Exception:
            pass

        draw_text(surf, "OPENBOARD", "title", INK, (546, 260), anchor="topleft")
        subtitle = f"PYGAME CHESS  ·  v{config.APP_VERSION}"
        draw_text(surf, fit_text(subtitle, "small", 650), "small", SECONDARY, (546, 318), anchor="topleft")

        # Horizontal divider
        pygame.draw.line(surf, CARD_BORDER, (390, 393), (1210, 393), 2)

        # Controls section
        draw_text(surf, "CONTROLS", "heading", INK, (390, 428), anchor="topleft")

        label_x = 390
        value_x = 604
        value_max_w = 1210 - value_x
        row_y = 492
        row_step = 56
        for action, desc in self._controls:
            draw_text(surf, fit_text(action, "label", value_x - label_x - 16), "label", INK, (label_x, row_y), anchor="topleft")
            draw_wrapped_text(surf, desc, "body", INK, (value_x, row_y), max_w=value_max_w, line_gap=4, max_lines=2)
            row_y += row_step

        # Repository link buttons
        self.github_btn.draw(surf)
        self.stockfish_btn.draw(surf)
