"""
openboard.engines.types
~~~~~~~~~~~~~~~~~~~~~~~
Frozen dataclasses and helpers for engine search requests and results.
No I/O, no pygame, no process logic.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Backend = Literal["python", "stockfish"]
Purpose = Literal["play", "evaluate"]
EngineMode = Literal["auto", "custom", "stockfish"]

MATE_SCORE = 10_000
MATE_THRESHOLD = 9_000


@dataclass(frozen=True, slots=True)
class SearchRequest:
    """Immutable specification for a single engine search."""

    request_id: int
    fen: str
    purpose: Purpose
    depth: int | None = None
    time_s: float | None = None
    level: int | None = None
    auto: bool = False
    limit_strength: bool = True


@dataclass(frozen=True, slots=True)
class SearchResult:
    """Immutable result of a completed (or cancelled/failed) search."""

    request_id: int
    best_uci: str | None
    score_cp: int | None      # White's POV, None when mate is forced
    mate_in: int | None       # positive = White mates; None when no forced mate
    depth: int
    nodes: int
    seconds: float
    pv_uci: tuple[str, ...]
    backend: Backend
    reason: str
    book: bool = False
    cancelled: bool = False
    error: str | None = None


@dataclass(frozen=True, slots=True)
class PythonCalibration:
    """Timing calibration data for the Python engine."""

    seconds_by_depth: dict[int, float]
    growth: float
    nps: float


@dataclass(frozen=True, slots=True)
class Capabilities:
    """Snapshot of what the engine service can currently offer."""

    stockfish_available: bool
    stockfish_name: str | None
    elo_range: tuple[int, int] | None
    calibration: PythonCalibration | None
    smart_engine: bool
    use_book: bool
    cpu_count: int
    engine_mode: EngineMode = "auto"
    custom_max_depth: int = 4


# ---------------------------------------------------------------------------
# Score helpers
# ---------------------------------------------------------------------------

def pawns_to_cp(x: float) -> int:
    """Convert a score in pawn units to centipawns."""
    return int(round(x * 100))


def decode_python_score(score_pawns: float) -> tuple[int | None, int | None]:
    """Decode a raw engine score (in pawns) into (score_cp, mate_in).

    Returns:
        (score_cp, None)  for normal positions
        (None, mate_in)   when a forced mate is detected

    mate_in is positive when White mates, negative when Black mates.
    """
    if abs(score_pawns) >= MATE_THRESHOLD:
        mate_in = (MATE_SCORE - abs(int(score_pawns)) + 1) // 2
        if score_pawns < 0:
            mate_in = -mate_in
        return None, mate_in
    return pawns_to_cp(score_pawns), None
