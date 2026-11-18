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


def make_caps(
    sf: bool = True,
    smart: bool = True,
    calib: PythonCalibration | None = FAST_CALIB,
    engine_mode: str = "auto",
    custom_max_depth: int = 4,
) -> Capabilities:
    return Capabilities(
        stockfish_available=sf,
        stockfish_name="Stockfish 19" if sf else None,
        elo_range=(1350, 3190) if sf else None,
        calibration=calib,
        smart_engine=smart,
        use_book=True,
        cpu_count=4,
        engine_mode=engine_mode,  # type: ignore[arg-type]
        custom_max_depth=custom_max_depth,
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
    assert "custom engine" in dec.reason


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
    assert isinstance(dec.request.depth, int)
    assert isinstance(dec.request.time_s, float)
    assert dec.request.auto is False


def test_r0_smart_engine_off_evaluate_modes() -> None:
    from openboard import config

    caps = make_caps(sf=True, smart=False, engine_mode="custom")

    # 1. Depth evaluate: capped to PY_EVAL_MAX_DEPTH so Python doesn't hang on depth 12
    req_depth = SearchRequest(request_id=101, fen=DUMMY_FEN, purpose="evaluate", depth=12)
    dec_depth = choose_backend(req_depth, caps)
    assert dec_depth.backend == "python"
    assert dec_depth.request.depth == config.PY_EVAL_MAX_DEPTH
    assert "custom engine" in dec_depth.reason
    assert "capped" in dec_depth.reason

    # 2. Time evaluate: routes to Python with bounded depth
    req_time = SearchRequest(request_id=102, fen=DUMMY_FEN, purpose="evaluate", time_s=2.0)
    dec_time = choose_backend(req_time, caps)
    assert dec_time.backend == "python"
    assert dec_time.request.time_s == pytest.approx(2.0)
    assert dec_time.request.depth is not None
    assert dec_time.request.depth <= config.PY_EVAL_MAX_DEPTH

    # 3. Auto evaluate: populates AUTO_EVAL_PY depth & time instead of leaving them None
    req_auto = SearchRequest(request_id=103, fen=DUMMY_FEN, purpose="evaluate", auto=True)
    dec_auto = choose_backend(req_auto, caps)
    assert dec_auto.backend == "python"
    assert dec_auto.request.auto is False
    assert dec_auto.request.depth == int(config.AUTO_EVAL_PY["depth"])
    assert dec_auto.request.time_s == pytest.approx(float(config.AUTO_EVAL_PY["time"]))
    assert "custom engine" in dec_auto.reason


def test_r0b_stockfish_mode_always_routes_to_stockfish() -> None:
    from openboard import config

    caps = make_caps(sf=True, smart=True, engine_mode="stockfish")

    # Even level 1 play and depth 2 evaluate route to Stockfish when forced
    for lvl in (1, 2, 4, 8):
        dec = choose_backend(SearchRequest(request_id=lvl, fen=DUMMY_FEN, purpose="play", level=lvl), caps)
        assert dec.backend == "stockfish"
        assert "stockfish selected" in dec.reason

    dec_eval = choose_backend(SearchRequest(request_id=201, fen=DUMMY_FEN, purpose="evaluate", depth=2), caps)
    assert dec_eval.backend == "stockfish"
    assert dec_eval.request.depth == 2

    dec_auto = choose_backend(SearchRequest(request_id=202, fen=DUMMY_FEN, purpose="evaluate", auto=True), caps)
    assert dec_auto.backend == "stockfish"
    assert dec_auto.request.depth == int(config.AUTO_EVAL_SF["depth"])
    assert dec_auto.request.time_s == pytest.approx(float(config.AUTO_EVAL_SF["time"]))


def test_custom_max_depth_threshold_switches_to_stockfish() -> None:
    # Lower threshold to 2: depth 2 stays Python, depth 3 switches to Stockfish
    caps_low = make_caps(sf=True, smart=True, engine_mode="auto", custom_max_depth=2)
    assert choose_backend(SearchRequest(request_id=301, fen=DUMMY_FEN, purpose="evaluate", depth=2), caps_low).backend == "python"
    assert choose_backend(SearchRequest(request_id=302, fen=DUMMY_FEN, purpose="evaluate", depth=3), caps_low).backend == "stockfish"
    assert choose_backend(SearchRequest(request_id=303, fen=DUMMY_FEN, purpose="play", level=2), caps_low).backend == "python"
    assert choose_backend(SearchRequest(request_id=304, fen=DUMMY_FEN, purpose="play", level=3), caps_low).backend == "stockfish"

    # Raise threshold to 6: depth 6 stays Python, depth 7 switches to Stockfish
    caps_high = make_caps(sf=True, smart=True, engine_mode="auto", custom_max_depth=6)
    assert choose_backend(SearchRequest(request_id=305, fen=DUMMY_FEN, purpose="evaluate", depth=6), caps_high).backend == "python"
    assert choose_backend(SearchRequest(request_id=306, fen=DUMMY_FEN, purpose="evaluate", depth=7), caps_high).backend == "stockfish"

    # When Custom Engine is forced, evaluate depth is capped to custom_max_depth
    caps_custom = make_caps(sf=True, smart=False, engine_mode="custom", custom_max_depth=5)
    dec_cap = choose_backend(SearchRequest(request_id=307, fen=DUMMY_FEN, purpose="evaluate", depth=12), caps_custom)
    assert dec_cap.backend == "python"
    assert dec_cap.request.depth == 5


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
