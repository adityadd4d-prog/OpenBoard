"""
openboard.ui.scene_manager
~~~~~~~~~~~~~~~~~~~~~~~~~~
SceneManager handles navigation, modal stacking, transitions, and dispatch.
"""

from __future__ import annotations

import logging
from typing import Any, Callable

import pygame

from openboard.ui.scenes.base import Scene
from openboard.ui.theme import DIM

log = logging.getLogger("openboard.ui.scene_manager")


class SceneManager:
    """Manages scene registration, stack transitions, and modal overlays."""

    def __init__(self, ctx: Any) -> None:
        self.ctx = ctx
        self._factories: dict[str, Callable[[Any], Scene]] = {}
        self._stack: list[Scene] = []
        self._quit_requested: bool = False

        # Transition state
        self._fading = False
        self._fade_alpha = 0.0
        self._fade_duration = 0.15
        self._fade_t = 0.0
        self._fade_surf: pygame.Surface | None = None

    def register(self, name: str, factory: Callable[[Any], Scene]) -> None:
        """Register a scene factory by name."""
        self._factories[name] = factory

    @property
    def current_name(self) -> str:
        """Name of the currently active top scene (used by F2 overlay)."""
        if self._stack:
            return self._stack[-1].name
        return ""

    @property
    def quit_requested(self) -> bool:
        """Whether a scene requested application termination."""
        return self._quit_requested

    def request_quit(self) -> None:
        """Flag application to quit cleanly."""
        self._quit_requested = True

    def go(self, name: str, **params: Any) -> None:
        """Replace the entire scene stack with the target scene."""
        if name not in self._factories:
            raise ValueError(f"Unknown scene: {name}")

        while self._stack:
            old = self._stack.pop()
            old.on_exit()

        scene = self._factories[name](self.ctx)
        scene.name = name
        self._stack.append(scene)
        scene.on_enter(**params)
        log.debug("Navigated to scene: %s", name)

    def push(self, name: str, **params: Any) -> None:
        """Push a modal or sub-scene on top of the current scene."""
        if name not in self._factories:
            raise ValueError(f"Unknown scene: {name}")

        scene = self._factories[name](self.ctx)
        scene.name = name
        self._stack.append(scene)
        scene.on_enter(**params)
        log.debug("Pushed scene: %s", name)

    def pop(self, result: Any = None) -> None:
        """Pop the top scene and notify the scene below via on_resume(result)."""
        if not self._stack:
            return

        top = self._stack.pop()
        top.on_exit()

        if self._stack:
            self._stack[-1].on_resume(result)
        log.debug("Popped scene %s (result=%s)", top.name, result)

    def handle_event(self, event: pygame.event.Event) -> None:
        """Deliver input events only to the top scene."""
        if self._stack:
            self._stack[-1].handle_event(event)

    def update(self, dt: float) -> None:
        """Update only the active top scene."""
        if self._stack:
            self._stack[-1].update(dt)

    def draw(self, surf: pygame.Surface) -> None:
        """Draw the active stack. If top scene is modal, draw base first then overlay."""
        if not self._stack:
            return

        if len(self._stack) > 1 and self._stack[-1].is_modal:
            # Draw underlying scene
            self._stack[-2].draw(surf)
            # Draw dim overlay
            dim_surf = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
            dim_surf.fill(DIM)
            surf.blit(dim_surf, (0, 0))
            # Draw modal on top
            self._stack[-1].draw(surf)
        else:
            self._stack[-1].draw(surf)
