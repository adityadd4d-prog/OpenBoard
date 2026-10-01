import pygame

class Assets():

    def __init__(self, piece_size= 80):
        self._load_assets((piece_size, piece_size))



    def _load_assets(self, size: tuple):
        # Backdrops
        self.bg_main = pygame.image.load("assets/bg_main.jpg").convert()
        self.bg_fork = pygame.image.load("assets/bg_fork.jpg").convert()

        # Black Pieces
        b_bishop = pygame.image.load("assets/BlackBishop.png").convert_alpha()
        b_king = pygame.image.load("assets/BlackKing.png").convert_alpha()
        b_knight = pygame.image.load("assets/BlackKnight.png").convert_alpha()
        b_pawn = pygame.image.load("assets/BlackPawn.png").convert_alpha()
        b_queen = pygame.image.load("assets/BlackQueen.png").convert_alpha()
        b_rook = pygame.image.load("assets/BlackRook.png").convert_alpha()
        b = pygame.transform.smoothscale(b_bishop, size)
        k = pygame.transform.smoothscale(b_king, size)
        n = pygame.transform.smoothscale(b_knight, size)
        p = pygame.transform.smoothscale(b_pawn, size)
        q = pygame.transform.smoothscale(b_queen, size)
        r = pygame.transform.smoothscale(b_rook, size)

        # White Pieces
        w_bishop = pygame.image.load("assets/WhiteBishop.png").convert_alpha()
        w_king = pygame.image.load("assets/WhiteKing.png").convert_alpha()
        w_knight = pygame.image.load("assets/WhiteKnight.png").convert_alpha()
        w_pawn = pygame.image.load("assets/WhitePawn.png").convert_alpha()
        w_queen = pygame.image.load("assets/WhiteQueen.png").convert_alpha()
        w_rook = pygame.image.load("assets/WhiteRook.png").convert_alpha()
        B = pygame.transform.smoothscale(w_bishop, size)
        K = pygame.transform.smoothscale(w_king, size)
        N = pygame.transform.smoothscale(w_knight, size)
        P = pygame.transform.smoothscale(w_pawn, size)
        Q = pygame.transform.smoothscale(w_queen, size)
        R = pygame.transform.smoothscale(w_rook, size)

        self.pieces = { "b" : b, "k" : k, "n" : n,
                        "p" : p, "q" : q, "r" : r,
                        "B" : B, "K" : K, "N" : N,
                        "P" : P, "Q" : Q, "R" : R
                    }


