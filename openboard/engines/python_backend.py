"""
openboard.engines.python_backend
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Assumption: multiprocessing start method is 'spawn' (set in main.py).
The worker runs engine.py in a child process to avoid blocking pygame.
"""
from __future__ import annotations

import logging
import multiprocessing
import multiprocessing.connection
import threading
import time
from typing import TYPE_CHECKING

import chess

from openboard import config
from openboard.engines.base import EngineBackend, EngineError
from openboard.engines.types import SearchRequest, SearchResult, Backend

if TYPE_CHECKING:
    pass

log = logging.getLogger('openboard.engines.python_backend')


def _worker_main(conn: multiprocessing.connection.Connection,
                 cancel_event: multiprocessing.Event) -> None:
    """Worker process main loop. Creates one Engine and handles requests."""
    from openboard.engines.engine import Engine
    engine = Engine(depth=2, level=None, log_to_file=False)

    while True:
        try:
            msg = conn.recv()
        except EOFError:
            break

        if msg is None:  # shutdown signal
            break

        if msg.get('cmd') == 'new_game':
            engine.new_game()
            conn.send({'ok': True})
            continue

        # It's a search request
        req = msg
        try:
            purpose = req.get('purpose', 'play')
            fen = req['fen']
            level = req.get('level')
            depth = req.get('depth')
            time_s = req.get('time_s')

            board = chess.Board(fen)

            if purpose == 'play' and level is not None:
                spec = config.LEVELS[level]
                py_level = spec.python_level if spec.python_level else 5
                engine.set_level(py_level)
                engine.set_use_book(req.get('use_book', True))
                # margin is set by set_level, leave it as-is
            else:
                # evaluate: use depth, no book, no margin
                if depth is not None:
                    engine.depth = depth
                engine.set_use_book(False)
                engine.set_margin(0.0)

            cancel_event.clear()
            t0 = time.monotonic()
            move, score, nodes = engine.best_move(board, time_limit=time_s, stop_event=cancel_event)
            elapsed = time.monotonic() - t0

            pv = engine.info.get('pv', [])
            search_depth = engine.info.get('depth', engine.depth)

            result = {
                'best_uci': move.uci() if move else None,
                'score_pawns': score,
                'depth': search_depth,
                'nodes': nodes,
                'seconds': elapsed,
                'pv_uci': pv,
                'book': engine.info.get('book', False),
            }
            conn.send(result)
        except Exception as exc:
            conn.send({'error': str(exc)})


class PythonBackend(EngineBackend):
    """Runs the built-in engine in a child process."""

    name: Backend = 'python'
    available: bool = True

    def __init__(self) -> None:
        self._proc: multiprocessing.Process | None = None
        self._parent_conn: multiprocessing.connection.Connection | None = None
        self._cancel_event: multiprocessing.Event | None = None
        self._lock = threading.Lock()
        self._started = False

    def start(self) -> None:
        """Initialise the backend by spawning the worker process."""
        if self._started:
            return
        self._start_worker()
        self._started = True

    def _start_worker(self) -> None:
        """Spawn a fresh worker process."""
        ctx = multiprocessing.get_context('spawn')
        parent_conn, child_conn = ctx.Pipe()
        cancel_event = ctx.Event()
        proc = ctx.Process(
            target=_worker_main,
            args=(child_conn, cancel_event),
            daemon=True,
        )
        proc.start()
        child_conn.close()
        self._proc = proc
        self._parent_conn = parent_conn
        self._cancel_event = cancel_event

    def stop(self) -> None:
        """Shut down the worker process gracefully, then kill if needed."""
        with self._lock:
            if self._parent_conn:
                try:
                    self._parent_conn.send(None)
                except Exception:
                    pass
            if self._proc:
                self._proc.join(timeout=2)
                if self._proc.is_alive():
                    self._proc.kill()
            self._proc = None
            self._parent_conn = None
            self._started = False

    def new_game(self) -> None:
        """Tell the worker process to clear its transposition table."""
        with self._lock:
            if self._parent_conn:
                try:
                    self._parent_conn.send({'cmd': 'new_game'})
                    self._parent_conn.recv()  # wait for ack
                except Exception:
                    pass

    def configure(self, **options: object) -> None:
        """No-op: Python backend is configured per-request."""
        pass

    def search(self, request: SearchRequest, cancel: threading.Event) -> SearchResult:
        """Send a search request to the worker and block until result arrives."""
        from openboard.engines.types import decode_python_score

        with self._lock:
            conn = self._parent_conn
            proc = self._proc

        if conn is None or proc is None or not proc.is_alive():
            # Try to restart once
            try:
                self._start_worker()
                with self._lock:
                    conn = self._parent_conn
            except Exception as exc:
                raise EngineError(f'Python backend not running: {exc}', recoverable=True)

        req_dict = {
            'purpose': request.purpose,
            'fen': request.fen,
            'level': request.level,
            'depth': request.depth,
            'time_s': request.time_s,
            'use_book': True,
        }

        try:
            conn.send(req_dict)
        except Exception as exc:
            raise EngineError(f'Failed to send to worker: {exc}', recoverable=True)

        # Poll for result while checking cancel
        while True:
            if cancel.is_set():
                if self._cancel_event is not None:
                    self._cancel_event.set()
            if conn.poll(0.05):
                break

        try:
            result = conn.recv()
        except Exception as exc:
            raise EngineError(f'Failed to receive from worker: {exc}', recoverable=True)

        if 'error' in result:
            raise EngineError(result['error'], recoverable=True)

        score_cp, mate_in = decode_python_score(result.get('score_pawns') or 0.0)

        return SearchResult(
            request_id=request.request_id,
            best_uci=result.get('best_uci'),
            score_cp=score_cp,
            mate_in=mate_in,
            depth=result.get('depth', 1),
            nodes=result.get('nodes', 0),
            seconds=result.get('seconds', 0.0),
            pv_uci=tuple(result.get('pv_uci', [])),
            backend='python',
            reason=f"python engine level {request.level}",
            book=result.get('book', False),
            cancelled=cancel.is_set(),
        )
