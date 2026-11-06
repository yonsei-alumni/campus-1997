"""Street furniture, statues, the main gate, 1990s Korean cars and pedestrians."""
import math, random
from mathutils import Vector, Matrix
from common import MeshBuilder
from landmarks import arch_fill


# ----------------------------------------------------------------------------- 쌍등 가로등 (double-globe lamp, 1997 library photo)
def lamp_double():
    mb = MeshBuilder('lamp_double')
    mb.box((0, 0, 0.25), (0.5, 0.5, 0.5), 'metal_dark')
    mb.cylinder((0, 0), 0.12, 0.5, 4.2, 'metal_dark', seg=10, r1=0.07)
    mb.cylinder((0, 0), 0.16, 0.5, 1.0, 'metal_dark', seg=10, r1=0.12)
    for s in (-1, 1):
        pts = [Vector((0, 0, 3.9)), Vector((s * 0.35, 0, 4.15)), Vector((s * 0.6, 0, 4.05))]
        for i in range(2):
            a, b = pts[i], pts[i + 1]
            d = (b - a)
            c = (a + b) / 2
            mb.box(tuple(c), (d.length, 0.06, 0.06), 'metal_dark', rotz=0)
        mb.cylinder((s * 0.6, 0), 0.05, 4.0, 4.12, 'metal_dark', seg=8)
        mb.sphere((s * 0.6, 0, 4.36), 0.25, 'globe', seg=14, rings=10)
    mb.cylinder((0, 0), 0.05, 4.2, 4.45, 'metal_dark', seg=8)
    mb.sphere((0, 0, 4.48), 0.07, 'metal_dark', seg=8, rings=6)
    return mb


# ----------------------------------------------------------------------------- 백양로 양팔 가로등 (1997 aerial photo)
def lamp_arm():
    """Two-armed street lamp with flat box luminaires.  Local +X points away from the road (over the sidewalk),
    -X over the carriageway."""
    mb = MeshBuilder('lamp_arm')
    mb.box((0, 0, 0.3), (0.42, 0.42, 0.6), 'metal_dark')
    mb.cylinder((0, 0), 0.11, 0.6, 7.6, 'metal_dark', seg=10, r1=0.065)
    for sx, L_ in ((-1, 1.7), (1, 1.05)):
        # slightly rising arm, then the luminaire box hanging from its tip
        p0, p1 = Vector((0, 0, 7.25)), Vector((sx * L_, 0, 7.55))
        c = (p0 + p1) / 2
        d = p1 - p0
        mb.box(tuple(c), (d.length, 0.07, 0.07), 'metal_dark')
        mb.box((sx * (L_ + 0.25), 0, 7.5), (0.75, 0.32, 0.16), 'lamp_housing')
        mb.box((sx * (L_ + 0.25), 0, 7.41), (0.6, 0.24, 0.02), 'globe')
    mb.cylinder((0, 0), 0.05, 7.6, 7.8, 'metal_dark', seg=8)
    return mb


# ----------------------------------------------------------------------------- 흰 세로 깃발 (sidewalk flags near the gate)
def flag_white():
    """A white cloth hung from a slim pole by the hedge, as the three on the west side of 백양로 north-east of the
    화단섬 in the 1997 aerial photo (reference/1997_백양로_항공사진.jpg, x 740 - 795, y 928 - 1033): about 1 m wide and
    2.3 m long, its foot a metre off the ground, the cloth stirring in the breeze (a few soft vertical folds)."""
    mb = MeshBuilder('flag_white')
    mb.cylinder((0, 0), 0.035, 0.0, 3.5, 'metal_dark', seg=8)
    mb.box((-0.55, 0, 3.32), (1.1, 0.035, 0.035), 'metal_dark')
    n = 8
    for k in range(n):
        u0, u1 = k / n, (k + 1) / n
        x0, x1 = -0.08 - 1.0 * u0, -0.08 - 1.0 * u1
        y0, y1 = 0.09 * math.sin(u0 * 2 * math.pi * 1.5), 0.09 * math.sin(u1 * 2 * math.pi * 1.5)
        mb.face([(x0, y0, 1.0 - 0.06 * u0), (x1, y1, 1.0 - 0.06 * u1), (x1, y1 * 0.4, 3.3), (x0, y0 * 0.4, 3.3)], 'flag_cloth',
                uvs=[(u0, 0), (u1, 0), (u1, 1), (u0, 1)])
    return mb


# ----------------------------------------------------------------------------- 공중전화 부스
def payphone_booth():
    """공중전화 부스 as on a 1990s campus: 95 x 95 cm, 2.2 m high, a grey steel frame with clear panels on three sides,
    an open front, a lit sign on the roof and a shelf under the phone (the phone itself, Poly Haven's Korean payphone,
    is added in build.py).  The front faces -Y."""
    mb = MeshBuilder('payphone_booth')
    w = d = 0.95
    h = 2.2
    mb.box((0, 0, 0.04), (w + 0.1, d + 0.1, 0.08), 'concrete')                         # base slab
    for sx in (-1, 1):
        for sy in (-1, 1):
            mb.box((sx * (w / 2 - 0.03), sy * (d / 2 - 0.03), h / 2), (0.06, 0.06, h), 'frame_silver')
    for sx in (-1, 1):                                                                 # clear side panels, mid rail
        mb.box((sx * (w / 2 - 0.03), 0, 1.2), (0.03, d - 0.1, 1.9), 'glass')
        mb.box((sx * (w / 2 - 0.03), 0, 1.0), (0.05, d - 0.06, 0.05), 'frame_silver')
    mb.box((0, d / 2 - 0.03, 1.2), (w - 0.1, 0.03, 1.9), 'glass')                      # back panel: lower half solid
    mb.box((0, d / 2 - 0.03, 0.55), (w - 0.06, 0.05, 0.9), 'plastic_grey')
    mb.box((0, -d / 2 + 0.03, 2.05), (w - 0.06, 0.06, 0.2), 'frame_silver')            # front head rail
    mb.box((0, 0, h + 0.05), (w + 0.12, d + 0.12, 0.1), 'frame_silver')                # roof
    mb.box((0, -d / 2 - 0.02, h + 0.27), (w * 0.9, 0.12, 0.34), 'light_white')         # lit sign
    mb.box((0, -d / 2 - 0.09, h + 0.27), (w * 0.9 - 0.12, 0.02, 0.2), 'sign_blue')
    mb.box((0, d / 2 - 0.2, 0.86), (0.5, 0.3, 0.04), 'metal')                          # shelf under the phone
    return mb


# ----------------------------------------------------------------------------- 원형 화분 (white round planters at the gate)
def planter():
    mb = MeshBuilder('planter')
    mb.cylinder((0, 0), 0.42, 0.0, 0.12, 'plaster_white', seg=18, r1=0.46, cap_top=False)
    mb.cylinder((0, 0), 0.46, 0.12, 0.55, 'plaster_white', seg=18, r1=0.5, cap_top=False)
    mb.cylinder((0, 0), 0.43, 0.5, 0.52, 'soil', seg=18)
    mb.sphere((0, 0, 0.75), 0.36, 'shrub_green', seg=10, rings=7, sz=0.8)
    return mb


# ----------------------------------------------------------------------------- 자연석 표지석
def stone_marker():
    import random as _r
    rnd = _r.Random(7)
    mb = MeshBuilder('stone_marker')
    seg, rings = 14, 9
    rad = [[1 + rnd.uniform(-0.08, 0.08) for i in range(seg)] for j in range(rings + 1)]
    P = []
    for j in range(rings + 1):
        th = math.pi * j / rings
        row = []
        for i in range(seg):
            ph = 2 * math.pi * i / seg
            r = rad[j][i] * (0.85 + 0.15 * math.cos(ph * 2))
            z = 1.15 * math.cos(th)
            row.append((0.85 * r * math.sin(th) * math.cos(ph), 0.45 * r * math.sin(th) * math.sin(ph), 1.1 + z * (1.0 if z > 0 else 0.95)))
        P.append(row)
    for j in range(rings):
        for i in range(seg):
            k = (i + 1) % seg
            mb.face([P[j][i], P[j + 1][i], P[j + 1][k], P[j][k]], 'stone_marker', smooth='rock')
    mb.box((0, 0, 0.08), (2.0, 1.2, 0.16), 'stone_granite')
    return mb


# ----------------------------------------------------------------------------- 안내판 (campus guide sign)
def sign_board():
    mb = MeshBuilder('sign_board')
    for x in (-0.85, 0.85):
        mb.box((x, 0, 1.0), (0.08, 0.08, 2.0), 'metal_dark')
    mb.box((0, 0, 1.55), (1.9, 0.08, 1.0), 'metal_dark')
    mb.face([(-0.9, -0.045, 1.08), (0.9, -0.045, 1.08), (0.9, -0.045, 2.02), (-0.9, -0.045, 2.02)], 'sign_blue')
    mb.face([(0.9, 0.045, 1.08), (-0.9, 0.045, 1.08), (-0.9, 0.045, 2.02), (0.9, 0.045, 2.02)], 'sign_blue')
    return mb


# ----------------------------------------------------------------------------- 정문
def gate():
    mb = MeshBuilder('gate')
    # main pillars either side of the carriageway, pedestrian pillars further out
    for sx in (-1, 1):
        for (x, w, h) in ((10.3, 1.9, 4.6), (16.8, 1.3, 3.2)):
            cx = sx * x
            mb.box((cx, 0, h / 2 - 0.5), (w, w, h + 1.0), 'stone_granite', mats={'top': 'stone_trim'})
            mb.box((cx, 0, h + 0.62), (w + 0.35, w + 0.35, 0.25), 'stone_trim')
            mb.box((cx, 0, h + 0.9), (w * 0.7, w * 0.7, 0.3), 'stone_trim')
        # low stone walls outwards
        mb.box((sx * 24.5, 0.0, 0.3), (14.0, 0.6, 1.6), 'stone_granite', mats={'top': 'stone_trim'})
    # plaque on the west main pillar (faces south = local -y)
    mb.face([(-11.15, -0.97, 3.2), (-9.45, -0.97, 3.2), (-9.45, -0.97, 3.62), (-11.15, -0.97, 3.62)], 'sign_gate',
            uvs=[(0, 0), (1, 0), (1, 1), (0, 1)])
    # guard booth (수위실)
    bx, by = 20.5, 3.5
    mb.box((bx, by, 1.3), (3.0, 2.6, 2.6), 'plaster_white')
    mb.box((bx, by, 2.75), (3.6, 3.2, 0.3), 'concrete')
    mb.face([(bx - 1.0, by - 1.31, 1.0), (bx + 1.0, by - 1.31, 1.0), (bx + 1.0, by - 1.31, 2.2), (bx - 1.0, by - 1.31, 2.2)], 'glass')
    return mb


def fix_gate_uv(mb):
    pass


# ----------------------------------------------------------------------------- 독수리상
def eagle_statue():
    mb = MeshBuilder('eagle_statue')
    mb.box((0, 0, 0.3), (5.0, 5.0, 1.0), 'stone_granite', mats={'top': 'stone_trim'})
    mb.box((0, 0, 1.2), (3.0, 3.0, 0.8), 'stone_granite', mats={'top': 'stone_trim'})
    mb.cylinder((0, 0), 0.75, 1.6, 12.0, 'stone_trim', seg=24, r1=0.62)
    mb.cylinder((0, 0), 0.95, 12.0, 12.5, 'stone_trim', seg=24)
    mb.cylinder((0, 0), 0.6, 12.5, 12.9, 'bronze', seg=16, r1=0.45)
    z = 13.0
    # body
    mb.sphere((0, 0.1, z + 1.0), 0.55, 'bronze', seg=14, rings=10, sz=1.7)
    mb.sphere((0, -0.35, z + 2.05), 0.33, 'bronze', seg=12, rings=8)            # head
    mb.face([(-0.1, -0.6, z + 2.1), (0.1, -0.6, z + 2.1), (0, -0.95, z + 1.9)], 'bronze')   # beak
    mb.face([(0.1, -0.6, z + 2.1), (0, -0.6, z + 1.95), (0, -0.95, z + 1.9)], 'bronze')
    mb.face([(0, -0.6, z + 1.95), (-0.1, -0.6, z + 2.1), (0, -0.95, z + 1.9)], 'bronze')
    # talons / legs
    for sx in (-0.25, 0.25):
        mb.cylinder((sx, 0.0), 0.11, z - 0.1, z + 0.6, 'bronze', seg=8)
    # tail fan
    for k in range(7):
        a = math.radians(-30 + k * 10)
        mb.face([(0, 0.55, z + 0.4), (math.sin(a) * 0.35, 0.55 + 1.3 * math.cos(a), z - 0.2),
                 (math.sin(a + 0.15) * 0.45, 0.55 + 1.35 * math.cos(a + 0.15), z - 0.18)], 'bronze')
    # wings raised in a V, primaries spread like fingers
    for s in (-1, 1):
        root = Vector((s * 0.35, 0.05, z + 1.5))
        span = 3.2
        prev_top = prev_bot = None
        nseg = 6
        for i in range(nseg + 1):
            t = i / nseg
            x = s * (0.35 + span * t)
            zt = z + 1.6 + 1.9 * t + 0.4 * math.sin(t * math.pi)
            chord = 1.25 * (1 - 0.45 * t)
            top = Vector((x, -0.3 + 0.2 * t, zt))
            bot = Vector((x, -0.3 + 0.2 * t + chord * 0.15, zt - chord))
            if prev_top is not None:
                q = [prev_top, top, bot, prev_bot] if s > 0 else [prev_bot, bot, top, prev_top]
                mb.face(q, 'bronze', smooth='wing%d' % s)
                q2 = [prev_bot, bot, top, prev_top] if s > 0 else [prev_top, top, bot, prev_bot]
                mb.face([p + Vector((0, 0.08, 0)) for p in q2], 'bronze', smooth='wingb%d' % s)
            prev_top, prev_bot = top, bot
        # primaries
        tip = prev_top
        for f in range(5):
            a = math.radians(-10 - f * 14)
            d = Vector((s * math.cos(a), 0, math.sin(a)))
            base = tip + Vector((0, 0.05 * f, -0.18 * f))
            q = [base, base + d * 1.1 + Vector((0, 0, 0.08)), base + d * 1.15, base + Vector((0, 0, -0.16))]
            mb.face(q if s > 0 else q[::-1], 'bronze')
            mb.face(q[::-1] if s > 0 else q, 'bronze')
        # wing-to-body skin
        mb.face([root, Vector((s * 0.35, -0.3, z + 1.6)), Vector((s * 0.35, -0.12, z + 0.35))] if s > 0 else
                [Vector((s * 0.35, -0.12, z + 0.35)), Vector((s * 0.35, -0.3, z + 1.6)), root], 'bronze')
    return mb


# ----------------------------------------------------------------------------- 언더우드 동상
def underwood_statue():
    mb = MeshBuilder('underwood_statue')
    mb.box((0, 0, 0.2), (3.2, 3.2, 0.6), 'stone_granite', mats={'top': 'stone_trim'})
    mb.box((0, 0, 1.6), (1.7, 1.7, 2.4), 'stone_granite', mats={'top': 'stone_trim'})
    mb.box((0, 0, 2.9), (2.0, 2.0, 0.25), 'stone_trim')
    z = 3.02
    # figure in a frock coat
    mb.cylinder((0, 0), 0.32, z, z + 1.1, 'bronze', seg=12, r1=0.28)                    # coat skirt
    mb.cylinder((-0.12, 0), 0.1, z, z + 0.25, 'bronze', seg=8)
    mb.cylinder((0, 0), 0.28, z + 1.1, z + 1.75, 'bronze', seg=12, r1=0.3)             # chest
    mb.cylinder((0, 0), 0.3, z + 1.75, z + 1.85, 'bronze', seg=12, r1=0.12)            # shoulders
    mb.cylinder((0, 0), 0.07, z + 1.85, z + 1.95, 'bronze', seg=8)
    mb.sphere((0, 0, z + 2.08), 0.14, 'bronze', seg=12, rings=8, sz=1.2)
    for s in (-1, 1):
        mb.cylinder((s * 0.34, 0), 0.075, z + 1.05, z + 1.75, 'bronze', seg=8, r1=0.085)
    mb.box((0.36, -0.12, z + 1.12), (0.12, 0.3, 0.38), 'bronze')                        # book
    return mb


# ----------------------------------------------------------------------------- wheel for the motorbike (cars: blender/cars.py)
def _wheel(mb, x, y, r, w):
    seg = 12
    for k in range(seg):
        a0, a1 = 2 * math.pi * k / seg, 2 * math.pi * (k + 1) / seg
        p = lambda a, yy: (x + r * math.cos(a), yy, r + r * math.sin(a))
        mb.quad(p(a0, y - w / 2), p(a1, y - w / 2), p(a1, y + w / 2), p(a0, y + w / 2), 'rubber', smooth='whl%d%d' % (int(x * 10), int(y * 10)))
    for yy, sgn in ((y - w / 2, -1), (y + w / 2, 1)):
        pts = [(x + r * math.cos(2 * math.pi * k / seg), yy, r + r * math.sin(2 * math.pi * k / seg)) for k in range(seg)]
        mb.face(pts if sgn < 0 else pts[::-1], 'rubber')
        hub = [(x + r * 0.6 * math.cos(2 * math.pi * k / seg), yy + sgn * 0.005, r + r * 0.6 * math.sin(2 * math.pi * k / seg)) for k in range(seg)]
        mb.face(hub if sgn < 0 else hub[::-1], 'chrome')


# ----------------------------------------------------------------------------- 오토바이 (delivery scooter)
def motorbike():
    mb = MeshBuilder('motorbike')
    for x in (-0.62, 0.62):
        _wheel(mb, x, 0, 0.27, 0.09)
    mb.box((0, 0, 0.5), (0.9, 0.28, 0.25), 'car_paint')
    mb.box((-0.35, 0, 0.78), (0.6, 0.26, 0.12), 'rubber')                  # seat
    mb.box((0.48, 0, 0.75), (0.14, 0.2, 0.6), 'car_paint')                 # leg shield column
    mb.box((0.55, 0, 1.08), (0.06, 0.62, 0.04), 'metal_dark')               # handlebar
    mb.box((0.6, 0, 0.98), (0.12, 0.16, 0.1), 'light_white')
    mb.box((-0.62, 0, 0.82), (0.36, 0.34, 0.1), 'metal_dark')               # rack
    return mb
