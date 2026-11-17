"""
openboard.ui.scenes.base
~~~~~~~~~~~~~~~~~~~~~~~~
Base class for all UI scenes.
"""

from __future__ import annotations

from typing import Any

import pygame


class Scene:
    """Base class for all OpenBoard scenes."""

    name: str = ""
    is_modal: bool = False

    def __init__(self, ctx: Any) -> None:
        self.ctx = ctx

    def on_enter(self, **params: Any) -> None:
        """Called when this scene is pushed or transitioned to."""
        pass

    def on_exit(self) -> None:
        """Called when this scene is popped or replaced."""
        pass

    def on_resume(self, result: Any = None) -> None:
        """Called when a modal scene above this one is popped and delivers a result."""
        pass

    def handle_event(self, event: pygame.event.Event) -> None:
        """Process an input event."""
        pass

    def update(self, dt: float) -> None:
        """Update scene logic and animations."""
        pass

    def draw(self, surf: pygame.Surface) -> None:
        """Render scene onto virtual 1600×900 surface."""
        pass
