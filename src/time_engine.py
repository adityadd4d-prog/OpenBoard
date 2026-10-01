import chess
import engine
import time

import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

file_handler = logging.FileHandler("time_engine.log", mode="w", encoding="utf-8")
file_handler.setLevel(logging.INFO)
file_formater = logging.Formatter(
    "%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%d-%m %H:%M:%S"
)
file_handler.setFormatter(file_formater)
logger.addHandler(file_handler)

positions = [
    "6k1/5ppp/8/8/8/8/5PPP/4R1K1 w - - 0 1",
    "r1b1kb1r/pppp1ppp/2n2n2/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR w KQkq - 4 4",
    "7k/5Q2/6K1/8/8/8/8/8 b - - 0 1",
    "4k3/8/8/8/8/8/4q3/4K3 w - - 0 1",
    "r1b2rk1/ppp2ppp/2n5/2bqp3/8/2NP1N2/PPP1QPPP/R1B2RK1 w - - 0 10",
    "8/8/8/8/8/5K2/7P/7k w - - 0 1",
    "r2qkb1r/pp2nppp/3p4/2pNN1B1/2BnP3/3P4/PPP2PPP/R2QK2R w KQkq - 1 0",
    "r1bqkbnr/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R b KQkq - 3 2"
             ]
logger.info("======= Cold Start =======")
for depth in range(1, 7):
    logger.info(f"Depth Level :- {depth}")
    for pos in positions:
        start = time.time()
        eng = engine.Engine()
        eng.depth = depth
        board = chess.Board(pos)
        move, score, cnt = eng.best_move(board)
        logger.info(f"{move} | {score} | {cnt} | {time.time() - start:.2f}")
        print(f"{move} | {score} | {cnt} | {time.time() - start:.2f}")


logger.info("======= Transposition Table =======")
for pos in positions:
    logger.info(f"Position :- {pos}")
    eng = engine.Engine()
    for depth in range(1, 7):
        start = time.time()
        eng.depth = depth
        board = chess.Board(pos)
        move, score, cnt = eng.best_move(board)
        logger.info(f"{depth} | {move} | {score} | {cnt} | {time.time() - start:.2f}")
        print(f"{move} | {score} | {cnt} | {time.time() - start:.2f}")
