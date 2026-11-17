"""
demos/console_game.py
~~~~~~~~~~~~~~~~~~~~~
Terminal chess game against the engine.
"""

from __future__ import annotations

import argparse
import sys
import threading
import time

import chess

from openboard import config
from openboard.core.clock import ChessClock, format_clock
from openboard.core.results import GameOutcome, Reason, build_pgn, outcome_from_board
from openboard.engines.service import EngineService
from openboard.storage.settings import Settings


def main() -> None:
    parser = argparse.ArgumentParser(description="OpenBoard Console Chess")
    parser.add_argument("--level", "-l", type=int, default=1, choices=range(1, 9), help="Engine level 1-8")
    parser.add_argument("--time", "-t", type=str, default="rapid", choices=["blitz", "rapid"], help="Time control")
    args = parser.parse_args()

    settings = Settings()
    svc = EngineService(settings)
    svc.start()
    time.sleep(0.3)

    tc = config.TIME_CONTROLS[args.time]
    clock = ChessClock(tc)
    clock.start(chess.WHITE)

    board = chess.Board()
    san_moves: list[str] = []
    backends_used: list[str] = []

    print(f"=== OpenBoard Console Game vs Level {args.level} ===")
    print(f"Time Control: {tc.label}")
    print("Type moves in SAN (e.g. e4, Nf3, O-O). Type 'quit' or 'resign' to exit.\n")

    outcome: GameOutcome | None = None

    while not board.is_game_over() and not outcome:
        clock.update()
        flagged = clock.flagged()
        if flagged is not None:
            winner = chess.BLACK if flagged == chess.WHITE else chess.WHITE
            outcome = GameOutcome(winner=winner, reason=Reason.TIMEOUT)
            break

        print(board.unicode())
        print(f"Clock: White [{format_clock(clock.remaining(chess.WHITE))}]  Black [{format_clock(clock.remaining(chess.BLACK))}]")

        if board.turn == chess.WHITE:
            # Human move
            while True:
                clock.update()
                try:
                    user_input = input("White move > ").strip()
                except (EOFError, KeyboardInterrupt):
                    outcome = GameOutcome(winner=chess.BLACK, reason=Reason.ABANDONED)
                    break

                if user_input.lower() in ("quit", "exit"):
                    outcome = GameOutcome(winner=chess.BLACK, reason=Reason.ABANDONED)
                    break
                if user_input.lower() == "resign":
                    outcome = GameOutcome(winner=chess.BLACK, reason=Reason.RESIGNATION)
                    break

                try:
                    move = board.parse_san(user_input)
                    san = board.san(move)
                    board.push(move)
                    san_moves.append(san)
                    clock.press(chess.WHITE)
                    break
                except Exception as exc:
                    print(f"Invalid move: {exc}. Try again.")

            if outcome:
                break
        else:
            # Engine move
            print(f"Engine is thinking (Level {args.level})...")
            done_event = threading.Event()
            res_holder = []

            def on_done(res):
                res_holder.append(res)
                done_event.set()

            req_id = svc.submit(
                {"fen": board.fen(), "purpose": "play", "level": args.level, "time_s": 5.0},
                on_done,
            )

            while not done_event.is_set():
                clock.update()
                if clock.flagged() == chess.BLACK:
                    outcome = GameOutcome(winner=chess.WHITE, reason=Reason.TIMEOUT)
                    svc.cancel(req_id)
                    break
                svc.poll()
                time.sleep(0.05)

            if outcome:
                break

            svc.poll()
            res = res_holder[0]
            backends_used.append(res.backend)
            engine_move = chess.Move.from_uci(res.best_uci)
            san = board.san(engine_move)
            board.push(engine_move)
            san_moves.append(san)
            clock.press(chess.BLACK)
            print(f"Black plays: {san} (answered by {res.backend.upper()}: {res.reason})\n")

    if not outcome:
        outcome = outcome_from_board(board)

    print("\n=== GAME OVER ===")
    if outcome:
        print(f"Result: {outcome.result_string} ({outcome.headline})")

    pgn = build_pgn(
        white="Human",
        black=f"Engine (Level {args.level})",
        outcome=outcome or GameOutcome(winner=None, reason=Reason.ABANDONED),
        moves=san_moves,
        start_fen=None,
        time_control_label=tc.label,
        date=time.strftime("%Y.%m.%d"),
    )
    print("\n--- PGN ---")
    print(pgn)

    svc.shutdown()


if __name__ == "__main__":
    main()
