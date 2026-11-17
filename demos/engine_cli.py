"""
demos/engine_cli.py
~~~~~~~~~~~~~~~~~~~
CLI demo for testing engine search and routing.
"""

from __future__ import annotations

import argparse
import sys
import threading
import time

import chess

from openboard.engines.service import EngineService
from openboard.engines.types import SearchRequest
from openboard.storage.settings import Settings


def main() -> None:
    parser = argparse.ArgumentParser(description="OpenBoard Engine CLI")
    parser.add_argument("fen", nargs="?", default=chess.STARTING_FEN, help="FEN string to evaluate")
    parser.add_argument("--depth", "-d", type=int, help="Target search depth")
    parser.add_argument("--time", "-t", type=float, help="Target search time in seconds")
    parser.add_argument("--level", "-l", type=int, help="Engine level (1-8)")
    parser.add_argument("--auto", "-a", action="store_true", help="Auto search limit")
    parser.add_argument("--compare", "-c", action="store_true", help="Run on both backends and compare")
    args = parser.parse_args()

    settings = Settings()
    svc = EngineService(settings)
    svc.start()
    time.sleep(0.3)

    caps = svc.capabilities()
    print("=== Engine Capabilities ===")
    print(f"Stockfish Available: {caps.stockfish_available} ({caps.stockfish_name})")
    print(f"Smart Engine: {caps.smart_engine}, Use Book: {caps.use_book}")
    print()

    req_dict = {
        "fen": args.fen,
        "purpose": "evaluate" if args.level is None else "play",
        "depth": args.depth,
        "time_s": args.time,
        "level": args.level,
        "auto": args.auto,
    }

    if args.compare:
        print("=== Comparing Python vs Stockfish ===")
        # Run Python
        print("Running Python Backend...")
        cancel_py = threading.Event()
        req_py = SearchRequest(request_id=1, **req_dict)
        res_py = svc.py_backend.search(req_py, cancel_py)

        print("Running Stockfish Backend...")
        cancel_sf = threading.Event()
        req_sf = SearchRequest(request_id=2, **req_dict)
        res_sf = svc.sf_backend.search(req_sf, cancel_sf)

        print("\n--- Python ---")
        print(f"Best: {res_py.best_uci}, Score: {res_py.score_cp} cp, Mate: {res_py.mate_in}, Depth: {res_py.depth}, Nodes: {res_py.nodes}, Time: {res_py.seconds:.3f}s")
        print(f"PV: {' '.join(res_py.pv_uci)}")

        print("\n--- Stockfish ---")
        print(f"Best: {res_sf.best_uci}, Score: {res_sf.score_cp} cp, Mate: {res_sf.mate_in}, Depth: {res_sf.depth}, Nodes: {res_sf.nodes}, Time: {res_sf.seconds:.3f}s")
        print(f"PV: {' '.join(res_sf.pv_uci)}")
    else:
        done_event = threading.Event()
        res_holder = []

        def on_done(res):
            res_holder.append(res)
            done_event.set()

        req_id = svc.submit(req_dict, on_done)
        print(f"Submitted Request #{req_id}...")

        while not done_event.is_set():
            svc.poll()
            time.sleep(0.02)
        svc.poll()

        res = res_holder[0]
        board = chess.Board(args.fen)
        move_san = board.san(chess.Move.from_uci(res.best_uci)) if res.best_uci else "None"

        print(f"Backend Chosen: {res.backend.upper()} ({res.reason})")
        print(f"Best Move: {move_san} ({res.best_uci})")
        print(f"Score: {res.score_cp} cp, Mate: {res.mate_in}")
        print(f"Depth: {res.depth}, Nodes: {res.nodes}, Time: {res.seconds:.3f}s")
        print(f"PV: {' '.join(res.pv_uci)}")

    svc.shutdown()


if __name__ == "__main__":
    main()
