"""
openboard.config
~~~~~~~~~~~~~~~~
Compile-time constants and frozen dataclasses for the OpenBoard application.
No I/O, no pygame imports — safe to import anywhere.
"""

from __future__ import annotations

from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Application metadata
# ---------------------------------------------------------------------------

APP_NAME: str = "OpenBoard"
APP_VERSION: str = "0.1.0"
GITHUB_URL: str = "https://github.com/openboard/openboard"
STOCKFISH_SOURCE_URL: str = "https://github.com/official-stockfish/Stockfish"

# ---------------------------------------------------------------------------
# Display / window
# ---------------------------------------------------------------------------

DESIGN_W: int = 1600
DESIGN_H: int = 900
MIN_WINDOW: tuple[int, int] = (960, 540)
FPS_OPTIONS: tuple[int, ...] = (30, 60, 90, 120)
DEFAULT_FPS: int = 60

# ---------------------------------------------------------------------------
# Board layout (all coords in design space)
# ---------------------------------------------------------------------------

BOARD_SQ: int = 88                          # square side length in pixels
BOARD_ORIGIN: tuple[int, int] = (120, 136)  # top-left corner of the board

EVAL_BOARD_SQ: int = 72
EVAL_BOARD_ORIGIN: tuple[int, int] = (48, 136)

# ---------------------------------------------------------------------------
# Time controls
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class TimeControl:
    """Immutable specification for a game time control."""

    key: str
    label: str
    minutes: int
    increment_s: int


BLITZ: TimeControl = TimeControl(key="blitz", label="BLITZ 3 + 2", minutes=3, increment_s=2)
RAPID: TimeControl = TimeControl(key="rapid", label="RAPID 10 + 0", minutes=10, increment_s=0)

TIME_CONTROLS: dict[str, TimeControl] = {
    BLITZ.key: BLITZ,
    RAPID.key: RAPID,
}

# ---------------------------------------------------------------------------
# Engine difficulty levels
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class LevelSpec:
    """Immutable specification for a single UI difficulty level."""

    ui_level: int
    caption: str
    python_level: int | None
    sf_elo: int | None
    sf_movetime_s: float | None
    sf_only: bool


LEVELS: dict[int, LevelSpec] = {
    1: LevelSpec(ui_level=1, caption="BEGINNER",     python_level=1, sf_elo=None, sf_movetime_s=None, sf_only=False),
    2: LevelSpec(ui_level=2, caption="NOVICE",       python_level=2, sf_elo=None, sf_movetime_s=None, sf_only=False),
    3: LevelSpec(ui_level=3, caption="INTERMEDIATE", python_level=3, sf_elo=None, sf_movetime_s=None, sf_only=False),
    4: LevelSpec(ui_level=4, caption="ADVANCED",     python_level=4, sf_elo=None, sf_movetime_s=None, sf_only=False),
    5: LevelSpec(ui_level=5, caption="STRONG",       python_level=5, sf_elo=1600, sf_movetime_s=0.3,  sf_only=False),
    6: LevelSpec(ui_level=6, caption="EXPERT",       python_level=None, sf_elo=1900, sf_movetime_s=0.5, sf_only=True),
    7: LevelSpec(ui_level=7, caption="MASTER",       python_level=None, sf_elo=2400, sf_movetime_s=0.8, sf_only=True),
    8: LevelSpec(ui_level=8, caption="STOCKFISH",    python_level=None, sf_elo=None, sf_movetime_s=1.0, sf_only=True),
}

# ---------------------------------------------------------------------------
# Engine routing thresholds
# ---------------------------------------------------------------------------

PY_EVAL_MAX_DEPTH: int = 4
PY_TIME_FIT_RATIO: float = 0.6
PY_MIN_USEFUL_DEPTH: int = 4

# Named tuples would be nicer but plain dicts keep the import minimal
AUTO_EVAL_SF: dict[str, float | int] = {"depth": 14, "time": 2.0}
AUTO_EVAL_PY: dict[str, float | int] = {"depth": 3,  "time": 2.0}

WATCHDOG_GRACE_S: float = 3.0
MIN_ENGINE_MOVE_DELAY_S: float = 0.4

# ---------------------------------------------------------------------------
# Evaluate panel bounds
# ---------------------------------------------------------------------------

EVAL_DEPTH_RANGE: tuple[int, int] = (1, 40)
EVAL_TIME_RANGE: tuple[float, float] = (0.1, 60.0)
EVAL_DEFAULT_DEPTH: int = 12

# Evaluation word thresholds (in pawns)
EVAL_EQUAL_MAX: float = 0.5
EVAL_SLIGHT_EDGE_MAX: float = 1.0
EVAL_CLEAR_ADVANTAGE_MAX: float = 3.0
# >= EVAL_CLEAR_ADVANTAGE_MAX -> "WINNING"

# ---------------------------------------------------------------------------
# Misc UI / data limits
# ---------------------------------------------------------------------------

NAME_MAX: int = 16
HISTORY_PAGE: int = 50
