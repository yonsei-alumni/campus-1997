"""Procedurally paint foliage atlases, 1990s shop signs and the main-gate plaque.

Outputs (web/public/assets/textures):
  leaf_<species>[_<season>].png   2x2 atlas of leaf-cluster cards, RGBA (alpha-tested)
  litter_ginkgo.png               fallen ginkgo leaves, seamless tile, alpha = each leaf's rank
  sign_shops.png                  4x4 atlas of 1997 Sinchon storefront signboards
  sign_gate.png                   延世大學校 gate plaque
Run: .venv/bin/python tools/make_textures.py
"""
import math, os, random, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from scipy import ndimage

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
OUT = os.path.join(ROOT, 'web/public/assets/textures')
os.makedirs(OUT, exist_ok=True)
SS = 2                     # supersampling
ONLY = set(sys.argv[1:])     # optional: only rebuild these atlases, e.g. `make_textures.py azalea_red`
CELL = 512                 # final cell size, atlas = 2x2 cells


def jitter(c, rnd, amt=0.12):
    return tuple(int(max(0, min(255, v * (1 + rnd.uniform(-amt, amt)) + rnd.uniform(-8, 8)))) for v in c)


def rot(pts, a, cx, cy, s=1.0):
    ca, sa = math.cos(a), math.sin(a)
    return [(cx + (x * ca - y * sa) * s, cy + (x * sa + y * ca) * s) for x, y in pts]


# ---------------------------------------------------------------- leaf outlines (unit, stem at origin, tip toward -y)
def shape_ginkgo(rnd):
    pts = [(0, 0)]
    spread = math.radians(rnd.uniform(55, 75))
    r = 1.0
    for i in range(25):
        a = -math.pi / 2 - spread + 2 * spread * i / 24
        rr = r * (1 - 0.18 * math.exp(-((i - 12) / 1.6) ** 2))      # centre notch
        rr *= 1 + 0.03 * math.sin(i * 2.3)
        pts.append((rr * math.cos(a) * 0.95, rr * math.sin(a) * 0.95 - 0.35))
    return [(x, y) for x, y in pts], 0.35


def shape_ovate(rnd, serr=0.0, w=0.42, lo=1.0):
    pts = []
    n = 34
    for i in range(n + 1):
        t = i / n
        y = -t * lo
        x = w * math.sin(math.pi * t ** 0.85) * (1 - 0.15 * t)
        if serr and i % 2:
            x *= 1 + serr
        pts.append((x, y))
    return pts + [(-x, y) for x, y in reversed(pts)], 0.1


def shape_maple(rnd):
    pts = []
    lobes = [(-90, 1.0), (-35, 0.85), (20, 0.55), (160, 0.55), (215, 0.85)]
    n = 80
    for i in range(n):
        a = 2 * math.pi * i / n
        deg = math.degrees(a) - 270
        r = 0.25
        for c, L in [(-90, 1.0), (-145, 0.85), (-35, 0.85), (-190, 0.5), (10, 0.5)]:
            d = abs(((math.degrees(a) - 180) - c + 540) % 360 - 180)
            r = max(r, L * math.exp(-(d / 16) ** 2))
        pts.append((r * math.cos(a), r * math.sin(a) - 0.1))
    return pts, 0.15


def shape_oak(rnd):
    pts = []
    n = 40
    for i in range(n + 1):
        t = i / n
        x = 0.33 * math.sin(math.pi * t ** 0.9) * (1 + 0.28 * math.sin(t * math.pi * 9))
        pts.append((x, -t))
    return pts + [(-x, y) for x, y in reversed(pts)], 0.08


def shape_ivy(rnd):
    pts = []
    n = 60
    for i in range(n):
        a = 2 * math.pi * i / n
        r = 0.45
        for c, L in [(-90, 0.95), (-150, 0.7), (-30, 0.7), (-200, 0.5), (20, 0.5)]:
            d = abs(((math.degrees(a)) - c + 540) % 360 - 180)
            r = max(r, L * math.exp(-(d / 28) ** 2))
        pts.append((r * math.cos(a), r * math.sin(a) - 0.05))
    return pts, 0.1


def draw_leaf(d, shape, cx, cy, ang, size, col, rnd, vein=True):
    pts, stem = shape
    P = rot(pts, ang, cx, cy, size)
    base = jitter(col, rnd)
    d.polygon(P, fill=base + (255,))
    # light/dark half for a fake midrib fold
    half = [p for p in pts if p[0] >= 0] + [(0, pts[0][1])]
    if len(half) > 3:
        d.polygon(rot(half, ang, cx, cy, size), fill=tuple(int(v * 0.86) for v in base) + (255,))
    if vein:
        tip = min(pts, key=lambda p: p[1])
        a0 = rot([(0, 0)], ang, cx, cy, size)[0]
        a1 = rot([(0, tip[1] * 0.85)], ang, cx, cy, size)[0]
        d.line([a0, a1], fill=tuple(min(255, int(v * 1.15)) for v in base) + (255,), width=max(1, int(size * 0.04)))
    s0 = rot([(0, 0)], ang, cx, cy, size)[0]
    s1 = rot([(0, stem)], ang, cx, cy, size)[0]
    d.line([s0, s1], fill=(70, 60, 30, 255), width=max(1, int(size * 0.05)))


def finish(img):
    """downsample, dilate colour into transparent texels (no dark mip fringes)."""
    img = img.resize((img.width // SS, img.height // SS), Image.LANCZOS)
    a = np.array(img).astype(np.float32)
    alpha = a[..., 3] > 30
    rgb = a[..., :3]
    idx = ndimage.distance_transform_edt(~alpha, return_distances=False, return_indices=True)
    rgb = rgb[idx[0], idx[1]]
    out = np.concatenate([rgb, a[..., 3:4]], -1)
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8), 'RGBA')


def cluster_cell(kind, palette, rnd, flowers=None):
    S = CELL * SS
    img = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    cx, cy = S / 2, S / 2
    # twigs
    twig_col = (85, 70, 50, 255)
    tips = []
    for k in range(rnd.randint(4, 6)):
        a = rnd.uniform(0, 2 * math.pi)
        L = rnd.uniform(0.25, 0.45) * S
        x0, y0 = cx + rnd.uniform(-0.05, 0.05) * S, S * 0.97
        x1, y1 = cx + math.cos(a) * L * 0.8, cy + math.sin(a) * L * 0.7
        d.line([(x0, y0), (x1, y1)], fill=twig_col, width=int(S * 0.008))
        tips.append((x0, y0, x1, y1))
    if kind == 'ivy_bare':
        return ivy_bare_cell(palette, rnd)
    if kind == 'pine':
        for (x0, y0, x1, y1) in tips * 3:
            for t in np.linspace(0.3, 1.0, 9):
                px, py = x0 + (x1 - x0) * t, y0 + (y1 - y0) * t
                for k in range(26):
                    a = rnd.uniform(0, 2 * math.pi)
                    L = rnd.uniform(0.05, 0.11) * S
                    c = jitter(palette[rnd.randrange(len(palette))], rnd, 0.15)
                    d.line([(px, py), (px + math.cos(a) * L, py + math.sin(a) * L * 0.8)], fill=c + (255,), width=int(S * 0.004) + 1)
        return finish(img)
    shapes = {'ginkgo': shape_ginkgo, 'zelkova': lambda r: shape_ovate(r, 0.08, 0.36), 'cherry': lambda r: shape_ovate(r, 0.05, 0.4),
              'maple': shape_maple, 'oak': shape_oak, 'ivy': shape_ivy, 'boxwood': lambda r: shape_ovate(r, 0.0, 0.55, 0.9),
              'azalea': lambda r: shape_ovate(r, 0.0, 0.33)}
    size_rng = {'ginkgo': (0.055, 0.075), 'zelkova': (0.05, 0.075), 'cherry': (0.06, 0.085), 'maple': (0.06, 0.085),
                'oak': (0.07, 0.095), 'ivy': (0.06, 0.09), 'boxwood': (0.022, 0.03), 'azalea': (0.04, 0.055)}[kind]
    n = {'boxwood': 1500, 'azalea': 420, 'ivy': 330}.get(kind, 230)
    for k in range(n):
        # leaves concentrate in an ellipse (cluster), denser in the middle; ivy: a flatter mat filling the card
        r = (rnd.random() ** (0.45 if kind == 'ivy' else 0.6)) * (0.47 if kind == 'ivy' else 0.45)
        a = rnd.uniform(0, 2 * math.pi)
        x = cx + math.cos(a) * r * S
        y = cy + math.sin(a) * r * S * 0.9
        if kind in ('boxwood',):
            x = rnd.uniform(0.02, 0.98) * S
            y = rnd.uniform(0.02, 0.98) * S
        elif kind == 'ivy':           # a square mat of leaves: overlapping cards close up into a continuous cover
            x = rnd.uniform(0.07, 0.93) * S
            y = rnd.uniform(0.07, 0.93) * S
        ang = math.atan2(y - cy, x - cx) + math.pi / 2 + rnd.uniform(-0.8, 0.8)
        # top of cluster brighter (sky light), bottom darker
        shade = 1.08 - 0.3 * ((y / S) - 0.2)
        col = palette[rnd.randrange(len(palette))]
        col = tuple(int(min(255, c * shade)) for c in col)
        draw_leaf(d, shapes[kind](rnd), x, y, ang, rnd.uniform(*size_rng) * S, col, rnd, vein=kind not in ('boxwood',))
    if flowers:
        fcol, fn, fs = flowers
        for k in range(fn):
            r = (rnd.random() ** 0.5) * 0.46
            a = rnd.uniform(0, 2 * math.pi)
            x = cx + math.cos(a) * r * S
            y = cy + math.sin(a) * r * S * 0.9
            sz = rnd.uniform(*fs) * S
            c = jitter(fcol, rnd, 0.06)
            for p in range(5):
                pa = p * 2 * math.pi / 5 + rnd.uniform(0, 1)
                px, py = x + math.cos(pa) * sz * 0.55, y + math.sin(pa) * sz * 0.55
                d.ellipse([px - sz * 0.45, py - sz * 0.45, px + sz * 0.45, py + sz * 0.45], fill=c + (255,))
            d.ellipse([x - sz * 0.18, y - sz * 0.18, x + sz * 0.18, y + sz * 0.18], fill=(230, 200, 90, 255))
    return finish(img)


def ivy_bare_cell(palette, rnd):
    """담쟁이 in mid-April: a web of brown woody vines stuck to the wall, with the first small leaves
    (bronze-red and yellow-green) just opening at the nodes."""
    S = CELL * SS
    img = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    nodes = []
    for k in range(rnd.randint(5, 7)):
        # a vine wanders up across the card, forking now and then
        x, y = rnd.uniform(0.1, 0.9) * S, S * rnd.uniform(0.85, 1.0)
        a = -math.pi / 2 + rnd.uniform(-0.6, 0.6)
        w = S * rnd.uniform(0.010, 0.016)
        for step in range(rnd.randint(14, 22)):
            a += rnd.uniform(-0.45, 0.45)
            a = -math.pi / 2 + max(-1.1, min(1.1, a + math.pi / 2))
            L = S * rnd.uniform(0.03, 0.055)
            nx, ny = x + math.cos(a) * L, y + math.sin(a) * L
            c = jitter((92, 70, 50), rnd, 0.15)
            d.line([(x, y), (nx, ny)], fill=c + (255,), width=max(2, int(w)))
            if rnd.random() < 0.35:                     # side shoot
                b = a + rnd.choice((-1, 1)) * rnd.uniform(0.7, 1.3)
                L2 = S * rnd.uniform(0.04, 0.09)
                d.line([(x, y), (x + math.cos(b) * L2, y + math.sin(b) * L2)], fill=c + (255,), width=max(2, int(w * 0.6)))
                nodes.append((x + math.cos(b) * L2, y + math.sin(b) * L2))
            nodes.append((nx, ny))
            x, y = nx, ny
            w *= 0.97
            if not (0 <= x <= S and 0 <= y <= S):
                break
    for (x, y) in nodes:
        if rnd.random() < 0.45:
            continue
        col = palette[rnd.randrange(len(palette))]
        for m in range(rnd.randint(1, 3)):
            draw_leaf(d, shape_ivy(rnd), x + rnd.uniform(-8, 8), y + rnd.uniform(-8, 8), rnd.uniform(0, 6.28),
                      rnd.uniform(0.022, 0.042) * S, col, rnd, vein=False)
    return finish(img)


def atlas(name, kind, palette, flowers=None, seed=0):
    if ONLY and name not in ONLY:
        return
    rnd = random.Random(hash(name) & 0xffff ^ seed)
    out = Image.new('RGBA', (CELL * 2, CELL * 2))
    for i in range(4):
        out.paste(cluster_cell(kind, palette, rnd, flowers), ((i % 2) * CELL, (i // 2) * CELL))
    out.save(os.path.join(OUT, f'leaf_{name}.png'), optimize=True)
    print('leaf', name)


G = [(78, 118, 40), (95, 135, 45), (62, 100, 34), (110, 150, 55)]
atlas('ginkgo', 'ginkgo', [(120, 160, 50), (100, 145, 45), (140, 175, 60), (90, 130, 40)])
atlas('ginkgo_autumn', 'ginkgo', [(240, 200, 40), (230, 185, 30), (250, 215, 70), (215, 170, 30), (200, 180, 50)])
atlas('ginkgo_spring', 'ginkgo', [(150, 190, 70), (135, 180, 60), (165, 200, 85)])
atlas('zelkova', 'zelkova', G)
atlas('zelkova_autumn', 'zelkova', [(190, 110, 40), (170, 90, 35), (200, 140, 50), (150, 110, 40)])
atlas('zelkova_spring', 'zelkova', [(120, 165, 60), (105, 150, 50), (135, 175, 70)])
atlas('cherry', 'cherry', [(70, 110, 38), (85, 122, 42), (60, 95, 32)])
atlas('cherry_spring', 'cherry', [(110, 150, 60), (95, 140, 55)], flowers=((250, 215, 225), 260, (0.035, 0.05)))
atlas('cherry_autumn', 'cherry', [(190, 80, 40), (210, 110, 40), (160, 70, 40)])
atlas('maple', 'maple', [(85, 130, 40), (100, 145, 45), (70, 115, 35)])
atlas('maple_autumn', 'maple', [(200, 40, 25), (220, 70, 30), (180, 30, 25), (230, 110, 30)])
atlas('maple_spring', 'maple', [(130, 165, 60), (150, 120, 70)])
atlas('oak', 'oak', [(70, 105, 38), (82, 118, 42), (60, 92, 32)])
atlas('oak_autumn', 'oak', [(150, 110, 50), (130, 90, 40), (165, 125, 55)])
atlas('oak_spring', 'oak', [(105, 150, 55), (95, 140, 50)])
atlas('pine', 'pine', [(40, 75, 35), (50, 88, 40), (34, 64, 30), (60, 95, 45)])
# 담쟁이 (Boston ivy) on the stone halls: fresh glossy green in late May (underwood_2023.jpg), crimson / orange /
# wine in late October with a few leaves still green-yellow, bare vines with the first leaves in mid-April
atlas('ivy', 'ivy', [(54, 98, 30), (70, 116, 36), (44, 82, 26), (86, 130, 42)])
atlas('ivy_autumn', 'ivy', [(165, 34, 30), (190, 58, 32), (128, 28, 40), (205, 96, 38), (150, 100, 40), (110, 30, 45)])
atlas('ivy_spring', 'ivy_bare', [(150, 72, 48), (170, 96, 52), (128, 150, 58), (112, 136, 50)])
atlas('boxwood', 'boxwood', [(45, 82, 32), (55, 95, 36), (38, 70, 28)])
atlas('azalea', 'azalea', [(55, 90, 35), (65, 100, 40)], flowers=((225, 60, 150), 380, (0.045, 0.06)))
atlas('azalea_summer', 'azalea', [(55, 90, 35), (65, 100, 40)])
atlas('azalea_red', 'azalea', [(50, 85, 32), (60, 95, 38)], flowers=((200, 32, 48), 300, (0.04, 0.055)))


# Fallen ginkgo leaves (issue #18): a seamless tile of the autumn atlas's leaves lying flat on the ground (0.8 m of
# ground per tile in web/src/litter.js).  Its alpha is each leaf's rank, not its coverage: the shader shows the leaves
# whose rank clears the carpet's thinness there, so a few strewn leaves and a full carpet come from the one tile.
# Higher ranks lie on top, so a thin strew is whole leaves.
def litter(name, kind, palette, n, size, seed=0):
    if ONLY and name not in ONLY:
        return
    rnd = random.Random(seed)
    S = CELL * SS
    img = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    rank = Image.new('L', (S, S), 0)
    d, dk = ImageDraw.Draw(img), ImageDraw.Draw(rank)
    shape_fn = {'ginkgo': shape_ginkgo}[kind]
    leaves = sorted((rnd.uniform(0.14, 1.0), rnd.uniform(0, S), rnd.uniform(0, S), rnd.uniform(0, 2 * math.pi),
                     rnd.uniform(*size) * S, rnd.choice(palette), rnd.random()) for _ in range(n))
    for r, x, y, a, sz, col, sd in leaves:
        shape = shape_fn(random.Random(sd))
        pts, stem = shape
        for ox in (-S, 0, S):                   # wrap round the edges: the tile repeats seamlessly
            for oy in (-S, 0, S):
                cx, cy = x + ox, y + oy
                if not (-2 * sz < cx < S + 2 * sz and -2 * sz < cy < S + 2 * sz):
                    continue
                draw_leaf(d, shape, cx, cy, a, sz, col, random.Random(sd))     # (same colour on every copy)
                dk.polygon(rot(pts, a, cx, cy, sz), fill=int(r * 255))
                dk.line([rot([(0, 0)], a, cx, cy, sz)[0], rot([(0, stem)], a, cx, cy, sz)[0]], fill=int(r * 255),
                        width=max(1, int(sz * 0.05)))
    img.putalpha(rank)
    out = finish(img)
    out.save(os.path.join(OUT, f'{name}.png'), optimize=True)
    print('litter', name, 'cover %.2f' % (np.array(out)[..., 3] > 30).mean())


litter('litter_ginkgo', 'ginkgo', [(240, 200, 40), (230, 185, 30), (250, 215, 70), (215, 170, 30), (200, 180, 50),
                                   (236, 196, 52), (190, 150, 40), (175, 130, 45)], 1500, (0.036, 0.052), seed=18)

if ONLY:
    raise SystemExit(0)

# ---------------------------------------------------------------- signs
FONT_B = '/usr/share/fonts/opentype/noto/NotoSansCJK-Black.ttc'
FONT_S = '/usr/share/fonts/opentype/noto/NotoSerifCJK-Bold.ttc'


def font(path, size, idx=1):
    for i in (idx, 0, 1, 2, 3):
        try:
            return ImageFont.truetype(path, size, index=i)
        except Exception:
            continue
    return ImageFont.load_default()

SIGNS = [('독수리다방', (180, 30, 30), (255, 240, 200)), ('연세문구', (20, 60, 150), (255, 255, 255)),
         ('서점', (30, 110, 60), (255, 255, 230)), ('만화방', (250, 200, 30), (40, 30, 20)),
         ('복사·제본', (255, 255, 255), (30, 60, 160)), ('호프 · 생맥주', (120, 30, 20), (255, 220, 120)),
         ('당구장', (20, 20, 20), (255, 80, 60)), ('분식 떡볶이', (230, 90, 30), (255, 255, 255)),
         ('레코드 · 테이프', (60, 20, 100), (255, 230, 120)), ('삐삐 · 시티폰', (0, 120, 170), (255, 255, 255)),
         ('하숙 · 자취방', (255, 250, 240), (150, 30, 30)), ('노래방', (200, 20, 120), (255, 255, 120)),
         ('통닭 · 맥주', (200, 120, 20), (255, 255, 255)), ('안경원', (30, 30, 90), (220, 220, 255)),
         ('약국', (40, 130, 60), (255, 255, 255)), ('비디오 대여', (20, 20, 20), (90, 220, 255))]
S = 1024
img = Image.new('RGB', (S, S), (200, 200, 200))
d = ImageDraw.Draw(img)
for i, (txt, bg, fg) in enumerate(SIGNS):          # 2 columns x 8 rows, each sign 512x128 (4:1)
    x0, y0 = (i % 2) * 512, (i // 2) * 128
    d.rectangle([x0, y0, x0 + 511, y0 + 127], fill=bg)
    d.rectangle([x0 + 6, y0 + 6, x0 + 505, y0 + 121], outline=tuple(int(c * 0.75) for c in fg), width=4)
    size = 96
    while True:
        f = font(FONT_B, size)
        w = d.textlength(txt, font=f)
        if w < 440 or size < 30:
            break
        size -= 4
    d.text((x0 + 256 - w / 2, y0 + 64), txt, font=f, fill=fg, anchor='lm')
img.save(os.path.join(OUT, 'sign_shops.png'), optimize=True)

# gate plaque: carved granite with gilded hanja + hangul
W, H = 1024, 256
img = Image.new('RGB', (W, H), (175, 172, 165))
noise = (np.random.RandomState(3).rand(H, W) * 30 - 15)
arr = np.array(img).astype(np.float32) + noise[..., None]
img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
d = ImageDraw.Draw(img)
f = font(FONT_S, 150, 1)
txt = '延世大學校'
w = d.textlength(txt, font=f)
d.text((W / 2 - w / 2 + 3, H / 2 + 3), txt, font=f, fill=(70, 66, 60), anchor='lm')
d.text((W / 2 - w / 2, H / 2), txt, font=f, fill=(40, 38, 34), anchor='lm')
img.save(os.path.join(OUT, 'sign_gate.png'))
print('signs ok')


# ---------------------------------------------------------------- pre-2004 Korean licence plates + taxi sign
# 2x2 atlas (512x256 each): [0] green private, [1] green private, [2] yellow commercial (taxi), [3] taxi roof sign
PW, PH = 512, 256
img = Image.new('RGB', (PW * 2, PH * 2), (0, 0, 0))
d = ImageDraw.Draw(img)
plates = [((38, 104, 64), (245, 245, 240), '서울 33', '가 1997'), ((38, 104, 64), (245, 245, 240), '서울 52', '러 4821'),
          ((236, 196, 40), (30, 40, 90), '서울 31', '바 2380')]
for i, (bg, fg, top, bottom) in enumerate(plates):
    x0, y0 = (i % 2) * PW, (i // 2) * PH
    d.rectangle([x0, y0, x0 + PW - 1, y0 + PH - 1], fill=bg)
    d.rectangle([x0 + 8, y0 + 8, x0 + PW - 9, y0 + PH - 9], outline=fg, width=6)
    f1, f2 = font(FONT_B, 72), font(FONT_B, 132)
    w1 = d.textlength(top, font=f1)
    d.text((x0 + PW / 2 - w1 / 2, y0 + 62), top, font=f1, fill=fg, anchor='lm')
    w2 = d.textlength(bottom, font=f2)
    d.text((x0 + PW / 2 - w2 / 2, y0 + 172), bottom, font=f2, fill=fg, anchor='lm')
    for bx in (40, PW - 40):
        d.ellipse([x0 + bx - 9, y0 + 30, x0 + bx + 9, y0 + 48], fill=tuple(int(c * 0.7) for c in fg))
x0, y0 = PW, PH                              # taxi roof sign
d.rectangle([x0, y0, x0 + PW - 1, y0 + PH - 1], fill=(255, 196, 30))
d.rectangle([x0 + 10, y0 + 10, x0 + PW - 11, y0 + PH - 11], outline=(40, 40, 40), width=8)
f = font(FONT_B, 150)
w = d.textlength('개인', font=f)
d.text((x0 + PW / 2 - w / 2, y0 + PH / 2 + 4), '개인', font=f, fill=(25, 25, 25), anchor='lm')
img.save(os.path.join(OUT, 'plates.png'), optimize=True)

print('plates ok')
