"""
tests/test_service.py
~~~~~~~~~~~~~~~~~~~~~
Tests for EngineService with FakeBackends.
"""

import threading
import time
from typing import Any
import pytest

from openboard.engines.base import EngineBackend, EngineError
from openboard.engines.service import EngineService
from openboard.engines.types import Backend, SearchRequest, SearchResult


class FakeBackend(EngineBackend):
    def __init__(self, name: Backend, available: bool = True, fail: bool = False, delay: float = 0.0) -> None:
        self.name = name
        self.available = available
        self.fail = fail
        self.delay = delay
        self.started = False
        self.stopped = False
        self.search_calls = 0

    def start(self) -> None:
        self.started = True

    def stop(self) -> None:
        self.stopped = True

    def new_game(self) -> None:
        pass

    def configure(self, **options: Any) -> None:
        pass

    def search(self, request: SearchRequest, cancel: threading.Event) -> SearchResult:
        self.search_calls += 1
        if self.delay > 0:
            cancel.wait(self.delay)

        if self.fail:
            raise EngineError(f"{self.name} simulated failure", recoverable=True)

        return SearchResult(
            request_id=request.request_id,
            best_uci="e2e4",
            score_cp=20,
            mate_in=None,
            depth=request.depth or 4,
            nodes=100,
            seconds=0.01,
            pv_uci=("e2e4",),
            backend=self.name,
            reason="fake search",
            cancelled=cancel.is_set(),
        )


class DummySettings:
    smart_engine = True
    use_book = True
    python_calibration = None
    calibration_key = None


def test_service_routing_and_poll() -> None:
    settings = DummySettings()
    py = FakeBackend("python", available=True)
    sf = FakeBackend("stockfish", available=True)
    svc = EngineService(settings, backends=(py, sf))
    svc.start()

    results: list[SearchResult] = []
    # Play level 1 -> routes to Python
    req_id = svc.submit(
        {"fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1", "purpose": "play", "level": 1},
        on_done=results.append,
    )

    # Wait briefly for worker thread to process
    time.sleep(0.1)
    svc.poll()

    assert len(results) == 1
    assert results[0].backend == "python"
    assert results[0].request_id == req_id
    svc.shutdown()


def test_service_fallback_on_failure() -> None:
    settings = DummySettings()
    # Python fails, stockfish succeeds
    py = FakeBackend("python", available=True, fail=True)
    sf = FakeBackend("stockfish", available=True, fail=False)
    svc = EngineService(settings, backends=(py, sf))
    svc.start()

    results: list[SearchResult] = []
    # Level 1 goes to Python first, then falls back to Stockfish
    svc.submit(
        {"fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1", "purpose": "play", "level": 1},
        on_done=results.append,
    )

    time.sleep(0.15)
    svc.poll()

    assert len(results) == 1
    assert results[0].backend == "stockfish"
    assert "fallback" in results[0].reason
    svc.shutdown()


def test_service_stockfish_killed_falls_back_to_python() -> None:
    settings = DummySettings()
    # Stockfish fails (e.g. killed process), Python succeeds as fallback
    py = FakeBackend("python", available=True, fail=False)
    sf = FakeBackend("stockfish", available=True, fail=True)
    svc = EngineService(settings, backends=(py, sf))
    svc.start()

    results: list[SearchResult] = []
    # Level 6 goes to Stockfish first, then falls back to Python
    svc.submit(
        {"fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1", "purpose": "play", "level": 6},
        on_done=results.append,
    )

    time.sleep(0.15)
    svc.poll()

    assert len(results) == 1
    assert results[0].backend == "python"
    assert "fallback" in results[0].reason
    svc.shutdown()


def test_latest_wins_cancellation() -> None:
    settings = DummySettings()
    py = FakeBackend("python", available=True, delay=0.2)
    sf = FakeBackend("stockfish", available=True, delay=0.2)
    svc = EngineService(settings, backends=(py, sf))
    svc.start()

    results: list[SearchResult] = []
    # Evaluate 1
    id1 = svc.submit(
        {"fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1", "purpose": "evaluate", "depth": 3},
        on_done=results.append,
    )
    # Evaluate 2 quickly supersedes Evaluate 1
    id2 = svc.submit(
        {"fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1", "purpose": "evaluate", "depth": 3},
        on_done=results.append,
    )

    time.sleep(0.3)
    svc.poll()

    # The stale result (id1) should have been dropped or cancelled
    ids_received = [r.request_id for r in results]
    assert id2 in ids_received
    assert id1 not in ids_received
    svc.shutdown()


def test_idempotent_shutdown() -> None:
    settings = DummySettings()
    py = FakeBackend("python")
    sf = FakeBackend("stockfish")
    svc = EngineService(settings, backends=(py, sf))
    svc.start()
    svc.shutdown()
    svc.shutdown()
    assert py.stopped
    assert sf.stopped


def test_cancel_returns_in_under_300ms() -> None:
    settings = DummySettings()
    py = FakeBackend("python", available=True, delay=2.0)
    sf = FakeBackend("stockfish", available=True, delay=2.0)
    svc = EngineService(settings, backends=(py, sf))
    svc.start()

    req_id = svc.submit(
        {"fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1", "purpose": "evaluate", "depth": 15},
        on_done=lambda _: None,
    )

    t0 = time.monotonic()
    svc.cancel(req_id)
    elapsed = time.monotonic() - t0
    assert elapsed < 0.3, f"cancel took {elapsed:.3f}s (must be < 0.3s)"
    svc.shutdown()
