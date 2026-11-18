"""tests/test_settings.py — SettingsStore unit tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from openboard import config
from openboard.storage.settings import Settings, SettingsStore


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _store(tmp_path: Path, filename: str = "settings.json") -> SettingsStore:
    return SettingsStore(tmp_path / filename)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_corrupt_json_creates_bak_and_uses_defaults(tmp_path: Path) -> None:
    p = tmp_path / "settings.json"
    p.write_text("{ not valid json !!!", encoding="utf-8")

    store = _store(tmp_path)
    store.load()

    bak = tmp_path / "settings.json.bak"
    assert bak.exists(), ".bak file should be created on corrupt JSON"
    # Defaults used
    assert store.fps == config.DEFAULT_FPS
    assert store.audio is True


def test_partial_json_uses_defaults_for_missing_keys(tmp_path: Path) -> None:
    p = tmp_path / "settings.json"
    p.write_text(json.dumps({"schema_version": 1, "fps": 30}), encoding="utf-8")

    store = _store(tmp_path)
    store.load()

    assert store.fps == 30
    assert store.audio is True          # default
    assert store.fullscreen is False    # default


def test_fps_clamping_invalid_fps(tmp_path: Path) -> None:
    p = tmp_path / "settings.json"
    p.write_text(json.dumps({"fps": 999}), encoding="utf-8")

    store = _store(tmp_path)
    store.load()

    # 999 nearest is 120
    assert store.fps in config.FPS_OPTIONS


def test_atomic_save_round_trip(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.load()
    store.set(audio=False, fps=30, last_time_control="blitz")

    store2 = _store(tmp_path)
    store2.load()

    assert store2.audio is False
    assert store2.fps == 30
    assert store2.last_time_control == "blitz"


def test_listener_notified_on_set(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.load()

    received: list[Settings] = []
    store.subscribe(received.append)

    store.set(audio=False)
    assert len(received) == 1
    assert received[0].audio is False


def test_unknown_keys_ignored_on_load(tmp_path: Path) -> None:
    p = tmp_path / "settings.json"
    p.write_text(
        json.dumps({"fps": 60, "mystery_key": "should_be_ignored", "audio": False}),
        encoding="utf-8",
    )

    store = _store(tmp_path)
    store.load()  # must not raise

    assert store.audio is False
    assert store.fps == 60


def test_engine_mode_persistence_and_legacy_migration(tmp_path: Path) -> None:
    # Legacy JSON with only smart_engine=False migrates to engine_mode='custom'
    p = tmp_path / "settings.json"
    p.write_text(json.dumps({"smart_engine": False}), encoding="utf-8")
    store = _store(tmp_path)
    assert store.engine_mode == "custom"
    assert store.smart_engine is False

    # Switching to stockfish persists and syncs smart_engine=True
    store.set(engine_mode="stockfish")
    store2 = _store(tmp_path)
    assert store2.engine_mode == "stockfish"
    assert store2.smart_engine is True

    # Invalid mode falls back safely to 'auto'
    store2.set(engine_mode="invalid_value")
    assert store2.engine_mode == "auto"

    # custom_max_depth persists and clamps to valid bounds
    store2.set(custom_max_depth=6)
    store3 = _store(tmp_path)
    assert store3.custom_max_depth == 6
    store3.set(custom_max_depth=99)
    assert store3.custom_max_depth == max(config.CUSTOM_MAX_DEPTH_OPTIONS)
    store3.set(custom_max_depth=0)
    assert store3.custom_max_depth == min(config.CUSTOM_MAX_DEPTH_OPTIONS)
