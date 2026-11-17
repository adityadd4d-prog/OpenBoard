"""
tests/test_context.py
~~~~~~~~~~~~~~~~~~~~~
Tests for openboard.context in headless mode.
"""

from pathlib import Path
import pytest

from openboard import paths
from openboard.context import build_context


def test_build_context_headless_and_double_shutdown(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(paths, "user_data_dir", lambda: tmp_path)
    monkeypatch.setattr(paths, "log_dir", lambda: tmp_path / "logs")

    ctx = build_context(headless=True)
    assert ctx.settings is not None
    assert ctx.profile is not None
    assert ctx.history is not None
    assert ctx.engines is not None
    assert ctx.display is None

    # Sound play in headless is a no-op and never raises
    ctx.sfx("move")

    # Idempotent shutdown
    ctx.shutdown()
    ctx.shutdown()
