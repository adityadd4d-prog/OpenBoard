"""
tests.test_clock
~~~~~~~~~~~~~~~~
Unit tests for openboard.core.clock — ChessClock and format_clock.
"""

from __future__ import annotations

import pytest
import chess

from openboard.core.clock import ChessClock, format_clock
from openboard.config import TimeControl


# ---------------------------------------------------------------------------
# format_clock
# ---------------------------------------------------------------------------


class TestFormatClock:
    """Edge-case tests for format_clock."""

    def test_zero(self) -> None:
        assert format_clock(0.0) == "0:00.0"

    def test_just_below_20(self) -> None:
        # 19.9 seconds: show tenths
        result = format_clock(19.9)
        assert result == "0:19.9"

    def test_exactly_20(self) -> None:
        # At 20 seconds we switch to MM:SS
        result = format_clock(20.0)
        assert result == "00:20"

    def test_one_minute(self) -> None:
        assert format_clock(60.0) == "01:00"

    def test_599_9(self) -> None:
        # 9 minutes 59.9 seconds
        result = format_clock(599.9)
        assert result == "09:59"

    def test_600(self) -> None:
        assert format_clock(600.0) == "10:00"

    def test_negative_clamped(self) -> None:
        assert format_clock(-5.0) == "0:00.0"

    def test_tenths_digit(self) -> None:
        # 5.3 seconds
        result = format_clock(5.3)
        assert result == "0:05.3"


# ---------------------------------------------------------------------------
# ChessClock helpers
# ---------------------------------------------------------------------------


def _make_clock(minutes: int = 5, increment_s: int = 0, start: float = 0.0):
    """Return (clock, time_ref) where time_ref[0] is the fake current time."""
    tc = TimeControl(key="test", label="Test", minutes=minutes, increment_s=increment_s)
    t = [start]
    clock = ChessClock(tc, now=lambda: t[0])
    return clock, t


# ---------------------------------------------------------------------------
# ChessClock tests
# ---------------------------------------------------------------------------


class TestChessClock:
    """Behavioural tests for ChessClock."""

    def test_initial_remaining(self) -> None:
        clock, _ = _make_clock(minutes=3)
        clock.start(chess.WHITE)
        assert clock.remaining(chess.WHITE) == pytest.approx(180.0)
        assert clock.remaining(chess.BLACK) == pytest.approx(180.0)

    def test_time_drains_for_running_side(self) -> None:
        clock, t = _make_clock(minutes=5)
        clock.start(chess.WHITE)
        t[0] = 10.0  # 10 seconds have passed
        clock.update()
        assert clock.remaining(chess.WHITE) == pytest.approx(300.0 - 10.0)
        assert clock.remaining(chess.BLACK) == pytest.approx(300.0)

    def test_side_switches_after_press(self) -> None:
        clock, t = _make_clock(minutes=5)
        clock.start(chess.WHITE)
        t[0] = 5.0
        clock.update()
        clock.press(chess.WHITE)  # White pressed → Black's turn now
        # Black's time should not have decreased yet
        assert clock.remaining(chess.BLACK) == pytest.approx(300.0)
        # Advance time, update — only Black should drain now
        t[0] = 10.0
        clock.update()
        assert clock.remaining(chess.BLACK) == pytest.approx(300.0 - 5.0)
        assert clock.remaining(chess.WHITE) == pytest.approx(300.0 - 5.0)  # already drained 5s

    def test_increment_applied_after_press(self) -> None:
        clock, t = _make_clock(minutes=1, increment_s=10)
        clock.start(chess.WHITE)
        t[0] = 15.0
        clock.update()
        # White spent 15s, then presses → +10s increment
        clock.press(chess.WHITE)
        expected = 60.0 - 15.0 + 10.0
        assert clock.remaining(chess.WHITE) == pytest.approx(expected)

    def test_pause_stops_counting(self) -> None:
        clock, t = _make_clock(minutes=2)
        clock.start(chess.WHITE)
        t[0] = 10.0
        clock.update()
        clock.pause()
        # Advance time — should not count
        t[0] = 60.0
        clock.update()  # update while paused — should be no-op
        assert clock.remaining(chess.WHITE) == pytest.approx(120.0 - 10.0)

    def test_resume_continues_counting(self) -> None:
        clock, t = _make_clock(minutes=2)
        clock.start(chess.WHITE)
        t[0] = 10.0
        clock.update()
        clock.pause()
        t[0] = 60.0  # paused period
        clock.resume()
        t[0] = 65.0  # 5 more seconds after resume
        clock.update()
        # Should have counted 10s before pause + 5s after resume = 15s total
        assert clock.remaining(chess.WHITE) == pytest.approx(120.0 - 15.0)

    def test_flagged_returns_none_while_time_remains(self) -> None:
        clock, _ = _make_clock(minutes=1)
        clock.start(chess.WHITE)
        assert clock.flagged() is None

    def test_flagged_returns_color_when_timeout(self) -> None:
        clock, t = _make_clock(minutes=1)
        clock.start(chess.WHITE)
        t[0] = 61.0  # 61 seconds elapsed
        clock.update()
        assert clock.flagged() == chess.WHITE

    def test_flagged_clamps_remaining_at_zero(self) -> None:
        clock, t = _make_clock(minutes=1)
        clock.start(chess.WHITE)
        t[0] = 100.0
        clock.update()
        assert clock.remaining(chess.WHITE) == pytest.approx(0.0)

    def test_black_flags(self) -> None:
        clock, t = _make_clock(minutes=1)
        clock.start(chess.WHITE)
        t[0] = 1.0
        clock.update()
        clock.press(chess.WHITE)  # switch to Black
        t[0] = 65.0
        clock.update()
        assert clock.flagged() == chess.BLACK

    def test_no_increment_without_press(self) -> None:
        clock, t = _make_clock(minutes=1, increment_s=5)
        clock.start(chess.WHITE)
        t[0] = 10.0
        clock.update()
        # No press → no increment
        assert clock.remaining(chess.WHITE) == pytest.approx(60.0 - 10.0)
