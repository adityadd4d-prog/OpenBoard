import pygame

from enum import Enum

def letterbox(win_w, win_h):
    """Return (scale, (offset_x, offset_y), (out_w, out_h)) for fitting the canvas."""
    scale = min(win_w / 1600, win_h / 900)
    out_w, out_h = int(1600 * scale), int(900 * scale)
    offset = ((win_w - out_w) // 2, (win_h - out_h) // 2)
    return scale, offset, (out_w, out_h)


def translate_event(event, scale, offset):
    """Convert mouse positions from window space to 1600x900 design space."""
    if event.type in (pygame.MOUSEMOTION, pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP):
        data = dict(event.dict)
        data["pos"] = (
            int((event.pos[0] - offset[0]) / scale),
            int((event.pos[1] - offset[1]) / scale),
        )
        return pygame.event.Event(event.type, data)
    return event


class Assets():

    def __init__(self, piece_size= 80, screen_w = 1600, screen_h = 900):
        self._load_assets((piece_size, piece_size), (screen_w, screen_h))

        self.black = (0, 0, 0)
        self.light = (245, 237, 255)
        self.dark = (141, 115, 198)
        self.board_hint = (72, 201, 176, 128)
        self.secondary = (26, 24, 41)
        self.bg = (205, 184, 246)
        self.primary = (144, 86, 245)
        self.inactive = (215, 211, 226)
        self.check = (245, 176, 65)
        self.safe = (72, 201, 176)
        self.danger = (236, 112, 99)
        self.move = (252, 243, 207)

    def _load_assets(self, piece_size: tuple, bg_size: tuple):
        # Backdrops
        bg_main = pygame.image.load("assets/bg_main.jpg").convert()
        bg_fork = pygame.image.load("assets/bg_fork.jpg").convert()
        self.bg_main = pygame.transform.smoothscale(bg_main, bg_size)
        self.bg_fork = pygame.transform.smoothscale(bg_fork, bg_size)

        # Black Pieces
        b_bishop = pygame.image.load("assets/BlackBishop.png").convert_alpha()
        b_king = pygame.image.load("assets/BlackKing.png").convert_alpha()
        b_knight = pygame.image.load("assets/BlackKnight.png").convert_alpha()
        b_pawn = pygame.image.load("assets/BlackPawn.png").convert_alpha()
        b_queen = pygame.image.load("assets/BlackQueen.png").convert_alpha()
        b_rook = pygame.image.load("assets/BlackRook.png").convert_alpha()
        b = pygame.transform.smoothscale(b_bishop, piece_size)
        k = pygame.transform.smoothscale(b_king, piece_size)
        n = pygame.transform.smoothscale(b_knight, piece_size)
        p = pygame.transform.smoothscale(b_pawn, piece_size)
        q = pygame.transform.smoothscale(b_queen, piece_size)
        r = pygame.transform.smoothscale(b_rook, piece_size)

        # White Pieces
        w_bishop = pygame.image.load("assets/WhiteBishop.png").convert_alpha()
        w_king = pygame.image.load("assets/WhiteKing.png").convert_alpha()
        w_knight = pygame.image.load("assets/WhiteKnight.png").convert_alpha()
        w_pawn = pygame.image.load("assets/WhitePawn.png").convert_alpha()
        w_queen = pygame.image.load("assets/WhiteQueen.png").convert_alpha()
        w_rook = pygame.image.load("assets/WhiteRook.png").convert_alpha()
        B = pygame.transform.smoothscale(w_bishop, piece_size)
        K = pygame.transform.smoothscale(w_king, piece_size)
        N = pygame.transform.smoothscale(w_knight, piece_size)
        P = pygame.transform.smoothscale(w_pawn, piece_size)
        Q = pygame.transform.smoothscale(w_queen, piece_size)
        R = pygame.transform.smoothscale(w_rook, piece_size)

        self.pieces = { "b" : b, "k" : k, "n" : n,
                        "p" : p, "q" : q, "r" : r,
                        "B" : B, "K" : K, "N" : N,
                        "P" : P, "Q" : Q, "R" : R
                    }


class Button():
    def __init__(self, manager):
        self._assets = Assets()
        self._manager = manager

    def primary(self, text: str, x, y):
        button = pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect((x, y), (w, h)),
            text=text,
            manager=self._manager
        )

    def secondary(self, text: str, x, y, w, h):
        button = pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect((x, y), (w, h)),
            text=text,
            manager=self._manager
        )

    def danger(self, text: str, x, y, w, h):
        button = pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect((x, y), (w, h)),
            text=text,
            manager=self._manager
        )


class Menu:

    def __init__(self, canvas, assets, manager):
        self._canvas = canvas
        self._assets = assets
        self._manager = manager
        self._nav = []
        self.draw_main()

    def back(self):
        if len(self._nav) > 1:
            pygame.event.post(self._nav.pop())
        else:
            pygame.event.post(pygame.event.Event(pygame.QUIT))

    def draw_main(self):
        self._canvas.blit(self._assets.bg_main, (0, 0))


    def draw_exit_dialog(self):
        pass





