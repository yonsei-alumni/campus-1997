"""Paint what is seen through the campus windows: a 4 x 4 atlas of 1997 rooms and halls behind glass.

The web app's window glass (web/src/materials.js) picks a cell for every pane, so that the windows of a facade differ
as in reference/학생회관_정면_2009.jpg: dark rooms, white, beige and pale green curtains, venetian blinds, lit
classrooms, bookshelves, papers taped to the glass.  Rows 0-2 are rooms (punched windows), row 3 halls (lobbies,
stair halls and corridors behind tall glazing, blender/common.py pane_uv).  The cells marked LIT are drawn as their
own light (a room with the lights on); the others are lit like a surface just behind the glass.

Output: web/public/assets/textures/windows.jpg (1024 x 1024, cells 256 px, top row first)
Run: .venv/bin/python tools/make_window_atlas.py
"""
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
OUT = os.path.join(ROOT, 'web/public/assets/textures/windows.jpg')
CELL = 256
SS = 2                      # supersampling
N = CELL * SS
LIT = (8, 13, 15)           # keep in step with web/src/materials.js windowGlass


def grad(c0, c1, h, w):
    """vertical gradient image (h, w, 3) from colour c0 at the top to c1 at the bottom"""
    t = np.linspace(0, 1, h)[:, None, None]
    return np.broadcast_to(np.array(c0, float) * (1 - t) + np.array(c1, float) * t, (h, w, 3)).copy()


def poly(a, pts, col):
    """fill a polygon (pixel coords) into float image a"""
    m = Image.new('L', (a.shape[1], a.shape[0]), 0)
    ImageDraw.Draw(m).polygon([(float(x), float(y)) for x, y in pts], fill=255)
    k = np.asarray(m, float)[..., None] / 255
    a[:] = a * (1 - k) + np.array(col, float) * k


def rect(a, x0, y0, x1, y1, col):
    poly(a, [(x0, y0), (x1, y0), (x1, y1), (x0, y1)], col)


def room(rng, ceil, wall, floor, back=None, hz=0.56, bw=(0.2, 0.8), bh=(0.2, None)):
    """one-point view into a room: ceiling, side walls, floor and the back wall (fractions of the cell)"""
    a = np.zeros((N, N, 3))
    bx0, bx1 = bw[0] * N, bw[1] * N
    by0 = bh[0] * N
    by1 = (bh[1] if bh[1] is not None else hz + (hz - bh[0]) * 0.35) * N
    poly(a, [(0, 0), (N, 0), (bx1, by0), (bx0, by0)], ceil)                  # ceiling
    poly(a, [(0, N), (N, N), (bx1, by1), (bx0, by1)], floor)                 # floor
    poly(a, [(0, 0), (bx0, by0), (bx0, by1), (0, N)], [c * 0.86 for c in wall])     # left wall
    poly(a, [(N, 0), (bx1, by0), (bx1, by1), (N, N)], [c * 0.92 for c in wall])     # right wall
    rect(a, bx0, by0, bx1, by1, back or wall)                                  # back wall
    return a, (bx0, by0, bx1, by1)


def ceiling_lights(a, box, col, rows=3, cols=2, glow=0.0):
    """fluorescent fittings on the ceiling in perspective, in rows towards the back wall"""
    bx0, by0, bx1, by1 = box
    for r in range(rows):
        t0, t1 = (r + 0.25) / (rows + 0.2), (r + 0.55) / (rows + 0.2)       # 0 = window wall, 1 = back wall
        for c in range(cols):
            u0, u1 = (c + 0.3) / cols, (c + 0.7) / cols
            pts = []
            for t, u in ((t0, u0), (t0, u1), (t1, u1), (t1, u0)):
                x = (1 - t) * (u * N) + t * (bx0 + u * (bx1 - bx0))
                y = (1 - t) * 0 + t * by0
                pts.append((x, y))
            poly(a, pts, col)
    if glow:
        a[: int(by0 + 4)] = a[: int(by0 + 4)] * (1 - glow) + np.array(col) * glow * 0.5


def desks(rng, a, box, col, n=5, chair=None):
    """rows of desks and chairs between the window and the back wall (dark shapes low in the view)"""
    bx0, by0, bx1, by1 = box
    for k in range(n):
        t = (k + 0.6) / (n + 0.4)
        y = (1 - t) * N * 1.02 + t * by1
        h = (1 - t) * N * 0.12 + t * (by1 - by0) * 0.12
        for c in range(3):
            u0, u1 = c / 3 + 0.04, (c + 1) / 3 - 0.06
            x0 = (1 - t) * (u0 * N) + t * (bx0 + u0 * (bx1 - bx0))
            x1 = (1 - t) * (u1 * N) + t * (bx0 + u1 * (bx1 - bx0))
            rect(a, x0, y - h, x1, y - h * 0.75, col)                       # desk top
            rect(a, x0 + 2, y - h * 0.75, x0 + 6 + h * 0.08, y, col)        # legs
            rect(a, x1 - 6 - h * 0.08, y - h * 0.75, x1 - 2, y, col)
            if chair is not None:
                cx = (x0 + x1) / 2 + rng.uniform(-0.1, 0.1) * (x1 - x0)
                rect(a, cx - h * 0.35, y - h * 1.25, cx + h * 0.35, y - h * 0.55, chair)


def curtain(rng, a, x0, x1, col, y0=0.0, y1=1.0, period=0.07, bunched=False, sheer=0.0):
    """a pleated curtain over [x0, x1] x [y0, y1] (fractions): soft vertical folds, a hem at the foot"""
    X0, X1, Y0, Y1 = int(x0 * N), int(x1 * N), int(y0 * N), int(y1 * N)
    w = X1 - X0
    if w <= 0:
        return
    x = np.arange(w)
    p = period * N * (0.45 if bunched else 1.0)
    ph = rng.uniform(0, 6.28)
    fold = np.sin(2 * np.pi * x / p + ph + 0.8 * np.sin(x / (p * 2.7)))
    shade = 0.84 + (0.24 if bunched else 0.14) * fold
    shade = shade[None, :, None] * np.linspace(0.97, 1.03, Y1 - Y0)[:, None, None]
    c = np.array(col, float)[None, None, :] * shade
    if sheer:
        c = c * (1 - sheer) + a[Y0:Y1, X0:X1] * sheer
    a[Y0:Y1, X0:X1] = c
    rect(a, X0, Y1 - 0.025 * N, X1, Y1, [v * 0.9 for v in col])              # hem
    rect(a, X0, Y0, X1, Y0 + 0.02 * N, [v * 0.6 for v in col])               # rail shadow


def blinds(rng, a, y0, y1, col, x0=0.0, x1=1.0, slat=0.05):
    """venetian blind lowered over [y0, y1]: light slats with dark gaps, the bottom rail heavier"""
    X0, X1, Y0, Y1 = int(x0 * N), int(x1 * N), int(y0 * N), int(y1 * N)
    p = slat * N
    y = np.arange(Y1 - Y0)
    ph = (y % p) / p
    tilt = rng.uniform(-0.01, 0.01) * N
    s = np.where(ph < 0.78, 0.88 + 0.16 * (1 - ph / 0.78), 0.45)              # slat lit from above, gap dark
    band = np.array(col, float)[None, None, :] * s[:, None, None]
    a[Y0:Y1, X0:X1] = band
    if tilt:
        a[Y0:Y1, X0:X1] = np.roll(a[Y0:Y1, X0:X1], int(tilt / 8), axis=0)
    rect(a, X0, Y1 - 0.02 * N, X1, Y1 + 0.012 * N, [v * 0.8 for v in col])    # bottom rail
    for xc in (0.25, 0.75):                                                   # ladder cords
        rect(a, (x0 + (x1 - x0) * xc) * N - 1, Y0, (x0 + (x1 - x0) * xc) * N + 1, Y1, [v * 0.7 for v in col])


def books(rng, a, x0, x1, y0, y1, shelves=5, dim=1.0):
    """a bookcase: dark boards, rows of spines of muted colours and heights"""
    rect(a, x0 * N, y0 * N, x1 * N, y1 * N, [46 * dim, 36 * dim, 28 * dim])
    sh = (y1 - y0) / shelves
    pal = [(120, 40, 34), (40, 60, 100), (150, 130, 90), (60, 80, 50), (170, 160, 140), (90, 50, 70), (30, 30, 34),
           (180, 150, 70), (110, 100, 90)]
    for k in range(shelves):
        top, bot = (y0 + k * sh) * N, (y0 + (k + 1) * sh) * N
        x = x0 * N + 4
        while x < x1 * N - 6:
            w = rng.uniform(0.012, 0.03) * N
            hh = (bot - top) * rng.uniform(0.6, 0.9)
            c = np.array(pal[rng.integers(len(pal))], float) * rng.uniform(0.6, 1.0) * dim
            if rng.random() < 0.08:
                w *= 2.5
                rect(a, x, bot - hh * 0.3, x + w, bot - 3, c)                # books lying flat
            else:
                rect(a, x, bot - hh, x + w, bot - 3, c)
                if rng.random() < 0.5:
                    rect(a, x, bot - hh * 0.75, x + w, bot - hh * 0.7, c * 1.25)   # a label band
            x += w + rng.uniform(0, 2)
        rect(a, x0 * N, bot - 4, x1 * N, bot, [70 * dim, 56 * dim, 42 * dim])     # the board


def papers(rng, a, n=3):
    """sheets taped low on the glass (a notice, a timetable), a small faded poster above them"""
    x, y = rng.uniform(0.5, 0.7) * N, 0.14 * N                                  # the poster, sun-faded
    rect(a, x, y, x + 0.22 * N, y + 0.3 * N, [150, 92, 78])
    rect(a, x + 0.02 * N, y + 0.04 * N, x + 0.2 * N, y + 0.14 * N, [200, 190, 170])
    for k in range(n):
        w = rng.uniform(0.13, 0.17) * N
        h = w * 1.41
        x = (0.08 + k * 0.3 + rng.uniform(0, 0.08)) * N
        y = rng.uniform(0.52, 0.62) * N
        c = [rng.uniform(190, 215), rng.uniform(186, 210), rng.uniform(170, 196)]
        if k == 1:
            c = [215, 200, 130]                                               # a yellow notice
        rect(a, x, y, x + w, y + h, c)
        for ln in range(int(rng.integers(5, 12))):
            yy = y + h * (0.12 + ln * 0.07)
            if yy > y + h * 0.9:
                break
            rect(a, x + w * 0.1, yy, x + w * rng.uniform(0.5, 0.9), yy + max(2, h * 0.015), [c[0] * 0.5, c[1] * 0.5, c[2] * 0.5])
        rect(a, x + w * 0.4, y - 3, x + w * 0.6, y + 5, [210, 210, 200])     # tape


def noise(rng, a, amt=4.0):
    a += rng.normal(0, amt, a.shape[:2])[..., None]
    return a


# ----------------------------------------------------------------------------- the cells
DARK_CEIL, DARK_WALL, DARK_FLOOR = (52, 54, 54), (40, 42, 41), (26, 25, 24)


def c_dark(rng):
    a, box = room(rng, DARK_CEIL, DARK_WALL, DARK_FLOOR)
    ceiling_lights(a, box, (70, 72, 72))
    desks(rng, a, box, (20, 19, 18), n=3)
    return a


def c_dark_office(rng):
    a, box = room(rng, (60, 60, 58), (46, 46, 44), (30, 28, 26), back=(50, 48, 44), bw=(0.3, 0.86))
    ceiling_lights(a, box, (80, 82, 82), rows=2, cols=1)
    books(rng, a, 0.32, 0.6, 0.3, 0.72, shelves=4, dim=0.45)                   # a bookcase on the back wall
    rect(a, 0.1 * N, 0.78 * N, 0.75 * N, 0.84 * N, (24, 22, 20))              # a desk under the window
    rect(a, 0.62 * N, 0.62 * N, 0.74 * N, 0.78 * N, (34, 34, 36))             # a monitor / file box
    return a


def c_curtain(rng, col, half=None, sheer=0.0):
    a = c_dark(rng)
    if half is None:
        curtain(rng, a, 0.0, 0.52, col, sheer=sheer)
        curtain(rng, a, 0.48, 1.0, col, sheer=sheer)
        rect(a, 0.495 * N, 0.04 * N, 0.505 * N, 0.97 * N, [v * 0.55 for v in col])   # the meeting edges
    elif half == 'left':
        curtain(rng, a, 0.0, 0.42, col, bunched=True)
    else:                                                                       # drawn to both sides
        curtain(rng, a, 0.0, 0.22, col, bunched=True)
        curtain(rng, a, 0.8, 1.0, col, bunched=True)
    return a


def c_blinds(rng, down=1.0):
    a = c_dark(rng)
    blinds(rng, a, 0.0, down, (200, 200, 192))
    return a


def c_lit_classroom(rng):
    a, box = room(rng, (232, 234, 228), (196, 198, 186), (150, 146, 132), back=(200, 200, 188))
    bx0, by0, bx1, by1 = box
    ceiling_lights(a, box, (255, 255, 250), rows=3, cols=2)
    rect(a, bx0 + 0.12 * (bx1 - bx0), by0 + 0.2 * (by1 - by0), bx1 - 0.12 * (bx1 - bx0), by0 + 0.62 * (by1 - by0), (46, 70, 56))   # chalkboard
    desks(rng, a, box, (120, 96, 70), n=4, chair=(70, 70, 76))
    return a


def c_bookshelf(rng):
    a = np.zeros((N, N, 3)) + np.array(DARK_WALL, float)
    books(rng, a, 0.0, 1.0, 0.04, 1.0, shelves=6, dim=0.8)
    a[: int(0.04 * N)] = (34, 30, 26)
    return a


def c_papers(rng):
    a = c_dark(rng)
    papers(rng, a)
    return a


def c_hall_dark(rng):
    a, box = room(rng, (44, 46, 46), (36, 38, 38), (40, 40, 38), hz=0.6, bw=(0.3, 0.7), bh=(0.3, 0.68))
    bx0, by0, bx1, by1 = box
    for u in (0.18, 0.82):                                                    # columns
        rect(a, u * N - 0.04 * N, 0.08 * N, u * N + 0.04 * N, N, (30, 31, 31))
    rect(a, bx0 + 8, by0 + 0.2 * (by1 - by0), bx1 - 8, by1, (24, 24, 24))      # a dark doorway at the back
    return a


def c_hall_lit(rng):
    a, box = room(rng, (220, 222, 216), (190, 186, 172), (176, 172, 160), hz=0.6, bw=(0.3, 0.7), bh=(0.3, 0.68))
    bx0, by0, bx1, by1 = box
    ceiling_lights(a, box, (255, 255, 248), rows=4, cols=3)
    for u in (0.16, 0.84):
        rect(a, u * N - 0.045 * N, 0.06 * N, u * N + 0.045 * N, N, (200, 196, 186))
    rect(a, bx0 + 0.15 * (bx1 - bx0), by0 + 0.25 * (by1 - by0), bx0 + 0.55 * (bx1 - bx0), by0 + 0.7 * (by1 - by0), (150, 110, 80))   # notice board
    for k in range(3):                                                        # people: body and head
        x, yb = rng.uniform(0.3, 0.7) * N, by1 + rng.uniform(0.08, 0.2) * N
        h = rng.uniform(0.2, 0.28) * N
        c = (rng.uniform(40, 90), rng.uniform(40, 70), rng.uniform(50, 90))
        rect(a, x - h * 0.11, yb - h * 0.82, x + h * 0.11, yb, c)
        poly(a, [(x + h * 0.07 * np.cos(t), yb - h * 0.9 + h * 0.08 * np.sin(t)) for t in np.linspace(0, 6.28, 12)], (40, 32, 28))
    # the polished floor reflects the lights
    fl = a[int(by1):].copy()
    a[int(by1):] = fl * 0.85 + fl[::-1][: N - int(by1)] * 0.15
    return a


def c_hall_stair(rng):
    a, box = room(rng, (50, 50, 48), (44, 44, 42), (34, 33, 32), hz=0.6, bw=(0.25, 0.75), bh=(0.25, 0.7))
    for k in range(10):                                                       # a flight rising to the left
        x0, y0 = (0.85 - k * 0.07) * N, (0.95 - k * 0.07) * N
        rect(a, x0 - 0.07 * N, y0 - 0.035 * N, x0 + 0.25 * N, y0, (62, 60, 56))
        rect(a, x0 - 0.07 * N, y0 - 0.008 * N, x0 + 0.25 * N, y0, (30, 30, 28))
    poly(a, [(0.95 * N, 0.62 * N), (0.25 * N, -0.08 * N), (0.25 * N, -0.04 * N), (0.95 * N, 0.66 * N)], (90, 90, 88))   # handrail
    return a


def c_corridor_lit(rng):
    a, box = room(rng, (215, 218, 212), (184, 186, 176), (150, 148, 138), hz=0.58, bw=(0.4, 0.6), bh=(0.36, 0.64))
    bx0, by0, bx1, by1 = box
    for k in range(6):                                                        # lights down the corridor
        t = 1 - 0.62 ** (k + 0.5)
        y = t * by0
        w = (1 - t) * 0.12 * N + t * 0.03 * N
        rect(a, N / 2 - w, y, N / 2 + w, y + (1 - t) * 0.03 * N + 2, (255, 255, 250))
    for k in range(4):                                                        # doors along the walls
        t0, t1 = 1 - 0.6 ** (k + 0.3), 1 - 0.6 ** (k + 0.7)
        for side in (0, 1):
            xa = (1 - t0) * (side * N) + t0 * (bx1 if side else bx0)
            xb = (1 - t1) * (side * N) + t1 * (bx1 if side else bx0)
            ya0, ya1 = (1 - t0) * 0.25 * N + t0 * (by0 + 0.1 * (by1 - by0)), (1 - t0) * N + t0 * by1
            yb0, yb1 = (1 - t1) * 0.25 * N + t1 * (by0 + 0.1 * (by1 - by0)), (1 - t1) * N + t1 * by1
            poly(a, [(xa, ya0), (xb, yb0), (xb, yb1), (xa, ya1)], (120, 92, 66))
    return a


def build():
    rng = np.random.default_rng(1997)
    cells = [
        c_dark(rng),                                       # 0  dark room
        c_dark_office(rng),                                # 1  dark office, bookcase on the back wall
        c_curtain(rng, (214, 212, 204)),                   # 2  white curtains drawn
        c_curtain(rng, (220, 218, 210), half='left'),      # 3  white curtain pulled to one side
        c_curtain(rng, (206, 184, 146)),                   # 4  beige curtains drawn
        c_curtain(rng, (200, 178, 140), half='both'),      # 5  beige curtains open to both sides
        c_blinds(rng, 1.0),                                # 6  venetian blind down
        c_blinds(rng, 0.55),                               # 7  blind half down
        c_lit_classroom(rng),                              # 8  LIT classroom: fluorescent tubes, chalkboard
        c_bookshelf(rng),                                  # 9  bookcase against the glass
        c_papers(rng),                                     # 10 papers taped on the glass
        c_curtain(rng, (176, 200, 176), half='both'),      # 11 pale green curtains (학생회관 2009 photo)
        c_hall_dark(rng),                                  # 12 dark lobby
        c_hall_lit(rng),                                   # 13 LIT lobby
        c_hall_stair(rng),                                 # 14 stair hall
        c_corridor_lit(rng),                               # 15 LIT corridor
    ]
    atlas = Image.new('RGB', (CELL * 4, CELL * 4))
    for i, a in enumerate(cells):
        a = noise(rng, a, 3.0)
        im = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.8))
        im = im.resize((CELL, CELL), Image.LANCZOS)
        atlas.paste(im, ((i % 4) * CELL, (i // 4) * CELL))
    atlas.save(OUT, quality=88, optimize=True)
    print('wrote', OUT, os.path.getsize(OUT) // 1024, 'KB')


if __name__ == '__main__':
    build()
