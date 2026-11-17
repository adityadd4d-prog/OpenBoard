"""
openboard.core.clock
~~~~~~~~~~~~~~~~~~~~
Pure-Python chess clock — no pygame, no threads.
"""

from __future__ import annotations

import logging
import time as _time
from typing import Callable

import chess

log = logging.getLogger("openboard.core.clock")


def format_clock(seconds: float) -> str:
    """Format *seconds* as a clock string.

    * ``MM:SS`` for 20 seconds and above.
    * ``M:SS.t`` (tenths) below 20 seconds.
    * Never returns a negative string; clamps to ``0:00.0``.

    Args:
        seconds: Elapsed/remaining time in seconds (may be fractional).

    Returns:
        A human-readable clock string.
    """
    if seconds < 0.0:
        seconds = 0.0
    if seconds < 20.0:
        minutes = int(seconds) // 60
        secs = int(seconds) % 60
        tenths = int(seconds * 10) % 10
        return f"{minutes}:{secs:02d}.{tenths}"
    total_secs = int(seconds)
    minutes = total_secs // 60
    secs = total_secs % 60
    return f"{minutes:02d}:{secs:02d}"


class ChessClock:
    """Per-colour chess clock with configurable time source.

    The clock is *inactive* until :meth:`start` is called.  After that,
    :meth:`update` must be called regularly (e.g. from the game loop) so the
    running side's time decreases.

    Args:
        time_control: A :class:`~openboard.config.TimeControl` (or any object
            with ``minutes: int`` and ``increment_s: int`` attributes).
        now: A zero-argument callable that returns the current monotonic time
            in seconds.  Defaults to :func:`time.monotonic`.  Inject a fake
            for unit testing.
    """

    def __init__(
        self,
        time_control: object,
        now: Callable[[], float] = _time.monotonic,
    ) -> None:
        self._now = now
        self._increment: float = float(time_control.increment_s)  # type: ignore[attr-defined]
        base: float = float(time_control.minutes) * 60.0  # type: ignore[attr-defined]
        self._remaining: dict[chess.Color, float] = {
            chess.WHITE: base,
            chess.BLACK: base,
        }
        self._running: chess.Color | None = None  # None = not started / paused
        self._last_tick: float | None = None
        self._paused: bool = False
        self._started: bool = False

    # ------------------------------------------------------------------
    # Control
    # ------------------------------------------------------------------

    def start(self, first_to_move: chess.Color) -> None:
        """Begin the clock for *first_to_move*.

        Args:
            first_to_move: :data:`chess.WHITE` or :data:`chess.BLACK`.
        """
        self._running = first_to_move
        self._last_tick = self._now()
        self._paused = False
        self._started = True
        log.debug("Clock started for %s", "WHITE" if first_to_move == chess.WHITE else "BLACK")

    def update(self) -> None:
        """Deduct elapsed time from the running side.

        Call this every frame / game-loop tick.  Has no effect when the clock
        has not been started, is paused, or a side has flagged.
        """
        if self._running is None or self._last_tick is None:
            return
        now = self._now()
        elapsed = now - self._last_tick
        self._last_tick = now
        self._remaining[self._running] = max(
            0.0, self._remaining[self._running] - elapsed
        )

    def press(self, color: chess.Color) -> None:
        """Apply increment to *color* (the side that just moved) then switch.

        Args:
            color: The side whose move just ended.
        """
        if not self._started:
            return
        # Apply increment to the side that just moved.
        self._remaining[color] = self._remaining[color] + self._increment
        # Switch running side.
        self._running = not color  # type: ignore[assignment]
        self._last_tick = self._now()
        log.debug(
            "Clock pressed by %s — switching to %s",
            "WHITE" if color == chess.WHITE else "BLACK",
            "WHITE" if self._running == chess.WHITE else "BLACK",
        )

    def pause(self) -> None:
        """Freeze the clock (no time deducted while paused)."""
        if self._paused or self._running is None:
            return
        # Drain any elapsed time before pausing.
        self.update()
        self._running = None
        self._paused = True
        log.debug("Clock paused")

    def resume(self) -> None:
        """Resume the clock on the side it was paused for.

        Does nothing if the clock was never paused.
        """
        if not self._paused:
            return
        # We stored None in _running when pausing; restore from _paused_side.
        self._running = self._paused_side  # type: ignore[attr-defined]
        self._last_tick = self._now()
        self._paused = False
        log.debug("Clock resumed")

    # Override pause to also store the paused side:
    # (we need a small trick — keep paused_side separately)
    def pause(self) -> None:  # noqa: F811  # type: ignore[no-redef]
        """Freeze the clock (no time deducted while paused)."""
        if self._paused or self._running is None:
            return
        self.update()
        self._paused_side: chess.Color = self._running
        self._running = None
        self._paused = True
        log.debug("Clock paused (side=%s)", "WHITE" if self._paused_side == chess.WHITE else "BLACK")

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def remaining(self, color: chess.Color) -> float:
        """Return the remaining time for *color* in seconds (clamped at 0.0).

        Args:
            color: :data:`chess.WHITE` or :data:`chess.BLACK`.

        Returns:
            Remaining seconds ≥ 0.0.
        """
        return max(0.0, self._remaining[color])

    def flagged(self) -> chess.Color | None:
        """Return the color whose clock has reached zero, or ``None``.

        Returns:
            :data:`chess.WHITE`, :data:`chess.BLACK`, or ``None``.
        """
        for color in (chess.WHITE, chess.BLACK):
            if self._remaining[color] <= 0.0:
                return color
        return None
