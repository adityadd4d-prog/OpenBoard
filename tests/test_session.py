"""
tests/test_session.py
~~~~~~~~~~~~~~~~~~~~~
Tests for GameSession pure logic in openboard.core.session.
"""

import chess
import pytest

from openboard.config import TIME_CONTROLS
from openboard.core.results import Reason
from openboard.core.session import GameSession, PlayerInfo, SessionEvent


class FakeTime:
    def __init__(self, current: float = 1000.0) -> None:
        self.time = current

    def now(self) -> float:
        return self.time

    def advance(self, seconds: float) -> None:
        self.time += seconds


def test_scholars_mate() -> None:
    p_white = PlayerInfo(name="WhitePlayer", kind="human")
    p_black = PlayerInfo(name="BlackPlayer", kind="human")
    session = GameSession(p_white, p_black, TIME_CONTROLS["rapid"])

    # 1. e4 e5
    r = session.try_move(chess.E2, chess.E4)
    assert r.ok and r.san == "e4"
    r = session.try_move(chess.E7, chess.E5)
    assert r.ok and r.san == "e5"

    # 2. Qh5 Nc6
    r = session.try_move(chess.D1, chess.H5)
    assert r.ok and r.san == "Qh5"
    r = session.try_move(chess.B8, chess.C6)
    assert r.ok and r.san == "Nc6"

    # 3. Bc4 Nf6
    r = session.try_move(chess.F1, chess.C4)
    assert r.ok and r.san == "Bc4"
    r = session.try_move(chess.G8, chess.F6)
    assert r.ok and r.san == "Nf6"

    # 4. Qxf7#
    r = session.try_move(chess.H5, chess.F7)
    assert r.ok and r.san == "Qxf7#"
    assert SessionEvent.CHECK in r.events
    assert SessionEvent.CAPTURE in r.events
    assert SessionEvent.GAME_OVER in r.events

    assert session.is_over
    assert session.outcome is not None
    assert session.outcome.winner == chess.WHITE
    assert session.outcome.reason == Reason.CHECKMATE
    assert len(session.move_rows) == 4


def test_stalemate() -> None:
    # Setup position 1 move away from stalemate
    # White: Ka6, Qc6. Black: Ka8. White plays Qc7 -> Stalemate!
    fen = "k7/8/K1Q5/8/8/8/8/8 w - - 0 1"
    p_white = PlayerInfo(name="W", kind="human")
    p_black = PlayerInfo(name="B", kind="human")
    session = GameSession(p_white, p_black, TIME_CONTROLS["blitz"], start_fen=fen)

    r = session.try_move(chess.C6, chess.C7)
    assert r.ok
    assert session.is_over
    assert session.outcome is not None
    assert session.outcome.winner is None
    assert session.outcome.reason == Reason.STALEMATE


def test_timeout_with_fake_clock() -> None:
    fake_time = FakeTime(100.0)
    p_white = PlayerInfo(name="W", kind="human")
    p_black = PlayerInfo(name="B", kind="human")
    # Blitz 3+2 (180s)
    session = GameSession(p_white, p_black, TIME_CONTROLS["blitz"], now=fake_time.now)

    assert not session.is_over
    # White is to move. Advance time by 200 seconds -> White flags!
    fake_time.advance(200.0)
    session.update()

    assert session.is_over
    assert session.outcome is not None
    assert session.outcome.winner == chess.BLACK
    assert session.outcome.reason == Reason.TIMEOUT


def test_promotion() -> None:
    # White pawn on a7
    fen = "8/P7/8/8/8/8/8/4K2k w - - 0 1"
    p_white = PlayerInfo(name="W", kind="human")
    p_black = PlayerInfo(name="B", kind="human")
    session = GameSession(p_white, p_black, TIME_CONTROLS["rapid"], start_fen=fen)

    assert session.needs_promotion(chess.A7, chess.A8)
    r = session.try_move(chess.A7, chess.A8, promotion=chess.QUEEN)
    assert r.ok
    assert r.san == "a8=Q+"
    assert SessionEvent.PROMOTION in r.events


def test_resignation() -> None:
    p_white = PlayerInfo(name="W", kind="human")
    p_black = PlayerInfo(name="B", kind="human")
    session = GameSession(p_white, p_black, TIME_CONTROLS["rapid"])

    session.resign(chess.WHITE)
    assert session.is_over
    assert session.outcome is not None
    assert session.outcome.winner == chess.BLACK
    assert session.outcome.reason == Reason.RESIGNATION


def test_to_record() -> None:
    p_white = PlayerInfo(name="W", kind="human")
    p_black = PlayerInfo(name="B", kind="human")
    session = GameSession(p_white, p_black, TIME_CONTROLS["rapid"])
    session.resign(chess.BLACK)

    rec = session.to_record(player1_color=chess.WHITE)
    assert rec["winner"] == "white"
    assert rec["result"] == "1-0"
    assert rec["reason"] == Reason.RESIGNATION.value


def test_draw_offer_and_accept() -> None:
    p_white = PlayerInfo(name="W", kind="human")
    p_black = PlayerInfo(name="B", kind="human")
    session = GameSession(p_white, p_black, TIME_CONTROLS["rapid"])

    # Draw offer
    session.offer_draw(chess.WHITE)
    assert session.draw_offered_by == chess.WHITE

    # Decline
    session.decline_draw()
    assert session.draw_offered_by is None
    assert not session.is_over

    # Re-offer and accept
    session.offer_draw(chess.BLACK)
    assert session.draw_offered_by == chess.BLACK
    session.accept_draw()
    assert session.is_over
    assert session.outcome is not None
    assert session.outcome.winner is None
    assert session.outcome.reason == Reason.DRAW_AGREED

    rec = session.to_record(player1_color=chess.WHITE)
    assert rec["winner"] is None
    assert rec["result"] == "1/2-1/2"
    assert rec["reason"] == Reason.DRAW_AGREED.value


def test_last_move() -> None:
    p_white = PlayerInfo(name="W", kind="human")
    p_black = PlayerInfo(name="B", kind="human")
    session = GameSession(p_white, p_black, TIME_CONTROLS["rapid"])

    assert session.last_move is None
    session.try_move(chess.E2, chess.E4)
    assert session.last_move == chess.Move.from_uci("e2e4")
    session.try_move(chess.E7, chess.E5)
    assert session.last_move == chess.Move.from_uci("e7e5")
    assert session.check_square is None
