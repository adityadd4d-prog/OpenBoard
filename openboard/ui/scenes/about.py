"""
openboard.ui.scenes.about
~~~~~~~~~~~~~~~~~~~~~~~~~
About screen displaying controls, credits, licenses, and external links.
"""

from __future__ import annotations

import logging
import webbrowser
from typing import Any

import pygame

from openboard import config
from openboard.ui import theme
from openboard.ui.scenes.base import Scene
from openboard.ui.theme import ACCENT, BORDER, CARD, CARD_BORDER, INK, PURPLE, SHADOW, TINT, draw_panel, draw_text, wrap_text
from openboard.ui.widgets import Button, ScrollList

log = logging.getLogger("openboard.ui.scenes.about")


class AboutScene(Scene):
    """About dialog with controls, engine information, and third-party licenses."""

    name = "about"

    def on_enter(self, **_kw: Any) -> None:
        self.back_btn = Button((60, 48, 140, 52), "BACK", lambda: self.ctx.scenes.go("main_menu"), style="secondary")

        pw = 1100
        ph = 700
        px = (config.DESIGN_W - pw) // 2
        py = 120
        self.panel_rect = pygame.Rect(px, py, pw, ph)

        # GitHub link button
        self.github_btn = Button(
            (px + 48, py + ph - 80, 240, 48),
            "GITHUB REPO ↗",
            self._open_github,
            style="secondary",
        )

        # Stockfish source button
        self.stockfish_btn = Button(
            (px + 308, py + ph - 80, 260, 48),
            "STOCKFISH SOURCE ↗",
            self._open_stockfish,
            style="secondary",
        )

        # Prepare credits lines
        caps = self.ctx.engines.capabilities()
        sf_name = caps.stockfish_name or "Stockfish (GNU GPLv3)"

        credits_text = [
            ("OpenBoard", f"Version {config.APP_VERSION} — Neo-brutalist offline chess"),
            ("pygame", "v2.x — Multimedia & game engine (LGPL-2.1)"),
            ("python-chess", "Chess rules, move generation, and UCI engine interface (GPL-3.0+)"),
            ("Stockfish", f"{sf_name} — Free software under GNU GPLv3."),
            ("Source Code", config.STOCKFISH_SOURCE_URL),
            ("Inter Font", "Designed by Rasmus Andersson — SIL Open Font License 1.1"),
            ("platformdirs", "Standard cross-platform storage directories (MIT)"),
            ("Pillow", "Image processing pipeline tools (HPND)"),
        ]

        self.credits_list = ScrollList(
            (px + 520, py + 160, pw - 568, ph - 260),
            item_height=56,
            draw_item=self._draw_credit_row,
            items=credits_text,
        )

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

    def _draw_credit_row(self, surf: pygame.Surface, item: tuple[str, str], rect: pygame.Rect, idx: int, hovered: bool) -> None:
        title, desc = item
        draw_text(surf, title, "label", INK, (rect.x + 8, rect.y + 6), anchor="topleft")
        draw_text(surf, desc, "small", TINT, (rect.x + 8, rect.bottom - 8), anchor="bottomleft")
        pygame.draw.line(surf, CARD_BORDER, (rect.x, rect.bottom - 1), (rect.right, rect.bottom - 1), 1)

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
        self.credits_list.handle_event(event)

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

        self.back_btn.draw(surf)

        draw_panel(surf, self.panel_rect, fill=CARD, border=BORDER, shadow=SHADOW, shadow_color=INK)
        px, py, pw, ph = self.panel_rect

        # Emblem & Header (Left column)
        try:
            emblem = self.ctx.assets.image("emblem")
            surf.blit(emblem, (px + 48, py + 48))
        except Exception:
            pass

        draw_text(surf, "OPENBOARD", "title", INK, (px + 180, py + 56), anchor="topleft")
        draw_text(surf, f"OFFLINE DESKTOP CHESS  ·  v{config.APP_VERSION}", "small", PURPLE, (px + 180, py + 104), anchor="topleft")

        # Controls reference
        ctrl_y = py + 180
        draw_text(surf, "CONTROLS", "heading", INK, (px + 48, ctrl_y), anchor="topleft")

        controls = [
            ("MOVE", "Click square or drag and drop piece"),
            ("PLAY", "Blitz (3 + 2) and Rapid (10 + 0)"),
            ("EVALUATE", "FEN, SAN, or LAN move sequences"),
            ("HOTKEYS", "F11 Fullscreen  ·  F2 Design Overlay"),
        ]

        cy = ctrl_y + 46
        for action, desc in controls:
            draw_text(surf, action, "label", ACCENT, (px + 48, cy), anchor="topleft")
            draw_text(surf, desc, "body", INK, (px + 48, cy + 24), anchor="topleft")
            cy += 60

        # Credits & Licenses (Right column)
        draw_text(surf, "CREDITS & LICENSES", "heading", INK, (px + 520, py + 110), anchor="topleft")
        self.credits_list.draw(surf)

        # Action buttons
        self.github_btn.draw(surf)
        self.stockfish_btn.draw(surf)
