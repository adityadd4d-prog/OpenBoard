"""
tests/test_engine_types.py
~~~~~~~~~~~~~~~~~~~~~~~~~~
Unit tests for openboard.engines.types helpers.
"""

import pytest
from openboard.engines.types import decode_python_score, pawns_to_cp


def test_pawns_to_cp() -> None:
    assert pawns_to_cp(0.0) == 0
    assert pawns_to_cp(1.23) == 123
    assert pawns_to_cp(-0.45) == -45
    assert pawns_to_cp(2.999) == 300


def test_decode_python_score_normal() -> None:
    score_cp, mate_in = decode_python_score(0.25)
    assert score_cp == 25
    assert mate_in is None

    score_cp, mate_in = decode_python_score(-1.50)
    assert score_cp == -150
    assert mate_in is None


def test_decode_python_score_white_mate() -> None:
    # Forced mate for White: score >= 9000
    # MATE_SCORE = 10000. score = 10000 - 1 = 9999 (mate in 1)
    score_cp, mate_in = decode_python_score(9999)
    assert score_cp is None
    assert mate_in == 1

    # Mate in 2: 10000 - 3 = 9997 -> (10000 - 9997 + 1) // 2 = 4 // 2 = 2
    score_cp, mate_in = decode_python_score(9997)
    assert score_cp is None
    assert mate_in == 2


def test_decode_python_score_black_mate() -> None:
    # Forced mate for Black: score <= -9000
    # -9999 (Black mates in 1)
    score_cp, mate_in = decode_python_score(-9999)
    assert score_cp is None
    assert mate_in == -1

    # -9997 (Black mates in 2)
    score_cp, mate_in = decode_python_score(-9997)
    assert score_cp is None
    assert mate_in == -2
