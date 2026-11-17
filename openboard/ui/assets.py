"""
openboard.ui.assets
~~~~~~~~~~~~~~~~~~~~
Asset loading and caching for OpenBoard.

Assets are described in ``assets/build/index.json``.  Every public method
returns a usable object (placeholder surface / None) rather than raising on
missing files so the game degrades gracefully when the asset-build step has
not been run.
"""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Callable

import chess
import pygame

log = logging.getLogger("openboard.ui.assets")

# ---------------------------------------------------------------------------
# Piece name helpers
# ---------------------------------------------------------------------------

_COLOR_PREFIX: dict[bool, str] = {chess.WHITE: "w", chess.BLACK: "b"}

_PIECE_SUFFIX: dict[int, str] = {
    chess.KING:   "K",
    chess.QUEEN:  "Q",
    chess.ROOK:   "R",
    chess.BISHOP: "B",
    chess.KNIGHT: "N",
    chess.PAWN:   "P",
}


def _piece_name(color: chess.Color, piece_type: int) -> str:
    """Return the logical asset name for a chess piece, e.g. ``"piece_wK"``."""
    return f"piece_{_COLOR_PREFIX[color]}{_PIECE_SUFFIX[piece_type]}"


# ---------------------------------------------------------------------------
# Magenta placeholder
# ---------------------------------------------------------------------------

def _placeholder(w: int = 88, h: int = 88) -> pygame.Surface:
    """Return a magenta surface used when an asset is missing."""
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    surf.fill((255, 0, 255))
    return surf


# ---------------------------------------------------------------------------
# AssetStore
# ---------------------------------------------------------------------------


class AssetStore:
    """Loads and caches game assets from ``assets/build/index.json``.

    Call :meth:`preload` once after ``pygame.init()`` to warm the cache.
    All other methods are safe to call lazily — they will load on first use.
    """

    def __init__(self) -> None:
        self._root: Path = self._find_root()
        self._index: dict[str, dict] = self._load_index()
        self._image_cache: dict[str, pygame.Surface] = {}
        self._sound_cache: dict[str, pygame.mixer.Sound | None] = {}
        self._warned: set[str] = set()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _find_root() -> Path:
        """Return the ``assets/build`` directory, relative to the package."""
        here = Path(__file__).resolve().parent.parent.parent
        return here / "assets" / "build"

    def _load_index(self) -> dict[str, dict]:
        idx_path = self._root / "index.json"
        if not idx_path.exists():
            log.warning("Asset index not found at %s — running without assets.", idx_path)
            return {}
        try:
            with idx_path.open() as fh:
                return json.load(fh)
        except Exception as exc:
            log.error("Failed to parse asset index: %s", exc)
            return {}

    def _warn_once(self, name: str, detail: str = "") -> None:
        if name not in self._warned:
            log.warning("Asset '%s' not found%s.", name, f": {detail}" if detail else "")
            self._warned.add(name)

    def _load_image(self, name: str, alpha: bool = True) -> pygame.Surface:
        """Load a surface from the index, returning a placeholder on failure."""
        if name in self._image_cache:
            return self._image_cache[name]

        entry = self._index.get(name)
        if entry is None:
            self._warn_once(name, "not in index")
            surf = _placeholder()
            self._image_cache[name] = surf
            return surf

        path = self._root / entry["path"]
        if not path.exists():
            self._warn_once(name, f"file missing: {path}")
            w, h = entry.get("size", [88, 88])
            surf = _placeholder(w, h)
            self._image_cache[name] = surf
            return surf

        try:
            if alpha:
                surf = pygame.image.load(str(path)).convert_alpha()
            else:
                surf = pygame.image.load(str(path)).convert()
        except Exception as exc:
            self._warn_once(name, str(exc))
            surf = _placeholder()

        self._image_cache[name] = surf
        return surf

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def image(self, name: str) -> pygame.Surface:
        """Load and cache an image by logical name.

        Returns a magenta placeholder surface when the asset is missing.
        """
        return self._load_image(name, alpha=True)

    def piece(self, color: chess.Color, piece_type: int, size: int = 88) -> pygame.Surface:
        """Load a chess piece surface.

        *color* is ``chess.WHITE`` or ``chess.BLACK``.
        *piece_type* is one of the ``chess.KING`` … ``chess.PAWN`` constants.
        *size* is the desired pixel size; a smooth-scaled copy is returned when
        the indexed size differs.
        """
        name = _piece_name(color, piece_type)
        # Cache key includes size
        cache_key = f"{name}@{size}"
        if cache_key in self._image_cache:
            return self._image_cache[cache_key]

        base = self._load_image(name, alpha=True)
        if base.get_width() != size or base.get_height() != size:
            scaled = pygame.transform.smoothscale(base, (size, size))
        else:
            scaled = base
        self._image_cache[cache_key] = scaled
        return scaled

    def background(self, name: str) -> pygame.Surface:
        """Load a background image (no alpha channel) by logical name."""
        # Store converted separately
        bg_key = f"bg:{name}"
        if bg_key in self._image_cache:
            return self._image_cache[bg_key]

        surf = self._load_image(name, alpha=False)
        self._image_cache[bg_key] = surf
        return surf

    def sound(self, name: str) -> "pygame.mixer.Sound | None":
        """Load a sound by logical name.

        Returns ``None`` when the mixer is unavailable or the file is missing.
        """
        if name in self._sound_cache:
            return self._sound_cache[name]

        result: pygame.mixer.Sound | None = None
        try:
            if not pygame.mixer.get_init():
                result = None
            else:
                entry = self._index.get(name)
                if entry is None:
                    self._warn_once(name, "not in index")
                else:
                    path = self._root / entry["path"]
                    if path.exists():
                        result = pygame.mixer.Sound(str(path))
                    else:
                        self._warn_once(name, f"file missing: {path}")
        except Exception as exc:
            self._warn_once(name, str(exc))

        self._sound_cache[name] = result
        return result

    def tile(self, name: str, target_rect: pygame.Rect) -> pygame.Surface:
        """Create a tiled surface of *name* sized to *target_rect*."""
        src = self._load_image(name, alpha=True)
        sw, sh = src.get_size()
        out = pygame.Surface((target_rect.width, target_rect.height), pygame.SRCALPHA)
        for y in range(0, target_rect.height, sh):
            for x in range(0, target_rect.width, sw):
                out.blit(src, (x, y))
        return out

    def preload(self, on_progress: Callable[[str, int, int], None] | None = None) -> None:
        """Preload all indexed assets into the cache.

        *on_progress(name, done, total)* is called after each asset load if
        provided.
        """
        names = list(self._index.keys())
        total = len(names)
        for i, name in enumerate(names, 1):
            entry = self._index[name]
            path_str = entry.get("path", "")
            is_sound = Path(path_str).suffix.lower() in (".wav", ".ogg", ".mp3")
            if is_sound:
                self.sound(name)
            else:
                self._load_image(name, alpha=True)
            if on_progress:
                on_progress(name, i, total)


# ---------------------------------------------------------------------------
# Demo entry-point
# ---------------------------------------------------------------------------


def _demo() -> None:  # pragma: no cover
    """List every asset with its size and load time."""
    import sys
    pygame.init()
    store = AssetStore()

    print(f"Asset root: {store._root}")
    print(f"Index entries: {len(store._index)}")
    print()

    for name, entry in store._index.items():
        t0 = time.perf_counter()
        is_sound = Path(entry.get("path", "")).suffix.lower() in (".wav", ".ogg", ".mp3")
        if is_sound:
            obj = store.sound(name)
            info = "sound" if obj else "sound (failed)"
        else:
            surf = store.image(name)
            info = f"{surf.get_width()}×{surf.get_height()}px"
        elapsed = (time.perf_counter() - t0) * 1000
        print(f"  {name:30s}  {info:20s}  {elapsed:.2f}ms")

    pygame.quit()


if __name__ == "__main__":
    _demo()
