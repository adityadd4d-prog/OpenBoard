"""
main.py
~~~~~~~
OpenBoard application entrypoint.
"""

from __future__ import annotations

import argparse
import json
import logging
from logging.handlers import RotatingFileHandler
import multiprocessing
import os
import sys
import threading
import time
import traceback

# Suppress pygame community advertisement prompt
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

import chess
import pygame

from openboard import config, paths
from openboard.context import build_context
from openboard.ui.scenes.about import AboutScene
from openboard.ui.scenes.confirm import ConfirmScene
from openboard.ui.scenes.evaluate import EvaluateScene
from openboard.ui.scenes.game import GameScene
from openboard.ui.scenes.main_menu import MainMenuScene
from openboard.ui.scenes.opponent_select import OpponentSelectScene
from openboard.ui.scenes.pass_play_setup import PassPlaySetupScene
from openboard.ui.scenes.profile import ProfileScene
from openboard.ui.scenes.settings import SettingsScene
from openboard.ui.scenes.vs_engine_setup import VsEngineSetupScene

log = logging.getLogger("openboard")


def setup_logging() -> None:
    """Configure rotating file handler and console output."""
    log_dir = paths.log_dir()
    log_file = log_dir / "openboard.log"

    root_logger = logging.getLogger("openboard")
    root_logger.setLevel(logging.INFO)

    # Console
    ch = logging.StreamHandler(sys.stderr)
    ch.setLevel(logging.INFO)
    fmt = logging.Formatter("[%(asctime)s] %(levelname)s %(name)s: %(message)s", "%H:%M:%S")
    ch.setFormatter(fmt)
    root_logger.addHandler(ch)

    # Rotating file handler: 512 KB x 3
    try:
        fh = RotatingFileHandler(log_file, maxBytes=512 * 1024, backupCount=3, encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fh_fmt = logging.Formatter("[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s")
        fh.setFormatter(fh_fmt)
        root_logger.addHandler(fh)
    except Exception as exc:
        print(f"Warning: could not initialize file logger: {exc}", file=sys.stderr)


def run_selftest() -> int:
    """Headless self-test verifying both backends answer properly. Outputs JSON."""
    ctx = build_context(headless=True)
    time.sleep(0.3)

    py_res = None
    sf_res = None
    done = threading.Event()

    def on_done(res):
        nonlocal py_res, sf_res
        if res.backend == "python":
            py_res = res
        else:
            sf_res = res
        if py_res and (sf_res or not ctx.engines.sf_backend.available):
            done.set()

    # Search request
    fen = chess.STARTING_FEN
    ctx.engines.submit({"fen": fen, "purpose": "play", "level": 1}, on_done)
    if ctx.engines.sf_backend.available:
        ctx.engines.submit({"fen": fen, "purpose": "evaluate", "depth": 6}, on_done)

    t0 = time.monotonic()
    while not done.is_set() and time.monotonic() - t0 < 5.0:
        ctx.engines.poll()
        time.sleep(0.05)
    ctx.engines.poll()

    py_ok = py_res is not None and py_res.best_uci is not None
    sf_ok = (not ctx.engines.sf_backend.available) or (sf_res is not None and sf_res.best_uci is not None)

    summary = {
        "python_engine_ok": py_ok,
        "stockfish_available": ctx.engines.sf_backend.available,
        "stockfish_ok": sf_ok,
        "capabilities": {
            "stockfish_name": ctx.engines.capabilities().stockfish_name,
            "smart_engine": ctx.engines.capabilities().smart_engine,
        },
    }
    print(json.dumps(summary, indent=2))
    ctx.shutdown()
    return 0 if (py_ok and sf_ok) else 1


def draw_crash_screen(win: pygame.Surface, error_text: str) -> None:
    """Render a basic fallback error screen if the main loop crashes."""
    win.fill((48, 42, 59))  # INK
    f = pygame.font.SysFont("monospace", 16)
    y = 40
    header = f.render("OpenBoard crashed. Traceback saved to logs. Press ESC to quit.", True, (243, 232, 250))
    win.blit(header, (40, y))
    y += 40

    for line in error_text.split("\n")[:28]:
        line_surf = f.render(line[:120], True, (220, 53, 69))
        win.blit(line_surf, (40, y))
        y += 20
    pygame.display.flip()

    clock = pygame.time.Clock()
    running = True
    while running:
        for ev in pygame.event.get():
            if ev.type in (pygame.QUIT, pygame.KEYDOWN):
                running = False
        clock.tick(30)


def main() -> None:
    multiprocessing.freeze_support()
    try:
        multiprocessing.set_start_method("spawn", force=True)
    except RuntimeError:
        pass

    parser = argparse.ArgumentParser(description=config.APP_NAME)
    parser.add_argument("--selftest", action="store_true", help="Run automated headless engine self-test")
    args = parser.parse_args()

    setup_logging()

    if args.selftest:
        sys.exit(run_selftest())

    # Pygame initialization
    pygame.init()
    try:
        pygame.mixer.init(frequency=44100, size=-16, channels=1, buffer=1024)
    except Exception as exc:
        log.warning("pygame.mixer initialization failed (%s); audio disabled.", exc)

    log.info("Starting %s v%s", config.APP_NAME, config.APP_VERSION)
    ctx = build_context(headless=False)

    # Register all scenes
    scenes = ctx.scenes
    scenes.register("main_menu", lambda c: MainMenuScene(c))
    scenes.register("opponent_select", lambda c: OpponentSelectScene(c))
    scenes.register("pass_play_setup", lambda c: PassPlaySetupScene(c))
    scenes.register("vs_engine_setup", lambda c: VsEngineSetupScene(c))
    scenes.register("game", lambda c: GameScene(c))
    scenes.register("evaluate", lambda c: EvaluateScene(c))
    scenes.register("profile", lambda c: ProfileScene(c))
    scenes.register("about", lambda c: AboutScene(c))
    scenes.register("settings", lambda c: SettingsScene(c))
    scenes.register("confirm", lambda c: ConfirmScene(c))

    # Initial scene
    scenes.go("main_menu")

    # Main game loop
    running = True
    try:
        while running:
            # Re-read fps live from settings so UI updates apply instantly
            target_fps = getattr(ctx.settings.settings, "fps", config.DEFAULT_FPS)
            dt = ctx.clock.tick(target_fps) / 1000.0

            # Drain engine callbacks on main thread
            ctx.engines.poll()

            # Event handling
            for raw_event in pygame.event.get():
                if raw_event.type == pygame.QUIT:
                    running = False
                    break
                elif raw_event.type == pygame.KEYDOWN and raw_event.key == pygame.K_F11:
                    ctx.display.toggle_fullscreen()
                    continue
                elif raw_event.type == pygame.KEYDOWN and raw_event.key == pygame.K_F2:
                    ctx.display.toggle_reference(scenes.current_name)
                    continue

                event = ctx.display.translate_event(raw_event)
                if event is not None:
                    scenes.handle_event(event)

            if scenes.quit_requested:
                running = False
                break

            # Update & render
            scenes.update(dt)
            scenes.draw(ctx.display.surface)
            ctx.display.present()

    except Exception:
        err_msg = traceback.format_exc()
        log.error("Unhandled exception in game loop:\n%s", err_msg)
        try:
            draw_crash_screen(pygame.display.get_surface(), err_msg)
        except Exception:
            pass
    finally:
        log.info("Shutting down OpenBoard...")
        ctx.shutdown()
        pygame.quit()
        log.info("Shutdown complete.")


if __name__ == "__main__":
    main()
