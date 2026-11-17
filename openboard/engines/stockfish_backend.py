"""
openboard.engines.stockfish_backend
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Stockfish chess engine backend wrapping python-chess chess.engine.
No pygame allowed here.
"""

from __future__ import annotations

import logging
import os
import subprocess
import threading
import time
from typing import Any

import chess
import chess.engine

from openboard import config, paths
from openboard.engines.base import EngineBackend, EngineError
from openboard.engines.types import Backend, SearchRequest, SearchResult

log = logging.getLogger("openboard.engines.stockfish_backend")


class StockfishBackend(EngineBackend):
    """Engine backend using a bundled Stockfish executable."""

    name: Backend = "stockfish"

    def __init__(self) -> None:
        self.available: bool = False
        self.name_str: str | None = None
        self.elo_range: tuple[int, int] | None = None
        self._engine: chess.engine.SimpleEngine | None = None
        self._lock = threading.Lock()
        self._game_token: object = object()
        self._cpu_count = os.cpu_count() or 1
        self._active_path: paths.Path | None = None

    def start(self) -> None:
        """Probe candidate Stockfish binaries and connect to the best working one."""
        with self._lock:
            if self._engine is not None and self.available:
                return

            candidates = paths.stockfish_candidates()
            if not candidates:
                log.info("No Stockfish binaries found in bin/stockfish/")
                self.available = False
                return

            for path in candidates:
                try:
                    kwargs: dict[str, Any] = {"timeout": 10.0}
                    if os.name == "nt":
                        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW  # type: ignore[attr-defined]

                    eng = chess.engine.SimpleEngine.popen_uci(str(path), **kwargs)
                    self.name_str = eng.id.get("name", "Stockfish")

                    # Check UCI_LimitStrength and UCI_Elo
                    elo_range = None
                    if "UCI_Elo" in eng.options:
                        opt = eng.options["UCI_Elo"]
                        if hasattr(opt, "min") and hasattr(opt, "max"):
                            elo_range = (opt.min, opt.max)
                    self.elo_range = elo_range

                    # Configure Threads and Hash
                    cfg: dict[str, Any] = {}
                    threads = min(4, max(1, self._cpu_count - 1))
                    if "Threads" in eng.options:
                        cfg["Threads"] = threads
                    if "Hash" in eng.options:
                        cfg["Hash"] = 64
                    if cfg:
                        eng.configure(cfg)

                    self._engine = eng
                    self._active_path = path
                    self.available = True
                    log.info("Started Stockfish backend: %s (%s)", self.name_str, path)
                    return
                except Exception as exc:
                    log.debug("Stockfish candidate %s failed: %s", path, exc)

            log.warning("All Stockfish candidates failed to initialize.")
            self.available = False

    def stop(self) -> None:
        """Shut down the running Stockfish process."""
        with self._lock:
            if self._engine is not None:
                try:
                    self._engine.quit()
                except Exception as exc:
                    log.debug("Error quitting Stockfish: %s", exc)
                finally:
                    self._engine = None
                    self.available = False

    def new_game(self) -> None:
        """Signal a new game to the engine."""
        with self._lock:
            self._game_token = object()

    def configure(self, **options: Any) -> None:
        """Send configuration options to Stockfish."""
        with self._lock:
            if self._engine is not None and self.available:
                try:
                    self._engine.configure(options)
                except Exception as exc:
                    log.warning("Failed to configure Stockfish: %s", exc)

    def search(self, request: SearchRequest, cancel: threading.Event) -> SearchResult:
        """Run analysis / move search against Stockfish."""
        with self._lock:
            engine = self._engine
            if engine is None or not self.available:
                raise EngineError("Stockfish backend is not available", recoverable=False)
            game_token = self._game_token

        board = chess.Board(request.fen)

        # Build options & limit
        cfg: dict[str, Any] = {}
        if request.purpose == "play" and request.level is not None:
            spec = config.LEVELS[request.level]
            if spec.sf_elo is not None and "UCI_LimitStrength" in engine.options:
                cfg["UCI_LimitStrength"] = True
                target_elo = spec.sf_elo
                if self.elo_range:
                    target_elo = max(self.elo_range[0], min(self.elo_range[1], target_elo))
                cfg["UCI_Elo"] = target_elo
            else:
                if "UCI_LimitStrength" in engine.options:
                    cfg["UCI_LimitStrength"] = False

            movetime = spec.sf_movetime_s or request.time_s or 1.0
            limit = chess.engine.Limit(time=movetime)
        else:
            if "UCI_LimitStrength" in engine.options:
                cfg["UCI_LimitStrength"] = False
            limit_kw: dict[str, Any] = {}
            if request.depth is not None:
                limit_kw["depth"] = request.depth
            if request.time_s is not None:
                limit_kw["time"] = request.time_s
            limit = chess.engine.Limit(**limit_kw) if limit_kw else chess.engine.Limit(depth=config.EVAL_DEFAULT_DEPTH)

        if cfg:
            try:
                engine.configure(cfg)
            except Exception as exc:
                log.debug("Could not apply config %s: %s", cfg, exc)

        t0 = time.monotonic()
        best_uci: str | None = None
        score_cp: int | None = None
        mate_in: int | None = None
        depth_reached = 0
        nodes = 0
        pv_uci: list[str] = []

        try:
            with engine.analysis(board, limit, game=game_token) as analysis:
                for info in analysis:
                    if cancel.is_set():
                        analysis.stop()
                        break

                    if "depth" in info:
                        depth_reached = info["depth"]
                    if "nodes" in info:
                        nodes = info["nodes"]
                    if "score" in info:
                        s = info["score"].white()
                        score_cp = s.score()
                        mate_in = s.mate()
                    if "pv" in info and info["pv"]:
                        pv_uci = [m.uci() for m in info["pv"][:8]]

                try:
                    res = analysis.wait()
                    if res.move:
                        best_uci = res.move.uci()
                except Exception:
                    pass

                if best_uci is None and pv_uci:
                    best_uci = pv_uci[0]

        except (chess.engine.EngineTerminatedError, chess.engine.EngineError) as exc:
            log.warning("Stockfish search encountered %s; attempting restart", exc)
            self._restart()
            raise EngineError(f"Stockfish failure: {exc}", recoverable=True) from exc
        except Exception as exc:
            log.error("Stockfish unexpected error: %s", exc)
            raise EngineError(f"Stockfish error: {exc}", recoverable=True) from exc

        elapsed = time.monotonic() - t0

        return SearchResult(
            request_id=request.request_id,
            best_uci=best_uci,
            score_cp=score_cp,
            mate_in=mate_in,
            depth=depth_reached,
            nodes=nodes,
            seconds=elapsed,
            pv_uci=tuple(pv_uci),
            backend="stockfish",
            reason=f"stockfish {self.name_str or ''}".strip(),
            book=False,
            cancelled=cancel.is_set(),
            error=None,
        )

    def _restart(self) -> None:
        """Attempt to restart Stockfish once."""
        self.stop()
        self.start()
