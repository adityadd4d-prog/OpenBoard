"""
openboard.engines.benchmark
~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Pure functions for calibrating the Python engine's search speed.
No I/O, no pygame, no process logic. Runs in a worker process.
"""

from __future__ import annotations

import math
import threading
import time

import chess

from openboard.engines.types import PythonCalibration

MIDDLEGAME_FEN = 'r1bqkb1r/pp2pppp/2np1n2/2p5/4P3/2NP1N2/PPP2PPP/R1BQKB1R w KQkq - 2 6'


def calibrate(make_engine, budget_s: float = 1.5) -> PythonCalibration:
    """Time search at depths 1,2,3 on two positions (start + middlegame).

    Returns PythonCalibration. growth = geometric mean of t(d+1)/t(d), clamped 2.0-12.0.
    Runs within budget_s total wall time.
    """
    positions = [chess.STARTING_FEN, MIDDLEGAME_FEN]
    times_by_depth: dict[int, list[float]] = {}
    total_nodes = 0
    total_time = 0.0
    budget_used = 0.0

    for fen in positions:
        board = chess.Board(fen)
        for depth in [1, 2, 3]:
            if budget_used >= budget_s:
                break
            engine = make_engine()
            engine.depth = depth
            stop = threading.Event()
            t0 = time.monotonic()
            _, _, nodes = engine.best_move(board, time_limit=None, stop_event=stop)
            elapsed = time.monotonic() - t0
            budget_used += elapsed
            times_by_depth.setdefault(depth, []).append(elapsed)
            total_nodes += nodes
            total_time += elapsed

    # Average times per depth
    seconds_by_depth = {d: sum(ts) / len(ts) for d, ts in times_by_depth.items()}

    # Growth rate (geometric mean of consecutive ratios)
    depths_sorted = sorted(seconds_by_depth.keys())
    ratios = []
    for i in range(len(depths_sorted) - 1):
        d0, d1 = depths_sorted[i], depths_sorted[i + 1]
        t0_v, t1_v = seconds_by_depth[d0], seconds_by_depth[d1]
        if t0_v > 0:
            ratios.append(t1_v / t0_v)

    if ratios:
        growth = math.exp(sum(math.log(r) for r in ratios) / len(ratios))
        growth = max(2.0, min(12.0, growth))
    else:
        growth = 4.0  # default

    nps = total_nodes / total_time if total_time > 0 else 1000.0
    return PythonCalibration(seconds_by_depth=seconds_by_depth, growth=growth, nps=nps)


def estimate_seconds(depth: int, calib: PythonCalibration) -> float:
    """Estimate seconds for a given depth using calibration data.

    If the depth is known, return it directly. Otherwise extrapolate
    from the last known depth using the growth rate.
    """
    depths = sorted(calib.seconds_by_depth.keys())
    if not depths:
        return float('inf')
    if depth in calib.seconds_by_depth:
        return calib.seconds_by_depth[depth]
    # Extrapolate from last known depth
    last_depth = depths[-1]
    last_time = calib.seconds_by_depth[last_depth]
    return last_time * (calib.growth ** (depth - last_depth))


def max_depth_within(seconds: float, calib: PythonCalibration) -> int:
    """Return maximum depth achievable within the time budget."""
    if not calib.seconds_by_depth:
        return 1
    for d in range(40, 0, -1):
        if estimate_seconds(d, calib) <= seconds:
            return d
    return 1
