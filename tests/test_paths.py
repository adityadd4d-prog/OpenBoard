"""
tests/test_paths.py
~~~~~~~~~~~~~~~~~~~
Tests for openboard.paths — exercises both frozen and dev-mode behaviour.
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

import openboard.paths as paths


# ---------------------------------------------------------------------------
# is_frozen / resource_path
# ---------------------------------------------------------------------------


class TestIsFrozen:
    def test_not_frozen_in_dev(self) -> None:
        """In the test environment sys.frozen is not set."""
        assert paths.is_frozen() is False

    def test_frozen_when_attribute_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        assert paths.is_frozen() is True

    def test_not_frozen_when_attribute_false(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(sys, "frozen", False, raising=False)
        assert paths.is_frozen() is False


class TestResourcePath:
    def test_dev_root_contains_openboard_package(self) -> None:
        """In dev mode resource_path('.') is the repo root (contains openboard/)."""
        root = paths.resource_path(".")
        assert (root / "openboard").is_dir()

    def test_frozen_uses_meipass(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """When frozen, resource_path should use sys._MEIPASS as the base."""
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
        result = paths.resource_path("some/file.txt")
        assert result == tmp_path / "some" / "file.txt"


# ---------------------------------------------------------------------------
# stockfish_candidates ordering
# ---------------------------------------------------------------------------


class TestStockfishCandidates:
    def _make_sf_dir(self, tmp_path: Path, names: list[str]) -> Path:
        """Create a fake bin/stockfish/linux/ directory with the given file names."""
        sf_dir = tmp_path / "bin" / "stockfish" / "linux"
        sf_dir.mkdir(parents=True)
        for name in names:
            (sf_dir / name).touch()
        return tmp_path

    def test_avx2_first_on_linux(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """On Linux, the avx2 variant must come before plain and sse41."""
        self._make_sf_dir(
            tmp_path,
            ["stockfish-sse41-popcnt", "stockfish", "stockfish-avx2"],
        )

        # Patch resource_path to point at tmp_path
        monkeypatch.setattr(sys, "frozen", False, raising=False)
        monkeypatch.setattr(sys, "platform", "linux")
        monkeypatch.setattr(
            paths,
            "resource_path",
            lambda rel: tmp_path / rel,
        )

        result = paths.stockfish_candidates()
        assert len(result) == 3
        assert result[0].name == "stockfish-avx2"
        assert result[1].name == "stockfish"
        assert result[2].name == "stockfish-sse41-popcnt"

    def test_empty_dir_returns_empty_list(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """An empty stockfish folder must return []."""
        sf_dir = tmp_path / "bin" / "stockfish" / "linux"
        sf_dir.mkdir(parents=True)

        monkeypatch.setattr(sys, "platform", "linux")
        monkeypatch.setattr(paths, "resource_path", lambda rel: tmp_path / rel)

        assert paths.stockfish_candidates() == []

    def test_missing_dir_returns_empty_list(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """A missing stockfish folder must return [] without raising."""
        monkeypatch.setattr(sys, "platform", "linux")
        monkeypatch.setattr(paths, "resource_path", lambda rel: tmp_path / rel)

        result = paths.stockfish_candidates()
        assert result == []

    def test_windows_requires_exe(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """On Windows only .exe files should be returned."""
        sf_dir = tmp_path / "bin" / "stockfish" / "win"
        sf_dir.mkdir(parents=True)
        (sf_dir / "stockfish.exe").touch()
        (sf_dir / "stockfish").touch()       # no extension — should be excluded

        monkeypatch.setattr(sys, "platform", "win32")
        monkeypatch.setattr(paths, "resource_path", lambda rel: tmp_path / rel)

        result = paths.stockfish_candidates()
        assert all(p.name.endswith(".exe") for p in result)
        assert len(result) == 1
