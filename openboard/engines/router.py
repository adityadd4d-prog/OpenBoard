"""
openboard.engines.router
~~~~~~~~~~~~~~~~~~~~~~~~
Pure routing decision logic. No I/O, no processes, no time calls.
Same input always produces the exact same Decision.
"""

from __future__ import annotations

from dataclasses import dataclass

from openboard import config
from openboard.engines.benchmark import estimate_seconds, max_depth_within
from openboard.engines.types import Backend, Capabilities, SearchRequest


@dataclass(frozen=True, slots=True)
class Decision:
    """The decision made by choose_backend."""

    backend: Backend
    request: SearchRequest
    reason: str


def choose_backend(req: SearchRequest, caps: Capabilities) -> Decision:
    """Choose backend (python or stockfish) based on strict precedence rules."""
    calib = caps.calibration

    # R0: Stockfish unavailable OR smart_engine is False -> Python
    if not caps.stockfish_available or not caps.smart_engine:
        cause = "stockfish missing" if not caps.stockfish_available else "smart engine off"
        adj_depth = req.depth
        if req.time_s is not None and calib is not None:
            adj_depth = max(1, max_depth_within(req.time_s * config.PY_TIME_FIT_RATIO, calib))
        elif req.time_s is not None:
            adj_depth = 1

        adj_level = req.level
        if req.level is not None and req.level >= 5:
            adj_level = 5

        new_req = SearchRequest(
            request_id=req.request_id,
            fen=req.fen,
            purpose=req.purpose,
            depth=adj_depth,
            time_s=req.time_s,
            level=adj_level,
            auto=req.auto,
            limit_strength=req.limit_strength,
        )
        return Decision(backend="python", request=new_req, reason=cause)

    # R4: req.auto: Stockfish with AUTO_EVAL_SF, or Python with AUTO_EVAL_PY if SF missing
    if req.auto:
        depth, time_s = config.AUTO_EVAL_SF
        new_req = SearchRequest(
            request_id=req.request_id,
            fen=req.fen,
            purpose=req.purpose,
            depth=depth,
            time_s=time_s,
            level=req.level,
            auto=False,
            limit_strength=req.limit_strength,
        )
        return Decision(backend="stockfish", request=new_req, reason="auto mode -> stockfish")

    # R1: purpose 'play': spec = config.LEVELS[level]
    if req.purpose == "play" and req.level is not None:
        spec = config.LEVELS[req.level]
        if spec.sf_only:
            return Decision(
                backend="stockfish",
                request=req,
                reason=f"level {req.level} -> stockfish only",
            )
        if spec.python_level is not None and spec.sf_elo is None:
            return Decision(
                backend="python",
                request=req,
                reason=f"level {req.level} -> built-in engine",
            )
        # Both set (level 5): Python if estimate fits ratio, else Stockfish
        if spec.python_level is not None and spec.sf_elo is not None:
            py_depth = spec.python_level
            time_budget = req.time_s if req.time_s is not None else (spec.sf_movetime_s or 1.0)
            budget = time_budget * config.PY_TIME_FIT_RATIO
            if calib is not None and estimate_seconds(py_depth, calib) <= budget:
                return Decision(
                    backend="python",
                    request=req,
                    reason=f"level {req.level} -> built-in engine (time fits)",
                )
            return Decision(
                backend="stockfish",
                request=req,
                reason=f"level {req.level} -> stockfish",
            )

    # R2: purpose 'evaluate' with explicit depth
    if req.purpose == "evaluate" and req.depth is not None:
        if req.depth > config.PY_EVAL_MAX_DEPTH:
            return Decision(
                backend="stockfish",
                request=req,
                reason=f"depth {req.depth} > {config.PY_EVAL_MAX_DEPTH} -> Stockfish",
            )
        # Otherwise Python if no time limit or estimate fits ratio, else Stockfish
        if req.time_s is None:
            if calib is None and req.depth > 2:
                return Decision(
                    backend="stockfish",
                    request=req,
                    reason=f"depth {req.depth} > 2 without calibration -> Stockfish",
                )
            return Decision(
                backend="python",
                request=req,
                reason=f"depth {req.depth} <= {config.PY_EVAL_MAX_DEPTH} -> built-in engine",
            )
        else:
            budget = req.time_s * config.PY_TIME_FIT_RATIO
            if calib is not None and estimate_seconds(req.depth, calib) <= budget:
                return Decision(
                    backend="python",
                    request=req,
                    reason="estimate fits time budget -> built-in engine",
                )
            return Decision(
                backend="stockfish",
                request=req,
                reason="time budget tight -> Stockfish",
            )

    # R3: purpose 'evaluate' with only a time limit
    if req.purpose == "evaluate" and req.depth is None and req.time_s is not None:
        if calib is None:
            return Decision(
                backend="stockfish",
                request=req,
                reason="no calibration for time limit -> Stockfish",
            )
        max_d = max_depth_within(req.time_s, calib)
        if max_d < config.PY_MIN_USEFUL_DEPTH:
            return Decision(
                backend="stockfish",
                request=req,
                reason=f"Python max depth {max_d} < {config.PY_MIN_USEFUL_DEPTH} -> Stockfish",
            )
        adj_req = SearchRequest(
            request_id=req.request_id,
            fen=req.fen,
            purpose=req.purpose,
            depth=max_d,
            time_s=req.time_s,
            level=req.level,
            auto=req.auto,
            limit_strength=req.limit_strength,
        )
        return Decision(
            backend="python",
            request=adj_req,
            reason=f"Python can reach depth {max_d} in time -> built-in engine",
        )

    # Fallback default
    return Decision(backend="python", request=req, reason="default fallback -> built-in engine")
