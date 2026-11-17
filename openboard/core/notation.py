"""
openboard.core.notation
~~~~~~~~~~~~~~~~~~~~~~~
Input detection, position parsing, and SAN formatting.  No pygame.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

import chess
import chess.pgn

log = logging.getLogger("openboard.core.notation")

# ---------------------------------------------------------------------------
# Helpers / regexes
# ---------------------------------------------------------------------------

_RESULT_TOKENS: frozenset[str] = frozenset({"1-0", "0-1", "1/2-1/2", "*"})

# Strip {comment}, (variation), ;line-comment, $NAG, !?+#= annotation marks,
# result tokens, and move numbers like "1." "1..." "12."
_STRIP_RE = re.compile(
    r"\{[^}]*\}"           # block comments
    r"|\([^)]*\)"          # single-level variations
    r"|;[^\n]*"            # line comments
    r"|\$\d+"              # NAGs
    r"|[!?]+"              # annotation glyphs
    r"|\d+\.{1,3}"         # move numbers  "1." "1..."
    r"|1-0|0-1|1/2-1/2|\*" # result tokens
    r"|[+#]"               # check/mate marks (keep = for promotion like e7e8=Q)
)

_LAN_PIECE_RE = re.compile(
    r"^[KQRBN]?[a-h][1-8][-x]?[a-h][1-8](?:=[QRBN])?$"
    r"|^O-O(?:-O)?$"
    r"|^0-0(?:-0)?$"
)

_FEN_RE = re.compile(
    r"^[prnbqkPRNBQK1-8/]{15,}\s"  # board part
    r"[wb]\s"                        # side to move
    r"[KQkq-]+\s"                   # castling
    r"[a-h1-8-]+\s"                  # en-passant
    r"\d+\s\d+\s*$"                  # halfmove / fullmove
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def detect_input_type(text: str) -> str:
    """Detect whether *text* looks like a FEN, LAN, or SAN move-list.

    Args:
        text: Raw input string from the user.

    Returns:
        One of ``'fen'``, ``'lan'``, or ``'san'``.
    """
    stripped = text.strip()

    # FEN: 5-6 space-separated fields AND first field has 7+ slashes
    parts = stripped.split()
    if 5 <= len(parts) <= 6:
        slashes = parts[0].count("/")
        if slashes >= 7:
            return "fen"

    # LAN: contains move-like tokens with hyphens (e2-e4, Ng1-f3)
    # Look for at least one hyphen in a move-like context.
    # Piece moves like Ng1-f3: uppercase piece letter + from_sq + hyphen + to_sq
    if re.search(r"(?:^|\s)[KQRBN]?[a-h][1-8]-[a-h][1-8]", stripped):
        return "lan"

    return "san"


class NotationError(Exception):
    """Raised when a position or move cannot be parsed.

    Attributes:
        message: Human-readable description of the problem.
        ply: 0-based ply index where the error occurred, or ``None``.
    """

    def __init__(self, message: str, ply: int | None = None) -> None:
        super().__init__(message)
        self.message: str = message
        self.ply: int | None = ply


@dataclass
class ParsedPosition:
    """Result of a successful :func:`parse_position` call.

    Attributes:
        start_fen: FEN of the starting position.
        board: :class:`chess.Board` after all moves have been applied.
        uci_moves: Moves in UCI notation, in order.
        san_moves: Moves in SAN notation, in order.
    """

    start_fen: str
    board: chess.Board
    uci_moves: list[str] = field(default_factory=list)
    san_moves: list[str] = field(default_factory=list)


def parse_position(text: str, kind: str = "auto") -> ParsedPosition:
    """Parse a chess position from *text*.

    Args:
        text: A FEN string, SAN move list, or LAN move list.
        kind: ``'auto'``, ``'fen'``, ``'san'``, or ``'lan'``.  When
            ``'auto'``, :func:`detect_input_type` is used.

    Returns:
        A :class:`ParsedPosition` on success.

    Raises:
        NotationError: When the input is invalid.
    """
    if kind == "auto":
        kind = detect_input_type(text)

    if kind == "fen":
        return _parse_fen(text.strip())
    elif kind == "lan":
        return _parse_moves(text, lan=True)
    else:
        return _parse_moves(text, lan=False)


# ---------------------------------------------------------------------------
# Internal parsers
# ---------------------------------------------------------------------------

def _parse_fen(fen: str) -> ParsedPosition:
    """Parse and validate a FEN string."""
    try:
        board = chess.Board(fen)
    except ValueError as exc:
        raise NotationError(f"Invalid FEN: {exc}") from exc

    status = board.status()
    if status != chess.STATUS_VALID:
        errors: list[str] = []
        if status & chess.STATUS_TOO_MANY_KINGS:
            errors.append("too many kings")
        if status & chess.STATUS_NO_WHITE_KING:
            errors.append("no white king")
        if status & chess.STATUS_NO_BLACK_KING:
            errors.append("no black king")
        if status & chess.STATUS_TOO_MANY_CHECKERS:
            errors.append("too many checkers / illegal check")
        if status & chess.STATUS_OPPOSITE_CHECK:
            errors.append("side not to move is in check")
        if status & chess.STATUS_BAD_CASTLING_RIGHTS:
            errors.append("invalid castling rights")
        if status & chess.STATUS_INVALID_EP_SQUARE:
            errors.append("invalid en-passant square")
        if status & chess.STATUS_RACE_CHECK:
            errors.append("impossible check / race check")
        if status & chess.STATUS_RACE_OVER:
            errors.append("race is already over")
        if not errors:
            errors.append(f"status flags 0x{status:04x}")
        raise NotationError("FEN validation failed: " + "; ".join(errors))

    return ParsedPosition(start_fen=fen, board=board, uci_moves=[], san_moves=[])


def _extract_start_fen(text: str) -> tuple[str | None, str]:
    """Return (start_fen_or_None, remaining_text)."""
    # Support 'FEN: <fen>' header line
    m = re.match(r"^\s*FEN:\s*(.+)", text, re.IGNORECASE)
    if m:
        fen_line = m.group(1).split("\n")[0].strip()
        rest = text[m.end():].strip()
        return fen_line, rest

    # Support PGN-style '[FEN "..."]' tag
    m = re.match(r'^\s*\[FEN\s+"([^"]+)"\]', text, re.IGNORECASE)
    if m:
        fen_line = m.group(1).strip()
        rest = text[m.end():].strip()
        return fen_line, rest

    return None, text


def _normalise_castling(token: str) -> str:
    """Convert 0-0 / 0-0-0 to O-O / O-O-O for chess.parse_san."""
    return token.replace("0", "O")


def _lan_token_to_uci(token: str, board: chess.Board) -> str | None:
    """Try to convert a LAN token to a UCI move string.

    Accepts:  e2-e4, e2e4, Ng1-f3, Nf3, exd5, e2xd5, O-O, 0-0, e7-e8=Q
    Returns UCI string on success, None on failure.
    """
    # Castling
    if token in ("O-O", "0-0"):
        return "e1g1" if board.turn == chess.WHITE else "e8g8"
    if token in ("O-O-O", "0-0-0"):
        return "e1c1" if board.turn == chess.WHITE else "e8c8"

    # Strip piece letter prefix if present (for LAN like Ng1-f3 → g1-f3 → g1f3)
    # But keep it if it's just SAN-style (Nf3 without from-square)
    # Promotion suffix
    promo = ""
    promo_m = re.search(r"=([QRBN])$", token)
    if promo_m:
        promo = promo_m.group(1).lower()
        token = token[: promo_m.start()]

    # Try to find from/to squares:  Ng1-f3, g1-f3, g1f3, e2xe4, e2-e4
    sq_m = re.match(
        r"^[KQRBN]?([a-h][1-8])[-x]?([a-h][1-8])$", token
    )
    if sq_m:
        return sq_m.group(1) + sq_m.group(2) + promo

    # Pure SAN style (no from-square): Nf3, exd5 — let python-chess handle it
    # by trying parse_san. Return None to indicate we need SAN parsing.
    return None


def _parse_moves(text: str, lan: bool) -> ParsedPosition:
    """Parse a move list (SAN or LAN) with optional FEN header."""
    start_fen, text = _extract_start_fen(text)

    if start_fen is not None:
        try:
            board = chess.Board(start_fen)
        except ValueError as exc:
            raise NotationError(f"Invalid start FEN: {exc}") from exc
        status = board.status()
        if status != chess.STATUS_VALID:
            raise NotationError(f"Invalid start FEN status: 0x{status:04x}")
    else:
        start_fen = chess.STARTING_FEN
        board = chess.Board()

    # Strip comments / variations / NAGs etc.
    cleaned = _STRIP_RE.sub(" ", text)

    tokens = cleaned.split()
    # Remove empty tokens and pure punctuation
    tokens = [t for t in tokens if t and t not in _RESULT_TOKENS]

    uci_moves: list[str] = []
    san_moves: list[str] = []

    for ply, token in enumerate(tokens):
        if not token:
            continue

        if lan:
            uci = _lan_token_to_uci(token, board)
            if uci is not None:
                # Try as UCI move
                try:
                    move = chess.Move.from_uci(uci)
                    if move not in board.legal_moves:
                        raise NotationError(
                            f"Illegal move '{token}' at ply {ply}", ply=ply
                        )
                    san = board.san(move)
                    board.push(move)
                    uci_moves.append(uci)
                    san_moves.append(san)
                    continue
                except (ValueError, chess.InvalidMoveError):
                    raise NotationError(
                        f"Invalid LAN token '{token}' at ply {ply}", ply=ply
                    )
            # Fall through to SAN for tokens like Nf3, exd5

        # Parse as SAN (or LAN token that looks like SAN)
        san_token = _normalise_castling(token)
        try:
            move = board.parse_san(san_token)
        except (chess.InvalidMoveError, chess.AmbiguousMoveError, chess.IllegalMoveError) as exc:
            raise NotationError(
                f"Illegal/invalid move '{token}' at ply {ply}: {exc}", ply=ply
            )
        san = board.san(move)
        uci_moves.append(move.uci())
        san_moves.append(san)
        board.push(move)

    return ParsedPosition(
        start_fen=start_fen,
        board=board,
        uci_moves=uci_moves,
        san_moves=san_moves,
    )


# ---------------------------------------------------------------------------
# SAN line formatter
# ---------------------------------------------------------------------------


def san_line(start_fen: str, uci_moves: list[str], max_moves: int = 8) -> str:
    """Format a move sequence as a SAN line string.

    Args:
        start_fen: Starting position FEN.
        uci_moves: Moves in UCI notation.
        max_moves: Maximum number of *plies* to include.

    Returns:
        A string like ``'1. e4 e5 2. Nf3 Nc6'``.  Starts with ``'1...'``
        when it is Black's turn in *start_fen*.
    """
    board = chess.Board(start_fen)
    parts: list[str] = []
    move_num = board.fullmove_number
    black_to_move_first = board.turn == chess.BLACK

    for ply, uci in enumerate(uci_moves[:max_moves]):
        move = chess.Move.from_uci(uci)
        san = board.san(move)
        board.push(move)

        is_white_move = board.turn == chess.BLACK  # after push, turn has flipped
        if is_white_move:
            parts.append(f"{move_num}. {san}")
        else:
            if ply == 0 and black_to_move_first:
                parts.append(f"{move_num}... {san}")
            else:
                parts.append(san)
            move_num += 1

    return " ".join(parts)
