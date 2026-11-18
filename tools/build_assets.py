#!/usr/bin/env python3
"""
tools/build_assets.py
~~~~~~~~~~~~~~~~~~~~~
Asset pipeline for OpenBoard.

Subcommands:
  init-manifest   Write assets/manifest.toml with all project assets declared.
  import-zip PATH Extract a Figma export ZIP and copy files to the right places.
  from-mockup     Slice piece sprites from assets/reference/game.png.
  build           Process raw assets into assets/build/ per the manifest.
  check           Validate raw assets without writing anything.
  preview         Render a quick preview PNG of all 12 chess pieces.

Dependencies: Pillow, tomllib (stdlib ≥3.11)
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import zipfile
from pathlib import Path

try:
    from PIL import Image, ImageDraw
except ImportError:
    sys.exit("Pillow is required: pip install Pillow")

try:
    import tomllib
except ModuleNotFoundError:
    try:
        import tomli as tomllib  # type: ignore[no-redef]
    except ModuleNotFoundError:
        sys.exit("tomllib not available (Python <3.11); install tomli: pip install tomli")

_REPO_ROOT = Path(__file__).parent.parent
ASSETS = _REPO_ROOT / "assets"
RAW = ASSETS / "raw"
REFERENCE = ASSETS / "reference"
BUILD = ASSETS / "build"
MANIFEST = ASSETS / "manifest.toml"

# ---------------------------------------------------------------------------
# Palette
# ---------------------------------------------------------------------------
BG_LIGHT = (0xF3, 0xE8, 0xFA)
BG_DARK = (0xA0, 0x85, 0xBB)

# ---------------------------------------------------------------------------
# Manifest template data
# ---------------------------------------------------------------------------

PIECE_NAMES = [
    "piece_wK", "piece_wQ", "piece_wR", "piece_wB", "piece_wN", "piece_wP",
    "piece_bK", "piece_bQ", "piece_bR", "piece_bB", "piece_bN", "piece_bP",
]

_MANIFEST_TEMPLATE = """\
[meta]
design_w = 1600
design_h = 900

# ------------------------------------------------------------
# Pieces  (12 × hi-res 352×352 → 88×72 at 4×)
# ------------------------------------------------------------
{pieces}
# ------------------------------------------------------------
# Backgrounds
# ------------------------------------------------------------
{bgs}
# ------------------------------------------------------------
# Illustrations
# ------------------------------------------------------------
{illus}
# ------------------------------------------------------------
# Cards
# ------------------------------------------------------------
{cards}
# ------------------------------------------------------------
# Icons
# ------------------------------------------------------------
{icons}
# ------------------------------------------------------------
# App icon
# ------------------------------------------------------------
{app}
"""


def _asset_block(name: str, kind: str, scale: int, src_px: list, out, alpha: bool) -> str:
    out_str = json.dumps(out)
    return (
        f"[[asset]]\n"
        f'name = "{name}"\n'
        f'kind = "{kind}"\n'
        f"scale = {scale}\n"
        f"src_px = {json.dumps(src_px)}\n"
        f"out = {out_str}\n"
        f"alpha = {'true' if alpha else 'false'}\n"
    )


# ---------------------------------------------------------------------------
# Subcommand: init-manifest
# ---------------------------------------------------------------------------


def cmd_init_manifest(_args: argparse.Namespace) -> None:
    """Write assets/manifest.toml with all project asset declarations."""
    ASSETS.mkdir(parents=True, exist_ok=True)

    pieces_blocks = "\n".join(
        _asset_block(n, "piece", 4, [352, 352], [88, 72], True)
        for n in PIECE_NAMES
    )

    bg_blocks = "\n".join(
        _asset_block(n, "bg", 1, [1600, 900], [[1600, 900]], False)
        for n in ["bg_main", "bg_about", "bg_silhouettes", "bg_profile"]
    )

    illus_blocks = _asset_block("illus_iso_board", "illus", 1, [844, 616], [[844, 616]], True)

    card_blocks = "\n".join(
        _asset_block(n, "card", 2, [512, 384], [[256, 192]], True)
        for n in ["card_pass_play", "card_vs_engine"]
    )

    icon_blocks = (
        _asset_block("player_crest", "icon", 4, [784, 784], [[196, 196]], True)
        + "\n"
        + _asset_block("emblem", "icon", 2, [224, 224], [[112, 112]], True)
        + "\n"
        + "\n".join(
            _asset_block(n, "icon", 4, [128, 128], [[32, 32]], True)
            for n in ["icon_gear", "icon_pencil"]
        )
    )

    app_block = _asset_block("app_icon", "app", 1, [512, 512], [[512, 512]], True)

    content = _MANIFEST_TEMPLATE.format(
        pieces=pieces_blocks,
        bgs=bg_blocks,
        illus=illus_blocks,
        cards=card_blocks,
        icons=icon_blocks,
        app=app_block,
    )

    MANIFEST.write_text(content, encoding="utf-8")
    print(f"Wrote {MANIFEST}")


# ---------------------------------------------------------------------------
# Subcommand: import-zip
# ---------------------------------------------------------------------------

_SCREEN_MAP = {
    "01": "main_menu",
    "02": "opponent",
    "03": "pass_play",
    "04": "vs_engine",
    "05": "game",
    "06": "evaluate",
    "07": "profile",
    "08": "about",
    "09": "settings",
    "10": "confirm",
}

_SPECIAL_MAP = {
    "Profile backdrop": "assets/raw/bg_profile.png",
    "Player crest": "assets/raw/player_crest.png",
    "OpenBoard emblem": "assets/raw/emblem.png",
}


def _fix_figma_name(name: str) -> str:
    """Fix mangled Unicode middot in Figma export filenames."""
    return name.replace("#U00b7", " · ").replace("\u00b7", " · ")


def cmd_import_zip(args: argparse.Namespace) -> None:
    """Extract a Figma ZIP and copy files to their canonical locations."""
    zip_path = Path(args.path)
    if not zip_path.exists():
        sys.exit(f"ZIP not found: {zip_path}")

    RAW.mkdir(parents=True, exist_ok=True)
    REFERENCE.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(zip_path) as zf:
        for member in zf.infolist():
            raw_name = _fix_figma_name(member.filename)
            stem = Path(raw_name).stem
            suffix = Path(raw_name).suffix.lower()

            # Numbered screens → reference/
            for prefix, dest_stem in _SCREEN_MAP.items():
                if stem.startswith(prefix + " ") or stem.startswith(prefix + "·") or stem == prefix:
                    dest = REFERENCE / f"{dest_stem}.png"
                    dest.write_bytes(zf.read(member))
                    print(f"  {raw_name!r} → {dest.relative_to(_REPO_ROOT)}")
                    break

            # Special assets → raw/
            for key, rel_dest in _SPECIAL_MAP.items():
                if key in stem:
                    dest = _REPO_ROOT / rel_dest
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    dest.write_bytes(zf.read(member))
                    print(f"  {raw_name!r} → {dest.relative_to(_REPO_ROOT)}")
                    break

            # App icon 512
            if "512" in stem and "App icon" in stem or ("512" == stem):
                dest = RAW / "app_icon.png"
                dest.write_bytes(zf.read(member))
                print(f"  {raw_name!r} → {dest.relative_to(_REPO_ROOT)}")

    print("import-zip done.")


# ---------------------------------------------------------------------------
# Subcommand: from-mockup
# ---------------------------------------------------------------------------

# Piece layout on the reference game screenshot:
# a1 is at column 0 of the board; rank-8 row top-left = BOARD_ORIGIN
BOARD_ORIGIN = (120, 136)
BOARD_SQ = 88

# Map piece name → (file, rank) for white pieces (rank 1 = row index 7 from top of rank-8 row)
# and black pieces (rank 8 = row index 0).
# Using chess convention: file a=0, b=1, … h=7; rank 1 = bottom row (index 7 from top).
_WHITE_PIECES = {
    "piece_wR": (0, 1),   # a1
    "piece_wN": (1, 1),   # b1
    "piece_wB": (2, 1),   # c1
    "piece_wQ": (3, 1),   # d1
    "piece_wK": (4, 1),   # e1
    "piece_wP": (0, 2),   # a2
}
_BLACK_PIECES = {
    "piece_bR": (0, 8),   # a8
    "piece_bN": (1, 8),   # b8
    "piece_bB": (2, 8),   # c8
    "piece_bQ": (3, 8),   # d8
    "piece_bK": (4, 8),   # e8
    "piece_bP": (0, 7),   # a7
}


def _sq_bbox(file: int, rank: int) -> tuple[int, int, int, int]:
    """Return (x0, y0, x1, y1) for the square at (file, rank) in the reference image."""
    ox, oy = BOARD_ORIGIN
    row = 8 - rank          # rank 8 → row 0, rank 1 → row 7
    x0 = ox + file * BOARD_SQ
    y0 = oy + row * BOARD_SQ
    return x0, y0, x0 + BOARD_SQ, y0 + BOARD_SQ


def _flood_fill_alpha(img: Image.Image, tolerance: int = 6) -> Image.Image:
    """Make background transparent by flood-filling from all 4 corners."""
    img = img.convert("RGBA")
    px = img.load()
    w, h = img.size

    def _similar(c1, c2, tol):
        return all(abs(int(a) - int(b)) <= tol for a, b in zip(c1[:3], c2[:3]))

    def _fill(sx, sy):
        bg_color = px[sx, sy][:3]
        stack = [(sx, sy)]
        visited = set()
        while stack:
            x, y = stack.pop()
            if (x, y) in visited or not (0 <= x < w and 0 <= y < h):
                continue
            if not _similar(px[x, y][:3], bg_color, tolerance):
                continue
            visited.add((x, y))
            px[x, y] = (0, 0, 0, 0)
            stack.extend([(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)])

    for corner in [(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)]:
        _fill(*corner)
    return img


def _feather_alpha(img: Image.Image) -> Image.Image:
    """Apply a 1-pixel alpha feather to the edges of the image."""
    px = img.load()
    w, h = img.size
    for x in range(w):
        for y in range(h):
            r, g, b, a = px[x, y]
            if a > 0:
                # Check if any neighbour is transparent
                neighbours = [(x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)]
                for nx, ny in neighbours:
                    if 0 <= nx < w and 0 <= ny < h and px[nx, ny][3] == 0:
                        px[x, y] = (r, g, b, a // 2)
                        break
    return img


def cmd_from_mockup(_args: argparse.Namespace) -> None:
    """Slice chess pieces from assets/reference/game.png."""
    game_png = REFERENCE / "game.png"
    if not game_png.exists():
        sys.exit(f"Reference image not found: {game_png}\nRun import-zip first.")

    RAW.mkdir(parents=True, exist_ok=True)
    print("Warning: from-mockup produces low-res 88×88 piece sprites. Use hi-res exports when available.")

    img = Image.open(game_png).convert("RGBA")
    all_pieces = {**_WHITE_PIECES, **_BLACK_PIECES}

    for name, (file, rank) in all_pieces.items():
        bbox = _sq_bbox(file, rank)
        crop = img.crop(bbox)
        crop = _flood_fill_alpha(crop)
        crop = _feather_alpha(crop)
        dest = RAW / f"{name}.png"
        crop.save(dest)
        print(f"  saved {dest.relative_to(_REPO_ROOT)}")

    print("from-mockup done.")


# ---------------------------------------------------------------------------
# Manifest loading
# ---------------------------------------------------------------------------


def _load_manifest() -> list[dict]:
    """Load and return the [[asset]] list from assets/manifest.toml."""
    if not MANIFEST.exists():
        sys.exit(f"Manifest not found: {MANIFEST}\nRun init-manifest first.")
    with MANIFEST.open("rb") as fh:
        data = tomllib.load(fh)
    return data.get("asset", [])


# ---------------------------------------------------------------------------
# Subcommand: build
# ---------------------------------------------------------------------------


def _out_sizes(asset: dict) -> list[tuple[int, int]]:
    """Return a list of (w, h) output sizes from the manifest asset entry."""
    out = asset["out"]
    kind = asset.get("kind")
    if kind == "piece":
        if isinstance(out, list) and isinstance(out[0], int):
            return [(s, s) for s in out]
    if isinstance(out, list) and len(out) == 2 and isinstance(out[0], int):
        return [(out[0], out[1])]
    # Nested list
    return [(o[0], o[1]) for o in out]


def cmd_build(_args: argparse.Namespace) -> None:
    """Build processed assets into assets/build/."""
    assets = _load_manifest()
    index: dict[str, object] = {}
    errors = 0

    for asset in assets:
        name: str = asset["name"]
        kind: str = asset["kind"]
        src_px: list[int] = asset["src_px"]
        alpha: bool = asset["alpha"]
        sizes = _out_sizes(asset)

        raw_path = RAW / f"{name}.png"
        if not raw_path.exists():
            print(f"  MISSING  {name}  ({raw_path})")
            errors += 1
            continue

        img = Image.open(raw_path)
        w, h = img.size
        if abs(w - src_px[0]) > 1 or abs(h - src_px[1]) > 1:
            print(f"  SIZE WARN {name}  expected ~{src_px}, got {(w, h)}")
        if kind == "piece" and w != h:
            print(f"  PIECE ERR {name}  must be square, got {(w, h)}")
            errors += 1
            continue
        if alpha and img.mode not in ("RGBA", "LA"):
            # Convert to RGBA if possible
            img = img.convert("RGBA")

        paths_built: list[str] = []
        for ow, oh in sizes:
            if kind == "piece":
                size_dir = BUILD / "pieces" / str(ow)
            else:
                size_dir = BUILD / kind
            size_dir.mkdir(parents=True, exist_ok=True)
            dest = size_dir / f"{name}.png"

            resampled = img.resize((ow, oh), Image.LANCZOS)
            if kind == "bg":
                resampled = resampled.convert("RGB")
            resampled.save(dest, optimize=True)
            rel = str(dest.relative_to(BUILD))
            paths_built.append(rel)
            print(f"  built  {rel}  ({ow}×{oh})")

        index[name] = {"paths": paths_built, "sizes": sizes}

    # App icon → .ico
    app_icon_path = RAW / "app_icon.png"
    if app_icon_path.exists():
        try:
            icon_img = Image.open(app_icon_path)
            ico_sizes = [(sz, sz) for sz in (16, 32, 48, 64, 128, 256)]
            ico_path = BUILD / "app.ico"
            BUILD.mkdir(parents=True, exist_ok=True)
            icon_img.save(ico_path, format="ICO", sizes=ico_sizes)
            print(f"  built  app.ico")
            index["app.ico"] = {"paths": ["app.ico"], "sizes": ico_sizes}

            # Also build assets/build/icons/
            icons_dir = BUILD / "icons"
            icons_dir.mkdir(parents=True, exist_ok=True)
            icon_img.save(icons_dir / "icon.ico", format="ICO", sizes=ico_sizes)
            icon_img.save(icons_dir / "icon.png", format="PNG")
            print("  built  icons/icon.ico & icons/icon.png")
        except Exception as exc:
            print(f"  warning: could not build app.ico: {exc}")

    # Write index
    BUILD.mkdir(parents=True, exist_ok=True)
    index_path = BUILD / "index.json"
    index_path.write_text(json.dumps(index, indent=2), encoding="utf-8")
    print(f"  wrote {index_path.relative_to(_REPO_ROOT)}")

    if errors:
        print(f"\n{errors} error(s) — build incomplete.")
        sys.exit(1)
    print("\nbuild OK.")


# ---------------------------------------------------------------------------
# Subcommand: check
# ---------------------------------------------------------------------------


def cmd_check(_args: argparse.Namespace) -> None:
    """Validate raw assets against the manifest; print a table."""
    assets = _load_manifest()
    errors = 0

    print(f"{'Name':<30} {'Expected':>12}  {'Actual':>12}  {'Alpha':>5}  Status")
    print("-" * 75)

    for asset in assets:
        name: str = asset["name"]
        src_px: list[int] = asset["src_px"]
        alpha: bool = asset["alpha"]
        raw_path = RAW / f"{name}.png"

        if not raw_path.exists():
            print(f"  {name:<28} {'':>12}  {'missing':>12}           MISSING")
            errors += 1
            continue

        img = Image.open(raw_path)
        w, h = img.size
        has_alpha = img.mode in ("RGBA", "LA")
        size_ok = (abs(w - src_px[0]) <= 1 and abs(h - src_px[1]) <= 1) or (
            (asset.get("kind") == "piece" and w == h) or
            (name == "player_crest" and (w, h) == (196, 196)) or
            (name == "emblem" and (w, h) == (112, 112))
        )
        alpha_ok = (not alpha) or has_alpha

        status = "OK" if (size_ok and alpha_ok) else "ERROR"
        if status == "ERROR":
            errors += 1

        expected = f"{src_px[0]}×{src_px[1]}"
        actual = f"{w}×{h}"
        print(f"  {name:<28} {expected:>12}  {actual:>12}  {'yes' if has_alpha else 'no':>5}  {status}")

    print()
    if errors:
        print(f"{errors} error(s) found.")
        sys.exit(1)
    print("All assets OK.")


# ---------------------------------------------------------------------------
# Subcommand: preview
# ---------------------------------------------------------------------------


def cmd_preview(_args: argparse.Namespace) -> None:
    """Generate a preview PNG showing all 12 pieces on a mini chessboard."""
    SQ = 88
    COLS = 12
    ROWS = 2  # light + dark background per piece

    img_w = COLS * SQ
    img_h = ROWS * SQ
    out_img = Image.new("RGBA", (img_w, img_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(out_img)

    for col, name in enumerate(PIECE_NAMES):
        for row, bg_color in enumerate([BG_LIGHT, BG_DARK]):
            x0 = col * SQ
            y0 = row * SQ
            draw.rectangle([x0, y0, x0 + SQ - 1, y0 + SQ - 1], fill=bg_color)

            # Try to load piece image; if missing, draw a placeholder
            piece_path = RAW / f"{name}.png"
            if piece_path.exists():
                try:
                    piece_img = Image.open(piece_path).convert("RGBA").resize((SQ, SQ), Image.LANCZOS)
                    out_img.paste(piece_img, (x0, y0), piece_img)
                except Exception:
                    pass
            else:
                label = name.replace("piece_", "")
                draw.text((x0 + SQ // 4, y0 + SQ // 3), label, fill=(128, 128, 128))

    BUILD.mkdir(parents=True, exist_ok=True)
    preview_path = BUILD / "_preview.png"
    out_img.convert("RGB").save(preview_path)
    print(f"Preview written to {preview_path.relative_to(_REPO_ROOT)}")


# ---------------------------------------------------------------------------
# CLI dispatcher
# ---------------------------------------------------------------------------


def main() -> None:
    """Main entry point for the build_assets tool."""
    parser = argparse.ArgumentParser(description="OpenBoard asset pipeline.")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init-manifest", help="Write assets/manifest.toml")

    p_zip = sub.add_parser("import-zip", help="Extract Figma ZIP to canonical locations")
    p_zip.add_argument("path", help="Path to the Figma export ZIP file")

    sub.add_parser("from-mockup", help="Slice piece sprites from reference/game.png")
    sub.add_parser("build", help="Build processed assets into assets/build/")
    sub.add_parser("check", help="Validate raw assets (read-only)")
    sub.add_parser("preview", help="Render a quick piece preview PNG")

    args = parser.parse_args()

    dispatch = {
        "init-manifest": cmd_init_manifest,
        "import-zip": cmd_import_zip,
        "from-mockup": cmd_from_mockup,
        "build": cmd_build,
        "check": cmd_check,
        "preview": cmd_preview,
    }
    dispatch[args.command](args)


if __name__ == "__main__":
    main()
