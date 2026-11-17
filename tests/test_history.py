"""tests/test_history.py — HistoryStore unit tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from openboard.storage.history import HistoryStore, Stats


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_record(
    result: str = "won",
    mode: str = "vs_engine",
    started_at: str = "2024-01-01T00:00:00Z",
) -> dict:
    return {
        "started_at": started_at,
        "mode": mode,
        "opponent": "Engine",
        "engine_level": 3,
        "time_control": "rapid",
        "player_color": "white",
        "result": result,
        "reason": "checkmate",
        "moves": 40,
        "pgn": "1. e4 e5 *",
        "backends": "python:23",
    }


@pytest.fixture()
def store(tmp_path: Path) -> HistoryStore:
    return HistoryStore(tmp_path / "history.db")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_empty_db_stats(store: HistoryStore) -> None:
    s = store.stats()
    assert s == Stats(played=0, won=0, lost=0, drawn=0, by_mode={})


def test_add_and_stats_won(store: HistoryStore) -> None:
    store.add(_make_record(result="won"))
    s = store.stats()
    assert s.played == 1
    assert s.won == 1
    assert s.lost == 0
    assert s.drawn == 0


def test_add_multiple_results(store: HistoryStore) -> None:
    store.add(_make_record(result="won"))
    store.add(_make_record(result="lost"))
    store.add(_make_record(result="drawn"))

    s = store.stats()
    assert s.played == 3
    assert s.won == 1
    assert s.lost == 1
    assert s.drawn == 1


def test_recent_ordering_newest_first(store: HistoryStore) -> None:
    id1 = store.add(_make_record(started_at="2024-01-01T10:00:00Z"))
    id2 = store.add(_make_record(started_at="2024-01-02T10:00:00Z"))
    id3 = store.add(_make_record(started_at="2024-01-03T10:00:00Z"))

    records = store.recent()
    ids = [r.id for r in records]
    assert ids == [id3, id2, id1], "Recent should return newest (highest id) first"


def test_recent_pagination(store: HistoryStore) -> None:
    for i in range(5):
        store.add(_make_record(started_at=f"2024-01-0{i+1}T00:00:00Z"))

    page = store.recent(limit=2, offset=2)
    assert len(page) == 2


def test_get_by_id(store: HistoryStore) -> None:
    record_id = store.add(_make_record(result="lost"))
    record = store.get(record_id)
    assert record is not None
    assert record.result == "lost"
    assert record.id == record_id


def test_get_nonexistent_id(store: HistoryStore) -> None:
    assert store.get(9999) is None


def test_clear(store: HistoryStore) -> None:
    store.add(_make_record(result="won"))
    store.add(_make_record(result="lost"))
    store.clear()

    s = store.stats()
    assert s == Stats(played=0, won=0, lost=0, drawn=0, by_mode={})


def test_by_mode_stats(store: HistoryStore) -> None:
    store.add(_make_record(mode="vs_engine"))
    store.add(_make_record(mode="vs_engine"))
    store.add(_make_record(mode="pass_play"))

    s = store.stats()
    assert s.by_mode.get("vs_engine") == 2
    assert s.by_mode.get("pass_play") == 1
