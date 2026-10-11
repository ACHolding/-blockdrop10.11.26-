# Python 3.14+ / pygame-ce
# AC's Famicom Block Drop 0.1
# Single-file, 60 FPS, no external assets.

import sys
import random
from collections import deque

import pygame
from array import array
import math

pygame.mixer.pre_init(22050, -16, 1, 512)
pygame.init()
pygame.display.set_caption("AC's Famicom Block Drop 0.1")

# ---------------------------------------------------------------------
# VIDEO / TIMING
# ---------------------------------------------------------------------
BASE_W, BASE_H = 220, 200
SCALE = 3
FPS = 60

screen = pygame.display.set_mode(
    (BASE_W * SCALE, BASE_H * SCALE),
    pygame.RESIZABLE
)
canvas = pygame.Surface((BASE_W, BASE_H))
clock = pygame.time.Clock()

# Game Boy-ish green palette inspired by the supplied GUI.
BG      = (118, 178, 72)
DARK    = (28, 68, 32)
MID     = (58, 104, 47)
LIGHT   = (151, 200, 93)
INK     = (22, 56, 28)

# ---------------------------------------------------------------------
# LAYOUT
# ---------------------------------------------------------------------
BOARD_X = 13
BOARD_Y = 4
CELL = 8
COLS = 10
ROWS = 22
BOARD_W = COLS * CELL
BOARD_H = ROWS * CELL

PANEL_X = 147
PANEL_W = 70

# ---------------------------------------------------------------------
# FONTS
# ---------------------------------------------------------------------
def font(size, bold=False):
    return pygame.font.Font(None, size)

FONT_TINY = font(10)
FONT_SMALL = font(12)
FONT_MED = font(16)
FONT_BIG = font(24)

def draw_text(surf, text, x, y, fnt=FONT_SMALL, color=INK, center=False):
    img = fnt.render(str(text), False, color)
    if center:
        x -= img.get_width() // 2
    surf.blit(img, (x, y))

# ---------------------------------------------------------------------
# TETROMINO DATA
# ---------------------------------------------------------------------
SHAPES = {
    "I": [
        [(0,1),(1,1),(2,1),(3,1)],
        [(2,0),(2,1),(2,2),(2,3)],
        [(0,2),(1,2),(2,2),(3,2)],
        [(1,0),(1,1),(1,2),(1,3)],
    ],
    "O": [
        [(1,0),(2,0),(1,1),(2,1)],
    ],
    "T": [
        [(1,0),(0,1),(1,1),(2,1)],
        [(1,0),(1,1),(2,1),(1,2)],
        [(0,1),(1,1),(2,1),(1,2)],
        [(1,0),(0,1),(1,1),(1,2)],
    ],
    "S": [
        [(1,0),(2,0),(0,1),(1,1)],
        [(1,0),(1,1),(2,1),(2,2)],
    ],
    "Z": [
        [(0,0),(1,0),(1,1),(2,1)],
        [(2,0),(1,1),(2,1),(1,2)],
    ],
    "J": [
        [(0,0),(0,1),(1,1),(2,1)],
        [(1,0),(2,0),(1,1),(1,2)],
        [(0,1),(1,1),(2,1),(2,2)],
        [(1,0),(1,1),(0,2),(1,2)],
    ],
    "L": [
        [(2,0),(0,1),(1,1),(2,1)],
        [(1,0),(1,1),(1,2),(2,2)],
        [(0,1),(1,1),(2,1),(0,2)],
        [(0,0),(1,0),(1,1),(1,2)],
    ],
}

PIECES = tuple(SHAPES.keys())

# NES/Famicom-style gravity: frames per row at 60 FPS.
# Levels beyond table clamp to final speed.
FAMICOM_FRAMES_PER_ROW = [
    48, 43, 38, 33, 28, 23, 18, 13, 8, 6,
    5, 5, 5, 4, 4, 4, 3, 3, 3, 2,
    2, 2, 2, 2, 2, 2, 2, 2, 1
]

# ---------------------------------------------------------------------
# DRAWING HELPERS
# ---------------------------------------------------------------------
def rect_outline(surf, rect, color=INK, width=2):
    pygame.draw.rect(surf, color, rect, width)

def draw_block(surf, px, py, filled=True):
    r = pygame.Rect(px, py, CELL, CELL)
    if filled:
        pygame.draw.rect(surf, DARK, r)
        pygame.draw.rect(surf, MID, (px+1, py+1, CELL-2, CELL-2))
        pygame.draw.rect(surf, DARK, (px+2, py+2, CELL-4, CELL-4))
    else:
        pygame.draw.rect(surf, MID, r, 1)

def draw_border_pattern(surf, x, y, h):
    # Decorative "hardware" strip similar to the supplied reference.
    for yy in range(y, y+h, 4):
        pygame.draw.rect(surf, DARK, (x, yy, 4, 2))
        pygame.draw.rect(surf, MID, (x+4, yy+2, 4, 2))

def draw_panel_box(surf, y, h, title, value=None):
    pygame.draw.rect(surf, DARK, (PANEL_X, y, PANEL_W, h), 2)
    pygame.draw.rect(surf, MID, (PANEL_X+3, y+3, PANEL_W-6, h-6), 1)
    draw_text(surf, title, PANEL_X + PANEL_W//2, y+4, FONT_MED, INK, True)
    if value is not None:
        # Right-align the counter inside the panel.  The old code started
        # drawing at x=210, so multi-digit values were clipped off-screen.
        img = FONT_MED.render(str(value), False, INK)
        vx = PANEL_X + PANEL_W - 6 - img.get_width()
        surf.blit(img, (vx, y+h-15))

# ---------------------------------------------------------------------
# BAG RANDOMIZER
# ---------------------------------------------------------------------
class Bag:
    def __init__(self):
        self.q = deque()

    def take(self):
        if not self.q:
            bag = list(PIECES)
            random.shuffle(bag)
            self.q.extend(bag)
        return self.q.popleft()


# ---------------------------------------------------------------------
# GAMEPLAY MUSIC — "KOROBEINIKI" / traditional Russian folk melody
# Synthesized in code: no external audio file required.
# Plays only during gameplay; pauses/stops when returning to menu or EXIT.
# ---------------------------------------------------------------------
class RussianMusic:
    RATE = 22050

    # Traditional Korobeiniki melody, compact looping arrangement.
    # note, beats (None = rest)
    MELODY = [
        ("E5",1),("B4",0.5),("C5",0.5),("D5",1),("C5",0.5),("B4",0.5),
        ("A4",1),("A4",0.5),("C5",0.5),("E5",1),("D5",0.5),("C5",0.5),
        ("B4",1.5),("C5",0.5),("D5",1),("E5",1),
        ("C5",1),("A4",1),("A4",1), (None,0.5),

        ("D5",1),("F5",0.5),("A5",1),("G5",0.5),("F5",0.5),
        ("E5",1.5),("C5",0.5),("E5",1),("D5",0.5),("C5",0.5),
        ("B4",1),("B4",0.5),("C5",0.5),("D5",1),("E5",1),
        ("C5",1),("A4",1),("A4",1), (None,0.5),
    ]

    NOTE_INDEX = {
        "A4": 69, "B4": 71, "C5": 72, "D5": 74,
        "E5": 76, "F5": 77, "G5": 79, "A5": 81,
    }

    def __init__(self):
        self.ok = pygame.mixer.get_init() is not None
        self.sound = None
        self.channel = None
        self.playing = False
        if self.ok:
            try:
                self.sound = self._build_loop()
                self.channel = pygame.mixer.Channel(0)
            except Exception:
                self.ok = False

    @classmethod
    def freq(cls, note):
        midi = cls.NOTE_INDEX[note]
        return 440.0 * (2.0 ** ((midi - 69) / 12.0))

    def _build_loop(self):
        bpm = 150.0
        beat_sec = 60.0 / bpm
        out = array("h")
        phase = 0.0

        for note, beats in self.MELODY:
            dur = beat_sec * beats
            n = max(1, int(self.RATE * dur))

            if note is None:
                out.extend([0] * n)
                continue

            f = self.freq(note)
            for i in range(n):
                phase = (phase + f / self.RATE) % 1.0

                # Famicom-ish pulse wave + tiny octave layer.
                pulse = 1.0 if phase < 0.25 else -1.0
                octave = 1.0 if ((phase * 2.0) % 1.0) < 0.5 else -1.0

                # Short attack/release to prevent harsh clicks.
                attack = min(1.0, i / max(1, int(self.RATE * 0.008)))
                release = min(1.0, (n - 1 - i) / max(1, int(self.RATE * 0.020)))
                env = max(0.0, min(attack, release))

                sample = int((pulse * 0.13 + octave * 0.035) * env * 32767)
                out.append(max(-32768, min(32767, sample)))

        return pygame.mixer.Sound(buffer=out.tobytes())

    def play(self):
        if self.ok and self.sound and self.channel:
            if not self.playing:
                self.channel.play(self.sound, loops=-1)
                self.playing = True

    def pause(self):
        if self.ok and self.channel and self.playing:
            self.channel.pause()

    def resume(self):
        if self.ok and self.channel and self.playing:
            self.channel.unpause()

    def stop(self):
        if self.ok and self.channel:
            self.channel.stop()
        self.playing = False

# ---------------------------------------------------------------------
# GAME
# ---------------------------------------------------------------------
class Game:
    def __init__(self):
        self.bag = Bag()
        self.board = [[None for _ in range(COLS)] for _ in range(ROWS)]
        self.score = 0
        self.lines = 0
        self.level = 0
        self.game_over = False
        self.paused = False
        self.drop_counter = 0
        self.soft_drop = False
        self.next_kind = self.bag.take()
        self.spawn()

    def spawn(self):
        self.kind = self.next_kind
        self.next_kind = self.bag.take()
        self.rot = 0
        self.x = 3
        self.y = 0
        self.drop_counter = 0

        if not self.valid(self.x, self.y, self.rot):
            self.game_over = True

    def cells(self, x=None, y=None, rot=None):
        if x is None: x = self.x
        if y is None: y = self.y
        if rot is None: rot = self.rot
        states = SHAPES[self.kind]
        shape = states[rot % len(states)]
        return [(x+cx, y+cy) for cx, cy in shape]

    def valid(self, x, y, rot):
        for cx, cy in self.cells(x, y, rot):
            if cx < 0 or cx >= COLS or cy >= ROWS:
                return False
            if cy >= 0 and self.board[cy][cx] is not None:
                return False
        return True

    def move(self, dx, dy):
        if self.valid(self.x+dx, self.y+dy, self.rot):
            self.x += dx
            self.y += dy
            return True
        return False

    def rotate(self, direction=1):
        states = SHAPES[self.kind]
        nr = (self.rot + direction) % len(states)

        # Small wall-kick set, still keeping a classic feel.
        for kick in (0, -1, 1, -2, 2):
            if self.valid(self.x + kick, self.y, nr):
                self.x += kick
                self.rot = nr
                return True
        return False

    def hard_drop(self):
        if self.game_over or self.paused:
            return
        rows = 0
        while self.move(0, 1):
            rows += 1
        self.score += rows * 2
        self.lock_piece()

    def lock_piece(self):
        for x, y in self.cells():
            if y < 0:
                self.game_over = True
                return
            self.board[y][x] = self.kind

        cleared = self.clear_lines()
        if cleared:
            # Classic-ish scoring.
            points = (0, 40, 100, 300, 1200)[cleared]
            self.score += points * (self.level + 1)

        self.level = min(99, self.lines // 10)
        self.spawn()

    def clear_lines(self):
        keep = [row for row in self.board if any(cell is None for cell in row)]
        cleared = ROWS - len(keep)
        while len(keep) < ROWS:
            keep.insert(0, [None] * COLS)
        self.board = keep
        self.lines += cleared
        return cleared

    def gravity_frames(self):
        idx = min(self.level, len(FAMICOM_FRAMES_PER_ROW)-1)
        frames = FAMICOM_FRAMES_PER_ROW[idx]
        if self.soft_drop:
            frames = min(frames, 2)
        return max(1, frames)

    def update(self):
        if self.game_over or self.paused:
            return
        self.drop_counter += 1
        if self.drop_counter >= self.gravity_frames():
            self.drop_counter = 0
            moved = self.move(0, 1)
            if moved:
                # Classic-style soft-drop reward so SCORE visibly advances
                # while the player holds DOWN/S. Normal gravity is free.
                if self.soft_drop:
                    self.score += 1
            else:
                self.lock_piece()

    def draw(self, surf):
        surf.fill(BG)

        # Reference-like decorative strips.
        draw_border_pattern(surf, 0, 0, BASE_H)
        draw_border_pattern(surf, 137, 0, BASE_H)

        # Board backing.
        pygame.draw.rect(surf, LIGHT, (BOARD_X-2, BOARD_Y-2, BOARD_W+4, BOARD_H+4))
        pygame.draw.rect(surf, DARK, (BOARD_X-2, BOARD_Y-2, BOARD_W+4, BOARD_H+4), 2)

        # Subtle grid.
        for gy in range(ROWS):
            for gx in range(COLS):
                draw_block(surf, BOARD_X + gx*CELL, BOARD_Y + gy*CELL, False)

        # Locked blocks.
        for y, row in enumerate(self.board):
            for x, cell in enumerate(row):
                if cell is not None:
                    draw_block(surf, BOARD_X + x*CELL, BOARD_Y + y*CELL)

        # Falling piece.
        if not self.game_over:
            for x, y in self.cells():
                if y >= 0:
                    draw_block(surf, BOARD_X + x*CELL, BOARD_Y + y*CELL)

        # Right HUD.
        draw_panel_box(surf, 3, 38, "SCORE", f"{self.score}")
        draw_panel_box(surf, 56, 34, "LEVEL", f"{self.level}")
        draw_panel_box(surf, 95, 34, "LINES", f"{self.lines}")

        # Next preview box.
        pygame.draw.rect(surf, DARK, (PANEL_X+9, 140, 60, 53), 2)
        pygame.draw.rect(surf, MID, (PANEL_X+12, 143, 54, 47), 1)
        draw_text(surf, "NEXT", PANEL_X+39, 144, FONT_TINY, INK, True)

        preview = SHAPES[self.next_kind][0]
        min_x = min(x for x, _ in preview)
        max_x = max(x for x, _ in preview)
        min_y = min(y for _, y in preview)
        max_y = max(y for _, y in preview)
        pw = (max_x-min_x+1)*CELL
        ph = (max_y-min_y+1)*CELL
        ox = PANEL_X + 39 - pw//2 - min_x*CELL
        oy = 163 + (20-ph)//2 - min_y*CELL
        for x, y in preview:
            draw_block(surf, ox+x*CELL, oy+y*CELL)

        if self.paused:
            pygame.draw.rect(surf, BG, (24, 76, 100, 42))
            rect_outline(surf, (24, 76, 100, 42), DARK, 2)
            draw_text(surf, "PAUSED", 74, 84, FONT_BIG, DARK, True)
            draw_text(surf, "P TO RESUME", 74, 106, FONT_TINY, DARK, True)

        if self.game_over:
            pygame.draw.rect(surf, BG, (18, 69, 112, 58))
            rect_outline(surf, (18, 69, 112, 58), DARK, 2)
            draw_text(surf, "GAME OVER", 74, 77, FONT_MED, DARK, True)
            draw_text(surf, "ENTER = RETRY", 74, 98, FONT_TINY, DARK, True)
            draw_text(surf, "ESC = MENU", 74, 112, FONT_TINY, DARK, True)

# ---------------------------------------------------------------------
# MENU
# ---------------------------------------------------------------------
MENU_ITEMS = ["PLAY GAME", "HELP", "ABOUT", "EXIT"]

class Menu:
    def __init__(self):
        self.index = 0
        self.mode = "main"

    def key(self, key):
        if self.mode != "main":
            if key in (pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_SPACE, pygame.K_BACKSPACE):
                self.mode = "main"
            return None

        if key in (pygame.K_UP, pygame.K_w):
            self.index = (self.index - 1) % len(MENU_ITEMS)
        elif key in (pygame.K_DOWN, pygame.K_s):
            self.index = (self.index + 1) % len(MENU_ITEMS)
        elif key in (pygame.K_RETURN, pygame.K_SPACE):
            return MENU_ITEMS[self.index]
        return None

    def draw_frame(self, surf, title):
        surf.fill(BG)
        draw_border_pattern(surf, 0, 0, BASE_H)
        draw_border_pattern(surf, 137, 0, BASE_H)
        pygame.draw.rect(surf, DARK, (13, 8, 120, 184), 2)
        pygame.draw.rect(surf, MID, (17, 12, 112, 176), 1)
        draw_text(surf, title, 73, 19, FONT_BIG, DARK, True)

        # HUD-like right side for style continuity.
        draw_panel_box(surf, 3, 38, "SCORE", "0")
        draw_panel_box(surf, 56, 34, "LEVEL", "0")
        draw_panel_box(surf, 95, 34, "LINES", "0")
        pygame.draw.rect(surf, DARK, (156, 140, 60, 53), 2)
        pygame.draw.rect(surf, MID, (159, 143, 54, 47), 1)

    def draw(self, surf):
        if self.mode == "main":
            self.draw_frame(surf, "BLOCK DROP")
            draw_text(surf, "FAMICOM SPEED", 73, 45, FONT_TINY, INK, True)
            for i, item in enumerate(MENU_ITEMS):
                y = 72 + i*23
                selected = i == self.index
                if selected:
                    pygame.draw.rect(surf, DARK, (28, y-3, 90, 18))
                    draw_text(surf, "> " + item, 73, y, FONT_MED, BG, True)
                else:
                    draw_text(surf, item, 73, y, FONT_MED, DARK, True)

            draw_text(surf, "ARROWS + ENTER", 73, 171, FONT_TINY, DARK, True)
            draw_text(surf, "60 FPS", 73, 182, FONT_TINY, DARK, True)

        elif self.mode == "help":
            self.draw_frame(surf, "HELP")
            lines = [
                "LEFT / RIGHT  MOVE",
                "DOWN          SOFT DROP",
                "UP / X        ROTATE",
                "Z             ROTATE BACK",
                "SPACE         HARD DROP",
                "P             PAUSE",
                "ESC           MENU",
                "",
                "CLEAR LINES TO SCORE",
                "LEVEL UP EVERY 10 LINES",
                "SPEED USES CLASSIC",
                "FAMICOM 60HZ GRAVITY",
            ]
            for i, line in enumerate(lines):
                draw_text(surf, line, 22, 51+i*11, FONT_TINY, DARK)

        elif self.mode == "about":
            self.draw_frame(surf, "ABOUT")
            lines = [
                "AC'S FAMICOM",
                "BLOCK DROP 0.1",
                "",
                "PYTHON 3.14+",
                "PYGAME-CE",
                "60 FPS",
                "",
                "NO EXTERNAL ASSETS",
                "SINGLE FILE",
                "",
                "GUI INSPIRED BY",
                "THE PROVIDED IMAGE",
            ]
            for i, line in enumerate(lines):
                draw_text(surf, line, 73, 51+i*11, FONT_TINY, DARK, True)

# ---------------------------------------------------------------------
# PRESENTATION / SCALING
# ---------------------------------------------------------------------
def present():
    sw, sh = screen.get_size()
    integer_scale = max(1, min(sw // BASE_W, sh // BASE_H))
    w, h = BASE_W * integer_scale, BASE_H * integer_scale
    scaled = pygame.transform.scale(canvas, (w, h))
    screen.fill(DARK)
    screen.blit(scaled, ((sw-w)//2, (sh-h)//2))
    pygame.display.flip()

# ---------------------------------------------------------------------
# MAIN LOOP
# ---------------------------------------------------------------------
def main():
    menu = Menu()
    game = None
    music = RussianMusic()
    state = "menu"
    running = True

    while running:
        clock.tick(FPS)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                music.pause()
                running = False

            elif event.type == pygame.KEYDOWN:
                if state == "menu":
                    action = menu.key(event.key)
                    if action == "PLAY GAME":
                        game = Game()
                        state = "game"
                        music.stop()
                        music.play()
                    elif action == "HELP":
                        menu.mode = "help"
                    elif action == "ABOUT":
                        menu.mode = "about"
                    elif action == "EXIT":
                        music.pause()
                        running = False

                elif state == "game":
                    if event.key == pygame.K_ESCAPE:
                        music.pause()
                        state = "menu"
                        menu.mode = "main"
                    elif event.key == pygame.K_p and not game.game_over:
                        game.paused = not game.paused
                        if game.paused:
                            music.pause()
                        else:
                            music.resume()
                    elif game.game_over and event.key in (pygame.K_RETURN, pygame.K_SPACE):
                        game = Game()
                    elif not game.paused and not game.game_over:
                        if event.key in (pygame.K_LEFT, pygame.K_a):
                            game.move(-1, 0)
                        elif event.key in (pygame.K_RIGHT, pygame.K_d):
                            game.move(1, 0)
                        elif event.key in (pygame.K_UP, pygame.K_x):
                            game.rotate(1)
                        elif event.key == pygame.K_z:
                            game.rotate(-1)
                        elif event.key == pygame.K_SPACE:
                            game.hard_drop()
                        elif event.key in (pygame.K_DOWN, pygame.K_s):
                            game.soft_drop = True

            elif event.type == pygame.KEYUP and state == "game" and game:
                if event.key in (pygame.K_DOWN, pygame.K_s):
                    game.soft_drop = False

        if state == "menu":
            menu.draw(canvas)
        else:
            game.update()
            game.draw(canvas)

        present()

    music.stop()
    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()
