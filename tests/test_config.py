"""
tests/test_config.py
~~~~~~~~~~~~~~~~~~~~
Smoke tests for openboard.config — no pygame required.
"""

from __future__ import annotations

import pytest

import openboard.config as cfg


class TestLevels:
    """Tests for the LEVELS dictionary."""

    def test_levels_has_keys_1_to_8(self) -> None:
        """LEVELS must contain exactly the keys 1 through 8."""
        assert set(cfg.LEVELS.keys()) == set(range(1, 9))

    def test_level_field_types(self) -> None:
        """Every LevelSpec field must be the declared type (or None)."""
        for key, spec in cfg.LEVELS.items():
            assert isinstance(spec.ui_level, int), f"level {key}: ui_level not int"
            assert isinstance(spec.caption, str), f"level {key}: caption not str"
            assert spec.python_level is None or isinstance(
                spec.python_level, int
            ), f"level {key}: python_level wrong type"
            assert spec.sf_elo is None or isinstance(
                spec.sf_elo, int
            ), f"level {key}: sf_elo wrong type"
            assert spec.sf_movetime_s is None or isinstance(
                spec.sf_movetime_s, float
            ), f"level {key}: sf_movetime_s wrong type"
            assert isinstance(spec.sf_only, bool), f"level {key}: sf_only not bool"

    def test_level_ui_level_matches_key(self) -> None:
        """ui_level field must match the dict key."""
        for key, spec in cfg.LEVELS.items():
            assert spec.ui_level == key

    def test_specific_level_values(self) -> None:
        """Spot-check a few concrete level values."""
        assert cfg.LEVELS[1].caption == "BEGINNER"
        assert cfg.LEVELS[1].python_level == 1
        assert cfg.LEVELS[1].sf_only is False

        assert cfg.LEVELS[8].caption == "STOCKFISH"
        assert cfg.LEVELS[8].python_level is None
        assert cfg.LEVELS[8].sf_only is True
        assert cfg.LEVELS[8].sf_movetime_s == 1.0

        assert cfg.LEVELS[5].sf_elo == 1600
        assert cfg.LEVELS[5].sf_movetime_s == pytest.approx(0.3)


class TestTimeControls:
    """Tests for the TIME_CONTROLS dictionary."""

    def test_time_controls_has_blitz_and_rapid(self) -> None:
        """TIME_CONTROLS must contain 'blitz' and 'rapid'."""
        assert "blitz" in cfg.TIME_CONTROLS
        assert "rapid" in cfg.TIME_CONTROLS

    def test_blitz_values(self) -> None:
        """Verify BLITZ time control fields."""
        blitz = cfg.TIME_CONTROLS["blitz"]
        assert blitz.minutes == 3
        assert blitz.increment_s == 2
        assert blitz.label == "BLITZ 3 + 2"

    def test_rapid_values(self) -> None:
        """Verify RAPID time control fields."""
        rapid = cfg.TIME_CONTROLS["rapid"]
        assert rapid.minutes == 10
        assert rapid.increment_s == 0
        assert rapid.label == "RAPID 10 + 0"

    def test_time_control_field_types(self) -> None:
        """TimeControl fields must all be the right types."""
        for key, tc in cfg.TIME_CONTROLS.items():
            assert isinstance(tc.key, str), f"{key}: key not str"
            assert isinstance(tc.label, str), f"{key}: label not str"
            assert isinstance(tc.minutes, int), f"{key}: minutes not int"
            assert isinstance(tc.increment_s, int), f"{key}: increment_s not int"


class TestConstants:
    """Tests for miscellaneous constants."""

    def test_design_dimensions(self) -> None:
        assert cfg.DESIGN_W == 1600
        assert cfg.DESIGN_H == 900

    def test_fps_options_contains_default(self) -> None:
        assert cfg.DEFAULT_FPS in cfg.FPS_OPTIONS

    def test_eval_depth_range(self) -> None:
        lo, hi = cfg.EVAL_DEPTH_RANGE
        assert lo < hi
        assert cfg.EVAL_DEFAULT_DEPTH in range(lo, hi + 1)

    def test_eval_thresholds_ordered(self) -> None:
        assert cfg.EVAL_EQUAL_MAX < cfg.EVAL_SLIGHT_EDGE_MAX < cfg.EVAL_CLEAR_ADVANTAGE_MAX
