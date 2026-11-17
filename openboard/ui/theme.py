"""
openboard.ui.theme
~~~~~~~~~~~~~~~~~~
Colour constants, font loading, and core drawing helpers for the
neo-brutalist OpenBoard UI.

All drawing helpers operate on ``pygame.Surface`` objects and are
intentionally side-effect-free (no global state aside from the font
cache which is populated lazily).
"""
from __future__ import annotations

import logging
import os
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING

import pygame

if TYPE_CHECKING:
    pass

log = logging.getLogger("openboard.ui.theme")

# ---------------------------------------------------------------------------
# Colour palette
# ---------------------------------------------------------------------------

BG: tuple[int, int, int] = (243, 232, 250)      # #F3E8FA
CARD: tuple[int, int, int] = (251, 244, 255)     # #FBF4FF
INK: tuple[int, int, int] = (48, 42, 59)         # #302A3B
PURPLE: tuple[int, int, int] = (160, 133, 187)   # #A085BB
ACCENT: tuple[int, int, int] = (117, 84, 137)    # #755489
TINT: tuple[int, int, int] = (227, 213, 236)     # #E3D5EC
CARD_BORDER: tuple[int, int, int] = (199, 177, 210)  # #C7B1D2
DANGER: tuple[int, int, int] = (220, 53, 69)     # red for check / invalid
DIM: tuple[int, int, int, int] = (48, 42, 59, 115)  # INK at ~45% alpha

# ---------------------------------------------------------------------------
# Layout constants
# ---------------------------------------------------------------------------

BORDER: int = 3
SHADOW: int = 6

# ---------------------------------------------------------------------------
# Font configuration
# ---------------------------------------------------------------------------

# Map role -> (weight, size_px)
_FONT_SPEC: dict[str, tuple[str, int]] = {
    "wordmark": ("ExtraBold", 110),
    "title":    ("Bold", 30),
    "heading":  ("Bold", 24),
    "label":    ("Bold", 18),
    "body":     ("Regular", 18),
    "small":    ("Regular", 14),
    "number":   ("Bold", 56),
    "clock":    ("Bold", 64),
    "mono":     ("Regular", 18),  # falls back to monospace sysfonts
}

# Weight -> Inter TTF filename stem
_WEIGHT_FILE: dict[str, str] = {
    "Regular":   "Inter-Regular",
    "Medium":    "Inter-Medium",
    "SemiBold":  "Inter-SemiBold",
    "Bold":      "Inter-Bold",
    "ExtraBold": "Inter-ExtraBold",
}

_font_cache: dict[str, pygame.font.Font] = {}
_warned_missing: bool = False


def _fonts_dir() -> Path:
    """Return the assets/build/fonts directory, relative to this package."""
    here = Path(__file__).resolve().parent.parent.parent  # project root
    return here / "assets" / "build" / "fonts"


def font(role: str) -> pygame.font.Font:
    """Return a cached ``pygame.font.Font`` for the given role.

    Roles: ``wordmark``, ``title``, ``heading``, ``label``, ``body``,
    ``small``, ``number``, ``clock``, ``mono``.

    Falls back to ``pygame.font.SysFont`` (with one warning) when Inter
    TTFs are not present in *assets/build/fonts/*.
    """
    global _warned_missing
    if role in _font_cache:
        return _font_cache[role]

    spec = _FONT_SPEC.get(role, ("Regular", 18))
    weight, size = spec
    fonts_dir = _fonts_dir()
    ttf_name = _WEIGHT_FILE.get(weight, "Inter-Regular")
    ttf_path = fonts_dir / f"{ttf_name}.ttf"

    loaded: pygame.font.Font | None = None

    if ttf_path.exists():
        try:
            if role == "mono":
                # Try a monospace TTF next to Inter if available
                mono_path = fonts_dir / "JetBrainsMono-Regular.ttf"
                if mono_path.exists():
                    loaded = pygame.font.Font(str(mono_path), size)
                else:
                    loaded = pygame.font.Font(str(ttf_path), size)
            else:
                loaded = pygame.font.Font(str(ttf_path), size)
        except Exception as exc:
            log.warning("Could not load font %s: %s", ttf_path, exc)

    if loaded is None:
        if not _warned_missing:
            log.warning(
                "Inter TTF not found at %s — falling back to system fonts. "
                "Run the asset-build script to get pixel-perfect rendering.",
                fonts_dir,
            )
            _warned_missing = True
        if role == "mono":
            loaded = pygame.font.SysFont("monospace", size)
        else:
            sysname = {
                "wordmark": "sans-bold",
                "title": "sans-bold",
                "heading": "sans-bold",
                "label": "sans-bold",
                "number": "sans-bold",
                "clock": "sans-bold",
            }.get(role, "sans")
            loaded = pygame.font.SysFont(sysname, size, bold=(weight in ("Bold", "ExtraBold", "SemiBold")))

    _font_cache[role] = loaded
    return loaded


# ---------------------------------------------------------------------------
# Drawing helpers
# ---------------------------------------------------------------------------


def draw_panel(
    surf: pygame.Surface,
    rect: pygame.Rect,
    fill: tuple = CARD,
    border: int = BORDER,
    shadow: int = SHADOW,
    shadow_color: tuple = INK,
) -> None:
    """Draw a neo-brutalist panel: filled rect with ink border and hard offset shadow.

    The shadow is a solid-coloured rectangle offset *shadow* pixels
    down-right, drawn beneath the panel fill.  No blur is applied.
    """
    # Shadow (drawn first, behind the panel)
    if shadow > 0:
        shadow_rect = pygame.Rect(rect.x + shadow, rect.y + shadow, rect.width, rect.height)
        pygame.draw.rect(surf, shadow_color, shadow_rect)

    # Panel fill
    pygame.draw.rect(surf, fill, rect)

    # Border
    if border > 0:
        pygame.draw.rect(surf, shadow_color, rect, border)


def draw_text(
    surf: pygame.Surface,
    text: str,
    role: str,
    color: tuple,
    pos: tuple[int, int],
    anchor: str = "topleft",
) -> pygame.Rect:
    """Render *text* with the given font *role* and return the bounding rect.

    *anchor* may be any ``pygame.Rect`` attribute name (e.g. ``"center"``,
    ``"midright"``).
    """
    f = font(role)
    surf_text = f.render(text, True, color)
    rect = surf_text.get_rect()
    setattr(rect, anchor, pos)
    surf.blit(surf_text, rect)
    return rect


def fit_text(text: str, role: str, max_w: int) -> str:
    """Return *text* truncated with an ellipsis if wider than *max_w* pixels."""
    f = font(role)
    if f.size(text)[0] <= max_w:
        return text
    ellipsis = "…"
    while text and f.size(text + ellipsis)[0] > max_w:
        text = text[:-1]
    return text + ellipsis


def wrap_text(text: str, role: str, max_w: int) -> list[str]:
    """Word-wrap *text* to *max_w* pixels and return a list of lines."""
    f = font(role)
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = (current + " " + word).strip()
        if f.size(candidate)[0] <= max_w:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines or [""]


def lerp_color(a: tuple, b: tuple, t: float) -> tuple:
    """Linear interpolate between two RGB(A) colour tuples."""
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(len(a)))  # type: ignore[return-value]


def ease_out_cubic(t: float) -> float:
    """Ease-out cubic: ``1 - (1 - t)^3``."""
    return 1.0 - (1.0 - t) ** 3


# ---------------------------------------------------------------------------
# Demo entry-point
# ---------------------------------------------------------------------------


def _demo() -> None:  # pragma: no cover
    """Show a window with colour swatches, font samples, and a sample panel."""
    pygame.init()
    screen = pygame.display.set_mode((900, 700))
    pygame.display.set_caption("theme demo")
    clock = pygame.time.Clock()

    swatches = [
        ("BG", BG), ("CARD", CARD), ("INK", INK), ("PURPLE", PURPLE),
        ("ACCENT", ACCENT), ("TINT", TINT), ("CARD_BORDER", CARD_BORDER),
        ("DANGER", DANGER),
    ]
    roles = list(_FONT_SPEC.keys())

    running = True
    while running:
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                running = False
            if ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
                running = False

        screen.fill(BG)

        # Swatches
        for i, (name, colour) in enumerate(swatches):
            x, y = 20 + i * 105, 20
            r = pygame.Rect(x, y, 90, 50)
            draw_panel(screen, r, fill=colour[:3], shadow=4)
            draw_text(screen, name, "small", INK, (x + 45, y + 55), anchor="midtop")

        # Font samples
        for i, role in enumerate(roles):
            y = 110 + i * 42
            draw_text(screen, f"{role}: The quick brown fox", role, INK, (20, y))

        # Sample panel
        panel_r = pygame.Rect(600, 110, 280, 160)
        draw_panel(screen, panel_r)
        draw_text(screen, "Sample Panel", "heading", INK, (panel_r.centerx, panel_r.y + 20), anchor="midtop")
        draw_text(screen, "Neo-brutalist style", "body", ACCENT, (panel_r.centerx, panel_r.y + 60), anchor="midtop")

        pygame.display.flip()
        clock.tick(60)

    pygame.quit()


if __name__ == "__main__":
    _demo()
