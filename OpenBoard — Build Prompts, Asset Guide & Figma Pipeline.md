# OpenBoard — Build Prompts, Asset Guide & Figma Pipeline

Built around your finalized design: 1600×900 letterbox, pygame UI, python-chess, your own `engine.py` plus a bundled Stockfish with automatic switching, and assets exported from Figma. Every tool and script here is Python.

## 1. How to use this document

1. Paste the **Shared Context Block** (section 3) at the top of every prompt.
2. Paste one file's prompt under it. Build in the order given in section 10.
3. A file is done only when its *Done when* line passes (self-test, pytest, or demo).
4. ⚠ marks a decision I made where your mockups were silent. Change any of them.

## 2. Facts read from your mockups

These come from the 10 screens in your zip (all 1600×900). Every prompt below assumes them.

- **Palette:** background `#F3E8FA`, card `#FBF4FF`, ink `#302A3B`, primary purple `#A085BB`, accent purple `#755489`, tint `#E3D5EC`, card inner border `#C7B1D2`. The 'Board' half of the wordmark is a vivid purple; sample it in Figma.
- **Style:** flat fills, \~3 px ink borders, hard offset shadow (ink, no blur, \~6–8 px down-right), bold uppercase labels, Inter-style typeface (confirm in Figma's text panel).
- **Game board:** 88 px squares, 704 px board, top-left of the squares at (120, 136). Rank numbers on the left, file letters underneath. The Evaluate board looks like ≈72 px squares; measure it.
- **Game screen:** board on the left. Right column: mode label (RAPID · 10 + 0), MENU button, two player cards with clocks (the side to move is the dark, inverted card), a status line (WHITE TO MOVE), a MOVES panel, and DRAW / RESIGN buttons.
- **VS Engine has 8 levels** (BEGINNER … EXPERT) but your `engine.py` has 5. The mapping is defined in the `config.py` prompt.
- **Time controls:** BLITZ 3 + 2 and RAPID 10 + 0.
- **Pass & Play:** Player 1 comes from the profile, Player 2 is typed, colours are random.
- **Settings:** AUDIO, USE BOOK, SMART ENGINE toggles; frame rate 30 / 60 / 90 / 120; DONE. ⚠ SMART ENGINE ON lets the router use Stockfish; OFF forces the built-in Python engine only.
- **Evaluate:** input type FEN / SAN / LAN, text box, SEARCH LIMIT DEPTH / AUTO / TIME with a number field (plies or seconds), EVALUATE button, a result such as +0.20 with a word (EQUAL), a caption (Example · depth 20) and a move line.
- **Profile:** PLAYED / WON / LOST / DRAWN, crest, editable name, preferred time control, MATCH HISTORY rows (opponent, mode · moves, result).
- **Confirm:** modal CONFIRM ACTION with NO / YES over a dimmed screen.
- **About:** wordmark, CONTROLS list, GitHub and credits line.
- **Differences from your flowchart:** the mockups add Settings (gear on the main menu) and the Confirm modal.

## 3. Shared context block

Paste this above every file prompt.

```text
You are a senior Python engineer helping build OpenBoard, an offline desktop chess game.
STACK: Python 3.11+, pygame 2.x, python-chess (import name: chess), platformdirs. Pillow/requests only inside tools/. No other runtime dependencies unless the prompt says so.
ARCHITECTURE: package openboard/ with core/, engines/, storage/ (these three NEVER import pygame) and ui/ (the only place pygame is used). Scenes never import each other; they navigate by name through SceneManager and receive shared services from AppContext.
DISPLAY: fixed internal resolution 1600x900, letterboxed to the window. All UI coordinates are in that space.
STYLE: neo-brutalist. Palette lives in ui/theme.py: BG #F3E8FA, CARD #FBF4FF, INK #302A3B, PURPLE #A085BB, ACCENT #755489, TINT #E3D5EC. 3px ink borders, hard offset shadows, Inter font.
CODE RULES: type hints everywhere; dataclasses with slots=True; no global mutable state; logging via logging.getLogger('openboard.<module>'); docstring on every public class and function; no print() outside demos/tools; pathlib only; never block the UI thread; pure logic gets pytest tests.
OUTPUT: complete files only, no TODO stubs. Put a short header comment listing any assumptions. If something is ambiguous, choose the simplest option and say so in that comment.
```

## 4. Assets

### 4.1 What to export from Figma

| File name | What it is | Figma frame → export | Used by |
| --- | --- | --- | --- |
| `piece_wK` `piece_wQ` `piece_wR` `piece_wB` `piece_wN` `piece_wP` `piece_bK` `piece_bQ` `piece_bR` `piece_bB` `piece_bN` `piece_bP` | 12 pieces, transparent | 88×88 frame → PNG @4x (352×352) | board\_view |
| `bg_main` | main menu background: lavender plus the large knight silhouette, no widgets | 1600×900 → PNG @1x | main\_menu |
| `illus_iso_board` | isometric board with pieces, transparent | artwork + 16 px margin → PNG @2x | main\_menu |
| `bg_silhouettes` | rook and king silhouettes background | 1600×900 → @1x | pass\_play\_setup, vs\_engine\_setup, settings |
| `bg_profile` | pawn / queen silhouette backdrop | 1600×900 → @1x (you already have Profile backdrop.png) | profile |
| `bg_about` | tiled rook pattern | 1600×900 → @1x | about |
| `card_pass_play` `card_vs_engine` | tilted cards with crown / knight art, shadow included, transparent | artwork + margin → @2x | opponent\_select |
| `player_crest` | knight crest (196 px; you have it) | export @4x if you want it sharper | profile |
| `emblem` | small knight emblem (112 px; you have it) | existing file is fine | about |
| `app_icon` | 512 px app icon (you have it) | existing file is fine | window icon, packaging |
| `icon_gear` `icon_pencil` | 32×32 icons, transparent | @4x | main\_menu, profile |

**Drawn in code, never exported:** buttons, panels, text inputs, chips, toggles, level chips, board squares and frame, highlights, legal-move dots, the dim overlay, the purple diagonal panel on the opponent screen. Code-drawn UI stays crisp at any window size and removes dozens of exports.

**Reference only (do not ship):** the 10 full-screen mockups. They go into `assets/reference/` and power an F2 pixel-overlay debug mode so you can line up every widget with your design.

### 4.2 Preparing the Figma file (once)

1. Add a page named `Export`.
2. For every row in 4.1 create a **top-level Frame** on that page named exactly like the file (without `.png`). Use frames, not groups.
3. **Pieces:** 88×88 frame, fill removed (transparent), square-colour rectangles deleted, piece centred. Keep the outlines (dark outline on white pieces, white halo on black pieces).
4. **Backgrounds:** 1600×900 frame containing only decor. Hide buttons, panels and text.
5. **Illustrations and cards with shadows:** make the frame at least 16 px larger than the artwork on every side so the shadow is not cut off.
6. Convert any text baked into artwork (the card labels) to outlines with Ctrl/Cmd+Shift+O.
7. Layer names use letters, digits and underscores only.

### 4.3 Manual export

Select all frames on the Export page → Export panel → `+` → PNG → set the scale from the table (pieces 4x, icons 4x, illustrations and cards 2x, backgrounds 1x) → **Export N layers** → unzip into `assets/raw/`. The file pixel size is the frame size × the scale; `build_assets.py` verifies this.

### 4.4 Automatic export with Python

1. In Figma: profile menu → Settings → Security → **Personal access tokens** → create one with the **File content: read-only** scope.
2. Copy the file key from the URL: `figma.com/design/<FILE_KEY>/…`.
3. Run:

```bash
export FIGMA_TOKEN=figd_xxx        # Windows: set FIGMA_TOKEN=figd_xxx
python tools/figma_export.py --file-key <FILE_KEY>
python tools/build_assets.py build
```

Image links returned by Figma expire after about 30 days, so the script downloads the files immediately instead of storing links.

### 4.5 Folder layout

```text
assets/
  manifest.toml        # source of truth (generated by build_assets.py --init-manifest)
  raw/                 # untouched Figma exports (commit these)
  reference/           # the 10 mockups, for the F2 overlay (do not ship)
  build/               # generated, shipped: pieces/ bg/ ui/ icons/ sounds/ fonts/ index.json
bin/stockfish/{win,linux,mac}/   # bundled engine builds + LICENSE + VERSION.txt
```

### 4.6 Things that do not come from Figma

- **Font:** Inter static TTFs (Regular, Medium, SemiBold, Bold, ExtraBold) from Google Fonts or rsms.me/inter into `assets/build/fonts/`. pygame cannot use variable fonts, so take the *static* files. Inter is SIL OFL; credit it in About.
- **Sounds:** generated by `tools/make_sounds.py` (placeholders you can replace later).
- **Stockfish:** download the official build for each OS from stockfishchess.org/download and place it with `tools/fetch_stockfish.py`. It is GPLv3: ship its license text and link to its source from About.
- **Your zip:** the file names contain the `·` character that unzip mangles to `#U00b7`; `build_assets.py --import-zip` renames and files them correctly.

## 5. Prompts: asset tooling

### tools/figma\_export.py

```text
FILE: tools/figma_export.py. Dependency: requests.
Write a CLI script (argparse) that downloads PNG exports of named frames from a Figma file using the REST API.
Inputs: env FIGMA_TOKEN (never print it); --file-key, or env FIGMA_FILE_KEY, or --url (parse the key from figma.com/design/<key>/ or /file/<key>/); --page (default 'Export'); --manifest (default assets/manifest.toml); --out (default assets/raw); --only name1,name2; --force; --list.
Steps:
1. GET https://api.figma.com/v1/files/{key}?depth=2 with header X-Figma-Token. Find the page by name; collect its direct child frames as {name: node_id}. --list prints them and exits.
2. Read the manifest with tomllib. Each [[asset]] has name, scale (0.01-4), kind. Report manifest assets with no frame and frames not in the manifest.
3. Group node ids in chunks of 40 per distinct scale and call GET /v1/images/{key}?ids=<comma list>&format=png&scale=<S>&use_absolute_bounding_box=true. The response maps id -> url (null means the render failed).
4. Download each url (no auth header) to out/<name>.png. Skip existing files unless --force. Verify the PNG signature and non-zero size.
5. Errors: 403 -> explain how to create a token with the File content read-only scope; 404 -> wrong file key; 429 -> sleep Retry-After then retry (max 3); network timeouts 20 s with 3 retries and backoff.
6. Print a table (name, scale, status OK/SKIPPED/MISSING/FAILED). Exit non-zero if any required asset failed. Write out/_export_log.json with timestamps and node ids.
DONE WHEN: with a valid token every manifest frame lands in assets/raw/; with a bad token you get a clear message and no traceback.
```

### tools/build\_assets.py

```text
FILE: tools/build_assets.py. Dependencies: Pillow, stdlib tomllib/json.
Write a CLI with subcommands: init-manifest, import-zip, from-mockup, build, check, preview.
MANIFEST (assets/manifest.toml): [meta] design_w=1600 design_h=900. One [[asset]] per row of the asset table: name, kind (piece|bg|illus|card|icon|app), scale (source scale), src_px (expected raw size as [w,h]), out (list of output sizes; pieces use [88,72]; other kinds keep native size), alpha (bool). init-manifest writes the full manifest (generate the 12 piece entries in a loop).
import-zip PATH: extract the Figma zip you already have; fix mangled names ('#U00b7' or the middle-dot); copy the ten numbered screens into assets/reference/ as main_menu.png, opponent.png, pass_play.png, vs_engine.png, game.png, evaluate.png, profile.png, about.png, settings.png, confirm.png; copy 'Profile backdrop.png' -> raw/bg_profile.png, 'Player crest.png' -> raw/player_crest.png, 'OpenBoard emblem.png' -> raw/emblem.png, the 512 app icon -> raw/app_icon.png.
from-mockup: fallback for when transparent pieces are not exported yet. Slice the 12 pieces from assets/reference/game.png: squares are 88 px, the top-left of a1's rank-8 row is (120,136); white K,Q,R,B,N from rank 1 (e1,d1,a1,c1,b1) and P from a2; black from rank 8 and a7. For each crop, take the square's own background colour from a corner pixel and flood-fill it to transparent from all four edges only (tolerance ~6), so interior whites and the halo outline survive; feather the alpha edge by 1 px. Save to raw/ at 88x88 and warn that these are not hi-res.
build: for each manifest asset load raw/<name>.png, validate (file exists; size equals src_px within 1 px, else warn; alpha channel present when alpha=true; pieces must be square), then resample with LANCZOS to every out size and save optimized PNGs to assets/build/<kind>/<name>.png (pieces: build/pieces/<size>/<name>.png). Backgrounds are resized to exactly 1600x900. Create app.ico (16,32,48,64,128,256) and app.icns from app_icon. Write assets/build/index.json mapping logical name -> relative path(s) and size; ui/assets.py reads only this file.
check: validate only, print a table (name, expected, actual, status), exit non-zero on any error.
preview: write assets/build/_preview.png showing all 12 pieces on a light and a dark square (#F3E8FA / #A085BB) at 88 px.
DONE WHEN: init-manifest + import-zip + from-mockup + build runs on a fresh checkout and preview shows 12 clean pieces; check exits 0.
```

### tools/make\_sounds.py

```text
FILE: tools/make_sounds.py. Stdlib only (wave, math, random, struct).
Synthesize short placeholder sound effects as 44.1 kHz mono 16-bit WAV into assets/build/sounds/: move (40 ms wooden tick: noise burst plus a decaying 180 Hz sine), capture (heavier tick, ~70 ms), check (two quick rising tones), castle (two ticks 90 ms apart), game_end (three descending tones), click (15 ms UI tick). Apply a short fade-in and fade-out, normalise peak to 0.6, seed the RNG so output is deterministic. Print the file sizes. Add a --force flag; skip existing files otherwise.
DONE WHEN: six playable WAVs under 100 KB each are produced and the script is idempotent.
```

### tools/fetch\_stockfish.py

```text
FILE: tools/fetch_stockfish.py. Stdlib only (urllib, zipfile, tarfile, hashlib, subprocess, shutil).
CLI: --os {win,linux,mac} --url <archive url> [--sha256 <hex>] [--variant <label>]. Do NOT hardcode download URLs (they change per release); print that official builds are at stockfishchess.org/download and that x86-64-avx2 is the best default with x86-64-sse41-popcnt as a compatibility build.
Steps: download to a temp dir; verify sha256 if given; extract .zip or .tar; find the executable whose name starts with 'stockfish'; copy to bin/stockfish/<os>/ as stockfish (stockfish.exe on win) or stockfish-<variant> when --variant is given, so several builds can coexist; chmod +x on posix; copy any COPYING/LICENSE file as bin/stockfish/<os>/LICENSE.txt; run the binary, send 'uci', require 'uciok' within 5 s, parse the 'id name' line and write it to bin/stockfish/<os>/VERSION.txt.
DONE WHEN: running it with a real archive leaves a working executable, VERSION.txt and LICENSE.txt, and it fails clearly if the smoke test fails.
```

## 6. Prompts: project setup and core logic

No pygame anywhere in this section.

### requirements.txt, requirements-dev.txt, pyproject.toml, every `__init__.py`

```text
Create: requirements.txt (pygame>=2.5, chess>=1.10, platformdirs>=4); requirements-dev.txt (-r requirements.txt, pytest, Pillow, requests, pyinstaller); pyproject.toml (project name openboard, requires-python >=3.11, [tool.pytest.ini_options] testpaths=['tests'] pythonpath=['.']). The PyPI package that provides `import chess` is named 'chess' (python-chess). Also create empty __init__.py in openboard/, openboard/core, engines, storage, ui, ui/scenes, tests, tools, demos, and a .gitignore (venv, __pycache__, dist, build, logs, assets/build, bin/stockfish/*/stockfish*).
DONE WHEN: pip install -r requirements-dev.txt then pytest runs with 'no tests collected'.
```

### openboard/config.py

```text
FILE: openboard/config.py. Constants and small frozen dataclasses only. No I/O, no pygame.
- APP_NAME='OpenBoard', APP_VERSION='0.1.0', GITHUB_URL placeholder, STOCKFISH_SOURCE_URL='https://github.com/official-stockfish/Stockfish'.
- DESIGN_W=1600, DESIGN_H=900, MIN_WINDOW=(960,540), FPS_OPTIONS=(30,60,90,120), DEFAULT_FPS=60.
- BOARD_SQ=88, BOARD_ORIGIN=(120,136); EVAL_BOARD_SQ=72 and EVAL_BOARD_ORIGIN (measure from assets/reference/evaluate.png).
- TimeControl(key, label, minutes, increment_s): BLITZ ('blitz','BLITZ 3 + 2',3,2), RAPID ('rapid','RAPID 10 + 0',10,0); TIME_CONTROLS dict by key.
- LevelSpec(ui_level, caption, python_level|None, sf_elo|None, sf_movetime_s|None, sf_only:bool) and LEVELS for the 8 UI levels:
  1 -> python_level 1; 2 -> 2; 3 -> 3; 4 -> 4 (all Python only)
  5 -> python_level 5 AND sf_elo 1600, movetime 0.3 (Python if its time estimate fits, else Stockfish)
  6 -> Stockfish only, elo 1900, movetime 0.5
  7 -> Stockfish only, elo 2400, movetime 0.8
  8 -> Stockfish only, full strength (sf_elo None), movetime 1.0
  If Stockfish is missing or SMART ENGINE is off, levels 5-8 fall back to python_level 5.
- Router thresholds: PY_EVAL_MAX_DEPTH=4, PY_TIME_FIT_RATIO=0.6, PY_MIN_USEFUL_DEPTH=4, AUTO_EVAL_SF=(depth 14, time 2.0), AUTO_EVAL_PY=(depth 3, time 2.0), WATCHDOG_GRACE_S=3.0, MIN_ENGINE_MOVE_DELAY_S=0.4.
- Evaluate bounds: EVAL_DEPTH_RANGE=(1,40), EVAL_TIME_RANGE=(0.1,60.0), EVAL_DEFAULT_DEPTH=12.
- Evaluation word thresholds in pawns: EQUAL < 0.5, SLIGHT EDGE < 1.0, CLEAR ADVANTAGE < 3.0, otherwise WINNING.
- NAME_MAX=16, HISTORY_PAGE=50.
DONE WHEN: the module imports on a machine without pygame and a test asserts LEVELS has keys 1..8.
```

### openboard/paths.py

```text
FILE: openboard/paths.py. Dependency: platformdirs.
Functions: is_frozen() (sys.frozen); resource_path(rel) -> Path (sys._MEIPASS when frozen, otherwise the project root = parent of the openboard package); user_data_dir() -> Path using platformdirs.user_data_dir('OpenBoard', appauthor=False), created on demand; log_dir() -> user_data_dir()/logs; assets_dir() -> resource_path('assets/build'); reference_dir() -> resource_path('assets/reference'); stockfish_candidates() -> list[Path]: bin/stockfish/<win|linux|mac>/ files starting with 'stockfish', ordered best-first (for x86-64: names containing 'avx2' first, then the plain file, then 'sse41'/'popcnt'; on macOS arm64 prefer an 'apple-silicon' or 'm1' name). Pick the OS folder from sys.platform and platform.machine(). Return [] when the folder is empty; never raise.
DONE WHEN: pytest covers frozen vs normal mode (monkeypatch sys.frozen / sys._MEIPASS) and the candidate ordering with a temp folder.
```

### openboard/context.py

```text
FILE: openboard/context.py.
AppContext (dataclass, slots): settings: SettingsStore, profile: ProfileStore, history: HistoryStore, engines: EngineService, assets, display, scenes, clock. Import ui types only under TYPE_CHECKING so this file imports without pygame.
build_context(headless=False): create settings -> profile -> history -> engines (start asynchronously, do not block) -> unless headless: display, assets, scenes. ctx.shutdown() is idempotent: engines.shutdown(), settings.save(). ctx.sfx(name) plays a sound only when settings.audio is on and is a no-op otherwise or if the mixer failed.
DONE WHEN: build_context(headless=True) works in a pytest using a temp user-data dir (monkeypatch paths.user_data_dir) and shutdown() can be called twice.
```

### main.py

```text
FILE: main.py (project root).
First line of main(): multiprocessing.freeze_support(); then multiprocessing.set_start_method('spawn', force=True). Set up logging: rotating file handler (512 KB x 3) in paths.log_dir() plus console. Build the context, init pygame (display + mixer, tolerate mixer failure), register all scenes by name (main_menu, opponent_select, pass_play_setup, vs_engine_setup, game, evaluate, profile, about, settings, confirm), start at main_menu. Game loop: dt in seconds from clock.tick(settings.fps) (re-read the fps every frame so Settings changes apply live); translate mouse events into design coordinates via ctx.display; F11 fullscreen, F2 reference overlay; call ctx.engines.poll() once per frame on the main thread; draw to the virtual surface then ctx.display.present(). Wrap the loop in try/except: log the traceback to the log file and show a simple pygame error screen, then exit cleanly. Always call ctx.shutdown() and pygame.quit().
DONE WHEN: python main.py opens a letterboxed window showing the main menu and closes cleanly with no zombie Stockfish process.
```

### openboard/core/clock.py

```text
FILE: openboard/core/clock.py. Pure Python, no pygame, no threads.
class ChessClock(time_control, now=time.monotonic): per-colour remaining seconds (chess.Color); start(first_to_move); update() reads now() and subtracts elapsed time from the running side only; press(color) is called after a move: apply the increment to the side that moved, then switch the running side; pause()/resume(); remaining(color); flagged() -> Optional[chess.Color] (clamp remaining at 0.0). Inject the time source so tests can fake it.
format_clock(seconds) -> 'MM:SS' (e.g. '10:00'); under 20 seconds show tenths ('0:09.4'); never negative.
DONE WHEN: pytest covers increment, switching, pause/resume, flagging and the formatter edge cases using a fake time source.
```

### openboard/core/notation.py

```text
FILE: openboard/core/notation.py. Dependency: chess. No pygame.
Purpose: the Evaluate screen types FEN, SAN or LAN text; convert everything to a chess.Board plus a UCI move list.
- detect_input_type(text) -> 'fen'|'san'|'lan'|'unknown' (a FEN has 5-6 space-separated fields and 7 slashes; LAN has hyphens or an explicit from-to like Ng1-f3 or e2-e4; otherwise SAN).
- @dataclass ParsedPosition(start_fen, board (final position), uci_moves: list[str], san_moves: list[str]).
- parse_position(text, kind='auto') -> ParsedPosition; raise NotationError(message, ply: int|None) with a human sentence such as 'Illegal move Nf6 at move 3 (ply 5)'.
- FEN: validate with chess.Board(fen) and board.status(); translate the status flags into readable errors (no king, too many pieces, opposite check, bad castling rights...).
- SAN lists: allow an optional first line 'FEN: <fen>' or '[FEN "..."]' as the start position. Strip move numbers (1. and 1...), result tokens (1-0 0-1 1/2-1/2 *), {comments}, (variations), ; line comments, NAGs ($1) and annotation marks (!?). Replay with board.parse_san. Accept O-O / 0-0 castling.
- LAN: accept e2-e4, e2e4, Ng1-f3, Nf3, exd5, e2xd5, O-O, e7-e8=Q, e7e8q. Normalise to UCI by trying board.parse_uci after stripping piece letters, 'x', '-', '+', '#', '='; fall back to parse_san.
- san_line(start_fen, uci_moves, max_moves=8) -> str such as '1. e4 e5 2. Nf3 Nc6' (starts with '1...' when Black is to move).
DONE WHEN: pytest has 30+ cases including bad FENs, comments, castling spellings, promotions and illegal moves with the correct ply reported.
```

### openboard/core/results.py

```text
FILE: openboard/core/results.py. Dependency: chess, chess.pgn.
- Reason enum: CHECKMATE, RESIGNATION, TIMEOUT, STALEMATE, DRAW_AGREED, INSUFFICIENT, FIFTY_MOVE, REPETITION, ABANDONED.
- @dataclass(frozen=True) GameOutcome(winner: chess.Color|None, reason: Reason) with .result_string ('1-0','0-1','1/2-1/2') and .headline ('WHITE WINS - CHECKMATE', 'DRAW - STALEMATE'...).
- outcome_from_board(board) -> GameOutcome|None (claim fifty-move and threefold automatically; five-fold/75-move are subsumed).
- build_pgn(white, black, outcome, san_moves or board.move_stack, start_fen=None, time_control_label, date) -> str using chess.pgn.Game headers (Event 'OpenBoard Game', Site 'OpenBoard', Date, White, Black, Result, TimeControl, Termination).
- describe_eval(score_cp, mate_in) -> tuple[str, str]: ('+0.20','EQUAL'), ('-1.35','CLEAR ADVANTAGE'), ('#3','MATE IN 3'). Score is from White's point of view; thresholds come from config. None score -> ('--','NO EVALUATION').
DONE WHEN: pytest covers each reason, PGN round-trips through chess.pgn.read_game, and eval formatting at the threshold boundaries.
```

### openboard/core/session.py

```text
FILE: openboard/core/session.py. No pygame, no threads, no engine calls.
- @dataclass PlayerInfo(name, kind: 'human'|'engine', engine_level: int|None).
- class GameSession(white: PlayerInfo, black: PlayerInfo, time_control, start_fen=None, now=time.monotonic): owns chess.Board, ChessClock, move records (uci, san, seconds_spent), last_move, outcome, draw_offer state.
- Methods: legal_targets(square) -> list[int]; needs_promotion(from_sq,to_sq) -> bool; try_move(from_sq,to_sq,promotion=None) -> MoveResult(ok, move, san, events, error); apply_uci(uci) for engine moves (same path as try_move); resign(color); offer_draw(by)/accept_draw()/decline_draw(); update() -> checks the flag and ends the game on timeout (a flagged side loses unless the opponent has insufficient mating material, then it is a draw).
- Properties: turn, is_over, outcome, move_rows() -> list[(number, white_san, black_san|None)] for the MOVES panel, check_square -> int|None, fen, san_moves, status_text ('WHITE TO MOVE', 'BLACK IN CHECK', or the outcome headline).
- Events (enum SessionEvent: MOVE, CAPTURE, CHECK, CASTLE, PROMOTION, GAME_OVER): collected per move and returned through drain_events() so the UI can play sounds without the session knowing about audio.
- to_record(player1_color) -> dict ready for HistoryStore (mode, opponent, level, time control, result from Player 1's view, reason, move count, pgn).
DONE WHEN: pytest plays scholar's mate, a stalemate, a timeout with a fake clock, a promotion and a resignation; the clock starts only after White's first move is not required (clock starts at game start).
```

## 7. Prompts: engines and automatic switching

The core idea: both engines hide behind one interface and one result type. A pure function (`router.py`) decides which backend answers each request, and a service object keeps the UI thread free.

### openboard/engines/engine.py (your attached file)

```text
FILE: openboard/engines/engine.py. Start from the attached engine.py. Do NOT change search, evaluation, move ordering or the TT.
Changes only:
1. Remove DEFAULT_LOG_PATH (it assumes the file sits two folders below the project root). setup_file_logging() must accept an explicit path, and Engine(log_to_file=...) must default to False. The app configures logging in main.py.
2. Add Engine.set_use_book(flag: bool).
3. After each search store a principal variation in self.info['pv'] (list of UCI strings, up to 8 plies) by walking the transposition table's stored best moves from the root, verifying each move is legal; an empty list is acceptable when nothing is stored.
4. Add LEVEL_COUNT = len(LEVELS).
Add tests/test_engine.py: finds mate in one, returns a legal move at every level, honours a pre-set stop_event within 200 ms after depth 1 completes, never mutates the board passed in, returns (None, score, 0) on a finished game.
DONE WHEN: all of those pass and the diff against the original touches only the items above.
```

### openboard/engines/types.py

```text
FILE: openboard/engines/types.py. Dataclasses (slots, frozen) only.
- Backend = Literal['python','stockfish']; Purpose = Literal['play','evaluate'].
- SearchRequest(request_id: int, fen: str, purpose, depth: int|None, time_s: float|None, level: int|None, auto: bool=False, limit_strength: bool=True).
- SearchResult(request_id, best_uci: str|None, score_cp: int|None (White's point of view), mate_in: int|None (positive = White mates), depth: int, nodes: int, seconds: float, pv_uci: tuple[str,...], backend: Backend, reason: str, book: bool=False, cancelled: bool=False, error: str|None=None).
- PythonCalibration(seconds_by_depth: dict[int,float], growth: float, nps: float) and Capabilities(stockfish_available, stockfish_name, elo_range: tuple[int,int]|None, calibration: PythonCalibration|None, smart_engine: bool, use_book: bool, cpu_count: int).
- Helpers: pawns_to_cp(x) -> int; decode_python_score(score_pawns) -> (score_cp|None, mate_in|None) using MATE_SCORE=10000 and MATE_THRESHOLD=9000 from engine.py (mate in N moves = (MATE_SCORE - abs(score) + 1) // 2, positive for White).
DONE WHEN: pytest checks decode_python_score for +/- mates, normal scores and rounding.
```

### openboard/engines/base.py

```text
FILE: openboard/engines/base.py.
abstract class EngineBackend: name: Backend; available: bool; start() -> None; stop() -> None; new_game() -> None; search(request, cancel: threading.Event) -> SearchResult (blocking; the service calls it from a worker); configure(**options). class EngineError(Exception) with .recoverable flag.
No logic beyond the interface and docstrings explaining the contract: search must return within request.time_s plus 1 s, must honour cancel, must never raise for a legal position (wrap internal failures in EngineError), and must fill backend and reason fields.
DONE WHEN: a FakeBackend in tests subclasses it and the interface is documented.
```

### openboard/engines/benchmark.py

```text
FILE: openboard/engines/benchmark.py.
calibrate(make_engine, budget_s=1.5) -> PythonCalibration: on two fixed positions (start position and a middlegame FEN), time depth 1, 2, 3 (stop early when the budget is used), record seconds per depth and nodes/second; growth = geometric mean of t(d+1)/t(d), clamped 2.0-12.0. estimate_seconds(depth, calib) = t_last * growth ** (depth - last_depth); max_depth_within(seconds, calib) -> int. Pure and deterministic given the calibration. Runs in the worker process, never the UI thread; the service stores the result in settings so it only reruns when the app version or CPU count changes.
DONE WHEN: pytest with a hand-built calibration checks estimates and max_depth_within; a manual demo prints real numbers.
```

### openboard/engines/python\_backend.py

```text
FILE: openboard/engines/python_backend.py.
class PythonBackend(EngineBackend): runs engine.py in a SEPARATE PROCESS (multiprocessing, spawn) because pure-Python search holds the GIL and would freeze pygame if run in a thread. Use a Pipe for requests and results and a multiprocessing.Event for cancel. Module-level _worker_main(conn, cancel_event, use_book) creates one Engine and loops: receive a request dict, set level or depth/time, run best_move(chess.Board(fen), time_limit, stop_event=cancel_event), reply with a plain dict (converted to SearchResult in the parent). Handle 'play' by level: set_level(config.LEVELS[level].python_level). Handle 'evaluate' by setting engine.depth to the request depth (or the AUTO value) with the request time limit and use_book False. Level 1-3 randomness (the engine margin) must only apply to play, never to evaluate: for evaluate set margin to 0 through a public method you add to engine.py (set_margin).
search() sends the request, waits with poll(0.05) so cancel works, returns SearchResult(backend='python'). If the child dies, restart it once and raise EngineError(recoverable=True) for the failed request. new_game() clears the TT in the child. stop() terminates the child cleanly (join with timeout, then kill).
DONE WHEN: a pytest-run demo gets a legal move from the start position at level 1, a mate-in-1 at level 4, a cancel returns within 300 ms, and killing the child mid-search yields a recoverable EngineError followed by a working restart.
```

### openboard/engines/stockfish\_backend.py

```text
FILE: openboard/engines/stockfish_backend.py. Dependency: chess.engine.
class StockfishBackend(EngineBackend). start(): for each path in paths.stockfish_candidates() try chess.engine.SimpleEngine.popen_uci(path, timeout=10, creationflags=subprocess.CREATE_NO_WINDOW on win32); the first that answers 'uciok' wins (this gives an AVX2 -> older-CPU fallback). Read engine.options to detect UCI_LimitStrength, UCI_Elo range (clamp requested Elo into it), Threads, Hash. Configure Threads=min(4, max(1, cpu_count-1)), Hash=64. Expose available, name (the id string) and elo_range for Capabilities. If no candidate works: available=False, log once, never raise from start().
search(request, cancel): build the chess.Board from the FEN. For purpose='play' with a level: look up config.LEVELS; if sf_elo is set enable UCI_LimitStrength and UCI_Elo else disable it; limit = chess.engine.Limit(time=sf_movetime_s). For 'evaluate': UCI_LimitStrength False, Limit(depth=..., time=...). Use engine.analysis(board, limit, game=<token>) so cancel works: iterate infos, and when cancel.is_set() call analysis.stop(); the best move is analysis.wait().move (fall back to the last info['pv'][0]). Normalise: info['score'].white() -> cp via .score() and mate via .mate(); pv -> UCI strings; depth, nodes, time. new_game(): replace the game token so python-chess sends ucinewgame. Wrap chess.engine.EngineTerminatedError / EngineError: restart once, otherwise set available=False and raise EngineError(recoverable=True) so the router falls back. stop(): engine.quit() in try/except.
DONE WHEN: with a real Stockfish present, the demo returns a move and score at depth 12, a limited-Elo move for level 6, and a cancelled analysis within 300 ms; with the binary missing, available is False and nothing raises.
```

### openboard/engines/router.py

```text
FILE: openboard/engines/router.py. PURE: no I/O, no processes, no time calls. This is the heart of the automatic switching.
@dataclass(frozen=True) Decision(backend, request: SearchRequest, reason: str). choose_backend(req, caps) -> Decision, same input always gives the same output (no flip-flopping inside a game).
Rules, first match wins:
R0  Stockfish unavailable OR caps.smart_engine is False -> Python. Clamp so the search fits: if req.time_s is set, reduce depth to max_depth_within(time_s * PY_TIME_FIT_RATIO) (minimum 1). For play levels 5-8 use python_level 5. Reason names the cause ('stockfish missing', 'smart engine off').
R1  purpose 'play': spec = config.LEVELS[level]. spec.sf_only -> Stockfish. spec.python_level and not spec.sf_elo -> Python. Both set (level 5): Python if estimate_seconds(python depth) <= PY_TIME_FIT_RATIO * time budget, else Stockfish.
R2  purpose 'evaluate' with an explicit depth: depth > PY_EVAL_MAX_DEPTH -> Stockfish. Otherwise Python if there is no time limit or the estimate fits the ratio, else Stockfish.
R3  purpose 'evaluate' with only a time limit: if max_depth_within(time_s) < PY_MIN_USEFUL_DEPTH (a quick answer is wanted, Python cannot go deep enough in that time) -> Stockfish, else Python.
R4  req.auto: Stockfish with AUTO_EVAL_SF, or Python with AUTO_EVAL_PY if Stockfish is missing.
The Decision's request carries the adjusted depth/time. reason is a short human sentence, for example 'depth 12 > 4 -> Stockfish' or 'level 3 -> built-in engine'; it is shown in the Evaluate caption and written to the log.
DONE WHEN: a table-driven pytest covers every rule, missing calibration (treat Python as slow: nps unknown -> Stockfish for anything above depth 2), smart_engine off, and determinism (call twice, equal results).
```

### openboard/engines/service.py

```text
FILE: openboard/engines/service.py. The only thing the UI talks to.
class EngineService(settings, backends=None): start() launches PythonBackend and StockfishBackend in background threads (UI must not wait), then runs calibration in the Python worker and stores it in settings. capabilities() -> Capabilities reflecting live settings (smart_engine, use_book) and availability.
submit(req_kwargs, on_done: Callable[[SearchResult], None]) -> int: assigns a request_id, runs router.choose_backend, queues the work on ONE worker thread per backend (a Python search and a Stockfish search never run on the same backend at once), 'latest wins' for evaluate: a new evaluate request cancels the previous one. Results go into a thread-safe queue; poll() (called once per frame by main.py on the main thread) drains it and runs the callbacks, so UI code is never touched from another thread. Stale results (request id no longer wanted) are dropped.
Resilience: if the chosen backend raises EngineError, retry once on the other backend with reason 'fallback: <why>'; a watchdog cancels any search that exceeds its budget plus WATCHDOG_GRACE_S and answers with a depth-1 Python move for play requests. cancel(request_id=None) cancels all. new_game() resets both backends. shutdown() is idempotent and kills child processes.
DONE WHEN: pytest with FakeBackends proves routing, fallback on failure, latest-wins cancellation, stale-result dropping and a clean shutdown with no leaked threads.
```

### demos/engine\_cli.py and demos/console\_game.py

```text
FILES: demos/engine_cli.py, demos/console_game.py (the only places print() is allowed besides tools).
engine_cli: python -m demos.engine_cli '<fen>' --depth N | --time S | --level L | --auto. Builds an EngineService, prints the router Decision (backend plus reason), the SearchResult (move in SAN, score, mate, depth, nodes, seconds, pv) and the capabilities. Add --compare to run the same request on both backends and print them side by side.
console_game: play in the terminal as White against the engine at --level 1..8 using SAN input, printing the board with chess.Board.unicode(), the clock, and which backend answered each move. Ends with the PGN.
DONE WHEN: you can watch the backend switch from python to stockfish as you raise --level from 4 to 6.
```

## 8. Prompts: storage

All three use stdlib json or sqlite3, write atomically, and survive corrupted files.

### openboard/storage/settings.py

```text
FILE: openboard/storage/settings.py.
@dataclass Settings: schema_version=1, audio=True, use_book=True, smart_engine=True, fps=60, fullscreen=False, window_size=(1280,720), last_time_control='rapid', python_calibration: dict|None, calibration_key: str|None (app version + cpu count).
SettingsStore(path): load() with validation and clamping (fps must be in config.FPS_OPTIONS; unknown keys ignored; missing keys defaulted); a corrupt file is renamed to settings.json.bak and defaults are used; save() writes to a temp file then os.replace (atomic); set(**changes) validates, saves, and notifies listeners; subscribe(callback) so the engine service reacts to smart_engine / use_book changes.
DONE WHEN: pytest covers corrupt JSON, partial files, clamping, atomic save and listener notification.
```

### openboard/storage/profile.py

```text
FILE: openboard/storage/profile.py.
@dataclass PlayerProfile: id (uuid4 hex), name='Player 1', preferred_time_control='rapid', created_at (ISO UTC). ProfileStore(path): load-or-create profile.json; rename(name) trims, collapses whitespace, enforces 1..config.NAME_MAX characters and rejects control characters, raising ValueError with a message the UI can show; set_time_control(key). Saves atomically.
DONE WHEN: pytest covers rename validation (empty, too long, whitespace, emoji allowed) and persistence across reloads.
```

### openboard/storage/history.py

```text
FILE: openboard/storage/history.py. Stdlib sqlite3.
Table matches(id INTEGER PK, started_at TEXT, mode TEXT ('pass_play'|'vs_engine'), opponent TEXT, engine_level INTEGER NULL, time_control TEXT, player_color TEXT, result TEXT ('won'|'lost'|'drawn' from Player 1's view), reason TEXT, moves INTEGER, pgn TEXT, backends TEXT NULL (e.g. 'python:23,stockfish:18'). Create with a schema-version table and a simple migration hook.
HistoryStore(path): add(record) -> id; stats() -> Stats(played, won, lost, drawn, by_mode); recent(limit=50, offset=0) -> list[MatchRecord]; get(id); clear(). A game abandoned through MENU is stored with result 'lost', reason 'abandoned'. Open one connection per call or use check_same_thread=False with a lock; never write from the UI frame loop except on game end.
DONE WHEN: pytest with a temp db covers add/stats/recent ordering and pagination, empty database stats (all zeros) and clear().
```

## 9. Prompts: UI framework and scenes

pygame is allowed only in this section. For every scene prompt, tell the assistant to open the named reference PNG in `assets/reference/`, measure every rectangle from it, and keep those rectangles as named constants at the top of the file so you can nudge them.

### openboard/ui/display.py

```text
FILE: openboard/ui/display.py.
class DisplayManager(settings): creates the window (RESIZABLE, min size config.MIN_WINDOW, caption APP_NAME, icon from the app_icon asset) and owns `surface`, a 1600x900 pygame.Surface that every scene draws on.
present(): scale = min(win_w/1600, win_h/900); dest size = round(1600*scale), round(900*scale); centre it; fill the bars with the INK colour; if scale == 1.0 blit directly, else smoothscale into a cached destination surface (reuse it until the window size changes) and blit; then pygame.display.flip().
window_to_design(pos) -> (float, float). translate_event(event) -> event copy with pos converted for MOUSEMOTION / MOUSEBUTTONDOWN / MOUSEBUTTONUP (rel scaled too), or None for clicks that land in the letterbox bars. toggle_fullscreen() (F11); remember window size in settings, debounced. set_hand_cursor(bool).
Debug: toggle_reference(scene_name) overlays assets/reference/<scene>.png at 50% alpha inside present() (F2) so you can align widgets with the mockup.
DONE WHEN: python -m openboard.ui.display opens a window with a bordered 1600x900 grid; resizing to odd aspect ratios shows even bars; clicking prints design coordinates accurate to 1 px at three different window sizes.
```

### openboard/ui/theme.py

```text
FILE: openboard/ui/theme.py.
Colour constants (BG, CARD, INK, PURPLE, ACCENT, TINT, CARD_BORDER, DANGER for check highlight and invalid input, DIM = INK at 45% alpha). Layout constants: BORDER=3, SHADOW=6 (measure from the mockups). Font roles loaded from assets/build/fonts (Inter static TTFs): wordmark (ExtraBold ~110), title (Bold 30), heading (Bold 24), label (Bold 18, uppercase use), body (Regular 18), small (Regular 14), number (Bold 56), clock (Bold 64), mono (for FEN input; fall back to a system monospace). font(role) is cached. If Inter is missing, fall back to pygame.font.SysFont with a single logged warning.
Helpers: draw_panel(surf, rect, fill=CARD, border=BORDER, shadow=SHADOW, shadow_color=INK); draw_text(surf, text, role, color, pos, anchor='topleft'); fit_text(text, role, max_w) -> ellipsised string; wrap_text(text, role, max_w) -> list[str]; lerp_color; ease_out_cubic(t).
DONE WHEN: python -m openboard.ui.theme shows a style sheet window listing every colour, font role and a sample panel so you can compare it with Figma side by side.
```

### openboard/ui/assets.py

```text
FILE: openboard/ui/assets.py.
class AssetStore: reads assets/build/index.json. image(name) -> Surface (convert_alpha, cached); piece(color: chess.Color, piece_type: int, size: int) -> Surface from build/pieces/<size>/ with smoothscale fallback for other sizes (cached); background(name) -> Surface converted without alpha; sound(name) -> a pygame Sound or a silent stub when the mixer is unavailable or audio is off; tile(name) helper. preload(on_progress=None) loads everything used by scenes. A missing file must never crash: return a magenta placeholder of a sensible size and log once. Font loading stays in theme.py.
DONE WHEN: python -m openboard.ui.assets lists every asset with size and load time and reports missing ones; deleting a file only produces a placeholder and a log line.
```

### openboard/ui/widgets.py

```text
FILE: openboard/ui/widgets.py. Draw everything in code with theme helpers; match the mockups.
Base Widget(rect): visible, enabled, hovered, pressed, focused; handle_event(event) -> bool (True if consumed); update(dt); draw(surf).
- Button(label, on_click, style='primary'|'secondary'|'ghost'): flat fill, ink border, hard shadow; hover lifts (shadow shrinks slightly, label stays), press sinks the button onto its shadow; disabled is greyed. Keyboard: Enter/Space when focused.
- Chips(options, selected, on_change, columns): single-select group for BLITZ/RAPID, FEN/SAN/LAN, DEPTH/AUTO/TIME, level 1-8, FPS. Selected chip is PURPLE-filled, others CARD.
- Toggle(on, on_change): ON/OFF switch like the Settings mockup, with an ON/OFF text label.
- TextInput(text, max_len, placeholder, filter=None, on_change, on_submit): TEXTINPUT events, caret blink, Backspace/Delete/Home/End/Left/Right, Ctrl+A/C/V/X via pygame.scrap when available, click to place caret, invalid state draws a DANGER border.
- TextArea: like TextInput but multi-line with word wrap, vertical scroll and a mono font (used for FEN and move lists); paste of multi-line text works.
- Label, Panel(draw_panel wrapper), ScrollList(item_height, draw_item, items) with mouse wheel and a slim scrollbar (used by MOVES and MATCH HISTORY).
- FocusManager: Tab / Shift+Tab cycle through enabled widgets; a scene registers its widgets in order.
Provide a gallery demo: python -m openboard.ui.widgets.
DONE WHEN: every widget works with mouse and keyboard in the gallery, hover/press states match the mockups' look, and a disabled widget never fires its callback.
```

### openboard/ui/board\_view.py

```text
FILE: openboard/ui/board_view.py. Reference: assets/reference/game.png (88 px squares at (120,136)) and evaluate.png (smaller board).
class BoardView(origin, square, assets): draws the framed board (border plus shadow), light #F3E8FA / dark #A085BB squares, rank numbers on the left and file letters below, pieces from a chess.Board, orientation (white or black at the bottom). Overlays: last-move highlight (ACCENT at ~35% alpha), selected square, legal-move dots (and a ring on capture squares), check highlight on the king (DANGER tint).
Input (only when interactive): click-then-click and drag-and-drop with the dragged piece following the cursor above the others; right click cancels. It never mutates a game: handle_event returns a MoveIntent(from_sq, to_sq) or None, and the scene asks GameSession to validate. Promotion: when GameSession.needs_promotion is true the scene calls board_view.ask_promotion(color) which shows a four-piece popup panel over the board and returns the choice through a callback.
API: set_board(board), set_orientation(color), set_interactive(color|None|'both'), set_marks(last_move, check_square), animate_move(move, ms=150) (ease-out slide; captures fade), draw(surf), square_at(pos). Read-only mode for the Evaluate screen. Cache the board surface so only pieces and overlays are redrawn each frame.
DONE WHEN: a standalone demo lets you play both sides on a plain chess.Board with legal-move dots, drag, promotion popup and flipping, with no rule logic inside the view.
```

### openboard/ui/scene\_manager.py and openboard/ui/scenes/base.py

```text
FILES: openboard/ui/scenes/base.py and openboard/ui/scene_manager.py.
Scene base class: name, ctx, is_modal=False; on_enter(**params), on_exit(), on_resume(result=None), handle_event(event) -> None, update(dt), draw(surf).
SceneManager(ctx): register(name, factory); go(name, **params) replaces the whole stack; push(name, **params) adds a scene; pop(result=None) removes the top scene and calls the one beneath with on_resume(result). A modal scene (confirm, game-over) is drawn on top of the dimmed scene below it (DIM overlay) and receives all events; non-top scenes get no update. Optional 150 ms cross-fade on go(). Scenes never import each other; they navigate only by name. Provide quit_requested handling and a current_name property for the F2 reference overlay.
DONE WHEN: pytest with fake scenes proves go/push/pop order, result delivery on pop, and that only the top scene is updated.
```

### openboard/ui/scenes/confirm.py (modal)

```text
FILE: openboard/ui/scenes/confirm.py. Reference: assets/reference/confirm.png.
Modal params: title ('CONFIRM ACTION'), message, yes_label='YES', no_label='NO', single_button=False (info variant with one OK button), on_result(bool) callback. Draws a centred panel over the dimmed previous scene; NO is secondary, YES is primary. Keys: Esc or N = no, Enter or Y = yes; clicking outside the panel does nothing. Pops itself and delivers the result both through the callback and on_resume.
DONE WHEN: it can be pushed from any scene with custom text and always returns exactly one result.
```

### openboard/ui/scenes/main\_menu.py

```text
FILE: openboard/ui/scenes/main_menu.py. Reference: assets/reference/main_menu.png.
Background bg_main; wordmark: 'Open' in INK and 'Board' in the vivid purple, staggered on two lines; five stacked buttons PLAY, EVALUATE, PROFILE, ABOUT, QUIT (the focused one is purple-filled); gear icon button top right; the illus_iso_board illustration right of the menu with a gentle idle bob (about 4 px, 4 s sine, paused when the window is not focused).
Navigation: PLAY -> go('opponent_select'), EVALUATE -> go('evaluate'), PROFILE -> go('profile'), ABOUT -> go('about'), gear -> push('settings'), QUIT -> push('confirm') then quit on yes. Keyboard: Up/Down/Enter, Esc opens the quit confirmation.
DONE WHEN: F2 overlay on the reference shows the buttons within 2 px; every button navigates correctly and quitting asks first.
```

### openboard/ui/scenes/opponent\_select.py

```text
FILE: openboard/ui/scenes/opponent_select.py. Reference: assets/reference/opponent.png.
Title PLAY with a BACK button. Draw the large purple diagonal panel as a polygon in code. Two tilted cards (card_pass_play about -6 degrees, card_vs_engine about +3 degrees, take the angles from the mockup) drawn with rotozoom-free pre-rotated images; on hover a card lifts, straightens slightly and its shadow grows, with a 120 ms ease. Click or Enter on the focused card -> go('pass_play_setup') or go('vs_engine_setup'). Left/Right arrows move focus, Esc/BACK -> go('main_menu').
DONE WHEN: hover animation is smooth at 30 and 120 fps (time-based, not frame-based) and hit-testing follows the rotated card shape, not its bounding box.
```

### openboard/ui/scenes/pass\_play\_setup.py

```text
FILE: openboard/ui/scenes/pass_play_setup.py. Reference: assets/reference/pass_play.png.
Panel PLAYERS: label PLAYER 2 plus a TextInput (default 'Player 2', 1-16 characters, trimmed; empty disables START GAME and shows the DANGER border); helper text 'Player 1 from profile · Colors assigned randomly' using the profile name; TIME Chips (BLITZ 3 + 2 / RAPID 10 + 0) preselected from profile.preferred_time_control; START GAME primary button; BACK -> go('opponent_select'). Enter starts the game. START: choose colours with random.choice, persist the time-control choice, then go('game', mode='pass_play', white=PlayerInfo, black=PlayerInfo, time_control=TimeControl). ⚠ If both names are equal, append ' (2)' to Player 2.
DONE WHEN: validation works with keyboard only and the game scene receives well-formed params.
```

### openboard/ui/scenes/vs\_engine\_setup.py

```text
FILE: openboard/ui/scenes/vs_engine_setup.py. Reference: assets/reference/vs_engine.png.
Panel ENGINE LEVEL with eight numbered Chips (default 4) and the captions BEGINNER (left) and EXPERT (right); TIME Chips; START GAME; BACK. START: random colours for the human, then go('game', mode='vs_engine', white=..., black=..., time_control=..., level=N). The scene never mentions which engine answers; that is the router's job. Left/Right arrows change the level.
DONE WHEN: all 8 levels are selectable by mouse and keyboard and the selected level reaches the game scene intact.
```

### openboard/ui/scenes/game.py

```text
FILE: openboard/ui/scenes/game.py. Reference: assets/reference/game.png. The biggest scene; keep rule logic in GameSession and engine logic in EngineService.
Layout: title (PASS & PLAY or VS ENGINE) top left; mode label (e.g. RAPID · 10 + 0) and MENU button top right; BoardView at the measured origin; two player cards with name, colour and clock (format_clock); the card of the side to move uses the inverted INK style; status line (WHITE TO MOVE / CHECK / result); MOVES ScrollList (numbered rows, auto-scroll to the latest); DRAW and RESIGN buttons.
Behaviour: build a GameSession from the params. Human moves: BoardView intent -> session.try_move (promotion popup when needed). Engine moves: when the side to move is an engine, submit a SearchRequest(purpose='play', level=...) through ctx.engines and apply the result with session.apply_uci, but never sooner than config.MIN_ENGINE_MOVE_DELAY_S after the request and never while the window is minimised; show 'ENGINE THINKING' with animated dots in the status line. Ignore results whose request id is stale. Each frame: session.update(), drain_events() -> sounds (move, capture, check, castle, game_end through ctx.sfx), animate moves.
Board orientation: vs engine = human at the bottom. ⚠ Pass & Play keeps White at the bottom (no auto flip).
RESIGN -> confirm modal -> session.resign. DRAW: pass & play -> confirm modal addressed to the other player; vs engine -> the engine accepts only after move 30 when its latest score for itself is <= +0.20, otherwise a short 'DRAW DECLINED' message. MENU -> confirm modal; yes = abandon (stored as a loss with reason 'abandoned') then go('main_menu').
Game over: when session.is_over, stop the clocks, save a record to ctx.history, show a modal result panel (headline plus the reason) with two buttons: EVALUATE (go('evaluate', moves=session.san_moves, start_fen=...)) and MENU. Call ctx.engines.cancel() on exit.
DONE WHEN: you can finish a full game of each mode, including a timeout, a resignation, a promotion and a checkmate, with the correct sound and history entry each time, and no engine request outlives the scene.
```

### openboard/ui/scenes/evaluate.py

```text
FILE: openboard/ui/scenes/evaluate.py. Reference: assets/reference/evaluate.png.
Left: read-only BoardView at the Evaluate size showing the parsed position. Right panel: Chips FEN / SAN / LAN (default FEN, auto-switch when detect_input_type is confident and the user has not clicked a chip); TextArea (mono, prefilled with the starting FEN); SEARCH LIMIT Chips DEPTH / AUTO / TIME with a number field (suffix 'plies' for depth, 's' for time; hidden for AUTO; clamped to config ranges); EVALUATE button (becomes CANCEL while running); result block: big score ('+0.20' from White's point of view, mate as '#3'), the word (EQUAL ...), a caption '<engine name> · depth N · 0.8 s' and the router reason in small text, and the move line from notation.san_line. MENU top right -> go('main_menu').
Live parsing: after 300 ms of idle typing run notation.parse_position; success updates the board, failure shows the NotationError message under the text area with a DANGER border and disables EVALUATE. EVALUATE builds a SearchRequest(purpose='evaluate') from the board FEN plus the limit and calls ctx.engines.submit; ignore stale results by request id; show a small spinner while waiting. The engine name shown is 'OpenBoard engine' for python and the Stockfish id string for stockfish. Accept optional params moves/start_fen to prefill from a finished game.
DONE WHEN: all three input types work, an invalid input never reaches the engine, depth 3 shows the built-in engine, depth 15 shows Stockfish, and pressing CANCEL returns the UI to idle within 300 ms.
```

### openboard/ui/scenes/profile.py

```text
FILE: openboard/ui/scenes/profile.py. Reference: assets/reference/profile.png and the profile backdrop asset.
Three columns inside one panel. STATS: PLAYED / WON (accent colour) / LOST / DRAWN big numbers from ctx.history.stats(). Centre: player_crest image, the name with a pencil icon button that switches the name into an inline TextInput (Enter saves via profile.rename and shows the ValueError message on failure, Esc cancels), and the preferred time control label that cycles BLITZ / RAPID on click. MATCH HISTORY: ScrollList of rows (opponent or 'Engine · Level N', 'Rapid · 32 moves', result WON / LOST / DRAWN right aligned); clicking a row -> go('evaluate', moves=..., start_fen=...) using the stored PGN; empty state text 'No games yet'. BACK -> go('main_menu'). Remove the 'Example data' caption.
DONE WHEN: with an empty database it shows zeros and the empty state; after playing two games the counts and rows update.
```

### openboard/ui/scenes/about.py

```text
FILE: openboard/ui/scenes/about.py. Reference: assets/reference/about.png.
Panel with the emblem, 'OPENBOARD' and 'PYGAME CHESS', a CONTROLS list (MOVE: click or drag a piece, PLAY: Blitz 3 + 2 / Rapid 10 + 0, EVALUATE: SAN / FEN / LAN), version from config, and a scrollable CREDITS area: pygame, python-chess, platformdirs, Pillow (tools), Inter (SIL OFL) and Stockfish with the text 'Stockfish is free software under the GNU GPLv3. Source code: <STOCKFISH_SOURCE_URL>', plus the installed Stockfish id string from ctx.engines.capabilities(). A GitHub link line opens config.GITHUB_URL with webbrowser.open. Background bg_about. BACK -> go('main_menu').
DONE WHEN: the credits include every bundled third-party component and the links open in the default browser.
```

### openboard/ui/scenes/settings.py

```text
FILE: openboard/ui/scenes/settings.py (modal-style scene pushed from the main menu). Reference: assets/reference/settings.png.
Toggles AUDIO, USE BOOK, SMART ENGINE, each with one small helper line beneath (SMART ENGINE: 'Switch between the built-in engine and Stockfish automatically'); FRAME RATE Chips 30 / 60 / 90 / 120; DONE primary button. Changes apply and save immediately through settings.set(). If Stockfish is unavailable, SMART ENGINE is disabled, shown OFF, and a small line says 'Stockfish not found - built-in engine only'. Esc or DONE -> pop().
DONE WHEN: toggling USE BOOK changes the next engine search, the FPS change is visible at once, and settings persist across restarts.
```

## 10. Build order and integration

| Phase | Build | Done when |
| --- | --- | --- |
| 0 | Setup files, config, paths, tools, assets pipeline | `build_assets.py check` exits 0, pytest runs |
| 1 | core: clock, notation, results, session | console game works end to end with pytest green |
| 2 | engines: engine.py patch, types, benchmark, both backends | `engine_cli --compare` prints two results for one FEN |
| 3 | router + service | table-driven router tests pass; fallback and cancel tests pass |
| 4 | storage: settings, profile, history | persistence tests pass |
| 5 | ui framework: display, theme, assets, widgets, board\_view, scene manager | each module's demo runs; letterbox clicks are accurate |
| 6 | scenes in this order: confirm, main\_menu, opponent\_select, pass\_play\_setup, game (pass & play), vs\_engine\_setup, game (vs engine), evaluate, profile, about, settings | F2 overlay matches each mockup within 2 px |
| 7 | context.py, main.py wiring | the app runs start to finish from a clean data folder |
| 8 | packaging (below) | the built folder runs on a machine without Python |

Build the **game scene against a pass-and-play stub first**; it exercises the board, clocks, move list and history together, and every other scene is simpler.

### tools/build\_exe.py and licenses

```text
FILES: tools/build_exe.py, openboard.spec (generated or checked in), THIRD_PARTY_LICENSES.md.
build_exe.py runs PyInstaller in --onedir mode (⚠ not --onefile: Stockfish is started as a subprocess and must be a real executable on disk, and onefile re-extracts on every launch and triggers antivirus warnings). Windowed app, icon from assets/build/icons, main.py as the entry point, data files: assets/build, bin/stockfish/<current os>, THIRD_PARTY_LICENSES.md. Hidden imports: chess, chess.engine, chess.polyglot, platformdirs. Verify multiprocessing.freeze_support() is called first in main.py.
Post-build smoke test: run the built Stockfish with 'uci' and require 'uciok'; run the built app headless flag --selftest (add it to main.py: build the context, run one Python-engine search and one Stockfish search, print JSON, exit) and fail the build if either backend does not answer. Zip the dist folder as OpenBoard-<version>-<os>.zip.
THIRD_PARTY_LICENSES.md: python-chess (GPL-3.0+), pygame (LGPL-2.1), platformdirs (MIT), Stockfish (GPL-3.0, with a link to the exact source release that matches the bundled binary), Inter (SIL OFL 1.1). ⚠ python-chess and Stockfish are GPL, so distributing the combined app means offering the corresponding source under a GPL-compatible licence; the project's own licence should be chosen with that in mind.
DONE WHEN: the zip runs on a clean Windows or Linux machine with no Python installed and both engines answer in --selftest.
```

### Final integration checklist

1. The window letterboxes correctly at 16:9, 4:3 and ultra-wide, and clicks land on the right square at every size.
2. Pass & Play: a full game with both clocks, a promotion, a resignation and a draw offer all end with the right history entry.
3. VS Engine levels 1–4 answer with the built-in engine; level 6 and above use Stockfish (check the log for the router reasons).
4. With Stockfish removed from the folder, the app still plays every level and Settings shows the notice.
5. Evaluate: depth 3 uses the built-in engine, depth 15 uses Stockfish, TIME 0.2 s uses Stockfish, CANCEL always returns in under 300 ms.
6. Killing the Stockfish process mid-game never freezes the UI; the next move comes from the fallback.
7. Quitting leaves no orphan Stockfish or Python-engine processes.
8. Settings persist; a corrupted settings.json is replaced and the old one kept as .bak.
9. The F2 overlay shows every scene within 2 px of its mockup.
10. The built zip passes `--selftest` on a clean machine and About lists every bundled licence.
