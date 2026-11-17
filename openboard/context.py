"""
openboard.context
~~~~~~~~~~~~~~~~~
Central AppContext holding application services and state.
Can be instantiated in headless mode without pygame.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from openboard import paths
from openboard.engines.service import EngineService
from openboard.storage.history import HistoryStore
from openboard.storage.profile import ProfileStore
from openboard.storage.settings import SettingsStore

if TYPE_CHECKING:
    import pygame
    from openboard.ui.assets import AssetStore
    from openboard.ui.display import DisplayManager
    from openboard.ui.scene_manager import SceneManager

log = logging.getLogger("openboard.context")


@dataclass(slots=True)
class AppContext:
    """Holds shared runtime services across the application."""

    settings: SettingsStore
    profile: ProfileStore
    history: HistoryStore
    engines: EngineService
    assets: Any = None
    display: Any = None
    scenes: Any = None
    clock: Any = None
    _shutdown_done: bool = False

    def sfx(self, name: str) -> None:
        """Play a sound effect if audio is enabled in settings and assets is initialized."""
        if not getattr(self.settings.settings, "audio", True):
            return

        if self.assets is not None:
            try:
                snd = self.assets.sound(name)
                if snd is not None:
                    snd.play()
            except Exception as exc:
                log.debug("Could not play sound %s: %s", name, exc)

    def shutdown(self) -> None:
        """Idempotently shuts down background engines and saves state."""
        if self._shutdown_done:
            return
        self._shutdown_done = True

        log.info("AppContext shutting down...")
        try:
            self.engines.shutdown()
        except Exception as exc:
            log.warning("Engine shutdown error: %s", exc)

        try:
            self.settings.save()
        except Exception as exc:
            log.warning("Settings save error: %s", exc)


def build_context(headless: bool = False) -> AppContext:
    """Build and wire all services in the application.

    Args:
        headless: When True, initializes only non-pygame services.
    """
    user_data = paths.user_data_dir()
    settings_store = SettingsStore(user_data / "settings.json")
    profile_store = ProfileStore(user_data / "profile.json")
    history_store = HistoryStore(user_data / "history.db")

    engine_service = EngineService(settings_store)
    engine_service.start()

    ctx = AppContext(
        settings=settings_store,
        profile=profile_store,
        history=history_store,
        engines=engine_service,
    )

    if not headless:
        import pygame
        from openboard.ui.assets import AssetStore
        from openboard.ui.display import DisplayManager
        from openboard.ui.scene_manager import SceneManager

        display_mgr = DisplayManager(settings_store.settings)
        asset_store = AssetStore()
        scene_mgr = SceneManager(ctx)
        game_clock = pygame.time.Clock()

        ctx.display = display_mgr
        ctx.assets = asset_store
        ctx.scenes = scene_mgr
        ctx.clock = game_clock

    return ctx
