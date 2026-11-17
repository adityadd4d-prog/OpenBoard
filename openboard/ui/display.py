"""
openboard.ui.display
~~~~~~~~~~~~~~~~~~~~
DisplayManager: fixed 1600x900 virtual canvas letterboxed to any window size.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

import pygame

from openboard import config, paths
from openboard.ui.theme import INK

log = logging.getLogger("openboard.ui.display")


class DisplayManager:
    """Manages the OS window and the 1600×900 letterboxed virtual surface."""

    def __init__(self, settings: Any) -> None:
        self.settings = settings
        self.surface = pygame.Surface((config.DESIGN_W, config.DESIGN_H))

        self._win_w = 0
        self._win_h = 0
        self._scale = 1.0
        self._offset_x = 0
        self._offset_y = 0
        self._dest_w = config.DESIGN_W
        self._dest_h = config.DESIGN_H
        self._scaled_surface: pygame.Surface | None = None

        self._fullscreen: bool = getattr(settings, "fullscreen", False)
        self._fs_debounce: float = 0.0

        # Reference overlay (F2)
        self._ref_surface: pygame.Surface | None = None
        self._ref_scene_name: str | None = None
        self._ref_visible: bool = False

        self._create_window()

    def _create_window(self) -> None:
        pygame.display.set_caption(config.APP_NAME)
        self._set_window_icon()

        flags = pygame.RESIZABLE
        win_size = getattr(self.settings, "window_size", (1280, 720))
        if self._fullscreen:
            flags |= pygame.FULLSCREEN

        self.window = pygame.display.set_mode(win_size, flags)
        self._recalc_viewport()

    def _set_window_icon(self) -> None:
        try:
            icon_path = paths.assets_dir() / "app" / "app_icon.png"
            if not icon_path.exists():
                icon_path = paths.assets_dir() / "raw" / "app_icon.png"
            if icon_path.exists():
                surf = pygame.image.load(str(icon_path))
                pygame.display.set_icon(surf)
        except Exception as exc:
            log.debug("Could not set window icon: %s", exc)

    def _recalc_viewport(self) -> None:
        w, h = pygame.display.get_surface().get_size()
        w = max(w, config.MIN_WINDOW[0])
        h = max(h, config.MIN_WINDOW[1])
        self._win_w = w
        self._win_h = h

        scale_x = w / config.DESIGN_W
        scale_y = h / config.DESIGN_H
        self._scale = min(scale_x, scale_y)

        dest_w = round(config.DESIGN_W * self._scale)
        dest_h = round(config.DESIGN_H * self._scale)
        self._dest_w = dest_w
        self._dest_h = dest_h

        self._offset_x = (w - dest_w) // 2
        self._offset_y = (h - dest_h) // 2

        if self._scale != 1.0:
            if self._scaled_surface is None or self._scaled_surface.get_size() != (dest_w, dest_h):
                self._scaled_surface = pygame.Surface((dest_w, dest_h))
        else:
            self._scaled_surface = None

    def window_to_design(self, pos: tuple[int, int] | tuple[float, float]) -> tuple[float, float]:
        """Convert actual window coordinates to 1600×900 design coordinates."""
        dx = (pos[0] - self._offset_x) / self._scale
        dy = (pos[1] - self._offset_y) / self._scale
        return (dx, dy)

    def translate_event(self, event: pygame.event.Event) -> pygame.event.Event | None:
        """Translate event coordinates into design space. Clicks in letterbox bars return None."""
        if event.type == pygame.VIDEORESIZE:
            self._recalc_viewport()
            if hasattr(self.settings, "set") and not self._fullscreen:
                self.settings.set(window_size=(event.w, event.h))
            return event

        if event.type in (pygame.MOUSEMOTION, pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP):
            x, y = self.window_to_design(event.pos)
            in_bounds = (0 <= x <= config.DESIGN_W) and (0 <= y <= config.DESIGN_H)

            if not in_bounds and event.type != pygame.MOUSEMOTION:
                return None  # Ignore clicks in black bars

            new_dict = dict(event.__dict__)
            new_dict["pos"] = (int(x), int(y))
            if "rel" in new_dict and self._scale > 0:
                rx, ry = new_dict["rel"]
                new_dict["rel"] = (int(rx / self._scale), int(ry / self._scale))

            return pygame.event.Event(event.type, new_dict)

        return event

    def toggle_fullscreen(self) -> None:
        """Toggle fullscreen mode (F11)."""
        now = time.monotonic()
        if now - self._fs_debounce < 0.3:
            return
        self._fs_debounce = now

        self._fullscreen = not self._fullscreen
        if self._fullscreen:
            self.window = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        else:
            win_size = getattr(self.settings, "window_size", (1280, 720))
            self.window = pygame.display.set_mode(win_size, pygame.RESIZABLE)

        if hasattr(self.settings, "set"):
            self.settings.set(fullscreen=self._fullscreen)

        self._recalc_viewport()

    def toggle_reference(self, scene_name: str) -> None:
        """Toggle 50% alpha reference overlay for the named scene (F2)."""
        if self._ref_visible and self._ref_scene_name == scene_name:
            self._ref_visible = False
            return

        ref_dir = paths.reference_dir()
        alias_map = {
            "opponent_select": "opponent",
            "pass_play_setup": "pass_play",
            "vs_engine_setup": "vs_engine",
        }
        ref_file = ref_dir / f"{scene_name}.png"
        if not ref_file.exists() and scene_name in alias_map:
            ref_file = ref_dir / f"{alias_map[scene_name]}.png"

        if not ref_file.exists():
            log.info("Reference mockup not found at %s", ref_file)
            self._ref_visible = False
            return

        try:
            img = pygame.image.load(str(ref_file)).convert_alpha()
            if img.get_size() != (config.DESIGN_W, config.DESIGN_H):
                img = pygame.transform.smoothscale(img, (config.DESIGN_W, config.DESIGN_H))
            img.set_alpha(128)  # 50% alpha
            self._ref_surface = img
            self._ref_scene_name = scene_name
            self._ref_visible = True
            log.info("F2 reference overlay enabled for: %s", scene_name)
        except Exception as exc:
            log.warning("Could not load reference overlay: %s", exc)
            self._ref_visible = False

    def set_hand_cursor(self, hand: bool) -> None:
        """Switch between standard pointer and clickable hand cursor."""
        cursor = pygame.SYSTEM_CURSOR_HAND if hand else pygame.SYSTEM_CURSOR_ARROW
        try:
            pygame.mouse.set_cursor(cursor)
        except Exception:
            pass

    def present(self) -> None:
        """Scale and blit the design surface onto the window with letterbox bars."""
        win = pygame.display.get_surface()
        if win is None:
            return

        win.fill(INK)

        draw_surf = self.surface
        if self._ref_visible and self._ref_surface is not None:
            draw_surf = self.surface.copy()
            draw_surf.blit(self._ref_surface, (0, 0))

        if self._scale == 1.0:
            win.blit(draw_surf, (self._offset_x, self._offset_y))
        else:
            if self._scaled_surface is None or self._scaled_surface.get_size() != (self._dest_w, self._dest_h):
                self._scaled_surface = pygame.Surface((self._dest_w, self._dest_h))
            pygame.transform.smoothscale(draw_surf, (self._dest_w, self._dest_h), self._scaled_surface)
            win.blit(self._scaled_surface, (self._offset_x, self._offset_y))

        pygame.display.flip()


def _demo() -> None:
    pygame.init()
    class S:
        fullscreen = False
        window_size = (1280, 720)
    disp = DisplayManager(S())
    clock = pygame.time.Clock()
    running = True

    while running:
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                running = False
            elif ev.type == pygame.KEYDOWN and ev.key == pygame.K_F11:
                disp.toggle_fullscreen()
            tev = disp.translate_event(ev)
            if tev and tev.type == pygame.MOUSEBUTTONDOWN:
                print(f"Window click: design coords {tev.pos}")

        disp.surface.fill((243, 232, 250))
        # Draw a grid and border
        pygame.draw.rect(disp.surface, (48, 42, 59), (0, 0, 1600, 900), 5)
        for x in range(0, 1600, 200):
            pygame.draw.line(disp.surface, (199, 177, 210), (x, 0), (x, 900), 1)
        for y in range(0, 900, 100):
            pygame.draw.line(disp.surface, (199, 177, 210), (0, y), (1600, y), 1)

        disp.present()
        clock.tick(60)

    pygame.quit()


if __name__ == "__main__":
    _demo()
