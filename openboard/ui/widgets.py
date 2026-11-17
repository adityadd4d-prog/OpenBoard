"""
openboard.ui.widgets
~~~~~~~~~~~~~~~~~~~~
Neo-brutalist widget library drawn entirely in code via openboard.ui.theme.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Callable

import pygame

from openboard.ui import theme
from openboard.ui.theme import (
    ACCENT,
    BORDER,
    CARD,
    CARD_BORDER,
    DANGER,
    INK,
    PURPLE,
    SHADOW,
    TINT,
    draw_panel,
    draw_text,
    font,
)

log = logging.getLogger("openboard.ui.widgets")


class Widget:
    """Base class for all interactive and visual widgets."""

    def __init__(self, rect: pygame.Rect | tuple[int, int, int, int]) -> None:
        self.rect = pygame.Rect(rect)
        self.visible: bool = True
        self.enabled: bool = True
        self.hovered: bool = False
        self.pressed: bool = False
        self.focused: bool = False

    def handle_event(self, event: pygame.event.Event) -> bool:
        """Handle an input event. Return True if consumed."""
        return False

    def update(self, dt: float) -> None:
        """Advance time-based animations or timers."""
        pass

    def draw(self, surf: pygame.Surface) -> None:
        """Render widget onto target surface."""
        pass


class Button(Widget):
    """Neo-brutalist push button with flat fills, ink borders, and hard shadow."""

    def __init__(
        self,
        rect: pygame.Rect | tuple[int, int, int, int],
        label: str,
        on_click: Callable[[], None] | None = None,
        style: str = "primary",  # 'primary' | 'secondary' | 'ghost'
    ) -> None:
        super().__init__(rect)
        self.label = label
        self.on_click = on_click
        self.style = style

    def handle_event(self, event: pygame.event.Event) -> bool:
        if not self.visible or not self.enabled:
            return False

        if event.type == pygame.MOUSEMOTION:
            self.hovered = self.rect.collidepoint(event.pos)
            return False

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                self.pressed = True
                return True

        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self.pressed:
                self.pressed = False
                if self.rect.collidepoint(event.pos):
                    if self.on_click:
                        self.on_click()
                    return True

        if event.type == pygame.KEYDOWN and self.focused:
            if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                if self.on_click:
                    self.on_click()
                return True

        return False

    def draw(self, surf: pygame.Surface) -> None:
        if not self.visible:
            return

        # Styling
        if not self.enabled:
            fill_col = CARD
            text_col = TINT
            border_col = CARD_BORDER
            shadow_val = 0
            offset = 0
        else:
            if self.style == "primary":
                fill_col = PURPLE if not self.pressed else ACCENT
                text_col = CARD
            elif self.style == "secondary":
                fill_col = CARD if not self.pressed else TINT
                text_col = INK
            else:  # ghost
                fill_col = (0, 0, 0, 0)
                text_col = INK

            border_col = INK
            # Hover lifts (shadow slightly larger or offset), press sinks onto shadow
            if self.pressed:
                shadow_val = 1
                offset = SHADOW - 1
            elif self.hovered or self.focused:
                shadow_val = SHADOW + 2
                offset = -1
            else:
                shadow_val = SHADOW if self.style != "ghost" else 0
                offset = 0

        draw_rect = self.rect.move(offset, offset)
        if self.style != "ghost" or self.hovered:
            draw_panel(
                surf,
                draw_rect,
                fill=fill_col if self.style != "ghost" else CARD,
                border=BORDER,
                shadow=shadow_val,
                shadow_color=INK,
            )
        else:
            pygame.draw.rect(surf, INK, draw_rect, BORDER)

        # Draw label
        draw_text(surf, self.label, "label", text_col, draw_rect.center, anchor="center")


class Chips(Widget):
    """Single-select option chips (e.g. BLITZ/RAPID, FEN/SAN/LAN, Level 1-8)."""

    def __init__(
        self,
        rect: pygame.Rect | tuple[int, int, int, int],
        options: list[str],
        selected: int = 0,
        on_change: Callable[[int], None] | None = None,
        columns: int = 0,
    ) -> None:
        super().__init__(rect)
        self.options = options
        self.selected = selected
        self.on_change = on_change
        self.columns = columns if columns > 0 else len(options)
        self._chip_rects: list[pygame.Rect] = []
        self._recalc()

    def _recalc(self) -> None:
        self._chip_rects.clear()
        n = len(self.options)
        if n == 0:
            return

        cols = min(self.columns, n)
        rows = (n + cols - 1) // cols
        spacing = 8
        chip_w = (self.rect.width - (cols - 1) * spacing) // cols
        chip_h = (self.rect.height - (rows - 1) * spacing) // rows

        for i in range(n):
            c = i % cols
            r = i // cols
            x = self.rect.x + c * (chip_w + spacing)
            y = self.rect.y + r * (chip_h + spacing)
            self._chip_rects.append(pygame.Rect(x, y, chip_w, chip_h))

    def handle_event(self, event: pygame.event.Event) -> bool:
        if not self.visible or not self.enabled:
            return False

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for idx, r in enumerate(self._chip_rects):
                if r.collidepoint(event.pos):
                    if self.selected != idx:
                        self.selected = idx
                        if self.on_change:
                            self.on_change(idx)
                    return True
        return False

    def draw(self, surf: pygame.Surface) -> None:
        if not self.visible:
            return

        for idx, (opt, r) in enumerate(zip(self.options, self._chip_rects)):
            is_sel = idx == self.selected
            fill_col = PURPLE if is_sel else CARD
            text_col = CARD if is_sel else INK
            draw_panel(surf, r, fill=fill_col, border=BORDER, shadow=2 if not is_sel else 0)
            draw_text(surf, opt, "label", text_col, r.center, anchor="center")


class Toggle(Widget):
    """Neo-brutalist ON/OFF toggle switch matching mockup style."""

    def __init__(
        self,
        rect: pygame.Rect | tuple[int, int, int, int],
        on: bool = True,
        on_change: Callable[[bool], None] | None = None,
    ) -> None:
        super().__init__(rect)
        self.on = on
        self.on_change = on_change

    def handle_event(self, event: pygame.event.Event) -> bool:
        if not self.visible or not self.enabled:
            return False

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                self.on = not self.on
                if self.on_change:
                    self.on_change(self.on)
                return True
        return False

    def draw(self, surf: pygame.Surface) -> None:
        if not self.visible:
            return

        track_w = 90
        track_h = 36
        track_r = pygame.Rect(self.rect.x, self.rect.centery - track_h // 2, track_w, track_h)

        track_fill = PURPLE if self.on else TINT
        draw_panel(surf, track_r, fill=track_fill, border=BORDER, shadow=3)

        knob_w = 34
        knob_h = 28
        knob_x = track_r.right - knob_w - 4 if self.on else track_r.x + 4
        knob_y = track_r.centery - knob_h // 2
        knob_r = pygame.Rect(knob_x, knob_y, knob_w, knob_h)
        pygame.draw.rect(surf, CARD, knob_r)
        pygame.draw.rect(surf, INK, knob_r, BORDER)

        label = "ON" if self.on else "OFF"
        text_pos = (track_r.right + 16, self.rect.centery)
        draw_text(surf, label, "label", INK, text_pos, anchor="midleft")


class TextInput(Widget):
    """Single-line text box with caret, clipboard support, and validation state."""

    def __init__(
        self,
        rect: pygame.Rect | tuple[int, int, int, int],
        text: str = "",
        max_len: int = 100,
        placeholder: str = "",
        filter_func: Callable[[str], bool] | None = None,
        on_change: Callable[[str], None] | None = None,
        on_submit: Callable[[str], None] | None = None,
    ) -> None:
        super().__init__(rect)
        self.text = text
        self.max_len = max_len
        self.placeholder = placeholder
        self.filter_func = filter_func
        self.on_change = on_change
        self.on_submit = on_submit

        self.caret: int = len(text)
        self.invalid: bool = False
        self._blink_t: float = 0.0
        self._caret_visible: bool = True

    def handle_event(self, event: pygame.event.Event) -> bool:
        if not self.visible or not self.enabled:
            return False

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                self.focused = True
                f = font("body")
                rel_x = event.pos[0] - (self.rect.x + 12)
                best_idx = len(self.text)
                for idx in range(len(self.text) + 1):
                    w, _ = f.size(self.text[:idx])
                    if w >= rel_x:
                        best_idx = idx
                        break
                self.caret = best_idx
                self._caret_visible = True
                self._blink_t = 0.0
                return True
            else:
                self.focused = False

        if not self.focused:
            return False

        if event.type == pygame.KEYDOWN:
            self._caret_visible = True
            self._blink_t = 0.0

            if event.key == pygame.K_BACKSPACE:
                if self.caret > 0:
                    self.text = self.text[: self.caret - 1] + self.text[self.caret :]
                    self.caret -= 1
                    if self.on_change:
                        self.on_change(self.text)
                return True

            if event.key == pygame.K_DELETE:
                if self.caret < len(self.text):
                    self.text = self.text[: self.caret] + self.text[self.caret + 1 :]
                    if self.on_change:
                        self.on_change(self.text)
                return True

            if event.key == pygame.K_LEFT:
                self.caret = max(0, self.caret - 1)
                return True

            if event.key == pygame.K_RIGHT:
                self.caret = min(len(self.text), self.caret + 1)
                return True

            if event.key == pygame.K_HOME:
                self.caret = 0
                return True

            if event.key == pygame.K_END:
                self.caret = len(self.text)
                return True

            if event.key == pygame.K_RETURN:
                if self.on_submit:
                    self.on_submit(self.text)
                return True

            # Ctrl+A/C/V/X
            if event.mod & pygame.KMOD_CTRL:
                if event.key == pygame.K_v:
                    try:
                        pygame.scrap.init()
                        clip = pygame.scrap.get(pygame.SCRAP_TEXT)
                        if clip:
                            s = clip.decode("utf-8").rstrip("\x00")
                            self._insert_text(s)
                    except Exception:
                        pass
                    return True
                elif event.key == pygame.K_a:
                    self.caret = len(self.text)
                    return True

        if event.type == pygame.TEXTINPUT:
            self._insert_text(event.text)
            return True

        return False

    def _insert_text(self, s: str) -> None:
        for ch in s:
            if ch in ("\r", "\n"):
                continue
            if self.filter_func and not self.filter_func(ch):
                continue
            if len(self.text) < self.max_len:
                self.text = self.text[: self.caret] + ch + self.text[self.caret :]
                self.caret += 1
        if self.on_change:
            self.on_change(self.text)

    def update(self, dt: float) -> None:
        if self.focused:
            self._blink_t += dt
            if self._blink_t >= 0.5:
                self._blink_t = 0.0
                self._caret_visible = not self._caret_visible

    def draw(self, surf: pygame.Surface) -> None:
        if not self.visible:
            return

        border_col = DANGER if self.invalid else (INK if self.focused else CARD_BORDER)
        draw_panel(surf, self.rect, fill=CARD, border=BORDER, shadow=3, shadow_color=border_col)

        inner = self.rect.inflate(-16, -8)
        clip = surf.get_clip()
        surf.set_clip(inner)

        f = font("body")
        if self.text:
            txt_surf = f.render(self.text, True, INK)
            surf.blit(txt_surf, (inner.x, inner.centery - txt_surf.get_height() // 2))
        elif self.placeholder:
            p_surf = f.render(self.placeholder, True, TINT)
            surf.blit(p_surf, (inner.x, inner.centery - p_surf.get_height() // 2))

        if self.focused and self._caret_visible:
            pre = self.text[: self.caret]
            cx = inner.x + f.size(pre)[0]
            cy1 = inner.centery - f.get_height() // 2 + 2
            cy2 = cy1 + f.get_height() - 4
            pygame.draw.line(surf, INK, (cx, cy1), (cx, cy2), 2)

        surf.set_clip(clip)


class TextArea(Widget):
    """Multi-line text editor with word-wrap, scrolling, and monospaced font."""

    def __init__(
        self,
        rect: pygame.Rect | tuple[int, int, int, int],
        text: str = "",
        on_change: Callable[[str], None] | None = None,
    ) -> None:
        super().__init__(rect)
        self.text = text
        self.on_change = on_change
        self.scroll_y = 0

    def handle_event(self, event: pygame.event.Event) -> bool:
        if not self.visible or not self.enabled:
            return False

        if event.type == pygame.MOUSEBUTTONDOWN:
            if self.rect.collidepoint(event.pos):
                self.focused = True
                if event.button == 4:
                    self.scroll_y = max(0, self.scroll_y - 20)
                elif event.button == 5:
                    self.scroll_y += 20
                return True
            else:
                self.focused = False

        if not self.focused:
            return False

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_BACKSPACE:
                if self.text:
                    self.text = self.text[:-1]
                    if self.on_change:
                        self.on_change(self.text)
                return True
            if event.key == pygame.K_RETURN:
                self.text += "\n"
                if self.on_change:
                    self.on_change(self.text)
                return True
            if (event.mod & pygame.KMOD_CTRL) and event.key == pygame.K_v:
                try:
                    pygame.scrap.init()
                    clip = pygame.scrap.get(pygame.SCRAP_TEXT)
                    if clip:
                        s = clip.decode("utf-8").rstrip("\x00")
                        self.text += s
                        if self.on_change:
                            self.on_change(self.text)
                except Exception:
                    pass
                return True

        if event.type == pygame.TEXTINPUT:
            self.text += event.text
            if self.on_change:
                self.on_change(self.text)
            return True

        return False

    def draw(self, surf: pygame.Surface) -> None:
        if not self.visible:
            return

        draw_panel(surf, self.rect, fill=CARD, border=BORDER, shadow=4)
        inner = self.rect.inflate(-16, -16)
        clip = surf.get_clip()
        surf.set_clip(inner)

        f = font("mono")
        line_h = f.get_linesize()
        lines = self.text.split("\n")

        y = inner.y - self.scroll_y
        for line in lines:
            if y + line_h >= inner.y and y <= inner.bottom:
                txt = f.render(line, True, INK)
                surf.blit(txt, (inner.x, y))
            y += line_h

        surf.set_clip(clip)


class Label(Widget):
    """Read-only text label."""

    def __init__(
        self,
        rect: pygame.Rect | tuple[int, int, int, int],
        text: str,
        role: str = "body",
        color: tuple[int, int, int] | None = None,
        anchor: str = "topleft",
    ) -> None:
        super().__init__(rect)
        self.text = text
        self.role = role
        self.color = color or INK
        self.anchor = anchor

    def draw(self, surf: pygame.Surface) -> None:
        if not self.visible:
            return
        draw_text(surf, self.text, self.role, self.color, getattr(self.rect, self.anchor), anchor=self.anchor)


class Panel(Widget):
    """Visual panel wrapper."""

    def __init__(
        self,
        rect: pygame.Rect | tuple[int, int, int, int],
        fill: tuple[int, int, int] | None = None,
        border: int = BORDER,
        shadow: int = SHADOW,
    ) -> None:
        super().__init__(rect)
        self.fill = fill or CARD
        self.border = border
        self.shadow = shadow

    def draw(self, surf: pygame.Surface) -> None:
        if not self.visible:
            return
        draw_panel(surf, self.rect, fill=self.fill, border=self.border, shadow=self.shadow)


class ScrollList(Widget):
    """Smooth scrollable list with mouse-wheel support and slim scrollbar."""

    def __init__(
        self,
        rect: pygame.Rect | tuple[int, int, int, int],
        item_height: int,
        draw_item: Callable[[pygame.Surface, Any, pygame.Rect, int, bool], None],
        items: list[Any],
    ) -> None:
        super().__init__(rect)
        self.item_height = item_height
        self.draw_item = draw_item
        self.items = list(items)
        self.scroll_y = 0
        self._hovered_idx: int | None = None

    def set_items(self, items: list[Any]) -> None:
        self.items = list(items)
        max_scroll = max(0, len(self.items) * self.item_height - self.rect.height)
        self.scroll_y = min(self.scroll_y, max_scroll)

    def scroll_to_bottom(self) -> None:
        max_scroll = max(0, len(self.items) * self.item_height - self.rect.height)
        self.scroll_y = max_scroll

    def handle_event(self, event: pygame.event.Event) -> bool:
        if not self.visible:
            return False

        if event.type == pygame.MOUSEMOTION:
            if self.rect.collidepoint(event.pos):
                rel_y = event.pos[1] - self.rect.y + self.scroll_y
                idx = rel_y // self.item_height
                self._hovered_idx = idx if 0 <= idx < len(self.items) else None
            else:
                self._hovered_idx = None

        if event.type == pygame.MOUSEWHEEL:
            if self.rect.collidepoint(pygame.mouse.get_pos()):
                self.scroll_y -= event.y * self.item_height
                max_scroll = max(0, len(self.items) * self.item_height - self.rect.height)
                self.scroll_y = max(0, min(self.scroll_y, max_scroll))
                return True

        return False

    def draw(self, surf: pygame.Surface) -> None:
        if not self.visible:
            return

        draw_panel(surf, self.rect, fill=CARD, border=BORDER, shadow=0)

        inner = self.rect.inflate(-BORDER * 2, -BORDER * 2)
        clip = surf.get_clip()
        surf.set_clip(inner)

        for idx, item in enumerate(self.items):
            y = inner.y + idx * self.item_height - self.scroll_y
            if y + self.item_height < inner.y or y > inner.bottom:
                continue

            item_rect = pygame.Rect(inner.x, y, inner.width - 8, self.item_height)
            self.draw_item(surf, item, item_rect, idx, idx == self._hovered_idx)

        # Scrollbar
        total_h = len(self.items) * self.item_height
        if total_h > inner.height:
            bar_h = max(24, int(inner.height * (inner.height / total_h)))
            max_scroll = total_h - inner.height
            bar_y = inner.y + int((inner.height - bar_h) * (self.scroll_y / max_scroll))
            sb_rect = pygame.Rect(inner.right - 6, bar_y, 4, bar_h)
            pygame.draw.rect(surf, INK, sb_rect, border_radius=2)

        surf.set_clip(clip)


class FocusManager:
    """Handles Tab / Shift+Tab cycling among widgets."""

    def __init__(self, widgets: list[Widget]) -> None:
        self.widgets = widgets
        self.current_idx: int = -1

    def handle_event(self, event: pygame.event.Event) -> bool:
        if event.type == pygame.KEYDOWN and event.key == pygame.K_TAB:
            enabled_widgets = [w for w in self.widgets if w.enabled and w.visible]
            if not enabled_widgets:
                return False

            if self.current_idx >= 0 and self.current_idx < len(self.widgets):
                self.widgets[self.current_idx].focused = False

            step = -1 if (event.mod & pygame.KMOD_SHIFT) else 1
            self.current_idx = (self.current_idx + step) % len(enabled_widgets)
            target = enabled_widgets[self.current_idx]
            target.focused = True
            return True
        return False

    def reset(self) -> None:
        for w in self.widgets:
            w.focused = False
        self.current_idx = -1


def _demo() -> None:
    pygame.init()
    win = pygame.display.set_mode((1600, 900))
    clock = pygame.time.Clock()

    btn_primary = Button((100, 100, 200, 60), "PRIMARY")
    btn_sec = Button((100, 180, 200, 60), "SECONDARY", style="secondary")
    btn_ghost = Button((100, 260, 200, 60), "GHOST", style="ghost")

    chips = Chips((400, 100, 300, 50), ["BLITZ 3+2", "RAPID 10+0"])
    toggle = Toggle((400, 200, 120, 50), on=True)
    text_input = TextInput((400, 300, 300, 50), text="Player 2", placeholder="Enter name")

    running = True
    while running:
        dt = clock.tick(60) / 1000.0
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                running = False
            btn_primary.handle_event(ev)
            btn_sec.handle_event(ev)
            btn_ghost.handle_event(ev)
            chips.handle_event(ev)
            toggle.handle_event(ev)
            text_input.handle_event(ev)

        btn_primary.update(dt)
        text_input.update(dt)

        win.fill(theme.BG)
        btn_primary.draw(win)
        btn_sec.draw(win)
        btn_ghost.draw(win)
        chips.draw(win)
        toggle.draw(win)
        text_input.draw(win)

        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    _demo()
