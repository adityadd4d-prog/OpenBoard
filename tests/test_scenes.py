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


def test_promotion_popup_in_game_scene(tmp_path, monkeypatch):
    import chess
    monkeypatch.setattr(paths, "user_data_dir", lambda: tmp_path)
    monkeypatch.setattr(paths, "log_dir", lambda: tmp_path / "logs")

    ctx = build_context(headless=False)
    scenes = ctx.scenes
    scenes.register("game", lambda c: GameScene(c))
    scenes.register("confirm", lambda c: ConfirmScene(c))
    scenes.go("game")

    game_scene = scenes._stack[-1]
    fen = "7k/P7/8/8/8/8/8/4K3 w - - 0 1"
    game_scene.session._board = chess.Board(fen)
    game_scene.board_view.set_board(game_scene.session.board)

    a7_coords = game_scene.board_view._square_coords(chess.A7)
    a8_coords = game_scene.board_view._square_coords(chess.A8)
    game_scene.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=a7_coords))
    game_scene.handle_event(pygame.event.Event(pygame.MOUSEBUTTONUP, button=1, pos=a8_coords))

    assert game_scene.board_view._promotion_active is True

    # Draw game scene while promotion popup is active (verifies rendering)
    scenes.draw(ctx.display.surface)
    ctx.display.present()

    # Choose Knight via keyboard shortcut
    game_scene.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_n))
    assert game_scene.board_view._promotion_active is False
    assert game_scene.session.last_move == chess.Move(chess.A7, chess.A8, promotion=chess.KNIGHT)

    ctx.shutdown()


def test_game_over_dialog_play_again_and_back(tmp_path, monkeypatch):
    from openboard.core.session import PlayerInfo
    monkeypatch.setattr(paths, "user_data_dir", lambda: tmp_path)
    monkeypatch.setattr(paths, "log_dir", lambda: tmp_path / "logs")

    ctx = build_context(headless=False)
    scenes = ctx.scenes
    scenes.register("game", lambda c: GameScene(c))
    scenes.register("confirm", lambda c: ConfirmScene(c))
    scenes.register("opponent_select", lambda c: OpponentSelectScene(c))

    scenes.go("game", mode="pass_play", white=PlayerInfo("P1", "human"), black=PlayerInfo("P2", "human"))
    game_scene = scenes._stack[-1]

    # Trigger game over dialog
    game_scene._show_game_over_dialog()
    assert scenes.current_name == "confirm"
    confirm_scene = scenes._stack[-1]
    assert confirm_scene.yes_label == "PLAY AGAIN"
    assert confirm_scene.no_label == "BACK"

    # Click BACK -> returns to opponent_select
    confirm_scene._on_no()
    assert scenes.current_name == "opponent_select"

    # Click PLAY AGAIN -> restarts game
    scenes.go("game", mode="pass_play", white=PlayerInfo("P1", "human"), black=PlayerInfo("P2", "human"))
    game_scene = scenes._stack[-1]
    game_scene._show_game_over_dialog()
    confirm_scene = scenes._stack[-1]
    confirm_scene._on_yes()
    assert scenes.current_name == "game"
    assert scenes._stack[-1].session.white.name == "P1"

    ctx.shutdown()


def test_evaluate_scene_board_interactivity_and_auto_fen(tmp_path, monkeypatch):
    import chess
    monkeypatch.setattr(paths, "user_data_dir", lambda: tmp_path)
    monkeypatch.setattr(paths, "log_dir", lambda: tmp_path / "logs")

    ctx = build_context(headless=False)
    scenes = ctx.scenes
    scenes.register("evaluate", lambda c: EvaluateScene(c))
    scenes.go("evaluate")

    eval_scene = scenes._stack[-1]
    assert eval_scene.board_view.interactive == "both"

    # Move e2 to e4
    e2_coords = eval_scene.board_view._square_coords(chess.E2)
    e4_coords = eval_scene.board_view._square_coords(chess.E4)
    eval_scene.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=e2_coords))
    eval_scene.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=e4_coords))

    expected_fen_1 = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1"
    assert eval_scene._parsed_board.fen() == expected_fen_1
    assert eval_scene.text_area.text == expected_fen_1
    assert not hasattr(eval_scene, "format_chips")

    # Move e7 to e5
    e7_coords = eval_scene.board_view._square_coords(chess.E7)
    e5_coords = eval_scene.board_view._square_coords(chess.E5)
    eval_scene.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=e7_coords))
    eval_scene.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=e5_coords))

    expected_fen_2 = "rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2"
    assert eval_scene._parsed_board.fen() == expected_fen_2
    assert eval_scene.text_area.text == expected_fen_2

    ctx.shutdown()


def test_text_area_wrapping_caret_and_selection(tmp_path, monkeypatch):
    from openboard.ui.widgets import TextArea, _clipboard_get
    pygame.init()
    ta = TextArea((100, 100, 400, 120), text="hello world test")
    assert ta.caret == 16

    # Select all via Ctrl+A
    ta.focused = True
    ta.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_a, mod=pygame.KMOD_CTRL))
    assert ta.has_selection()
    assert ta.get_selected_text() == "hello world test"

    # Copy via Ctrl+C
    ta.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_c, mod=pygame.KMOD_CTRL))
    assert _clipboard_get() == "hello world test"

    # Replace with set_text
    ta.set_text("new text")
    assert ta.text == "new text"
    assert ta.caret == 8


def test_vs_engine_no_draw_button(tmp_path, monkeypatch):
    from openboard.core.session import PlayerInfo
    monkeypatch.setattr(paths, "user_data_dir", lambda: tmp_path)
    monkeypatch.setattr(paths, "log_dir", lambda: tmp_path / "logs")

    ctx = build_context(headless=False)
    scenes = ctx.scenes
    scenes.register("game", lambda c: GameScene(c))
    scenes.go("game", mode="vs_engine", white=PlayerInfo("Human", "human"), black=PlayerInfo("Stockfish", "engine"))

    vs_scene = scenes._stack[-1]
    assert vs_scene.draw_btn is None
    assert vs_scene.resign_btn.rect.width == 580
    ctx.shutdown()


def test_pass_play_draw_offer_and_accept(tmp_path, monkeypatch):
    from openboard.core.session import PlayerInfo
    monkeypatch.setattr(paths, "user_data_dir", lambda: tmp_path)
    monkeypatch.setattr(paths, "log_dir", lambda: tmp_path / "logs")

    ctx = build_context(headless=False)
    scenes = ctx.scenes
    scenes.register("game", lambda c: GameScene(c))
    scenes.register("confirm", lambda c: ConfirmScene(c))
    scenes.go("game", mode="pass_play", white=PlayerInfo("Alice", "human"), black=PlayerInfo("Bob", "human"))

    game_scene = scenes._stack[-1]
    assert game_scene.draw_btn is not None
    assert game_scene.draw_btn.rect.width == 280

    # Trigger draw offer
    game_scene._on_draw_click()
    assert scenes.current_name == "confirm"
    confirm_scene = scenes._stack[-1]
    assert "Alice offers a draw" in confirm_scene.message

    # Accept draw
    confirm_scene._on_yes()
    game_scene.update(0.016)
    assert game_scene.session.is_over
    assert game_scene.session.outcome.reason.name == "DRAW_AGREED"
    assert scenes.current_name == "confirm"
    assert scenes._stack[-1].title == "GAME OVER"
    ctx.shutdown()


def test_main_menu_static_board_illustration(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "user_data_dir", lambda: tmp_path)
    monkeypatch.setattr(paths, "log_dir", lambda: tmp_path / "logs")

    ctx = build_context(headless=False)
    scenes = ctx.scenes
    scenes.register("main_menu", lambda c: MainMenuScene(c))
    scenes.go("main_menu")

    menu_scene = scenes._stack[-1]
    assert not hasattr(menu_scene, "_bob_t")
    ctx.shutdown()


def test_evaluate_text_input_resilience_and_no_crash(tmp_path, monkeypatch):
    import chess
    from openboard.engines.types import SearchResult
    monkeypatch.setattr(paths, "user_data_dir", lambda: tmp_path)
    monkeypatch.setattr(paths, "log_dir", lambda: tmp_path / "logs")

    ctx = build_context(headless=False)
    scenes = ctx.scenes
    scenes.register("evaluate", lambda c: EvaluateScene(c))
    scenes.go("evaluate")

    eval_scene = scenes._stack[-1]
    ta = eval_scene.text_area

    # Focus text area
    eval_scene.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=ta.rect.center))
    assert ta.focused

    # Test typing via KEYDOWN with unicode
    ta.set_text("")
    eval_scene.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_e, unicode="e", mod=0))
    eval_scene.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_4, unicode="4", mod=0))
    assert ta.text == "e4"

    # Test FEN with mismatched PV line doesn't crash san_line or draw
    crash_fen = "2r2rk1/1p2bppp/p3pn2/3p4/3P4/2P1PN2/PP3PPP/2R2RK1 b - - 0 15"
    ta.set_text(crash_fen)
    eval_scene._parse_now()
    assert eval_scene._parsed_board.fen() == crash_fen

    fake_result = SearchResult(
        request_id=1,
        backend="stockfish",
        depth=12,
        score_cp=20,
        mate_in=None,
        best_uci="e2e4",
        pv_uci=("e2e4", "e7e5"),
        nodes=1000,
        seconds=0.1,
        reason="Stockfish 19",
    )
    eval_scene._eval_result = fake_result
    eval_scene._eval_fen = chess.STARTING_FEN

    surf = pygame.Surface((1600, 900))
    eval_scene.draw(surf)

    # Editing text clears old evaluation
    ta.handle_event(pygame.event.Event(pygame.TEXTINPUT, text=" "))
    assert eval_scene._eval_result is None

    ctx.shutdown()


def test_evaluate_depth_and_time_limit_input(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "user_data_dir", lambda: tmp_path)
    monkeypatch.setattr(paths, "log_dir", lambda: tmp_path / "logs")

    ctx = build_context(headless=False)
    scenes = ctx.scenes
    scenes.register("evaluate", lambda c: EvaluateScene(c))
    scenes.go("evaluate")

    eval_scene = scenes._stack[-1]
    li = eval_scene.limit_input

    # Default DEPTH mode
    assert eval_scene.limit_chips.selected == 0
    assert li.text == "12"
    assert not li.invalid

    # Click limit_input to focus
    eval_scene.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=li.rect.center))
    assert li.focused
    assert not eval_scene.text_area.focused

    # Ctrl+A and type 18 via KEYDOWN unicode
    eval_scene.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_a, mod=pygame.KMOD_CTRL))
    assert li.all_selected
    eval_scene.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_1, unicode="1", mod=0))
    eval_scene.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_8, unicode="8", mod=0))
    assert li.text == "18"
    assert not li.invalid
    assert eval_scene.eval_btn.enabled

    # Dot rejected in DEPTH mode
    eval_scene.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_PERIOD, unicode=".", mod=0))
    assert li.text == "18"

    # Up/Down arrow stepping
    eval_scene.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_UP, mod=0))
    assert li.text == "19"
    eval_scene.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_DOWN, mod=0))
    assert li.text == "18"

    # Invalid range (e.g. 99) disables eval_btn
    li.set_text("99")
    assert li.invalid
    assert not eval_scene.eval_btn.enabled

    # Switch to TIME chip
    eval_scene.limit_chips.selected = 2
    eval_scene._on_limit_chip_change(2)
    assert li.text == "2.0"
    assert not li.invalid
    assert eval_scene.eval_btn.enabled

    # Type 5.5 in TIME mode
    eval_scene.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=li.rect.center))
    eval_scene.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_a, mod=pygame.KMOD_CTRL))
    eval_scene.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_5, unicode="5", mod=0))
    eval_scene.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_PERIOD, unicode=".", mod=0))
    eval_scene.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_5, unicode="5", mod=0))
    assert li.text == "5.5"
    assert not li.invalid

    # Up arrow steps by 0.5 in TIME mode
    eval_scene.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_UP, mod=0))
    assert li.text == "6.0"

    # Verify F2 reference overlay has been completely removed from Display
    assert not hasattr(ctx.display, "toggle_reference")

    ctx.shutdown()


def test_secondary_color_and_text_wrapping():
    from openboard.ui import theme

    assert theme.SECONDARY == (63, 111, 108)  # #3F6F6C

    # Long sentence wraps within max_w
    max_w = 180
    long_msg = "Stockfish 19 selected for high-depth evaluation (depth 14 > Python limit 4)"
    lines = theme.wrap_text(long_msg, "small", max_w)
    assert len(lines) >= 2
    f = theme.font("small")
    for line in lines:
        assert f.size(line)[0] <= max_w

    # Single unspaced long token breaks cleanly within max_w
    url = "https://github.com/official-stockfish/Stockfish/blob/master/src/search.cpp"
    url_lines = theme.wrap_text(url, "small", max_w)
    assert len(url_lines) >= 2
    for line in url_lines:
        assert f.size(line)[0] <= max_w
    assert "".join(url_lines) == url

    # Explicit newlines preserved
    multi = theme.wrap_text("Line one\nLine two", "body", 500)
    assert multi == ["Line one", "Line two"]


def test_profile_match_history_opens_evaluate_correctly(tmp_path, monkeypatch):
    import chess
    monkeypatch.setattr(paths, "user_data_dir", lambda: tmp_path)
    monkeypatch.setattr(paths, "log_dir", lambda: tmp_path / "logs")

    ctx = build_context(headless=False)
    scenes = ctx.scenes
    scenes.register("profile", lambda c: ProfileScene(c))
    scenes.register("evaluate", lambda c: EvaluateScene(c))

    pgn_with_moves = (
        '[Event "?"]\n[Site "?"]\n[Date "????.??.??"]\n[Round "?"]\n'
        '[White "Slayer"]\n[Black "Alex"]\n[Result "1-0"]\n\n'
        '1. e4 e5 2. Nf3 Nc6 1-0'
    )
    ctx.history.add(
        {
            "started_at": "2026-11-18T00:00:00+00:00",
            "mode": "pass_play",
            "opponent": "Alex",
            "engine_level": None,
            "time_control": "RAPID 10 + 0",
            "player_color": "white",
            "result": "won",
            "reason": "resignation",
            "moves": 4,
            "pgn": pgn_with_moves,
            "backends": None,
        }
    )

    scenes.go("profile")
    profile_scene = scenes._stack[-1]
    assert len(profile_scene.matches) == 1

    # Click the first match row inside history_list
    click_pos = (profile_scene.history_list.rect.x + 40, profile_scene.history_list.rect.y + 20)
    profile_scene.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=click_pos))

    assert scenes.current_name == "evaluate"
    eval_scene = scenes._stack[-1]
    expected_fen = "r1bqkbnr/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 2 3"
    assert eval_scene._parse_error is None
    assert eval_scene._parsed_board.fen() == expected_fen
    assert eval_scene.text_area.text == expected_fen
    assert eval_scene.eval_btn.enabled is True
    assert eval_scene.board_view.last_move == chess.Move.from_uci("b8c6")
    assert eval_scene.menu_btn.label == "BACK"

    # Clicking BACK returns to profile
    eval_scene.menu_btn.on_click()
    assert scenes.current_name == "profile"

    ctx.shutdown()


def test_no_clock_option_in_pass_play_and_vs_engine(tmp_path, monkeypatch):
    import math
    from openboard import config
    from openboard.ui.scenes.pass_play_setup import PassPlaySetupScene
    from openboard.ui.scenes.vs_engine_setup import VsEngineSetupScene

    monkeypatch.setattr(paths, "user_data_dir", lambda: tmp_path)
    monkeypatch.setattr(paths, "log_dir", lambda: tmp_path / "logs")

    ctx = build_context(headless=False)
    scenes = ctx.scenes
    scenes.register("pass_play_setup", lambda c: PassPlaySetupScene(c))
    scenes.register("vs_engine_setup", lambda c: VsEngineSetupScene(c))
    scenes.register("game", lambda c: GameScene(c))

    # 1. Pass & Play setup exposes NO CLOCK and launches unlimited game
    scenes.go("pass_play_setup")
    pp_scene = scenes._stack[-1]
    assert "NO CLOCK" in pp_scene.tc_chips.options
    unlimited_idx = list(config.TIME_CONTROLS.keys()).index("unlimited")
    pp_scene.tc_chips.selected = unlimited_idx
    pp_scene._on_tc_change(unlimited_idx)
    pp_scene._start_game()
    assert scenes.current_name == "game"
    game_scene = scenes._stack[-1]
    assert game_scene.time_control == config.UNLIMITED
    assert game_scene.session.clock.is_unlimited is True
    assert math.isinf(game_scene.session.clock.remaining(0))

    # 2. VS Engine setup exposes NO CLOCK and launches unlimited game
    scenes.go("vs_engine_setup")
    vs_scene = scenes._stack[-1]
    assert "NO CLOCK" in vs_scene.tc_chips.options
    assert vs_scene.tc_chips.selected == unlimited_idx  # persisted preference
    vs_scene._start_game()
    assert scenes.current_name == "game"
    game_scene2 = scenes._stack[-1]
    assert game_scene2.time_control == config.UNLIMITED
    assert game_scene2.session.clock.is_unlimited is True

    ctx.shutdown()


def test_about_scene_redesign_keeps_repo_buttons(tmp_path, monkeypatch):
    from openboard.ui.scenes.about import AboutScene

    monkeypatch.setattr(paths, "user_data_dir", lambda: tmp_path)
    monkeypatch.setattr(paths, "log_dir", lambda: tmp_path / "logs")

    ctx = build_context(headless=False)
    scenes = ctx.scenes
    scenes.register("about", lambda c: AboutScene(c))
    scenes.go("about")

    about_scene = scenes._stack[-1]
    assert about_scene.github_btn.label == "GITHUB REPO ↗"
    assert about_scene.stockfish_btn.label == "STOCKFISH SOURCE ↗"
    assert not hasattr(about_scene, "credits_list")

    surf = pygame.Surface((1600, 900))
    about_scene.draw(surf)
    ctx.shutdown()


def test_profile_tc_filter_includes_all_and_filters_match_history(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "user_data_dir", lambda: tmp_path)
    monkeypatch.setattr(paths, "log_dir", lambda: tmp_path / "logs")

    ctx = build_context(headless=False)
    scenes = ctx.scenes
    scenes.register("profile", lambda c: ProfileScene(c))

    for tc_label, opp in (("BLITZ 3 + 2", "BlitzOpp"), ("RAPID 10 + 0", "RapidOpp"), ("NO CLOCK", "NoClockOpp")):
        ctx.history.add(
            {
                "started_at": "2026-11-18T00:00:00+00:00",
                "mode": "pass_play",
                "opponent": opp,
                "engine_level": None,
                "time_control": tc_label,
                "player_color": "white",
                "result": "won",
                "reason": "resignation",
                "moves": 10,
                "pgn": "1. e4 e5 1-0",
                "backends": None,
            }
        )

    scenes.go("profile")
    prof = scenes._stack[-1]

    # Starts on ALL showing all 3 matches
    assert prof._current_tc_label() == "ALL"
    assert len(prof.matches) == 3

    # Cycle to BLITZ
    prof._cycle_time_control()
    assert prof._current_tc_label() == "BLITZ · 3 + 2"
    assert [m.opponent for m in prof.matches] == ["BlitzOpp"]

    # Cycle to RAPID
    prof._cycle_time_control()
    assert prof._current_tc_label() == "RAPID · 10 + 0"
    assert [m.opponent for m in prof.matches] == ["RapidOpp"]

    # Cycle to NO CLOCK
    prof._cycle_time_control()
    assert prof._current_tc_label() == "NO CLOCK"
    assert [m.opponent for m in prof.matches] == ["NoClockOpp"]

    # Cycle wraps back to ALL
    prof._cycle_time_control()
    assert prof._current_tc_label() == "ALL"
    assert len(prof.matches) == 3

    ctx.shutdown()


def test_game_moves_list_scrollable_in_pass_play_and_vs_engine(tmp_path, monkeypatch):
    from openboard.core.session import PlayerInfo

    monkeypatch.setattr(paths, "user_data_dir", lambda: tmp_path)
    monkeypatch.setattr(paths, "log_dir", lambda: tmp_path / "logs")

    ctx = build_context(headless=False)
    scenes = ctx.scenes
    scenes.register("game", lambda c: GameScene(c))

    sans = [
        "e4", "e5", "Nf3", "Nc6", "Bb5", "a6", "Ba4", "Nf6", "O-O", "Be7",
        "Re1", "b5", "Bb3", "d6", "c3", "O-O", "h3", "Nb8", "d4", "Nbd7",
        "Nbd2", "Bb7", "Bc2", "Re8", "Nf1", "Bf8", "Ng3", "g6", "a4", "c5",
    ]

    for mode in ("pass_play", "vs_engine"):
        black_pi = PlayerInfo("Alex", "human") if mode == "pass_play" else PlayerInfo("Engine", "engine", engine_level=2)
        scenes.go("game", mode=mode, white=PlayerInfo("Player 1", "human"), black=black_pi)
        g = scenes._stack[-1]
        for san in sans:
            mv = g.session.board.parse_san(san)
            g.session.try_move(mv.from_square, mv.to_square, mv.promotion)
        g.update(0.016)
        max_scroll = g.moves_list._max_scroll()
        assert max_scroll > 0
        assert g.moves_list.scroll_y == max_scroll

        # Scroll up via mouse wheel
        wheel_pos = g.moves_list.rect.center
        g.handle_event(pygame.event.Event(pygame.MOUSEWHEEL, y=3, pos=wheel_pos))
        scrolled_y = g.moves_list.scroll_y
        assert scrolled_y < max_scroll

        # Subsequent update frames MUST NOT reset scroll back to bottom
        g.update(0.016)
        g.update(0.016)
        assert g.moves_list.scroll_y == scrolled_y

        # Scrollbar drag works too
        sb = g.moves_list._scrollbar_rects()
        assert sb is not None
        track, thumb = sb
        g.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=thumb.center))
        g.handle_event(pygame.event.Event(pygame.MOUSEMOTION, pos=(thumb.centerx, track.top)))
        g.handle_event(pygame.event.Event(pygame.MOUSEBUTTONUP, button=1, pos=(thumb.centerx, track.top)))
        assert g.moves_list.scroll_y == 0

    ctx.shutdown()


def test_settings_scene_smart_select_three_modes(tmp_path, monkeypatch):
    from openboard.ui.scenes.settings import SettingsScene

    monkeypatch.setattr(paths, "user_data_dir", lambda: tmp_path)
    monkeypatch.setattr(paths, "log_dir", lambda: tmp_path / "logs")

    ctx = build_context(headless=False)
    # Simulate Stockfish available so all 3 options are selectable
    ctx.engines.sf_backend.available = True
    scenes = ctx.scenes
    scenes.register("settings", lambda c: SettingsScene(c))
    scenes.go("settings")

    s = scenes._stack[-1]
    assert s.engine_chips.options == ["AUTO", "CUSTOM ENGINE", "STOCKFISH"]
    assert s.engine_chips.selected == 0

    s.engine_chips.selected = 1
    s._on_engine_mode_change(1)
    assert ctx.settings.engine_mode == "custom"
    assert ctx.settings.smart_engine is False

    s.engine_chips.selected = 2
    s._on_engine_mode_change(2)
    assert ctx.settings.engine_mode == "stockfish"
    assert ctx.settings.smart_engine is True
    assert s.depth_chips.enabled is False

    s.engine_chips.selected = 0
    s._on_engine_mode_change(0)
    assert ctx.settings.engine_mode == "auto"
    assert ctx.settings.smart_engine is True
    assert s.depth_chips.enabled is True

    # Selecting depth level 2 persists custom_max_depth=2
    assert s.depth_chips.options == ["1", "2", "3", "4", "5", "6"]
    s.depth_chips.selected = 1
    s._on_depth_change(1)
    assert ctx.settings.custom_max_depth == 2

    ctx.shutdown()
