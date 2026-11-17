"""tests/test_profile.py — ProfileStore unit tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from openboard.storage.profile import PlayerProfile, ProfileStore


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _store(tmp_path: Path, filename: str = "profile.json") -> ProfileStore:
    return ProfileStore(tmp_path / filename)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_load_or_create_new_path(tmp_path: Path) -> None:
    store = _store(tmp_path)
    profile = store.load()

    assert isinstance(profile, PlayerProfile)
    assert profile.id  # non-empty hex uuid
    assert len(profile.id) == 32  # uuid4 hex length


def test_rename_empty_string_raises(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.load()

    with pytest.raises(ValueError, match="empty"):
        store.rename("")


def test_rename_whitespace_only_raises(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.load()

    with pytest.raises(ValueError):
        store.rename("   ")


def test_rename_too_long_raises(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.load()

    with pytest.raises(ValueError, match="long"):
        store.rename("A" * 17)  # 17 > NAME_MAX(16)


def test_rename_control_char_raises(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.load()

    with pytest.raises(ValueError, match="control"):
        store.rename("bad\x01name")


def test_rename_emoji_allowed(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.load()

    # Should not raise
    store.rename("🏆 Champion")
    assert store.profile is not None
    assert store.profile.name == "🏆 Champion"


def test_persistence_across_reload(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.load()
    store.rename("Magnus")
    store.set_time_control("blitz")

    store2 = _store(tmp_path)
    profile = store2.load()

    assert profile.name == "Magnus"
    assert profile.preferred_time_control == "blitz"
