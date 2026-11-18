"""
openboard.core.session
~~~~~~~~~~~~~~~~~~~~~~
High-level game session: moves, clock, events, outcome.  No pygame, no threads,
no engine calls.
"""

from __future__ import annotations

import enum
import logging
import time as _time
from dataclasses import dataclass, field
from typing import Literal

import chess
import chess.pgn

from openboard.core.clock import ChessClock
from openboard.core.results import GameOutcome, Reason, outcome_from_board

log = logging.getLogger("openboard.core.session")


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class PlayerInfo:
    """Identity and kind of one player.

    Attributes:
        name: Display name.
        kind: ``'human'`` or ``'engine'``.
        engine_level: UI difficulty level (1–8), only used for engine players.
    """

    name: str
    kind: Literal["human", "engine"]
    engine_level: int | None = None


class SessionEvent(enum.Enum):
    """Events emitted by :class:`GameSession` after each move."""

    MOVE = "move"
    CAPTURE = "capture"
    CHECK = "check"
    CASTLE = "castle"
    PROMOTION = "promotion"
    GAME_OVER = "game_over"


@dataclass
class MoveResult:
    """Result of :meth:`GameSession.try_move` or :meth:`GameSession.apply_uci`.

    Attributes:
        ok: ``True`` iff the move was accepted.
        move: The :class:`chess.Move` that was applied, or ``None``.
        san: SAN string of the move, or ``None``.
        events: Events fired by this move.
        error: Human-readable error when *ok* is ``False``.
    """

    ok: bool
    move: chess.Move | None = None
    san: str | None = None
    events: list[SessionEvent] = field(default_factory=list)
    error: str | None = None


# ---------------------------------------------------------------------------
# GameSession
# ---------------------------------------------------------------------------


class GameSession:
    """Manages a single chess game: board, clock, moves, draw offers, outcome.

    Args:
        white: White player information.
        black: Black player information.
        time_control: A time-control object with ``minutes`` and
            ``increment_s`` attributes (e.g. a :class:`~openboard.config.TimeControl`).
        start_fen: Starting FEN, or ``None`` for the standard opening.
        now: Time source (injectable for testing).
    """

    def __init__(
        self,
        white: PlayerInfo,
        black: PlayerInfo,
        time_control: object,
        start_fen: str | None = None,
        now: object = _time.monotonic,
    ) -> None:
        self._white = white
        self._black = black
        self._board: chess.Board = (
            chess.Board(start_fen) if start_fen else chess.Board()
        )
        self._start_fen: str = start_fen or chess.STARTING_FEN
        self._clock = ChessClock(time_control, now=now)  # type: ignore[arg-type]
        self._clock.start(chess.WHITE)
        self._outcome: GameOutcome | None = None
        self._san_moves: list[str] = []
        self._pending_events: list[SessionEvent] = []
        self._draw_offered_by: chess.Color | None = None

    # ------------------------------------------------------------------
    # Move interface
    # ------------------------------------------------------------------

    def legal_targets(self, square: int) -> list[int]:
        """Return destination squares reachable from *square* for the side to move.

        Args:
            square: Source square index (0–63).

        Returns:
            Sorted list of destination square indices.
        """
        if self._outcome is not None:
            return []
        return sorted(
            {
                m.to_square
                for m in self._board.legal_moves
                if m.from_square == square
            }
        )

    def needs_promotion(self, from_sq: int, to_sq: int) -> bool:
        """Return ``True`` if the pawn on *from_sq* promotes when moving to *to_sq*.

        Args:
            from_sq: Source square.
            to_sq: Destination square.

        Returns:
            ``True`` iff a promotion piece must be chosen.
        """
        piece = self._board.piece_at(from_sq)
        if piece is None or piece.piece_type != chess.PAWN:
            return False
        rank = chess.square_rank(to_sq)
        if rank not in (0, 7):
            return False
        return chess.Move(from_sq, to_sq, promotion=chess.QUEEN) in self._board.legal_moves

    def try_move(
        self,
        from_sq: int,
        to_sq: int,
        promotion: int | None = None,
    ) -> MoveResult:
        """Attempt a move from *from_sq* to *to_sq*.

        Args:
            from_sq: Source square index.
            to_sq: Destination square index.
            promotion: Promotion piece type (e.g. ``chess.QUEEN``), or ``None``.

        Returns:
            A :class:`MoveResult`.
        """
        if self._outcome is not None:
            return MoveResult(ok=False, error="Game is already over")

        move = chess.Move(from_sq, to_sq, promotion=promotion)
        # Handle under-promotion by trying all promotions if promotion is None
        # and it's a pawn move to the back rank.
        if promotion is None and self.needs_promotion(from_sq, to_sq):
            move = chess.Move(from_sq, to_sq, promotion=chess.QUEEN)

        if move not in self._board.legal_moves:
            return MoveResult(ok=False, error=f"Illegal move: {move.uci()}")

        return self._apply_move(move)

    def apply_uci(self, uci: str) -> MoveResult:
        """Apply a move from a UCI string (used for engine moves).

        Args:
            uci: Move in UCI notation, e.g. ``'e2e4'`` or ``'e7e8q'``.

        Returns:
            A :class:`MoveResult`.
        """
        if self._outcome is not None:
            return MoveResult(ok=False, error="Game is already over")
        try:
            move = chess.Move.from_uci(uci)
        except ValueError as exc:
            return MoveResult(ok=False, error=str(exc))
        if move not in self._board.legal_moves:
            return MoveResult(ok=False, error=f"Illegal move: {uci}")
        return self._apply_move(move)

    def _apply_move(self, move: chess.Move) -> MoveResult:
        """Internal: apply *move* unconditionally, update state, emit events."""
        moving_color = self._board.turn

        # Collect events before pushing
        events: list[SessionEvent] = [SessionEvent.MOVE]
        is_capture = self._board.is_capture(move)
        is_castle = self._board.is_castling(move)
        is_en_passant = self._board.is_en_passant(move)
        is_promotion = bool(move.promotion)

        if is_capture or is_en_passant:
            events.append(SessionEvent.CAPTURE)
        if is_castle:
            events.append(SessionEvent.CASTLE)
        if is_promotion:
            events.append(SessionEvent.PROMOTION)

        san = self._board.san(move)
        self._board.push(move)
        self._san_moves.append(san)

        # Check detection (after push)
        if self._board.is_check():
            events.append(SessionEvent.CHECK)

        # Clock press
        self._clock.update()
        self._clock.press(moving_color)

        # Check for game over
        self._outcome = outcome_from_board(self._board)
        if self._outcome is not None:
            events.append(SessionEvent.GAME_OVER)

        self._pending_events.extend(events)

        return MoveResult(
            ok=True,
            move=move,
            san=san,
            events=events,
        )

    # ------------------------------------------------------------------
    # Game control
    # ------------------------------------------------------------------

    def resign(self, color: chess.Color) -> None:
        """Resign on behalf of *color*.

        Args:
            color: The side that is resigning.
        """
        if self._outcome is not None:
            return
        winner: chess.Color = not color  # type: ignore[assignment]
        self._outcome = GameOutcome(winner=winner, reason=Reason.RESIGNATION)
        self._pending_events.append(SessionEvent.GAME_OVER)
        log.info("%s resigned", "WHITE" if color == chess.WHITE else "BLACK")

    def offer_draw(self, by: chess.Color) -> None:
        """Record a draw offer from *by*.

        Args:
            by: The side offering the draw.
        """
        self._draw_offered_by = by
        log.debug("Draw offered by %s", "WHITE" if by == chess.WHITE else "BLACK")

    def accept_draw(self) -> None:
        """Accept a pending draw offer or agree to a draw."""
        if self._outcome is not None:
            return
        self._outcome = GameOutcome(winner=None, reason=Reason.DRAW_AGREED)
        self._draw_offered_by = None
        self._pending_events.append(SessionEvent.GAME_OVER)
        log.info("Draw agreed")

    def decline_draw(self) -> None:
        """Decline a pending draw offer."""
        self._draw_offered_by = None
        log.debug("Draw declined")

    def update(self) -> None:
        """Update the clock and end the game on timeout.

        Call this every game-loop frame.
        """
        if self._outcome is not None:
            return
        self._clock.update()
        flagged = self._clock.flagged()
        if flagged is not None:
            winner: chess.Color | None
            # Check whether the opponent has sufficient mating material
            opponent: chess.Color = not flagged  # type: ignore[assignment]
            # Insufficient material for opponent → draw; else opponent wins
            # (simplified: check whether opponent has any pieces beyond king)
            if self._board.occupied_co[opponent] & ~self._board.kings:
                winner = opponent
            else:
                winner = None  # draw by insufficient mating material
            self._outcome = GameOutcome(winner=winner, reason=Reason.TIMEOUT)
            self._pending_events.append(SessionEvent.GAME_OVER)
            log.info(
                "%s flagged",
                "WHITE" if flagged == chess.WHITE else "BLACK",
            )

    def drain_events(self) -> list[SessionEvent]:
        """Return and clear all pending events.

        Returns:
            List of :class:`SessionEvent` values since last drain.
        """
        events = list(self._pending_events)
        self._pending_events.clear()
        return events

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def board(self) -> chess.Board:
        """The underlying :class:`chess.Board`."""
        return self._board

    @property
    def last_move(self) -> chess.Move | None:
        """The last move played, or None if no moves have been made yet."""
        if self._board.move_stack:
            return self._board.peek()
        return None

    @property
    def white(self) -> PlayerInfo:
        """White player information."""
        return self._white

    @property
    def black(self) -> PlayerInfo:
        """Black player information."""
        return self._black

    @property
    def clock(self) -> ChessClock:
        """The chess clock."""
        return self._clock

    @property
    def current_player(self) -> PlayerInfo:
        """The player whose turn it is to move."""
        return self._white if self._board.turn == chess.WHITE else self._black

    @property
    def turn(self) -> chess.Color:
        """The side to move."""
        return self._board.turn

    @property
    def is_over(self) -> bool:
        """``True`` iff the game has ended."""
        return self._outcome is not None

    @property
    def outcome(self) -> GameOutcome | None:
        """The :class:`GameOutcome`, or ``None`` if still playing."""
        return self._outcome

    @property
    def move_rows(self) -> list[tuple[int, str, str | None]]:
        """Move list as display rows.

        Returns:
            List of ``(move_number, white_san, black_san_or_None)`` tuples.
        """
        rows: list[tuple[int, str, str | None]] = []
        for i in range(0, len(self._san_moves), 2):
            move_num = i // 2 + 1
            white_san = self._san_moves[i]
            black_san = self._san_moves[i + 1] if i + 1 < len(self._san_moves) else None
            rows.append((move_num, white_san, black_san))
        return rows

    @property
    def check_square(self) -> int | None:
        """The square of the king in check, or ``None``."""
        if not self._board.is_check():
            return None
        return self._board.king(self._board.turn)

    @property
    def fen(self) -> str:
        """Current board FEN."""
        return self._board.fen()

    @property
    def san_moves(self) -> list[str]:
        """All moves played so far in SAN notation."""
        return list(self._san_moves)

    @property
    def draw_offered_by(self) -> chess.Color | None:
        """The color that offered a draw, or None if no offer is pending."""
        return self._draw_offered_by

    @property
    def status_text(self) -> str:
        """Single-line status string for display."""
        if self._outcome is not None:
            return self._outcome.headline
        if self._board.is_check():
            side = "WHITE" if self._board.turn == chess.WHITE else "BLACK"
            return f"{side} IN CHECK"
        side = "WHITE" if self._board.turn == chess.WHITE else "BLACK"
        return f"{side} TO MOVE"

    # ------------------------------------------------------------------
    # Record
    # ------------------------------------------------------------------

    def to_record(self, player1_color: chess.Color) -> dict:
        """Serialize the session to a plain-dict record for storage.

        Args:
            player1_color: Which color ``player1`` (the local human) played.

        Returns:
            A JSON-serialisable ``dict``.
        """
        try:
            game = chess.pgn.Game.from_board(self._board)
            game.headers["White"] = self._white.name
            game.headers["Black"] = self._black.name
            game.headers["Result"] = self._outcome.result_string if self._outcome else "*"
            exporter = chess.pgn.StringExporter(headers=True, variations=False, comments=False)
            pgn_str = game.accept(exporter)
        except Exception:
            pgn_str = " ".join(self._san_moves)

        return {
            "white": self._white.name,
            "black": self._black.name,
            "player1_color": "white" if player1_color == chess.WHITE else "black",
            "start_fen": self._start_fen,
            "san_moves": list(self._san_moves),
            "pgn": pgn_str,
            "result": self._outcome.result_string if self._outcome else "*",
            "reason": self._outcome.reason.value if self._outcome else None,
            "winner": (
                "white"
                if self._outcome and self._outcome.winner == chess.WHITE
                else "black"
                if self._outcome and self._outcome.winner == chess.BLACK
                else None
            ),
        }
