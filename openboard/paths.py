"""
openboard.paths
~~~~~~~~~~~~~~~
Resolve runtime filesystem paths for both frozen (PyInstaller) and
development environments.  No pygame, no config — safe to import early.
"""

from __future__ import annotations

import sys
from pathlib import Path

import platformdirs

# ---------------------------------------------------------------------------
# Frozen / development detection
# ---------------------------------------------------------------------------


def is_frozen() -> bool:
    """Return True when running inside a PyInstaller bundle."""
    return bool(getattr(sys, "frozen", False))


def resource_path(rel: str) -> Path:
    """Return an absolute Path for *rel* relative to the project/bundle root.

    When frozen the root is ``sys._MEIPASS``; in development it is the
    directory that *contains* the ``openboard`` package (i.e. the repo root).
    """
    if is_frozen():
        base = Path(sys._MEIPASS)  # type: ignore[attr-defined]
    else:
        # __file__ is openboard/paths.py → parent is openboard/ → parent is root
        base = Path(__file__).parent.parent
    return base / rel


# ---------------------------------------------------------------------------
# User-writable directories (created on demand)
# ---------------------------------------------------------------------------


def user_data_dir() -> Path:
    """Return (and create) the platform-appropriate user data directory."""
    p = Path(platformdirs.user_data_dir("OpenBoard", appauthor=False))
    p.mkdir(parents=True, exist_ok=True)
    return p


def log_dir() -> Path:
    """Return (and create) the log directory inside the user data dir."""
    p = user_data_dir() / "logs"
    p.mkdir(parents=True, exist_ok=True)
    return p


# ---------------------------------------------------------------------------
# Asset directories (read-only, inside the bundle / repo)
# ---------------------------------------------------------------------------


def assets_dir() -> Path:
    """Return the path to the built assets directory."""
    return resource_path("assets/build")


def reference_dir() -> Path:
    """Return the path to the reference screenshot directory."""
    return resource_path("assets/reference")


# ---------------------------------------------------------------------------
# Stockfish binary candidates
# ---------------------------------------------------------------------------

_SF_OS_FOLDER: dict[str, str] = {
    "win32": "win",
    "linux": "linux",
    "linux2": "linux",
    "darwin": "mac",
}

_SF_PRIORITY_POSIX: list[str] = ["avx2", "", "sse41", "popcnt"]


def stockfish_candidates() -> list[Path]:
    """Return available Stockfish binaries ordered by preference.

    On Linux/macOS: avx2 variant first, then the plain binary, then sse41/popcnt.
    On Windows: same ordering but only files whose name ends with '.exe'.
    Returns an empty list if the folder is missing or empty; never raises.
    """
    try:
        platform_key = sys.platform
        os_folder = _SF_OS_FOLDER.get(platform_key)
        if os_folder is None:
            # Fallback: try linux
            os_folder = "linux"

        sf_dir = resource_path(f"bin/stockfish/{os_folder}")
        if not sf_dir.is_dir():
            return []

        is_windows = platform_key == "win32"
        candidates: list[Path] = [
            p for p in sf_dir.iterdir()
            if p.name.startswith("stockfish")
            and (p.name.endswith(".exe") if is_windows else True)
        ]

        def _priority(p: Path) -> int:
            name = p.name.lower()
            if "avx2" in name:
                return 0
            if name in ("stockfish", "stockfish.exe"):
                return 1
            if "sse41" in name or "popcnt" in name:
                return 2
            return 3

        candidates.sort(key=_priority)
        return candidates
    except Exception:
        return []
