"""
openboard.ui.board_view
~~~~~~~~~~~~~~~~~~~~~~~
Chess board widget: renders squares, coordinates, pieces, highlights, drag-and-drop,
legal-move dots, move animations, and promotion popup.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Callable

import chess
import pygame

from openboard.ui import theme
from openboard.ui.assets import AssetStore
from openboard.ui.theme import (
    ACCENT,
    BORDER,
    CARD,
    CARD_BORDER,
    DANGER,
    INK,
    PURPLE,
    SHADOW,
    TINT,
    draw_panel,
    draw_text,
    ease_out_cubic,
)

log = logging.getLogger("openboard.ui.board_view")

LIGHT_SQ = (243, 232, 250)  # #F3E8FA
DARK_SQ = (160, 133, 187)   # #A085BB


@dataclass(frozen=True, slots=True)
class MoveIntent:
    from_sq: int
    to_sq: int


class BoardView:
    """Renders a chessboard and converts mouse interactions to MoveIntent objects."""

    def __init__(
        self,
        origin: tuple[int, int],
        square_size: int,
        assets: AssetStore,
    ) -> None:
        self.origin = origin
        self.square_size = square_size
        self.assets = assets

        self.board: chess.Board = chess.Board()
        self.orientation: chess.Color = chess.WHITE
        self.interactive: chess.Color | str | None = "both"  # WHITE, BLACK, 'both', or None

        self.last_move: chess.Move | None = None
        self.check_square: int | None = None
        self.selected_square: int | None = None

        # Drag state
        self._dragged_sq: int | None = None
        self._drag_pos: tuple[int, int] | None = None

        # Move animation state
        self._animating = False
        self._anim_move: chess.Move | None = None
        self._anim_start_pos: tuple[float, float] = (0.0, 0.0)
        self._anim_end_pos: tuple[float, float] = (0.0, 0.0)
        self._anim_piece: chess.Piece | None = None
        self._anim_t: float = 0.0
        self._anim_duration: float = 0.15

        # Promotion popup
        self._promotion_active: bool = False
        self._promotion_color: chess.Color = chess.WHITE
        self._promotion_callback: Callable[[int], None] | None = None
        self._promotion_rect: pygame.Rect | None = None
        self._promo_options: list[tuple[int, pygame.Rect, str, str]] = []
        self._promo_hovered: int | None = None

        # Cache static board background
        self._board_surf: pygame.Surface | None = None
        self._rebuild_board_surface()

    def _rebuild_board_surface(self) -> None:
        total_sq = self.square_size * 8
        frame_pad = 24
        # Board surface with ranks & files area
        w = total_sq + frame_pad * 2
        h = total_sq + frame_pad * 2
        surf = pygame.Surface((w, h))
        surf.fill(CARD)

        # Draw frame panel around squares
        board_rect = pygame.Rect(frame_pad, frame_pad, total_sq, total_sq)
        draw_panel(surf, board_rect, fill=LIGHT_SQ, border=BORDER, shadow=SHADOW)

        # Draw squares
        for file in range(8):
            for rank in range(8):
                is_dark = (file + rank) % 2 == 1
                col = DARK_SQ if is_dark else LIGHT_SQ
                sq_r = pygame.Rect(
                    frame_pad + file * self.square_size,
                    frame_pad + (7 - rank) * self.square_size,
                    self.square_size,
                    self.square_size,
                )
                pygame.draw.rect(surf, col, sq_r)

        self._board_surf = surf

    def set_board(self, board: chess.Board) -> None:
        self.board = board
        self.selected_square = None
        self._dragged_sq = None
        self._drag_pos = None

    def set_orientation(self, color: chess.Color) -> None:
        if self.orientation != color:
            self.orientation = color
            self.selected_square = None
            self._dragged_sq = None

    def set_interactive(self, color: chess.Color | str | None) -> None:
        self.interactive = color

    def set_marks(self, last_move: chess.Move | None, check_square: int | None) -> None:
        self.last_move = last_move
        self.check_square = check_square

    def animate_move(self, move: chess.Move, ms: int = 150) -> None:
        self._animating = True
        self._anim_move = move
        self._anim_duration = ms / 1000.0
        self._anim_t = 0.0

        p = self.board.piece_at(move.to_square)
        if p is None:
            p = self.board.piece_at(move.from_square)
        self._anim_piece = p

        self._anim_start_pos = self._square_coords(move.from_square)
        self._anim_end_pos = self._square_coords(move.to_square)

    def ask_promotion(self, color: chess.Color, callback: Callable[[int], None]) -> None:
        self._promotion_active = True
        self._promotion_color = color
        self._promotion_callback = callback
        self._promo_hovered = None

        total_sq = self.square_size * 8
        pw = 460
        ph = 190
        px = self.origin[0] + (total_sq - pw) // 2
        py = self.origin[1] + (total_sq - ph) // 2
        self._promotion_rect = pygame.Rect(px, py, pw, ph)

        # 4 options: Queen, Rook, Bishop, Knight
        pieces = [
            (chess.QUEEN, "QUEEN", "Q"),
            (chess.ROOK, "ROOK", "R"),
            (chess.BISHOP, "BISHOP", "B"),
            (chess.KNIGHT, "KNIGHT", "N"),
        ]
        self._promo_options.clear()
        card_w = 88
        card_h = 104
        gap = 14
        total_cards_w = 4 * card_w + 3 * gap
        start_x = self._promotion_rect.centerx - total_cards_w // 2
        card_y = py + 66

        for idx, (pt, label, key) in enumerate(pieces):
            r = pygame.Rect(start_x + idx * (card_w + gap), card_y, card_w, card_h)
            self._promo_options.append((pt, r, label, key))

    def _choose_promotion(self, pt: int) -> None:
        self._promotion_active = False
        self._promo_hovered = None
        if self._promotion_callback:
            cb = self._promotion_callback
            self._promotion_callback = None
            cb(pt)

    def _cancel_promotion(self) -> None:
        self._promotion_active = False
        self._promo_hovered = None
        self._promotion_callback = None
        self.selected_square = None
        self._dragged_sq = None
        self._drag_pos = None

    def _square_coords(self, square: int) -> tuple[float, float]:
        file = chess.square_file(square)
        rank = chess.square_rank(square)
        if self.orientation == chess.BLACK:
            col = 7 - file
            row = rank
        else:
            col = file
            row = 7 - rank
        x = self.origin[0] + col * self.square_size
        y = self.origin[1] + row * self.square_size
        return (float(x), float(y))

    def square_at(self, pos: tuple[int, int]) -> int | None:
        x, y = pos
        rel_x = x - self.origin[0]
        rel_y = y - self.origin[1]

        total_size = self.square_size * 8
        if 0 <= rel_x < total_size and 0 <= rel_y < total_size:
            col = int(rel_x // self.square_size)
            row = int(rel_y // self.square_size)
            if self.orientation == chess.BLACK:
                file = 7 - col
                rank = row
            else:
                file = col
                rank = 7 - row
            return chess.square(file, rank)
        return None

    def _is_interactive_turn(self) -> bool:
        if self.interactive is None:
            return False
        if self.interactive == "both":
            return True
        return self.interactive == self.board.turn

    def handle_event(self, event: pygame.event.Event) -> MoveIntent | None:
        # Promotion popup absorbs events
        if self._promotion_active:
            if event.type == pygame.MOUSEMOTION:
                self._promo_hovered = None
                for idx, (pt, r, label, key) in enumerate(self._promo_options):
                    if r.collidepoint(event.pos):
                        self._promo_hovered = idx
                        break
                return None

            if event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:
                    for pt, r, label, key in self._promo_options:
                        if r.collidepoint(event.pos):
                            self._choose_promotion(pt)
                            return None
                    # Click outside popup panel cancels
                    if self._promotion_rect and not self._promotion_rect.collidepoint(event.pos):
                        self._cancel_promotion()
                        return None
                elif event.button == 3:  # Right-click cancels
                    self._cancel_promotion()
                    return None
                return None

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self._cancel_promotion()
                    return None
                if event.key in (pygame.K_q, pygame.K_1):
                    self._choose_promotion(chess.QUEEN)
                    return None
                if event.key in (pygame.K_r, pygame.K_2):
                    self._choose_promotion(chess.ROOK)
                    return None
                if event.key in (pygame.K_b, pygame.K_3):
                    self._choose_promotion(chess.BISHOP)
                    return None
                if event.key in (pygame.K_n, pygame.K_k, pygame.K_4):
                    self._choose_promotion(chess.KNIGHT)
                    return None
                return None

            return None

        if not self._is_interactive_turn():
            return None

        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 3:  # Right-click cancels
                self.selected_square = None
                self._dragged_sq = None
                self._drag_pos = None
                return None

            if event.button == 1:
                sq = self.square_at(event.pos)
                if sq is not None:
                    # If clicking an existing selected square or a legal destination
                    if self.selected_square is not None and sq != self.selected_square:
                        intent = MoveIntent(self.selected_square, sq)
                        self.selected_square = None
                        self._dragged_sq = None
                        return intent

                    piece = self.board.piece_at(sq)
                    if piece is not None and (self.interactive == "both" or piece.color == self.board.turn):
                        self.selected_square = sq
                        self._dragged_sq = sq
                        self._drag_pos = event.pos
                    else:
                        self.selected_square = None
                        self._dragged_sq = None
                else:
                    self.selected_square = None
                    self._dragged_sq = None

        elif event.type == pygame.MOUSEMOTION:
            if self._dragged_sq is not None:
                self._drag_pos = event.pos

        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self._dragged_sq is not None:
                from_sq = self._dragged_sq
                self._dragged_sq = None
                self._drag_pos = None
                to_sq = self.square_at(event.pos)
                if to_sq is not None and to_sq != from_sq:
                    self.selected_square = None
                    return MoveIntent(from_sq, to_sq)

        return None

    def update(self, dt: float) -> None:
        if self._animating:
            self._anim_t += dt
            if self._anim_t >= self._anim_duration:
                self._animating = False
                self._anim_move = None

    def draw(self, surf: pygame.Surface) -> None:
        total_sq = self.square_size * 8

        # Frame & background
        frame_pad = 24
        board_rect = pygame.Rect(
            self.origin[0] - frame_pad,
            self.origin[1] - frame_pad,
            total_sq + frame_pad * 2,
            total_sq + frame_pad * 2,
        )
        draw_panel(surf, board_rect, fill=CARD, border=BORDER, shadow=SHADOW)

        # Draw squares
        for file in range(8):
            for rank in range(8):
                sq = chess.square(file, rank)
                is_dark = (file + rank) % 2 == 1
                col = DARK_SQ if is_dark else LIGHT_SQ
                sx, sy = self._square_coords(sq)
                sq_r = pygame.Rect(int(sx), int(sy), self.square_size, self.square_size)
                pygame.draw.rect(surf, col, sq_r)

        # Coordinate labels
        rank_names = ["1", "2", "3", "4", "5", "6", "7", "8"]
        file_names = ["a", "b", "c", "d", "e", "f", "g", "h"]
        if self.orientation == chess.BLACK:
            rank_names.reverse()
            file_names.reverse()

        margin_left_cx = (self.origin[0] - frame_pad + BORDER + self.origin[0]) // 2
        margin_bottom_cy = (self.origin[1] + total_sq + self.origin[1] + total_sq + frame_pad - BORDER) // 2

        for idx, r_name in enumerate(reversed(rank_names)):
            ry = self.origin[1] + idx * self.square_size + self.square_size // 2
            draw_text(surf, r_name, "coord", INK, (margin_left_cx, ry), anchor="center")

        for idx, f_name in enumerate(file_names):
            fx = self.origin[0] + idx * self.square_size + self.square_size // 2
            draw_text(surf, f_name, "coord", INK, (fx, margin_bottom_cy), anchor="center")

        # Overlays: Last move highlight
        if self.last_move:
            hl_surf = pygame.Surface((self.square_size, self.square_size), pygame.SRCALPHA)
            hl_surf.fill((*ACCENT, 90))
            for sq in (self.last_move.from_square, self.last_move.to_square):
                x, y = self._square_coords(sq)
                surf.blit(hl_surf, (int(x), int(y)))

        # Selected square highlight
        if self.selected_square is not None:
            sel_surf = pygame.Surface((self.square_size, self.square_size), pygame.SRCALPHA)
            sel_surf.fill((*PURPLE, 120))
            x, y = self._square_coords(self.selected_square)
            surf.blit(sel_surf, (int(x), int(y)))

        # King check highlight
        if self.check_square is not None:
            chk_surf = pygame.Surface((self.square_size, self.square_size), pygame.SRCALPHA)
            chk_surf.fill((*DANGER, 140))
            x, y = self._square_coords(self.check_square)
            surf.blit(chk_surf, (int(x), int(y)))

        # Legal move indicators
        if self.selected_square is not None and self._is_interactive_turn():
            for move in self.board.legal_moves:
                if move.from_square == self.selected_square:
                    to_sq = move.to_square
                    tx, ty = self._square_coords(to_sq)
                    cx = int(tx + self.square_size / 2)
                    cy = int(ty + self.square_size / 2)
                    is_capture = self.board.is_capture(move)
                    if is_capture:
                        # Ring
                        pygame.draw.circle(surf, INK, (cx, cy), self.square_size // 3, 3)
                    else:
                        # Dot
                        pygame.draw.circle(surf, INK, (cx, cy), self.square_size // 8)

        # Draw pieces
        for sq in range(64):
            # Skip dragged piece or animated piece during movement
            if sq == self._dragged_sq:
                continue
            if self._animating and self._anim_move and (sq == self._anim_move.from_square or sq == self._anim_move.to_square):
                continue

            piece = self.board.piece_at(sq)
            if piece is not None:
                x, y = self._square_coords(sq)
                p_surf = self.assets.piece(piece.color, piece.piece_type, self.square_size)
                surf.blit(p_surf, (int(x), int(y)))

        # Animated move sliding piece
        if self._animating and self._anim_piece is not None:
            t = ease_out_cubic(min(1.0, self._anim_t / self._anim_duration))
            curr_x = self._anim_start_pos[0] + (self._anim_end_pos[0] - self._anim_start_pos[0]) * t
            curr_y = self._anim_start_pos[1] + (self._anim_end_pos[1] - self._anim_start_pos[1]) * t
            p_surf = self.assets.piece(self._anim_piece.color, self._anim_piece.piece_type, self.square_size)
            surf.blit(p_surf, (int(curr_x), int(curr_y)))

        # Dragged piece above all
        if self._dragged_sq is not None and self._drag_pos is not None:
            piece = self.board.piece_at(self._dragged_sq)
            if piece is not None:
                p_surf = self.assets.piece(piece.color, piece.piece_type, self.square_size)
                px = self._drag_pos[0] - self.square_size // 2
                py = self._drag_pos[1] - self.square_size // 2
                surf.blit(p_surf, (px, py))

        # Promotion popup
        if self._promotion_active and self._promotion_rect:
            # 1. Fullscreen Dim overlay
            dim_surf = pygame.Surface((1600, 900), pygame.SRCALPHA)
            dim_surf.fill((*INK, 115))
            surf.blit(dim_surf, (0, 0))

            # 2. Main modal card
            draw_panel(surf, self._promotion_rect, fill=CARD, border=BORDER, shadow=SHADOW, shadow_color=INK)

            # 3. Header title and helper hint
            draw_text(surf, "PROMOTE PAWN", "heading", INK, (self._promotion_rect.centerx, self._promotion_rect.y + 24), anchor="center")
            draw_text(
                surf,
                "Select a piece or press [Q, R, B, N] · Esc to cancel",
                "small",
                ACCENT,
                (self._promotion_rect.centerx, self._promotion_rect.y + 48),
                anchor="center",
            )

            # 4. 4 Piece Option Cards
            for idx, (pt, r, label, key) in enumerate(self._promo_options):
                is_hov = (self._promo_hovered == idx)
                fill_col = PURPLE if is_hov else CARD
                text_col = CARD if is_hov else INK
                shadow_val = 2 if is_hov else 4
                offset = -1 if is_hov else 0
                draw_r = r.move(offset, offset)

                draw_panel(surf, draw_r, fill=fill_col, border=BORDER, shadow=shadow_val, shadow_color=INK)

                # Piece sprite
                p_surf = self.assets.piece(self._promotion_color, pt, 56)
                px = draw_r.centerx - p_surf.get_width() // 2
                py = draw_r.y + 12
                surf.blit(p_surf, (px, py))

                # Label with shortcut key
                draw_text(surf, f"[{key}] {label}", "small", text_col, (draw_r.centerx, draw_r.bottom - 16), anchor="center")


def _demo() -> None:
    pygame.init()
    win = pygame.display.set_mode((1600, 900))
    assets = AssetStore()
    bv = BoardView((120, 136), 88, assets)
    clock = pygame.time.Clock()

    running = True
    while running:
        dt = clock.tick(60) / 1000.0
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                running = False
            elif ev.type == pygame.KEYDOWN and ev.key == pygame.K_f:
                bv.set_orientation(chess.BLACK if bv.orientation == chess.WHITE else chess.WHITE)

            intent = bv.handle_event(ev)
            if intent:
                move = chess.Move(intent.from_sq, intent.to_sq)
                if move in bv.board.legal_moves:
                    bv.board.push(move)
                    bv.set_marks(move, None)

        bv.update(dt)
        win.fill(theme.BG)
        bv.draw(win)
        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    _demo()
