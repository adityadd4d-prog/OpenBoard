"""
tests.test_notation
~~~~~~~~~~~~~~~~~~~
Unit tests for openboard.core.notation.
"""

from __future__ import annotations

import pytest
import chess

from openboard.core.notation import (
    NotationError,
    ParsedPosition,
    detect_input_type,
    parse_position,
    san_line,
)


# ---------------------------------------------------------------------------
# detect_input_type
# ---------------------------------------------------------------------------


class TestDetectInputType:
    def test_fen_standard(self) -> None:
        fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
        assert detect_input_type(fen) == "fen"

    def test_fen_mid_game(self) -> None:
        fen = "r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4"
        assert detect_input_type(fen) == "fen"

    def test_san_simple(self) -> None:
        assert detect_input_type("1. e4 e5 2. Nf3 Nc6") == "san"

    def test_san_single_move(self) -> None:
        assert detect_input_type("e4") == "san"

    def test_lan_hyphen(self) -> None:
        assert detect_input_type("e2-e4 e7-e5") == "lan"

    def test_lan_piece_hyphen(self) -> None:
        assert detect_input_type("Ng1-f3") == "lan"


# ---------------------------------------------------------------------------
# FEN parsing
# ---------------------------------------------------------------------------


class TestFENParsing:
    def test_valid_fen(self) -> None:
        fen = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1"
        pos = parse_position(fen, kind="fen")
        assert pos.start_fen == fen
        assert pos.board.turn == chess.BLACK
        assert pos.uci_moves == []

    def test_too_many_kings(self) -> None:
        # Two white kings — invalid
        bad_fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBKQKBNR w KQkq - 0 1"
        with pytest.raises(NotationError) as exc_info:
            parse_position(bad_fen, kind="fen")
        assert exc_info.value.ply is None

    def test_opposite_side_in_check(self) -> None:
        # Black king in check but it's White's turn — invalid
        bad_fen = "rnbqkb1r/ppppp2p/5n2/5ppQ/4P3/8/PPPP1PPP/RNB1KBNR w KQkq - 0 4"
        # This may or may not be STATUS_OPPOSITE_CHECK depending on exact position;
        # let's use a known position where non-moving side is in check
        # King directly attacked by white queen
        bad_fen2 = "4k3/8/8/8/8/8/8/4K2Q b - - 0 1"
        # Black to move, but white queen attacks e8 — white is NOT in check here
        # Let's try: black king on e1, white queen on e8, white to move — black king in check
        # and it's white's turn (STATUS_OPPOSITE_CHECK)
        bad_fen3 = "8/8/8/8/8/8/8/4k2K w - - 0 1"  # two kings adjacent
        # Simplest case: set up position that is STATUS_OPPOSITE_CHECK
        # White to move, black king in check by white rook
        bad_fen4 = "4k3/8/4R3/8/8/8/8/4K3 w - - 0 1"
        with pytest.raises(NotationError):
            parse_position(bad_fen4, kind="fen")

    def test_bad_castling_rights(self) -> None:
        # Castling rights declared but rooks are not in position
        bad_fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQK2R w KQkq - 0 1"
        # This is actually valid — the rook IS on h1; test a genuinely bad one:
        bad_fen2 = "1nbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
        # Above has black rook missing on a8 but castling right 'q' — invalid
        with pytest.raises(NotationError):
            parse_position(bad_fen2, kind="fen")

    def test_invalid_fen_string(self) -> None:
        with pytest.raises(NotationError):
            parse_position("not a fen at all", kind="fen")

    def test_no_white_king(self) -> None:
        # Remove white king
        bad_fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQ1BNR w KQkq - 0 1"
        with pytest.raises(NotationError):
            parse_position(bad_fen, kind="fen")


# ---------------------------------------------------------------------------
# SAN parsing
# ---------------------------------------------------------------------------


class TestSANParsing:
    def test_simple_moves(self) -> None:
        pos = parse_position("1. e4 e5 2. Nf3 Nc6", kind="san")
        assert len(pos.uci_moves) == 4
        assert pos.san_moves[0] == "e4"

    def test_strip_comments(self) -> None:
        text = "1. e4 {great move} e5 2. Nf3"
        pos = parse_position(text, kind="san")
        assert len(pos.uci_moves) == 3

    def test_strip_variations(self) -> None:
        text = "1. e4 (1. d4) e5"
        pos = parse_position(text, kind="san")
        assert len(pos.uci_moves) == 2

    def test_strip_nags(self) -> None:
        text = "1. e4 $1 e5 $2"
        pos = parse_position(text, kind="san")
        assert len(pos.uci_moves) == 2

    def test_strip_result_tokens(self) -> None:
        text = "1. e4 e5 2. Qh5 Nc6 3. Bc4 Nf6 4. Qxf7# 1-0"
        pos = parse_position(text, kind="san")
        assert len(pos.uci_moves) == 7

    def test_strip_line_comment(self) -> None:
        text = "1. e4 ; this is e4\ne5"
        pos = parse_position(text, kind="san")
        assert len(pos.uci_moves) == 2

    def test_castling_O_O(self) -> None:
        # Set up a position where O-O is legal
        fen = "rnbqkbnr/pppp1ppp/4p3/8/4P3/5N2/PPPPBPPP/RNBQK2R w KQkq - 2 3"
        text = f"FEN: {fen}\nO-O"
        pos = parse_position(text, kind="san")
        assert pos.uci_moves == ["e1g1"]

    def test_castling_0_0(self) -> None:
        fen = "rnbqkbnr/pppp1ppp/4p3/8/4P3/5N2/PPPPBPPP/RNBQK2R w KQkq - 2 3"
        text = f"FEN: {fen}\n0-0"
        pos = parse_position(text, kind="san")
        assert pos.uci_moves == ["e1g1"]

    def test_castling_O_O_O(self) -> None:
        fen = "r3kbnr/ppp1pppp/2nqb3/3p4/3P4/2NQB3/PPP1PPPP/R3KBNR w KQkq - 6 6"
        text = f"FEN: {fen}\nO-O-O"
        pos = parse_position(text, kind="san")
        assert pos.uci_moves == ["e1c1"]

    def test_promotion_san(self) -> None:
        # Set up White pawn on e7 ready to promote
        fen = "8/4P3/8/8/8/8/8/4K1k1 w - - 0 1"
        text = f"FEN: {fen}\ne8=Q"
        pos = parse_position(text, kind="san")
        assert pos.uci_moves == ["e7e8q"]

    def test_fen_header_bracket_style(self) -> None:
        fen = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1"
        text = f'[FEN "{fen}"]\n1... e5'
        pos = parse_position(text, kind="san")
        assert len(pos.uci_moves) == 1
        assert pos.start_fen == fen

    def test_fen_header_colon_style(self) -> None:
        fen = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1"
        text = f"FEN: {fen}\ne5"
        pos = parse_position(text, kind="san")
        assert len(pos.uci_moves) == 1

    def test_illegal_move_raises_notation_error(self) -> None:
        with pytest.raises(NotationError) as exc_info:
            parse_position("1. e4 e5 2. e5", kind="san")  # e5 is not reachable
        assert exc_info.value.ply is not None

    def test_illegal_move_correct_ply(self) -> None:
        with pytest.raises(NotationError) as exc_info:
            parse_position("e4 e5 Nf6", kind="san")  # Nf6 is Black's move, now White's turn
        # ply 2 (0-indexed)
        assert exc_info.value.ply == 2

    def test_annotation_marks_stripped(self) -> None:
        text = "1. e4! e5? 2. Nf3!!"
        pos = parse_position(text, kind="san")
        assert len(pos.uci_moves) == 3

    def test_full_game(self) -> None:
        # Fool's mate
        text = "1. f3 e5 2. g4 Qh4#"
        pos = parse_position(text, kind="san")
        assert len(pos.uci_moves) == 4
        assert pos.board.is_checkmate()

    def test_auto_detect_san(self) -> None:
        pos = parse_position("1. d4 d5 2. c4")
        assert len(pos.uci_moves) == 3

    def test_auto_detect_fen(self) -> None:
        fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
        pos = parse_position(fen)
        assert pos.board.turn == chess.WHITE

    def test_nested_variations_stripped(self) -> None:
        # Nested variation — only single-level supported, outer stripped
        text = "1. e4 (1. d4 d5) e5"
        pos = parse_position(text, kind="san")
        # At minimum, e4 and e5 should be there
        assert "e4e5"[:2] == "e4"  # sanity
        # We get e4 and then e5 since the variation is stripped
        assert len(pos.uci_moves) == 2


# ---------------------------------------------------------------------------
# LAN parsing
# ---------------------------------------------------------------------------


class TestLANParsing:
    def test_simple_lan(self) -> None:
        pos = parse_position("e2-e4 e7-e5", kind="lan")
        assert len(pos.uci_moves) == 2
        assert pos.uci_moves[0] == "e2e4"

    def test_lan_no_hyphen(self) -> None:
        pos = parse_position("e2e4 e7e5", kind="lan")
        assert pos.uci_moves[0] == "e2e4"

    def test_lan_piece_move(self) -> None:
        # Ng1-f3 after e4 e5
        text = "e2-e4 e7-e5 Ng1-f3"
        pos = parse_position(text, kind="lan")
        assert len(pos.uci_moves) == 3
        assert pos.uci_moves[2] == "g1f3"

    def test_lan_promotion(self) -> None:
        fen = "8/4P3/8/8/8/8/8/4K1k1 w - - 0 1"
        pos = parse_position(f"FEN: {fen}\ne7-e8=Q", kind="lan")
        assert pos.uci_moves == ["e7e8q"]

    def test_lan_promotion_no_hyphen(self) -> None:
        fen = "8/4P3/8/8/8/8/8/4K1k1 w - - 0 1"
        pos = parse_position(f"FEN: {fen}\ne7e8=Q", kind="lan")
        assert pos.uci_moves == ["e7e8q"]

    def test_lan_illegal_move_raises(self) -> None:
        with pytest.raises(NotationError):
            parse_position("e2-e5", kind="lan")  # pawn can't jump 3 squares

    def test_lan_auto_detect(self) -> None:
        pos = parse_position("e2-e4 e7-e5")
        assert len(pos.uci_moves) == 2

    def test_lan_castling_o_o(self) -> None:
        fen = "rnbqkbnr/pppp1ppp/4p3/8/4P3/5N2/PPPPBPPP/RNBQK2R w KQkq - 2 3"
        pos = parse_position(f"FEN: {fen}\nO-O", kind="lan")
        assert pos.uci_moves == ["e1g1"]


# ---------------------------------------------------------------------------
# san_line
# ---------------------------------------------------------------------------


class TestSanLine:
    def test_white_starts(self) -> None:
        fen = chess.STARTING_FEN
        moves = ["e2e4", "e7e5", "g1f3", "b8c6"]
        result = san_line(fen, moves)
        assert result == "1. e4 e5 2. Nf3 Nc6"

    def test_max_moves_limit(self) -> None:
        fen = chess.STARTING_FEN
        moves = ["e2e4", "e7e5", "g1f3", "b8c6"]
        result = san_line(fen, moves, max_moves=2)
        assert result == "1. e4 e5"

    def test_black_starts(self) -> None:
        fen = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1"
        moves = ["e7e5"]
        result = san_line(fen, moves)
        assert result.startswith("1...")

    def test_empty_moves(self) -> None:
        assert san_line(chess.STARTING_FEN, []) == ""
