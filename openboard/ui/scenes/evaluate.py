"""
openboard.ui.scenes.evaluate
~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Position evaluation scene with FEN/SAN/LAN inputs and live analysis.
"""

from __future__ import annotations

import logging
import time
from typing import Any

import chess
import pygame

from openboard import config
from openboard.core import notation
from openboard.core.notation import NotationError, detect_input_type, parse_position, san_line
from openboard.core.results import describe_eval
from openboard.engines.types import SearchResult
from openboard.ui import theme
from openboard.ui.board_view import BoardView
from openboard.ui.scenes.base import Scene
from openboard.ui.theme import ACCENT, BORDER, CARD, CARD_BORDER, DANGER, INK, PURPLE, SHADOW, TINT, draw_panel, draw_text
from openboard.ui.widgets import Button, Chips, TextArea, TextInput

log = logging.getLogger("openboard.ui.scenes.evaluate")


class EvaluateScene(Scene):
    """Position evaluation workbench supporting multiple notations and real-time engine analysis."""

    name = "evaluate"

    def on_enter(
        self,
        moves: list[str] | None = None,
        start_fen: str | None = None,
        **_kw: Any,
    ) -> None:
        self.menu_btn = Button((config.DESIGN_W - 180, 48, 120, 52), "MENU", lambda: self.ctx.scenes.go("main_menu"), style="secondary")

        # Board on the left (read-only)
        board_orig = (120, 150)
        self.board_view = BoardView(board_orig, config.EVAL_BOARD_SQ, self.ctx.assets)
        self.board_view.set_interactive(None)

        # Right panel layout
        rp_x = 760
        rp_w = 760
        rp_y = 150
        rp_h = 680
        self.panel_rect = pygame.Rect(rp_x, rp_y, rp_w, rp_h)

        # Notation selection chips
        self._input_chip_manually_selected = False
        self.format_chips = Chips(
            (rp_x + 36, rp_y + 36, 320, 44),
            options=["FEN", "SAN", "LAN"],
            selected=0,
            on_change=self._on_format_chip_change,
        )

        # Text input area
        initial_text = chess.STARTING_FEN
        if moves:
            initial_text = " ".join(moves)
            if start_fen and start_fen != chess.STARTING_FEN:
                initial_text = f"FEN: {start_fen}\n" + initial_text
            self.format_chips.selected = 1  # SAN

        self.text_area = TextArea(
            (rp_x + 36, rp_y + 96, rp_w - 72, 110),
            text=initial_text,
            on_change=self._on_text_changed,
        )

        # Search limit mode: DEPTH (0), AUTO (1), TIME (2)
        self.limit_chips = Chips(
            (rp_x + 36, rp_y + 246, 320, 44),
            options=["DEPTH", "AUTO", "TIME"],
            selected=0,
            on_change=self._on_limit_chip_change,
        )

        # Numeric limit input
        self.limit_input = TextInput(
            (rp_x + 372, rp_y + 246, 120, 44),
            text=str(config.EVAL_DEFAULT_DEPTH),
            max_len=5,
            filter_func=lambda ch: ch.isdigit() or ch == ".",
            on_change=self._validate_limit_input,
        )

        # Evaluate / Cancel button
        self.eval_btn = Button(
            (rp_x + rp_w - 36 - 180, rp_y + 246, 180, 44),
            "EVALUATE",
            self._on_eval_btn_click,
            style="primary",
        )

        # Parse debounce
        self._parse_dirty: bool = True
        self._last_type_time: float = time.monotonic()
        self._parse_error: str | None = None
        self._parsed_board: chess.Board = chess.Board()

        # Evaluation result state
        self._eval_running: bool = False
        self._eval_req_id: int | None = None
        self._eval_result: SearchResult | None = None
        self._spinner_angle: float = 0.0

        # Perform initial parse
        self._parse_now()

    def _on_format_chip_change(self, idx: int) -> None:
        self._input_chip_manually_selected = True
        self._parse_dirty = True

    def _on_limit_chip_change(self, idx: int) -> None:
        if idx == 0:  # DEPTH
            self.limit_input.text = str(config.EVAL_DEFAULT_DEPTH)
        elif idx == 2:  # TIME
            self.limit_input.text = "2.0"
        self._validate_limit_input(self.limit_input.text)

    def _validate_limit_input(self, text: str) -> None:
        idx = self.limit_chips.selected
        try:
            val = float(text)
            if idx == 0:  # Depth
                d_min, d_max = config.EVAL_DEPTH_RANGE
                self.limit_input.invalid = not (d_min <= int(val) <= d_max)
            elif idx == 2:  # Time
                t_min, t_max = config.EVAL_TIME_RANGE
                self.limit_input.invalid = not (t_min <= val <= t_max)
            else:
                self.limit_input.invalid = False
        except ValueError:
            self.limit_input.invalid = True

    def _on_text_changed(self, text: str) -> None:
        self._parse_dirty = True
        self._last_type_time = time.monotonic()

        # Auto-detect input type if not manually locked
        if not self._input_chip_manually_selected:
            detected = detect_input_type(text)
            if detected == "fen":
                self.format_chips.selected = 0
            elif detected == "san":
                self.format_chips.selected = 1
            elif detected == "lan":
                self.format_chips.selected = 2

    def _parse_now(self) -> None:
        self._parse_dirty = False
        text = self.text_area.text.strip()
        if not text:
            self._parse_error = "Empty input"
            self.eval_btn.enabled = False
            return

        fmt = ["fen", "san", "lan"][self.format_chips.selected]
        try:
            parsed = parse_position(text, kind=fmt)
            self._parsed_board = parsed.board
            self.board_view.set_board(self._parsed_board)
            if parsed.uci_moves:
                last_m = chess.Move.from_uci(parsed.uci_moves[-1])
                self.board_view.set_marks(last_m, self._parsed_board.king(self._parsed_board.turn) if self._parsed_board.is_check() else None)
            else:
                self.board_view.set_marks(None, None)
            self._parse_error = None
            self.eval_btn.enabled = True
        except NotationError as err:
            self._parse_error = str(err)
            self.eval_btn.enabled = False
        except Exception as exc:
            self._parse_error = f"Invalid position: {exc}"
            self.eval_btn.enabled = False

    def _on_eval_btn_click(self) -> None:
        if self._eval_running:
            # Cancel
            self.ctx.engines.cancel()
            self._eval_running = False
            self.eval_btn.label = "EVALUATE"
            return

        if self._parse_error or not self.eval_btn.enabled:
            return

        # Prepare limit
        depth_val: int | None = None
        time_val: float | None = None
        auto_val: bool = False

        sel_limit = self.limit_chips.selected
        if sel_limit == 0:  # DEPTH
            try:
                depth_val = int(self.limit_input.text)
            except ValueError:
                depth_val = config.EVAL_DEFAULT_DEPTH
        elif sel_limit == 1:  # AUTO
            auto_val = True
        else:  # TIME
            try:
                time_val = float(self.limit_input.text)
            except ValueError:
                time_val = 2.0

        req_kwargs = {
            "fen": self._parsed_board.fen(),
            "purpose": "evaluate",
            "depth": depth_val,
            "time_s": time_val,
            "auto": auto_val,
        }

        self._eval_running = True
        self.eval_btn.label = "CANCEL"
        self._eval_req_id = self.ctx.engines.submit(req_kwargs, self._on_eval_complete)

    def _on_eval_complete(self, result: SearchResult) -> None:
        if result.request_id != self._eval_req_id:
            return

        self._eval_running = False
        self.eval_btn.label = "EVALUATE"
        self._eval_result = result

    def handle_event(self, event: pygame.event.Event) -> None:
        if self.menu_btn.handle_event(event):
            return
        if self.format_chips.handle_event(event):
            return
        if self.text_area.handle_event(event):
            return
        if self.limit_chips.handle_event(event):
            return
        if self.limit_chips.selected != 1:  # Show limit input only when not AUTO
            if self.limit_input.handle_event(event):
                return
        self.eval_btn.handle_event(event)

    def update(self, dt: float) -> None:
        self.menu_btn.update(dt)
        self.eval_btn.update(dt)
        if self.limit_chips.selected != 1:
            self.limit_input.update(dt)

        if self._parse_dirty and (time.monotonic() - self._last_type_time >= 0.3):
            self._parse_now()

        if self._eval_running:
            self._spinner_angle = (self._spinner_angle + dt * 360) % 360

    def draw(self, surf: pygame.Surface) -> None:
        surf.fill(theme.BG)

        draw_text(surf, "POSITION EVALUATION", "heading", INK, (120, 60), anchor="midleft")
        self.menu_btn.draw(surf)

        # Chess board
        self.board_view.draw(surf)

        # Right panel container
        draw_panel(surf, self.panel_rect, fill=CARD, border=BORDER, shadow=SHADOW, shadow_color=INK)

        # Format chips & Text area
        draw_text(surf, "INPUT FORMAT", "label", INK, (self.panel_rect.x + 36, self.panel_rect.y + 16), anchor="topleft")
        self.format_chips.draw(surf)
        self.text_area.draw(surf)

        # Parse error feedback
        if self._parse_error:
            draw_text(surf, self._parse_error, "small", DANGER, (self.panel_rect.x + 36, self.panel_rect.y + 214), anchor="topleft")

        # Search limit controls
        draw_text(surf, "SEARCH LIMIT", "label", INK, (self.panel_rect.x + 36, self.panel_rect.y + 226), anchor="topleft")
        self.limit_chips.draw(surf)

        # Number input suffix
        if self.limit_chips.selected != 1:
            self.limit_input.draw(surf)
            suffix = "plies" if self.limit_chips.selected == 0 else "sec"
            draw_text(surf, suffix, "small", TINT, (self.limit_input.rect.right + 8, self.limit_input.rect.centery), anchor="midleft")

        self.eval_btn.draw(surf)

        # Result display block
        res_rect = pygame.Rect(self.panel_rect.x + 36, self.panel_rect.y + 316, self.panel_rect.width - 72, 330)
        draw_panel(surf, res_rect, fill=theme.BG, border=BORDER, shadow=2)

        if self._eval_running:
            draw_text(surf, "ANALYZING POSITION...", "heading", ACCENT, res_rect.center, anchor="center")
        elif self._eval_result:
            r = self._eval_result
            score_str, word_str = describe_eval(r.score_cp, r.mate_in)

            # Big score display
            draw_text(surf, score_str, "clock", INK, (res_rect.x + 36, res_rect.y + 30), anchor="topleft")
            draw_text(surf, word_str, "heading", PURPLE, (res_rect.x + 36, res_rect.y + 110), anchor="topleft")

            # Engine info & reason caption
            eng_label = "Stockfish" if r.backend == "stockfish" else "OpenBoard Engine"
            caption = f"{eng_label}   ·   depth {r.depth}   ·   {r.seconds:.2f} s   ·   {r.nodes} nodes"
            draw_text(surf, caption, "body", INK, (res_rect.x + 36, res_rect.y + 160), anchor="topleft")
            draw_text(surf, f"Router: {r.reason}", "small", TINT, (res_rect.x + 36, res_rect.y + 195), anchor="topleft")

            # Principal variation move line
            if r.pv_uci:
                line_str = san_line(self._parsed_board.fen(), list(r.pv_uci), max_moves=6)
                draw_text(surf, f"Line:  {line_str}", "heading", ACCENT, (res_rect.x + 36, res_rect.y + 240), anchor="topleft")
        else:
            draw_text(surf, "Ready for analysis.", "body", TINT, res_rect.center, anchor="center")
