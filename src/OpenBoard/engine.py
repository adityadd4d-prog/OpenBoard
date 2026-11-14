import logging
from enum import IntEnum

import chess
from chess import polyglot as pg


HASH_MOVE_BONUS = 1_000_000
QUEEN_PROMOTION_BONUS = 20_000
CAPTURE_BONUS = 10_000
MATE_SCORE = 10_000
MATE_THRESHOLD = 9_000  #

PAWN_PST = (
    0, 0, 0, 0, 0, 0, 0, 0,
    50, 50, 50, 50, 50, 50, 50, 50,
    10, 10, 20, 30, 30, 20, 10, 10,
    5, 5, 10, 25, 25, 10, 5, 5,
    0, 0, 0, 20, 20, 0, 0, 0,
    5, -5, -10, 0, 0, -10, -5, 5,
    5, 10, 10, -20, -20, 10, 10, 5,
    0, 0, 0, 0, 0, 0, 0, 0,
)

KNIGHT_PST = (
    -50, -40, -30, -30, -30, -30, -40, -50,
    -40, -20, 0, 0, 0, 0, -20, -40,
    -30, 0, 10, 15, 15, 10, 0, -30,
    -30, 5, 15, 20, 20, 15, 5, -30,
    -30, 0, 15, 20, 20, 15, 0, -30,
    -30, 5, 10, 15, 15, 10, 5, -30,
    -40, -20, 0, 5, 5, 0, -20, -40,
    -50, -40, -30, -30, -30, -30, -40, -50,
)

BISHOP_PST = (
    -20, -10, -10, -10, -10, -10, -10, -20,
    -10, 0, 0, 0, 0, 0, 0, -10,
    -10, 0, 5, 10, 10, 5, 0, -10,
    -10, 5, 5, 10, 10, 5, 5, -10,
    -10, 0, 10, 10, 10, 10, 0, -10,
    -10, 10, 10, 10, 10, 10, 10, -10,
    -10, 5, 0, 0, 0, 0, 5, -10,
    -20, -10, -10, -10, -10, -10, -10, -20,
)

ROOK_PST = (
    0, 0, 0, 0, 0, 0, 0, 0,
    5, 10, 10, 10, 10, 10, 10, 5,
    -5, 0, 0, 0, 0, 0, 0, -5,
    -5, 0, 0, 0, 0, 0, 0, -5,
    -5, 0, 0, 0, 0, 0, 0, -5,
    -5, 0, 0, 0, 0, 0, 0, -5,
    -5, 0, 0, 0, 0, 0, 0, -5,
    0, 0, 0, 5, 5, 0, 0, 0,
)

QUEEN_PST = (
    -20, -10, -10, -5, -5, -10, -10, -20,
    -10, 0, 0, 0, 0, 0, 0, -10,
    -10, 0, 5, 5, 5, 5, 0, -10,
    -5, 0, 5, 5, 5, 5, 0, -5,
    0, 0, 5, 5, 5, 5, 0, -5,
    -10, 5, 5, 5, 5, 5, 0, -10,
    -10, 0, 5, 0, 0, 0, 0, -10,
    -20, -10, -10, -5, -5, -10, -10, -20,
)

KING_MIDDLEGAME_PST = (
    -30, -40, -40, -50, -50, -40, -40, -30,
    -30, -40, -40, -50, -50, -40, -40, -30,
    -30, -40, -40, -50, -50, -40, -40, -30,
    -30, -40, -40, -50, -50, -40, -40, -30,
    -20, -30, -30, -40, -40, -30, -30, -20,
    -10, -20, -20, -20, -20, -20, -20, -10,
    20, 20, 0, 0, 0, 0, 20, 20,
    20, 30, 10, 0, 0, 10, 30, 20,
)

KING_ENDGAME_PST = (
    -50, -40, -30, -20, -20, -30, -40, -50,
    -30, -20, -10, 0, 0, -10, -20, -30,
    -30, -10, 20, 30, 30, 20, -10, -30,
    -30, -10, 30, 40, 40, 30, -10, -30,
    -30, -10, 30, 40, 40, 30, -10, -30,
    -30, -10, 20, 30, 30, 20, -10, -30,
    -30, -30, 0, 0, 0, 0, -30, -30,
    -50, -30, -30, -30, -30, -30, -30, -50,
)

PST = {
    chess.PAWN: PAWN_PST,
    chess.KNIGHT: KNIGHT_PST,
    chess.BISHOP: BISHOP_PST,
    chess.ROOK: ROOK_PST,
    chess.QUEEN: QUEEN_PST,
}

# Non-pawn material of both sides at the start: 2 * (2*3 + 2*3.25 + 2*5 + 9)
MAX_PHASE_MATERIAL = 63.0


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

        file_handler = logging.FileHandler("../logs/Engine.log", mode="w", encoding="utf-8")
        file_handler.setLevel(logging.INFO)
        file_formater = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(funcName)-10s | %(message)s",
            datefmt="%d-%m %H:%M:%S"
        )
        file_handler.setFormatter(file_formater)
        self._logger.addHandler(file_handler)

    def evaluate(self, board):
        score = 0.0
        phase_material = 0.0
        king_mg = 0.0
        king_eg = 0.0

        for square, piece in board.piece_map().items():
            piece_type = piece.piece_type
            if piece.color == chess.WHITE:
                sign, idx = 1, square ^ 56
            else:
                sign, idx = -1, square

            if piece_type == chess.KING:
                king_mg += sign * KING_MIDDLEGAME_PST[idx]
                king_eg += sign * KING_ENDGAME_PST[idx]
                continue

            score += sign * (self._values[piece_type] + PST[piece_type][idx] / 100)
            if piece_type != chess.PAWN:
                phase_material += self._values[piece_type]

        # 1.0 = full middlegame, 0.0 = bare endgame; blend the two king tables
        phase = min(phase_material / MAX_PHASE_MATERIAL, 1.0)
        score += (phase * king_mg + (1.0 - phase) * king_eg) / 100

        return score

    def best_move(self, board):
        board = board.copy()
        self._node_cnt = 0

        moves = self.ordered_moves(board)
        if not moves:
            # Game is already over at the root: report it, there is no move.
            if board.is_checkmate():
                score = -MATE_SCORE if board.turn == chess.WHITE else MATE_SCORE
            else:
                score = 0
            return None, score, 0

        maximizing = board.turn == chess.WHITE
        alpha = float("-inf")
        beta = float("inf")

        chosen = moves[0]
        best_score = float("-inf") if maximizing else float("inf")

        for move in moves:
            board.push(move)
            score = self.minmax(board, self._depth - 1, alpha, beta)
            board.pop()

            if maximizing:
                if score > best_score:
                    best_score, chosen = score, move
                alpha = max(alpha, best_score)
            else:
                if score < best_score:
                    best_score, chosen = score, move
                beta = min(beta, best_score)

        return chosen, best_score, self._node_cnt

    @staticmethod
    def _to_tt(score, ply):
        """Root-relative mate score -> node-relative, for storing."""
        if score >= MATE_THRESHOLD:
            return score + ply
        if score <= -MATE_THRESHOLD:
            return score - ply
        return score

    @staticmethod
    def _from_tt(score, ply):
        """Node-relative mate score -> root-relative, for using at this ply."""
        if score >= MATE_THRESHOLD:
            return score - ply
        if score <= -MATE_THRESHOLD:
            return score + ply
        return score

    def minmax(self, board, depth, alpha, beta):

        self._node_cnt += 1

        ply = self.depth - depth

        board_hash = pg.zobrist_hash(board)
        if board_hash in self.__trans_table:
            score, hash_depth, flag = self.__trans_table[board_hash]
            if hash_depth >= depth:
                score = self._from_tt(score, ply)
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
                return (-MATE_SCORE + ply) if board.turn == chess.WHITE else (MATE_SCORE - ply)

        # Base Condition
        if depth == 0:
            return self.evaluate(board)

        org_alpha = alpha
        org_beta = beta

        # Maximizer
        if board.turn == chess.WHITE:
            best_score = float("-inf")
            for move in self.ordered_moves(board):
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
            for move in self.ordered_moves(board):
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

        self.__trans_table[board_hash] = (self._to_tt(best_score, ply), depth, fl)

        return best_score

    def ordered_moves(self, board, hash_move=None):
        scored = []

        for move in board.legal_moves:
            score = 0

            if move == hash_move:
                score += HASH_MOVE_BONUS

            if move.promotion == chess.QUEEN:
                score += QUEEN_PROMOTION_BONUS

            if board.is_capture(move):
                # En passant: the destination square is empty, the victim is a pawn.
                if board.is_en_passant(move):
                    victim = chess.PAWN
                else:
                    victim = board.piece_type_at(move.to_square)
                attacker = board.piece_type_at(move.from_square)
                score += CAPTURE_BONUS + 10 * victim - attacker

            scored.append((score, move))

        # sort is stable, so equal scores keep generation order
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [move for _, move in scored]


