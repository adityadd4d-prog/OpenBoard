"""
tests/test_results.py
~~~~~~~~~~~~~~~~~~~~~
Tests for openboard.core.results.
"""

import io
import chess
import chess.pgn
import pytest

from openboard.core.results import (
    GameOutcome,
    Reason,
    build_pgn,
    describe_eval,
    outcome_from_board,
)


def test_outcome_headlines_and_result_strings() -> None:
    # Checkmate White
    o1 = GameOutcome(winner=chess.WHITE, reason=Reason.CHECKMATE)
    assert o1.result_string == "1-0"
    assert "WHITE WINS" in o1.headline

    # Checkmate Black
    o2 = GameOutcome(winner=chess.BLACK, reason=Reason.CHECKMATE)
    assert o2.result_string == "0-1"
    assert "BLACK WINS" in o2.headline

    # Stalemate
    o3 = GameOutcome(winner=None, reason=Reason.STALEMATE)
    assert o3.result_string == "1/2-1/2"
    assert "DRAW" in o3.headline

    # Resignation
    o4 = GameOutcome(winner=chess.BLACK, reason=Reason.RESIGNATION)
    assert "BLACK WINS - RESIGNATION" in o4.headline

    # Timeout
    o5 = GameOutcome(winner=chess.WHITE, reason=Reason.TIMEOUT)
    assert "WHITE WINS - TIMEOUT" in o5.headline


def test_outcome_from_board() -> None:
    # Starting position -> None
    b = chess.Board()
    assert outcome_from_board(b) is None

    # Checkmate position (Fool's Mate: 1. f3 e5 2. g4 Qh4#)
    b_mate = chess.Board("rnb1kbnr/pppp1ppp/8/4p3/5PPq/8/PPPPP2P/RNBQKBNR w KQkq - 1 3")
    o_mate = outcome_from_board(b_mate)
    assert o_mate is not None
    assert o_mate.winner == chess.BLACK
    assert o_mate.reason == Reason.CHECKMATE

    # Stalemate position: White Ka8, Black Ka6, Qc7
    b_stale = chess.Board("k7/2Q5/K7/8/8/8/8/8 b - - 0 1")
    o_stale = outcome_from_board(b_stale)
    assert o_stale is not None
    assert o_stale.winner is None
    assert o_stale.reason == Reason.STALEMATE


def test_pgn_round_trip() -> None:
    outcome = GameOutcome(winner=chess.WHITE, reason=Reason.CHECKMATE)
    moves = ["e4", "e5", "Qh5", "Nc6", "Bc4", "Nf6", "Qxf7#"]
    pgn_text = build_pgn(
        white="Player 1",
        black="Player 2",
        outcome=outcome,
        moves=moves,
        start_fen=None,
        time_control_label="RAPID 10 + 0",
        date="2026.11.17",
    )

    game = chess.pgn.read_game(io.StringIO(pgn_text))
    assert game is not None
    assert game.headers["White"] == "Player 1"
    assert game.headers["Black"] == "Player 2"
    assert game.headers["Result"] == "1-0"
    assert game.headers["Termination"] == "checkmate"

    # Verify moves replay
    board = game.board()
    for move in game.mainline_moves():
        board.push(move)
    assert board.is_checkmate()


def test_describe_eval_boundaries() -> None:
    # Thresholds:
    # EQUAL < 0.5 (50 cp)
    # SLIGHT EDGE < 1.0 (100 cp)
    # CLEAR ADVANTAGE < 3.0 (300 cp)
    # otherwise WINNING

    assert describe_eval(0, None) == ("+0.00", "EQUAL")
    assert describe_eval(49, None) == ("+0.49", "EQUAL")
    assert describe_eval(50, None) == ("+0.50", "SLIGHT EDGE")
    assert describe_eval(99, None) == ("+0.99", "SLIGHT EDGE")
    assert describe_eval(100, None) == ("+1.00", "CLEAR ADVANTAGE")
    assert describe_eval(299, None) == ("+2.99", "CLEAR ADVANTAGE")
    assert describe_eval(300, None) == ("+3.00", "WINNING")
    assert describe_eval(-350, None) == ("-3.50", "WINNING")

    # Mates
    assert describe_eval(None, 3) == ("#3", "MATE IN 3")
    assert describe_eval(None, -2) == ("#-2", "MATED IN 2")

    # None
    assert describe_eval(None, None) == ("--", "NO EVALUATION")
