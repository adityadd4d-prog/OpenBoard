"""
OpenBoard chess engine.

Search:  minimax with alpha-beta (White maximises, Black minimises), iterative
         deepening with a time limit and a stop flag, quiescence search,
         transposition table (with best move), move ordering (hash move,
         MVV-LVA, killers, history), draw detection (insufficient material,
         fifty-move rule, repetition).
Eval:    material + piece-square tables, king table tapered by game phase.
Extras:  small opening book, five difficulty levels, named logger.

Scores are in pawn units from WHITE's point of view (positive = White ahead).
Forced mates are +/- (MATE_SCORE - ply), so faster mates score higher.

Public API:
    engine = Engine(depth=2, level=None)
    engine.best_move(board, time_limit=None, stop_event=None) -> (move, score, nodes)
    engine.evaluate(board)          -> static score (White's point of view)
    engine.new_game()               -> clears table, killers, history
    engine.set_level(1..5)          -> difficulty preset (clears the table)
    engine.depth                    -> maximum search depth (property)
    engine.info                     -> details of the last search (dict)

`best_move` searches a COPY of the board, so the caller's board is never
touched, and it is safe to call from a worker thread/process.
"""

import logging
import random
import time
from enum import IntEnum
from pathlib import Path

import chess
from chess import polyglot as pg


# --------------------------------------------------------------------------
# Constants
# --------------------------------------------------------------------------

MATE_SCORE = 10_000
MATE_THRESHOLD = 9_000      # |score| above this means "forced mate"
INF = float("inf")

MAX_PLY = 128               # size of the killer table
QS_MAX_PLY = 10             # quiescence search depth limit

HASH_MOVE_BONUS = 1_000_000
QUEEN_PROMOTION_BONUS = 20_000
CAPTURE_BONUS = 10_000
KILLER_BONUS = (9_000, 8_000)
HISTORY_CAP = 7_000         # keeps quiet-move history below the killers

# Non-pawn material of both sides at the start: 2 * (2*3 + 2*3.25 + 2*5 + 9)
MAX_PHASE_MATERIAL = 63.0

# --- piece-square tables (centipawns) ---------------------------------------
# Written the way you read a board: rank 8 first, so index 0 = a8.
#   White piece on square sq -> index  sq ^ 56
#   Black piece on square sq -> index  sq
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

# Difficulty presets.  depth = maximum depth, time = seconds per move (None =
# no limit), margin = Black/White may pick any root move whose score is within
# this many pawns of the best one (0 = always the best move).
LEVELS = {
    1: {"depth": 1, "time": None, "margin": 1.50},
    2: {"depth": 2, "time": None, "margin": 0.75},
    3: {"depth": 3, "time": None, "margin": 0.30},
    4: {"depth": 4, "time": 3.0, "margin": 0.10},
    5: {"depth": 8, "time": 5.0, "margin": 0.00},
}

# Small opening book: UCI lines. Positions are matched by Zobrist hash, so
# transpositions into a line are recognised too.
BOOK_LINES = (
    "e2e4 e7e5 g1f3 b8c6 f1b5 a7a6 b5a4 g8f6 e1g1 f8e7",     # Ruy Lopez
    "e2e4 e7e5 g1f3 b8c6 f1c4 f8c5 c2c3 g8f6 d2d3",           # Italian
    "e2e4 e7e5 g1f3 g8f6 f3e5 d7d6 e5f3 f6e4",                # Petroff
    "e2e4 c7c5 g1f3 d7d6 d2d4 c5d4 f3d4 g8f6 b1c3 a7a6",      # Sicilian Najdorf
    "e2e4 c7c5 g1f3 b8c6 d2d4 c5d4 f3d4 g8f6 b1c3 e7e5",      # Sicilian Sveshnikov
    "e2e4 e7e6 d2d4 d7d5 b1c3 g8f6 c1g5 f8e7",                # French
    "e2e4 c7c6 d2d4 d7d5 b1c3 d5e4 c3e4 c8f5",                # Caro-Kann
    "e2e4 d7d5 e4d5 d8d5 b1c3 d5a5",                          # Scandinavian
    "d2d4 d7d5 c2c4 e7e6 b1c3 g8f6 c1g5 f8e7",                # Queen's Gambit Declined
    "d2d4 g8f6 c2c4 e7e6 b1c3 f8b4",                          # Nimzo-Indian
    "d2d4 g8f6 c2c4 g7g6 b1c3 f8g7 e2e4 d7d6",                # King's Indian
    "g1f3 d7d5 g2g3 g8f6 f1g2 e7e6 e1g1",                     # Reti
    "c2c4 e7e5 b1c3 g8f6 g1f3 b8c6",                          # English
)

DEFAULT_LOG_PATH = Path(__file__).resolve().parents[2] / "logs" / "Engine.log"

log = logging.getLogger("openboard.engine")
log.addHandler(logging.NullHandler())


def setup_file_logging(path=None, level=logging.INFO):
    """Attach a file handler to the engine logger (once per file).

    Creates the folder if needed and returns the handler, or None if the file
    cannot be opened (the engine keeps working without a log).
    """
    path = Path(path) if path else DEFAULT_LOG_PATH
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        target = str(path.resolve())
        for handler in log.handlers:
            if isinstance(handler, logging.FileHandler) and handler.baseFilename == target:
                return handler
        handler = logging.FileHandler(target, mode="a", encoding="utf-8")
    except OSError:
        return None
    handler.setFormatter(logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(funcName)-12s | %(message)s",
        datefmt="%d-%m %H:%M:%S",
    ))
    log.addHandler(handler)
    log.setLevel(level)
    return handler


# --------------------------------------------------------------------------
# Transposition table
# --------------------------------------------------------------------------

class Flag(IntEnum):
    EXACT = 0   # score is exact
    ALPHA = 1   # score is an upper bound (the node failed low)
    BETA = 2    # score is a lower bound (the node failed high)


EXACT, ALPHA, BETA = Flag.EXACT, Flag.ALPHA, Flag.BETA


def _to_tt(score, ply):
    """Root-relative mate score -> node-relative, for storing."""
    if score >= MATE_THRESHOLD:
        return score + ply
    if score <= -MATE_THRESHOLD:
        return score - ply
    return score


def _from_tt(score, ply):
    """Node-relative mate score -> root-relative, for using at this ply."""
    if score >= MATE_THRESHOLD:
        return score - ply
    if score <= -MATE_THRESHOLD:
        return score + ply
    return score


class TranspositionTable:
    """Zobrist key -> (score, remaining depth, flag, best move).

    Two generations: when the current one is full it becomes the old one and
    the previous old one is dropped, so memory is bounded by `max_entries`
    and eviction is O(1).  `max_entries=0` disables the table.
    Mate scores are stored node-relative and converted back on probe.
    """

    def __init__(self, max_entries=200_000):
        self.enabled = max_entries > 0
        self._per_gen = max(1, max_entries // 2)
        self._cur = {}
        self._old = {}
        self.reset_stats()

    def reset_stats(self):
        self.probes = 0
        self.hits = 0
        self.stores = 0
        self.evictions = 0

    def clear(self):
        self._cur = {}
        self._old = {}

    def __len__(self):
        return len(self._cur) + len(self._old)

    def probe(self, key, ply):
        """Return (score, depth, flag, move) with the score converted to `ply`, or None."""
        if not self.enabled:
            return None
        self.probes += 1
        entry = self._cur.get(key)
        if entry is None:
            entry = self._old.get(key)
            if entry is None:
                return None
        self.hits += 1
        score, depth, flag, move = entry
        return _from_tt(score, ply), depth, flag, move

    def store(self, key, score, depth, flag, move, ply):
        if not self.enabled:
            return
        cur = self._cur
        prev = cur.get(key)
        if prev is not None:
            if prev[1] > depth:
                return                      # keep the deeper entry
            if move is None:
                move = prev[3]              # keep a known best move
        elif len(cur) >= self._per_gen:
            self.evictions += len(self._old)
            self._old = cur
            self._cur = cur = {}
        cur[key] = (_to_tt(score, ply), depth, flag, move)
        self.stores += 1

    def stats(self):
        return {
            "size": len(self),
            "capacity": self._per_gen * 2,
            "probes": self.probes,
            "hits": self.hits,
            "stores": self.stores,
            "evictions": self.evictions,
            "hit_rate": (self.hits / self.probes) if self.probes else 0.0,
        }


class _SearchStopped(Exception):
    """Raised inside the search when the time limit or stop flag triggers."""


# --------------------------------------------------------------------------
# Engine
# --------------------------------------------------------------------------

class Engine:

    def __init__(self, depth=2, level=None, tt_size=200_000, use_book=True,
                 seed=None, log_to_file=True):
        self._values = {
            chess.PAWN: 1,
            chess.KNIGHT: 3,
            chess.BISHOP: 3.25,
            chess.ROOK: 5,
            chess.QUEEN: 9,
            chess.KING: 0,
        }
        if log_to_file:
            setup_file_logging()

        self._rng = random.Random(seed)
        self._tt = TranspositionTable(tt_size)
        self._killers = [[None, None] for _ in range(MAX_PLY)]
        self._history = [[0] * 4096, [0] * 4096]    # [colour][from * 64 + to]
        self._book = self._build_book()
        self._use_book = use_book

        self._time_limit = None
        self._margin = 0.0
        self._level = None
        self.depth = depth
        if level is not None:
            self.set_level(level)

        self._node_cnt = 0
        self._root_best = None
        self._deadline = None
        self._stop_event = None
        self._can_stop = False
        self.info = {}

    # ---- configuration ---------------------------------------------------

    @property
    def depth(self):
        return self._depth

    @depth.setter
    def depth(self, depth):
        self._depth = max(1, int(depth))

    @property
    def level(self):
        return self._level

    def set_level(self, level):
        """Apply a difficulty preset (1 = weakest, 5 = strongest) and clear the table."""
        level = min(max(int(level), 1), max(LEVELS))
        preset = LEVELS[level]
        self._level = level
        self.depth = preset["depth"]
        self._time_limit = preset["time"]
        self._margin = preset["margin"]
        self.new_game()

    def new_game(self):
        """Forget everything learned during the previous game."""
        self._tt.clear()
        self._tt.reset_stats()
        self._killers = [[None, None] for _ in range(MAX_PLY)]
        self._history = [[0] * 4096, [0] * 4096]
        self._root_best = None

    # ---- opening book ----------------------------------------------------

    @staticmethod
    def _build_book():
        book = {}
        for line in BOOK_LINES:
            board = chess.Board()
            for uci in line.split():
                move = chess.Move.from_uci(uci)
                candidates = book.setdefault(pg.zobrist_hash(board), [])
                if move not in candidates:
                    candidates.append(move)
                board.push(move)
        return book

    def _book_move(self, board, legal_moves):
        candidates = self._book.get(pg.zobrist_hash(board))
        if not candidates:
            return None
        playable = [m for m in candidates if m in legal_moves]
        return self._rng.choice(playable) if playable else None

    # ---- evaluation ------------------------------------------------------

    def evaluate(self, board):
        """Static evaluation in pawns, from White's point of view."""
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

    # ---- public search entry point ----------------------------------------

    def best_move(self, board, time_limit=None, stop_event=None):
        """Return (move, score, nodes) for the side to move.

        time_limit  seconds for this search (default: the level's limit, or
                    none, in which case the search runs to `self.depth`)
        stop_event  anything with .is_set() (threading/multiprocessing Event);
                    when set, the search returns the best move found so far

        Depth 1 always completes, so a legal move is always returned (None only
        when the game is already over).  Iterative deepening runs depth 1..
        `self.depth`; an unfinished iteration is thrown away.
        """
        started = time.perf_counter()
        board = board.copy()
        self._node_cnt = 0
        self._stop_event = stop_event
        limit = self._time_limit if time_limit is None else time_limit
        self._deadline = started + limit if limit else None
        self._tt.reset_stats()
        self._reset_search_tables()

        moves = list(board.legal_moves)
        if not moves:
            score = self._mated_score(board, 0) if board.is_check() else 0.0
            self.info = {"depth": 0, "nodes": 0, "seconds": 0.0, "score": score,
                         "book": False, "tt": self._tt.stats()}
            return None, score, 0

        if self._use_book:
            book_move = self._book_move(board, moves)
            if book_move is not None:
                score = self.evaluate(board)
                self.info = {"depth": 0, "nodes": 0, "seconds": 0.0, "score": score,
                             "book": True, "tt": self._tt.stats()}
                log.info("book move %s", book_move)
                return book_move, score, 0

        chosen, score = moves[0], 0.0
        completed = 0
        self._root_best = None

        for depth in range(1, self._depth + 1):
            self._can_stop = depth > 1          # always finish depth 1
            try:
                best, best_score, pool = self._search_root(board, moves, depth)
            except _SearchStopped:
                break

            self._root_best = best
            chosen, score = best, best_score
            if self._margin > 0 and len(pool) > 1:
                chosen, score = self._rng.choice(pool)
            completed = depth

            elapsed = time.perf_counter() - started
            log.debug("depth %d | %s | %.2f | %d nodes | %.2fs",
                      depth, best, best_score, self._node_cnt, elapsed)

            if len(moves) == 1 or abs(best_score) >= MATE_THRESHOLD:
                break                           # forced move / proven mate
            if limit and elapsed > 0.5 * limit:
                break                           # the next iteration would not finish

        self._can_stop = False
        elapsed = time.perf_counter() - started
        self.info = {"depth": completed, "nodes": self._node_cnt, "seconds": elapsed,
                     "score": score, "book": False, "tt": self._tt.stats()}
        log.info("%s | score %.2f | depth %d | %d nodes | %.2fs",
                 chosen, score, completed, self._node_cnt, elapsed)
        return chosen, score, self._node_cnt

    # ---- search ----------------------------------------------------------

    def _reset_search_tables(self):
        self._killers = [[None, None] for _ in range(MAX_PLY)]
        for table in self._history:             # age the history instead of wiping it
            for i, value in enumerate(table):
                if value:
                    table[i] = value >> 1

    def _tick(self):
        self._node_cnt += 1
        if self._can_stop and (self._node_cnt & 255) == 0:
            if self._stop_event is not None and self._stop_event.is_set():
                raise _SearchStopped
            if self._deadline is not None and time.perf_counter() >= self._deadline:
                raise _SearchStopped

    @staticmethod
    def _mated_score(board, ply):
        """Score of a checkmated position for the side to move."""
        return (-MATE_SCORE + ply) if board.turn == chess.WHITE else (MATE_SCORE - ply)

    @staticmethod
    def _is_draw(board):
        """Draws by rule, below the root. Checkmate takes precedence over the fifty-move rule."""
        if board.halfmove_clock >= 100 and board.is_fifty_moves():
            return True
        if board.occupied.bit_count() <= 4 and board.is_insufficient_material():
            return True
        # a position that has occurred before (once is enough inside the search)
        if board.halfmove_clock >= 4 and board.is_repetition(2):
            return True
        return False

    def _search_root(self, board, moves, depth):
        """Search every root move to `depth`.

        Returns (best_move, best_score, pool) where pool is a list of
        (move, exact score) for all moves within `margin` of the best one.
        With margin 0 the root window is the usual alpha-beta window and the
        pool only holds the best move.
        """
        maximizing = board.turn == chess.WHITE
        margin = self._margin
        ordered = self._order_moves(board, moves, 0, self._root_best)

        alpha, beta = -INF, INF
        best, best_score = ordered[0], (-INF if maximizing else INF)
        scored = []

        for move in ordered:
            board.push(move)
            score = self._search(board, depth - 1, 1, alpha, beta)
            board.pop()

            if maximizing:
                if score > alpha:               # inside the window: exact
                    scored.append((move, score))
                if score > best_score:
                    best, best_score = move, score
                alpha = max(alpha, best_score - margin)
            else:
                if score < beta:
                    scored.append((move, score))
                if score < best_score:
                    best, best_score = move, score
                beta = min(beta, best_score + margin)

        if margin > 0:
            if maximizing:
                pool = [(m, s) for m, s in scored if s >= best_score - margin]
            else:
                pool = [(m, s) for m, s in scored if s <= best_score + margin]
        else:
            pool = [(best, best_score)]
        return best, best_score, pool

    def _search(self, board, depth, ply, alpha, beta):
        """Alpha-beta below the root. Returns a score from White's point of view."""
        self._tick()

        if self._is_draw(board):
            return 0.0
        if depth <= 0:
            return self._quiesce(board, alpha, beta, ply, 0)

        key = pg.zobrist_hash(board)
        hash_move = None
        entry = self._tt.probe(key, ply)
        if entry is not None:
            tt_score, tt_depth, tt_flag, hash_move = entry
            if tt_depth >= depth:
                if tt_flag == EXACT:
                    return tt_score
                if tt_flag == ALPHA and tt_score <= alpha:
                    return tt_score
                if tt_flag == BETA and tt_score >= beta:
                    return tt_score

        moves = list(board.legal_moves)
        if not moves:
            return self._mated_score(board, ply) if board.is_check() else 0.0

        org_alpha, org_beta = alpha, beta
        best_move = None

        if board.turn == chess.WHITE:
            best_score = -INF
            for move in self._order_moves(board, moves, ply, hash_move):
                board.push(move)
                score = self._search(board, depth - 1, ply + 1, alpha, beta)
                board.pop()
                if score > best_score:
                    best_score, best_move = score, move
                if best_score > alpha:
                    alpha = best_score
                if alpha >= beta:
                    self._record_cutoff(board, move, ply, depth)
                    break
        else:
            best_score = INF
            for move in self._order_moves(board, moves, ply, hash_move):
                board.push(move)
                score = self._search(board, depth - 1, ply + 1, alpha, beta)
                board.pop()
                if score < best_score:
                    best_score, best_move = score, move
                if best_score < beta:
                    beta = best_score
                if alpha >= beta:
                    self._record_cutoff(board, move, ply, depth)
                    break

        if best_score <= org_alpha:
            flag, best_move = ALPHA, None       # nothing is known to be best
        elif best_score >= org_beta:
            flag = BETA
        else:
            flag = EXACT
        self._tt.store(key, best_score, depth, flag, best_move, ply)
        return best_score

    def _quiesce(self, board, alpha, beta, ply, qply):
        """Search captures (and queen promotions) until the position is quiet.

        When in check every evasion is searched and standing pat is not
        allowed. Stalemate/checkmate are detected at the first quiescence node
        (the search horizon); deeper in the capture chain only check evasions
        can be mated.
        """
        self._tick()

        if board.occupied.bit_count() <= 4 and board.is_insufficient_material():
            return 0.0

        in_check = board.is_check()
        maximizing = board.turn == chess.WHITE

        if in_check:
            candidates = list(board.legal_moves)
            if not candidates:
                return self._mated_score(board, ply)
            if qply >= QS_MAX_PLY:
                return self.evaluate(board)
            best_score = -INF if maximizing else INF
        else:
            if qply == 0 and not board.legal_moves:
                return 0.0                      # stalemate
            stand_pat = self.evaluate(board)
            if qply >= QS_MAX_PLY:
                return stand_pat
            if maximizing:
                if stand_pat >= beta:
                    return stand_pat
                alpha = max(alpha, stand_pat)
            else:
                if stand_pat <= alpha:
                    return stand_pat
                beta = min(beta, stand_pat)
            best_score = stand_pat
            candidates = self._noisy_moves(board)

        candidates.sort(key=lambda m: self._capture_score(board, m), reverse=True)

        if maximizing:
            for move in candidates:
                board.push(move)
                score = self._quiesce(board, alpha, beta, ply + 1, qply + 1)
                board.pop()
                if score > best_score:
                    best_score = score
                if best_score > alpha:
                    alpha = best_score
                if alpha >= beta:
                    break
        else:
            for move in candidates:
                board.push(move)
                score = self._quiesce(board, alpha, beta, ply + 1, qply + 1)
                board.pop()
                if score < best_score:
                    best_score = score
                if best_score < beta:
                    beta = best_score
                if alpha >= beta:
                    break
        return best_score

    # ---- move ordering ----------------------------------------------------

    @staticmethod
    def _noisy_moves(board):
        """Legal captures plus queen promotions (no under-promotions)."""
        moves = [m for m in board.generate_legal_captures()
                 if m.promotion is None or m.promotion == chess.QUEEN]
        seventh = chess.BB_RANK_7 if board.turn == chess.WHITE else chess.BB_RANK_2
        pawns = board.pieces_mask(chess.PAWN, board.turn) & seventh
        if pawns:
            for m in board.generate_legal_moves(from_mask=pawns):
                if m.promotion == chess.QUEEN and not board.is_capture(m):
                    moves.append(m)
        return moves

    @staticmethod
    def _capture_score(board, move):
        """Queen promotions, then captures by MVV-LVA (victim value first)."""
        score = 0
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
        return score

    def _order_moves(self, board, moves, ply, hash_move=None):
        """Hash move, promotions/captures (MVV-LVA), killers, then history."""
        killers = self._killers[ply] if ply < MAX_PLY else (None, None)
        history = self._history[board.turn]
        scored = []

        for move in moves:
            if move == hash_move:
                score = HASH_MOVE_BONUS
            else:
                score = self._capture_score(board, move)
                if score == 0:                  # quiet move
                    if move == killers[0]:
                        score = KILLER_BONUS[0]
                    elif move == killers[1]:
                        score = KILLER_BONUS[1]
                    else:
                        score = min(history[move.from_square * 64 + move.to_square],
                                    HISTORY_CAP)
            scored.append((score, move))

        # sort is stable, so equal scores keep generation order
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [move for _, move in scored]

    def _record_cutoff(self, board, move, ply, depth):
        """A quiet move caused a beta cutoff: remember it as a killer and in the history."""
        if board.is_capture(move) or move.promotion:
            return
        if ply < MAX_PLY:
            killers = self._killers[ply]
            if killers[0] != move:
                killers[1] = killers[0]
                killers[0] = move
        self._history[board.turn][move.from_square * 64 + move.to_square] += depth * depth
