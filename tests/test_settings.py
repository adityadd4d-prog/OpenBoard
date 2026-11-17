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
