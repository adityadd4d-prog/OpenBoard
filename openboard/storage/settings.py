"""
openboard.storage.settings
~~~~~~~~~~~~~~~~~~~~~~~~~~
Persistent application settings stored in JSON.
No pygame, no engine imports.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable

from openboard import config

log = logging.getLogger("openboard.storage.settings")


@dataclass(slots=True)
class Settings:
    """All user-configurable settings with safe defaults."""

    schema_version: int = 1
    audio: bool = True
    use_book: bool = True
    smart_engine: bool = True
    fps: int = config.DEFAULT_FPS
    fullscreen: bool = False
    window_size: tuple[int, int] = (1280, 720)
    last_time_control: str = "rapid"
    python_calibration: dict | None = None
    calibration_key: str | None = None


def _clamp_fps(fps: int) -> int:
    """Return the nearest valid fps from FPS_OPTIONS, defaulting to DEFAULT_FPS."""
    if fps in config.FPS_OPTIONS:
        return fps
    # pick nearest
    return min(config.FPS_OPTIONS, key=lambda v: abs(v - fps))


class SettingsStore:
    """Loads, saves, and distributes application settings."""

    _KNOWN_KEYS = set(Settings.__dataclass_fields__)  # type: ignore[attr-defined]

    def __init__(self, path: Path) -> None:
        self._path = path
        self._settings: Settings = Settings()
        self._listeners: list[Callable[[Settings], None]] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load(self) -> None:
        """Load settings from disk.

        On corrupt JSON: rename to .bak and use defaults.
        Unknown keys are ignored; missing keys use defaults.
        fps is clamped to the nearest FPS_OPTIONS value.
        """
        defaults = Settings()
        if not self._path.exists():
            self._settings = defaults
            return

        try:
            raw = self._path.read_text(encoding="utf-8")
            data: dict = json.loads(raw)
        except (json.JSONDecodeError, OSError) as exc:
            log.warning("Corrupt settings file (%s); backing up and using defaults.", exc)
            bak = self._path.with_suffix(".json.bak")
            try:
                self._path.rename(bak)
            except OSError:
                pass
            self._settings = defaults
            return

        # Build kwargs: known keys only, fill missing with defaults
        kwargs: dict = {}
        for key in self._KNOWN_KEYS:
            if key in data:
                kwargs[key] = data[key]
            else:
                kwargs[key] = getattr(defaults, key)

        # window_size may be a list from JSON
        if "window_size" in kwargs and isinstance(kwargs["window_size"], list):
            kwargs["window_size"] = tuple(kwargs["window_size"])

        # Clamp fps
        if "fps" in kwargs:
            kwargs["fps"] = _clamp_fps(kwargs["fps"])

        self._settings = Settings(**kwargs)

    def save(self) -> None:
        """Atomically write settings to disk (write temp then os.replace)."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".json.tmp")
        data = asdict(self._settings)
        # tuple[int,int] becomes a list via asdict — that is fine for JSON
        tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        os.replace(tmp, self._path)

    def set(self, **changes) -> None:
        """Apply validated changes, persist, and notify subscribers."""
        for key, value in changes.items():
            if key not in self._KNOWN_KEYS:
                raise ValueError(f"Unknown setting: {key!r}")
            if key == "fps":
                value = _clamp_fps(value)
            setattr(self._settings, key, value)
        self.save()
        for cb in self._listeners:
            cb(self._settings)

    def subscribe(self, callback: Callable[[Settings], None]) -> None:
        """Register a callback invoked after every set()."""
        self._listeners.append(callback)

    # ------------------------------------------------------------------
    # Properties (read-only views of the current settings)
    # ------------------------------------------------------------------

    @property
    def schema_version(self) -> int:
        return self._settings.schema_version

    @property
    def audio(self) -> bool:
        return self._settings.audio

    @property
    def use_book(self) -> bool:
        return self._settings.use_book

    @property
    def smart_engine(self) -> bool:
        return self._settings.smart_engine

    @property
    def fps(self) -> int:
        return self._settings.fps

    @property
    def fullscreen(self) -> bool:
        return self._settings.fullscreen

    @property
    def window_size(self) -> tuple[int, int]:
        return self._settings.window_size

    @property
    def last_time_control(self) -> str:
        return self._settings.last_time_control

    @property
    def python_calibration(self) -> dict | None:
        return self._settings.python_calibration

    @property
    def calibration_key(self) -> str | None:
        return self._settings.calibration_key

    @property
    def current(self) -> Settings:
        """Return the live Settings dataclass instance."""
        return self._settings
