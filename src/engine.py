import logging
from enum import IntEnum

import chess
from chess import polyglot as pg

class Flag(IntEnum):
    EXACT = 0
    ALPHA = 1
    BETA = 2

class Engine:

    def __init__(self, depth = 2):
        self._values = {
                chess.PAWN : 1,
                chess.KNIGHT : 3,
                chess.BISHOP : 3.25,
                chess.ROOK : 5,
                chess.QUEEN : 9,
                chess.KING : 0
                      }
        self._setup_logger()
        self.depth = depth
        self.__trans_table = {}
        self._node_cnt = 0

    @property
    def depth(self):
        return self._depth

    @depth.setter
    def depth(self, depth):
        if depth <= 1:
            self._depth = 2
        else:
            self._depth = depth

    def _setup_logger(self):
        self._logger = logging.getLogger()
        self._logger.setLevel(logging.INFO)

        file_handler = logging.FileHandler("Engine.log", mode="w", encoding="utf-8")
        file_handler.setLevel(logging.INFO)
        file_formater = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(funcName)-10s | %(message)s",
            datefmt="%d-%m %H:%M:%S"
        )
        file_handler.setFormatter(file_formater)
        self._logger.addHandler(file_handler)


    def evaluate(self, board):
        score = 0

        for square, piece in board.piece_map().items():
            value = self._values[piece.piece_type]
            if piece.color == chess.WHITE:
                score += value
            else:
                score -= value

        return score

    def best_move(self, board):
        best_move = None
        self._node_cnt = 0

        alpha = float("-inf")
        beta = float("inf")

        if board.turn == chess.WHITE:
            best_score = float("-inf")
            for move in board.legal_moves:
                board.push(move)
                score = self.minmax(board, self._depth -1, alpha, beta)
                board.pop()
                # self._logger.info(f"{move} | {score} | {self._node_cnt}")
                if score > best_score:
                    best_move = move
                best_score = max(best_score, score)
                alpha = max(alpha, best_score)

        else:
            best_score = float("inf")
            for move in board.legal_moves:
                board.push(move)
                score = self.minmax(board, self._depth -1, alpha, beta)
                board.pop()
                # self._logger.info(f"{move} | {score} | {self._node_cnt}")
                if score < best_score:
                    best_move = move
                best_score = min(best_score, score)
                beta = min(beta, best_score)

        return best_move, best_score, self._node_cnt

    def minmax(self, board, depth, alpha, beta):

        self._node_cnt += 1

        board_hash = pg.zobrist_hash(board)
        if board_hash in self.__trans_table:
            score, hash_depth, flag = self.__trans_table[board_hash]
            if hash_depth >= depth:
                if flag == Flag.EXACT:
                    return score
                elif flag == Flag.ALPHA and score <= alpha:
                    return score
                elif flag == Flag.BETA and score >= beta:
                    return score

        # Checking Game Status
        if not bool(board.legal_moves):

            if board.is_stalemate():
                return 0

            if board.is_checkmate():
                return (-10000 - (self.depth - depth)) if board.turn == chess.WHITE else (10000 + (self.depth - depth))

        # Base Condition
        if depth == 0:
            return self.evaluate(board)

        org_alpha = alpha
        org_beta = beta

        # Maximizer
        if board.turn == chess.WHITE:
            best_score = float("-inf")
            for move in board.legal_moves:
                board.push(move)
                score = self.minmax(board, depth - 1, alpha, beta)
                board.pop()
                best_score = max(best_score, score)
                alpha = max(score, alpha)
                if beta <= alpha:
                    break
                if self._logger.isEnabledFor(logging.DEBUG):
                    self._logger.debug(f"{move} : {score}")

        # Minimizer
        else:
            best_score = float("inf")
            for move in board.legal_moves:
                board.push(move)
                score = self.minmax(board, depth - 1, alpha, beta)
                board.pop()
                best_score = min(best_score, score)
                beta = min(beta, score)
                if alpha >= beta:
                    break
                if self._logger.isEnabledFor(logging.DEBUG):
                    self._logger.debug(f"{move} : {score}")

        if best_score <= org_alpha:
            fl = Flag.ALPHA
        elif best_score >= org_beta:
            fl = Flag.BETA
        else:
            fl = Flag.EXACT

        self.__trans_table[board_hash] = (best_score, self.depth - depth, fl)

        return best_score



