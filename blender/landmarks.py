"""Hand-modelled 1997 landmarks.  Every builder returns a list of MeshBuilders in
world coordinates (local frames are applied through MeshBuilder.xf)."""
import math, random
from mathutils import Vector, Matrix
from common import MeshBuilder, ground, min_area_rect, local_frame, offset_poly, poly_area, CAMPUS
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
    z0 = lift_base(z0, cx, cy, ang, W / 2 + 2.5, 0.9, 0.6)
    mb = MeshBuilder('lm_library')
    mb.xf = local_frame(cx, cy, ang, z0)
    H = 23.0                     # top of attic
    spring, attic0 = 16.6, 18.8
    inset = 2.4
    fh, nf, g0 = 3.6, 5, 0.9
    # plinth
    mb.prism(offset_poly(rect(L, W), 0.6), -4, g0, 'stone_granite', 'stone_granite')
    # recessed wall in the bays: per floor a bronze spandrel band, then glazing split by slim mullions
    core = rect(L - 2 * inset, W - 2 * inset)
    for i in range(4):
        a, bb = core[i], core[(i + 1) % 4]
        P, Le, t, n = edge_P(a, bb)
        flat_wall(mb, P, 0, Le, g0, g0 + 3.4, 'glass', d=-0.3)                 # ground floor: dark glazing, set back
        for k in range(int(Le / 2.0)):
            s = (k + 0.5) * Le / int(Le / 2.0)
            mb.quad(P(s - 0.06, g0, -0.25), P(s + 0.06, g0, -0.25), P(s + 0.06, g0 + 3.4, -0.25), P(s - 0.06, g0 + 3.4, -0.25), 'frame_dark')
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
    # entrance: steps up to the recessed ground floor on the 백양로 (local -y) side
    stair_flight(mb, 0, -W / 2, 17.0, g0, n=6, landing=1.6, tread=0.45, flare=1.5, cheek=0.0, rail=False, gfn=local_ground(mb))
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
    HP = 8.6                     # podium roof
    c = (5.6, -203.5)            # drum centre: pole of inaccessibility of the footprint
    R, HD = 21.4, 25.0           # drum radius / top
    seg = 96
    # podium
    mb.prism(offset_poly(fp, 0.3), z0 - 4, z0 + 0.4, 'stone_granite', 'stone_granite')
    mb.prism(fp, z0 + 0.4, z0 + HP, 'stone_ashlar', 'roof_flat')
    for zz in (3.2, 6.0):
        mb.prism(offset_poly(fp, 0.04), z0 + zz, z0 + zz + 0.14, 'concrete_dark')
    mb.prism(offset_poly(fp, 0.12), z0 + HP, z0 + HP + 0.9, 'stone_ashlar', 'stone_ashlar')
    # drum with incised horizontal joints above the podium
    joints = [HP + 0.9 + k * 3.3 for k in range(1, 5)]
    z = z0 + 0.4
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
    # deep dark portal in the podium's 백양로 (west) face, framed by projecting stone jambs and a lintel
    a, bb = Vector((-11.05, -181.26)), Vector((-28.82, -256.68))
    P, Le, t, n = edge_P(tuple(a), tuple(bb), z0)
    s0, s1, zt, dep = Le * 0.5, Le * 0.5 + 17.0, 6.3, 1.4
    mb.quad(P(s0, 0.4, 0.03), P(s1, 0.4, 0.03), P(s1, zt, 0.03), P(s0, zt, 0.03), 'glass')
    for k in range(1, 6):          # mullions deep in the shadow
        sm = s0 + (s1 - s0) * k / 6
        mb.quad(P(sm - 0.08, 0.4, 0.05), P(sm + 0.08, 0.4, 0.05), P(sm + 0.08, zt, 0.05), P(sm - 0.08, zt, 0.05), 'frame_dark')
    for sj in (s0, s1):
        w = 1.1 if sj == s0 else -1.1
        mb.quad(P(sj, 0.4, 0), P(sj, 0.4, dep), P(sj, zt + 1.2, dep), P(sj, zt + 1.2, 0), 'stone_ashlar')
        mb.quad(P(sj - w, 0.4, dep), P(sj - w, 0.4, 0), P(sj - w, zt + 1.2, 0), P(sj - w, zt + 1.2, dep), 'stone_ashlar')
        mb.quad(P(sj, 0.4, dep), P(sj - w, 0.4, dep), P(sj - w, zt + 1.2, dep), P(sj, zt + 1.2, dep), 'stone_ashlar')
    mb.quad(P(s0 - 1.1, zt, dep), P(s1 + 1.1, zt, dep), P(s1 + 1.1, zt + 1.2, dep), P(s0 - 1.1, zt + 1.2, dep), 'stone_ashlar')
    mb.quad(P(s0 - 1.1, zt, 0), P(s1 + 1.1, zt, 0), P(s1 + 1.1, zt, dep), P(s0 - 1.1, zt, dep), 'concrete_dark')
    mb.quad(P(s0 - 1.1, zt + 1.2, dep), P(s1 + 1.1, zt + 1.2, dep), P(s1 + 1.1, zt + 1.2, 0), P(s0 - 1.1, zt + 1.2, 0), 'stone_ashlar')
    # granite steps down to the forecourt
    for k in range(3):
        q = [P(s0 - 1.5, 0.4 - k * 0.15, dep + 0.4 + k * 0.6), P(s1 + 1.5, 0.4 - k * 0.15, dep + 0.4 + k * 0.6)]
        mb.quad(P(s0 - 1.5, 0.4 - k * 0.15, dep + k * 0.6), P(s1 + 1.5, 0.4 - k * 0.15, dep + k * 0.6),
                q[1], q[0], 'stone_granite')
    return [mb, sh]


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
    """Terrain height in a builder's local frame (relative to its z origin): ground_local(lx, ly)."""
    def g(lx, ly):
        w = mb.xf @ Vector((lx, ly, 0.0))
        return ground(w.x, w.y) - mb.xf.translation.z
    return g


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
        # as many risers as the ground in front needs: the foot of the flight stands on the terrain
        for n in range(2, 19):
            zbot = gfn(x, y_face - landing - n * tread) - 0.04
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


def lamp_post(mb, x, y, h=3.6, globe='plaster_white'):
    """A cast-iron post with a white globe lamp, like those beside the 대우관 별관 steps."""
    mb.cylinder((x, y), 0.09, -0.6, h, 'metal_dark', seg=8, cap_top=False)
    mb.cylinder((x, y), 0.17, -0.6, 0.3, 'metal_dark', seg=8, cap_top=False)
    mb.cylinder((x, y), 0.2, h, h + 0.22, globe, seg=12, r1=0.3)
    mb.cylinder((x, y), 0.3, h + 0.22, h + 0.5, globe, seg=12, r1=0.2)
    mb.cylinder((x, y), 0.22, h + 0.5, h + 0.6, 'metal_dark', seg=10)


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
        zbot = gfn(0, y_foot - 0.6) - 0.03
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
           dormers=True, stairs=None, portal=None, door=None):
    cx, cy, L, W, ang, z0 = frame_for(b, front)
    stairs = dict(dict(width=None, wl=None, rise=1.3, cheeks=True, lamps=False), **(stairs or {}))
    door = dict(dict(w=3.0, arch='tudor', spring=2.55, style='grid'), **(door or {}))
    # the floor stands on the ground in front of the door, not at the lowest corner of the footprint (the halls sit on
    # slopes: 대우관 별관's front is ~3 m above that corner and would bury the whole flight); `rise` is how high the
    # porch stands over the ground just in front of the hall
    z0 = lift_base(z0, cx, cy, ang, W / 2 + (1.8 if portal == 'flat' else 3.3), 1.2, stairs['rise'])
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
                    holes = (win_holes(Le, plinth, floors, fh, 3.3, ww=0.5, s_end=s_t0)
                             + win_holes(Le, plinth, floors, fh, 3.3, ww=0.5, s_start=s_t1))
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
            wins = []
            for f in range(1, floors):
                w0, w1 = Le / 2 - min(1.3, tw * 0.15), Le / 2 + min(1.3, tw * 0.15)
                zw0, zw1 = plinth + f * fh + 0.9, plinth + (f + 1) * fh - 0.6
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
    hall_steps(mb, ty0, plinth - 0.1, sw, local_ground(mb), wall=wall, wl=stairs['wl'], cheeks=stairs['cheeks'],
               lamps=stairs['lamps'])
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
def auditorium():
    b = bld(371403811)
    cx, cy, L, W, ang, z0 = frame_for(b, (-1.0, 0.25))
    mb = MeshBuilder('lm_auditorium')
    z0 = lift_base(z0, cx, cy, ang, W * 0.8 / 2 + 11.5, 0.5, 0.45)
    mb.xf = local_frame(cx, cy, ang, z0)
    L, W = L * 0.92, W * 0.8
    H = 17.0
    hall = rect(L, W)
    mb.prism(offset_poly(hall, 0.3), -4, 0.5, 'stone_granite')
    for i in range(4):
        a, bb = hall[i], hall[(i + 1) % 4]
        P, Le, t, n = edge_P(a, bb)
        flat_wall(mb, P, 0, Le, 0.5, H, 'concrete_warm')
        # vertical fins + slit windows
        nf = int(Le / 3.2)
        for k in range(1, nf):
            s = k * Le / nf
            c = P(s, 0, 0.45)
            mb.box((c[0], c[1], z0 * 0 + (0.5 + H) / 2), (0.5, 0.9, H - 0.5), 'concrete', rotz=math.atan2(t.y, t.x), skip=('bottom',))
            mb.quad(P(s + 0.6, 6.0, 0.02), P(s + 1.3, 6.0, 0.02), P(s + 1.3, H - 2.0, 0.02), P(s + 0.6, H - 2.0, 0.02), 'glass')
        mb.quad(P(-0.6, H, 1.0), P(Le + 0.6, H, 1.0), P(Le + 0.6, H + 1.0, 1.0), P(-0.6, H + 1.0, 1.0), 'concrete')
        mb.quad(P(-0.6, H + 1.0, 1.0), P(Le + 0.6, H + 1.0, 1.0), P(Le + 0.6, H + 1.0, 0), P(-0.6, H + 1.0, 0), 'concrete')
        mb.quad(P(-0.6, H, 0), P(Le + 0.6, H, 0), P(Le + 0.6, H, 1.0), P(-0.6, H, 1.0), 'concrete')
    # shallow pitched copper-green roof
    mb.face([(-L / 2, -W / 2, H + 1.0), (L / 2, -W / 2, H + 1.0), (L / 2, 0, H + 4.5), (-L / 2, 0, H + 4.5)], 'metal_green')
    mb.face([(L / 2, W / 2, H + 1.0), (-L / 2, W / 2, H + 1.0), (-L / 2, 0, H + 4.5), (L / 2, 0, H + 4.5)], 'metal_green')
    mb.face([(-L / 2, -W / 2, H + 1.0), (-L / 2, 0, H + 4.5), (-L / 2, W / 2, H + 1.0)], 'concrete')
    mb.face([(L / 2, W / 2, H + 1.0), (L / 2, 0, H + 4.5), (L / 2, -W / 2, H + 1.0)], 'concrete')
    # front lobby (lower glass block facing 백양로) with deep canopy on columns
    ly = -W / 2 - 5
    lobby = [(-L * 0.35, ly), (L * 0.35, ly), (L * 0.35, -W / 2), (-L * 0.35, -W / 2)]
    mb.prism(lobby, -4, 0.5, 'stone_granite', 'stone_granite')
    P, Le, t, n = edge_P(lobby[0], lobby[1])
    flat_wall(mb, P, 0, Le, 0.5, 6.0, 'glass')
    for k in range(int(Le / 2.0) + 1):
        s = k * Le / int(Le / 2.0)
        mb.quad(P(s - 0.06, 0.5, 0.04), P(s + 0.06, 0.5, 0.04), P(s + 0.06, 6.0, 0.04), P(s - 0.06, 6.0, 0.04), 'frame_dark')
    for side in (1, 3):
        a, bb = lobby[side], lobby[(side + 1) % 4]
        P2, Le2, _, _ = edge_P(a, bb)
        flat_wall(mb, P2, 0, Le2, 0.5, 6.0, 'concrete_warm')
    mb.box((0, ly - 3.0, 6.6), (L * 0.8, 7.0, 0.8), 'concrete', mats={'top': 'roof_flat'})
    mb.face([(-L * 0.35, ly, 6.0), (L * 0.35, ly, 6.0), (L * 0.35, -W / 2, 6.0), (-L * 0.35, -W / 2, 6.0)], 'roof_flat')
    for k in range(6):
        x = -L * 0.38 + k * L * 0.76 / 5
        mb.cylinder((x, ly - 6.0), 0.35, 0.5, 6.2, 'concrete', seg=10, cap_top=False)
    stair_flight(mb, 0, ly - 6.8, L * 0.7, 0.5, n=5, landing=0.8, tread=0.5, flare=1.0, cheek=0.0, rail=False, gfn=local_ground(mb))
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
    st.update(wall='plaster_white', alt='plaster_white', ww=0.86, bay=3.0, sill=1.05, head=0.5, mull=2)
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
    # entrance canopy in the middle of the 백양로 facade
    mb.box((0, -W / 2 - 2.2, 4.0), (10, 4.4, 0.45), 'concrete')
    for x in (-4.5, 4.5):
        mb.cylinder((x, -W / 2 - 4.0), 0.22, 0.4, 3.8, 'concrete', seg=8, cap_top=False)
    # wide concrete flight with handrails under the canopy, glass double doors behind a landing
    stair_flight(mb, 0, -W / 2, 8.0, 0.4, n=4, mat='stone_granite', landing=1.8, tread=0.4, flare=0.6, rail=True, gfn=local_ground(mb))
    mb.quad((-2.6, -W / 2 - 0.02, 0.4), (2.6, -W / 2 - 0.02, 0.4), (2.6, -W / 2 - 0.02, 3.4), (-2.6, -W / 2 - 0.02, 3.4), 'glass')
    mb.box((0, -W / 2 - 0.03, 3.5), (5.4, 0.08, 0.16), 'frame_dark')
    mb.box((0, -W / 2 - 0.03, 0.4 + 1.5), (0.1, 0.08, 3.0), 'frame_dark')
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


def daewoo():
    """대우관 (1984): a six-storey hall in white stone, Collegiate Gothic like the old halls but pale
    (reference/대우관_블로그_본관_정면_상뜰.jpg): an H plan whose end pavilions stand forward with tall gables
    towards the round pine garden (상뜰), a long slate roof between them and a raised central entrance bay."""
    b = bld(242897922)
    fp = b['footprint']
    a, bb = Vector(fp[3]), Vector(fp[4])                 # the recessed front between the pavilions
    t = (bb - a).normalized()
    nl = Vector((-t.y, t.x))                              # into the building (north); the front faces -nl
    ang = math.atan2(t.y, t.x)
    W = lambda u, v: tuple(a + t * u + nl * v)
    centre = dict(b, footprint=[W(0.4, 0), W(46.7, 0), W(46.7, 14.8), W(0.4, 14.8)])
    out = gothic('daewoo', centre, tuple(-nl), 6, tower_w=9.0, tower_extra=2.5, ivy=0, wings=False, fh=3.6,
                 wall='stone_white', stairs=dict(width=6.0, cheeks=False, lamps=True), door=dict(w=3.2, spring=2.4, style='modern'))
    mb = MeshBuilder('lm_daewoo_pavilions')
    mb.xf = local_frame(a.x, a.y, ang, out[0].z_base)
    gable_hall(mb, -12.1, 0.0, -12.2, 24.5, 6, 3.6, 'stone_white')
    gable_hall(mb, 47.1, 55.5, -10.9, 24.3, 6, 3.6, 'stone_white')
    return out + [mb]


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


# ============================================================================= 활천 분수 (제1공학관 앞)
def fountain():
    """활천 (活泉, 'living spring'), the engineering college's fountain before 제1공학관: a round basin with a
    granite rim, water, a stepped central pedestal and a white jet.  No photo found, so a plain campus fountain."""
    F = CAMPUS.get('statues', {}).get('fountain')
    if not F:
        return []
    r = F['r']
    mb = MeshBuilder('lm_fountain')
    mb.xf = local_frame(F['pos'][0], F['pos'][1], 0.0, F['h'])
    # rim: a granite ring (outer and inner walls, flat top) round the water
    mb.cylinder((0, 0), r + 0.35, -0.6, 0.5, 'stone_granite', seg=40, cap_top=False)
    seg = 40
    for k in range(seg):
        a0, a1 = 2 * math.pi * k / seg, 2 * math.pi * (k + 1) / seg
        c0, s0, c1, s1 = math.cos(a0), math.sin(a0), math.cos(a1), math.sin(a1)
        mb.face([(r * c0, r * s0, 0.5), (r * c1, r * s1, 0.5), ((r + 0.35) * c1, (r + 0.35) * s1, 0.5), ((r + 0.35) * c0, (r + 0.35) * s0, 0.5)], 'stone_granite')
        mb.face([(r * c1, r * s1, 0.0), (r * c0, r * s0, 0.0), (r * c0, r * s0, 0.5), (r * c1, r * s1, 0.5)], 'stone_granite')
    mb.cylinder((0, 0), r, -0.2, 0.0, 'concrete_dark', seg=40)                       # basin floor
    # the water surface (level 0.375) is drawn live in the web app: web/src/water/fountain.js (Ultra Water)
    mb.cylinder((0, 0), 0.9, 0.3, 0.75, 'stone_granite', seg=20)                    # stepped pedestal
    mb.cylinder((0, 0), 0.5, 0.75, 1.25, 'stone_granite', seg=16)
    mb.cylinder((0, 0), 0.12, 1.25, 1.45, 'metal_dark', seg=10)
    sp = MeshBuilder('lm_fountain_spray')
    sp.xf = mb.xf
    sp.cylinder((0, 0), 0.22, 1.45, 4.4, 'water_spray', seg=12, r1=0.07)            # the central jet
    sp.cylinder((0, 0), 1.5, 0.4, 1.45, 'water_spray', seg=24, r1=0.3, cap_top=False)   # water falling back
    for k in range(8):                                                              # a ring of small arching jets
        a = 2 * math.pi * k / 8
        pts = [(r - 0.3 - (r - 1.4) * f, 0.42 + 1.6 * f * (1 - f) * 2.2) for f in [q / 6 for q in range(7)]]
        for (r0, z0), (r1_, z1) in zip(pts, pts[1:]):
            c, s_ = math.cos(a), math.sin(a)
            n_ = (-s_ * 0.07, c * 0.07)
            q = [(r0 * c - n_[0], r0 * s_ - n_[1], z0), (r1_ * c - n_[0], r1_ * s_ - n_[1], z1),
                 (r1_ * c + n_[0], r1_ * s_ + n_[1], z1), (r0 * c + n_[0], r0 * s_ + n_[1], z0)]
            sp.face(q, 'water_spray')
            sp.face([(x, y, zz + 0.07) for x, y, zz in q], 'water_spray')
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
