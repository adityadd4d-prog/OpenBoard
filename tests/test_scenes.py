"""
tests/test_scenes.py
~~~~~~~~~~~~~~~~~~~~
Integration tests rendering all 10 scenes in headless/dummy video driver.
"""

from __future__ import annotations

import os
import pytest

os.environ["SDL_VIDEODRIVER"] = "dummy"
import pygame

from openboard import paths
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


@pytest.fixture(scope="module", autouse=True)
def init_pygame():
    pygame.init()
    yield
    pygame.quit()


def test_all_10_scenes_render(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "user_data_dir", lambda: tmp_path)
    monkeypatch.setattr(paths, "log_dir", lambda: tmp_path / "logs")

    ctx = build_context(headless=False)
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

    scene_names = [
        "main_menu",
        "opponent_select",
        "pass_play_setup",
        "vs_engine_setup",
        "game",
        "evaluate",
        "profile",
        "about",
        "settings",
    ]

    for name in scene_names:
        scenes.go(name)
        scenes.update(0.016)
        scenes.draw(ctx.display.surface)
        ctx.display.present()
        assert scenes.current_name == name

    # Test confirm modal pushed on top
    scenes.push("confirm", title="TEST CONFIRM", message="Are you sure?", on_confirm=lambda: None)
    scenes.update(0.016)
    scenes.draw(ctx.display.surface)
    ctx.display.present()
    assert scenes.current_name == "confirm"

    ctx.shutdown()
