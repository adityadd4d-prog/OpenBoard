"""
openboard.core.results
~~~~~~~~~~~~~~~~~~~~~~
Game outcomes, PGN generation, and evaluation formatting.  No pygame.
"""

from __future__ import annotations

import enum
import io
import logging
from dataclasses import dataclass

import chess
import chess.pgn

from openboard.config import (
    EVAL_CLEAR_ADVANTAGE_MAX,
    EVAL_EQUAL_MAX,
    EVAL_SLIGHT_EDGE_MAX,
)

log = logging.getLogger("openboard.core.results")


# ---------------------------------------------------------------------------
# Reason enum
# ---------------------------------------------------------------------------


class Reason(enum.Enum):
    """Why the game ended."""

    CHECKMATE = "checkmate"
    RESIGNATION = "resignation"
    TIMEOUT = "timeout"
    STALEMATE = "stalemate"
    DRAW_AGREED = "draw_agreed"
    INSUFFICIENT = "insufficient"
    FIFTY_MOVE = "fifty_move"
    REPETITION = "repetition"
    ABANDONED = "abandoned"


# ---------------------------------------------------------------------------
# GameOutcome
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class GameOutcome:
    """Immutable record of how a game ended.

    Attributes:
        winner: :data:`chess.WHITE`, :data:`chess.BLACK`, or ``None`` for a draw.
        reason: Why the game ended.
    """

    winner: chess.Color | None
    reason: Reason

    @property
    def result_string(self) -> str:
        """Standard PGN result token: ``'1-0'``, ``'0-1'``, or ``'1/2-1/2'``."""
        if self.winner == chess.WHITE:
            return "1-0"
        if self.winner == chess.BLACK:
            return "0-1"
        return "1/2-1/2"

    @property
    def headline(self) -> str:
        """Human-readable single-line summary, e.g. ``'WHITE WINS - CHECKMATE'``."""
        reason_label = self.reason.name.replace("_", " ")
        if self.winner == chess.WHITE:
            return f"WHITE WINS - {reason_label}"
        if self.winner == chess.BLACK:
            return f"BLACK WINS - {reason_label}"
        return f"DRAW - {reason_label}"


# ---------------------------------------------------------------------------
# outcome_from_board
# ---------------------------------------------------------------------------


def outcome_from_board(board: chess.Board) -> GameOutcome | None:
    """Determine the outcome of *board*, claiming draws automatically.

    Fifty-move and threefold-repetition draws are claimed (not just detected)
    so the game can end without an explicit player claim.  Five-fold repetition
    and the 75-move rule are subsumed by those checks.

    Args:
        board: Current board state.

    Returns:
        A :class:`GameOutcome`, or ``None`` if the game is still ongoing.
    """
    # Checkmate / stalemate via python-chess
    if board.is_checkmate():
        return GameOutcome(winner=not board.turn, reason=Reason.CHECKMATE)  # type: ignore[arg-type]

    if board.is_stalemate():
        return GameOutcome(winner=None, reason=Reason.STALEMATE)

    if board.is_insufficient_material():
        return GameOutcome(winner=None, reason=Reason.INSUFFICIENT)

    # Claim fifty-move (also covers 75-move, which always implies fifty-move)
    if board.can_claim_fifty_moves():
        return GameOutcome(winner=None, reason=Reason.FIFTY_MOVE)

    # Claim threefold repetition (also covers fivefold)
    if board.can_claim_threefold_repetition():
        return GameOutcome(winner=None, reason=Reason.REPETITION)

    return None


# ---------------------------------------------------------------------------
# build_pgn
# ---------------------------------------------------------------------------


def build_pgn(
    white: str,
    black: str,
    outcome: GameOutcome,
    moves: list[str] | chess.Board,
    start_fen: str | None,
    time_control_label: str,
    date: str,
) -> str:
    """Build a PGN string for a completed game.

    Args:
        white: Name of the White player.
        black: Name of the Black player.
        outcome: Game outcome.
        moves: Either a list of UCI move strings, or a fully-played
            :class:`chess.Board` (the mainline is read from its move stack).
        start_fen: Starting FEN, or ``None`` for the standard opening.
        time_control_label: Human-readable time control string.
        date: Date string in ``YYYY.MM.DD`` format.

    Returns:
        A PGN string ready to write to a file.
    """
    game = chess.pgn.Game()
    game.headers["Event"] = "OpenBoard Game"
    game.headers["Site"] = "OpenBoard"
    game.headers["Date"] = date
    game.headers["White"] = white
    game.headers["Black"] = black
    game.headers["Result"] = outcome.result_string
    game.headers["TimeControl"] = time_control_label
    game.headers["Termination"] = outcome.reason.value.replace("_", " ")

    if start_fen and start_fen != chess.STARTING_FEN:
        game.headers["SetUp"] = "1"
        game.headers["FEN"] = start_fen

    # Build node chain from moves
    if isinstance(moves, chess.Board):
        move_list = list(moves.move_stack)
    else:
        move_list = list(moves)

    if start_fen and start_fen != chess.STARTING_FEN:
        game.setup(chess.Board(start_fen))

    node = game
    replay_board = chess.Board(start_fen) if start_fen else chess.Board()
    for item in move_list:
        if isinstance(item, chess.Move):
            move = item
        else:
            try:
                move = replay_board.parse_san(item)
            except Exception:
                move = chess.Move.from_uci(item)
        node = node.add_variation(move)
        replay_board.push(move)

    out = io.StringIO()
    exporter = chess.pgn.FileExporter(out)
    game.accept(exporter)
    return out.getvalue()


# ---------------------------------------------------------------------------
# describe_eval
# ---------------------------------------------------------------------------


def describe_eval(
    score_cp: int | None,
    mate_in: int | None,
) -> tuple[str, str]:
    """Format an engine evaluation as a (score_str, word_label) pair.

    Scores are from White's point of view.

    Args:
        score_cp: Centipawn score, or ``None``.
        mate_in: Mate-in-N (positive = White mates, negative = Black mates),
            or ``None``.

    Returns:
        A ``(score_str, label)`` tuple, e.g. ``('+0.20', 'EQUAL')``.
    """
    if mate_in is not None:
        if mate_in > 0:
            return (f"#{mate_in}", f"MATE IN {mate_in}")
        elif mate_in < 0:
            return (f"#-{abs(mate_in)}", f"MATED IN {abs(mate_in)}")
        # mate_in == 0: shouldn't normally occur mid-game
        return ("#0", "CHECKMATE")

    if score_cp is None:
        return ("--", "NO EVALUATION")

    pawns = score_cp / 100.0
    sign = "+" if pawns >= 0 else ""
    score_str = f"{sign}{pawns:.2f}"

    abs_pawns = abs(pawns)
    if abs_pawns < EVAL_EQUAL_MAX:
        label = "EQUAL"
    elif abs_pawns < EVAL_SLIGHT_EDGE_MAX:
        label = "SLIGHT EDGE"
    elif abs_pawns < EVAL_CLEAR_ADVANTAGE_MAX:
        label = "CLEAR ADVANTAGE"
    else:
        label = "WINNING"

    return (score_str, label)
