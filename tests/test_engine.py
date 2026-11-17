"""
tests/test_engine.py
~~~~~~~~~~~~~~~~~~~~
Tests for the modified openboard.engines.engine.Engine.
"""

import threading
import time
import chess
import pytest

from openboard.engines.engine import Engine, LEVELS, MATE_SCORE


def test_finds_mate_in_one() -> None:
    # Fool's mate setup: White plays 1. f3 e5 2. g4 Qh4#
    board = chess.Board("rnb1kbnr/pppp1ppp/8/4p3/5PPq/8/PPPPP2P/RNBQKBNR w KQkq - 1 3")
    # Wait, in this board, Black just played Qh4# so White is checkmated
    # Let's set up where Black has Qh4# available:
    # 1. f3 e5 2. g4 -> White to move or Black to move
    board = chess.Board("rnbqkbnr/pppp1ppp/8/4p3/6P1/5P2/PPPPP2P/RNBQKBNR b KQkq - 0 2")
    engine = Engine(depth=2, level=None, log_to_file=False)
    move, score, nodes = engine.best_move(board)
    assert move == chess.Move.from_uci("d8h4")
    assert score is not None
    # For Black winning, score is -MATE_SCORE + ply
    assert score <= -9000


def test_returns_legal_move_at_every_level() -> None:
    board = chess.Board()
    engine = Engine(depth=1, log_to_file=False)
    for lvl in range(1, 6):
        engine.set_level(lvl)
        move, score, nodes = engine.best_move(board, time_limit=1.0)
        assert move is not None
        assert move in board.legal_moves


def test_honours_stop_event_quickly() -> None:
    board = chess.Board()
    engine = Engine(depth=6, level=None, log_to_file=False)
    stop = threading.Event()
    stop.set()  # Already set before search starts
    t0 = time.monotonic()
    move, score, nodes = engine.best_move(board, stop_event=stop)
    elapsed = time.monotonic() - t0
    assert elapsed < 0.3
    assert move in board.legal_moves


def test_never_mutates_caller_board() -> None:
    board = chess.Board()
    fen_before = board.fen()
    engine = Engine(depth=2, level=None, log_to_file=False)
    engine.best_move(board)
    assert board.fen() == fen_before


def test_returns_none_move_on_finished_game() -> None:
    # Scholar's mate final position (White checkmated Black)
    board = chess.Board("r1bqkb1r/pppp1Qpp/2n5/4p3/2B1n3/8/PPPP1PPP/RNB1K1NR b KQkq - 0 4")
    assert board.is_checkmate()
    engine = Engine(depth=2, level=None, log_to_file=False)
    move, score, nodes = engine.best_move(board)
    assert move is None
    # Score is always from White's POV: White checkmated Black -> White winning (+10000)
    assert score >= 9000
    assert nodes == 0


def test_pv_extraction() -> None:
    board = chess.Board()
    engine = Engine(depth=2, level=None, log_to_file=False)
    engine.best_move(board)
    pv = engine.info.get("pv")
    assert isinstance(pv, list)
