"""Hand-modelled 1997 landmarks.  Every builder returns a list of MeshBuilders in
world coordinates (local frames are applied through MeshBuilder.xf)."""
import math, random
from mathutils import Vector, Matrix
from common import MeshBuilder, ground, ground_top, min_area_rect, local_frame, offset_poly, poly_area, CAMPUS
import generic

rnd = random.Random(97)


def bld(id_):
    return next(b for b in CAMPUS['buildings'] if b['id'] == id_)


def frame_for(b, front_dir, z=None):
    """OBB frame whose local -Y axis points along front_dir (world 2D)."""
    cx, cy, L, W, ang = min_area_rect([tuple(p) for p in b['footprint']])
    fy = Vector((math.sin(ang), -math.cos(ang)))
    if fy.dot(Vector(front_dir)) < 0:
        ang += math.pi
    return cx, cy, L, W, ang, (b['base'] if z is None else z)


# ----------------------------------------------------------------------------- shared pieces
def arch_points(s0, s1, zs, kind='round', seg=10):
    """Points of an arch from left springing to right springing (s, z)."""
    w = s1 - s0
    pts = []
    if kind == 'round':
        r = w / 2
        for i in range(seg + 1):
            a = math.pi - math.pi * i / seg
            pts.append((s0 + r + r * math.cos(a), zs + r * math.sin(a)))
    elif kind == 'segment':   # shallow segmental arch: rise a quarter of the span
        w = s1 - s0
        rise = w * 0.16
        r = (w * w / 4 + rise * rise) / (2 * rise)
        a0 = math.asin((w / 2) / r)
        for i in range(seg + 1):
            a = -a0 + 2 * a0 * i / seg
            pts.append((s0 + w / 2 + r * math.sin(a), zs + r * math.cos(a) - (r - rise)))
        pts.sort(key=lambda p: p[0])
        return pts
    elif kind == 'tudor':     # four-centred: tight arcs at the springings, then nearly straight to a low point
        a = w / 2
        r1, th = 0.36 * a, math.radians(66)
        na = max(3, seg // 3)
        left = [(s0 + r1 - r1 * math.cos(th * i / na), zs + r1 * math.sin(th * i / na)) for i in range(na + 1)]
        ex, ez = left[-1]
        apex = ez + (s0 + a - ex) / math.tan(th)
        nl_ = max(2, seg // 2 - na)
        for i in range(1, nl_ + 1):            # a slightly bellied line to the apex (a large-radius arc)
            t = i / nl_
            bell = 0.06 * a * math.sin(math.pi * t) * (1 - t)
            left.append((ex + (s0 + a - ex) * t, ez + (apex - ez) * t + bell))
        right = [(2 * (s0 + a) - s, z) for s, z in reversed(left[:-1])]
        return left + right
    else:   # pointed (equilateral gothic)
        r = w
        half = seg // 2
        for i in range(half + 1):          # left arc centred at s1
            a = math.pi - (math.pi / 3) * i / half
            pts.append((s1 + r * math.cos(a), zs + r * math.sin(a)))
        for i in range(1, half + 1):       # right arc centred at s0
            a = math.pi / 3 - (math.pi / 3) * i / half
            pts.append((s0 + r * math.cos(a), zs + r * math.sin(a)))
    return pts


def arch_fill(mb, P, s0, s1, zs, ztop, depth, mat, kind='round', seg=10, intrados_mat=None):
    """Fill the area between an arch and the horizontal line ztop over [s0,s1].
    P(s, z, d) -> local 3D point (d = offset along outward normal, negative = inward)."""
    pts = arch_points(s0, s1, zs, kind, seg)
    for i in range(len(pts) - 1):
        (sa, za), (sb, zb) = pts[i], pts[i + 1]
        mb.quad(P(sa, za, 0), P(sb, zb, 0), P(sb, ztop, 0), P(sa, ztop, 0), mat)                  # front
        mb.quad(P(sb, zb, -depth), P(sa, za, -depth), P(sa, ztop, -depth), P(sb, ztop, -depth), mat)  # back
        mb.quad(P(sb, zb, 0), P(sa, za, 0), P(sa, za, -depth), P(sb, zb, -depth), intrados_mat or mat)  # soffit


def edge_P(a, b, base_z=0.0):
    a, b = Vector((*a, 0)), Vector((*b, 0))
    t = (b - a)
    L = t.length
    t.normalize()
    n = Vector((t.y, -t.x, 0))

    def P(s, z, d=0.0):
        p = a + t * s + n * d
        return (p.x, p.y, base_z + z)
    return P, L, t, n


def rect(L, W):
    return [(-L / 2, -W / 2), (L / 2, -W / 2), (L / 2, W / 2), (-L / 2, W / 2)]


def flat_wall(mb, P, s0, s1, z0, z1, mat, d=0.0):
    mb.quad(P(s0, z0, d), P(s1, z0, d), P(s1, z1, d), P(s0, z1, d), mat)


def window_grid(mb, P, L, z0, nfl, fh, bay, mat_wall, ww=0.6, sill=0.9, head=0.6, depth=0.25,
                glass='glass', frame='frame_dark', trim=None, mull=1, s_start=0.0, s_end=None, d=0.0):
    """Punched windows on an edge segment [s_start, s_end] (local wall plane offset d)."""
    s_end = L if s_end is None else s_end
    span = s_end - s_start
    nb = max(1, int(round(span / bay)))
    bw = span / nb
    for f in range(nfl):
        zf = z0 + f * fh
        for k in range(nb):
            s0 = s_start + k * bw
            s1 = s0 + bw
            w = bw * ww
            w0, w1 = s0 + (bw - w) / 2, s0 + (bw + w) / 2
            zs, zh = zf + sill, zf + fh - head
            Q = lambda s, z, dd=0.0: P(s, z, d + dd)
            mb.quad(Q(s0, zf), Q(s1, zf), Q(s1, zs), Q(s0, zs), mat_wall)
            mb.quad(Q(s0, zh), Q(s1, zh), Q(s1, zf + fh), Q(s0, zf + fh), mat_wall)
            mb.quad(Q(s0, zs), Q(w0, zs), Q(w0, zh), Q(s0, zh), mat_wall)
            mb.quad(Q(w1, zs), Q(s1, zs), Q(s1, zh), Q(w1, zh), mat_wall)
            rv = trim or mat_wall
            mb.quad(Q(w0, zs), Q(w0, zs, -depth), Q(w1, zs, -depth), Q(w1, zs), rv)
            mb.quad(Q(w1, zh), Q(w1, zh, -depth), Q(w0, zh, -depth), Q(w0, zh), rv)
            mb.quad(Q(w0, zh), Q(w0, zh, -depth), Q(w0, zs, -depth), Q(w0, zs), rv)
            mb.quad(Q(w1, zs), Q(w1, zs, -depth), Q(w1, zh, -depth), Q(w1, zh), rv)
            mb.quad(Q(w0, zs, -depth), Q(w1, zs, -depth), Q(w1, zh, -depth), Q(w0, zh, -depth), glass)
            for m in range(mull):
                sm = w0 + (w1 - w0) * (m + 1) / (mull + 1)
                mb.quad(Q(sm - 0.04, zs, -depth + 0.06), Q(sm + 0.04, zs, -depth + 0.06),
                        Q(sm + 0.04, zh, -depth + 0.06), Q(sm - 0.04, zh, -depth + 0.06), frame)
            zt = zs + (zh - zs) * 0.7
            mb.quad(Q(w0, zt - 0.04, -depth + 0.06), Q(w1, zt - 0.04, -depth + 0.06),
                    Q(w1, zt + 0.04, -depth + 0.06), Q(w0, zt + 0.04, -depth + 0.06), frame)
            if trim:
                # protruding stone sill + hood moulding
                mb.quad(Q(w0 - 0.12, zs - 0.12, 0.1), Q(w1 + 0.12, zs - 0.12, 0.1), Q(w1 + 0.12, zs, 0.1), Q(w0 - 0.12, zs, 0.1), trim)
                mb.quad(Q(w0 - 0.12, zs, 0.1), Q(w1 + 0.12, zs, 0.1), Q(w1 + 0.12, zs, 0), Q(w0 - 0.12, zs, 0), trim)
                mb.quad(Q(w0 - 0.15, zh, 0.1), Q(w1 + 0.15, zh, 0.1), Q(w1 + 0.15, zh + 0.18, 0.1), Q(w0 - 0.15, zh + 0.18, 0.1), trim)
                mb.quad(Q(w0 - 0.15, zh + 0.18, 0.1), Q(w1 + 0.15, zh + 0.18, 0.1), Q(w1 + 0.15, zh + 0.18, 0), Q(w0 - 0.15, zh + 0.18, 0), trim)
                mb.quad(Q(w0 - 0.15, zh, 0), Q(w1 + 0.15, zh, 0), Q(w1 + 0.15, zh, 0.1), Q(w0 - 0.15, zh, 0.1), trim)


# ============================================================================= 중앙도서관
def library():
    """중앙도서관 (1979) as in reference/1997_중앙도서관.jpg and 1995_백양로와_중앙도서관.jpg: tall slender piers of pale
    stone panels from the plinth to a deep attic band, each bay closed at the top by a shallow segmental arch;
    deep in the bays, rows of windows between bronze-tan spandrel panels; panel joints over piers and attic."""
    b = bld(163525865)
    cx, cy, L, W, ang, z0 = frame_for(b, (1.0, -0.25))
    # the piers stand on a low granite base only two steps over the forecourt (1997 photo: people walk at the foot of
    # the piers; no flight up to a podium), and the ground is level all round it (tools/build_campus.py LIBRARY_APRON)
    g0 = 0.3
    z0 = lift_base(z0, cx, cy, ang, W / 2 + 2.5, g0, 0.3)
    mb = MeshBuilder('lm_library')
    mb.xf = local_frame(cx, cy, ang, z0)
    H = 23.0                     # top of attic
    spring, attic0 = 16.6, 18.8
    inset = 2.4
    fh, nf = 3.6, 5
    # plinth
    mb.prism(offset_poly(rect(L, W), 0.6), -4, g0, 'stone_granite', 'stone_granite')
    # its top is the floor of the deep arcade between the piers, walked on all round to the glass
    W_ = lambda lx, ly, lz: tuple(mb.xf @ Vector((lx, ly, lz)))
    ring_o, ring_i = offset_poly(rect(L, W), 0.6), rect(L - 2 * (inset + 0.25), W - 2 * (inset + 0.25))
    for i in range(4):
        j = (i + 1) % 4
        WALK_FACES.append([W_(*ring_o[i], g0), W_(*ring_o[j], g0), W_(*ring_i[j], g0), W_(*ring_i[i], g0)])
    # the main door: the two bays either side of the middle pier of the 백양로 front, glass doors in bright frames
    # with the lit entrance hall behind (instead of the dark glazing of the other bays)
    nb_f = max(1, int(round(L / 5.4)))
    bw_f = (L - 1.25) / nb_f
    mid_k = nb_f // 2
    door_bays = [(-L / 2 + (mid_k - 1) * bw_f + 1.25, -L / 2 + mid_k * bw_f),
                 (-L / 2 + mid_k * bw_f + 1.25, -L / 2 + (mid_k + 1) * bw_f)]
    # recessed wall in the bays: per floor a bronze spandrel band, then glazing split by slim mullions
    core = rect(L - 2 * inset, W - 2 * inset)
    for i in range(4):
        a, bb = core[i], core[(i + 1) % 4]
        P, Le, t, n = edge_P(a, bb)
        gaps = [(x0 - a[0] + 0.15, x1 - a[0] - 0.15) for x0, x1 in door_bays] if i == 0 else []
        cuts = [0.0] + [v for g in gaps for v in g] + [Le]
        for s0_, s1_ in zip(cuts[0::2], cuts[1::2]):                          # ground floor: dark glazing, set back
            flat_wall(mb, P, s0_, s1_, g0, g0 + 3.4, 'glass', d=-0.3)
        for k in range(int(Le / 2.0)):
            s = (k + 0.5) * Le / int(Le / 2.0)
            if any(g[0] - 0.1 < s < g[1] + 0.1 for g in gaps):
                continue
            mb.quad(P(s - 0.06, g0, -0.25), P(s + 0.06, g0, -0.25), P(s + 0.06, g0 + 3.4, -0.25), P(s - 0.06, g0 + 3.4, -0.25), 'frame_dark')
        for s0_, s1_ in gaps:
            shopfront(mb, P, s0_, s1_, g0, g0 + 3.3, -0.3, bays=4, door_h=2.4)
            vestibule(mb, P, s0_ - 0.1, s1_ + 0.1, g0 + 0.002, g0 + 3.25, -0.32, 6.0, lights=3)
            mb.quad(P(s0_ - 0.15, g0 + 3.3, -0.3), P(s1_ + 0.15, g0 + 3.3, -0.3), P(s1_ + 0.15, g0 + 3.4, -0.3),
                    P(s0_ - 0.15, g0 + 3.4, -0.3), 'frame_silver')
        for f in range(1, nf):
            zf = g0 + 3.4 + (f - 1) * fh
            flat_wall(mb, P, 0, Le, zf, zf + 1.35, 'panel_bronze')
            flat_wall(mb, P, 0, Le, zf + 1.35, zf + fh, 'glass', d=-0.12)
            mb.quad(P(0, zf + 1.35, 0), P(Le, zf + 1.35, 0), P(Le, zf + 1.35, -0.12), P(0, zf + 1.35, -0.12), 'panel_bronze')
            for k in range(int(Le / 1.4)):
                s = (k + 0.5) * Le / int(Le / 1.4)
                mb.quad(P(s - 0.05, zf + 1.35, -0.08), P(s + 0.05, zf + 1.35, -0.08), P(s + 0.05, zf + fh, -0.08), P(s - 0.05, zf + fh, -0.08), 'frame_dark')
        flat_wall(mb, P, 0, Le, g0 + 3.4 + (nf - 1) * fh, attic0 + 0.4, 'panel_bronze')
    # pier screen
    pier = 1.25
    depth = 2.0
    outer = rect(L, W)

    def joint(P, s0, s1, z):          # a recessed horizontal panel joint
        mb.quad(P(s0, z, 0.015), P(s1, z, 0.015), P(s1, z + 0.05, 0.015), P(s0, z + 0.05, 0.015), 'concrete_dark')

    for i in range(4):
        a, bb = outer[i], outer[(i + 1) % 4]
        P, Le, t, n = edge_P(a, bb)
        nb = max(1, int(round(Le / 5.4)))
        bw = (Le - pier) / nb
        for k in range(nb + 1):
            s = k * bw
            pw = pier * (1.7 if k in (0, nb) else 1.0)
            s0, s1 = (s, s + pw) if k < nb else (Le - pw, Le)
            if k == 0:
                s1 = pw
            mb.quad(P(s0, g0, 0), P(s1, g0, 0), P(s1, attic0, 0), P(s0, attic0, 0), 'stone_panel')
            mb.quad(P(s1, g0, 0), P(s1, g0, -depth), P(s1, attic0, -depth), P(s1, attic0, 0), 'stone_panel')
            mb.quad(P(s0, g0, -depth), P(s0, g0, 0), P(s0, attic0, 0), P(s0, attic0, -depth), 'stone_panel')
            for zz in [g0 + 1.8 * q for q in range(1, int((attic0 - g0) / 1.8))]:
                joint(P, s0, s1, zz)
            if k < nb:
                a0 = s1
                a1 = (k + 1) * bw if k + 1 < nb else Le - pier * 1.7
                arch_fill(mb, P, a0, a1, spring, attic0, depth, 'stone_panel', 'segment', 10)
        # deep attic band of square panels
        flat_wall(mb, P, 0, Le, attic0, H, 'stone_panel')
        mb.quad(P(0, H, 0), P(Le, H, 0), P(Le, H, -depth), P(0, H, -depth), 'stone_panel')
        mb.quad(P(0, attic0, 0), P(0, attic0, -depth), P(Le, attic0, -depth), P(Le, attic0, 0), 'stone_panel')
        for zz in (attic0 + 1.4, attic0 + 2.8):
            joint(P, 0, Le, zz)
        npn = max(1, int(round(Le / 2.1)))
        for q in range(1, npn):
            sq = q * Le / npn
            mb.quad(P(sq - 0.025, attic0, 0.015), P(sq + 0.025, attic0, 0.015), P(sq + 0.025, H, 0.015), P(sq - 0.025, H, 0.015), 'concrete_dark')
        flat_wall(mb, P, 0, Le, H - 1.2, H, 'concrete', d=-depth)
    mb.face([(p[0], p[1], H - 1.2) for p in offset_poly(rect(L, W), -depth)], 'roof_flat')
    # rooftop plant room (seen over the attic in the 1995 photo)
    mb.box((0, 4, H + 0.3), (16, 9, 3.0), 'stone_panel', mats={'top': 'roof_flat'})
    # two broad granite steps along the whole 백양로 front, from the forecourt up onto the base
    stair_flight(mb, 0, -W / 2 - 0.6, L + 1.2, g0, n=2, landing=0.0, tread=0.42, flare=0.0, cheek=0.0, rail=False,
                 gfn=local_ground(mb))
    return [mb]


# ============================================================================= 학생회관
def union():
    b = bld(1444448640)
    cx, cy, L, W, ang, z0 = frame_for(b, (-1.0, 0.25))
    L, W = L - 2, min(W, 24)
    mb = MeshBuilder('lm_union')
    mb.xf = local_frame(cx, cy, ang, z0)
    fh, nf = 3.9, 4
    g = 4.6                     # pilotis ground floor
    H = g + nf * fh
    mb.prism(offset_poly(rect(L, W), 0.3), -4, 0.3, 'stone_granite', 'stone_granite')
    # recessed glazed ground floor + pilotis
    core = rect(L - 4, W - 4)
    for i in range(4):
        a, bb = core[i], core[(i + 1) % 4]
        P, Le, t, n = edge_P(a, bb)
        flat_wall(mb, P, 0, Le, 0.3, g, 'glass')
        for k in range(int(Le / 2.4)):
            s = (k + 0.5) * Le / int(Le / 2.4)
            mb.quad(P(s - 0.06, 0.3, 0.05), P(s + 0.06, 0.3, 0.05), P(s + 0.06, g, 0.05), P(s - 0.06, g, 0.05), 'frame_dark')
    outer = rect(L, W)
    for i in range(4):
        a, bb = outer[i], outer[(i + 1) % 4]
        P, Le, t, n = edge_P(a, bb)
        npil = int(Le / 7.5)
        for k in range(npil + 1):
            s = 0.6 + k * (Le - 1.2) / npil
            mb.box((P(s, 0)[0] - n.x * 1.0, P(s, 0)[1] - n.y * 1.0, g / 2 + 0.3), (0.9, 0.9, g - 0.3), 'stone_panel',
                   rotz=math.atan2(t.y, t.x), skip=('top', 'bottom'))
        # soffit of the overhang
        mb.quad(P(0, g, 0), P(0, g, -2.0), P(Le, g, -2.0), P(Le, g, 0), 'stone_panel')
        # upper floors: glass wall behind a precast concrete lattice
        flat_wall(mb, P, 0, Le, g, H, 'glass', d=-0.9)
        for f in range(nf):
            zf = g + f * fh
            # slab edge band
            flat_wall(mb, P, 0, Le, zf, zf + 0.45, 'stone_panel')
            mb.quad(P(0, zf + 0.45, 0), P(Le, zf + 0.45, 0), P(Le, zf + 0.45, -0.9), P(0, zf + 0.45, -0.9), 'stone_panel')
            mb.quad(P(0, zf, -0.9), P(Le, zf, -0.9), P(Le, zf, 0), P(0, zf, 0), 'stone_panel')
            npan = max(2, int(round(Le / 1.7)))
            pw = Le / npan
            za, zb = zf + 0.45, zf + fh
            zm = (za + zb) / 2
            for k in range(npan):
                s0, s1 = k * pw, (k + 1) * pw
                sm = (s0 + s1) / 2
                # vertical fin
                mb.quad(P(s0 - 0.07, za, 0), P(s0 + 0.07, za, 0), P(s0 + 0.07, zb, 0), P(s0 - 0.07, zb, 0), 'stone_white')
                mb.quad(P(s0 + 0.07, za, 0), P(s0 + 0.07, za, -0.5), P(s0 + 0.07, zb, -0.5), P(s0 + 0.07, zb, 0), 'stone_panel')
                mb.quad(P(s0 - 0.07, za, -0.5), P(s0 - 0.07, za, 0), P(s0 - 0.07, zb, 0), P(s0 - 0.07, zb, -0.5), 'stone_panel')
                # the 학생회관 lattice (reference/1997_학생회관.jpg): from each fin two curved ribs spring up into a
                # pointed arch over the window, and two short ribs curve down into an inverted arch at the sill
                th = 0.1
                for (z_spring, z_apex, nseg) in ((za + (zb - za) * 0.5, zb - 0.02, 5), (za + (zb - za) * 0.24, za + 0.02, 3)):
                    for (sa, sgn) in ((s0 + 0.07, 1), (s1 - 0.07, -1)):
                        half = sm - sa
                        pts = []
                        for q in range(nseg + 1):
                            f_ = q / nseg
                            # gothic rib: a circular arc cut at 60 deg, vertical at the fin, meeting its twin in a point
                            th_ = f_ * math.pi / 3
                            pts.append((sa + half * (1 - math.cos(th_)) / 0.5, z_spring + (z_apex - z_spring) * math.sin(th_) / math.sin(math.pi / 3)))
                        for (p0, p1) in zip(pts, pts[1:]):
                            mb.quad(P(p0[0], p0[1] - th, 0), P(p1[0], p1[1] - th, 0), P(p1[0], p1[1] + th, 0), P(p0[0], p0[1] + th, 0), 'stone_white')
                            mb.quad(P(p1[0], p1[1] - th, 0), P(p0[0], p0[1] - th, 0), P(p0[0], p0[1] - th, -0.45), P(p1[0], p1[1] - th, -0.45), 'stone_panel')
        flat_wall(mb, P, 0, Le, H, H + 1.0, 'stone_panel')
        mb.quad(P(0, H + 1.0, 0), P(Le, H + 1.0, 0), P(Le, H + 1.0, -0.9), P(0, H + 1.0, -0.9), 'stone_panel')
    mb.face([(p[0], p[1], H + 0.2) for p in offset_poly(rect(L, W), -0.9)], 'roof_flat')
    mb.box((L * 0.2, 2, H + 1.6), (8, 6, 3.0), 'stone_panel', mats={'top': 'roof_flat'})
    # long vertical cloth banners (동아리 / 총학생회 현수막) on the front facade
    banners = []
    cols = ['banner_yellow', 'banner_red', 'banner_orange', 'banner_yellow']
    bm = MeshBuilder('lm_union_banners')
    bm.xf = mb.xf
    for k, c in enumerate(cols):
        s = -6 + k * 2.6
        y = -W / 2 - 0.1
        bm.quad((s, y, g + 1.5), (s + 1.8, y, g + 1.5), (s + 1.8, y, H - 0.6), (s, y, H - 0.6), c,
                uvs=[(k * 0.25, 0), (k * 0.25 + 0.25, 0), (k * 0.25 + 0.25, 1), (k * 0.25, 1)])
    # the lower white wing in the 1997 photo (학생회관 별관 is generic) -> nothing else
    return [mb, bm]


# ============================================================================= 백주년기념관
def centennial():
    """1997 aerial photo (reference/1997_백양로_항공사진.jpg): a large stone drum rising out of a two-storey podium that fills
    the whole site, a deep dark portal in the podium facing 백양로, and a plain box (stage house) standing above
    the drum on its north side.  Light granite with incised horizontal courses."""
    b = bld(324328422)
    z0 = b['base']
    fp = [tuple(p) for p in b['footprint']]
    mb = MeshBuilder('lm_centennial')
    # sized from the 1997 photo with its camera fitted to the surrounding halls (the 1997 photo view in the bird's-eye
    # mode): the drum is ~52 m across, its outer ring overhanging the podium towards 백양로, and as low as the
    # building's four storeys (its top ~19 m up, the podium ~7 m)
    HP = 7.0                     # podium roof
    c = (3.8, -207.6)            # drum centre
    R, HD = 25.9, 19.5           # drum radius / top
    seg = 96
    # the dark porch (1997 photo, back-projected onto the podium's 백양로 face with the photo's camera): pitch black
    # from ~3 m to ~46 m south of the north-west corner, up under the drum, whose ring overhangs it.  The podium wall
    # steps back 5 m there; the podium roof runs on over the recess, and the drum stands on the podium roof
    PS0, PS1, PD = 3.0, 46.0, 5.0
    A_, B_ = Vector(fp[3]), Vector(fp[4])          # the 백양로 (west) face, north to south
    tw = (B_ - A_).normalized()
    nw = Vector((-tw.y, tw.x))                     # into the building
    notch = [A_ + tw * PS0, A_ + tw * PS0 + nw * PD, A_ + tw * PS1 + nw * PD, A_ + tw * PS1]
    fpn = fp[:4] + [(p.x, p.y) for p in notch] + fp[4:]
    # podium
    mb.prism(offset_poly(fp, 0.3), z0 - 4, z0 + 0.4, 'stone_granite', 'stone_granite')
    for i in range(len(fpn)):
        p, q = fpn[i], fpn[(i + 1) % len(fpn)]
        inner = 4 <= i <= 6                          # the recess's two sides and its back
        mb.face([(p[0], p[1], z0 + 0.4), (q[0], q[1], z0 + 0.4), (q[0], q[1], z0 + HP), (p[0], p[1], z0 + HP)],
                'trim_black' if inner else 'stone_ashlar')
    mb.face([(p[0], p[1], z0 + HP) for p in fp], 'roof_flat')
    mb.face([(p.x, p.y, z0 + HP - 0.01) for p in notch], 'trim_black')                # the porch ceiling
    for zz in (3.2, 6.0):
        for i in range(len(fpn)):
            if 4 <= i <= 6:
                continue
            p, q = Vector(fpn[i]), Vector(fpn[(i + 1) % len(fpn)])
            d = (q - p).normalized()
            o = Vector((d.y, -d.x)) * 0.04
            mb.face([(*(p + o), z0 + zz), (*(q + o), z0 + zz), (*(q + o), z0 + zz + 0.14), (*(p + o), z0 + zz + 0.14)],
                    'concrete_dark')
    mb.prism(offset_poly(fp, 0.12), z0 + HP, z0 + HP + 0.9, 'stone_ashlar', 'stone_ashlar')
    # drum with incised horizontal joints above the podium; where it overhangs the podium its underside is in shadow
    joints = [HP + 0.9 + k * 3.0 for k in range(1, 4)]
    z = z0 + HP
    mb.cylinder(c, R, z0 + HP - 0.02, z0 + HP, 'concrete_dark', seg=seg, cap_top=False, cap_bot=True,
                mat_cap='trim_black')
    for zj in joints + [HD - 1.2]:
        mb.cylinder(c, R, z, z0 + zj, 'stone_ashlar', seg=seg, cap_top=False)
        mb.cylinder(c, R - 0.1, z0 + zj, z0 + zj + 0.12, 'concrete_dark', seg=seg, cap_top=False)
        z = z0 + zj + 0.12
    mb.cylinder(c, R + 0.3, z0 + HD - 1.2, z0 + HD, 'stone_ashlar', seg=seg, cap_top=False)
    ring = [(c[0] + (R + 0.3) * math.cos(2 * math.pi * i / seg), c[1] + (R + 0.3) * math.sin(2 * math.pi * i / seg)) for i in range(seg)]
    inner = [(c[0] + (R - 0.5) * math.cos(2 * math.pi * i / seg), c[1] + (R - 0.5) * math.sin(2 * math.pi * i / seg)) for i in range(seg)]
    for i in range(seg):
        j = (i + 1) % seg
        mb.quad((*ring[i], z0 + HD), (*ring[j], z0 + HD), (*inner[j], z0 + HD), (*inner[i], z0 + HD), 'stone_ashlar')
        mb.quad((*inner[j], z0 + HD), (*inner[j], z0 + HD - 1.0), (*inner[i], z0 + HD - 1.0), (*inner[i], z0 + HD), 'concrete')
    mb.face([(*p, z0 + HD - 1.0) for p in inner], 'roof_flat')
    # stage house: plain stone box above the drum on the north side, with a slot window
    sh = MeshBuilder('lm_centennial_stage')
    sh.xf = local_frame(c[0] + 2.0, c[1] + 12.5, math.radians(-8), z0)
    sh.box((0, 0, (HD + 6.5) / 2), (19.0, 12.0, HD + 6.5), 'stone_ashlar', mats={'top': 'roof_flat'})
    sh.box((0, 0, HD + 6.5 + 0.45), (19.4, 12.4, 0.9), 'stone_ashlar', skip=('bottom',))
    sh.face([(-3.0, -6.03, HD + 3.0), (3.0, -6.03, HD + 3.0), (3.0, -6.03, HD + 4.2), (-3.0, -6.03, HD + 4.2)], 'glass')
    sh.box((7.0, 3.0, HD + 8.0), (3.0, 3.0, 2.2), 'concrete', mats={'top': 'roof_flat'})
    # in the porch: dark glass doors and their frames at the back, granite steps down from its floor to the forecourt
    P, Le, t, n = edge_P(tuple(A_), tuple(B_), z0)              # d < 0: into the building
    zt = HP - 1.4
    mb.quad(P(PS0 + 0.3, 0.4, -PD + 0.03), P(PS1 - 0.3, 0.4, -PD + 0.03), P(PS1 - 0.3, zt, -PD + 0.03),
            P(PS0 + 0.3, zt, -PD + 0.03), 'glass')
    for k in range(1, 15):
        sm = PS0 + (PS1 - PS0) * k / 15
        mb.quad(P(sm - 0.08, 0.4, -PD + 0.05), P(sm + 0.08, 0.4, -PD + 0.05), P(sm + 0.08, zt, -PD + 0.05),
                P(sm - 0.08, zt, -PD + 0.05), 'frame_dark')
    mb.quad(P(PS0 + 0.3, zt, -PD + 0.05), P(PS1 - 0.3, zt, -PD + 0.05), P(PS1 - 0.3, zt + 0.2, -PD + 0.05),
            P(PS0 + 0.3, zt + 0.2, -PD + 0.05), 'frame_dark')
    for k in range(3):
        q = [P(PS0, 0.4 - k * 0.15, 0.4 + k * 0.6), P(PS1, 0.4 - k * 0.15, 0.4 + k * 0.6)]
        mb.quad(P(PS0, 0.4 - k * 0.15, k * 0.6), P(PS1, 0.4 - k * 0.15, k * 0.6), q[1], q[0], 'stone_granite')
    # the porch's depths go black as in the photo (a flat unlit lining just inside the glass and the walls)
    s0, s1 = PS0 + 0.05, PS1 - 0.05
    mb.quad(P(s0, 0.05, -PD + 0.01), P(s1, 0.05, -PD + 0.01), P(s1, HP - 0.05, -PD + 0.01), P(s0, HP - 0.05, -PD + 0.01), 'void_black')
    out = [mb, sh]
    # the low front block before the podium's south-west corner (tools/build_campus.py CENT_BLOCK, issue #9)
    K = CAMPUS.get('centennial_block')
    if K:
        bk = MeshBuilder('lm_centennial_block')
        c0, tf, tsd = Vector(K['corner']), Vector(K['t_front']), Vector(K['t_side'])
        Hb = K['h']

        def Q(e, a, z, out_f=0.0, out_s=0.0):
            # e along the front (east), a along the side (north), out_f out of the front (south), out_s out of the side
            p = c0 + tf * e + tsd * a - tsd * out_f - tf * out_s
            return (p.x, p.y, z0 + z)
        F, S = K['front'], K['side']
        e0, e1, he = K['entrance']
        d0, d1, hd = K['door']
        # front face (south) with the wide dark entrance, recessed 2.5 m
        bk.quad(Q(0, 0, -3), Q(e0, 0, -3), Q(e0, 0, Hb), Q(0, 0, Hb), 'stone_ashlar')
        bk.quad(Q(e1, 0, -3), Q(F, 0, -3), Q(F, 0, Hb), Q(e1, 0, Hb), 'stone_ashlar')
        bk.quad(Q(e0, 0, he), Q(e1, 0, he), Q(e1, 0, Hb), Q(e0, 0, Hb), 'stone_ashlar')
        bk.quad(Q(e0, 2.5, 0), Q(e1, 2.5, 0), Q(e1, 2.5, he), Q(e0, 2.5, he), 'void_black')        # its dark back
        bk.quad(Q(e1, 0, 0), Q(e1, 2.5, 0), Q(e1, 2.5, he), Q(e1, 0, he), 'void_black')
        bk.quad(Q(e0, 2.5, 0), Q(e0, 0, 0), Q(e0, 0, he), Q(e0, 2.5, he), 'void_black')
        bk.quad(Q(e0, 0, he), Q(e0, 2.5, he), Q(e1, 2.5, he), Q(e1, 0, he), 'void_black')          # its soffit
        bk.quad(Q(e0, 0, 0.02), Q(e1, 0, 0.02), Q(e1, 2.5, 0.02), Q(e0, 2.5, 0.02), 'stone_granite')
        bk.quad(Q(e0 + 0.4, 2.45, 0.05), Q(e1 - 0.4, 2.45, 0.05), Q(e1 - 0.4, 2.45, he - 0.3), Q(e0 + 0.4, 2.45, he - 0.3), 'glass')
        # west side with its dark door
        bk.quad(Q(0, d0, -3), Q(0, 0, -3), Q(0, 0, Hb), Q(0, d0, Hb), 'stone_ashlar')
        bk.quad(Q(0, S, -3), Q(0, d1, -3), Q(0, d1, Hb), Q(0, S, Hb), 'stone_ashlar')
        bk.quad(Q(0, d1, hd), Q(0, d0, hd), Q(0, d0, Hb), Q(0, d1, Hb), 'stone_ashlar')
        bk.quad(Q(0.6, d1, 0), Q(0.6, d0, 0), Q(0.6, d0, hd), Q(0.6, d1, hd), 'void_black')
        bk.quad(Q(0, d0, 0), Q(0.6, d0, 0), Q(0.6, d0, hd), Q(0, d0, hd), 'void_black')
        bk.quad(Q(0.6, d1, 0), Q(0, d1, 0), Q(0, d1, hd), Q(0.6, d1, hd), 'void_black')
        bk.quad(Q(0, d0, hd), Q(0.6, d0, hd), Q(0.6, d1, hd), Q(0, d1, hd), 'void_black')
        # north side (mostly against the podium), the roof with a coping, and a band of joints like the podium's
        bk.quad(Q(0, S, -3), Q(F, S, -3), Q(F, S, Hb), Q(0, S, Hb), 'stone_ashlar')
        bk.quad(Q(F, 0, -3), Q(F, S, -3), Q(F, S, Hb), Q(F, 0, Hb), 'stone_ashlar')
        bk.face([Q(0, 0, Hb), Q(F, 0, Hb), Q(F, S, Hb), Q(0, S, Hb)], 'roof_flat')
        for (a0, a1, b0, b1) in ((0, F, 0, 0), (0, 0, 0, S)):
            bk.box(((Q(a0, b0, 0)[0] + Q(a1, b1, 0)[0]) / 2, (Q(a0, b0, 0)[1] + Q(a1, b1, 0)[1]) / 2, z0 + Hb + 0.2),
                   (math.hypot(Q(a1, b1, 0)[0] - Q(a0, b0, 0)[0], Q(a1, b1, 0)[1] - Q(a0, b0, 0)[1]) + 0.3, 0.45, 0.4),
                   'stone_ashlar', rotz=math.atan2(Q(a1, b1, 0)[1] - Q(a0, b0, 0)[1], Q(a1, b1, 0)[0] - Q(a0, b0, 0)[0]))
        bk.quad(Q(e1, 0, 2.9, 0.04), Q(F, 0, 2.9, 0.04), Q(F, 0, 3.02, 0.04), Q(e1, 0, 3.02, 0.04), 'concrete_dark')
        # the light wall stepping up from the block's west side towards the porch (photo x 1500 - 1562)
        for (a0, a1, top) in K['parapet']:
            pa, pb = Q(0, a0, 0), Q(0, a1, 0)
            bk.box(((pa[0] + pb[0]) / 2, (pa[1] + pb[1]) / 2, z0 + top / 2 - 1.5), (math.hypot(pb[0] - pa[0], pb[1] - pa[1]), 0.5, top + 3.0),
                   'stone_ashlar', rotz=math.atan2(pb[1] - pa[1], pb[0] - pa[0]))
        out.append(bk)
    return out


# ============================================================================= gothic stone halls
def win_holes(L, z0, nfl, fh, bay, ww=0.6, sill=0.9, head=0.6, s_start=0.0, s_end=None):
    """Window openings of window_grid() with the same arguments, as (s0, s1, z0, z1) rectangles."""
    s_end = L if s_end is None else s_end
    nb = max(1, int(round((s_end - s_start) / bay)))
    bw = (s_end - s_start) / nb
    out = []
    for f in range(nfl):
        zf = z0 + f * fh
        for k in range(nb):
            w = bw * ww
            w0 = s_start + k * bw + (bw - w) / 2
            out.append((w0, w0 + w, zf + sill, zf + fh - head))
    return out


def ivy_patch(iv, P, s0, s1, z0, z1, density, seedoff=0, holes=(), top=None, cover=1.0):
    """Boston ivy (담쟁이) on a wall rectangle, as leaf cards.

    As in the photos of 언더우드관 (1990s - 2023): the vines climb from the foot of the wall in broad vertical
    strands that merge into an almost continuous mat; each strand reaches its own height (most of them the
    eaves), and the window openings stay clear (the leaves only lap over their edges).
    holes: (s0, s1, z0, z1) openings to keep clear; top(s): wall top for gables; cover: 0..1 how much of the
    wall the strands cover."""
    r = random.Random(int(s0 * 13 + z0 * 7 + seedoff * 101))
    H = z1 - z0
    ph = r.uniform(0, 6.283)

    def reach(s):      # how high the strand rooted at s has climbed (fraction of the wall)
        return (0.62 + 0.55 * cover + 0.22 * math.sin(s * 0.23 + ph) + 0.12 * math.sin(s * 0.71 + 2 * ph)
                + 0.08 * math.sin(s * 1.9 + ph))

    def thick(s, z):   # gaps between strands, and thinner growth near the top of each strand
        g = 0.5 + 0.5 * math.sin(s * 1.15 + ph + 0.6 * math.sin(z * 0.3 + s * 0.2))
        return cover * (0.62 + 0.38 * g)

    hl = [(a - 0.15, b + 0.15, c - 0.15, d + 0.1) for a, b, c, d in holes]
    area = (s1 - s0) * H
    for k in range(int(area * density)):
        s = r.uniform(s0, s1)
        z = z0 + H * (r.random() ** 0.85)                  # a little denser near the ground
        zt = z1 if top is None else min(z1, top(s))
        if z > zt:
            continue
        f = (z - z0) / H
        rf = reach(s)
        if f > rf:
            continue
        edge = 1.0 - max(0.0, (f - (rf - 0.18)) / 0.18)    # strand tips thin out
        if r.random() > thick(s, z) * edge:
            continue
        if any(a < s < b and c < z < d for a, b, c, d in hl):
            continue
        sz = r.uniform(0.5, 0.95)
        off = r.uniform(0.04, 0.2)
        a = r.uniform(0, 6.283)
        ca, sa = math.cos(a) * sz / 2, math.sin(a) * sz / 2
        cell = r.randrange(4)
        u0, v0 = (cell % 2) * 0.5, (cell // 2) * 0.5
        dz = r.uniform(-0.1, 0.1)
        iv.face([P(s - ca + sa, z - sa - ca, off), P(s + ca + sa, z + sa - ca, off + dz),
                 P(s + ca - sa, z + sa + ca, off), P(s - ca - sa, z - sa + ca, off - dz)], 'leaf_ivy',
                uvs=[(u0, v0), (u0 + .5, v0), (u0 + .5, v0 + .5), (u0, v0 + .5)])


WALK_FACES = []       # world-space quads (4 points each): the smoothed surface of every flight, exported as the invisible
                      # 'walk_stairs' mesh the walker is raycast against (web/src/main.js)


def local_ground(mb):
    """Terrain height in a builder's local frame (relative to its z origin): ground_local(lx, ly).  The top of the
    bilinear and the drawn (triangulated) surface, so that what is placed on it is never buried."""
    def g(lx, ly):
        w = mb.xf @ Vector((lx, ly, 0.0))
        return ground_top(w.x, w.y) - mb.xf.translation.z
    return g


def across(gfn, x0, x1, y, n=6):
    """Highest ground along the line y from x0 to x1: a flight's foot has to clear the whole width, not just its middle
    (on a cross slope the uphill end of the bottom tread went under the grass)."""
    return max(gfn(x0 + (x1 - x0) * k / n, y) for k in range(n + 1))


def lift_base(z0, cx, cy, ang, d, zl, rise):
    """Raise a building's floor so the landing zl stands `rise` m above the ground d m in front of its wall."""
    g = ground(cx + math.sin(ang) * d, cy - math.cos(ang) * d)
    return max(z0, g - zl + rise)


def walk_mesh():
    mb = MeshBuilder('walk_stairs')
    for q in WALK_FACES:
        mb.face(q, 'concrete')
        mb.face(q[::-1], 'concrete')
    WALK_FACES.clear()
    return mb


def stair_flight(mb, x, y_face, width, zl, n=8, mat='stone_granite', landing=1.8, tread=0.36, flare=0.35,
                 cheek=0.0, cheek_mat=None, newel=False, rail=False, ground=-1.2, zbot=-0.15, gfn=None, maxrise=0.18):
    """A straight entrance flight in a builder's local frame, going down towards -y from the wall at y_face.
    zl: top of the landing in front of the door; n risers (rise = (zl - ground_level) / n, ground_level ~ -0.15);
    each tread is a solid block down to `ground`, the lowest ones a little wider (flare) like the real granite steps.
    cheek: thickness of the low sloped side walls (0 = none); newel: a squared post with a cap at the foot of each;
    rail: slim metal handrails along the flight."""
    cheek_mat = cheek_mat or mat
    if gfn is not None:
        # as many risers as the ground in front needs: the foot of the flight stands on the terrain, all across it
        hf0 = width / 2 + flare
        for n in range(2, 19):
            zbot = across(gfn, x - hf0, x + hf0, y_face - landing - n * tread) - 0.04
            if (zl - zbot) / n <= maxrise:
                break
        zbot = min(zbot, zl - 0.2)
        ground = min(ground, zbot - 1.0)
    rise = (zl - zbot) / n
    mb.box((x, y_face - landing / 2 + 0.6, (zl + ground) / 2), (width, landing + 1.2, zl - ground), mat,
           mats={'top': mat})                                               # landing, running into the recess
    for k in range(1, n + 1):
        top = zl - k * rise
        y1 = y_face - landing - (k - 1) * tread
        w = width + 2 * flare * (k / n)
        mb.box((x, y1 - tread / 2 + 0.02, (top + ground) / 2), (w, tread + 0.04, top - ground), mat)
    y_foot = y_face - landing - n * tread
    # walkable surface: the landing and one smooth ramp through the middle of the treads
    hw = width / 2
    W_ = lambda lx, ly, lz: tuple(mb.xf @ Vector((lx, ly, lz)))
    # (the landing runs 1.2 m on into a recessed doorway, e.g. 대우관 별관's: walked on all the way to the door)
    WALK_FACES.append([W_(x - hw, y_face + 1.15, zl), W_(x + hw, y_face + 1.15, zl), W_(x + hw, y_face - landing, zl), W_(x - hw, y_face - landing, zl)])
    hf_ = hw + flare
    WALK_FACES.append([W_(x - hw, y_face - landing, zl), W_(x + hw, y_face - landing, zl), W_(x + hf_, y_foot, zbot), W_(x - hf_, y_foot, zbot)])
    if cheek:
        for sg in (-1, 1):
            xo = x + sg * (width / 2 + flare * 0.6 + cheek / 2)
            hz0, hz1 = zl + 0.55, zbot + 0.35
            # sloped coping wall: a wedge from the landing down to the foot of the flight
            ya, yb = y_face + 0.4, y_foot - 0.1
            xa, xb = xo - cheek / 2, xo + cheek / 2
            pts = lambda yy, zz, xx: (xx, yy, zz)
            for (x0, x1) in ((xa, xb),):
                mb.quad((x0, yb, ground), (x0, ya, ground), (x0, ya, hz0), (x0, yb, hz1), cheek_mat) if sg < 0 else \
                    mb.quad((x1, ya, ground), (x1, yb, ground), (x1, yb, hz1), (x1, ya, hz0), cheek_mat)
            mb.quad((xa, yb, hz1), (xb, yb, hz1), (xb, ya, hz0), (xa, ya, hz0), cheek_mat)       # sloping top
            mb.quad((xa, yb, ground), (xa, yb, hz1), (xb, yb, hz1), (xb, yb, ground), cheek_mat)  # foot end
            mb.quad((xb, ya, ground), (xb, ya, hz0), (xa, ya, hz0), (xa, ya, ground), cheek_mat)  # wall end
            if newel:
                mb.box((xo, yb + 0.1, hz1 + 0.35), (cheek + 0.2, cheek + 0.2, 0.9), cheek_mat)
                mb.box((xo, yb + 0.1, hz1 + 0.85), (cheek + 0.35, cheek + 0.35, 0.18), 'stone_trim')
    if rail:
        for sg in (-1, 1):
            xr = x + sg * (width / 2 + 0.05)
            yb, ya = y_foot + 0.2, y_face - landing + 0.3
            hb, ha = zbot + 0.95, zl + 0.95
            nr = 12
            for j in range(nr):
                t0, t1 = j / nr, (j + 1) / nr
                mb.quad((xr - 0.025, yb + (ya - yb) * t0, hb + (ha - hb) * t0), (xr + 0.025, yb + (ya - yb) * t0, hb + (ha - hb) * t0),
                        (xr + 0.025, yb + (ya - yb) * t1, hb + (ha - hb) * t1), (xr - 0.025, yb + (ya - yb) * t1, hb + (ha - hb) * t1), 'metal_dark')
            for yy in (yb, ya):
                zz = hb + (ha - hb) * ((yy - yb) / (ya - yb))
                mb.box((xr, yy, zz - 0.45), (0.06, 0.06, 0.9), 'metal_dark')
    note_entrance(mb, width / 2 + flare + cheek + 0.6, y_face + 1.2, y_foot - 1.0, x)
    return y_foot


def lamp_post(mb, x, y, h=3.6, globe='plaster_white', z=0.0):
    """A cast-iron post with a white globe lamp, like those beside the 대우관 별관 steps (standing on z)."""
    mb.cylinder((x, y), 0.09, z - 0.6, z + h, 'metal_dark', seg=8, cap_top=False)
    mb.cylinder((x, y), 0.17, z - 0.6, z + 0.3, 'metal_dark', seg=8, cap_top=False)
    mb.cylinder((x, y), 0.2, z + h, z + h + 0.22, globe, seg=12, r1=0.3)
    mb.cylinder((x, y), 0.3, z + h + 0.22, z + h + 0.5, globe, seg=12, r1=0.2)
    mb.cylinder((x, y), 0.22, z + h + 0.5, z + h + 0.6, 'metal_dark', seg=10)


ENTRANCES = []        # world-space zones over every entrance flight (web/public/data/entrances.json): the web app
                      # moves the clipped shrubs of the building aprons off the steps


def note_entrance(mb, hw, y0, y1, x=0.0):
    """Record the zone |x' - x| <= hw, y1 <= y <= y0 (local frame, the flight going down towards -y) of a flight."""
    o = mb.xf @ Vector((x, y0, 0.0))
    u = (mb.xf.to_3x3() @ Vector((1.0, 0.0, 0.0))).normalized()
    v = (mb.xf.to_3x3() @ Vector((0.0, -1.0, 0.0))).normalized()
    ENTRANCES.append(dict(o=[round(o.x, 2), round(o.y, 2)], u=[round(u.x, 4), round(u.y, 4)], v=[round(v.x, 4), round(v.y, 4)],
                          hw=round(hw, 2), len=round(y0 - y1, 2)))


def bar(mb, P, sa, za, sb, zb, w, d0, d1, mat, ends=False):
    """A square-section member in a wall plane P(s, z, d) from (sa, za) to (sb, zb), w wide, from depth d0 to d1."""
    ds, dz = sb - sa, zb - za
    L = math.hypot(ds, dz) or 1e-6
    ns, nz = -dz / L * w / 2, ds / L * w / 2
    A, B, C, D = (sa + ns, za + nz), (sb + ns, zb + nz), (sb - ns, zb - nz), (sa - ns, za - nz)
    mb.quad(P(*D, d1), P(*C, d1), P(*B, d1), P(*A, d1), mat)
    mb.quad(P(*A, d1), P(*B, d1), P(*B, d0), P(*A, d0), mat)
    mb.quad(P(*C, d1), P(*D, d1), P(*D, d0), P(*C, d0), mat)
    if ends:
        mb.quad(P(*D, d0), P(*D, d1), P(*A, d1), P(*A, d0), mat)
        mb.quad(P(*B, d0), P(*B, d1), P(*C, d1), P(*C, d0), mat)


# glazing of the old halls' front doors, from the photos: 언더우드관 a pair of leaves of small square panes under a
# glazed transom (reference/언더우드관_정면_2016.jpg, 언더우드관_2024_여름_정원.jpg), 스팀슨관 and 아펜젤러관 dark leaves
# glazed above a solid lower panel (reference/스팀슨관_정면_2016.jpg, 아펜젤러관_정면_2016.jpg), 연희관 four glazed
# leaves under a transom of upright panes (reference/연희관_정면_2023.jpg),
# 대우관 plain dark-framed glass (reference/대우관_정면_전경.jpg).  All black-painted steel, none of them wooden.
DOOR_STYLES = {
    #          leaves, panes across x up per leaf (0 = one pane), solid lower panel, members, transom panes
    'grid':   dict(leaves=2, cols=3, rows=5, panel=0.22, fw=0.09, mw=0.035, tcols=3),
    'panel':  dict(leaves=2, cols=2, rows=3, panel=0.95, fw=0.1, mw=0.04, tcols=2),
    'four':   dict(leaves=4, cols=2, rows=5, panel=0.2, fw=0.08, mw=0.035, tcols=2, plain_inner=True),
    'modern': dict(leaves=4, cols=0, rows=0, panel=0.12, fw=0.07, mw=0.0, tcols=1),
}


def glazed_door(mb, P, s0, s1, zd, zs, kind, d, style='grid'):
    """Black steel-framed glass doors and transom filling an arched opening [s0, s1] at depth d of a wall P."""
    st = DOOR_STYLES[style]
    apts = arch_points(s0, s1, zs, kind, 14)

    def arch_z(s):
        for (sa, za), (sb, zb) in zip(apts, apts[1:]):
            if sa <= s <= sb:
                return za + (zb - za) * (s - sa) / max(sb - sa, 1e-6)
        return zs
    F, G, H = 'door_frame', 'glass_door', 'frame_silver'
    fw, mw = st['fw'], st['mw']
    f0, f1 = d, d + 0.07                    # frame depth: glass at the back, members standing in front
    m1 = d + 0.04
    zt = min(zd + 2.45, zs - 0.08)          # head of the leaves = transom bar
    mb.quad(P(s0, zd, d), P(s1, zd, d), P(s1, zs, d), P(s0, zs, d), G)
    for (sa, za), (sb, zb) in zip(apts, apts[1:]):
        mb.quad(P(sa, zs, d), P(sb, zs, d), P(sb, zb, d), P(sa, za, d), G)
    # outer frame: jambs, the arch, the transom bar
    bar(mb, P, s0 + fw / 2, zd, s0 + fw / 2, zs, fw, f0, f1, F)
    bar(mb, P, s1 - fw / 2, zd, s1 - fw / 2, zs, fw, f0, f1, F)
    for (sa, za), (sb, zb) in zip(apts, apts[1:]):
        bar(mb, P, sa, za - fw / 2, sb, zb - fw / 2, fw, f0, f1, F)
    bar(mb, P, s0, zt, s1, zt, fw * 1.3, f0, f1 + 0.01, F)
    nlv = st['leaves']
    lw = (s1 - s0) / nlv
    lines = []
    for k in range(nlv):
        a, b = s0 + k * lw, s0 + (k + 1) * lw
        if k:
            bar(mb, P, a, zd, a, zt, fw * 1.2, f0, f1 + 0.01, F)          # meeting stiles
        lines.append(a)
        ia, ib = a + fw / 2, b - fw / 2
        zp = zd + st['panel']
        if st['panel'] > 0.3:            # solid lower panel with a raised field
            mb.quad(P(ia, zd, m1), P(ib, zd, m1), P(ib, zp, m1), P(ia, zp, m1), F)
            mb.quad(P(ia + 0.12, zd + 0.12, m1 + 0.015), P(ib - 0.12, zd + 0.12, m1 + 0.015), P(ib - 0.12, zp - 0.12, m1 + 0.015),
                    P(ia + 0.12, zp - 0.12, m1 + 0.015), F)
        bar(mb, P, ia, zp, ib, zp, fw, f0, f1, F)                           # bottom rail
        if st['panel'] <= 0.3:
            mb.quad(P(ia, zd, m1), P(ib, zd, m1), P(ib, zp - fw / 2, m1), P(ia, zp - fw / 2, m1), F)
        cols, rows = st['cols'], st['rows']
        if st.get('plain_inner') and 0 < k < nlv - 1:
            cols, rows = 1, 2
        for c in range(1, cols):
            s = ia + (ib - ia) * c / cols
            bar(mb, P, s, zp, s, zt, mw, f0, m1 + 0.02, F)
        for r in range(1, rows):
            z = zp + (zt - zp) * r / rows
            bar(mb, P, ia, z, ib, z, mw if cols > 1 else fw, f0, m1 + 0.02, F)
        if k in (nlv // 2 - 1, nlv // 2):
            hs = b - 0.16 if k == nlv // 2 - 1 else a + 0.16
            bar(mb, P, hs, zd + 0.95, hs, zd + 1.3, 0.03, f1, f1 + 0.06, H, ends=True)   # pull handles
    lines.append(s1)
    # transom: upright bars under the arch on the leaf lines (and between them)
    tc = max(1, st['tcols'])
    for k in range(nlv):
        for c in range(tc):
            s = lines[k] + (lines[k + 1] - lines[k]) * c / tc
            if s0 + 0.05 < s < s1 - 0.05:
                bar(mb, P, s, zt, s, arch_z(s) - 0.03, mw * 1.4 if c else fw, f0, m1 + 0.02, F)


def vestibule(mb, P, s0, s1, zf, zc, d0, depth, lights=2):
    """The entrance hall behind a glazed front door (issue #5; reference/언더우드관_정면_2016.jpg and
    언더우드관_2024_여름_정원.jpg show a bright hall and its far windows through the panes, 연희관_정면_2023.jpg the lit
    lobby through an open leaf): a shallow room [s0, s1] x [zf, zc] reaching `depth` m in from the door plane d0 of the
    wall P(s, z, d) (d < 0 inwards).  Pale stone floor, plastered walls with a stone dado, a coffered ceiling with
    lamps, and a pair of dark inner doors in the back wall.  The surfaces glow a little of their own, as no sunlight
    reaches in."""
    d1 = d0 - depth
    mb.quad(P(s0, zf, d0), P(s1, zf, d0), P(s1, zf, d1), P(s0, zf, d1), 'hall_floor')
    mb.quad(P(s0, zc, d1), P(s1, zc, d1), P(s1, zc, d0), P(s0, zc, d0), 'hall_wall')
    zw = zf + 1.0                                                  # stone dado below the plaster
    for s, sg in ((s0, 1), (s1, -1)):
        a, b = (d0, d1) if sg > 0 else (d1, d0)
        mb.quad(P(s, zf, a), P(s, zf, b), P(s, zw, b), P(s, zw, a), 'hall_floor')
        mb.quad(P(s, zw, a), P(s, zw, b), P(s, zc, b), P(s, zc, a), 'hall_wall')
    mb.quad(P(s0, zf, d1), P(s1, zf, d1), P(s1, zw, d1), P(s0, zw, d1), 'hall_floor')
    mb.quad(P(s0, zw, d1), P(s1, zw, d1), P(s1, zc, d1), P(s0, zc, d1), 'hall_wall')
    sm, dw = (s0 + s1) / 2, min(1.8, (s1 - s0) * 0.45)            # inner doors further in
    zt = min(zf + 2.4, zc - 0.25)
    mb.quad(P(sm - dw / 2, zf + 0.01, d1 + 0.02), P(sm + dw / 2, zf + 0.01, d1 + 0.02), P(sm + dw / 2, zt, d1 + 0.02),
            P(sm - dw / 2, zt, d1 + 0.02), 'wood_dark')
    bar(mb, P, sm, zf, sm, zt, 0.04, d1 + 0.02, d1 + 0.05, 'door_frame')
    bar(mb, P, sm - dw / 2 - 0.06, zt + 0.03, sm + dw / 2 + 0.06, zt + 0.03, 0.12, d1 + 0.02, d1 + 0.08, 'stone_trim', ends=True)
    for k in range(lights):                                        # ceiling lamps
        dd = d0 - depth * (k + 0.5) / lights
        mb.quad(P(sm - 0.35, zc - 0.03, dd - 0.35), P(sm + 0.35, zc - 0.03, dd - 0.35), P(sm + 0.35, zc - 0.03, dd + 0.35),
                P(sm - 0.35, zc - 0.03, dd + 0.35), 'hall_light')


def shopfront(mb, P, s0, s1, z0, z1, d, bays=6, door_h=2.35):
    """A modern aluminium-framed glass screen filling [s0, s1] x [z0, z1] at depth d of a wall P: fixed lights, a pair
    of glass doors in the middle bay(s), a transom bar over them (대우관's door under its podium arch)."""
    G, F = 'glass_door', 'frame_silver'
    mb.quad(P(s0, z0, d), P(s1, z0, d), P(s1, z1, d), P(s0, z1, d), G)
    f0, f1 = d, d + 0.08
    zt = z0 + door_h
    for k in range(bays + 1):
        s = s0 + (s1 - s0) * k / bays
        bar(mb, P, s, z0, s, z1, 0.09, f0, f1, F)
    for z in (z0 + 0.05, zt, z1 - 0.05):
        bar(mb, P, s0, z, s1, z, 0.1, f0, f1, F)
    mid = [(s0 + (s1 - s0) * k / bays) for k in (bays // 2 - 1, bays // 2, bays // 2 + 1)]
    for a, b in zip(mid, mid[1:]):                                  # the two door leaves: handles and kick rails
        hs = b - 0.18 if a == mid[0] else a + 0.18
        bar(mb, P, hs, z0 + 0.85, hs, z0 + 1.5, 0.035, f1, f1 + 0.07, F, ends=True)
        bar(mb, P, a, z0 + 0.22, b, z0 + 0.22, 0.2, f0, f1, F)


def sloped_wall(mb, x0, x1, prof, gnd, wall, cap='stone_trim', ct=0.14):
    """A solid side wall between x0 < x1 whose top follows prof [(y, z), ...] (y decreasing), down to gnd, with a pale
    stone coping ct deep along its top."""
    for (ya, za), (yb, zb) in zip(prof, prof[1:]):
        for x, sg in ((x0, -1), (x1, 1)):
            q = [(x, ya, gnd), (x, yb, gnd), (x, yb, zb - ct), (x, ya, za - ct)]
            c = [(x, ya, za - ct), (x, yb, zb - ct), (x, yb, zb), (x, ya, za)]
            if sg > 0:
                q, c = q[::-1], c[::-1]
            mb.face(q, wall)
            mb.face(c, cap)
        mb.quad((x0, ya, za), (x0, yb, zb), (x1, yb, zb), (x1, ya, za), cap)
    (ya, za), (yb, zb) = prof[0], prof[-1]
    mb.quad((x1, ya, gnd), (x0, ya, gnd), (x0, ya, za), (x1, ya, za), wall)
    mb.quad((x0, yb, gnd), (x1, yb, gnd), (x1, yb, zb), (x0, yb, zb), wall)


def pedestal(mb, x, y, top, gnd, wall, w=0.64):
    """A square stone post at the ends of a flight: rubble shaft, pale cap with a low hipped top."""
    mb.box((x, y, (gnd + top - 0.3) / 2), (w, w, top - 0.3 - gnd), wall, skip=('bottom',))
    mb.box((x, y, top - 0.21), (w + 0.12, w + 0.12, 0.18), 'stone_trim', skip=('bottom',))
    h0, h1, a, b = top - 0.12, top, (w + 0.06) / 2, 0.14
    for (p, q) in (((-1, -1), (1, -1)), ((1, -1), (1, 1)), ((1, 1), (-1, 1)), ((-1, 1), (-1, -1))):
        mb.face([(x + p[0] * a, y + p[1] * a, h0), (x + q[0] * a, y + q[1] * a, h0),
                 (x + q[0] * b, y + q[1] * b, h1), (x + p[0] * b, y + p[1] * b, h1)], 'stone_trim')
    mb.face([(x - b, y - b, h1), (x + b, y - b, h1), (x + b, y + b, h1), (x - b, y + b, h1)], 'stone_trim')


def hall_steps(mb, y_face, zl, wu, gfn, wall='stone_rubble', mat='stone_step', rec=0.9, porch=1.3, tread=0.35,
               maxrise=0.16, wl=None, cheeks=True, lamps=False, zone_hw=0.0):
    """The entrance steps of the old stone halls, as in reference/언더우드관_정면_2016.jpg, 스팀슨관_정면_2016.jpg and
    아펜젤러관_정면_2016.jpg:
    a porch from the door out past the arch, then granite treads of ~15 cm risers and 35 cm goings; flights of nine
    risers or more break at a landing, the lower flight a little wider.  Low rubble side walls with a pale coping
    follow the flights and end in square capped posts at the porch, at the landing and at the foot.
    Local frame: the door wall faces -y at y_face (the door itself rec m back), the porch top is zl.  Returns the
    y of the foot."""
    wl = wl or wu + 1.4
    T = tread
    y_p = y_face - porch
    for n in range(2, 31):
        split = n >= 9
        nl = max(3, round(n * 0.36)) if split else 0
        nu = n - nl
        mid = 1.6 if split else 0.0
        y_foot = y_p - (nu - 1) * T - mid - (nl - 1) * T if split else y_p - (n - 1) * T
        hx = (wl if split else wu) / 2 + (0.5 if cheeks else 0.0)
        zbot = across(gfn, -hx, hx, y_foot - 0.6) - 0.03
        if (zl - zbot) / n <= maxrise:
            break
    zbot = min(zbot, zl - 0.3)
    rise = (zl - zbot) / n
    gnd = min(-1.2, zbot - 1.0)
    ct = 0.5 if cheeks else 0.0
    hu, hl = wu / 2, wl / 2
    yw = y_face + rec
    mb.box((0, (yw + y_p) / 2, (zl + gnd) / 2), (wu + 2 * ct, yw - y_p, zl - gnd), mat, skip=('bottom',))   # porch
    nup = nu if split else n
    for k in range(1, nup):
        top = zl - k * rise
        mb.box((0, y_p - (k - 0.5) * T + 0.01, (top + gnd) / 2), (wu, T + 0.02, top - gnd), mat, skip=('bottom',))
    W_ = lambda lx, ly, lz: tuple(mb.xf @ Vector((lx, ly, lz)))

    def walk(x0, x1, ya, za, yb, zb):
        WALK_FACES.append([W_(x0, ya, za), W_(x1, ya, za), W_(x1, yb, zb), W_(x0, yb, zb)])
    walk(-hu, hu, yw - 0.05, zl, y_p, zl)
    xu, xl = hu + ct / 2, hl + ct / 2
    if split:
        zm = zl - nu * rise
        yb_ = y_p - (nu - 1) * T                 # back edge of the landing
        y_m = yb_ - mid                          # its nosing
        mb.box((0, (yb_ + y_m) / 2, (zm + gnd) / 2), (wl, mid, zm - gnd), mat, skip=('bottom',))
        for j in range(1, nl):
            top = zm - j * rise
            mb.box((0, y_m - (j - 0.5) * T + 0.01, (top + gnd) / 2), (wl, T + 0.02, top - gnd), mat, skip=('bottom',))
        walk(-hu, hu, y_p, zl, y_p - nu * T, zm)
        walk(-hl, hl, yb_, zm, y_m, zm)
        walk(-hl, hl, y_m, zm, y_m - nl * T, zbot)
        if cheeks:
            for sg in (-1, 1):
                x0, x1 = sorted((sg * hu, sg * (hu + ct)))
                sloped_wall(mb, x0, x1, [(y_face, zl + 0.78), (y_p, zl + 0.78), (yb_ + 0.2, zm + rise + 0.78)], gnd, wall)
                pedestal(mb, sg * xu, y_p + 0.25, zl + 1.08, gnd, wall)
                pedestal(mb, sg * xu, yb_ + 0.05, zm + 1.0, gnd, wall)
                x0, x1 = sorted((sg * hl, sg * (hl + ct)))
                sloped_wall(mb, x0, x1, [(yb_ + 0.3, zm + 0.72), (y_m, zm + 0.72), (y_foot + 0.1, zbot + rise + 0.68)], gnd, wall)
                pedestal(mb, sg * xl, y_m + 0.25, zm + 0.98, gnd, wall)
                pedestal(mb, sg * xl, y_foot + 0.25, zbot + 0.95, gnd, wall)
    else:
        walk(-hu, hu, y_p, zl, y_p - n * T, zbot)
        if cheeks:
            for sg in (-1, 1):
                x0, x1 = sorted((sg * hu, sg * (hu + ct)))
                sloped_wall(mb, x0, x1, [(y_face, zl + 0.78), (y_p, zl + 0.78), (y_foot + 0.1, zbot + rise + 0.7)], gnd, wall)
                pedestal(mb, sg * xu, y_p + 0.25, zl + 1.08, gnd, wall)
                pedestal(mb, sg * xu, y_foot + 0.25, zbot + 0.97, gnd, wall)
    if lamps:
        for sg in (-1, 1):
            lamp_post(mb, sg * (max(hu, hl if split else hu) + 1.9), y_foot - 0.5)
    note_entrance(mb, max(zone_hw, (hl if split else hu) + ct + 0.6), y_face + 0.5, y_foot - 1.0)
    return y_foot


def flat_portal(mb, W, plinth, fh, wall, bw=7.4, gfn=None):
    """대우관 별관's front door (reference/대우관_별관_정면_현관.jpg): a squared, slightly projecting central bay
    in pale stone, a rectangular glass double door deep in a recess under a flat lintel carrying a round medallion,
    stepped pilasters, red diamond tiles beside it, rusticated blocks on the wall corners, and two flights of steps with
    stone planters and round shrubs.  Local frame: front is -y, the wall plane is y = -W/2."""
    y0, pj = -W / 2, 1.3
    yf = y0 - pj
    zb = plinth + fh + 1.4                      # top of the bay
    ow, zo = 3.5, plinth + 3.7                  # opening width / top
    zd = plinth - 0.1                           # threshold
    for sg in (-1, 1):                          # piers either side of the opening
        xc = sg * (ow + (bw - ow) / 2) / 2 + sg * ow / 4 * 0
        mb.box((sg * (ow / 2 + (bw - ow) / 4), y0 - pj / 2, (zb - 0.5) / 2), ((bw - ow) / 2, pj, zb + 0.5), wall)
        mb.box((sg * (bw / 2 - 0.2), yf - 0.1, (zb + zd) / 2), (0.4, 0.2, zb - zd), 'stone_trim')       # stepped pilaster
    mb.box((0, y0 - pj / 2, (zb + zo) / 2), (ow, pj, zb - zo), wall)                                 # lintel
    mb.box((0, yf - 0.1, zb + 0.12), (bw + 0.5, pj + 0.25, 0.26), 'stone_trim')                       # cornice
    mb.box((0, yf - 0.05, zo - 0.08), (ow + 0.3, 0.12, 0.16), 'stone_trim')
    # back of the recess with the glass double door and a glazed transom
    yb = y0 - 0.03
    mb.quad((-ow / 2, yb, zd), (ow / 2, yb, zd), (ow / 2, yb, zo), (-ow / 2, yb, zo), wall)
    dw, dh = 2.9, 3.0
    mb.quad((-dw / 2, yb - 0.02, zd), (dw / 2, yb - 0.02, zd), (dw / 2, yb - 0.02, zd + dh), (-dw / 2, yb - 0.02, zd + dh), 'glass')
    mb.quad((-dw / 2, yb - 0.02, zd + dh + 0.1), (dw / 2, yb - 0.02, zd + dh + 0.1), (dw / 2, yb - 0.02, zo - 0.15), (-dw / 2, yb - 0.02, zo - 0.15), 'glass')
    for x in (-dw / 2, 0.0, dw / 2):
        mb.box((x, yb - 0.05, (zd + zo - 0.15) / 2), (0.1, 0.06, zo - 0.15 - zd), 'frame_dark')
    for z in (zd + dh + 0.05, zd + 0.05, zo - 0.15):
        mb.box((0, yb - 0.05, z), (dw + 0.1, 0.06, 0.1), 'frame_dark')
    for sg in (-1, 1):
        mb.box((sg * (ow / 2 - 0.05), y0 - pj / 2, (zd + zo) / 2), (0.1, pj, zo - zd), 'stone_trim')    # reveals
    # round medallion over the door
    cz, r = (zo + zb) / 2 + 0.02, 0.5
    ring = [(r * math.cos(2 * math.pi * i / 16), cz + r * math.sin(2 * math.pi * i / 16)) for i in range(16)]
    mb.face([(x, yf - 0.02, z) for x, z in ring][::-1], 'stone_trim')
    ring2 = [(0.72 * x, cz + 0.72 * (z - cz)) for x, z in ring]
    mb.face([(x, yf - 0.05, z) for x, z in ring2][::-1], 'plaster_cream')
    # red diamond tiles and rusticated corner blocks on the wall either side of the bay
    for sg in (-1, 1):
        dx, dz = sg * (bw / 2 + 2.1), zb - 0.1
        mb.face([(dx, y0 - 0.03, dz - 0.32), (dx + 0.32, y0 - 0.03, dz), (dx, y0 - 0.03, dz + 0.32), (dx - 0.32, y0 - 0.03, dz)][::-1], 'brick_red')
        for k in range(5):
            mb.box((sg * (bw / 2 + 0.7), y0 - 0.05, plinth + 0.5 + k * 0.62), (0.8 if k % 2 else 0.55, 0.12, 0.5), 'stone_trim')
    # two flights: a narrow one to the door between planters, then a wide one with handrails
    zl = plinth - 0.1
    zm = zl / 2 + 0.05
    y1 = stair_flight(mb, 0, yf, ow + 1.1, zl, n=4, landing=1.2, tread=0.38, flare=0.0, zbot=zm)
    for sg in (-1, 1):
        px = sg * (ow / 2 + 0.55 + 0.9)
        ph = zl - zm + 0.85
        mb.box((px, (yf + y1) / 2, zm - 0.1 + ph / 2 - 0.05), (1.6, yf - y1 + 1.2, ph), 'stone_trim', mats={'top': 'soil'})
        for dxy, rr in (((0.0, 0.2), 0.85), ((0.0, -1.2), 0.6)):
            c = (px + dxy[0], (yf + y1) / 2 + dxy[1])
            mb.cylinder(c, rr, zm + ph - 0.15, zm + ph + 0.35, 'shrub_green', seg=10, r1=rr * 0.9)
            mb.cylinder(c, rr * 0.85, zm + ph + 0.35, zm + ph + 0.62, 'shrub_green', seg=10, r1=rr * 0.5)
    y2 = stair_flight(mb, 0, y1, 9.5, zm, n=5, landing=2.2, tread=0.36, flare=0.3, rail=True, gfn=gfn)
    for sg in (-1, 1):                                       # a round shrub at each side of the lower flight
        c = (sg * 6.4, y1 - 2.0)
        mb.cylinder(c, 1.0, -0.3, 0.7, 'shrub_green', seg=12, r1=1.05)
        mb.cylinder(c, 1.0, 0.7, 1.15, 'shrub_green', seg=12, r1=0.5)
    return y2


def stone_base(mb, poly, plinth, wall):
    """The basement storey of the stone halls: the wall's own stone down into the ground (dark granite under the white
    halls), and a pale water table where the ground floor starts."""
    if wall == 'stone_white':
        mb.prism(offset_poly(poly, 0.25), -4, plinth, 'stone_granite')
        return
    mb.prism(offset_poly(poly, 0.25), -4, plinth - 0.3, wall)
    mb.prism(offset_poly(poly, 0.33), plinth - 0.3, plinth, 'stone_trim', 'stone_trim')


def basement_windows(mb, P, s0, s1, bay, plinth, gfn, wall, ww=0.5):
    """Low windows of the half-sunk basement (반지하층 of 스팀슨관, 지하층 of 언더우드관 and 아펜젤러관), one under each
    ground-floor window, wherever the ground leaves them clear."""
    if wall == 'stone_white' or s1 - s0 < 1.0:
        return
    nb = max(1, int(round((s1 - s0) / bay)))
    bw = (s1 - s0) / nb
    z0, z1, d = plinth - 1.15, plinth - 0.45, 0.27
    for k in range(nb):
        sc, w = s0 + (k + 0.5) * bw, bw * ww
        g = [gfn(*P(sc + o, 0, 1.0)[:2]) for o in (-w / 2, w / 2)]
        if max(g) > z0 - 0.12:
            continue
        mb.quad(P(sc - w / 2, z0, d), P(sc + w / 2, z0, d), P(sc + w / 2, z1, d), P(sc - w / 2, z1, d), 'glass')
        bar(mb, P, sc, z0, sc, z1, 0.07, d, d + 0.05, 'frame_dark')
        bar(mb, P, sc - w / 2 - 0.1, z0 - 0.06, sc + w / 2 + 0.1, z0 - 0.06, 0.12, 0.25, d + 0.08, 'stone_trim', ends=True)
        bar(mb, P, sc - w / 2 - 0.06, z1 + 0.07, sc + w / 2 + 0.06, z1 + 0.07, 0.14, 0.25, d + 0.05, 'stone_trim', ends=True)


def gothic(name, b, front, floors, tower_w=8.5, tower_extra=8.0, ivy=1.0, wings=True, fh=4.1, wall='stone_rubble',
           dormers=True, stairs=None, portal=None, door=None, z_floor=None, rear=None):
    cx, cy, L, W, ang, z0 = frame_for(b, front)
    stairs = dict(dict(width=None, wl=None, rise=1.3, cheeks=True, lamps=False, none=False), **(stairs or {}))
    door = dict(dict(w=3.0, arch='tudor', spring=2.55, style='grid'), **(door or {}))
    # the floor stands on the ground in front of the door, not at the lowest corner of the footprint (the halls sit on
    # slopes: 대우관 별관's front is ~3 m above that corner and would bury the whole flight); `rise` is how high the
    # porch stands over the ground just in front of the hall.  z_floor: the door threshold given outright (대우관, whose
    # front ground build_campus.py has reshaped round its podium)
    if z_floor is None:
        z0 = lift_base(z0, cx, cy, ang, W / 2 + (1.8 if portal == 'flat' else 3.3), 1.2, stairs['rise'])
    else:
        z0 = z_floor - 1.2
    mb = MeshBuilder('lm_' + name)
    iv = MeshBuilder('lm_' + name + '_ivy')
    mb.xf = iv.xf = local_frame(cx, cy, ang, z0)
    plinth = 1.3
    Hw = plinth + floors * fh + 0.6
    pitch = 0.9
    gl = local_ground(mb)
    # --- main block walls
    body = rect(L, W)
    stone_base(mb, body, plinth, wall)
    for i in range(4):
        a, bb = body[i], body[(i + 1) % 4]
        P, Le, t, n = edge_P(a, bb)
        if Le < W + 0.1:          # gable ends
            window_grid(mb, P, Le, plinth, floors, fh, 3.4, wall, ww=0.42, trim='stone_trim', mull=1)
            basement_windows(mb, P, 0, Le, 3.4, plinth, gl, wall, ww=0.42)
            flat_wall(mb, P, 0, Le, plinth + floors * fh, Hw, wall)
            # gable triangle + coping
            hz = Hw + (Le / 2) * pitch
            mb.face([P(0, Hw), P(Le, Hw), P(Le / 2, hz)], wall)
            mb.quad(P(-0.2, Hw, 0.25), P(Le / 2, hz + 0.35, 0.25), P(Le / 2, hz + 0.35, -0.2), P(-0.2, Hw, -0.2), 'stone_trim')
            mb.quad(P(Le / 2, hz + 0.35, 0.25), P(Le + 0.2, Hw, 0.25), P(Le + 0.2, Hw, -0.2), P(Le / 2, hz + 0.35, -0.2), 'stone_trim')
            if ivy:
                ivy_patch(iv, P, 0, Le, 0, hz - 0.4, 5.5, i, cover=ivy,
                          holes=win_holes(Le, plinth, floors, fh, 3.4, ww=0.42),
                          top=lambda s, Le=Le: Hw + (Le / 2 - abs(s - Le / 2)) * pitch - 0.4)
        else:
            front_side = (i == 0)
            if not front_side and rear is not None:
                rear(mb, P, Le, plinth, floors, fh, Hw, wall)      # a back of its own (대우관), no buttresses
                continue
            if front_side:
                tw = tower_w
                s_t0, s_t1 = Le / 2 - tw / 2, Le / 2 + tw / 2
                if portal == 'flat':
                    window_grid(mb, P, Le, plinth, floors, fh, 3.3, wall, ww=0.55, trim='stone_trim', mull=2)
                else:
                    window_grid(mb, P, Le, plinth, floors, fh, 3.3, wall, ww=0.5, trim='stone_trim', mull=2, s_start=0, s_end=s_t0)
                    window_grid(mb, P, Le, plinth, floors, fh, 3.3, wall, ww=0.5, trim='stone_trim', mull=2, s_start=s_t1, s_end=Le)
                    flat_wall(mb, P, s_t0, s_t1, plinth, Hw, wall)
                    for (a_, b_) in ((0, s_t0), (s_t1, Le)):
                        if wings:      # the end pavilions stand in front of the outer bays
                            a_, b_ = max(a_, 8.0 if a_ == 0 else a_), min(b_, Le - 8.0 if b_ == Le else b_)
                        basement_windows(mb, P, a_, b_, 3.3, plinth, gl, wall)
            else:
                window_grid(mb, P, Le, plinth, floors, fh, 3.3, wall, ww=0.5, trim='stone_trim', mull=2)
                basement_windows(mb, P, 0, Le, 3.3, plinth, gl, wall)
            flat_wall(mb, P, 0, Le, plinth + floors * fh, Hw, wall)
            # buttresses
            nbut = int(round(Le / 6.6))
            for k in range(1, nbut):
                s = k * Le / nbut
                if front_side and abs(s - Le / 2) < tower_w / 2 + 1:
                    continue
                c = P(s, 0, 0.3)
                mb.box((c[0], c[1], plinth + (Hw - plinth - 1.5) / 2), (0.7, 0.6, Hw - plinth - 1.5), wall,
                       rotz=math.atan2(t.y, t.x), mats={'top': 'stone_trim'})
                if ivy:        # the vines climb the buttress fronts too
                    ivy_patch(iv, lambda ss, zz, dd=0.0: P(ss, zz, dd + 0.6), s - 0.4, s + 0.4, 0, Hw - 1.2, 5.5,
                              i * 3 + k * 17, cover=ivy)
            # parapet with battlements along the eaves
            nm = int(Le / 1.6)
            for k in range(nm):
                if k % 2 == 0:
                    c = P((k + 0.5) * Le / nm, Hw + 0.45, 0.0)
                    mb.box(c, (Le / nm, 0.45, 0.9), 'stone_trim', rotz=math.atan2(t.y, t.x), skip=('bottom',))
            if ivy:
                if front_side:
                    # (none behind the tower: hidden there anyway, and it would grow into the entrance hall)
                    holes = (win_holes(Le, plinth, floors, fh, 3.3, ww=0.5, s_end=s_t0)
                             + win_holes(Le, plinth, floors, fh, 3.3, ww=0.5, s_start=s_t1)
                             + ([(s_t0 - 0.3, s_t1 + 0.3, -1.0, Hw + 1.0)] if portal != 'flat' else []))
                else:
                    holes = win_holes(Le, plinth, floors, fh, 3.3, ww=0.5)
                ivy_patch(iv, P, 0, Le, 0, Hw + 0.3, 5.5, i * 3, cover=ivy, holes=holes)
    # --- slate roof (gable along L)
    hz = Hw + (W / 2) * pitch
    A, B, C, D = (-L / 2, -W / 2 - 0.3, Hw - 0.3 * pitch), (L / 2, -W / 2 - 0.3, Hw - 0.3 * pitch), (L / 2, W / 2 + 0.3, Hw - 0.3 * pitch), (-L / 2, W / 2 + 0.3, Hw - 0.3 * pitch)
    R1, R2 = (-L / 2, 0, hz), (L / 2, 0, hz)
    mb.face([A, B, R2, R1], 'roof_slate')
    mb.face([C, D, R1, R2], 'roof_slate')
    mb.box((0, 0, hz + 0.1), (L, 0.35, 0.3), 'metal_dark')
    # dormers on the front roof slope
    for k in (range(-2, 3) if dormers else ()):
        if k == 0:
            continue
        x = k * L / 6
        zb_ = Hw + 0.8
        mb.box((x, -W / 4 + 0.4, zb_ + 1.0), (1.8, 1.6, 2.0), wall, mats={'front': 'glass'})
        mb.face([(x - 1.0, -W / 4 - 0.5, zb_ + 2.0), (x + 1.0, -W / 4 - 0.5, zb_ + 2.0), (x, -W / 4 - 0.5, zb_ + 3.0)], 'stone_trim')
        mb.face([(x - 1.0, -W / 4 - 0.5, zb_ + 2.0), (x, -W / 4 - 0.5, zb_ + 3.0), (x, -W / 4 + 1.2, zb_ + 3.0), (x - 1.0, -W / 4 + 1.2, zb_ + 2.0)][::-1], 'roof_slate')
        mb.face([(x + 1.0, -W / 4 - 0.5, zb_ + 2.0), (x + 1.0, -W / 4 + 1.2, zb_ + 2.0), (x, -W / 4 + 1.2, zb_ + 3.0), (x, -W / 4 - 0.5, zb_ + 3.0)][::-1], 'roof_slate')
    # --- end pavilions projecting forward with front gables
    if wings:
        for sgn in (-1, 1):
            pw = 8.0
            x0 = sgn * (L / 2 - pw / 2)
            proj = 1.6
            yb = -W / 2 - proj
            P, Le, t, n = edge_P((x0 - pw / 2, yb), (x0 + pw / 2, yb))
            window_grid(mb, P, Le, plinth, floors, fh, 4.0, wall, ww=0.55, trim='stone_trim', mull=2)
            basement_windows(mb, P, 0, Le, 4.0, plinth, gl, wall, ww=0.55)
            flat_wall(mb, P, 0, Le, plinth + floors * fh, Hw, wall)
            ghz = Hw + pw / 2 * 1.1
            mb.face([P(0, Hw), P(Le, Hw), P(Le / 2, ghz)], wall)
            mb.quad(P(-0.2, Hw, 0.25), P(Le / 2, ghz + 0.35, 0.25), P(Le / 2, ghz + 0.35, -0.2), P(-0.2, Hw, -0.2), 'stone_trim')
            mb.quad(P(Le / 2, ghz + 0.35, 0.25), P(Le + 0.2, Hw, 0.25), P(Le + 0.2, Hw, -0.2), P(Le / 2, ghz + 0.35, -0.2), 'stone_trim')
            # sides of the projection
            for (sx, ex) in ((x0 - pw / 2, -1), (x0 + pw / 2, 1)):
                pa, pb = ((sx, -W / 2), (sx, yb)) if ex < 0 else ((sx, yb), (sx, -W / 2))
                P2, Le2, _, _ = edge_P(pa, pb)
                flat_wall(mb, P2, 0, Le2, -4, Hw, wall)
            stone_base(mb, [(x0 - pw / 2, yb), (x0 + pw / 2, yb), (x0 + pw / 2, -W / 2), (x0 - pw / 2, -W / 2)], plinth, wall)
            # little gable roof over the projection
            mb.face([(x0 - pw / 2 - 0.3, yb - 0.3, Hw - 0.2), (x0, yb - 0.3, ghz), (x0, -W / 4, ghz), (x0 - pw / 2 - 0.3, -W / 4, Hw - 0.2)][::-1], 'roof_slate')
            mb.face([(x0 + pw / 2 + 0.3, yb - 0.3, Hw - 0.2), (x0 + pw / 2 + 0.3, -W / 4, Hw - 0.2), (x0, -W / 4, ghz), (x0, yb - 0.3, ghz)][::-1], 'roof_slate')
            if ivy:
                ivy_patch(iv, P, 0, Le, 0, ghz - 0.4, 5.5, sgn * 7, cover=ivy,
                          holes=win_holes(Le, plinth, floors, fh, 4.0, ww=0.55),
                          top=lambda s, Le=Le: Hw + (Le / 2 - abs(s - Le / 2)) * 1.1 - 0.4)
    if portal == 'flat':
        flat_portal(mb, W, plinth, fh, wall, bw=tower_w + 0.4, gfn=local_ground(mb))
        mb.z_base = z0
        return [mb, iv]
    # --- central tower
    tw = tower_w
    tproj = 3.0
    Ht = Hw + tower_extra
    ty0 = -W / 2 - tproj
    tower = [(-tw / 2, ty0), (tw / 2, ty0), (tw / 2, ty0 + tw), (-tw / 2, ty0 + tw)]
    stone_base(mb, tower, plinth, wall)
    for i in range(4):
        a, bb = tower[i], tower[(i + 1) % 4]
        P, Le, t, n = edge_P(a, bb)
        if i == 0:
            # entrance: a moulded four-centred (Tudor) arch over glazed steel doors set back in the reveal, then a
            # mullioned window for each floor above, as on the tower fronts in the photos; clock-less belfry openings
            ow = door['w']
            e0, e1 = Le / 2 - ow / 2, Le / 2 + ow / 2
            zd = plinth - 0.1
            kind = door['arch']
            zs = zd + door['spring']
            apts = arch_points(e0, e1, zs, kind, 14)
            zap = max(z for _, z in apts)
            rec, band = 0.9, 0.3
            zt = zap + band + 0.15
            flat_wall(mb, P, 0, e0 - band, -0.5, Ht, wall)
            flat_wall(mb, P, e1 + band, Le, -0.5, Ht, wall)
            flat_wall(mb, P, e0 - band, e1 + band, zt, Ht, wall)
            flat_wall(mb, P, e0, e1, -0.5, zd, wall)
            for (a_, b_) in ((e0 - band, e0), (e1, e1 + band)):              # stone jambs of the surround
                flat_wall(mb, P, a_, b_, -0.5, zt, 'stone_trim', d=0.05)
                mb.quad(P(a_, -0.5, 0), P(a_, -0.5, 0.05), P(a_, zt, 0.05), P(a_, zt, 0), 'stone_trim')
                mb.quad(P(b_, -0.5, 0.05), P(b_, -0.5, 0), P(b_, zt, 0), P(b_, zt, 0.05), 'stone_trim')
            arch_fill(mb, lambda s_, z_, d_=0.0: P(s_, z_, d_ + 0.05), e0 - band, e1 + band, zs, zt, 0.05, 'stone_trim', kind, 14)
            arch_fill(mb, lambda s_, z_, d_=0.0: P(s_, z_, d_ + 0.08), e0 - band, e1 + band, zs + band * 0.2, zt, 0.001, wall, kind, 14)
            mb.quad(P(e0 - band, zt, 0.05), P(e1 + band, zt, 0.05), P(e1 + band, zt, 0), P(e0 - band, zt, 0), 'stone_trim')
            arch_fill(mb, P, e0, e1, zs, zt, rec, 'stone_trim', kind, 14)     # soffit of the deep reveal
            mb.quad(P(e0, zd, 0), P(e0, zd, -rec), P(e0, zs, -rec), P(e0, zs, 0), 'stone_trim')
            mb.quad(P(e1, zd, -rec), P(e1, zd, 0), P(e1, zs, 0), P(e1, zs, -rec), 'stone_trim')
            glazed_door(mb, P, e0, e1, zd, zs, kind, -rec + 0.02, door['style'])
            # the entrance hall seen through the glass: as deep as the tower stands out from the main wall
            vestibule(mb, P, e0 - 0.5, e1 + 0.5, zd, min(zap + 0.3, zd + 4.4), -rec - 0.01, tproj - rec - 0.05)
            wins = []
            for f in range(1, floors):
                w0, w1 = Le / 2 - min(1.3, tw * 0.15), Le / 2 + min(1.3, tw * 0.15)
                zw0, zw1 = plinth + f * fh + 0.9, plinth + (f + 1) * fh - 0.6
                if zw0 < zt + 0.3:          # a tall door (대우관's pointed arch) takes the first window's place
                    continue
                wins.append((w0, w1, zw0, zw1))
                mb.quad(P(w0, zw0, 0.02), P(w1, zw0, 0.02), P(w1, zw1, 0.02), P(w0, zw1, 0.02), 'glass')
                for sm in (w0 + (w1 - w0) / 3, w0 + 2 * (w1 - w0) / 3):
                    bar(mb, P, sm, zw0, sm, zw1, 0.14, 0.02, 0.1, 'stone_trim')
                bar(mb, P, w0, zw0 + (zw1 - zw0) * 0.7, w1, zw0 + (zw1 - zw0) * 0.7, 0.1, 0.02, 0.08, 'stone_trim')
                for (a_, b_, za_, zb_) in ((w0 - 0.18, w0, zw0 - 0.18, zw1 + 0.2), (w1, w1 + 0.18, zw0 - 0.18, zw1 + 0.2),
                                          (w0 - 0.18, w1 + 0.18, zw0 - 0.18, zw0), (w0 - 0.28, w1 + 0.28, zw1, zw1 + 0.22)):
                    bar(mb, P, a_, (za_ + zb_) / 2, b_, (za_ + zb_) / 2, zb_ - za_, 0.0, 0.12, 'stone_trim', ends=True)
        else:
            flat_wall(mb, P, 0, Le, -0.5 if i != 2 else Hw, Ht, wall)
        # belfry louvres
        bw0, bw1 = Le / 2 - 0.9, Le / 2 + 0.9
        mb.quad(P(bw0, Ht - 4.5, 0.03), P(bw1, Ht - 4.5, 0.03), P(bw1, Ht - 1.5, 0.03), P(bw0, Ht - 1.5, 0.03), 'metal_dark')
        arch_fill(mb, P, bw0, bw1, Ht - 1.5, Ht - 0.4, 0.0001, 'stone_trim', 'pointed', 6)
        # string course
        mb.quad(P(-0.15, Hw, 0.18), P(Le + 0.15, Hw, 0.18), P(Le + 0.15, Hw + 0.3, 0.18), P(-0.15, Hw + 0.3, 0.18), 'stone_trim')
        # battlements
        nm = 5
        for k in range(nm):
            if k % 2 == 0:
                c = P((k + 0.5) * Le / nm, Ht + 0.55, 0.05)
                mb.box(c, (Le / nm, 0.55, 1.1), 'stone_trim', rotz=math.atan2(t.y, t.x), skip=('bottom',))
        if ivy:
            holes = [(bw0, bw1, Ht - 4.5, Ht - 0.4)]
            if i == 0:
                holes += [(e0 - band - 0.25, e1 + band + 0.25, -1.0, zt + 0.3)] + [(a_ - 0.35, b_ + 0.35, za_ - 0.3, zb_ + 0.35) for a_, b_, za_, zb_ in wins]
            ivy_patch(iv, P, 0, Le, Hw if i == 2 else 0, Ht - 0.5, 5.5, 11 + i, cover=ivy * 0.95, holes=holes)
    mb.face([(p[0], p[1], Ht) for p in tower], 'roof_flat')
    # corner pinnacles
    for (px_, py_) in tower:
        mb.box((px_, py_, Ht + 0.9), (0.9, 0.9, 1.8), 'stone_trim', skip=('bottom',))
        mb.face([(px_ - .45, py_ - .45, Ht + 1.8), (px_ + .45, py_ - .45, Ht + 1.8), (px_, py_, Ht + 3.2)], 'stone_trim')
        mb.face([(px_ + .45, py_ - .45, Ht + 1.8), (px_ + .45, py_ + .45, Ht + 1.8), (px_, py_, Ht + 3.2)], 'stone_trim')
        mb.face([(px_ + .45, py_ + .45, Ht + 1.8), (px_ - .45, py_ + .45, Ht + 1.8), (px_, py_, Ht + 3.2)], 'stone_trim')
        mb.face([(px_ - .45, py_ + .45, Ht + 1.8), (px_ - .45, py_ - .45, Ht + 1.8), (px_, py_, Ht + 3.2)], 'stone_trim')
    # entrance steps: porch, granite flights with a landing, rubble side walls and capped posts
    sw = stairs['width'] or min(tw * 0.5, 4.4)
    if not stairs['none']:
        hall_steps(mb, ty0, plinth - 0.1, sw, local_ground(mb), wall=wall, wl=stairs['wl'], cheeks=stairs['cheeks'],
                   lamps=stairs['lamps'])
    mb.tower_front = ty0
    mb.tower_info = (ty0, tw, Ht)
    mb.z_base = z0
    return [mb, iv]


def underwood():
    # the porch stands ~2.5 m over the garden walk (about 16 risers in the 2016 photo: five, a landing, then the rest)
    return gothic('underwood', bld(246156115), (0.27, -1.0), 3, tower_w=9.0, tower_extra=9.5, ivy=1.0,
                  stairs=dict(width=4.2, wl=5.8, rise=2.45), door=dict(w=3.0, style='grid'))


def stimson():
    return gothic('stimson', bld(246156118), (1.0, -0.27), 2, tower_w=6.5, tower_extra=6.0, ivy=0.8, wings=False,
                  stairs=dict(width=3.6, wl=4.8), door=dict(w=2.6, spring=2.45, style='panel'))


def appenzeller():
    return gothic('appenzeller', bld(246156116), (-1.0, 0.27), 3, tower_w=7.0, tower_extra=6.5, ivy=1.1, wings=False,
                  stairs=dict(width=3.8, wl=5.0), door=dict(w=2.8, spring=2.5, style='panel'))


# ============================================================================= 대강당
def wall_holes(mb, P, s0, s1, z0, z1, mat, holes, d=0.0):
    """A wall P(s, z, d) over [s0, s1] x [z0, z1] with the rectangular openings holes [(a, b, za, zb), ...] left out."""
    zs = sorted({z0, z1} | {z for h in holes for z in (h[2], h[3]) if z0 < z < z1})
    for za, zb in zip(zs, zs[1:]):
        zm = (za + zb) / 2
        s = s0
        for a, b in sorted((h[0], h[1]) for h in holes if h[2] <= zm <= h[3]):
            if a > s:
                flat_wall(mb, P, s, a, za, zb, mat, d=d)
            s = max(s, b)
        if s < s1:
            flat_wall(mb, P, s, s1, za, zb, mat, d=d)


def reveal(mb, P, a, b, za, zb, depth, mat):
    """The sill, head and jambs of an opening [a, b] x [za, zb] in a wall plane P, depth m deep."""
    mb.quad(P(a, za, 0), P(a, za, -depth), P(b, za, -depth), P(b, za, 0), mat)
    mb.quad(P(b, zb, 0), P(b, zb, -depth), P(a, zb, -depth), P(a, zb, 0), mat)
    mb.quad(P(a, zb, 0), P(a, zb, -depth), P(a, za, -depth), P(a, za, 0), mat)
    mb.quad(P(b, za, 0), P(b, za, -depth), P(b, zb, -depth), P(b, zb, 0), mat)


def glazing(mb, P, a, b, za, zb, d, cols, rows, frame, glass='glass', fw=0.07, transom=None):
    """A pane over [a, b] x [za, zb] at depth d of a wall P, divided cols x rows by slim bars (and a transom bar)."""
    mb.quad(P(a, za, d), P(b, za, d), P(b, zb, d), P(a, zb, d), glass)
    for k in range(cols + 1):
        x = a + (b - a) * k / cols
        bar(mb, P, x, za, x, zb, fw if 0 < k < cols else fw * 1.5, d, d + 0.06, frame)
    for k in range(rows + 1):
        z = za + (zb - za) * k / rows
        bar(mb, P, a, z, b, z, fw if 0 < k < rows else fw * 1.5, d, d + 0.06, frame)
    if transom is not None:
        bar(mb, P, a, transom, b, transom, fw * 1.6, d, d + 0.08, frame)


def lattice_rail(mb, a, b, z, h=1.0, mat='frame_silver'):
    """A steel railing from a to b (local 2D) standing on z: posts, a top and a bottom rail, and between two slimmer
    rails a band of square lattice (the porch railings of the 대강당 in the 2009 photos)."""
    a, b = Vector((*a, 0)), Vector((*b, 0))
    t = b - a
    Le = t.length
    t.normalize()
    rz = math.atan2(t.y, t.x)
    at = lambda s, zz: (a.x + t.x * s, a.y + t.y * s, zz)
    nseg = max(1, int(round(Le / 1.6)))
    for k in range(nseg + 1):
        mb.box(at(k * Le / nseg, z + h / 2), (0.07, 0.07, h), mat, rotz=rz)
    for zz, w in ((z + h - 0.03, 0.06), (z + 0.1, 0.04), (z + 0.32, 0.03), (z + h - 0.22, 0.03)):
        mb.box(at(Le / 2, zz), (Le, w, w), mat, rotz=rz)
    nsq = max(1, int(Le / 0.42))
    for k in range(nsq + 1):
        mb.box(at(k * Le / nsq, z + 0.21 + (h - 0.32) / 2), (0.025, 0.025, h - 0.54), mat, rotz=rz)
    for k in range(nsq):                                            # a smaller square in each, on its corner
        c = at((k + 0.5) * Le / nsq, z + 0.21 + (h - 0.32) / 2)
        r = min(0.12, (h - 0.54) / 3)
        for sx, sz in ((-1, 0), (1, 0)):
            mb.box((c[0] + t.x * sx * r * 0.5, c[1] + t.y * sx * r * 0.5, c[2]), (0.02, 0.02, r * 1.4), mat, rotz=rz)
        for sz in (-1, 1):
            mb.box((c[0], c[1], c[2] + sz * r * 0.7), (r, 0.02, 0.02), mat, rotz=rz)


def hip_roof(mb, poly, z, rise, mat, eave=0.5):
    """A hipped roof over a rectangle poly (4 corners, CCW) at eaves height z: the ridge along its long axis."""
    pts = [Vector((*p, 0)) for p in poly]
    e0, e1 = pts[1] - pts[0], pts[2] - pts[1]
    if e0.length < e1.length:
        pts = pts[1:] + pts[:1]
        e0, e1 = e1, e0
    c = sum(pts, Vector()) / 4
    la, lb = e0.normalized(), e1.normalized()
    A, B = e0.length / 2 + eave, e1.length / 2 + eave
    q = [c - la * A - lb * B, c + la * A - lb * B, c + la * A + lb * B, c - la * A + lb * B]
    r0, r1 = c - la * max(0.1, A - B), c + la * max(0.1, A - B)
    zr = z + rise
    P3 = lambda v, zz: (v.x, v.y, zz)
    mb.face([P3(q[0], z), P3(q[1], z), P3(r1, zr), P3(r0, zr)], mat)
    mb.face([P3(q[1], z), P3(q[2], z), P3(r1, zr)], mat)
    mb.face([P3(q[2], z), P3(q[3], z), P3(r0, zr), P3(r1, zr)], mat)
    mb.face([P3(q[3], z), P3(q[0], z), P3(r0, zr)], mat)


def auditorium():
    """대강당 (1980, 선교70주년기념관), from the 2009 photos (reference/대강당_2009_정면.jpg, 대강당_2009_측면.jpg,
    대강당_2009_앞길_계단.jpg; the front is as it was built): a hall clad in pale granite panels whose big gable faces
    백양로 over the whole front, a wall of square panels with the cross at the top.  Under it a clerestory of small
    windows over a cornice, five bays of tall paired windows between broad pilasters, and at the foot the lobby: three
    bays of glass doors in brass frames, a grilled window in each outer bay, lanterns on the pilasters.  Square end
    pylons with two slit windows each stand a little forward.  The lobby floor is a raised porch ten risers over the
    forecourt: a broad flight before the three door bays with steel handrails, lattice railings round the rest.
    (The model before had a flat canopy on columns over five low steps, which the photos do not show.)  Lower wings
    fill the rest of the OSM outline: two storeys with hipped roofs at the front, flat-roofed blocks at the back."""
    b = bld(371403811)
    fp = b['footprint']
    fa, fb = Vector(fp[1]), Vector(fp[0])            # the main hall's 34 m front, south -> north
    v = (fb - fa).normalized()
    u = Vector((v.y, -v.x))                          # into the hall (east, away from 백양로)
    m = (fa + fb) / 2
    # local frame: x along the front from north to south, y into the hall: the front wall at y = 0, the porch at -y
    ang = math.atan2(-v.y, -v.x)
    zf = max(ground(*(m - u * 4.0 + v * s_)) for s_ in (-14.0, -7.0, 0.0, 7.0, 14.0))     # the forecourt
    mb = MeshBuilder('lm_auditorium')
    mb.xf = local_frame(m.x, m.y, ang, zf)
    gl = local_ground(mb)
    loc = lambda p: ((Vector(p) - m).dot(-v), (Vector(p) - m).dot(u))
    W_ = lambda lx, ly, lz: tuple(mb.xf @ Vector((lx, ly, lz)))
    wall = 'stone_panel'
    hx = (fb - fa).length / 2
    D = max(loc(p)[1] for p in fp)
    Zp = 1.6                     # the porch and lobby floor: ten risers over the forecourt
    He = Zp + 14.6               # eaves of the gable
    Hr = He + 5.6                # its ridge
    pw, pp = 5.4, 0.8            # end pylons: width, how far they stand out
    zb = -9.0                    # the walls go on down into the slope (the back stands ~11 m higher)
    # --- side and back walls: slit windows by the front, a clerestory row high up the long sides, a cornice
    body = [(-hx, 0.0), (hx, 0.0), (hx, D), (-hx, D)]
    for i in (1, 2, 3):
        P, Le, t, n = edge_P(body[i], body[(i + 1) % 4])
        holes = []
        if i in (1, 3):
            for k in range(2):
                s_ = 1.8 + k * 2.6
                s_ = s_ if i == 1 else Le - s_
                holes.append((s_ - 0.45, s_ + 0.45, Zp + 4.2, Zp + 13.0))
            for k in range(int((Le - 16.0) / 3.4)):
                s_ = 12.0 + k * 3.4
                s_ = s_ if i == 1 else Le - s_
                holes.append((s_ - 0.6, s_ + 0.6, He - 2.4, He - 1.4))
        wall_holes(mb, P, 0, Le, zb, He, wall, holes)
        for a_, b_, za_, zb_ in holes:
            reveal(mb, P, a_, b_, za_, zb_, 0.2, wall)
            glazing(mb, P, a_, b_, za_, zb_, -0.2, 1, max(1, int(round((zb_ - za_) / 1.0))), 'frame_dark')
        bar(mb, P, -0.2, He - 0.15, Le + 0.2, He - 0.15, 0.3, 0.0, 0.25, 'stone_trim', ends=True)
    # --- the front: the pylons, then the recessed middle between them
    for x0 in (-hx, hx - pw):
        x1 = x0 + pw
        Pp, _, _, _ = edge_P((x0, -pp), (x1, -pp))
        slits = [(pw / 2 - 1.55, pw / 2 - 0.7, Zp + 4.0, Zp + 13.2), (pw / 2 + 0.7, pw / 2 + 1.55, Zp + 4.0, Zp + 13.2)]
        wall_holes(mb, Pp, 0, pw, zb, He + 0.4, wall, slits)
        for a_, b_, za_, zb_ in slits:
            reveal(mb, Pp, a_, b_, za_, zb_, 0.25, wall)
            glazing(mb, Pp, a_, b_, za_, zb_, -0.25, 1, 9, 'frame_dark')
        for (xa, ya, xb, yb) in ((x0, 0.0, x0, -pp), (x1, -pp, x1, 0.0)):
            Ps, Ls, _, _ = edge_P((xa, ya), (xb, yb))
            flat_wall(mb, Ps, 0, Ls, zb, He + 0.4, wall)
        mb.quad((x0, -pp, He + 0.4), (x1, -pp, He + 0.4), (x1, 0.0, He + 0.4), (x0, 0.0, He + 0.4), 'stone_trim')
    Pf, _, _, _ = edge_P((-hx, 0.0), (hx, 0.0))      # s from the north end, d outwards
    nb = 5
    pb = (2 * hx - 2 * pw) / nb                      # bay pitch
    pl = 1.0                                         # pilaster width
    bays = [(pw + k * pb + pl / 2, pw + (k + 1) * pb - pl / 2) for k in range(nb)]
    doors = bays[1:4]
    holes = []
    for k, (sa, sb) in enumerate(bays):
        holes.append((sa, sb, Zp if 0 < k < 4 else Zp + 0.9, Zp + 3.9))           # lobby: doors / grilled windows
        c = (sa + sb) / 2
        for sg in (-1, 1):
            holes.append((c + sg * 0.9 - 0.55, c + sg * 0.9 + 0.55, Zp + 5.4, Zp + 12.4))   # tall paired windows
            holes.append((c + sg * 1.0 - 0.65, c + sg * 1.0 + 0.65, Zp + 13.95, Zp + 14.5))  # clerestory
    wall_holes(mb, Pf, pw, 2 * hx - pw, zb, He, wall, holes)
    for (sa, sb, za_, zb_) in holes:
        lobby = zb_ < Zp + 4.0
        door = lobby and za_ < Zp + 0.1
        reveal(mb, Pf, sa, sb, za_, zb_, 0.3 if lobby else 0.22, wall)
        if door:          # brass-framed glass doors and the lit lobby behind
            glazing(mb, Pf, sa, sb, za_, zb_, -0.3, 4, 1, 'bronze', glass='glass_door', fw=0.08, transom=Zp + 2.75)
            for sk in (1, 2, 3):
                hs = sa + (sb - sa) * sk / 4
                if sk == 2:
                    for sg in (-1, 1):
                        bar(mb, Pf, hs + sg * 0.12, Zp + 0.95, hs + sg * 0.12, Zp + 1.55, 0.035, -0.22, -0.16, 'bronze', ends=True)
            vestibule(mb, Pf, sa, sb, Zp + 0.003, Zp + 3.85, -0.32, 7.0, lights=3)
        elif lobby:       # the grilled windows of the outer bays
            glazing(mb, Pf, sa, sb, za_, zb_, -0.3, 6, 4, 'frame_dark')
            for kk in range(6):
                c_ = sa + (sb - sa) * (kk + 0.5) / 6
                for zz in (za_ + (zb_ - za_) * q for q in (0.125, 0.375, 0.625, 0.875)):
                    bar(mb, Pf, c_ - 0.14, zz, c_ + 0.14, zz, 0.025, -0.24, -0.2, 'frame_dark')
        elif zb_ - za_ > 2.0:
            glazing(mb, Pf, sa, sb, za_, zb_, -0.22, 2, 7, 'frame_dark')
        else:
            glazing(mb, Pf, sa, sb, za_, zb_, -0.22, 2, 1, 'frame_dark')
    # pilasters between the bays from the porch to the cornice, a slimmer strip between each pair of windows
    for k in range(nb + 1):
        x = -hx + pw + k * pb
        w_ = pl if 0 < k < nb else pl * 0.6
        xc = x if 0 < k < nb else x + (w_ / 2 if k == 0 else -w_ / 2)
        mb.box((xc, -0.2, (Zp + Zp + 13.4) / 2), (w_, 0.4, 13.4), wall, skip=('bottom',))
    for sa, sb in bays:
        mb.box(((sa + sb) / 2 - hx, -0.1, Zp + 9.0), (0.7, 0.2, 7.6), wall, skip=('bottom',))
    mb.box((0.0, -0.3, Zp + 13.55), (2 * hx - 2 * pw, 0.6, 0.3), 'stone_trim')                 # cornice
    mb.box((0.0, -0.22, Zp + 4.65), (2 * hx - 2 * pw, 0.44, 0.12), 'stone_trim')               # band over the lobby
    mb.box((0.0, -0.25, He + 0.05), (2 * hx + 0.5, 0.5, 0.3), 'stone_trim')                    # under the gable
    for k in range(1, nb):                                         # lanterns on the inner pilasters
        x = -hx + pw + k * pb
        mb.box((x, -0.5, Zp + 3.5), (0.22, 0.2, 0.42), 'metal_dark')
        mb.box((x, -0.52, Zp + 3.48), (0.16, 0.16, 0.26), 'light_amber')
    # --- the gable: square panels, the cross; copings up the rakes; the same gable at the back
    mb.face([(-hx, -0.02, He), (hx, -0.02, He), (0.0, -0.02, Hr)], wall)
    mb.face([(hx, D + 0.02, He), (-hx, D + 0.02, He), (0.0, D + 0.02, Hr)], wall)
    ps = 1.46
    for k in range(1, int((Hr - He) / ps) + 1):
        z = He + k * ps
        hw_ = hx * (1 - (z - He) / (Hr - He)) - 0.1
        if hw_ > 0.3:
            mb.quad((-hw_, -0.04, z), (hw_, -0.04, z), (hw_, -0.04, z + 0.04), (-hw_, -0.04, z + 0.04), 'concrete_dark')
    for k in range(-int(hx / ps), int(hx / ps) + 1):
        x = k * ps
        zt = He + (Hr - He) * (1 - abs(x) / hx) - 0.12
        if zt > He + 0.3:
            mb.quad((x - 0.02, -0.04, He + 0.2), (x + 0.02, -0.04, He + 0.2), (x + 0.02, -0.04, zt), (x - 0.02, -0.04, zt), 'concrete_dark')
    for sg in (-1, 1):
        a3, b3 = (sg * (hx + 0.35), He - 0.1), (0.0, Hr + 0.15)
        mb.quad((a3[0], -0.35, a3[1]), (b3[0], -0.35, b3[1]), (b3[0], 0.05, b3[1]), (a3[0], 0.05, a3[1]),
                'stone_trim') if sg < 0 else \
            mb.quad((b3[0], -0.35, b3[1]), (a3[0], -0.35, a3[1]), (a3[0], 0.05, a3[1]), (b3[0], 0.05, b3[1]), 'stone_trim')
    zc = He + 3.6                                                  # the cross: a ring over a T
    mb.box((0.0, -0.08, zc), (0.16, 0.1, 2.2), 'metal_dark')
    mb.box((0.0, -0.08, zc + 0.75), (1.1, 0.1, 0.14), 'metal_dark')
    for k in range(10):
        a_ = 2 * math.pi * k / 10
        mb.box((0.36 * math.cos(a_), -0.08, zc + 1.55 + 0.36 * math.sin(a_)), (0.2, 0.1, 0.1), 'metal_dark', rotz=0.0)
    # --- the roof, its ridge front to back
    e = hx + 0.45
    # (grey standing-seam metal in the photos, a green flashing along the eaves and the rakes)
    mb.face([(-e, -0.45, He - 0.15), (0.0, -0.45, Hr + 0.1), (0.0, D + 0.45, Hr + 0.1), (-e, D + 0.45, He - 0.15)], 'roof_metal')
    mb.face([(e, D + 0.45, He - 0.15), (0.0, D + 0.45, Hr + 0.1), (0.0, -0.45, Hr + 0.1), (e, -0.45, He - 0.15)], 'roof_metal')
    for sg in (-1, 1):
        mb.box((sg * e, D / 2, He - 0.25), (0.14, D + 0.9, 0.22), 'metal_green')
    mb.box((0.0, D / 2, Hr + 0.18), (0.3, D + 0.9, 0.18), 'metal_green')
    # --- the porch: from the front of the pylons out to the flight, and between them up to the doors
    yP = -5.6
    mb.box((0.0, (yP - pp) / 2, (Zp - 2.0) / 2), (2 * hx, -pp - yP, Zp + 2.0), 'stone_granite', mats={'top': 'stone_step'},
           skip=('bottom',))
    mb.box((0.0, -pp / 2, (Zp - 2.0) / 2), (2 * hx - 2 * pw, pp, Zp + 2.0), 'stone_granite', mats={'top': 'stone_step'},
           skip=('bottom',))
    mb.box((0.0, yP + 0.12, Zp + 0.02), (2 * hx + 0.1, 0.3, 0.06), 'stone_trim')                 # nosing along its edge
    WALK_FACES.append([W_(-hx, yP, Zp), W_(hx, yP, Zp), W_(hx, -pp, Zp), W_(-hx, -pp, Zp)])
    WALK_FACES.append([W_(-hx + pw, -pp, Zp), W_(hx - pw, -pp, Zp), W_(hx - pw, 0.3, Zp), W_(-hx + pw, 0.3, Zp)])
    fw = sum(b_ - a_ for a_, b_ in doors) + 2 * pl                  # the flight: as wide as the three door bays
    stair_flight(mb, 0.0, yP, fw, Zp, n=10, mat='stone_step', landing=0.0, tread=0.33, flare=0.0, rail=True, gfn=gl,
                 maxrise=0.165)
    for sg in (-1, 1):                                             # lattice railings round the rest of the porch
        lattice_rail(mb, (sg * (fw / 2 + 0.1), yP + 0.15), (sg * (hx - 0.1), yP + 0.15), Zp)
        lattice_rail(mb, (sg * (hx - 0.1), yP + 0.15), (sg * (hx - 0.1), -pp - 0.05), Zp)
    # --- the lower wings round the hall (the rest of the OSM outline)
    lp = [loc(p) for p in fp]
    wings = [[lp[2], lp[3], lp[4], lp[5]], [lp[15], lp[14], lp[13], lp[12]],
             [lp[6], lp[7], lp[8], (lp[6][0], D)], [lp[11], lp[10], lp[9], (lp[11][0], D)]]
    for wi, wp in enumerate(wings):
        area = sum(wp[i][0] * wp[(i + 1) % 4][1] - wp[(i + 1) % 4][0] * wp[i][1] for i in range(4))
        if area < 0:
            wp = wp[::-1]
        gs = [gl(*p) for p in wp]
        top = min(He - 3.5, max(gs) + 7.8)
        base = min(gs) - 1.5
        for i in range(4):
            a2, b2 = wp[i], wp[(i + 1) % 4]
            mx, my = (a2[0] + b2[0]) / 2, (a2[1] + b2[1]) / 2
            if abs(mx) < hx + 0.8 and -0.4 < my < D + 0.4:
                continue                                           # against the hall's own wall
            P, Le, t, n = edge_P(a2, b2)
            zg = max(gl(*a2), gl(*b2), gl(mx, my))
            nfl = max(0, min(2, int((top - zg - 0.6) / 3.6)))
            flat_wall(mb, P, 0, Le, base, zg + 0.3, wall)
            if nfl:
                window_grid(mb, P, Le, zg + 0.3, nfl, 3.6, 3.2, wall, ww=0.5, trim='stone_trim', mull=1)
            flat_wall(mb, P, 0, Le, zg + 0.3 + nfl * 3.6, top, wall)
        if wi < 2:
            mb.face([(p[0], p[1], top) for p in wp], 'roof_flat')
            hip_roof(mb, wp, top, 2.4, 'roof_slate', eave=0.6)
        else:
            mb.face([(p[0], p[1], top) for p in wp], 'roof_flat')
            for i in range(4):
                P, Le, t, n = edge_P(wp[i], wp[(i + 1) % 4])
                mb.quad(P(0, top, 0), P(Le, top, 0), P(Le, top + 0.8, 0), P(0, top + 0.8, 0), wall)
                mb.quad(P(Le, top + 0.8, 0), P(0, top + 0.8, 0), P(0, top + 0.8, -0.3), P(Le, top + 0.8, -0.3), 'stone_trim')
    return [mb]


# ============================================================================= 루스채플
def chapel():
    b = bld(429249499)
    cx, cy, L, W, ang, z0 = frame_for(b, (-1.0, 0.25))
    mb = MeshBuilder('lm_chapel')
    mb.xf = local_frame(cx, cy, ang, z0)
    L, W = min(L, 34), min(W * 0.75, 18)
    H = 8.0
    body = rect(L, W)
    mb.prism(offset_poly(body, 0.3), -4, 0.6, 'stone_granite', 'stone_granite')
    for i in range(4):
        a, bb = body[i], body[(i + 1) % 4]
        P, Le, t, n = edge_P(a, bb)
        flat_wall(mb, P, 0, Le, 0.6, H, 'brick_red')
        nf = int(Le / 2.6)
        for k in range(1, nf):
            s = k * Le / nf
            mb.quad(P(s - 0.35, 1.6, 0.02), P(s + 0.35, 1.6, 0.02), P(s + 0.35, H - 0.8, 0.02), P(s - 0.35, H - 0.8, 0.02), 'glass')
            mb.quad(P(s - 0.45, 1.5, 0.05), P(s + 0.45, 1.5, 0.05), P(s + 0.45, 1.6, 0.05), P(s - 0.45, 1.6, 0.05), 'stone_trim')
        if Le < W + 0.1:
            hz = H + W / 2 * 1.25
            mb.face([P(0, H), P(Le, H), P(Le / 2, hz)], 'brick_red')
    hz = H + W / 2 * 1.25
    mb.face([(-L / 2 - 0.6, -W / 2 - 0.6, H - 0.75), (L / 2 + 0.6, -W / 2 - 0.6, H - 0.75), (L / 2 + 0.6, 0, hz), (-L / 2 - 0.6, 0, hz)], 'roof_slate')
    mb.face([(L / 2 + 0.6, W / 2 + 0.6, H - 0.75), (-L / 2 - 0.6, W / 2 + 0.6, H - 0.75), (-L / 2 - 0.6, 0, hz), (L / 2 + 0.6, 0, hz)], 'roof_slate')
    # slim bell tower with cross at the front corner
    tx, ty = -L / 2 + 2.0, -W / 2 - 2.5
    mb.box((tx, ty, 8.5), (2.4, 2.4, 17.0), 'concrete', mats={'top': 'concrete'})
    mb.box((tx, ty - 1.21, 13.5), (1.0, 0.02, 4.0), 'metal_dark')
    mb.box((tx, ty, 17.0 + 2.0), (0.25, 0.25, 4.0), 'metal')
    mb.box((tx, ty, 17.0 + 2.8), (1.6, 0.25, 0.25), 'metal')
    # entrance porch
    mb.box((-L / 2 - 1.5, 0, 3.5), (3.0, 6.0, 0.4), 'concrete')
    flat = edge_P((-L / 2, -2.0), (-L / 2, 2.0))
    return [mb]


# ============================================================================= 제1공학관 (front slab on 백양로)
def engineering():
    b = bld(205583531)
    cx, cy, L, W, ang, z0 = frame_for(b, (1.0, -0.25))
    z0 = lift_base(z0, cx, cy, ang, max(W, 13) / 2 + 2.5, 0.4, 0.6)
    mb = MeshBuilder('lm_engineering')
    mb.xf = local_frame(cx, cy, ang, z0)
    W = max(W, 13)
    fh, nf = 3.7, 5
    H = nf * fh + 0.6
    body = rect(L, W)
    mb.prism(offset_poly(body, 0.2), -4, 0.4, 'stone_granite')
    st = dict(generic.STYLE['modern'])
    # windows as in the 1997 aerial photo (reference/1997_백양로_항공사진.jpg): five rows on the 백양로 front, 14 wide
    # sliding windows a row across the 65 m (a 4.7 m bay, narrow piers between them), and deep plain spandrels: the
    # glass is under half the storey height
    st.update(wall='plaster_white', alt='plaster_white', ww=0.88, bay=L / 14.0, sill=1.0, head=1.05, mull=1)
    for i in range(4):
        a, bb = body[i], body[(i + 1) % 4]
        P, Le, t, n = edge_P(a, bb)
        if Le < W + 0.1:
            flat_wall(mb, P, 0, Le, 0.4, H + 0.9, 'stone_rubble_gray')   # grey rubble-granite end walls (1997 photo)
        else:
            # use local coordinates for the generic edge builder via a temporary identity xf
            pass
    # long facades through the generic wall builder in world space
    xf = mb.xf
    world = [tuple((xf @ Vector((p[0], p[1], 0)))[:2]) for p in body]
    mbw = MeshBuilder('lm_engineering_fac')
    rnd_ = random.Random(5)
    for i in (0, 2):
        generic.wall_edge(mbw, world[i], world[(i + 1) % 4], z0 + 0.4, z0 + H + 0.9, nf, fh, st, rnd_)
    generic.parapet_and_roof(mbw, world, z0 + H, st, rnd_)
    # the hall is the 1997 one (tools/build_campus.py FOOTPRINT_1997: 65 m, before the 2015 wings).  As in the 1997
    # aerial photo: a white rooftop storey over the south third (the sixth floor was only built out in 2007), and a
    # long flat canopy on columns along the north half of the 백양로 front with the entrance at its south end
    mb.box((-L / 2 + 11.0, 0.3, H + 1.8), (22.0, W - 0.6, 3.6), 'plaster_white', mats={'top': 'roof_flat'})
    for k in range(5):
        mb.box((-L / 2 + 2.5 + k * 4.2, -W / 2 + 0.27, H + 2.0), (1.6, 0.08, 1.1), 'glass')
    x0c, x1c = 0.0, L / 2 - 0.3
    mb.box(((x0c + x1c) / 2, -W / 2 - 2.2, 4.0), (x1c - x0c, 4.4, 0.45), 'concrete', mats={'top': 'roof_flat'})
    for k in range(6):
        mb.cylinder((x0c + 0.6 + k * (x1c - x0c - 1.2) / 5, -W / 2 - 4.0), 0.22, 0.4, 3.8, 'concrete', seg=8, cap_top=False)
    xe = x0c + 4.6
    # wide concrete flight with handrails under the canopy, glass double doors behind a landing
    stair_flight(mb, xe, -W / 2, 8.0, 0.4, n=4, mat='stone_granite', landing=1.8, tread=0.4, flare=0.6, rail=True, gfn=local_ground(mb))
    mb.quad((xe - 2.6, -W / 2 - 0.02, 0.4), (xe + 2.6, -W / 2 - 0.02, 0.4), (xe + 2.6, -W / 2 - 0.02, 3.4), (xe - 2.6, -W / 2 - 0.02, 3.4), 'glass')
    mb.box((xe, -W / 2 - 0.03, 3.5), (5.4, 0.08, 0.16), 'frame_dark')
    mb.box((xe, -W / 2 - 0.03, 0.4 + 1.5), (0.1, 0.08, 3.0), 'frame_dark')
    return [mb, mbw]


# ============================================================================= 광혜원 (traditional hanok)
def hanok():
    b = bld(429249496)
    cx, cy, L, W, ang, z0 = frame_for(b, (-1.0, 0.2))
    z0 = lift_base(z0, cx, cy, ang, 8.4 / 2 + 2.4, 0.9, 0.6)
    mb = MeshBuilder('lm_hanok')
    mb.xf = local_frame(cx, cy, ang, z0)
    L, W = 15.0, 8.4
    plat = 0.9
    mb.prism(offset_poly(rect(L + 2.4, W + 2.4), 0), -3, plat, 'stone_granite', 'stone_granite')
    WALK_FACES.append([tuple(mb.xf @ Vector((x_, y_, plat))) for x_, y_ in rect(L + 2.4, W + 2.4)])   # the 기단 is walked on
    stair_flight(mb, 0, -(W + 2.4) / 2, 3.0, plat, n=3, landing=0.3, tread=0.35, flare=0.25, gfn=local_ground(mb), maxrise=0.2)
    colh = 3.3
    nx, ny = 5, 3
    xs = [-L / 2 + L * i / nx for i in range(nx + 1)]
    ys = [-W / 2 + W * j / ny for j in range(ny + 1)]
    for x in xs:
        for y in (ys[0], ys[-1]):
            mb.cylinder((x, y), 0.2, plat, plat + colh, 'wood_red', seg=8, cap_top=False)
    for y in ys[1:-1]:
        for x in (xs[0], xs[-1]):
            mb.cylinder((x, y), 0.2, plat, plat + colh, 'wood_red', seg=8, cap_top=False)
    # infill walls: white plaster lower, lattice doors (창호)
    body = rect(L, W)
    for i in range(4):
        a, bb = body[i], body[(i + 1) % 4]
        P, Le, t, n = edge_P(a, bb, plat)
        flat_wall(mb, P, 0, Le, 0, 0.7, 'plaster_white', d=-0.08)
        flat_wall(mb, P, 0, Le, 0.7, colh - 0.6, 'wood_dark' if i == 0 else 'plaster_white', d=-0.1)
        flat_wall(mb, P, 0, Le, colh - 0.6, colh, 'wood_red', d=-0.05)
        if i == 0:
            for k in range(int(Le / 0.5)):
                s = k * 0.5
                mb.quad(P(s, 0.7, -0.06), P(s + 0.05, 0.7, -0.06), P(s + 0.05, colh - 0.6, -0.06), P(s, colh - 0.6, -0.06), 'paint_white')
            for zz in [0.7 + 0.45 * k for k in range(6)]:
                mb.quad(P(0, zz, -0.06), P(Le, zz, -0.06), P(Le, zz + 0.04, -0.06), P(0, zz + 0.04, -0.06), 'paint_white')
    # 팔작지붕 roof: curved eaves with upturned corners
    zr0 = plat + colh + 0.4
    ov = 1.6
    Lr, Wr = L / 2 + ov, W / 2 + ov
    ridge = zr0 + 3.0
    rl = L / 2 - 1.5
    N = 10

    def roof_z(u, v):
        """u in [-1,1] along L, v in [0,1] from eave (0) to ridge (1)."""
        sag = 0.35 * math.sin(math.pi * v)          # concave curve
        lift = 0.6 * (abs(u) ** 6) * (1 - v)          # corner upturn (처마 곡선)
        return zr0 + (ridge - zr0) * v - sag + lift
    for side in (-1, 1):
        for i in range(N):
            for j in range(N):
                u0, u1 = -1 + 2 * i / N, -1 + 2 * (i + 1) / N
                v0, v1 = j / N, (j + 1) / N

                def pt(u, v):
                    x = u * (Lr * (1 - v) + rl * v)
                    y = side * Wr * (1 - v)
                    return (x, y, roof_z(u, v))
                q = [pt(u0, v0), pt(u1, v0), pt(u1, v1), pt(u0, v1)]
                if side < 0:
                    mb.face(q, 'roof_giwa', smooth='roofA')
                else:
                    mb.face(q[::-1], 'roof_giwa', smooth='roofB')
    for side in (-1, 1):            # hip ends (triangular with gable 합각)
        for j in range(N):
            v0, v1 = j / N, (j + 1) / N

            def pt2(w, v):
                x = side * (Lr * (1 - v) + rl * v)
                y = w * Wr * (1 - v)
                return (x, y, roof_z(side, v))
            q = [pt2(-1, v0), pt2(1, v0), pt2(1, v1), pt2(-1, v1)]
            mb.face(q if side > 0 else q[::-1], 'roof_giwa')
        mb.face([(side * rl, -0.01, ridge), (side * rl, 0.01, ridge), (side * rl, 0, ridge - 0.01)], 'roof_giwa')
    mb.box((0, 0, ridge + 0.25), (2 * rl + 0.6, 0.6, 0.5), 'roof_giwa')
    for sx in (-1, 1):
        mb.box((sx * (rl + 0.3), 0, ridge + 0.55), (0.6, 0.7, 0.9), 'roof_giwa')
    # eave underside (서까래 colour)
    mb.face([(-Lr, -Wr, zr0 - 0.12), (Lr, -Wr, zr0 - 0.12), (L / 2, -W / 2, zr0 - 0.3), (-L / 2, -W / 2, zr0 - 0.3)][::-1], 'wood_red')
    mb.face([(Lr, Wr, zr0 - 0.12), (-Lr, Wr, zr0 - 0.12), (-L / 2, W / 2, zr0 - 0.3), (L / 2, W / 2, zr0 - 0.3)][::-1], 'wood_red')
    mb.box((0, 0, plat + colh + 0.2), (L + 0.4, W + 0.4, 0.4), 'wood_red', skip=('top',))
    return [mb]


# ============================================================================= 구 노천극장 (1997)
def amphitheater():
    A = CAMPUS['amphitheater']
    mb = MeshBuilder('lm_amphitheater')
    mb.xf = local_frame(A['cx'], A['cy'], A['rot'], 0)
    rx, ry = A['arena_rx'], A['arena_ry']
    h0 = A['arena_h']
    nseg = 56
    a0, a1 = math.radians(-128), math.radians(128)
    # arena floor (dirt) – full ellipse
    pts = [(rx * math.cos(2 * math.pi * i / 48), ry * math.sin(2 * math.pi * i / 48)) for i in range(48)]
    mb.face([(x, y, h0 + 0.02) for x, y in pts], 'dirt')
    from common import ground
    cA, sA = math.cos(A['rot']), math.sin(A['rot'])

    def E(t, d):
        return ((rx + d) * math.cos(t), (ry + d) * math.sin(t))

    def gz(p):
        # world ground at a local point -> rows never stand proud of the hillside
        wx = A['cx'] + p[0] * cA - p[1] * sA
        wy = A['cy'] + p[0] * sA + p[1] * cA
        return ground(wx, wy) + 0.03

    def zrow(r, p):
        return h0 + r * A['row_h']
    for r in range(A['rows']):
        d0, d1 = r * A['row_d'], (r + 1) * A['row_d']
        for i in range(nseg):
            t0 = a0 + (a1 - a0) * i / nseg
            t1 = a0 + (a1 - a0) * (i + 1) / nseg
            p00, p01 = E(t0, d0), E(t1, d0)
            p10, p11 = E(t0, d1), E(t1, d1)
            z00, z01 = zrow(r, p00), zrow(r, p01)
            z10, z11 = zrow(r + 1, p10), zrow(r + 1, p11)
            zb00, zb01 = zrow(r + 1, p00), zrow(r + 1, p01)
            # riser (stone edge) then grass tread
            if zb00 - z00 > 0.02 or zb01 - z01 > 0.02:
                mb.quad((*p01, z01), (*p00, z00), (*p00, zb00), (*p01, zb01), 'concrete_dark')
            mb.quad((*p01, zb01), (*p00, zb00), (*p10, z10), (*p11, z11), 'grass')
    # simple stage at the open (west) side
    sx = -rx - 4.0
    mb.box((sx, 0, h0 + 0.05), (6.0, 14.0, 1.1), 'concrete', mats={'top': 'wood_dark'})
    return [mb]


# ============================================================================= 대우관 (1984)
def gable_hall(mb, u0, u1, v0, v1, floors, fh, wall, pitch=1.3, plinth=1.0, bay=3.3, iv=None, ivy=0.0, seed=0, gothic_trim=False):
    """A stone hall in the builder's local frame whose ridge runs along v, with steep gables on its two v ends
    (the end pavilions of 대우관: their gables face the forecourt)."""
    W = u1 - u0
    Hw = plinth + floors * fh + 0.6
    hz = Hw + W / 2 * pitch
    body = [(u0, v0), (u1, v0), (u1, v1), (u0, v1)]
    stone_base(mb, body, plinth, wall)
    gl = local_ground(mb)
    for i in range(4):
        P, Le, t, n = edge_P(body[i], body[(i + 1) % 4])
        window_grid(mb, P, Le, plinth, floors, fh, bay, wall, ww=0.5, trim='stone_trim', mull=2)
        if plinth > 1.2:
            basement_windows(mb, P, 0, Le, bay, plinth, gl, wall)
        flat_wall(mb, P, 0, Le, plinth + floors * fh, Hw, wall)
        if gothic_trim and i in (1, 3):
            # as on the old stone halls (언더우드관): buttresses up the long sides and a battlemented parapet
            nbut = int(round(Le / 6.6))
            for k in range(1, nbut):
                c = P(k * Le / nbut, 0, 0.3)
                mb.box((c[0], c[1], plinth + (Hw - plinth - 1.5) / 2), (0.7, 0.6, Hw - plinth - 1.5), wall,
                       rotz=math.atan2(t.y, t.x), mats={'top': 'stone_trim'})
            nm = int(Le / 1.6)
            for k in range(0, nm, 2):
                c = P((k + 0.5) * Le / nm, Hw + 0.45, 0.0)
                mb.box(c, (Le / nm, 0.45, 0.9), 'stone_trim', rotz=math.atan2(t.y, t.x), skip=('bottom',))
        if iv is not None and ivy:
            gable = i in (0, 2)
            ivy_patch(iv, P, 0, Le, 0, (hz - 0.4) if gable else Hw + 0.3, 5.5, seed + i * 5, cover=ivy,
                      holes=win_holes(Le, plinth, floors, fh, bay, ww=0.5),
                      top=(lambda s_, Le=Le: Hw + (Le / 2 - abs(s_ - Le / 2)) * pitch - 0.4) if gable else None)
        mb.quad(P(-0.1, Hw - 0.1, 0.2), P(Le + 0.1, Hw - 0.1, 0.2), P(Le + 0.1, Hw + 0.2, 0.2), P(-0.1, Hw + 0.2, 0.2), 'stone_trim')
        if i in (0, 2):     # gable end: triangle, coping and a finial
            mb.face([P(0, Hw), P(Le, Hw), P(Le / 2, hz)], wall)
            mb.quad(P(-0.25, Hw, 0.3), P(Le / 2, hz + 0.4, 0.3), P(Le / 2, hz + 0.4, -0.2), P(-0.25, Hw, -0.2), 'stone_trim')
            mb.quad(P(Le / 2, hz + 0.4, 0.3), P(Le + 0.25, Hw, 0.3), P(Le + 0.25, Hw, -0.2), P(Le / 2, hz + 0.4, -0.2), 'stone_trim')
            c = P(Le / 2, hz + 0.9, 0.05)
            mb.box(c, (0.7, 0.7, 1.2), 'stone_trim', rotz=math.atan2(t.y, t.x), skip=('bottom',))
    uc = (u0 + u1) / 2
    e = 0.35
    A, B = (u0 - e, v0 - e, Hw - e * pitch), (u0 - e, v1 + e, Hw - e * pitch)
    C, D = (u1 + e, v1 + e, Hw - e * pitch), (u1 + e, v0 - e, Hw - e * pitch)
    R1, R2 = (uc, v0 - e, hz), (uc, v1 + e, hz)
    mb.face([A, R1, R2, B], 'roof_slate')
    mb.face([C, R2, R1, D], 'roof_slate')
    mb.box((uc, (v0 + v1) / 2, hz + 0.1), (0.35, v1 - v0, 0.3), 'metal_dark')


def daewoo_front(mb, zT, zP, u0, u1, uc=23.55, vp=-17.0):
    """대우관's terrace and podium (reference/대우관_2024_정면과_상뜰.jpg, 대우관_정면_전경.jpg, 대우관_블로그_본관_정면_상뜰.jpg,
    대우관_측면_2012.jpg), in the recess frame: u along the front from its west end, v into the hall (front wall v = 0),
    z from the hall's z0; zT the terrace, zP the plaza (the 상뜰 level) ~6 m below.
    The main door is not up a flight at all: a white stone podium stands 14 m out from the tower, 18 m wide, and the
    door is in its face at the plaza level, glass doors at the back of a deep porch under one wide low arch, a blue
    name board above, a clipped hedge along its top.  Flights climb to the terrace between high walls on either side
    of it; beyond them the front steps back, a planted tier and then the terrace wall, across the fronts of the wings.
    The tower's own pointed door opens onto the terrace three steps up."""
    hp, sw, ow = 9.0, 2.8, 8.6                   # podium half width, stair well width, arch span
    gnd = zP - 0.6
    W_ = lambda u, v, z: tuple(mb.xf @ Vector((u, v, z)))

    def walk(ua, ub, va, vb, z):
        WALK_FACES.append([W_(ua, va, z), W_(ub, va, z), W_(ub, vb, z), W_(ua, vb, z)])

    def block(ua, ub, va, vb, za, zb, mat='stone_white', top=None):
        mb.box(((ua + ub) / 2, (va + vb) / 2, (za + zb) / 2), (ub - ua, vb - va, zb - za), mat,
               mats={'top': top} if top else None, skip=('bottom',) if za <= gnd else ())

    def parapet(ua, ub, va, vb, z, h=1.0):
        block(ua, ub, va, vb, z, z + h - 0.12)
        block(ua - 0.06, ub + 0.06, va - 0.06, vb + 0.06, z + h - 0.12, z + h, 'stone_trim')

    # --- the podium, built round its porch (v from the face to -14) and the lit lobby behind the glass (to -8.5)
    pa, pb = uc - hp, uc + hp
    oa, ob = uc - ow / 2, uc + ow / 2
    zs = zP + 2.2                                # springing of the segmental arch
    zc = zs + ow * 0.16                          # its crown = the porch ceiling
    vr, vl = vp + 3.0, vp + 8.5                  # glass screen / back of the lobby
    block(pa, oa, vp, 0.0, gnd, zT, top='stone_step')
    block(ob, pb, vp, 0.0, gnd, zT, top='stone_step')
    block(oa, ob, vp, 0.0, zc, zT, top='stone_step')
    block(oa, ob, vl, 0.0, gnd, zc)
    Pf, _, _, _ = edge_P((pa, vp), (pb, vp))     # the podium face: s from its west end, d outwards (-v)
    arch_fill(mb, Pf, oa - pa, ob - pa, zs, zc + 0.01, 0.6, 'stone_white', 'segment', 16, intrados_mat='stone_trim')
    ring = arch_points(oa - pa, ob - pa, zs, 'segment', 16)
    for (sa, za), (sb, zb) in zip(ring, ring[1:]):                     # a pale moulded ring round the arch
        bar(mb, Pf, sa, za + 0.16, sb, zb + 0.16, 0.32, 0.0, 0.06, 'stone_trim')
    for s in (oa - pa - 0.16, ob - pa + 0.16):                         # and down the jambs
        bar(mb, Pf, s, zP, s, zs + 0.1, 0.32, 0.0, 0.06, 'stone_trim')
    mb.quad(Pf(oa - pa, zP + 0.02, 0.3), Pf(ob - pa, zP + 0.02, 0.3), Pf(ob - pa, zP + 0.02, -3.0), Pf(oa - pa, zP + 0.02, -3.0), 'stone_step')
    walk(oa, ob, vp - 0.3, vr, zP + 0.02)
    shopfront(mb, Pf, oa - pa + 0.05, ob - pa - 0.05, zP, zc - 0.01, -3.0)
    vestibule(mb, Pf, oa - pa + 0.03, ob - pa - 0.03, zP + 0.005, zc - 0.03, -3.02, vl - vr - 0.05, lights=3)
    zb0 = zc + 0.45                                                    # the blue name board over the arch
    mb.quad(Pf(hp - 5.2, zb0, 0.05), Pf(hp + 5.2, zb0, 0.05), Pf(hp + 5.2, zb0 + 0.62, 0.05), Pf(hp - 5.2, zb0 + 0.62, 0.05), 'sign_blue')
    bar(mb, Pf, hp - 5.3, zb0 + 0.31, hp + 5.3, zb0 + 0.31, 0.72, 0.0, 0.04, 'stone_trim', ends=True)
    mb.quad(Pf(hp - 4.2, zb0 + 0.27, 0.06), Pf(hp + 4.2, zb0 + 0.27, 0.06), Pf(hp + 4.2, zb0 + 0.35, 0.06), Pf(hp - 4.2, zb0 + 0.35, 0.06), 'paint_white')
    block(pa - 0.12, pb + 0.12, vp - 0.12, vp + 0.5, zT - 0.3, zT, 'stone_trim')        # coping band
    for k in range(6):                                                 # horizontal joints of the ashlar face
        z = zP + 0.6 + k * (zT - zP - 0.6) / 6
        if zs - 0.3 < z < zc + 1.2:
            continue
        mb.quad(Pf(0, z, 0.012), Pf(2 * hp, z, 0.012), Pf(2 * hp, z + 0.03, 0.012), Pf(0, z + 0.03, 0.012), 'stone_trim')
    # on top: a parapet with the clipped hedge behind it, the walk to the tower, side parapets over the wells
    parapet(pa, pb, vp, vp + 0.4, zT)
    block(pa + 0.4, pb - 0.4, vp + 0.4, vp + 1.6, zT, zT + 0.45, 'stone_trim', top='soil')
    mb.box((uc, vp + 1.0, zT + 0.8), (2 * hp - 1.2, 0.95, 0.75), 'shrub_green')
    walk(pa, pb, vp + 1.6, 0.0, zT)

    # --- the flights either side, two of ~18 risers with a landing between, from the plaza up to the terrace
    n1, n2, tr = 18, 19, 0.31
    rise = (zT - zP) / (n1 + n2)
    zm = zP + n1 * rise
    top_v = None
    for sg in (-1, 1):
        ux = uc + sg * (hp + sw / 2)
        yf1 = vp + 1.4 + n1 * tr
        stair_flight(mb, ux, yf1, sw, zm, n=n1, mat='stone_step', landing=1.4, tread=tr, flare=0.0, ground=gnd, zbot=zP)
        yf2 = yf1 + 1.0 + n2 * tr
        stair_flight(mb, ux, yf2, sw, zT, n=n2, mat='stone_step', landing=1.0, tread=tr, flare=0.0, ground=gnd, zbot=zm)
        top_v = yf2 + 1.2
        block(ux - sw / 2, ux + sw / 2, top_v, 0.0, gnd, zT, top='stone_step')       # the terrace behind the well
        walk(ux - sw / 2, ux + sw / 2, top_v - 0.05, 0.0, zT)
        parapet(*sorted((uc + sg * hp, uc + sg * (hp + 0.4))), vp + 0.4, top_v, zT)    # podium side over the well
    # --- beyond the wells: a planted tier, then the terrace wall, across the wings' fronts to the roads
    vA = vp + 2.5
    for ua, ub in ((u0, uc - hp - sw), (uc + hp + sw, u1)):
        block(ua, ub, vp, vA, gnd, zP + 2.8, top='soil')
        for k in range(int((ub - ua) / 2.6)):
            c = (ua + 1.3 + k * (ub - ua - 2.6) / max(1, int((ub - ua) / 2.6) - 1), vp + 1.25)
            mb.cylinder(c, 0.95, zP + 2.7, zP + 3.4, 'shrub_green', seg=10, r1=1.0)
            mb.cylinder(c, 1.0, zP + 3.4, zP + 3.8, 'shrub_green', seg=10, r1=0.45)
        block(ua - 0.1, ub + 0.1, vp - 0.1, vp + 0.25, zP + 2.65, zP + 2.85, 'stone_trim')
        block(ua, ub, vA, 0.0, gnd, zT, top='pavers')
        walk(ua, ub, vA + 0.35, 0.0, zT)
        parapet(ua, ub, vA, vA + 0.35, zT)
        inner = ub if ua < uc else ua                                  # parapet along the well
        parapet(*sorted((inner, inner + (-0.35 if ua < uc else 0.35))), vA + 0.35, top_v, zT)
        end = ua if ua < uc else ub                                    # and at the road end, up to the wing
        parapet(*sorted((end, end + (0.35 if ua < uc else -0.35))), vA + 0.35, -10.4, zT)
        # on the terrace between the wings and the stairs: a kerbed lawn along the hall with a row of clipped cones
        ba, bb = (1.4, ub - 1.3) if ua < uc else (ua + 1.3, 45.7)
        block(ba, bb, -11.8, -2.2, zT - 0.3, zT + 0.28, 'stone_trim', top='grass')
        for k in range(4):
            c = (ba + 1.2 + k * (bb - ba - 2.4) / 3, -4.0)
            mb.cylinder(c, 0.75, zT + 0.25, zT + 2.9, 'shrub_green', seg=10, r1=0.06)
            mb.cylinder((c[0], -9.6), 0.8, zT + 0.25, zT + 1.0, 'shrub_green', seg=10, r1=0.85)
            mb.cylinder((c[0], -9.6), 0.85, zT + 1.0, zT + 1.4, 'shrub_green', seg=10, r1=0.4)
    for sg in (-1, 1):                                                 # globe lamps on the plaza by the flights
        lamp_post(mb, uc + sg * (hp + sw + 1.2), vp - 1.6, h=3.4, z=zP - 0.04 * 1.6)


def daewoo_rear(mb, P, Le, plinth, floors, fh, Hw, wall):
    """The back of 대우관 (Google Street View 2009-11, from the drive behind it; the hall dates from 1996): none of the
    buttresses and battlements of the old halls but a plain coped parapet with the slate roof behind; single windows
    in pairs; in the middle a broad tower 2.5 m out that rises a storey and a half over the parapet, its middle part
    the highest, with a row of five vent pipes on top and a back door at its foot; either side, half way out to the
    wings, a stair glazed from the ground floor to the top in one tall dark screen, a plain box over it on the roof;
    a few downpipes.  P: the back wall, s from its east end (the tower's axis at Le / 2, as the front tower's)."""
    sc = Le / 2
    tw, tp = 6.0, 2.5               # back tower: half width, projection
    st, sw = 12.6, 1.6              # stair bays: distance from the middle, half width of the glazing
    zt = plinth + floors * fh       # top of the window floors
    for a, b in ((0.0, sc - st - sw - 0.7), (sc - st + sw + 0.7, sc - tw - 0.2), (sc + tw + 0.2, sc + st - sw - 0.7),
                 (sc + st + sw + 0.7, Le)):
        window_grid(mb, P, Le, plinth, floors, fh, 3.3, wall, ww=0.42, trim='stone_trim', mull=1, s_start=a, s_end=b)
    for c in (sc - st, sc + st):
        hole = (c - sw, c + sw, plinth + 0.9, zt - 0.3)
        wall_holes(mb, P, c - sw - 0.7, c + sw + 0.7, plinth, zt, wall, [hole])
        reveal(mb, P, *hole, 0.25, wall)
        glazing(mb, P, *hole, -0.25, 3, floors * 2, 'frame_dark')
        mb.box(P(c, Hw + 1.3, -1.5), (2 * sw + 1.8, 3.0, 3.6), wall, mats={'top': 'roof_flat'})
        bar(mb, P, c - sw - 0.95, Hw + 3.12, c + sw + 0.95, Hw + 3.12, 0.16, 0.0, 0.1, 'stone_trim', ends=True)
    flat_wall(mb, P, sc - tw - 0.2, sc + tw + 0.2, plinth, zt, wall)              # (behind the tower)
    flat_wall(mb, P, 0, Le, zt, Hw, wall)
    bar(mb, P, -0.15, Hw + 0.15, Le + 0.15, Hw + 0.15, 0.3, -0.3, 0.12, 'stone_trim', ends=True)   # coping
    for s in (sc - 18.2, sc - 8.4, sc + 8.4, sc + 18.2):                              # downpipes
        bar(mb, P, s, -0.6, s, Hw, 0.14, 0.0, 0.14, 'metal_dark')
    # the tower: the flanks to ht1, the middle (|s - sc| < 3) to ht2; its upper part runs back into the roof
    T = lambda s, z, d=0.0: P(s, z, d + tp)
    ht1, ht2, mid = Hw + 3.9, Hw + 5.4, 3.0
    for a, b in ((sc - tw, sc - mid), (sc + mid, sc + tw)):
        window_grid(mb, T, Le, plinth, floors, fh, b - a, wall, ww=0.3, trim='stone_trim', mull=0, s_start=a, s_end=b)
        flat_wall(mb, T, a, b, zt, ht1, wall)
        flat_wall(mb, T, a, b, -1.0, plinth, wall)
        mb.quad(P(a, ht1, -6.0), P(b, ht1, -6.0), P(b, ht1, tp), P(a, ht1, tp), 'roof_flat')
    window_grid(mb, T, Le, plinth + fh, floors - 1, fh, 3.0, wall, ww=0.55, trim='stone_trim', mull=1,
                s_start=sc - mid, s_end=sc + mid)
    door = (sc - 1.5, sc + 1.5, 0.9, 3.5)                      # the back door, from the yard (about 1 m up here)
    wall_holes(mb, T, sc - mid, sc + mid, -1.0, plinth + fh, wall, [door])
    reveal(mb, T, *door, 0.4, wall)
    shopfront(mb, T, door[0], door[1], door[2], door[3], -0.4, bays=4, door_h=2.3)
    vestibule(mb, T, door[0] - 0.2, door[1] + 0.2, door[2] + 0.002, door[3] - 0.05, -0.42, 2.0, lights=1)
    flat_wall(mb, T, sc - mid, sc + mid, zt, ht2, wall)
    mb.quad(P(sc - mid, ht2, -6.0), P(sc + mid, ht2, -6.0), P(sc + mid, ht2, tp), P(sc - mid, ht2, tp), 'roof_flat')
    for s0, z1, z0_ in ((sc - tw, ht1, -1.0), (sc - mid, ht2, ht1)):                  # the sides (east-facing)
        mb.quad(P(s0, z0_, -6.0), P(s0, z0_, tp), P(s0, z1, tp), P(s0, z1, -6.0), wall)
    for s1, z1, z0_ in ((sc + tw, ht1, -1.0), (sc + mid, ht2, ht1)):                  # (west-facing)
        mb.quad(P(s1, z0_, tp), P(s1, z0_, -6.0), P(s1, z1, -6.0), P(s1, z1, tp), wall)
    for s0, s1, z1 in ((sc - tw, sc + tw, ht1), (sc - mid, sc + mid, ht2)):            # its back, in the roof
        mb.quad(P(s1, Hw - 0.5, -6.0), P(s0, Hw - 0.5, -6.0), P(s0, z1, -6.0), P(s1, z1, -6.0), wall)
    for s in (sc - tw, sc - mid, sc + mid, sc + tw):                                  # strips up the tower
        bar(mb, T, s, -1.0, s, (ht2 if abs(s - sc) < mid + 0.1 else ht1) + 0.25, 0.45, 0.0, 0.22, wall, ends=True)
    for a, b, z in ((sc - tw - 0.15, sc - mid, ht1), (sc + mid, sc + tw + 0.15, ht1), (sc - mid - 0.15, sc + mid + 0.15, ht2)):
        bar(mb, T, a, z + 0.12, b, z + 0.12, 0.25, -0.2, 0.3, 'stone_trim', ends=True)
    for k in range(5):                                                                # vent pipes
        c = P(sc - 2.0 + k, 0.0, tp - 1.3)
        mb.cylinder((c[0], c[1]), 0.15, ht2, ht2 + 1.6, 'metal', seg=8)
        mb.cylinder((c[0], c[1]), 0.22, ht2 + 1.6, ht2 + 1.75, 'metal', seg=8)


def daewoo_back(mb, z0):
    """The yard behind 대우관 (Street View 2009-11; levels from tools/build_campus.py DAEWOO_BACK), in the hall frame
    (u, v): the long planter in the recess between the wings, low concrete walls round soil and pointed conifers;
    the parking bays painted on the car park; the iron fence along the road to 북문 above its east side."""
    db = CAMPUS['daewoo_back']
    hy = lambda u, v: db['h0'] + db['su'] * (u - db['u0']) + db['sv'] * (v - db['v0']) - z0
    gl = local_ground(mb)
    (u0, v0), (u1, _), (_, v1) = db['planter'][0], db['planter'][1], db['planter'][2]
    th, ht = 0.25, 0.85

    def wall_run(a, b, inward):
        """a planter wall from a to b (u, v), its inside towards `inward` (unit 2D), top following the yard"""
        a, b, nn = Vector(a), Vector(b), Vector(inward) * th
        pts = [(a, 0), (b, 0), (b, 1), (a, 1)]
        q = lambda p, k, top: (*(p + nn * k), hy(*p) + (ht if top else -0.3))
        mb.quad(q(a, 0, False), q(b, 0, False), q(b, 0, True), q(a, 0, True), 'concrete')
        mb.quad(q(b, 1, False), q(a, 1, False), q(a, 1, True), q(b, 1, True), 'concrete')
        mb.quad(q(a, 0, True), q(b, 0, True), q(b, 1, True), q(a, 1, True), 'stone_trim')
        mb.quad(q(a, 1, False), q(a, 0, False), q(a, 0, True), q(a, 1, True), 'concrete')
        mb.quad(q(b, 0, False), q(b, 1, False), q(b, 1, True), q(b, 0, True), 'concrete')

    # two planters, either side of the paved space in front of the back tower and its door
    for ua, ub in ((u0, 17.0), (30.1, u1)):
        wall_run((ua, v0), (ub, v0), (0, 1))
        wall_run((ub, v0), (ub, v1), (-1, 0))
        wall_run((ub, v1), (ua, v1), (0, -1))
        wall_run((ua, v1), (ua, v0), (1, 0))
        zs = lambda u, v: hy(u, v) + ht - 0.15
        mb.quad((ua + th, v0 + th, zs(ua, v0)), (ub - th, v0 + th, zs(ub, v0)), (ub - th, v1 - th, zs(ub, v1)),
                (ua + th, v1 - th, zs(ua, v1)), 'soil')
    # parking bays: white lines either side of every stall (cars nose in along u)
    for (uc, face) in db['rows']:
        vk = db['row_v'][0]
        while vk <= db['row_v'][1] + 0.01:
            if not (db['gap'][0] < vk < db['gap'][1]):
                for v in (vk - db['stall'] / 2, vk + db['stall'] / 2):
                    ua, ub = uc - 2.5, uc + 2.5
                    z = lambda u: max(hy(u, v), gl(u, v)) + 0.03
                    mb.quad((ua, v - 0.06, z(ua)), (ub, v - 0.06, z(ub)), (ub, v + 0.06, z(ub)), (ua, v + 0.06, z(ua)),
                            'paint_white')
            vk += db['stall']
    # the iron fence along the road to 북문, posts every 2.4 m on the ground and pickets between
    pts = [Vector(p) for p in db['fence']]
    for pa, pb in zip(pts, pts[1:]):
        d = pb - pa
        n = max(1, int(d.length / 2.4))
        for k in range(n):
            a = pa + d * (k / n)
            b = pa + d * ((k + 1) / n)
            za, zb = gl(*a) + 0.02, gl(*b) + 0.02
            mb.box((a.x, a.y, za + 0.6), (0.07, 0.07, 1.25), 'metal_dark')
            rz = math.atan2(d.y, d.x)
            for zz in (0.18, 1.08):
                m_ = (a + b) / 2
                mb.box((m_.x, m_.y, (za + zb) / 2 + zz), ((b - a).length, 0.04, 0.05), 'metal_dark', rotz=rz)
            npk = int((b - a).length / 0.16)
            for j in range(1, npk):
                p_ = a + (b - a) * (j / npk)
                zp = za + (zb - za) * (j / npk)
                mb.box((p_.x, p_.y, zp + 0.63), (0.025, 0.025, 0.9 if j % 2 else 0.72), 'metal_dark', rotz=rz)
        bpt = pts[-1]
        mb.box((bpt.x, bpt.y, gl(*bpt) + 0.62), (0.07, 0.07, 1.25), 'metal_dark')


def daewoo():
    """대우관 (1996): a six-storey hall in white stone, Collegiate Gothic like the old halls but pale
    (reference/대우관_블로그_본관_정면_상뜰.jpg): an H plan whose end pavilions stand forward with tall gables
    towards the round pine garden (상뜰), a long slate roof between them and a raised central entrance bay.
    It stands on a terrace over the 상뜰 with the main door down in the podium in front (daewoo_front); the tower
    door on the terrace is a tall pointed arch of dark glass (reference/대우관_정면_전경.jpg)."""
    b = bld(242897922)
    fp = b['footprint']
    a, bb = Vector(fp[3]), Vector(fp[4])                 # the recessed front between the pavilions
    t = (bb - a).normalized()
    nl = Vector((-t.y, t.x))                              # into the building (north); the front faces -nl
    ang = math.atan2(t.y, t.x)
    W = lambda u, v: tuple(a + t * u + nl * v)
    lv = CAMPUS['daewoo_front']                           # levels from tools/build_campus.py (DAEWOO)
    centre = dict(b, footprint=[W(0.4, 0), W(46.7, 0), W(46.7, 14.8), W(0.4, 14.8)])
    out = gothic('daewoo', centre, tuple(-nl), 6, tower_w=9.0, tower_extra=2.5, ivy=0, wings=False, fh=3.6,
                 wall='stone_white', stairs=dict(none=True), door=dict(w=3.0, arch='pointed', spring=2.45, style='modern'),
                 z_floor=lv['floor'], rear=daewoo_rear)
    z0 = out[0].z_base
    zT, zP = lv['terrace'] - z0, lv['plaza'] - z0
    # three steps from the terrace up to the tower door
    stair_flight(out[0], 0, out[0].tower_front, 6.4, 1.2, n=3, mat='stone_step', landing=1.0, tread=0.35, flare=0.4,
                 ground=zP, zbot=zT)
    mb = MeshBuilder('lm_daewoo_pavilions')
    mb.xf = local_frame(a.x, a.y, ang, z0)
    gable_hall(mb, -12.1, 0.0, -12.2, 24.5, 6, 3.6, 'stone_white')
    gable_hall(mb, 47.1, 55.5, -10.9, 24.3, 6, 3.6, 'stone_white')
    fr = MeshBuilder('lm_daewoo_front')
    fr.xf = local_frame(a.x, a.y, ang, z0)
    daewoo_front(fr, zT, zP, lv['u0'], lv['u1'], vp=lv['podium'])
    bk = MeshBuilder('lm_daewoo_back')
    bk.xf = local_frame(a.x, a.y, ang, z0)
    daewoo_back(bk, z0)
    return out + [mb, fr, bk]


def yeonhui():
    """연희관 (1956): a stone Gothic hall, H plan like 대우관 but in the dark rubble of the old halls, with a central
    tower and ivy over the walls (yonsei.ac.kr building history photo, reference/연희관_*.jpg)."""
    b = bld(245623759)
    fp = b['footprint']
    a, bb = Vector(fp[3]), Vector(fp[4])
    t = (bb - a).normalized()
    nl = Vector((-t.y, t.x))
    ang = math.atan2(t.y, t.x)
    W = lambda u, v: tuple(a + t * u + nl * v)
    centre = dict(b, footprint=[W(0.4, 0), W(39.9, 0), W(39.9, 14.2), W(0.4, 14.2)])
    out = gothic('yeonhui', centre, tuple(-nl), 4, tower_w=8.5, tower_extra=9.5, ivy=0.85, wings=False, fh=4.1,
                 stairs=dict(width=4.4, wl=5.6), door=dict(w=3.3, style='four'))
    mb = MeshBuilder('lm_yeonhui_pavilions')
    iv = MeshBuilder('lm_yeonhui_pavilions_ivy')
    mb.xf = iv.xf = local_frame(a.x, a.y, ang, out[0].z_base)
    gable_hall(mb, -14.0, 0.0, -7.9, 28.8, 4, 4.1, 'stone_rubble', pitch=1.1, plinth=1.3, iv=iv, ivy=0.85, seed=3, gothic_trim=True)
    gable_hall(mb, 40.3, 52.0, -6.7, 30.1, 4, 4.1, 'stone_rubble', pitch=1.1, plinth=1.3, iv=iv, ivy=0.85, seed=9, gothic_trim=True)
    return out + [mb, iv]


def daewoo_annex():
    """대우관 별관: the same pale stone Gothic, five storeys, end gables on the front."""
    return gothic('daewoo_annex', bld(242897923), (-0.97, 0.24), 5, tower_w=7.0, tower_extra=1.5, ivy=0, wings=True,
                  fh=3.6, wall='stone_white', portal='flat')


# ============================================================================= 대강당 앞 농구장
def basketball_court():
    """The 1997 outdoor basketball court in front of the 대강당 (later the site of 금호아트홀): a 28 x 15 m concrete
    slab with painted lines (FIBA rules of the time: trapezoid lanes, 6.25 m three-point arc) and two hoops on
    steel posts behind the baselines.  No photo found, so a plain standard court."""
    C = CAMPUS.get('statues', {}).get('court')
    if not C:
        return []
    L, W = C['L'], C['W']
    mb = MeshBuilder('lm_court')
    mb.xf = local_frame(C['pos'][0], C['pos'][1], C['rot'], C['h'])
    z = 0.06
    # slab with a skirt so it sits cleanly on the flattened ground
    mb.box((0, 0, z / 2 - 0.25), (L + 2.0, W + 2.0, z + 0.5), 'asphalt', skip=('bottom',))
    lw = 0.05

    def line(x0, y0, x1, y1):
        dx, dy = x1 - x0, y1 - y0
        n = math.hypot(dx, dy) or 1
        ox, oy = -dy / n * lw / 2, dx / n * lw / 2
        mb.face([(x0 + ox, y0 + oy, z + 0.012), (x0 - ox, y0 - oy, z + 0.012), (x1 - ox, y1 - oy, z + 0.012), (x1 + ox, y1 + oy, z + 0.012)], 'paint_white')

    def arc(cx, cy, r, a0, a1, seg=24):
        pts = [(cx + r * math.cos(a0 + (a1 - a0) * k / seg), cy + r * math.sin(a0 + (a1 - a0) * k / seg)) for k in range(seg + 1)]
        for p, q in zip(pts, pts[1:]):
            line(p[0], p[1], q[0], q[1])

    hl, hw = L / 2, W / 2
    for (x0, y0, x1, y1) in ((-hl, -hw, hl, -hw), (hl, -hw, hl, hw), (hl, hw, -hl, hw), (-hl, hw, -hl, -hw), (0, -hw, 0, hw)):
        line(x0, y0, x1, y1)
    arc(0, 0, 1.8, 0, 2 * math.pi, 32)
    for sg in (-1, 1):
        bx = sg * hl                               # baseline
        ft = bx - sg * 5.8                         # free-throw line
        # trapezoid lane: 6.0 m wide at the baseline, 3.6 m at the free-throw line
        line(bx, -3.0, ft, -1.8); line(bx, 3.0, ft, 1.8); line(ft, -1.8, ft, 1.8)
        arc(ft, 0, 1.8, -math.pi / 2, math.pi / 2, 16) if sg < 0 else arc(ft, 0, 1.8, math.pi / 2, 3 * math.pi / 2, 16)
        # three-point line: 6.25 m arc round the basket (1.575 m in from the baseline)
        hx = bx - sg * 1.575
        a = math.asin(min(1.0, (hw - 0.9) / 6.25))
        if sg < 0:
            arc(hx, 0, 6.25, -a, a, 28)
        else:
            arc(hx, 0, 6.25, math.pi - a, math.pi + a, 28)
        for yy in (-1, 1):                        # the straight bits down to the baseline
            ex = hx + (-sg) * 6.25 * math.cos(a)
            line(bx, yy * 6.25 * math.sin(a), ex, yy * 6.25 * math.sin(a))
        # hoop: post 1 m behind the baseline, arm out to the backboard 1.2 m inside it, rim at 3.05 m
        px = bx + sg * 1.0
        mb.cylinder((px, 0), 0.09, z, 3.6, 'metal_dark', seg=10)
        mb.box((px - sg * 1.1, 0, 3.45), (2.2, 0.14, 0.14), 'metal_dark')
        mb.box((bx - sg * 1.2 + sg * 0.03, 0, 3.4), (0.05, 1.8, 1.05), 'paint_white')
        mb.box((bx - sg * 1.2 - sg * 0.002, 0, 3.25), (0.01, 0.59, 0.45), 'metal_dark', skip=('bottom', 'top'))
        rc = bx - sg * 1.575
        # rim: an orange steel ring (18 straight pieces of 2 cm tube) 45 cm across at 3.05 m, bolted to the board by a bracket
        seg, rr = 18, 0.225
        for k in range(seg):
            a0 = 2 * math.pi * (k + 0.5) / seg
            mb.box((rc + rr * math.cos(a0), rr * math.sin(a0), 3.05), (0.03, 2 * math.pi * rr / seg * 1.05, 0.03), 'banner_orange',
                   rotz=a0)
        bkx = bx - sg * 1.2
        mb.box(((bkx + rc + sg * rr) / 2 if False else (bkx + (rc + sg * rr)) / 2, 0, 3.05), (abs(bkx - (rc + sg * rr)) + 0.02, 0.12, 0.03), 'banner_orange')
        mb.box((bkx - sg * 0.02, 0, 3.05), (0.04, 0.45, 0.05), 'metal_dark')
        # white net: 12 strings from the rim down to a narrower ring 40 cm below
        for k in range(12):
            a0 = 2 * math.pi * k / 12
            a1 = a0 + math.pi / 12
            top = (rc + rr * math.cos(a0), rr * math.sin(a0), 3.05)
            bot = (rc + 0.13 * math.cos(a1), 0.13 * math.sin(a1), 2.65)
            top2 = (rc + rr * math.cos(a0 + math.pi / 6), rr * math.sin(a0 + math.pi / 6), 3.05)
            for (u, v) in ((top, bot), (top2, bot)):
                dx, dy = -(v[1] - u[1]) * 0.0 + 0.007, 0.007
                q = [(u[0] - dx, u[1] - dy, u[2]), (u[0] + dx, u[1] + dy, u[2]), (v[0] + dx, v[1] + dy, v[2]), (v[0] - dx, v[1] - dy, v[2])]
                mb.face(q, 'paint_white')
                mb.face(q[::-1], 'paint_white')
        for zz, rn in ((2.9, 0.19), (2.77, 0.16)):          # cross-strings
            pts = [(rc + rn * math.cos(2 * math.pi * k / 12), rn * math.sin(2 * math.pi * k / 12), zz) for k in range(13)]
            for u, v in zip(pts, pts[1:]):
                q = [(u[0], u[1], zz - 0.008), (v[0], v[1], zz - 0.008), (v[0], v[1], zz + 0.008), (u[0], u[1], zz + 0.008)]
                mb.face(q, 'paint_white')
                mb.face(q[::-1], 'paint_white')
    return [mb]


# ============================================================================= 활천대 (독수리상 옆)
# The sculpture, from the 2017 photos of it (reference/활천대_2017_연세대블로그_*.jpg; the name plate reads 「활천대 기증
# 전기공학과 동창회 (1974년)」): a white stone column of cross section, carved all over with abstract figures in low
# relief, in three drums with a dark joint between them and its four arms ending above in upright prongs of
# different heights; it stands on a square slab with a carved edge, on a lower cross-shaped pedestal (letters cut in
# its faces), on a round dark plinth in the water.  The 1997 basin, from the 2009 photo (reference/활천대_2009_연세춘추.jpg,
# 「활천대는 독수리상 옆에 있는 분수대다」): a round pool about 6.4 m across with a low light rim, a tall jet out of
# the top of the column, and a ring of jets on the rim arching up and in towards the column, a bell of water as high
# as the column.  (Since 백양로's rebuilding it stands in front of 제1공학관 in a small brick-edged pool without jets.)
FOUNTAIN_COL = dict(plinth=0.45, ped=1.25, slab=1.52, top=3.72, arm=0.55, arm_w=0.34, core=0.3)
FOUNTAIN_JETS = dict(n=32, land=1.12, peak=3.5)            # web/src/water/fountain.js mirrors these


def _relief(mb, c, n, t, w, z0, z1, rnd, mat, depth=0.05):
    """carved low relief on a vertical face: c its centre line foot (x, y), n the outward normal, t the face's own
    horizontal direction, w its width; little blocks and ribs standing a few cm proud, like the 활천대 figures"""
    for _ in range(int(w * (z1 - z0) * 9)):
        u = rnd.uniform(-w / 2 + 0.04, w / 2 - 0.04)
        z = rnd.uniform(z0 + 0.05, z1 - 0.05)
        bw, bh = rnd.uniform(0.04, 0.14), rnd.uniform(0.05, 0.3)
        d = depth * rnd.uniform(0.4, 1.0)
        x, y = c[0] + t[0] * u + n[0] * d / 2, c[1] + t[1] * u + n[1] * d / 2
        mb.box((x, y, z), (bw, d, bh), mat, rotz=math.atan2(t[1], t[0]), skip=('bottom', 'back'))


def fountain():
    """활천대 (活泉臺, 1974): the electrical engineering alumni's fountain beside the eagle (see FOUNTAIN_COL)."""
    F = CAMPUS.get('statues', {}).get('fountain')
    if not F:
        return []
    r = F['r']
    rnd = random.Random(1974)
    mb = MeshBuilder('lm_fountain')
    mb.xf = local_frame(F['pos'][0], F['pos'][1], F.get('rot', 0.0), F['h'])
    # rim: a low ring of light granite (outer and inner walls, flat top) round the water
    seg = 48
    mb.cylinder((0, 0), r + 0.4, -0.6, 0.5, 'granite_light', seg=seg, cap_top=False)
    for k in range(seg):
        a0, a1 = 2 * math.pi * k / seg, 2 * math.pi * (k + 1) / seg
        c0, s0, c1, s1 = math.cos(a0), math.sin(a0), math.cos(a1), math.sin(a1)
        mb.face([(r * c0, r * s0, 0.5), (r * c1, r * s1, 0.5), ((r + 0.4) * c1, (r + 0.4) * s1, 0.5), ((r + 0.4) * c0, (r + 0.4) * s0, 0.5)], 'granite_light')
        mb.face([(r * c1, r * s1, 0.0), (r * c0, r * s0, 0.0), (r * c0, r * s0, 0.5), (r * c1, r * s1, 0.5)], 'stone_granite')
    mb.cylinder((0, 0), r, -0.2, 0.0, 'concrete_dark', seg=seg)                     # basin floor
    # the water surface (level 0.375) is drawn live in the web app: web/src/water/fountain.js (Ultra Water)
    C = FOUNTAIN_COL
    mb.cylinder((0, 0), 0.9, 0.0, C['plinth'], 'concrete_dark', seg=28)             # the round dark plinth
    # lower pedestal: a cross of two slabs (0.95 x 0.42 m), letters cut in its faces
    for ang in (0.0, math.pi / 2):
        mb.box((0, 0, (C['plinth'] + C['ped']) / 2), (0.95, 0.42, C['ped'] - C['plinth']), 'stone_white', rotz=ang)
    for k in range(4):
        a = k * math.pi / 2
        n_, t_ = (math.cos(a), math.sin(a)), (-math.sin(a), math.cos(a))
        _relief(mb, (n_[0] * 0.475, n_[1] * 0.475), n_, t_, 0.42, C['plinth'] + 0.1, C['ped'] - 0.08, rnd, 'stone_white', 0.03)
    # the square slab with a carved (wavy) edge
    mb.box((0, 0, (C['ped'] + C['slab']) / 2), (1.38, 1.38, C['slab'] - C['ped']), 'stone_white')
    for k in range(4):
        a = k * math.pi / 2
        n_, t_ = (math.cos(a), math.sin(a)), (-math.sin(a), math.cos(a))
        for j in range(9):
            u = -0.6 + j * 0.15
            x, y = n_[0] * 0.7 + t_[0] * u, n_[1] * 0.7 + t_[1] * u
            mb.box((x, y, C['ped'] + 0.06 + 0.16 * (j % 2)), (0.1, 0.035, 0.09), 'stone_white', rotz=a + math.pi / 2, skip=('back',))
    # the column: a core and four arms, in three drums with dark joints
    drums = [(C['slab'], 2.24), (2.27, 2.99), (3.02, C['top'])]
    for z0, z1 in drums:
        mb.box((0, 0, (z0 + z1) / 2), (C['core'] * 2, C['core'] * 2, z1 - z0), 'stone_white')
        for ang in (0.0, math.pi / 2):
            mb.box((0, 0, (z0 + z1) / 2), (C['arm'] * 2, C['arm_w'], z1 - z0), 'stone_white', rotz=ang)
        for k in range(4):
            a = k * math.pi / 2
            n_, t_ = (math.cos(a), math.sin(a)), (-math.sin(a), math.cos(a))
            _relief(mb, (n_[0] * C['arm'], n_[1] * C['arm']), n_, t_, C['arm_w'], z0, z1, rnd, 'stone_white')
            for sd in (-1, 1):          # the arm's two side faces and the core's corner faces between the arms
                o = (n_[0] * (C['core'] + (C['arm'] - C['core']) / 2) + t_[0] * sd * C['arm_w'] / 2,
                     n_[1] * (C['core'] + (C['arm'] - C['core']) / 2) + t_[1] * sd * C['arm_w'] / 2)
                _relief(mb, o, (t_[0] * sd, t_[1] * sd), n_, C['arm'] - C['core'], z0, z1, rnd, 'stone_white')
    for z0, z1 in zip([d[1] for d in drums[:-1]], [d[0] for d in drums[1:]]):            # the dark joints
        mb.box((0, 0, (z0 + z1) / 2), (C['arm'] * 2 - 0.06, C['arm_w'] - 0.06, z1 - z0 + 0.01), 'concrete_dark')
        mb.box((0, 0, (z0 + z1) / 2), (C['arm_w'] - 0.06, C['arm'] * 2 - 0.06, z1 - z0 + 0.01), 'concrete_dark')
    # the prongs: each arm ends above in two upright blades of different heights
    for k in range(4):
        a = k * math.pi / 2
        n_, t_ = (math.cos(a), math.sin(a)), (-math.sin(a), math.cos(a))
        for j, (off, h) in enumerate(((-0.09, rnd.uniform(0.22, 0.4)), (0.09, rnd.uniform(0.08, 0.25)))):
            dd = C['arm'] - 0.12
            mb.box((n_[0] * dd + t_[0] * off, n_[1] * dd + t_[1] * off, C['top'] + h / 2), (0.2, 0.15, h), 'stone_white',
                   rotz=a, skip=('bottom',))
    mb.cylinder((0, 0), 0.07, C['top'], C['top'] + 0.12, 'metal_dark', seg=8)        # the jet's nozzle
    sp = MeshBuilder('lm_fountain_spray')
    sp.xf = mb.xf
    sp.cylinder((0, 0), 0.13, C['top'] + 0.1, C['top'] + 2.5, 'water_spray', seg=12, r1=0.04)   # the tall central jet
    sp.cylinder((0, 0), 0.95, 0.4, C['top'] + 0.5, 'water_spray', seg=24, r1=0.22, cap_top=False)  # falling back over the column
    # the ring of jets on the rim, arching up and in to land at the column's foot (a bell as high as the column)
    J = FOUNTAIN_JETS
    r0 = r - 0.12
    for k in range(J['n']):
        a = 2 * math.pi * (k + 0.5) / J['n']
        c, s_ = math.cos(a), math.sin(a)
        prof = []
        for q in range(13):
            f = q / 12
            rad = r0 - (r0 - J['land']) * f ** 0.85             # it leaves the rim steeply, falls in near the column
            z = 0.5 + (J['peak'] - 0.5) * 4 * f * (1 - f) * (1.0 - 0.25 * f) / 0.89 - 0.12 * f
            prof.append((rad, z))
        w = 0.045
        for (ra, za), (rb, zb) in zip(prof, prof[1:]):
            ring = lambda rad, z: [(rad * c - s_ * w, rad * s_ + c * w, z), (rad * c + s_ * w, rad * s_ - c * w, z),
                                   (rad * c + s_ * w, rad * s_ - c * w, z + 2 * w), (rad * c - s_ * w, rad * s_ + c * w, z + 2 * w)]
            A, B = ring(ra, za), ring(rb, zb)
            for i in range(4):
                sp.face([A[i], A[(i + 1) % 4], B[(i + 1) % 4], B[i]], 'water_spray')
        mb.cylinder((r0 * c, r0 * s_), 0.05, 0.42, 0.55, 'metal_dark', seg=6)        # nozzle on the rim
    return [mb, sp]


# ============================================================================= 용재관 (demolished)
def yongjae():
    """용재관 as in reference/용재관.jpg: white painted concrete, a slender stair tower with vertical fins and paired
    windows facing the end of 백양로, a three-storey wing with a dark hipped roof and a flat entrance canopy at the
    foot of the tower, and a five-storey block with a roof penthouse behind.  Footprints: tools/build_campus.py."""
    import generic
    st = dict(generic.STYLE['white'])
    fh = 3.6
    rnd = random.Random(1997)
    parts = {b['id']: b for b in CAMPUS['buildings'] if b['name'] == '용재관'}
    out = []

    def corners(b):
        return [tuple(p) for p in b['footprint']]

    # five-storey block: plain white walls, parapet, penthouse
    blk = parts[990003]
    mb = MeshBuilder('lm_yongjae_block')
    poly, z0 = corners(blk), blk['base']
    zt = z0 + 5 * fh
    for i in range(4):
        generic.wall_edge(mb, poly[i], poly[(i + 1) % 4], z0, zt + 0.9, 5, fh, st, rnd)
    generic.parapet_and_roof(mb, poly, zt, st, rnd)
    out.append(mb)

    # three-storey wing with a dark hipped roof
    wg = parts[990002]
    mb = MeshBuilder('lm_yongjae_wing')
    poly, z0 = corners(wg), wg['base']
    zt = z0 + 3 * fh
    for i in range(4):
        generic.wall_edge(mb, poly[i], poly[(i + 1) % 4], z0, zt, 3, fh, st, rnd)
    cx, cy, L, W, ang = min_area_rect(poly)
    generic.hip_roof(mb, cx, cy, L, W, ang, zt, 'roof_slate', pitch=0.42, over=0.7)
    # entrance canopy at the tower end of the front, on two slim posts, and the notice board under it
    f = wg['frame']
    (ox, oy), a = f['o'], f['ang']
    c, s_ = math.cos(a), math.sin(a)
    U = lambda u, v, z: (ox + u * c - v * s_, oy + u * s_ + v * c, z)
    zc = z0 + 3.3
    mb.box(U(9.5, 2.6, zc + 0.15), (11.0, 3.4, 0.3), 'plaster_white', rotz=a)
    for u in (4.6, 14.4):
        mb.box(U(u, 4.0, z0 + (zc - z0) / 2 - 1.0), (0.25, 0.25, zc - z0 + 2.0), 'plaster_white', rotz=a)
    mb.box(U(11.0, 1.08, z0 + 1.6), (4.0, 0.12, 1.4), 'metal_green', rotz=a)
    out.append(mb)

    # the stair tower: seven storeys, three vertical fins on the front, paired windows, a blank crown
    tw = parts[990001]
    mb = MeshBuilder('lm_yongjae_tower')
    poly, z0 = corners(tw), tw['base']
    zt = z0 + 6 * fh
    zc = zt + 3.2
    tst = dict(st, bay=4.0, ww=0.5, sill=0.9, head=0.7)
    for i in range(4):
        generic.wall_edge(mb, poly[i], poly[(i + 1) % 4], z0, zc, 6, fh, tst, rnd)
    generic.parapet_and_roof(mb, poly, zc - 0.6, st, rnd, clutter=False)
    u0, u1, v0, v1 = tw['frame']['uv']
    for u in (u0 + 0.15, (u0 + u1) / 2, u1 - 0.15):      # fins on the face towards 백양로 (v1)
        mb.box(U(u, v1 + 0.18, z0 + 4.0 + (zc - z0 - 4.0) / 2), (0.3, 0.36, zc - z0 - 4.0), 'plaster_white', rotz=a)
    for k in range(1, 6):                                  # thin slab lines between the floors of the front
        mb.box(U((u0 + u1) / 2, v1 + 0.05, z0 + k * fh), (u1 - u0, 0.1, 0.12), 'plaster_white', rotz=a)
    out.append(mb)
    return out


BUILDERS = {'library': library, 'union': union, 'centennial': centennial, 'underwood': underwood,
            'stimson': stimson, 'appenzeller': appenzeller, 'auditorium': auditorium, 'chapel': chapel,
            'engineering': engineering, 'hanok': hanok, 'yongjae': yongjae, 'none': lambda: [],
            'daewoo': daewoo, 'daewoo_annex': daewoo_annex, 'yeonhui': yeonhui}
