"""Procedural facade generator for the non-landmark buildings (footprint extrusion
with real recessed windows, sills, floor bands, parapets, roofs and rooftop clutter)."""
import math, random
from mathutils import Vector, Matrix
from common import MeshBuilder, ground, offset_poly, min_area_rect, poly_area

STYLE = {
    #          wall            window frame     bay   win_w  sill  head  band      found
    'modern': dict(wall='concrete', alt='concrete_warm', glass='glass', frame='frame_dark', bay=3.6, ww=0.78, sill=1.0, head=0.45, band=True, depth=0.28, mull=2),
    'white':  dict(wall='plaster_white', alt='plaster_cream', glass='glass', frame='frame_dark', bay=3.2, ww=0.55, sill=0.95, head=0.6, band=False, depth=0.22, mull=1),
    'stone':  dict(wall='stone_rubble', alt='stone_rubble', glass='glass', frame='frame_white', bay=3.0, ww=0.42, sill=0.9, head=0.7, band=False, depth=0.32, mull=1, trim='stone_trim'),
    'house':  dict(wall='plaster_cream', alt='brick_red', glass='glass', frame='frame_white', bay=3.0, ww=0.45, sill=0.95, head=0.65, band=False, depth=0.18, mull=1),
    'gym':    dict(wall='concrete', alt='concrete', glass='glass', frame='frame_dark', bay=4.5, ww=0.8, sill=4.6, head=0.4, band=False, depth=0.2, mull=3),
    # 1997 halls from the university's building photos (yonsei.ac.kr/sc/349): red brick (광복관 · 알렌관 ·
    # 언어연구교육원), tan tile (국제학사), pale stone with a slate roof (빌링슬리관)
    'brick':  dict(wall='brick_red', alt='concrete', glass='glass', frame='frame_white', bay=3.0, ww=0.5, sill=0.95, head=0.6, band=False, depth=0.22, mull=1, trim='stone_trim'),
    'tile':   dict(wall='tile_facade', alt='concrete', glass='glass', frame='frame_silver', bay=3.2, ww=0.5, sill=0.95, head=0.6, band=False, depth=0.2, mull=1),
    'stone_pale': dict(wall='stone_white', alt='stone_white', glass='glass', frame='frame_dark', bay=3.0, ww=0.45, sill=0.9, head=0.7, band=False, depth=0.3, mull=1, trim='stone_trim'),
    'city':   dict(wall='brick_red', alt='plaster_cream', glass='glass', frame='frame_silver', bay=3.0, ww=0.5, sill=0.95, head=0.6, band=False, depth=0.15, mull=1),
}
FH = {'modern': 3.8, 'white': 3.6, 'stone': 4.2, 'house': 3.4, 'gym': 6.5, 'city': 3.0, 'brick': 3.6, 'tile': 3.4, 'stone_pale': 4.0}


def wall_edge(mb, a, b, z0, z1, nfloors, fh, st, rnd, skip_windows=False, ground_floor_shop=False):
    a, b = Vector((*a, 0)), Vector((*b, 0))
    t = b - a
    L = t.length
    if L < 0.05:
        return
    t /= L
    n = Vector((t.y, -t.x, 0))          # outward for CCW polygons
    wall, glass, frame = st['wall'], st['glass'], st['frame']

    def P(s, z, d=0.0):
        p = a + t * s + n * d
        return (p.x, p.y, z)

    # foundation (hidden under terrain on slopes)
    mb.quad(P(0, z0 - 4), P(L, z0 - 4), P(L, z0), P(0, z0), 'concrete_dark')
    bays = int(round(L / st['bay']))
    if L < 2.6 or bays < 1 or skip_windows:
        mb.quad(P(0, z0), P(L, z0), P(L, z1), P(0, z1), wall)
        return
    bw = L / bays
    zt = z0 + nfloors * fh
    for f in range(nfloors):
        zf = z0 + f * fh
        shop = ground_floor_shop and f == 0
        for k in range(bays):
            s0, s1 = k * bw, (k + 1) * bw
            mid = a + t * ((s0 + s1) / 2) + n * 0.6
            g = ground(mid.x, mid.y)
            sill = 0.25 if shop else st['sill']
            head = 0.35 if shop else st['head']
            if g > zf + sill - 0.15 or (f == 0 and st is STYLE['gym'] and False):
                mb.quad(P(s0, zf), P(s1, zf), P(s1, zf + fh), P(s0, zf + fh), wall)
                continue
            ww = bw * (0.92 if shop else st['ww'])
            w0 = s0 + (bw - ww) / 2
            w1 = w0 + ww
            zs, zh = zf + sill, zf + fh - head
            d = st['depth']
            # surround
            mb.quad(P(s0, zf), P(s1, zf), P(s1, zs), P(s0, zs), wall)
            mb.quad(P(s0, zh), P(s1, zh), P(s1, zf + fh), P(s0, zf + fh), wall)
            mb.quad(P(s0, zs), P(w0, zs), P(w0, zh), P(s0, zh), wall)
            mb.quad(P(w1, zs), P(s1, zs), P(s1, zh), P(w1, zh), wall)
            # reveals
            rv = st.get('trim', wall)
            mb.quad(P(w0, zs, 0), P(w0, zs, -d), P(w1, zs, -d), P(w1, zs, 0), rv)
            mb.quad(P(w1, zh, 0), P(w1, zh, -d), P(w0, zh, -d), P(w0, zh, 0), rv)
            mb.quad(P(w0, zh, 0), P(w0, zh, -d), P(w0, zs, -d), P(w0, zs, 0), rv)
            mb.quad(P(w1, zs, 0), P(w1, zs, -d), P(w1, zh, -d), P(w1, zh, 0), rv)
            # glass + frame
            mb.quad(P(w0, zs, -d), P(w1, zs, -d), P(w1, zh, -d), P(w0, zh, -d), glass)
            fw = 0.06
            nm = st['mull'] if not shop else 3
            dd = -d + 0.05
            if not (nm == 1 and ww < 1.0):
                for m in range(1, nm + 1):
                    sm = w0 + ww * m / (nm + 1)
                    mb.quad(P(sm - fw, zs, dd), P(sm + fw, zs, dd), P(sm + fw, zh, dd), P(sm - fw, zh, dd), frame)
            zt_ = zs + (zh - zs) * 0.72
            mb.quad(P(w0, zt_ - fw, dd), P(w1, zt_ - fw, dd), P(w1, zt_ + fw, dd), P(w0, zt_ + fw, dd), frame)
            if not shop:
                tm = st.get('trim', 'stone_trim' if st['wall'] != 'concrete' else 'concrete')
                mb.quad(P(w0 - 0.08, zs - 0.08, 0.1), P(w1 + 0.08, zs - 0.08, 0.1), P(w1 + 0.08, zs, 0.1), P(w0 - 0.08, zs, 0.1), tm)
                mb.quad(P(w0 - 0.08, zs, 0.1), P(w1 + 0.08, zs, 0.1), P(w1 + 0.08, zs, 0), P(w0 - 0.08, zs, 0), tm)
        # floor band (projecting slab edge) for modern blocks
        if st['band'] and f > 0:
            zb = zf - 0.18
            mb.quad(P(0, zb, 0.14), P(L, zb, 0.14), P(L, zb + 0.4, 0.14), P(0, zb + 0.4, 0.14), st['alt'])
            mb.quad(P(0, zb + 0.4, 0.14), P(L, zb + 0.4, 0.14), P(L, zb + 0.4, 0), P(0, zb + 0.4, 0), st['alt'])
            mb.quad(P(0, zb, 0), P(L, zb, 0), P(L, zb, 0.14), P(0, zb, 0.14), st['alt'])
    if z1 > zt:
        mb.quad(P(0, zt), P(L, zt), P(L, z1), P(0, z1), wall)


def parapet_and_roof(mb, poly, zt, st, rnd, roof_mat='roof_flat', clutter=True):
    inner = offset_poly(poly, -0.3)
    zp = zt + 0.9
    # coping
    n = len(poly)
    for i in range(n):
        a, b = poly[i], poly[(i + 1) % n]
        ia, ib = inner[i], inner[(i + 1) % n]
        mb.quad((a[0], a[1], zp), (b[0], b[1], zp), (ib[0], ib[1], zp), (ia[0], ia[1], zp), 'concrete')
        mb.quad((ib[0], ib[1], zt), (ia[0], ia[1], zt), (ia[0], ia[1], zp), (ib[0], ib[1], zp), st['wall'] if st['wall'] != 'stone_rubble' else 'concrete')
    mb.face([(p[0], p[1], zt) for p in inner], roof_mat)
    if not clutter:
        return
    cx = sum(p[0] for p in poly) / n
    cy = sum(p[1] for p in poly) / n
    area = abs(poly_area(poly))
    if area > 200:
        # stair penthouse
        _, _, L, W, ang = min_area_rect(poly)
        mb.box((cx, cy, zt + 1.6), (min(6, L * 0.3), min(4, W * 0.4), 3.2), st['wall'], rotz=ang,
               mats={'top': 'roof_flat'})
        for k in range(rnd.randint(1, 4)):
            ox, oy = rnd.uniform(-L * 0.3, L * 0.3), rnd.uniform(-W * 0.25, W * 0.25)
            x = cx + ox * math.cos(ang) - oy * math.sin(ang)
            y = cy + ox * math.sin(ang) + oy * math.cos(ang)
            mb.box((x, y, zt + 0.6), (1.6, 1.0, 1.2), 'metal', rotz=ang, skip=('bottom',))


def hip_roof(mb, cx, cy, L, W, ang, zt, mat, pitch=0.6, over=0.5, fascia='frame_white'):
    L2, W2 = L / 2 + over, W / 2 + over
    h = W2 * pitch
    c, s = math.cos(ang), math.sin(ang)

    def P(x, y, z):
        return (cx + x * c - y * s, cy + x * s + y * c, z)
    r = max(0.0, L2 - W2)
    z0 = zt - over * pitch
    A, B, C, D = P(-L2, -W2, z0), P(L2, -W2, z0), P(L2, W2, z0), P(-L2, W2, z0)
    zr = z0 + h
    R1, R2 = P(-r, 0, zr), P(r, 0, zr)
    mb.face([A, B, R2, R1], mat)
    mb.face([C, D, R1, R2], mat)
    mb.face([B, C, R2], mat)
    mb.face([D, A, R1], mat)
    # soffit + fascia
    mb.face([D, C, B, A], 'plaster_white')
    for p, q in ((A, B), (B, C), (C, D), (D, A)):
        mb.quad(p, q, (q[0], q[1], q[2] - 0.25), (p[0], p[1], p[2] - 0.25), fascia)


def barrel_roof(mb, cx, cy, L, W, ang, zt, rise=0.22, seg=12):
    """체육관 (1960): a reinforced-concrete arched (barrel-vaulted) roof spanning the short side, with arched end walls."""
    c, s = math.cos(ang), math.sin(ang)
    P = lambda x, y, z: (cx + x * c - y * s, cy + x * s + y * c, z)
    h = W * rise
    prof = [(-W / 2 + W * k / seg, zt + h * math.sin(math.pi * k / seg)) for k in range(seg + 1)]
    for (y0, z0), (y1, z1) in zip(prof, prof[1:]):
        mb.quad(P(-L / 2 - 0.4, y0, z0), P(-L / 2 - 0.4, y1, z1), P(L / 2 + 0.4, y1, z1), P(L / 2 + 0.4, y0, z0), 'metal')
    for x in (-L / 2, L / 2):           # arched gable ends
        for (y0, z0), (y1, z1) in zip(prof, prof[1:]):
            mb.quad(P(x, y0, zt), P(x, y1, zt), P(x, y1, z1), P(x, y0, z0), 'concrete')


# ----------------------------------------------------------------------------- rooftop features the outlines cannot say
def observatory(mb, b, zt, st):
    """과학관's observatory (reference/학교연혁_과학관.jpg, top right; reference/활천대_2009_연세춘추.jpg, far left): a
    square white tower about 1.4 storeys over the roof near the east end of the east wing, carrying a silver dome
    with an observing slit.  The tower stands back from the south face and is about 2.5 window bays across; the dome
    nearly fills it (7.6 m across on a short drum), its top some 9.5 m over the main roof."""
    fp = b['footprint']
    e0, e1 = Vector(fp[0]), Vector(fp[1])                # the east face of the east wing (south -> north)
    w = (Vector(fp[14]) - e0).normalized()               # along the wing, westwards
    c = (e0 + e1) / 2 + w * 7.5                          # tower centre, 7.5 m in from the east face (aerial)
    ang = math.atan2(w.y, w.x)
    T, Ht = 9.0, 5.0                                     # tower side, height over the roof
    zb = zt + Ht
    mb.box((c.x, c.y, zt + Ht / 2), (T, T, Ht), st['wall'], rotz=ang, mats={'top': 'roof_flat'}, skip=('bottom',))
    mb.box((c.x, c.y, zb + 0.12), (T + 0.3, T + 0.3, 0.24), 'concrete', rotz=ang, skip=('bottom',))   # coping
    cs, sn = math.cos(ang), math.sin(ang)
    L = lambda u, v, z: (c.x + u * cs - v * sn, c.y + u * sn + v * cs, z)     # u westwards, v southwards
    for (u, v, nu, nv) in ((0, T / 2, 0, 1), (-T / 2, 0, -1, 0), (T / 2, 0, 1, 0)):            # a window: S, E, W faces
        tu, tv = -nv, nu
        p = lambda s, z, d=0.02: L(u + tu * s + nu * d, v + tv * s + nv * d, z)
        mb.quad(p(-0.45, zt + 2.2), p(0.45, zt + 2.2), p(0.45, zt + 3.6), p(-0.45, zt + 3.6), st['glass'])
    R, seg, rings = 3.8, 24, 7
    mb.cylinder((c.x, c.y), R + 0.1, zb + 0.24, zb + 0.75, 'paint_white', seg=seg, cap_top=False)   # drum
    za = zb + 0.75
    # the dome: gores of the silver shell, with the slit (two gores wide, dark) running up over the top
    for i in range(seg):
        a0, a1 = 2 * math.pi * i / seg, 2 * math.pi * (i + 1) / seg
        slit = i in (5, 6)                               # facing south-west
        for j in range(rings):
            t0, t1 = math.pi / 2 * j / rings, math.pi / 2 * (j + 1) / rings
            q = lambda a, t: (c.x + R * math.cos(t) * math.cos(a + ang), c.y + R * math.cos(t) * math.sin(a + ang),
                              za + R * math.sin(t))
            mb.face([q(a0, t0), q(a1, t0), q(a1, t1), q(a0, t1)], 'metal_dark' if slit else 'lamp_housing',
                    smooth='obs_dome' if not slit else False)
    for i in range(0, seg, 2):                           # raised seams between the gores
        a = 2 * math.pi * i / seg + ang
        for j in range(rings):
            t0, t1 = math.pi / 2 * j / rings, math.pi / 2 * (j + 1) / rings
            r0, r1 = R + 0.03, R + 0.03
            p0 = (c.x + r0 * math.cos(t0) * math.cos(a), c.y + r0 * math.cos(t0) * math.sin(a), za + r0 * math.sin(t0))
            p1 = (c.x + r1 * math.cos(t1) * math.cos(a), c.y + r1 * math.cos(t1) * math.sin(a), za + r1 * math.sin(t1))
            dx, dy = -math.sin(a) * 0.04, math.cos(a) * 0.04
            mb.quad((p0[0] - dx, p0[1] - dy, p0[2]), (p0[0] + dx, p0[1] + dy, p0[2]),
                    (p1[0] + dx, p1[1] + dy, p1[2]), (p1[0] - dx, p1[1] - dy, p1[2]), 'frame_silver')


ROOF_EXTRAS = {222843398: observatory}


def build_generic(b, rnd):
    style = b['style']
    st = dict(STYLE[style])
    poly = [tuple(p) for p in b['footprint']]
    if poly_area(poly) < 0:
        poly.reverse()
    fh = FH[style]
    z0 = b['base']
    nf = b['levels']
    mb = MeshBuilder('bld_%s' % b['id'])
    if style == 'city':
        st['wall'] = rnd.choice(['brick_red', 'brick_red', 'plaster_cream', 'tile_facade', 'plaster_grey'])
        st['frame'] = 'frame_silver'
    elif style == 'white' and rnd.random() < 0.3:
        st['wall'] = 'plaster_cream'
    pitched = style in ('stone', 'house', 'stone_pale')
    if pitched or style == 'gym':
        cx, cy, L, W, ang = min_area_rect(poly)
        c, s = math.cos(ang), math.sin(ang)
        poly = [(cx + x * c - y * s, cy + x * s + y * c) for x, y in ((-L / 2, -W / 2), (L / 2, -W / 2), (L / 2, W / 2), (-L / 2, W / 2))]
    zt = z0 + nf * fh
    if style == 'gym':
        nf, fh = 1, nf * fh
    shop = style == 'city' and rnd.random() < 0.45
    for i in range(len(poly)):
        wall_edge(mb, poly[i], poly[(i + 1) % len(poly)], z0, zt if pitched else zt + 0.9, nf, fh, st, rnd,
                  ground_floor_shop=shop)
    if pitched:
        hip_roof(mb, cx, cy, L, W, ang, zt, rnd.choice(['roof_slate', 'roof_giwa']) if style == 'house' else 'roof_slate',
                 pitch=0.55 if style == 'house' else 0.75)
    elif style == 'gym':
        barrel_roof(mb, cx, cy, L, W, ang, zt)
    else:
        roof = 'roof_green' if (style == 'city' and rnd.random() < 0.6) else 'roof_flat'
        parapet_and_roof(mb, poly, zt, st, rnd, roof_mat=roof, clutter=style != 'city')
        if b['id'] in ROOF_EXTRAS:
            ROOF_EXTRAS[b['id']](mb, b, zt, st)
        if style == 'city':
            n = len(poly)
            cx = sum(p[0] for p in poly) / n
            cy = sum(p[1] for p in poly) / n
            if rnd.random() < 0.7:     # rooftop water tank
                mb.cylinder((cx + rnd.uniform(-1, 1), cy + rnd.uniform(-1, 1)), 0.75, zt, zt + 1.5,
                            rnd.choice(['metal', 'paint_blue', 'metal_green']), seg=10)
            if shop:
                # 1990s shop sign band on the longest edge
                best = max(range(n), key=lambda i: (Vector(poly[(i + 1) % n]) - Vector(poly[i])).length)
                a, bb = Vector(poly[best]), Vector(poly[(best + 1) % n])
                t = (bb - a)
                Lb = t.length
                t.normalize()
                nn = Vector((t.y, -t.x))
                k = rnd.randrange(16)
                u0, v0 = (k % 2) / 2, 1 - (k // 2 + 1) / 8
                sw = min(Lb - 0.6, 4.4)
                if sw > 1.5:
                    mid = (a + bb) / 2
                    p0 = mid - t * sw / 2 + nn * 0.12
                    p1 = mid + t * sw / 2 + nn * 0.12
                    zs0, zs1 = z0 + fh - 0.1, z0 + fh + 1.0
                    mb.face([(p0.x, p0.y, zs0), (p1.x, p1.y, zs0), (p1.x, p1.y, zs1), (p0.x, p0.y, zs1)], 'sign_shops',
                            uvs=[(u0, v0), (u0 + 0.5, v0), (u0 + 0.5, v0 + 0.125), (u0, v0 + 0.125)])
    return mb
