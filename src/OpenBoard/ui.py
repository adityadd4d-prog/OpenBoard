import pygame

class Menu:

    def __init__(self, canvas, assets, manager):
        self._canvas = canvas
        self._assets = assets
        self._manager = manager
        self._nav = []
        self.draw_main()

    def back(self):
        if len(self._nav) > 0:
            pygame.event.post(self._nav.pop())
        else:
            pygame.event.post(pygame.event.Event(pygame.QUIT))

    def draw_main(self):
        self._canvas.blit(self._assets.bg_main, (-1, 0))


    def draw_exit_dialog(self):
        pass
