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
    SECONDARY,
    SHADOW,
    TINT,
    draw_panel,
    draw_text,
    draw_wrapped_text,
    fit_text,
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
        align: str = "center",
        padding_x: int = 0,
        font_role: str = "label",
        shadow: int = SHADOW,
        fill_override: tuple[int, int, int] | None = None,
        text_color_override: tuple[int, int, int] | None = None,
    ) -> None:
        super().__init__(rect)
        self.label = label
        self.on_click = on_click
        self.style = style
        self.align = align
        self.padding_x = padding_x
        self.font_role = font_role
        self.shadow = shadow
        self.fill_override = fill_override
        self.text_color_override = text_color_override

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
            text_col = SECONDARY
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

            if self.fill_override is not None:
                fill_col = self.fill_override
            if self.text_color_override is not None:
                text_col = self.text_color_override

            border_col = INK
            # Hover lifts (shadow slightly larger or offset), press sinks onto shadow
            if self.pressed:
                shadow_val = 1
                offset = self.shadow - 1
            elif self.hovered:
                shadow_val = self.shadow + 2
                offset = -1
            else:
                shadow_val = self.shadow if self.style != "ghost" else 0
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
        if self.align == "left":
            draw_text(surf, self.label, self.font_role, text_col, (draw_rect.left + self.padding_x, draw_rect.centery), anchor="midleft")
        else:
            draw_text(surf, self.label, self.font_role, text_col, draw_rect.center, anchor="center")


class Chips(Widget):
    """Single-select option chips (e.g. BLITZ/RAPID, FEN/SAN/LAN, Level 1-8)."""

    def __init__(
        self,
        rect: pygame.Rect | tuple[int, int, int, int],
        options: list[str],
        selected: int = 0,
        on_change: Callable[[int], None] | None = None,
        columns: int = 0,
        spacing: int = 8,
        chip_w: int | None = None,
        shadow: int = 2,
        font_role: str = "label",
        text_color: tuple[int, int, int] | None = None,
    ) -> None:
        super().__init__(rect)
        self.options = options
        self.selected = selected
        self.on_change = on_change
        self.columns = columns if columns > 0 else len(options)
        self.spacing = spacing
        self.chip_w = chip_w
        self.shadow = shadow
        self.font_role = font_role
        self.text_color = text_color
        self._chip_rects: list[pygame.Rect] = []
        self._recalc()

    def _recalc(self) -> None:
        self._chip_rects.clear()
        n = len(self.options)
        if n == 0:
            return

        cols = min(self.columns, n)
        rows = (n + cols - 1) // cols
        spacing = self.spacing
        chip_w = self.chip_w if self.chip_w is not None else (self.rect.width - (cols - 1) * spacing) // cols
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
            text_col = self.text_color if self.text_color is not None else (CARD if is_sel else INK)
            draw_panel(surf, r, fill=fill_col, border=BORDER, shadow=self.shadow, shadow_color=INK)
            draw_text(surf, opt, self.font_role, text_col, r.center, anchor="center")


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


def _clipboard_get() -> str:
    try:
        if hasattr(pygame.scrap, "get_text"):
            return pygame.scrap.get_text() or ""
        if hasattr(pygame.scrap, "get"):
            data = pygame.scrap.get(pygame.SCRAP_TEXT)
            if data:
                return data.decode("utf-8", errors="replace").rstrip("\x00")
    except Exception:
        pass
    return ""


def _clipboard_put(text: str) -> None:
    try:
        if hasattr(pygame.scrap, "put_text"):
            pygame.scrap.put_text(text)
        elif hasattr(pygame.scrap, "put"):
            pygame.scrap.put(pygame.SCRAP_TEXT, text.encode("utf-8"))
    except Exception:
        pass


class TextInput(Widget):
    """Single-line text box with caret, selection, clipboard support, and validation state."""

    def __init__(
        self,
        rect: pygame.Rect | tuple[int, int, int, int],
        text: str = "",
        max_len: int = 100,
        placeholder: str = "",
        filter_func: Callable[[str], bool] | None = None,
        on_change: Callable[[str], None] | None = None,
        on_submit: Callable[[str], None] | None = None,
        fill: tuple[int, int, int] | None = None,
        shadow: int = 3,
        border_color: tuple[int, int, int] | None = None,
    ) -> None:
        super().__init__(rect)
        self.text = text
        self.max_len = max_len
        self.placeholder = placeholder
        self.filter_func = filter_func
        self.on_change = on_change
        self.on_submit = on_submit
        self.fill = fill
        self.shadow = shadow
        self.border_color = border_color

        self.caret: int = len(text)
        self.all_selected: bool = False
        self.invalid: bool = False
        self._blink_t: float = 0.0
        self._caret_visible: bool = True

    def set_text(self, text: str, notify: bool = True) -> None:
        """Programmatically update text and align caret."""
        self.text = text
        self.caret = len(text)
        self.all_selected = False
        self._caret_visible = True
        self._blink_t = 0.0
        if notify and self.on_change:
            self.on_change(self.text)

    def handle_event(self, event: pygame.event.Event) -> bool:
        if not self.visible or not self.enabled:
            return False

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                self.focused = True
                self.all_selected = False
                try:
                    if hasattr(pygame.key, "start_text_input"):
                        pygame.key.start_text_input()
                    if hasattr(pygame.key, "set_text_input_rect"):
                        pygame.key.set_text_input_rect(self.rect)
                except Exception:
                    pass
                f = font("body")
                rel_x = event.pos[0] - (self.rect.x + 8)
                best_idx = len(self.text)
                for idx in range(len(self.text) + 1):
                    w, _ = f.size(self.text[:idx])
                    if w >= rel_x:
                        prev_w = f.size(self.text[: idx - 1])[0] if idx > 0 else 0
                        best_idx = idx - 1 if (idx > 0 and abs(rel_x - prev_w) < abs(rel_x - w)) else idx
                        break
                self.caret = best_idx
                self._caret_visible = True
                self._blink_t = 0.0
                return True
            else:
                if self.focused:
                    try:
                        if hasattr(pygame.key, "stop_text_input"):
                            pygame.key.stop_text_input()
                    except Exception:
                        pass
                self.focused = False
                self.all_selected = False

        if not self.focused:
            return False

        if event.type == pygame.KEYDOWN:
            self._caret_visible = True
            self._blink_t = 0.0

            # Ctrl+A/C/V/X
            if event.mod & pygame.KMOD_CTRL:
                if event.key == pygame.K_v:
                    clip = _clipboard_get()
                    if clip:
                        if self.all_selected:
                            self.text = ""
                            self.caret = 0
                            self.all_selected = False
                        self._insert_text(clip)
                    return True
                elif event.key == pygame.K_a:
                    self.all_selected = len(self.text) > 0
                    self.caret = len(self.text)
                    return True
                elif event.key == pygame.K_c:
                    if self.text:
                        _clipboard_put(self.text)
                    return True
                elif event.key == pygame.K_x:
                    if self.text:
                        _clipboard_put(self.text)
                        self.set_text("")
                    return True

            if event.key == pygame.K_BACKSPACE:
                if self.all_selected:
                    self.set_text("")
                elif self.caret > 0:
                    self.text = self.text[: self.caret - 1] + self.text[self.caret :]
                    self.caret -= 1
                    if self.on_change:
                        self.on_change(self.text)
                return True

            if event.key == pygame.K_DELETE:
                if self.all_selected:
                    self.set_text("")
                elif self.caret < len(self.text):
                    self.text = self.text[: self.caret] + self.text[self.caret + 1 :]
                    if self.on_change:
                        self.on_change(self.text)
                return True

            if event.key == pygame.K_LEFT:
                if self.all_selected:
                    self.caret = 0
                    self.all_selected = False
                else:
                    self.caret = max(0, self.caret - 1)
                return True

            if event.key == pygame.K_RIGHT:
                if self.all_selected:
                    self.caret = len(self.text)
                    self.all_selected = False
                else:
                    self.caret = min(len(self.text), self.caret + 1)
                return True

            if event.key == pygame.K_HOME:
                self.caret = 0
                self.all_selected = False
                return True

            if event.key == pygame.K_END:
                self.caret = len(self.text)
                self.all_selected = False
                return True

            if event.key == pygame.K_RETURN:
                if self.on_submit:
                    self.on_submit(self.text)
                return True

            # Direct character input fallback for platforms/terminals where TEXTINPUT is not dispatched
            if (
                event.unicode
                and event.unicode.isprintable()
                and not (event.mod & (pygame.KMOD_CTRL | pygame.KMOD_ALT | pygame.KMOD_GUI))
            ):
                self._last_keydown_char = (time.monotonic(), event.unicode)
                self._insert_text(event.unicode)
                return True

        if event.type == pygame.TEXTINPUT:
            # Check if this character was already handled by KEYDOWN within 80ms
            if hasattr(self, "_last_keydown_char") and self._last_keydown_char:
                kd_t, kd_ch = self._last_keydown_char
                if event.text == kd_ch and (time.monotonic() - kd_t) < 0.08:
                    self._last_keydown_char = None
                    return True
            self._insert_text(event.text)
            return True

        return False

    def _insert_text(self, s: str) -> None:
        inserted_any = False
        for ch in s:
            if ch in ("\r", "\n"):
                continue
            if self.filter_func and not self.filter_func(ch):
                continue
            if self.all_selected:
                self.text = ""
                self.caret = 0
                self.all_selected = False
            if len(self.text) < self.max_len:
                self.text = self.text[: self.caret] + ch + self.text[self.caret :]
                self.caret += 1
                inserted_any = True
        if inserted_any and self.on_change:
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

        fill_col = self.fill if self.fill is not None else CARD
        if self.border_color is not None:
            border_col = DANGER if self.invalid else self.border_color
        else:
            border_col = DANGER if self.invalid else (INK if self.focused else CARD_BORDER)
        draw_panel(surf, self.rect, fill=fill_col, border=BORDER, shadow=self.shadow, shadow_color=border_col)

        inner = self.rect.inflate(-16, -8)
        clip = surf.get_clip()
        surf.set_clip(inner)

        f = font("body")
        if self.text:
            if self.all_selected:
                tw, th = f.size(self.text)
                sel_surf = pygame.Surface((tw, th), pygame.SRCALPHA)
                sel_surf.fill((*PURPLE, 90))
                surf.blit(sel_surf, (inner.x, inner.centery - th // 2))
            txt_surf = f.render(self.text, True, INK)
            surf.blit(txt_surf, (inner.x, inner.centery - txt_surf.get_height() // 2))
        elif self.placeholder:
            p_surf = f.render(self.placeholder, True, SECONDARY)
            surf.blit(p_surf, (inner.x, inner.centery - p_surf.get_height() // 2))

        if self.focused and self._caret_visible and not self.all_selected:
            pre = self.text[: self.caret]
            cx = inner.x + f.size(pre)[0]
            cy1 = inner.centery - f.get_height() // 2 + 2
            cy2 = cy1 + f.get_height() - 4
            pygame.draw.line(surf, INK, (cx, cy1), (cx, cy2), 2)

        surf.set_clip(clip)


class TextArea(Widget):
    """Multi-line text editor with word-wrap, caret cursor, selection, scrolling, and clipboard."""

    def __init__(
        self,
        rect: pygame.Rect | tuple[int, int, int, int],
        text: str = "",
        on_change: Callable[[str], None] | None = None,
    ) -> None:
        super().__init__(rect)
        self.text: str = text
        self.on_change: Callable[[str], None] | None = on_change
        self.caret: int = len(text)
        self.selection: tuple[int, int] | None = None
        self._drag_selecting: bool = False
        self._drag_start_idx: int = 0
        self.scroll_y: int = 0
        self._blink_t: float = 0.0
        self._caret_visible: bool = True

    def set_text(self, text: str, notify: bool = False) -> None:
        """Programmatically update text and reset caret/selection."""
        self.text = text
        self.caret = len(text)
        self.selection = None
        self.scroll_y = 0
        self._caret_visible = True
        self._blink_t = 0.0
        if notify and self.on_change:
            self.on_change(self.text)

    def has_selection(self) -> bool:
        return self.selection is not None and self.selection[0] < self.selection[1]

    def get_selected_text(self) -> str:
        if self.has_selection() and self.selection is not None:
            return self.text[self.selection[0] : self.selection[1]]
        return self.text

    def delete_selection(self) -> None:
        if self.has_selection() and self.selection is not None:
            s, e = self.selection
            self.text = self.text[:s] + self.text[e:]
            self.caret = s
            self.selection = None
            self._caret_visible = True
            self._blink_t = 0.0
            if self.on_change:
                self.on_change(self.text)

    def insert_text(self, s: str) -> None:
        if self.has_selection():
            self.delete_selection()
        clean_s = s.replace("\r\n", "\n").replace("\r", "\n")
        self.text = self.text[: self.caret] + clean_s + self.text[self.caret :]
        self.caret += len(clean_s)
        self.selection = None
        self._caret_visible = True
        self._blink_t = 0.0
        if self.on_change:
            self.on_change(self.text)

    def update(self, dt: float) -> None:
        if self.focused:
            self._blink_t += dt
            if self._blink_t >= 0.5:
                self._blink_t = 0.0
                self._caret_visible = not self._caret_visible
        else:
            self._caret_visible = False

    def _get_wrapped_lines(self, f: pygame.font.Font, max_w: int) -> list[tuple[str, int, int]]:
        """Returns list of (line_str, char_start_idx, char_end_idx)."""
        if not self.text:
            return [("", 0, 0)]

        lines: list[tuple[str, int, int]] = []
        paragraphs = self.text.split("\n")
        cur_idx = 0

        for para in paragraphs:
            p_start = cur_idx
            p_end = cur_idx + len(para)

            if not para:
                lines.append(("", p_start, p_end))
            else:
                words = para.split(" ")
                line_words: list[str] = []
                line_start = p_start

                for w_i, word in enumerate(words):
                    test_words = line_words + [word]
                    test_str = " ".join(test_words)
                    w_w, _ = f.size(test_str)

                    if w_w <= max_w or not line_words:
                        if w_w <= max_w:
                            line_words.append(word)
                        else:
                            sub = ""
                            sub_start = line_start
                            for ch in word:
                                if f.size(sub + ch)[0] <= max_w:
                                    sub += ch
                                else:
                                    if sub:
                                        lines.append((sub, sub_start, sub_start + len(sub)))
                                        sub_start += len(sub)
                                    sub = ch
                            if sub:
                                line_words = [sub]
                                line_start = sub_start
                    else:
                        cur_line_str = " ".join(line_words)
                        lines.append((cur_line_str, line_start, line_start + len(cur_line_str)))
                        line_words = [word]
                        line_start = line_start + len(cur_line_str) + 1

                if line_words:
                    cur_line_str = " ".join(line_words)
                    lines.append((cur_line_str, line_start, line_start + len(cur_line_str)))

            cur_idx = p_end + 1

        return lines

    def _pos_to_index(
        self,
        pos: tuple[int, int],
        wrapped_lines: list[tuple[str, int, int]],
        f: pygame.font.Font,
        inner: pygame.Rect,
    ) -> int:
        line_h = f.get_linesize()
        px, py = pos
        rel_y = py - inner.y + self.scroll_y
        line_idx = max(0, min(len(wrapped_lines) - 1, int(rel_y // line_h)))

        l_str, l_start, l_end = wrapped_lines[line_idx]
        if not l_str:
            return l_start

        rel_x = px - inner.x
        if rel_x <= 0:
            return l_start

        best_c = len(l_str)
        for c in range(1, len(l_str) + 1):
            w = f.size(l_str[:c])[0]
            if w >= rel_x:
                prev_w = f.size(l_str[: c - 1])[0]
                if abs(rel_x - prev_w) < abs(rel_x - w):
                    best_c = c - 1
                else:
                    best_c = c
                break
        return min(len(self.text), l_start + best_c)

    def handle_event(self, event: pygame.event.Event) -> bool:
        if not self.visible or not self.enabled:
            return False

        f = font("mono")
        inner = self.rect.inflate(-16, -16)
        line_h = f.get_linesize()
        wrapped_lines = self._get_wrapped_lines(f, inner.width)

        if event.type == pygame.MOUSEBUTTONDOWN:
            if self.rect.collidepoint(event.pos):
                self.focused = True
                try:
                    if hasattr(pygame.key, "start_text_input"):
                        pygame.key.start_text_input()
                    if hasattr(pygame.key, "set_text_input_rect"):
                        pygame.key.set_text_input_rect(self.rect)
                except Exception:
                    pass
                if event.button == 1:
                    idx = self._pos_to_index(event.pos, wrapped_lines, f, inner)
                    self.caret = idx
                    self.selection = None
                    self._drag_selecting = True
                    self._drag_start_idx = idx
                    self._caret_visible = True
                    self._blink_t = 0.0
                    return True
                elif event.button == 4:
                    self.scroll_y = max(0, self.scroll_y - line_h * 2)
                    return True
                elif event.button == 5:
                    max_scroll = max(0, len(wrapped_lines) * line_h - inner.height)
                    self.scroll_y = min(max_scroll, self.scroll_y + line_h * 2)
                    return True
                return True
            else:
                if self.focused:
                    try:
                        if hasattr(pygame.key, "stop_text_input"):
                            pygame.key.stop_text_input()
                    except Exception:
                        pass
                self.focused = False
                self.selection = None
                self._drag_selecting = False

        if event.type == pygame.MOUSEBUTTONUP:
            if event.button == 1:
                self._drag_selecting = False

        if event.type == pygame.MOUSEMOTION and self._drag_selecting:
            curr_idx = self._pos_to_index(event.pos, wrapped_lines, f, inner)
            self.caret = curr_idx
            if curr_idx != self._drag_start_idx:
                self.selection = (min(self._drag_start_idx, curr_idx), max(self._drag_start_idx, curr_idx))
            else:
                self.selection = None
            return True

        if not self.focused:
            return False

        if event.type == pygame.KEYDOWN:
            if event.mod & pygame.KMOD_CTRL:
                if event.key == pygame.K_a:
                    self.selection = (0, len(self.text))
                    self.caret = len(self.text)
                    return True
                elif event.key == pygame.K_c:
                    txt = self.get_selected_text()
                    if txt:
                        _clipboard_put(txt)
                    return True
                elif event.key == pygame.K_x:
                    txt = self.get_selected_text()
                    if txt:
                        _clipboard_put(txt)
                    if self.has_selection():
                        self.delete_selection()
                    else:
                        self.set_text("", notify=True)
                    return True
                elif event.key == pygame.K_v:
                    clip = _clipboard_get()
                    if clip:
                        self.insert_text(clip)
                    return True

            if event.key == pygame.K_BACKSPACE:
                if self.has_selection():
                    self.delete_selection()
                elif self.caret > 0:
                    self.text = self.text[: self.caret - 1] + self.text[self.caret :]
                    self.caret -= 1
                    self._caret_visible = True
                    self._blink_t = 0.0
                    if self.on_change:
                        self.on_change(self.text)
                return True

            if event.key == pygame.K_DELETE:
                if self.has_selection():
                    self.delete_selection()
                elif self.caret < len(self.text):
                    self.text = self.text[: self.caret] + self.text[self.caret + 1 :]
                    self._caret_visible = True
                    self._blink_t = 0.0
                    if self.on_change:
                        self.on_change(self.text)
                return True

            if event.key == pygame.K_LEFT:
                if self.has_selection() and self.selection is not None:
                    self.caret = self.selection[0]
                    self.selection = None
                else:
                    self.caret = max(0, self.caret - 1)
                self._caret_visible = True
                self._blink_t = 0.0
                return True

            if event.key == pygame.K_RIGHT:
                if self.has_selection() and self.selection is not None:
                    self.caret = self.selection[1]
                    self.selection = None
                else:
                    self.caret = min(len(self.text), self.caret + 1)
                self._caret_visible = True
                self._blink_t = 0.0
                return True

            if event.key == pygame.K_HOME:
                self.caret = 0
                self.selection = None
                self._caret_visible = True
                self._blink_t = 0.0
                return True

            if event.key == pygame.K_END:
                self.caret = len(self.text)
                self.selection = None
                self._caret_visible = True
                self._blink_t = 0.0
                return True

            if event.key == pygame.K_RETURN:
                self.insert_text("\n")
                return True

            # Direct character input fallback for platforms/terminals where TEXTINPUT is not dispatched
            if (
                event.unicode
                and event.unicode.isprintable()
                and not (event.mod & (pygame.KMOD_CTRL | pygame.KMOD_ALT | pygame.KMOD_GUI))
            ):
                self._last_keydown_char = (time.monotonic(), event.unicode)
                self.insert_text(event.unicode)
                return True

        if event.type == pygame.TEXTINPUT:
            # Check if this character was already handled by KEYDOWN within 80ms
            if hasattr(self, "_last_keydown_char") and self._last_keydown_char:
                kd_t, kd_ch = self._last_keydown_char
                if event.text == kd_ch and (time.monotonic() - kd_t) < 0.08:
                    self._last_keydown_char = None
                    return True
            self.insert_text(event.text)
            return True

        return False

    def draw(self, surf: pygame.Surface) -> None:
        if not self.visible:
            return

        border_col = INK if self.focused else CARD_BORDER
        draw_panel(surf, self.rect, fill=CARD, border=BORDER, shadow=4, shadow_color=border_col)
        inner = self.rect.inflate(-16, -16)
        clip = surf.get_clip()
        surf.set_clip(inner)

        f = font("mono")
        line_h = f.get_linesize()
        wrapped_lines = self._get_wrapped_lines(f, inner.width)

        caret_pos: tuple[int, int] | None = None
        for idx, (l_str, l_start, l_end) in enumerate(wrapped_lines):
            if (l_start <= self.caret < l_end) or (idx == len(wrapped_lines) - 1 and self.caret >= l_start):
                rel_char = min(len(l_str), max(0, self.caret - l_start))
                cx = inner.x + f.size(l_str[:rel_char])[0]
                cy = inner.y - self.scroll_y + idx * line_h
                caret_pos = (cx, cy)
                break

        if self.focused and caret_pos:
            cx, cy = caret_pos
            if cy < inner.y:
                self.scroll_y = max(0, self.scroll_y - (inner.y - cy))
            elif cy + line_h > inner.bottom:
                self.scroll_y += ((cy + line_h) - inner.bottom)

        y = inner.y - self.scroll_y
        for idx, (l_str, l_start, l_end) in enumerate(wrapped_lines):
            line_y = y + idx * line_h
            if line_y + line_h >= inner.y and line_y <= inner.bottom:
                if self.has_selection() and self.selection is not None:
                    sel_s, sel_e = self.selection
                    o_s = max(l_start, sel_s)
                    o_e = min(l_end, sel_e)
                    if o_s < o_e:
                        sx1 = inner.x + f.size(l_str[: o_s - l_start])[0]
                        sx2 = inner.x + f.size(l_str[: o_e - l_start])[0]
                        sel_w = max(4, sx2 - sx1)
                        sel_surf = pygame.Surface((sel_w, line_h), pygame.SRCALPHA)
                        sel_surf.fill((*PURPLE, 90))
                        surf.blit(sel_surf, (sx1, line_y))

                if l_str:
                    txt = f.render(l_str, True, INK)
                    surf.blit(txt, (inner.x, line_y))

        if self.focused and self._caret_visible and not self.has_selection():
            for idx, (l_str, l_start, l_end) in enumerate(wrapped_lines):
                if (l_start <= self.caret < l_end) or (idx == len(wrapped_lines) - 1 and self.caret >= l_start):
                    rel_char = min(len(l_str), max(0, self.caret - l_start))
                    cx = inner.x + f.size(l_str[:rel_char])[0]
                    cy = inner.y - self.scroll_y + idx * line_h
                    if inner.y <= cy <= inner.bottom - 4:
                        pygame.draw.rect(surf, INK, (cx, cy, 2, line_h))
                    break

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
        if self.rect.width > 0 and self.anchor in ("topleft", "midtop"):
            draw_wrapped_text(
                surf,
                self.text,
                self.role,
                self.color,
                getattr(self.rect, self.anchor),
                max_w=self.rect.width,
                anchor=self.anchor,
            )
        else:
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
    """Smooth scrollable list with mouse-wheel support and draggable scrollbar."""

    def __init__(
        self,
        rect: pygame.Rect | tuple[int, int, int, int],
        item_height: int,
        draw_item: Callable[[pygame.Surface, Any, pygame.Rect, int, bool], None],
        items: list[Any],
        borderless: bool = False,
    ) -> None:
        super().__init__(rect)
        self.item_height = item_height
        self.draw_item = draw_item
        self.items = list(items)
        self.borderless = borderless
        self.scroll_y = 0
        self._hovered_idx: int | None = None
        self._mouse_over: bool = False
        self._dragging_sb: bool = False
        self._drag_offset_y: int = 0
        self._sb_hovered: bool = False

    def _inner_rect(self) -> pygame.Rect:
        return self.rect if self.borderless else self.rect.inflate(-BORDER * 2, -BORDER * 2)

    def _max_scroll(self) -> int:
        inner_h = max(0, self._inner_rect().height)
        return max(0, len(self.items) * self.item_height - inner_h)

    def _scrollbar_rects(self) -> tuple[pygame.Rect, pygame.Rect] | None:
        """Return (track_rect, thumb_rect) when content overflows, else None."""
        inner = self._inner_rect()
        total_h = len(self.items) * self.item_height
        if total_h <= inner.height or inner.height <= 0:
            return None
        bar_w = 6 if self.borderless else 8
        pad = 4
        track_h = max(1, inner.height - pad * 2)
        track = pygame.Rect(inner.right - bar_w - 4, inner.y + pad, bar_w, track_h)
        bar_h = max(28, int(track_h * (inner.height / total_h)))
        max_scroll = max(1, total_h - inner.height)
        ratio = max(0.0, min(1.0, self.scroll_y / max_scroll))
        bar_y = track.y + int((track_h - bar_h) * ratio)
        thumb = pygame.Rect(track.x, bar_y, bar_w, bar_h)
        return track, thumb

    def set_items(self, items: list[Any]) -> None:
        self.items = list(items)
        self.scroll_y = min(self.scroll_y, self._max_scroll())

    def scroll_to_bottom(self) -> None:
        self.scroll_y = self._max_scroll()

    def _scroll_from_thumb_y(self, thumb_top: int, track: pygame.Rect, thumb_h: int) -> None:
        max_scroll = self._max_scroll()
        usable = max(1, track.height - thumb_h)
        ratio = max(0.0, min(1.0, (thumb_top - track.y) / usable))
        self.scroll_y = int(round(ratio * max_scroll))

    def handle_event(self, event: pygame.event.Event) -> bool:
        if not self.visible:
            return False

        inner = self._inner_rect()
        sb = self._scrollbar_rects()

        if event.type == pygame.MOUSEMOTION:
            if self._dragging_sb and sb is not None:
                track, thumb = sb
                self._scroll_from_thumb_y(event.pos[1] - self._drag_offset_y, track, thumb.height)
                return True

            self._mouse_over = inner.collidepoint(event.pos)
            if sb is not None:
                hit_track = sb[0].inflate(10, 4)
                self._sb_hovered = hit_track.collidepoint(event.pos)
            else:
                self._sb_hovered = False

            if self._mouse_over and not self._sb_hovered:
                rel_y = event.pos[1] - inner.y + self.scroll_y
                idx = rel_y // self.item_height
                self._hovered_idx = idx if 0 <= idx < len(self.items) else None
            else:
                self._hovered_idx = None

        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self._dragging_sb:
                self._dragging_sb = False
                return True

        if event.type == pygame.MOUSEWHEEL:
            ev_pos = getattr(event, "pos", None)
            over = inner.collidepoint(ev_pos) if ev_pos is not None else self._mouse_over
            if over and self._max_scroll() > 0:
                self.scroll_y -= int(event.y * self.item_height)
                self.scroll_y = max(0, min(self.scroll_y, self._max_scroll()))
                return True

        if event.type == pygame.MOUSEBUTTONDOWN and inner.collidepoint(event.pos):
            self._mouse_over = True
            if event.button == 4:
                if self._max_scroll() > 0:
                    self.scroll_y = max(0, self.scroll_y - self.item_height)
                    return True
            if event.button == 5:
                if self._max_scroll() > 0:
                    self.scroll_y = min(self._max_scroll(), self.scroll_y + self.item_height)
                    return True
            if event.button == 1 and sb is not None:
                track, thumb = sb
                hit_track = track.inflate(10, 4)
                if hit_track.collidepoint(event.pos):
                    self._dragging_sb = True
                    if thumb.inflate(10, 4).collidepoint(event.pos):
                        self._drag_offset_y = event.pos[1] - thumb.y
                    else:
                        self._drag_offset_y = thumb.height // 2
                        self._scroll_from_thumb_y(event.pos[1] - self._drag_offset_y, track, thumb.height)
                    return True

        return False

    def draw(self, surf: pygame.Surface) -> None:
        if not self.visible:
            return

        if not self.borderless:
            draw_panel(surf, self.rect, fill=CARD, border=BORDER, shadow=0)

        inner = self._inner_rect()
        clip = surf.get_clip()
        surf.set_clip(inner)

        sb = self._scrollbar_rects()
        row_w = inner.width - (16 if sb is not None else 8)

        for idx, item in enumerate(self.items):
            y = inner.y + idx * self.item_height - self.scroll_y
            if y + self.item_height < inner.y or y > inner.bottom:
                continue

            item_rect = pygame.Rect(inner.x, y, row_w, self.item_height)
            self.draw_item(surf, item, item_rect, idx, idx == self._hovered_idx)

        # Scrollbar track & thumb
        if sb is not None:
            track, thumb = sb
            pygame.draw.rect(surf, TINT, track, border_radius=3)
            thumb_col = ACCENT if (self._dragging_sb or self._sb_hovered) else (CARD_BORDER if self.borderless else INK)
            pygame.draw.rect(surf, thumb_col, thumb, border_radius=3)

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
