"""
tests/test_display.py
~~~~~~~~~~~~~~~~~~~~~
Tests for DisplayManager coordinate translation and letterbox handling.
"""

from __future__ import annotations

import os
import pytest

os.environ["SDL_VIDEODRIVER"] = "dummy"
import pygame

from openboard import config
from openboard.ui.display import DisplayManager


class DummySettings:
    window_size = (1600, 900)
    fullscreen = False

    def set(self, **kwargs):
        pass


@pytest.fixture(scope="module", autouse=True)
def init_pygame():
    pygame.init()
    yield
    pygame.quit()


def test_letterbox_16_9():
    """At 16:9 (1600x900), scale is 1.0, offsets are 0."""
    dm = DisplayManager(DummySettings())
    # Manually configure viewport to test geometry
    dm._win_w = 1600
    dm._win_h = 900
    dm._scale = 1.0
    dm._dest_w = 1600
    dm._dest_h = 900
    dm._offset_x = 0
    dm._offset_y = 0

    assert dm.window_to_design((0, 0)) == (0.0, 0.0)
    assert dm.window_to_design((800, 450)) == (800.0, 450.0)
    assert dm.window_to_design((1600, 900)) == (1600.0, 900.0)

    # Click inside
    ev = pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"pos": (800, 450), "button": 1})
    tev = dm.translate_event(ev)
    assert tev is not None
    assert tev.pos == (800, 450)


def test_letterbox_4_3():
    """At 4:3 (1600x1200), horizontal fits, vertical letterboxes (top/bottom bars)."""
    dm = DisplayManager(DummySettings())
    dm._win_w = 1600
    dm._win_h = 1200
    dm._scale = 1.0
    dm._dest_w = 1600
    dm._dest_h = 900
    dm._offset_x = 0
    dm._offset_y = 150  # (1200 - 900) // 2

    # Center of screen is center of canvas
    assert dm.window_to_design((800, 600)) == (800.0, 450.0)

    # Click in top bar (y=50) is out of bounds and ignored
    ev_top = pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"pos": (800, 50), "button": 1})
    assert dm.translate_event(ev_top) is None

    # Click in bottom bar (y=1150) is out of bounds and ignored
    ev_bottom = pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"pos": (800, 1150), "button": 1})
    assert dm.translate_event(ev_bottom) is None

    # Click on design origin
    ev_canvas_top = pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"pos": (0, 150), "button": 1})
    tev = dm.translate_event(ev_canvas_top)
    assert tev is not None
    assert tev.pos == (0, 0)


def test_pillarbox_ultrawide():
    """At 21:9 (2560x900), vertical fits, horizontal pillarboxes (left/right bars)."""
    dm = DisplayManager(DummySettings())
    dm._win_w = 2560
    dm._win_h = 900
    dm._scale = 1.0
    dm._dest_w = 1600
    dm._dest_h = 900
    dm._offset_x = 480  # (2560 - 1600) // 2
    dm._offset_y = 0

    # Center of screen is center of canvas
    assert dm.window_to_design((1280, 450)) == (800.0, 450.0)

    # Click in left bar (x=200) is ignored
    ev_left = pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"pos": (200, 450), "button": 1})
    assert dm.translate_event(ev_left) is None

    # Click in right bar (x=2200) is ignored
    ev_right = pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"pos": (2200, 450), "button": 1})
    assert dm.translate_event(ev_right) is None

    # Click on design origin
    ev_canvas_origin = pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"pos": (480, 0), "button": 1})
    tev = dm.translate_event(ev_canvas_origin)
    assert tev is not None
    assert tev.pos == (0, 0)
