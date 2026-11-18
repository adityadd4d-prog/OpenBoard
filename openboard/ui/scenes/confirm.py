"""
openboard.ui.scenes.confirm
~~~~~~~~~~~~~~~~~~~~~~~~~~~
Modal confirmation dialog.
"""

from __future__ import annotations

from typing import Any, Callable

import pygame

from openboard import config
from openboard.ui import theme
from openboard.ui.scenes.base import Scene
from openboard.ui.theme import BORDER, CARD, INK, SHADOW, draw_panel, draw_text, draw_wrapped_text, fit_text, wrap_text
from openboard.ui.widgets import Button


class ConfirmScene(Scene):
    """Modal dialog overlay with YES/NO or OK buttons."""

    name = "confirm"
    is_modal = True

    def on_enter(
        self,
        title: str = "CONFIRM ACTION",
        message: str = "",
        yes_label: str = "YES",
        no_label: str = "NO",
        single_button: bool = False,
        on_result: Callable[[bool], None] | None = None,
        **_kw: Any,
    ) -> None:
        self.title = title
        self.message = message
        self.yes_label = yes_label
        self.no_label = no_label
        self.single_button = single_button
        self.on_result = on_result

        # Centred panel matching reference mockup
        panel_w = 754
        panel_h = 354
        px = (config.DESIGN_W - panel_w) // 2
        py = (config.DESIGN_H - panel_h) // 2
        self.panel_rect = pygame.Rect(px, py, panel_w, panel_h)

        btn_w = 220
        btn_h = 56
        btn_y = self.panel_rect.bottom - btn_h - 36

        if single_button:
            bx = self.panel_rect.centerx - btn_w // 2
            self.yes_btn = Button((bx, btn_y, btn_w, btn_h), yes_label, self._on_yes, style="primary")
            self.no_btn = None
        else:
            spacing = 32
            bx_no = self.panel_rect.centerx - btn_w - spacing // 2
            bx_yes = self.panel_rect.centerx + spacing // 2
            self.no_btn = Button((bx_no, btn_y, btn_w, btn_h), no_label, self._on_no, style="secondary")
            self.yes_btn = Button((bx_yes, btn_y, btn_w, btn_h), yes_label, self._on_yes, style="primary")

    def _on_yes(self) -> None:
        cb = self.on_result
        self.ctx.scenes.pop(result=True)
        if cb:
            cb(True)

    def _on_no(self) -> None:
        cb = self.on_result
        self.ctx.scenes.pop(result=False)
        if cb:
            cb(False)

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_ESCAPE, pygame.K_n):
                self._on_no()
                return
            if event.key in (pygame.K_RETURN, pygame.K_y, pygame.K_SPACE):
                self._on_yes()
                return

        if self.yes_btn.handle_event(event):
            return
        if self.no_btn and self.no_btn.handle_event(event):
            return

    def update(self, dt: float) -> None:
        self.yes_btn.update(dt)
        if self.no_btn:
            self.no_btn.update(dt)

    def draw(self, surf: pygame.Surface) -> None:
        # Note: scene_manager draws the dimmed background of the previous scene
        draw_panel(surf, self.panel_rect, fill=CARD, border=BORDER, shadow=SHADOW, shadow_color=INK)

        # Title
        draw_text(
            surf,
            fit_text(self.title, "heading", self.panel_rect.width - 64),
            "heading",
            INK,
            (self.panel_rect.centerx, self.panel_rect.y + 36),
            anchor="midtop",
        )

        # Message wrapped (max 5 lines so it never collides with buttons)
        draw_wrapped_text(
            surf,
            self.message,
            "body",
            INK,
            (self.panel_rect.centerx, self.panel_rect.y + 90),
            max_w=self.panel_rect.width - 64,
            line_gap=6,
            anchor="midtop",
            max_lines=5,
        )

        self.yes_btn.draw(surf)
        if self.no_btn:
            self.no_btn.draw(surf)
