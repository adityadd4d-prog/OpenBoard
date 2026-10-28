import sys
import pygame

import ui

pygame.init()

WINDOW_SIZE = (1600, 900)
FPS = 60

pygame.display.set_mode(WINDOW_SIZE, pygame.RESIZABLE)
pygame.display.set_caption("OpenBoard")
clock = pygame.time.Clock()

canvas = pygame.Surface(WINDOW_SIZE)

assets = ui.Assets()

scaled = None
running = True

while running:
    time_delta = clock.tick(FPS) / 1000.0

    window = pygame.display.get_surface()
    scale, offset, out_size = ui.letterbox(*window.get_size())

    if out_size[0] < 1 or out_size[1] < 1:
        pygame.event.pump()
        continue

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            opt = screen.draw_exit_dialog()
            if opt:
                running = False
            else:
                continue



    window.fill(assets.black)
    if out_size == WINDOW_SIZE:
        window.blit(canvas, offset)
    else:
        if scaled is None or scaled.get_size() != out_size:
            scaled = pygame.Surface(out_size)
        pygame.transform.smoothscale(canvas, out_size, scaled)
        window.blit(scaled, offset)

    pygame.display.flip()

pygame.quit()
sys.exit()