"""
openboard.ui.scenes.game
~~~~~~~~~~~~~~~~~~~~~~~~
Main chess match scene for Pass & Play and VS Engine.
"""

from __future__ import annotations

import datetime
import logging
import time
from typing import Any

import chess
import pygame

from openboard import config
from openboard.core.clock import format_clock
from openboard.core.results import Reason
from openboard.core.session import GameSession, PlayerInfo, SessionEvent
from openboard.ui import theme
from openboard.ui.board_view import BoardView
from openboard.ui.scenes.base import Scene
from openboard.ui.theme import ACCENT, BORDER, CARD, INK, PURPLE, SECONDARY, SHADOW, TINT, draw_panel, draw_text, fit_text
from openboard.ui.widgets import Button, ScrollList

log = logging.getLogger("openboard.ui.scenes.game")


class GameScene(Scene):
    """The full gameplay scene managing board interaction, clocks, engine moves, and sounds."""

    name = "game"

    def on_enter(
        self,
        mode: str = "pass_play",
        white: PlayerInfo | None = None,
        black: PlayerInfo | None = None,
        time_control: Any = None,
        level: int | None = None,
        player1_color: chess.Color = chess.WHITE,
        **_kw: Any,
    ) -> None:
        self.mode = mode
        self.level = level
        self.player1_color = player1_color

        if white is None:
            white = PlayerInfo(name="White", kind="human")
        if black is None:
            black = PlayerInfo(name="Black", kind="human")
        if time_control is None:
            time_control = config.TIME_CONTROLS["rapid"]

        self.time_control = time_control
        self.session = GameSession(white, black, time_control)

        # BoardView
        self.board_view = BoardView(config.BOARD_ORIGIN, config.BOARD_SQ, self.ctx.assets)
        self.board_view.set_board(self.session.board)

        # Orientation: VS engine has human at bottom; Pass & Play has White at bottom
        if mode == "vs_engine":
            self.board_view.set_orientation(player1_color)
            self.board_view.set_interactive(player1_color)
        else:
            self.board_view.set_orientation(chess.WHITE)
            self.board_view.set_interactive("both")

        # Right column layout
        rc_x = 930
        rc_w = 580

        # Top bar: MENU button
        self.menu_btn = Button((1350, 48, 160, 52), "MENU", self._on_menu_click, style="secondary")

        # Player cards: Top card is opponent, Bottom card is local player
        self.top_card_rect = pygame.Rect(rc_x, 136, rc_w, 100)
        self.bot_card_rect = pygame.Rect(rc_x, 260, rc_w, 100)

        # Moves ScrollList
        moves_h = 300
        moves_y = 420
        self.moves_list = ScrollList(
            (rc_x, moves_y, rc_w, moves_h),
            item_height=32,
            draw_item=self._draw_move_item,
            items=[],
        )
        self._last_move_count: int = 0

        # Action buttons
        btn_y = moves_y + moves_h + 20
        if self.mode == "pass_play":
            btn_w = (rc_w - 20) // 2
            self.draw_btn: Button | None = Button((rc_x, btn_y, btn_w, 56), "DRAW", self._on_draw_click, style="secondary")
            self.resign_btn = Button((rc_x + btn_w + 20, btn_y, btn_w, 56), "RESIGN", self._on_resign_click, style="secondary")
        else:
            self.draw_btn = None
            self.resign_btn = Button((rc_x, btn_y, rc_w, 56), "RESIGN", self._on_resign_click, style="secondary")

        # Engine turn management
        self._engine_thinking: bool = False
        self._engine_req_id: int | None = None
        self._engine_req_time: float = 0.0
        self._engine_dots_t: float = 0.0
        self._engine_dots_count: int = 0
        self._last_engine_eval_score: float = 0.0

        # Temporary status message (e.g. Draw Declined)
        self._temp_status_msg: str | None = None
        self._temp_status_expiry: float = 0.0

        # Game over bookkeeping
        self._recorded_to_history: bool = False

    def on_exit(self) -> None:
        self.ctx.engines.cancel()

    def _draw_move_item(self, surf: pygame.Surface, item: tuple[int, str, str | None], rect: pygame.Rect, idx: int, hovered: bool) -> None:
        num, white_san, black_san = item
        num_str = f"{num}."
        draw_text(surf, num_str, "label", SECONDARY, (rect.x + 12, rect.centery), anchor="midleft")
        draw_text(surf, white_san, "label", INK, (rect.x + 80, rect.centery), anchor="midleft")
        if black_san:
            draw_text(surf, black_san, "label", INK, (rect.x + 240, rect.centery), anchor="midleft")

    def _on_menu_click(self) -> None:
        def on_confirm(yes: bool) -> None:
            if yes:
                if not self.session.is_over:
                    self.session.resign(self.player1_color)
                    self._record_game_history(abandoned=True)
                self.ctx.scenes.go("main_menu")

        self.ctx.scenes.push(
            "confirm",
            title="LEAVE MATCH",
            message="Leaving an active game will count as an immediate loss. Return to menu?",
            yes_label="LEAVE",
            no_label="RESUME",
            on_result=on_confirm,
        )

    def _on_resign_click(self) -> None:
        if self.session.is_over:
            return

        def on_confirm(yes: bool) -> None:
            if yes:
                self.session.resign(self.session.turn)

        self.ctx.scenes.push(
            "confirm",
            title="RESIGN GAME",
            message=f"Are you sure {self.session.current_player.name} wants to resign?",
            yes_label="RESIGN",
            no_label="CANCEL",
            on_result=on_confirm,
        )

    def _on_draw_click(self) -> None:
        if self.session.is_over or self.mode != "pass_play":
            return

        offering_player = self.session.current_player
        other_player = self.session.black if self.session.turn == chess.WHITE else self.session.white
        self.session.offer_draw(self.session.turn)

        def on_confirm(yes: bool) -> None:
            if yes:
                self.session.accept_draw()
            else:
                self.session.decline_draw()
                self._show_temp_status("DRAW DECLINED")

        self.ctx.scenes.push(
            "confirm",
            title="DRAW OFFER",
            message=f"{offering_player.name} offers a draw. {other_player.name}, do you accept?",
            yes_label="ACCEPT",
            no_label="DECLINE",
            on_result=on_confirm,
        )

    def _show_temp_status(self, msg: str, duration: float = 3.0) -> None:
        self._temp_status_msg = msg
        self._temp_status_expiry = time.monotonic() + duration

    def _trigger_engine_move_if_needed(self) -> None:
        if self.session.is_over or self._engine_thinking:
            return

        curr_pi = self.session.current_player
        if curr_pi.kind != "engine":
            return

        self._engine_thinking = True
        self._engine_req_time = time.monotonic()
        req_kwargs = {
            "fen": self.session.fen,
            "purpose": "play",
            "level": self.level,
            "time_s": 5.0,
        }
        self._engine_req_id = self.ctx.engines.submit(req_kwargs, self._on_engine_move_arrived)

    def _on_engine_move_arrived(self, result: Any) -> None:
        if result.request_id != self._engine_req_id:
            return  # Stale

        # Record score for draw offer logic
        if result.score_cp is not None:
            self._last_engine_eval_score = result.score_cp / 100.0

        # Delay execution if returned faster than MIN_ENGINE_MOVE_DELAY_S
        elapsed = time.monotonic() - self._engine_req_time
        remaining_delay = max(0.0, config.MIN_ENGINE_MOVE_DELAY_S - elapsed)

        def apply_move() -> None:
            if result.best_uci and not self.session.is_over:
                res = self.session.apply_uci(result.best_uci)
                self.board_view.set_board(self.session.board)
                self.board_view.set_marks(self.session.last_move, self.session.check_square)
                if res.move:
                    self.board_view.animate_move(res.move, ms=150)
            self._engine_thinking = False
            self._engine_req_id = None

        if remaining_delay > 0.01:
            # Simple deferred invocation on next frame via timer
            self._delayed_engine_action = (time.monotonic() + remaining_delay, apply_move)
        else:
            apply_move()

    def handle_event(self, event: pygame.event.Event) -> None:
        if self.menu_btn.handle_event(event):
            return
        if self.draw_btn and self.draw_btn.handle_event(event):
            return
        if self.resign_btn.handle_event(event):
            return
        if self.moves_list.handle_event(event):
            return

        # Board moves
        if not self.session.is_over and not self._engine_thinking:
            intent = self.board_view.handle_event(event)
            if intent is not None:
                if self.session.needs_promotion(intent.from_sq, intent.to_sq):
                    self.board_view.ask_promotion(
                        self.session.turn,
                        lambda promo: self._execute_move(intent.from_sq, intent.to_sq, promo),
                    )
                else:
                    self._execute_move(intent.from_sq, intent.to_sq, None)

    def _execute_move(self, from_sq: int, to_sq: int, promo: int | None) -> None:
        res = self.session.try_move(from_sq, to_sq, promo)
        if res.ok:
            self.board_view.set_board(self.session.board)
            self.board_view.set_marks(self.session.last_move, self.session.check_square)
            if res.move:
                self.board_view.animate_move(res.move, ms=150)

    def update(self, dt: float) -> None:
        self.menu_btn.update(dt)
        if self.draw_btn:
            self.draw_btn.update(dt)
        self.resign_btn.update(dt)
        self.board_view.update(dt)

        # Handle delayed engine action
        if hasattr(self, "_delayed_engine_action") and self._delayed_engine_action:
            fire_time, action = self._delayed_engine_action
            if time.monotonic() >= fire_time:
                self._delayed_engine_action = None
                action()

        # Update clocks and game state
        if not self.session.is_over:
            self.session.update()

        # Drain audio events
        for ev in self.session.drain_events():
            if ev == SessionEvent.MOVE:
                self.ctx.sfx("move")
            elif ev == SessionEvent.CAPTURE:
                self.ctx.sfx("capture")
            elif ev == SessionEvent.CHECK:
                self.ctx.sfx("check")
            elif ev == SessionEvent.CASTLE:
                self.ctx.sfx("castle")
            elif ev == SessionEvent.GAME_OVER:
                self.ctx.sfx("game_end")

        # Moves list update — only auto-scroll when new moves are played so user scrolling is preserved
        move_count = len(self.session.san_moves)
        if move_count != self._last_move_count:
            self._last_move_count = move_count
            self.moves_list.set_items(self.session.move_rows)
            self.moves_list.scroll_to_bottom()

        # Engine dots animation
        if self._engine_thinking:
            self._engine_dots_t += dt
            if self._engine_dots_t >= 0.35:
                self._engine_dots_t = 0.0
                self._engine_dots_count = (self._engine_dots_count + 1) % 4

        # Trigger engine if needed
        self._trigger_engine_move_if_needed()

        # Game over handling
        if self.session.is_over and not self._recorded_to_history:
            self._record_game_history(abandoned=False)
            self._show_game_over_dialog()

    def _record_game_history(self, abandoned: bool = False) -> None:
        if self._recorded_to_history:
            return
        self._recorded_to_history = True

        outcome = self.session.outcome
        winner = outcome.winner if outcome else None

        if abandoned:
            result_str = "lost"
            reason_str = "abandoned"
        else:
            if winner is None:
                result_str = "drawn"
            elif winner == self.player1_color:
                result_str = "won"
            else:
                result_str = "lost"
            reason_str = outcome.reason.value if outcome else "unknown"

        opp_name = self.session.black.name if self.player1_color == chess.WHITE else self.session.white.name

        rec = {
            "started_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "mode": self.mode,
            "opponent": opp_name,
            "engine_level": self.level if self.mode == "vs_engine" else None,
            "time_control": getattr(self.time_control, "label", "RAPID 10 + 0"),
            "player_color": "white" if self.player1_color == chess.WHITE else "black",
            "result": result_str,
            "reason": reason_str,
            "moves": len(self.session.san_moves),
            "pgn": self.session.to_record(self.player1_color).get("pgn", ""),
            "backends": None,
        }

        try:
            self.ctx.history.add(rec)
        except Exception as exc:
            log.warning("Could not record match to history: %s", exc)

    def _show_game_over_dialog(self) -> None:
        headline = self.session.status_text

        def on_choice(play_again_chosen: bool) -> None:
            if play_again_chosen:
                self.ctx.scenes.go(
                    "game",
                    mode=self.mode,
                    white=self.session.white,
                    black=self.session.black,
                    time_control=self.time_control,
                    level=self.level,
                    player1_color=self.player1_color,
                )
            else:
                self.ctx.scenes.go("opponent_select")

        self.ctx.scenes.push(
            "confirm",
            title="GAME OVER",
            message=headline,
            yes_label="PLAY AGAIN",
            no_label="BACK",
            on_result=on_choice,
        )

    def draw(self, surf: pygame.Surface) -> None:
        surf.fill(theme.BG)

        # Top title & mode
        mode_title = "PASS & PLAY" if self.mode == "pass_play" else "VS ENGINE"
        draw_text(surf, mode_title, "heading", INK, (120, 60), anchor="midleft")
        tc_label = getattr(self.time_control, "label", "RAPID · 10 + 0")
        draw_text(surf, tc_label, "label", PURPLE, (self.menu_btn.rect.left - 32, self.menu_btn.rect.centery), anchor="midright")

        self.menu_btn.draw(surf)

        # Chess board
        self.board_view.draw(surf)

        # Player cards
        top_color = chess.BLACK if self.board_view.orientation == chess.WHITE else chess.WHITE
        bot_color = chess.WHITE if self.board_view.orientation == chess.WHITE else chess.BLACK

        top_player = self.session.black if top_color == chess.BLACK else self.session.white
        bot_player = self.session.white if bot_color == chess.WHITE else self.session.black

        self._draw_player_card(surf, self.top_card_rect, top_player, top_color)
        self._draw_player_card(surf, self.bot_card_rect, bot_player, bot_color)

        # Status line
        status_y = 380
        if self._temp_status_msg and time.monotonic() < self._temp_status_expiry:
            status_text = self._temp_status_msg
        elif self._engine_thinking:
            dots = "." * self._engine_dots_count
            status_text = f"ENGINE THINKING{dots}"
        else:
            status_text = self.session.status_text

        draw_text(surf, fit_text(status_text, "heading", 560), "heading", ACCENT, (930 + 290, status_y), anchor="center")

        # Moves list
        self.moves_list.draw(surf)

        # Action buttons
        if self.draw_btn:
            self.draw_btn.draw(surf)
        self.resign_btn.draw(surf)

    def _draw_player_card(self, surf: pygame.Surface, rect: pygame.Rect, player: PlayerInfo, color: chess.Color) -> None:
        is_turn = (self.session.turn == color) and not self.session.is_over
        card_fill = INK if is_turn else CARD
        text_col = CARD if is_turn else INK

        draw_panel(surf, rect, fill=card_fill, border=BORDER, shadow=SHADOW if not is_turn else 2, shadow_color=INK)

        # Name & side label
        side_str = "WHITE" if color == chess.WHITE else "BLACK"
        draw_text(surf, fit_text(player.name.upper(), "label", rect.width - 230), "label", text_col, (rect.x + 24, rect.y + 24), anchor="topleft")
        draw_text(surf, side_str, "small", TINT if is_turn else SECONDARY, (rect.x + 24, rect.bottom - 24), anchor="bottomleft")

        # Clock
        rem = self.session.clock.remaining(color)
        clock_str = format_clock(rem)
        draw_text(surf, clock_str, "clock", text_col, (rect.right - 24, rect.centery), anchor="midright")
