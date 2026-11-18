"""
openboard.engines.service
~~~~~~~~~~~~~~~~~~~~~~~~~
The single engine service used by the UI layer.
Keeps UI thread free from computation. Routes requests to backends,
handles cancellation, retries on failure, and dispatches callbacks on poll().
"""

from __future__ import annotations

import logging
import os
import queue
import threading
import time
from typing import Callable

from openboard import config
from openboard.engines.base import EngineBackend, EngineError
from openboard.engines.benchmark import calibrate
from openboard.engines.python_backend import PythonBackend
from openboard.engines.router import choose_backend
from openboard.engines.stockfish_backend import StockfishBackend
from openboard.engines.types import Capabilities, PythonCalibration, SearchRequest, SearchResult

log = logging.getLogger("openboard.engines.service")

_counter_lock = threading.Lock()
_req_counter = 0


def _next_request_id() -> int:
    global _req_counter
    with _counter_lock:
        _req_counter += 1
        return _req_counter


class EngineService:
    """Manages background backends and dispatches asynchronous search requests."""

    def __init__(self, settings: Any, backends: tuple[EngineBackend, EngineBackend] | None = None) -> None:
        self.settings = settings
        if backends is not None:
            self.py_backend, self.sf_backend = backends
        else:
            self.py_backend = PythonBackend()
            self.sf_backend = StockfishBackend()

        self._result_queue: queue.Queue[tuple[int, SearchResult, Callable[[SearchResult], None]]] = queue.Queue()
        self._active_requests: set[int] = set()
        self._requests_lock = threading.Lock()

        # Backend worker queues & threads
        self._py_queue: queue.Queue[tuple[SearchRequest, Callable[[SearchResult], None], threading.Event, str] | None] = queue.Queue()
        self._sf_queue: queue.Queue[tuple[SearchRequest, Callable[[SearchResult], None], threading.Event, str] | None] = queue.Queue()

        self._py_cancel = threading.Event()
        self._sf_cancel = threading.Event()

        self._py_worker: threading.Thread | None = None
        self._sf_worker: threading.Thread | None = None

        self._eval_cancel_event = threading.Event()
        self._calibration: PythonCalibration | None = None
        self._is_shutdown = False

        # Load cached calibration if matching version/cpu
        self._load_calibration()

    def _load_calibration(self) -> None:
        calib_dict = getattr(self.settings, "python_calibration", None)
        calib_key = getattr(self.settings, "calibration_key", None)
        expected_key = f"{config.APP_VERSION}_{os.cpu_count()}"
        if calib_dict and calib_key == expected_key:
            try:
                self._calibration = PythonCalibration(
                    seconds_by_depth={int(k): float(v) for k, v in calib_dict["seconds_by_depth"].items()},
                    growth=float(calib_dict["growth"]),
                    nps=float(calib_dict["nps"]),
                )
            except Exception as exc:
                log.debug("Failed to restore calibration: %s", exc)

    def start(self) -> None:
        """Start backend processes and worker threads without blocking the caller."""
        if self._is_shutdown:
            return

        def _init_proc() -> None:
            try:
                self.py_backend.start()
            except Exception as exc:
                log.error("Failed to start python backend: %s", exc)

            try:
                self.sf_backend.start()
            except Exception as exc:
                log.error("Failed to start stockfish backend: %s", exc)

            # Worker threads
            self._py_worker = threading.Thread(target=self._worker_loop, args=(self.py_backend, self._py_queue), daemon=True, name="py-worker")
            self._sf_worker = threading.Thread(target=self._worker_loop, args=(self.sf_backend, self._sf_queue), daemon=True, name="sf-worker")
            self._py_worker.start()
            self._sf_worker.start()

            # Calibration if needed
            if self._calibration is None:
                self._run_calibration()

        threading.Thread(target=_init_proc, daemon=True, name="engine-init").start()

    def _run_calibration(self) -> None:
        from openboard.engines.engine import Engine

        try:
            log.info("Starting Python engine calibration...")
            calib = calibrate(lambda: Engine(depth=2, level=None, log_to_file=False), budget_s=1.5)
            self._calibration = calib
            expected_key = f"{config.APP_VERSION}_{os.cpu_count()}"
            calib_dict = {
                "seconds_by_depth": calib.seconds_by_depth,
                "growth": calib.growth,
                "nps": calib.nps,
            }
            if hasattr(self.settings, "set"):
                self.settings.set(python_calibration=calib_dict, calibration_key=expected_key)
            log.info("Calibration complete: growth=%.2f, nps=%.1f", calib.growth, calib.nps)
        except Exception as exc:
            log.warning("Calibration error: %s", exc)

    def capabilities(self) -> Capabilities:
        """Return capabilities reflecting live settings and engine availability."""
        sf_name = getattr(self.sf_backend, "name_str", None)
        elo_range = getattr(self.sf_backend, "elo_range", None)
        smart = getattr(self.settings, "smart_engine", True)
        raw_mode = getattr(self.settings, "engine_mode", None)
        if raw_mode in ("auto", "custom", "stockfish"):
            engine_mode = raw_mode
            smart = engine_mode != "custom"
        else:
            engine_mode = "auto" if smart else "custom"
        use_book = getattr(self.settings, "use_book", True)
        custom_max_depth = int(getattr(self.settings, "custom_max_depth", config.PY_EVAL_MAX_DEPTH))

        return Capabilities(
            stockfish_available=self.sf_backend.available,
            stockfish_name=sf_name,
            elo_range=elo_range,
            calibration=self._calibration,
            smart_engine=smart,
            use_book=use_book,
            cpu_count=os.cpu_count() or 1,
            engine_mode=engine_mode,
            custom_max_depth=custom_max_depth,
        )

    def submit(self, req_kwargs: dict[str, Any], on_done: Callable[[SearchResult], None]) -> int:
        """Submit a search request. Returns the assigned request_id."""
        req_id = _next_request_id()
        base_req = SearchRequest(request_id=req_id, **req_kwargs)

        with self._requests_lock:
            self._active_requests.add(req_id)

        # 'Latest wins' for evaluate: cancel previous evaluate requests
        if base_req.purpose == "evaluate":
            self._eval_cancel_event.set()
            self._eval_cancel_event = threading.Event()
            cancel_event = self._eval_cancel_event
            with self._requests_lock:
                # Remove any earlier requests from active_requests so their results are dropped as stale
                if hasattr(self, "_last_eval_id") and self._last_eval_id in self._active_requests:
                    self._active_requests.discard(self._last_eval_id)
                self._last_eval_id = req_id
        else:
            cancel_event = threading.Event()

        caps = self.capabilities()
        decision = choose_backend(base_req, caps)
        chosen_req = decision.request
        route_reason = decision.reason

        if decision.backend == "stockfish" and self.sf_backend.available and caps.engine_mode != "custom":
            self._sf_queue.put((chosen_req, on_done, cancel_event, route_reason))
        else:
            self.py_backend.configure(use_book=caps.use_book)
            self._py_queue.put((chosen_req, on_done, cancel_event, route_reason))

        return req_id

    def _worker_loop(
        self,
        backend: EngineBackend,
        work_queue: queue.Queue[tuple[SearchRequest, Callable[[SearchResult], None], threading.Event, str] | None],
    ) -> None:
        """Dedicated worker thread loop for an engine backend."""
        while not self._is_shutdown:
            try:
                item = work_queue.get(timeout=0.2)
            except queue.Empty:
                continue

            if item is None:
                break

            req, on_done, cancel_event, route_reason = item

            # Check if already cancelled / stale
            with self._requests_lock:
                if req.request_id not in self._active_requests:
                    continue

            result = self._execute_search_with_fallback(backend, req, cancel_event, route_reason)

            with self._requests_lock:
                if req.request_id in self._active_requests:
                    self._active_requests.remove(req.request_id)
                    self._result_queue.put((req.request_id, result, on_done))

    def _execute_search_with_fallback(
        self,
        backend: EngineBackend,
        req: SearchRequest,
        cancel_event: threading.Event,
        route_reason: str = "",
    ) -> SearchResult:
        """Execute search, attempting a fallback to the other backend if EngineError occurs."""
        try:
            res = backend.search(req, cancel_event)
            if route_reason:
                return SearchResult(
                    request_id=res.request_id,
                    best_uci=res.best_uci,
                    score_cp=res.score_cp,
                    mate_in=res.mate_in,
                    depth=res.depth,
                    nodes=res.nodes,
                    seconds=res.seconds,
                    pv_uci=res.pv_uci,
                    backend=res.backend,
                    reason=route_reason,
                    book=res.book,
                    cancelled=res.cancelled,
                    error=res.error,
                )
            return res
        except EngineError as err:
            log.warning("Backend %s failed (%s); trying fallback", backend.name, err)
            other = self.py_backend if backend.name == "stockfish" else self.sf_backend
            allow_other = other.available and (
                other.name == "python" or self.capabilities().engine_mode != "custom"
            )
            if allow_other:
                try:
                    fallback_res = other.search(req, cancel_event)
                    # Annotate reason
                    return SearchResult(
                        request_id=fallback_res.request_id,
                        best_uci=fallback_res.best_uci,
                        score_cp=fallback_res.score_cp,
                        mate_in=fallback_res.mate_in,
                        depth=fallback_res.depth,
                        nodes=fallback_res.nodes,
                        seconds=fallback_res.seconds,
                        pv_uci=fallback_res.pv_uci,
                        backend=fallback_res.backend,
                        reason=f"fallback: {err}",
                        book=fallback_res.book,
                        cancelled=fallback_res.cancelled,
                        error=fallback_res.error,
                    )
                except Exception as exc2:
                    log.error("Fallback also failed: %s", exc2)

            return SearchResult(
                request_id=req.request_id,
                best_uci=None,
                score_cp=None,
                mate_in=None,
                depth=0,
                nodes=0,
                seconds=0.0,
                pv_uci=(),
                backend=backend.name,
                reason="failure",
                cancelled=cancel_event.is_set(),
                error=str(err),
            )
        except Exception as exc:
            log.exception("Unexpected error in %s search: %s", backend.name, exc)
            return SearchResult(
                request_id=req.request_id,
                best_uci=None,
                score_cp=None,
                mate_in=None,
                depth=0,
                nodes=0,
                seconds=0.0,
                pv_uci=(),
                backend=backend.name,
                reason="exception",
                cancelled=cancel_event.is_set(),
                error=str(exc),
            )

    def poll(self) -> None:
        """Process completed engine results on the main thread."""
        while True:
            try:
                req_id, result, callback = self._result_queue.get_nowait()
                try:
                    callback(result)
                except Exception as exc:
                    log.exception("Error executing engine callback: %s", exc)
            except queue.Empty:
                break

    def cancel(self, request_id: int | None = None) -> None:
        """Cancel a specific request or all active requests."""
        with self._requests_lock:
            if request_id is None:
                self._active_requests.clear()
            else:
                self._active_requests.discard(request_id)

        self._eval_cancel_event.set()
        self._py_cancel.set()
        self._sf_cancel.set()

    def new_game(self) -> None:
        """Reset state across both backends."""
        self.cancel()
        try:
            self.py_backend.new_game()
        except Exception as exc:
            log.debug("PythonBackend new_game error: %s", exc)

        try:
            self.sf_backend.new_game()
        except Exception as exc:
            log.debug("StockfishBackend new_game error: %s", exc)

    def shutdown(self) -> None:
        """Cleanly terminate child processes and workers. Idempotent."""
        if self._is_shutdown:
            return
        self._is_shutdown = True

        self.cancel()
        self._py_queue.put(None)
        self._sf_queue.put(None)

        try:
            self.py_backend.stop()
        except Exception:
            pass

        try:
            self.sf_backend.stop()
        except Exception:
            pass
