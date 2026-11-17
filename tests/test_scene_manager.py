"""
tests/test_scene_manager.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~
Tests for SceneManager navigation and modal stacking logic.
"""

import pytest
from openboard.ui.scene_manager import SceneManager
from openboard.ui.scenes.base import Scene


class DummyScene(Scene):
    def __init__(self, ctx, name="dummy") -> None:
        super().__init__(ctx)
        self.name = name
        self.entered = False
        self.exited = False
        self.resumed_result = None
        self.updates = 0

    def on_enter(self, **params) -> None:
        self.entered = True
        self.params = params

    def on_exit(self) -> None:
        self.exited = True

    def on_resume(self, result=None) -> None:
        self.resumed_result = result

    def update(self, dt: float) -> None:
        self.updates += 1


class ModalScene(DummyScene):
    is_modal = True


def test_go_replaces_stack() -> None:
    sm = SceneManager(ctx=None)
    sm.register("s1", lambda ctx: DummyScene(ctx, "s1"))
    sm.register("s2", lambda ctx: DummyScene(ctx, "s2"))

    sm.go("s1", foo="bar")
    assert sm.current_name == "s1"
    first = sm._stack[0]
    assert first.entered
    assert first.params == {"foo": "bar"}

    sm.go("s2")
    assert sm.current_name == "s2"
    assert first.exited
    assert len(sm._stack) == 1


def test_push_pop_and_result_delivery() -> None:
    sm = SceneManager(ctx=None)
    sm.register("main", lambda ctx: DummyScene(ctx, "main"))
    sm.register("modal", lambda ctx: ModalScene(ctx, "modal"))

    sm.go("main")
    main_scene = sm._stack[0]

    sm.push("modal")
    assert sm.current_name == "modal"
    assert len(sm._stack) == 2

    # Update only top scene
    sm.update(0.016)
    assert sm._stack[-1].updates == 1
    assert main_scene.updates == 0

    # Pop with result
    sm.pop(result=True)
    assert sm.current_name == "main"
    assert len(sm._stack) == 1
    assert main_scene.resumed_result is True


def test_request_quit() -> None:
    sm = SceneManager(ctx=None)
    assert not sm.quit_requested
    sm.request_quit()
    assert sm.quit_requested
