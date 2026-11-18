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
    max_py_depth = max(1, int(caps.custom_max_depth))

    # Determine effective engine selection mode
    if caps.engine_mode == "custom" or not caps.smart_engine:
        effective_mode = "custom"
    elif caps.engine_mode == "stockfish":
        effective_mode = "stockfish"
    else:
        effective_mode = "auto"

    # R0: Stockfish unavailable OR Custom Engine forced -> Python
    if not caps.stockfish_available or effective_mode == "custom":
        cause = "stockfish missing" if not caps.stockfish_available else "custom engine selected"
        adj_depth = req.depth
        adj_time = req.time_s
        adj_level = req.level
        adj_auto = False

        if req.auto:
            adj_depth = min(max_py_depth, int(config.AUTO_EVAL_PY["depth"]))
            adj_time = float(config.AUTO_EVAL_PY["time"])
            reason = f"{cause} -> built-in engine (auto depth {adj_depth})"
        elif req.purpose == "evaluate":
            if req.depth is not None:
                if req.depth > max_py_depth:
                    adj_depth = max_py_depth
                    reason = f"{cause} -> built-in engine (capped to depth {adj_depth})"
                else:
                    adj_depth = req.depth
                    reason = f"{cause} -> built-in engine (depth {adj_depth})"
            elif req.time_s is not None:
                if calib is not None:
                    adj_depth = max(1, min(max_py_depth, max_depth_within(req.time_s * config.PY_TIME_FIT_RATIO, calib)))
                else:
                    adj_depth = min(max_py_depth, int(config.AUTO_EVAL_PY["depth"]))
                reason = f"{cause} -> built-in engine (time {req.time_s:.1f}s)"
            else:
                adj_depth = min(max_py_depth, int(config.AUTO_EVAL_PY["depth"]))
                reason = f"{cause} -> built-in engine"
        else:
            if req.level is not None and req.level >= 5:
                adj_level = 5
            reason = f"{cause} -> built-in engine (level {adj_level})" if adj_level is not None else f"{cause} -> built-in engine"

        new_req = SearchRequest(
            request_id=req.request_id,
            fen=req.fen,
            purpose=req.purpose,
            depth=adj_depth,
            time_s=adj_time,
            level=adj_level,
            auto=adj_auto,
            limit_strength=req.limit_strength,
        )
        return Decision(backend="python", request=new_req, reason=reason)

    # R0b: Stockfish explicitly selected -> always Stockfish
    if effective_mode == "stockfish":
        if req.auto:
            depth = int(config.AUTO_EVAL_SF["depth"])
            time_s = float(config.AUTO_EVAL_SF["time"])
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
            return Decision(backend="stockfish", request=new_req, reason="stockfish selected (auto) -> Stockfish")
        if req.purpose == "play" and req.level is not None:
            return Decision(
                backend="stockfish",
                request=req,
                reason=f"stockfish selected (level {req.level}) -> Stockfish",
            )
        return Decision(backend="stockfish", request=req, reason="stockfish selected -> Stockfish")

    # R4: req.auto: Stockfish with AUTO_EVAL_SF
    if req.auto:
        depth = int(config.AUTO_EVAL_SF["depth"])
        time_s = float(config.AUTO_EVAL_SF["time"])
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
        return Decision(backend="stockfish", request=new_req, reason="auto mode -> Stockfish")

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
            if spec.python_level > max_py_depth:
                return Decision(
                    backend="stockfish",
                    request=req,
                    reason=f"level {req.level} (depth {spec.python_level}) > custom max depth {max_py_depth} -> Stockfish",
                )
            return Decision(
                backend="python",
                request=req,
                reason=f"level {req.level} -> built-in engine",
            )
        # Both set (level 5): Python if within max_py_depth (or default) and estimate fits ratio, else Stockfish
        if spec.python_level is not None and spec.sf_elo is not None:
            if max_py_depth < config.PY_EVAL_MAX_DEPTH:
                return Decision(
                    backend="stockfish",
                    request=req,
                    reason=f"level {req.level} > custom max depth {max_py_depth} -> Stockfish",
                )
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
        if req.depth > max_py_depth:
            return Decision(
                backend="stockfish",
                request=req,
                reason=f"depth {req.depth} > {max_py_depth} -> Stockfish",
            )
        # Otherwise Python if no time limit or estimate fits ratio, else Stockfish
        if req.time_s is None:
            if calib is None and max_py_depth <= config.PY_EVAL_MAX_DEPTH and req.depth > 2:
                return Decision(
                    backend="stockfish",
                    request=req,
                    reason=f"depth {req.depth} > 2 without calibration -> Stockfish",
                )
            return Decision(
                backend="python",
                request=req,
                reason=f"depth {req.depth} <= {max_py_depth} -> built-in engine",
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
