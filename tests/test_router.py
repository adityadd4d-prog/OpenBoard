"""
tests/test_router.py
~~~~~~~~~~~~~~~~~~~~
Table-driven tests for choose_backend in openboard.engines.router.
"""

import pytest
from openboard.engines.router import choose_backend
from openboard.engines.types import Capabilities, PythonCalibration, SearchRequest

DUMMY_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"

FAST_CALIB = PythonCalibration(
    seconds_by_depth={1: 0.001, 2: 0.005, 3: 0.02, 4: 0.1},
    growth=4.0,
    nps=50000.0,
)

SLOW_CALIB = PythonCalibration(
    seconds_by_depth={1: 0.5, 2: 2.0, 3: 8.0},
    growth=4.0,
    nps=2000.0,
)


def make_caps(sf: bool = True, smart: bool = True, calib: PythonCalibration | None = FAST_CALIB) -> Capabilities:
    return Capabilities(
        stockfish_available=sf,
        stockfish_name="Stockfish 19" if sf else None,
        elo_range=(1350, 3190) if sf else None,
        calibration=calib,
        smart_engine=smart,
        use_book=True,
        cpu_count=4,
    )


def test_r0_stockfish_unavailable() -> None:
    caps = make_caps(sf=False)
    req = SearchRequest(request_id=1, fen=DUMMY_FEN, purpose="play", level=6)
    dec = choose_backend(req, caps)
    assert dec.backend == "python"
    assert dec.request.level == 5
    assert "missing" in dec.reason


def test_r0_smart_engine_disabled() -> None:
    caps = make_caps(sf=True, smart=False)
    req = SearchRequest(request_id=1, fen=DUMMY_FEN, purpose="play", level=7)
    dec = choose_backend(req, caps)
    assert dec.backend == "python"
    assert dec.request.level == 5
    assert "smart engine off" in dec.reason


def test_r1_play_spec() -> None:
    caps = make_caps()
    # Level 1-4: Python only
    for lvl in (1, 2, 3, 4):
        req = SearchRequest(request_id=lvl, fen=DUMMY_FEN, purpose="play", level=lvl)
        dec = choose_backend(req, caps)
        assert dec.backend == "python"

    # Level 6, 7, 8: Stockfish only
    for lvl in (6, 7, 8):
        req = SearchRequest(request_id=lvl, fen=DUMMY_FEN, purpose="play", level=lvl)
        dec = choose_backend(req, caps)
        assert dec.backend == "stockfish"

    # Level 5: with fast calibration and generous time, Python fits
    req = SearchRequest(request_id=5, fen=DUMMY_FEN, purpose="play", level=5, time_s=2.0)
    dec = choose_backend(req, caps)
    assert dec.backend == "python"

    # Level 5 with slow calibration -> Stockfish
    caps_slow = make_caps(calib=SLOW_CALIB)
    dec2 = choose_backend(req, caps_slow)
    assert dec2.backend == "stockfish"


def test_r2_evaluate_depth() -> None:
    caps = make_caps()
    # Depth 3 <= PY_EVAL_MAX_DEPTH(4) -> Python
    req_shallow = SearchRequest(request_id=10, fen=DUMMY_FEN, purpose="evaluate", depth=3)
    dec_shallow = choose_backend(req_shallow, caps)
    assert dec_shallow.backend == "python"

    # Depth 12 > 4 -> Stockfish
    req_deep = SearchRequest(request_id=11, fen=DUMMY_FEN, purpose="evaluate", depth=12)
    dec_deep = choose_backend(req_deep, caps)
    assert dec_deep.backend == "stockfish"


def test_r3_evaluate_time_only() -> None:
    caps_slow = make_caps(calib=SLOW_CALIB)
    # 0.1s is too short for Python to reach PY_MIN_USEFUL_DEPTH (4)
    req_short = SearchRequest(request_id=20, fen=DUMMY_FEN, purpose="evaluate", time_s=0.1)
    dec = choose_backend(req_short, caps_slow)
    assert dec.backend == "stockfish"


def test_r4_auto() -> None:
    caps = make_caps()
    req = SearchRequest(request_id=30, fen=DUMMY_FEN, purpose="evaluate", auto=True)
    dec = choose_backend(req, caps)
    assert dec.backend == "stockfish"
    assert dec.request.depth is not None


def test_missing_calibration() -> None:
    caps_no_calib = make_caps(calib=None)
    # Without calibration, depth > 2 goes to Stockfish
    req = SearchRequest(request_id=40, fen=DUMMY_FEN, purpose="evaluate", depth=3)
    dec = choose_backend(req, caps_no_calib)
    assert dec.backend == "stockfish"

    # Depth 2 stays Python
    req2 = SearchRequest(request_id=41, fen=DUMMY_FEN, purpose="evaluate", depth=2)
    dec2 = choose_backend(req2, caps_no_calib)
    assert dec2.backend == "python"


def test_determinism() -> None:
    caps = make_caps()
    req = SearchRequest(request_id=50, fen=DUMMY_FEN, purpose="play", level=5)
    dec1 = choose_backend(req, caps)
    dec2 = choose_backend(req, caps)
    assert dec1 == dec2
