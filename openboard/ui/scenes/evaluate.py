"""
openboard.ui.scenes.evaluate
~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Position evaluation scene with FEN input, interactive board moves, and live analysis.
"""

from __future__ import annotations

import io
import logging
import time
from typing import Any

import chess
import chess.pgn
import pygame

from openboard import config
from openboard.core.notation import NotationError, parse_position, san_line
from openboard.core.results import describe_eval
from openboard.engines.types import SearchResult
from openboard.ui import theme
from openboard.ui.board_view import BoardView
from openboard.ui.scenes.base import Scene
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
)
from openboard.ui.widgets import Button, Chips, TextArea, TextInput

log = logging.getLogger("openboard.ui.scenes.evaluate")


def _pgn_to_position(pgn_text: str) -> tuple[str, chess.Move | None]:
    """Replay a PGN string and return ``(final_fen, last_move)``."""
    if not pgn_text or not pgn_text.strip():
        return chess.STARTING_FEN, None
    try:
        game = chess.pgn.read_game(io.StringIO(pgn_text))
        if game is None:
            return chess.STARTING_FEN, None
        board = game.board()
        last_move: chess.Move | None = None
        for move in game.mainline_moves():
            board.push(move)
            last_move = move
        return board.fen(), last_move
    except Exception as exc:
        log.warning("Could not parse PGN for evaluation: %s", exc)
        return chess.STARTING_FEN, None


class EvaluateScene(Scene):
    """Position evaluation workbench supporting FEN input, board moves, and real-time engine analysis."""

    name = "evaluate"

    def on_enter(
        self,
        fen: str | None = None,
        pgn: str | None = None,
        moves: list[str] | None = None,
        start_fen: str | None = None,
        last_move: chess.Move | None = None,
        return_to: str = "main_menu",
        **_kw: Any,
    ) -> None:
        self._return_to = return_to
        back_label = "BACK" if return_to != "main_menu" else "MENU"
        self.menu_btn = Button((1350, 48, 160, 52), back_label, lambda: self.ctx.scenes.go(self._return_to), style="secondary")

        # Board on the left (interactive for moves, aligned with standard board size)
        self.board_view = BoardView(config.BOARD_ORIGIN, config.BOARD_SQ, self.ctx.assets)
        self.board_view.set_orientation(chess.WHITE)
        self.board_view.set_interactive("both")

        # Right panel layout
        rp_x = 930
        rp_w = 580
        rp_y = 136
        rp_h = 704
        self.panel_rect = pygame.Rect(rp_x, rp_y, rp_w, rp_h)
        inner_w = rp_w - 72

        # Resolve initial FEN & optional last move from fen / pgn / moves
        initial_fen = chess.STARTING_FEN
        initial_last_move: chess.Move | None = last_move

        if fen and fen.strip():
            initial_fen = fen.strip()
        elif pgn and pgn.strip():
            initial_fen, initial_last_move = _pgn_to_position(pgn)
        elif moves:
            joined = " ".join(moves).strip()
            if joined.startswith("["):
                initial_fen, initial_last_move = _pgn_to_position(joined)
            else:
                try:
                    raw = f"FEN: {start_fen}\n{joined}" if (start_fen and start_fen != chess.STARTING_FEN) else joined
                    parsed = parse_position(raw, kind="san")
                    initial_fen = parsed.board.fen()
                    if parsed.uci_moves:
                        initial_last_move = chess.Move.from_uci(parsed.uci_moves[-1])
                except Exception as exc:
                    log.warning("Could not parse initial moves for evaluation: %s", exc)
                    initial_fen = start_fen or chess.STARTING_FEN

        self.text_area = TextArea(
            (rp_x + 36, rp_y + 68, inner_w, 114),
            text=initial_fen,
            on_change=self._on_text_changed,
        )

        # Search limit mode: DEPTH (0), AUTO (1), TIME (2)
        self.limit_chips = Chips(
            (rp_x + 36, rp_y + 204, 232, 40),
            options=["DEPTH", "AUTO", "TIME"],
            selected=0,
            on_change=self._on_limit_chip_change,
        )

        # Numeric limit input
        self.limit_input = TextInput(
            (rp_x + 278, rp_y + 204, 64, 40),
            text=str(config.EVAL_DEFAULT_DEPTH),
            max_len=5,
            filter_func=self._limit_char_filter,
            on_change=self._validate_limit_input,
            on_submit=lambda _: self._on_eval_btn_click(),
        )

        # Evaluate / Cancel button
        self.eval_btn = Button(
            (rp_x + 398, rp_y + 204, 146, 40),
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

        # Perform initial parse & highlight last move if coming from a match
        self._parse_now()
        if initial_last_move is not None and self._parse_error is None:
            chk_sq = self._parsed_board.king(self._parsed_board.turn) if self._parsed_board.is_check() else None
            self.board_view.set_marks(initial_last_move, chk_sq)

    def _limit_char_filter(self, ch: str) -> bool:
        if self.limit_chips.selected == 0:  # DEPTH: integers only
            return ch.isdigit()
        if self.limit_chips.selected == 2:  # TIME: floats with at most one dot
            if ch.isdigit():
                return True
            if ch == ".":
                return "." not in self.limit_input.text or self.limit_input.all_selected
        return False

    def _update_eval_btn_state(self) -> None:
        if self._eval_running:
            self.eval_btn.enabled = True
            return
        valid_pos = self._parse_error is None
        valid_limit = (self.limit_chips.selected == 1) or (not self.limit_input.invalid)
        self.eval_btn.enabled = valid_pos and valid_limit

    def _on_limit_chip_change(self, idx: int) -> None:
        if idx == 0:  # DEPTH
            self.limit_input.set_text(str(config.EVAL_DEFAULT_DEPTH), notify=False)
        elif idx == 1:  # AUTO
            self.limit_input.focused = False
            self.limit_input.all_selected = False
        elif idx == 2:  # TIME
            self.limit_input.set_text("2.0", notify=False)
        self._validate_limit_input(self.limit_input.text)

    def _validate_limit_input(self, text: str) -> None:
        idx = self.limit_chips.selected
        if idx == 1:  # AUTO
            self.limit_input.invalid = False
            self._update_eval_btn_state()
            return

        clean = text.strip()
        if not clean:
            self.limit_input.invalid = True
            self._update_eval_btn_state()
            return

        try:
            if idx == 0:  # Depth (integer)
                val = int(clean)
                d_min, d_max = config.EVAL_DEPTH_RANGE
                self.limit_input.invalid = not (d_min <= val <= d_max)
            elif idx == 2:  # Time (float)
                val_f = float(clean)
                t_min, t_max = config.EVAL_TIME_RANGE
                self.limit_input.invalid = not (t_min <= val_f <= t_max)
        except ValueError:
            self.limit_input.invalid = True
        self._update_eval_btn_state()

    def _on_text_changed(self, text: str) -> None:
        self._parse_dirty = True
        self._last_type_time = time.monotonic()

        # Invalidate any running or previous evaluation result
        if self._eval_running:
            self.ctx.engines.cancel()
            self._eval_running = False
            self.eval_btn.label = "EVALUATE"
        self._eval_result = None

    def _parse_now(self) -> None:
        self._parse_dirty = False
        text = self.text_area.text.strip()
        if not text:
            self._parse_error = "Empty input"
            self._update_eval_btn_state()
            self._eval_result = None
            return

        # Strip optional leading "FEN:" label if pasted
        clean_fen = text[4:].strip() if text.upper().startswith("FEN:") else text

        try:
            parsed = parse_position(clean_fen, kind="fen")
            self._parsed_board = parsed.board
            self.board_view.set_board(self._parsed_board)
            chk_sq = self._parsed_board.king(self._parsed_board.turn) if self._parsed_board.is_check() else None
            self.board_view.set_marks(None, chk_sq)
            self._parse_error = None
            self._update_eval_btn_state()
        except NotationError as err:
            self._parse_error = str(err)
            self._update_eval_btn_state()
            self._eval_result = None
        except Exception as exc:
            self._parse_error = f"Invalid FEN: {exc}"
            self._update_eval_btn_state()
            self._eval_result = None

    def _on_eval_btn_click(self) -> None:
        if self._eval_running:
            # Cancel
            self.ctx.engines.cancel()
            self._eval_running = False
            self.eval_btn.label = "EVALUATE"
            return

        if self._parse_error or not self.eval_btn.enabled:
            return

        sel_limit = self.limit_chips.selected
        if sel_limit != 1 and self.limit_input.invalid:
            return

        # Prepare limit
        depth_val: int | None = None
        time_val: float | None = None
        auto_val: bool = False

        if sel_limit == 0:  # DEPTH
            try:
                raw_d = int(self.limit_input.text.strip())
                depth_val = max(config.EVAL_DEPTH_RANGE[0], min(config.EVAL_DEPTH_RANGE[1], raw_d))
            except ValueError:
                depth_val = config.EVAL_DEFAULT_DEPTH
        elif sel_limit == 1:  # AUTO
            auto_val = True
        else:  # TIME
            try:
                raw_t = float(self.limit_input.text.strip())
                time_val = max(config.EVAL_TIME_RANGE[0], min(config.EVAL_TIME_RANGE[1], raw_t))
            except ValueError:
                time_val = 2.0

        fen_to_eval = self._parsed_board.fen()
        req_kwargs = {
            "fen": fen_to_eval,
            "purpose": "evaluate",
            "depth": depth_val,
            "time_s": time_val,
            "auto": auto_val,
        }

        self._eval_running = True
        self.eval_btn.label = "CANCEL"
        self._eval_fen = fen_to_eval
        self._eval_req_id = self.ctx.engines.submit(req_kwargs, self._on_eval_complete)

    def _on_eval_complete(self, result: SearchResult) -> None:
        if result.request_id != self._eval_req_id:
            return

        self._eval_running = False
        self.eval_btn.label = "EVALUATE"
        self._eval_result = result

    def _needs_promotion(self, from_sq: int, to_sq: int) -> bool:
        p = self._parsed_board.piece_at(from_sq)
        if p is None or p.piece_type != chess.PAWN:
            return False
        target_rank = chess.square_rank(to_sq)
        if (p.color == chess.WHITE and target_rank == 7) or (p.color == chess.BLACK and target_rank == 0):
            return any(
                m.from_square == from_sq and m.to_square == to_sq and m.promotion is not None
                for m in self._parsed_board.legal_moves
            )
        return False

    def _on_board_move_intent(self, from_sq: int, to_sq: int) -> None:
        if self._needs_promotion(from_sq, to_sq):
            self.board_view.ask_promotion(
                self._parsed_board.turn,
                lambda promo: self._execute_board_move(from_sq, to_sq, promo),
            )
        else:
            self._execute_board_move(from_sq, to_sq, None)

    def _execute_board_move(self, from_sq: int, to_sq: int, promo: int | None) -> None:
        move = chess.Move(from_sq, to_sq, promotion=promo)
        if move not in self._parsed_board.legal_moves:
            return

        # SFX
        if self._parsed_board.is_castling(move):
            self.ctx.sfx("castle")
        elif self._parsed_board.is_capture(move):
            self.ctx.sfx("capture")
        else:
            self.ctx.sfx("move")

        self._parsed_board.push(move)

        if self._parsed_board.is_check():
            self.ctx.sfx("check")

        # Update board view
        self.board_view.set_board(self._parsed_board)
        chk_sq = self._parsed_board.king(self._parsed_board.turn) if self._parsed_board.is_check() else None
        self.board_view.set_marks(move, chk_sq)
        self.board_view.animate_move(move, ms=150)

        # Automatically build the new FEN string and populate input field
        new_fen = self._parsed_board.fen()
        self.text_area.set_text(new_fen, notify=False)
        self._parse_dirty = False
        self._parse_error = None
        self._update_eval_btn_state()

        # Reset evaluation state if running or completed
        if self._eval_running:
            self.ctx.engines.cancel()
            self._eval_running = False
            self.eval_btn.label = "EVALUATE"
        self._eval_result = None

    def _step_limit_value(self, direction: int) -> None:
        idx = self.limit_chips.selected
        if idx == 0:  # DEPTH
            d_min, d_max = config.EVAL_DEPTH_RANGE
            try:
                val = int(self.limit_input.text.strip())
            except ValueError:
                val = config.EVAL_DEFAULT_DEPTH
            new_val = max(d_min, min(d_max, val + direction))
            self.limit_input.set_text(str(new_val))
        elif idx == 2:  # TIME
            t_min, t_max = config.EVAL_TIME_RANGE
            try:
                val_f = float(self.limit_input.text.strip())
            except ValueError:
                val_f = 2.0
            new_val_f = round(max(t_min, min(t_max, val_f + direction * 0.5)), 1)
            self.limit_input.set_text(f"{new_val_f:.1f}")

    def handle_event(self, event: pygame.event.Event) -> None:
        if self.board_view._promotion_active:
            self.board_view.handle_event(event)
            return

        # Enforce exclusive focus between text inputs on left-click
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if not self.text_area.rect.collidepoint(event.pos):
                self.text_area.focused = False
                self.text_area.selection = None
                self.text_area._drag_selecting = False
            if self.limit_chips.selected == 1 or not self.limit_input.rect.collidepoint(event.pos):
                self.limit_input.focused = False
                self.limit_input.all_selected = False

        # Up/Down arrow stepping when limit_input is focused
        if (
            self.limit_chips.selected != 1
            and self.limit_input.focused
            and event.type == pygame.KEYDOWN
            and event.key in (pygame.K_UP, pygame.K_DOWN)
        ):
            self._step_limit_value(1 if event.key == pygame.K_UP else -1)
            return

        if self.menu_btn.handle_event(event):
            return
        if self.text_area.handle_event(event):
            return
        if self.limit_chips.handle_event(event):
            return
        if self.limit_chips.selected != 1:  # Show limit input only when not AUTO
            if self.limit_input.handle_event(event):
                return
        if self.eval_btn.handle_event(event):
            return

        # Board moves
        if not self._eval_running:
            intent = self.board_view.handle_event(event)
            if intent is not None:
                self._on_board_move_intent(intent.from_sq, intent.to_sq)

    def update(self, dt: float) -> None:
        self.menu_btn.update(dt)
        self.eval_btn.update(dt)
        self.board_view.update(dt)
        self.text_area.update(dt)
        if self.limit_chips.selected != 1:
            self.limit_input.update(dt)

        if self._parse_dirty and (time.monotonic() - self._last_type_time >= 0.3):
            self._parse_now()

        if self._eval_running:
            self._spinner_angle = (self._spinner_angle + dt * 360) % 360

    def draw(self, surf: pygame.Surface) -> None:
        surf.fill(theme.BG)

        draw_text(surf, "EVALUATE", "heading", INK, (120, 60), anchor="midleft")
        self.menu_btn.draw(surf)

        # Chess board
        self.board_view.draw(surf)

        # Right panel container
        draw_panel(surf, self.panel_rect, fill=CARD, border=BORDER, shadow=SHADOW, shadow_color=INK)

        # FEN header & Text area
        draw_text(surf, "FEN", "label", INK, (self.panel_rect.x + 36, self.panel_rect.y + 34), anchor="topleft")
        draw_text(
            surf,
            "Paste FEN or move pieces on board",
            "small",
            SECONDARY,
            (self.panel_rect.right - 36, self.panel_rect.y + 36),
            anchor="topright",
        )
        self.text_area.draw(surf)

        # Parse error feedback
        if self._parse_error:
            err_msg = fit_text(self._parse_error, "small", self.panel_rect.width - 72)
            draw_text(surf, err_msg, "small", DANGER, (self.panel_rect.x + 36, self.panel_rect.y + 186), anchor="topleft")

        # Search limit controls
        self.limit_chips.draw(surf)

        # Number input suffix
        if self.limit_chips.selected != 1:
            self.limit_input.draw(surf)
            suffix = "plies" if self.limit_chips.selected == 0 else "sec"
            draw_text(surf, suffix, "small", SECONDARY, (self.limit_input.rect.right + 8, self.limit_input.rect.centery), anchor="midleft")
            if self.limit_input.invalid:
                if self.limit_chips.selected == 0:
                    d_min, d_max = config.EVAL_DEPTH_RANGE
                    hint = f"Depth must be between {d_min} and {d_max}"
                else:
                    t_min, t_max = config.EVAL_TIME_RANGE
                    hint = f"Time must be between {t_min} and {t_max:.0f} sec"
                draw_text(surf, fit_text(hint, "small", self.panel_rect.width - 72), "small", DANGER, (self.panel_rect.x + 36, self.panel_rect.y + 248), anchor="topleft")

        self.eval_btn.draw(surf)

        # Result display block
        res_rect = pygame.Rect(self.panel_rect.x + 36, self.panel_rect.y + 266, self.panel_rect.width - 72, 400)
        draw_panel(surf, res_rect, fill=theme.BG, border=BORDER, shadow=2)

        old_clip = surf.get_clip()
        surf.set_clip(res_rect.inflate(-8, -8))

        if self._eval_running:
            draw_text(surf, "ANALYZING POSITION...", "heading", ACCENT, res_rect.center, anchor="center")
        elif self._eval_result:
            r = self._eval_result
            score_str, word_str = describe_eval(r.score_cp, r.mate_in)
            res_x = res_rect.x + 32
            res_max_w = res_rect.width - 64

            # Big score display
            draw_text(surf, score_str, "clock", INK, (res_x, res_rect.y + 26), anchor="topleft")
            cur_y = draw_wrapped_text(surf, word_str, "heading", PURPLE, (res_x, res_rect.y + 104), max_w=res_max_w)

            # Engine info & reason caption (wrapped)
            eng_label = "Stockfish" if r.backend == "stockfish" else "OpenBoard Engine"
            caption = f"{eng_label} · depth {r.depth} · {r.seconds:.2f} s · {r.nodes} nodes"
            cur_y = draw_wrapped_text(surf, caption, "body", INK, (res_x, cur_y + 18), max_w=res_max_w)
            cur_y = draw_wrapped_text(surf, f"Router: {r.reason}", "small", SECONDARY, (res_x, cur_y + 12), max_w=res_max_w)

            # Principal variation move line (wrapped)
            if r.pv_uci:
                eval_fen = getattr(self, "_eval_fen", self._parsed_board.fen())
                line_str = san_line(eval_fen, list(r.pv_uci), max_moves=6)
                if line_str:
                    draw_wrapped_text(surf, f"Line: {line_str}", "heading", ACCENT, (res_x, cur_y + 20), max_w=res_max_w)
        else:
            draw_text(surf, "Ready for analysis.", "body", SECONDARY, res_rect.center, anchor="center")

        surf.set_clip(old_clip)
