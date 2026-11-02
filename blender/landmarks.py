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
    b = bld(163525865)
    cx, cy, L, W, ang, z0 = frame_for(b, (1.0, -0.25))
    mb = MeshBuilder('lm_library')
    mb.xf = local_frame(cx, cy, ang, z0)
    H = 23.0                     # top of attic
    spring, attic0 = 15.8, 19.4
    inset = 2.4
    # plinth
    mb.prism(offset_poly(rect(L, W), 0.6), -4, 0.9, 'stone_granite', 'stone_granite')
    # glass core with floor spandrels
    core = rect(L - 2 * inset, W - 2 * inset)
    for i in range(4):
        a, bb = core[i], core[(i + 1) % 4]
        P, Le, t, n = edge_P(a, bb)
        for f in range(5):
            zf = 0.9 + f * 3.8
            flat_wall(mb, P, 0, Le, zf, zf + 0.9, 'concrete_dark')
            flat_wall(mb, P, 0, Le, zf + 0.9, zf + 3.8, 'glass_green', d=-0.15)
            mb.quad(P(0, zf + 0.9, 0), P(Le, zf + 0.9, 0), P(Le, zf + 0.9, -0.15), P(0, zf + 0.9, -0.15), 'concrete_dark')
            for k in range(int(Le / 1.55)):
                s = (k + 0.5) * Le / int(Le / 1.55)
                mb.quad(P(s - 0.05, zf + 0.9, -0.1), P(s + 0.05, zf + 0.9, -0.1), P(s + 0.05, zf + 3.8, -0.1), P(s - 0.05, zf + 3.8, -0.1), 'frame_dark')
        flat_wall(mb, P, 0, Le, 0.9 + 5 * 3.8, attic0, 'concrete_dark')
    # colonnade screen
    pier = 1.1
    depth = 1.9
    outer = rect(L, W)
    for i in range(4):
        a, bb = outer[i], outer[(i + 1) % 4]
        P, Le, t, n = edge_P(a, bb)
        nb = int(round(Le / 6.3))
        bw = (Le - pier) / nb
        for k in range(nb + 1):
            s = k * bw
            pw = pier * (1.6 if k in (0, nb) else 1.0)
            s0, s1 = (s, s + pw) if k < nb else (Le - pw, Le)
            if k == 0:
                s1 = pw
            # pier box (front, sides)
            mb.quad(P(s0, 0.9, 0), P(s1, 0.9, 0), P(s1, attic0, 0), P(s0, attic0, 0), 'stone_panel')
            mb.quad(P(s1, 0.9, 0), P(s1, 0.9, -depth), P(s1, attic0, -depth), P(s1, attic0, 0), 'stone_panel')
            mb.quad(P(s0, 0.9, -depth), P(s0, 0.9, 0), P(s0, attic0, 0), P(s0, attic0, -depth), 'stone_panel')
            mb.quad(P(s0, 0.9, -depth), P(s1, 0.9, -depth), P(s1, attic0, -depth), P(s0, attic0, -depth), 'stone_panel')
            if k < nb:
                a0 = s1
                a1 = (k + 1) * bw if k + 1 < nb else Le - pier * 1.6
                arch_fill(mb, P, a0, a1, spring, attic0, depth, 'stone_panel', 'round', 12)
        # attic band with thin cornice
        flat_wall(mb, P, 0, Le, attic0, H, 'stone_panel')
        mb.quad(P(0, H, 0), P(Le, H, 0), P(Le, H, -depth), P(0, H, -depth), 'stone_panel')
        mb.quad(P(0, attic0, 0), P(0, attic0, -depth), P(Le, attic0, -depth), P(Le, attic0, 0), 'stone_panel')
        # horizontal groove lines on attic
        for zz in (attic0 + 1.2, attic0 + 2.4):
            mb.quad(P(0, zz, 0.06), P(Le, zz, 0.06), P(Le, zz + 0.12, 0.06), P(0, zz + 0.12, 0.06), 'concrete')
        # attic inner face / parapet
        flat_wall(mb, P, 0, Le, H - 1.2, H, 'concrete', d=-depth)
    mb.face([(p[0], p[1], H - 1.2) for p in offset_poly(rect(L, W), -depth)], 'roof_flat')
    # rooftop plant room
    mb.box((0, 4, H + 0.3), (16, 9, 3.0), 'concrete', mats={'top': 'roof_flat'})
    # entrance: canopy + steps on the front (local -y) side, centred
    mb.box((0, -W / 2 - 2.0, 4.6), (14, 5.0, 0.5), 'stone_panel')
    for k in range(4):
        mb.box((0, -W / 2 - 1.0 - k * 0.45, 0.9 - (k + 1) * 0.22 + 0.11), (16, 1.0 + k * 0.9, 0.22), 'stone_granite')
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
            mb.box((P(s, 0)[0] - n.x * 1.0, P(s, 0)[1] - n.y * 1.0, g / 2 + 0.3), (0.9, 0.9, g - 0.3), 'concrete',
                   rotz=math.atan2(t.y, t.x), skip=('top', 'bottom'))
        # soffit of the overhang
        mb.quad(P(0, g, 0), P(0, g, -2.0), P(Le, g, -2.0), P(Le, g, 0), 'concrete')
        # upper floors: glass wall behind a precast concrete lattice
        flat_wall(mb, P, 0, Le, g, H, 'glass', d=-0.9)
        for f in range(nf):
            zf = g + f * fh
            # slab edge band
            flat_wall(mb, P, 0, Le, zf, zf + 0.45, 'concrete')
            mb.quad(P(0, zf + 0.45, 0), P(Le, zf + 0.45, 0), P(Le, zf + 0.45, -0.9), P(0, zf + 0.45, -0.9), 'concrete')
            mb.quad(P(0, zf, -0.9), P(Le, zf, -0.9), P(Le, zf, 0), P(0, zf, 0), 'concrete')
            npan = max(2, int(round(Le / 1.7)))
            pw = Le / npan
            za, zb = zf + 0.45, zf + fh
            zm = (za + zb) / 2
            for k in range(npan):
                s0, s1 = k * pw, (k + 1) * pw
                sm = (s0 + s1) / 2
                # vertical fin
                mb.quad(P(s0 - 0.07, za, 0), P(s0 + 0.07, za, 0), P(s0 + 0.07, zb, 0), P(s0 - 0.07, zb, 0), 'concrete_warm')
                mb.quad(P(s0 + 0.07, za, 0), P(s0 + 0.07, za, -0.5), P(s0 + 0.07, zb, -0.5), P(s0 + 0.07, zb, 0), 'concrete')
                mb.quad(P(s0 - 0.07, za, -0.5), P(s0 - 0.07, za, 0), P(s0 - 0.07, zb, 0), P(s0 - 0.07, zb, -0.5), 'concrete')
                # two stacked chevrons (V) per panel -> the 학생회관 lattice
                for (zt_, zb_) in ((zb, zm), (zm, za)):
                    for (sa, sb) in ((s0 + 0.07, sm), (s1 - 0.07, sm)):
                        th = 0.11
                        mb.quad(P(sa, zt_ - th, 0), P(sb, zb_, 0), P(sb, zb_ + th * 1.6, 0), P(sa, zt_, 0), 'concrete_warm')
                        mb.quad(P(sb, zb_, 0), P(sa, zt_ - th, 0), P(sa, zt_ - th, -0.45), P(sb, zb_, -0.45), 'concrete')
        flat_wall(mb, P, 0, Le, H, H + 1.0, 'concrete')
        mb.quad(P(0, H + 1.0, 0), P(Le, H + 1.0, 0), P(Le, H + 1.0, -0.9), P(0, H + 1.0, -0.9), 'concrete')
    mb.face([(p[0], p[1], H + 0.2) for p in offset_poly(rect(L, W), -0.9)], 'roof_flat')
    mb.box((L * 0.2, 2, H + 1.6), (8, 6, 3.0), 'concrete', mats={'top': 'roof_flat'})
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
    """1997 aerial photo (reference.pdf p.4-5): a large stone drum rising out of a two-storey podium that fills
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
def ivy_patch(iv, P, s0, s1, z0, z1, density, seedoff=0):
    """Scatter ivy leaf cards on a wall rectangle, clustered with a low-freq noise mask."""
    r = random.Random(int(s0 * 13 + z0 * 7 + seedoff))
    area = (s1 - s0) * (z1 - z0)
    for k in range(int(area * density)):
        s = r.uniform(s0, s1)
        z = z0 + (z1 - z0) * (r.random() ** 1.6)          # denser near the ground
        m = 0.5 + 0.5 * math.sin(s * 0.35 + seedoff) * math.cos(z * 0.25 + s * 0.11)
        if r.random() > m * 1.3:
            continue
        sz = r.uniform(0.45, 0.85)
        off = r.uniform(0.04, 0.22)
        a = r.uniform(0, 6.283)
        ca, sa = math.cos(a) * sz / 2, math.sin(a) * sz / 2
        cell = r.randrange(4)
        u0, v0 = (cell % 2) * 0.5, (cell // 2) * 0.5
        dz = r.uniform(-0.1, 0.1)
        iv.face([P(s - ca + sa, z - sa - ca, off), P(s + ca + sa, z + sa - ca, off + dz),
                 P(s + ca - sa, z + sa + ca, off), P(s - ca - sa, z - sa + ca, off - dz)], 'leaf_ivy',
                uvs=[(u0, v0), (u0 + .5, v0), (u0 + .5, v0 + .5), (u0, v0 + .5)])


def gothic(name, b, front, floors, tower_w=8.5, tower_extra=8.0, ivy=1.0, wings=True, fh=4.1):
    cx, cy, L, W, ang, z0 = frame_for(b, front)
    mb = MeshBuilder('lm_' + name)
    iv = MeshBuilder('lm_' + name + '_ivy')
    mb.xf = iv.xf = local_frame(cx, cy, ang, z0)
    plinth = 1.3
    Hw = plinth + floors * fh + 0.6
    pitch = 0.9
    # --- main block walls
    body = rect(L, W)
    mb.prism(offset_poly(body, 0.25), -4, plinth, 'stone_granite')
    for i in range(4):
        a, bb = body[i], body[(i + 1) % 4]
        P, Le, t, n = edge_P(a, bb)
        if Le < W + 0.1:          # gable ends
            window_grid(mb, P, Le, plinth, floors, fh, 3.4, 'stone_rubble', ww=0.42, trim='stone_trim', mull=1)
            flat_wall(mb, P, 0, Le, plinth + floors * fh, Hw, 'stone_rubble')
            # gable triangle + coping
            hz = Hw + (Le / 2) * pitch
            mb.face([P(0, Hw), P(Le, Hw), P(Le / 2, hz)], 'stone_rubble')
            mb.quad(P(-0.2, Hw, 0.25), P(Le / 2, hz + 0.35, 0.25), P(Le / 2, hz + 0.35, -0.2), P(-0.2, Hw, -0.2), 'stone_trim')
            mb.quad(P(Le / 2, hz + 0.35, 0.25), P(Le + 0.2, Hw, 0.25), P(Le + 0.2, Hw, -0.2), P(Le / 2, hz + 0.35, -0.2), 'stone_trim')
            if ivy:
                ivy_patch(iv, P, 0, Le, plinth * 0, Hw, 1.8 * ivy, i)
        else:
            front_side = (i == 0)
            if front_side:
                tw = tower_w
                s_t0, s_t1 = Le / 2 - tw / 2, Le / 2 + tw / 2
                window_grid(mb, P, Le, plinth, floors, fh, 3.3, 'stone_rubble', ww=0.5, trim='stone_trim', mull=2, s_start=0, s_end=s_t0)
                window_grid(mb, P, Le, plinth, floors, fh, 3.3, 'stone_rubble', ww=0.5, trim='stone_trim', mull=2, s_start=s_t1, s_end=Le)
                flat_wall(mb, P, s_t0, s_t1, plinth, Hw, 'stone_rubble')
            else:
                window_grid(mb, P, Le, plinth, floors, fh, 3.3, 'stone_rubble', ww=0.5, trim='stone_trim', mull=2)
            flat_wall(mb, P, 0, Le, plinth + floors * fh, Hw, 'stone_rubble')
            # buttresses
            nbut = int(round(Le / 6.6))
            for k in range(1, nbut):
                s = k * Le / nbut
                if front_side and abs(s - Le / 2) < tower_w / 2 + 1:
                    continue
                c = P(s, 0, 0.3)
                mb.box((c[0], c[1], plinth + (Hw - plinth - 1.5) / 2), (0.7, 0.6, Hw - plinth - 1.5), 'stone_rubble',
                       rotz=math.atan2(t.y, t.x), mats={'top': 'stone_trim'})
            # parapet with battlements along the eaves
            nm = int(Le / 1.6)
            for k in range(nm):
                if k % 2 == 0:
                    c = P((k + 0.5) * Le / nm, Hw + 0.45, 0.0)
                    mb.box(c, (Le / nm, 0.45, 0.9), 'stone_trim', rotz=math.atan2(t.y, t.x), skip=('bottom',))
            if ivy:
                ivy_patch(iv, P, 0, Le, 0, Hw, 1.5 * ivy, i * 3)
    # --- slate roof (gable along L)
    hz = Hw + (W / 2) * pitch
    A, B, C, D = (-L / 2, -W / 2 - 0.3, Hw - 0.3 * pitch), (L / 2, -W / 2 - 0.3, Hw - 0.3 * pitch), (L / 2, W / 2 + 0.3, Hw - 0.3 * pitch), (-L / 2, W / 2 + 0.3, Hw - 0.3 * pitch)
    R1, R2 = (-L / 2, 0, hz), (L / 2, 0, hz)
    mb.face([A, B, R2, R1], 'roof_slate')
    mb.face([C, D, R1, R2], 'roof_slate')
    mb.box((0, 0, hz + 0.1), (L, 0.35, 0.3), 'metal_dark')
    # dormers on the front roof slope
    for k in range(-2, 3):
        if k == 0:
            continue
        x = k * L / 6
        zb_ = Hw + 0.8
        mb.box((x, -W / 4 + 0.4, zb_ + 1.0), (1.8, 1.6, 2.0), 'stone_rubble', mats={'front': 'glass'})
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
            window_grid(mb, P, Le, plinth, floors, fh, 4.0, 'stone_rubble', ww=0.55, trim='stone_trim', mull=2)
            flat_wall(mb, P, 0, Le, plinth + floors * fh, Hw, 'stone_rubble')
            ghz = Hw + pw / 2 * 1.1
            mb.face([P(0, Hw), P(Le, Hw), P(Le / 2, ghz)], 'stone_rubble')
            mb.quad(P(-0.2, Hw, 0.25), P(Le / 2, ghz + 0.35, 0.25), P(Le / 2, ghz + 0.35, -0.2), P(-0.2, Hw, -0.2), 'stone_trim')
            mb.quad(P(Le / 2, ghz + 0.35, 0.25), P(Le + 0.2, Hw, 0.25), P(Le + 0.2, Hw, -0.2), P(Le / 2, ghz + 0.35, -0.2), 'stone_trim')
            # sides of the projection
            for (sx, ex) in ((x0 - pw / 2, -1), (x0 + pw / 2, 1)):
                pa, pb = ((sx, -W / 2), (sx, yb)) if ex < 0 else ((sx, yb), (sx, -W / 2))
                P2, Le2, _, _ = edge_P(pa, pb)
                flat_wall(mb, P2, 0, Le2, -4, Hw, 'stone_rubble')
            mb.prism(offset_poly([(x0 - pw / 2, yb), (x0 + pw / 2, yb), (x0 + pw / 2, -W / 2), (x0 - pw / 2, -W / 2)], 0.25), -4, plinth, 'stone_granite')
            # little gable roof over the projection
            mb.face([(x0 - pw / 2 - 0.3, yb - 0.3, Hw - 0.2), (x0, yb - 0.3, ghz), (x0, -W / 4, ghz), (x0 - pw / 2 - 0.3, -W / 4, Hw - 0.2)][::-1], 'roof_slate')
            mb.face([(x0 + pw / 2 + 0.3, yb - 0.3, Hw - 0.2), (x0 + pw / 2 + 0.3, -W / 4, Hw - 0.2), (x0, -W / 4, ghz), (x0, yb - 0.3, ghz)][::-1], 'roof_slate')
            if ivy:
                ivy_patch(iv, P, 0, Le, 0, Hw, 2.2 * ivy, sgn * 7)
    # --- central tower
    tw = tower_w
    tproj = 3.0
    Ht = Hw + tower_extra
    ty0 = -W / 2 - tproj
    tower = [(-tw / 2, ty0), (tw / 2, ty0), (tw / 2, ty0 + tw), (-tw / 2, ty0 + tw)]
    mb.prism(offset_poly(tower, 0.25), -4, plinth, 'stone_granite')
    for i in range(4):
        a, bb = tower[i], tower[(i + 1) % 4]
        P, Le, t, n = edge_P(a, bb)
        if i == 0:
            # pointed-arch entrance + tall window + clock-less belfry openings
            ew = 3.2
            e0, e1 = Le / 2 - ew / 2, Le / 2 + ew / 2
            zs = plinth + 3.2
            flat_wall(mb, P, 0, e0, -0.5, Ht, 'stone_rubble')
            flat_wall(mb, P, e1, Le, -0.5, Ht, 'stone_rubble')
            arch_fill(mb, P, e0, e1, zs, zs + ew * 0.95, 1.2, 'stone_trim', 'pointed', 12)
            flat_wall(mb, P, e0, e1, zs + ew * 0.95, Ht, 'stone_rubble')
            mb.quad(P(e0, -0.5, -1.2), P(e1, -0.5, -1.2), P(e1, zs + ew * 0.9, -1.2), P(e0, zs + ew * 0.9, -1.2), 'wood_dark')
            mb.quad(P(e0, -0.5, 0), P(e0, -0.5, -1.2), P(e0, zs, -1.2), P(e0, zs, 0), 'stone_trim')
            mb.quad(P(e1, -0.5, -1.2), P(e1, -0.5, 0), P(e1, zs, 0), P(e1, zs, -1.2), 'stone_trim')
            # tall tracery window above the door
            w0, w1 = Le / 2 - 1.1, Le / 2 + 1.1
            zw0, zw1 = zs + ew + 1.0, Hw - 1.0
            mb.quad(P(w0, zw0, 0.02), P(w1, zw0, 0.02), P(w1, zw1, 0.02), P(w0, zw1, 0.02), 'glass')
            for sm in (Le / 2 - 0.37, Le / 2 + 0.37):
                mb.quad(P(sm - 0.08, zw0, 0.06), P(sm + 0.08, zw0, 0.06), P(sm + 0.08, zw1, 0.06), P(sm - 0.08, zw1, 0.06), 'stone_trim')
            arch_fill(mb, P, w0, w1, zw1, zw1 + 2.2, 0.0001, 'stone_trim', 'pointed', 8)
        else:
            flat_wall(mb, P, 0, Le, -0.5 if i != 2 else Hw, Ht, 'stone_rubble')
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
        if ivy and i != 2:
            ivy_patch(iv, P, 0, Le, 0, Hw * 0.8, 1.2 * ivy, 11 + i)
    mb.face([(p[0], p[1], Ht) for p in tower], 'roof_flat')
    # corner pinnacles
    for (px_, py_) in tower:
        mb.box((px_, py_, Ht + 0.9), (0.9, 0.9, 1.8), 'stone_trim', skip=('bottom',))
        mb.face([(px_ - .45, py_ - .45, Ht + 1.8), (px_ + .45, py_ - .45, Ht + 1.8), (px_, py_, Ht + 3.2)], 'stone_trim')
        mb.face([(px_ + .45, py_ - .45, Ht + 1.8), (px_ + .45, py_ + .45, Ht + 1.8), (px_, py_, Ht + 3.2)], 'stone_trim')
        mb.face([(px_ + .45, py_ + .45, Ht + 1.8), (px_ - .45, py_ + .45, Ht + 1.8), (px_, py_, Ht + 3.2)], 'stone_trim')
        mb.face([(px_ - .45, py_ + .45, Ht + 1.8), (px_ - .45, py_ - .45, Ht + 1.8), (px_, py_, Ht + 3.2)], 'stone_trim')
    # entrance steps
    for k in range(5):
        mb.box((0, ty0 - 0.6 - k * 0.4, 0.15 + (4 - k) * 0.25 - 1.0), (5.0 + k * 0.6, 1.2 + k * 0.8, 0.25), 'stone_granite')
    return [mb, iv]


def underwood():
    return gothic('underwood', bld(246156115), (0.27, -1.0), 3, tower_w=9.0, tower_extra=9.5, ivy=1.0)


def stimson():
    return gothic('stimson', bld(246156118), (1.0, -0.27), 2, tower_w=6.5, tower_extra=6.0, ivy=0.8, wings=False)


def appenzeller():
    return gothic('appenzeller', bld(246156116), (-1.0, 0.27), 3, tower_w=7.0, tower_extra=6.5, ivy=1.1, wings=False)


# ============================================================================= 대강당
def auditorium():
    b = bld(371403811)
    cx, cy, L, W, ang, z0 = frame_for(b, (-1.0, 0.25))
    mb = MeshBuilder('lm_auditorium')
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
    for k in range(4):
        mb.box((0, ly - 7.5 - k * 0.45, 0.5 - (k + 1) * 0.2 + 0.1), (L * 0.75, 1.2, 0.2), 'stone_granite')
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
    return [mb, mbw]


# ============================================================================= 광혜원 (traditional hanok)
def hanok():
    b = bld(429249496)
    cx, cy, L, W, ang, z0 = frame_for(b, (-1.0, 0.2))
    mb = MeshBuilder('lm_hanok')
    mb.xf = local_frame(cx, cy, ang, z0)
    L, W = 15.0, 8.4
    plat = 0.9
    mb.prism(offset_poly(rect(L + 2.4, W + 2.4), 0), -3, plat, 'stone_granite', 'stone_granite')
    for k in range(3):     # front steps
        mb.box((0, -(W + 2.4) / 2 - 0.35 - k * 0.35, plat - (k + 1) * 0.3 + 0.15), (3.0, 0.7 + k * 0.0, 0.3), 'stone_granite')
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


BUILDERS = {'library': library, 'union': union, 'centennial': centennial, 'underwood': underwood,
            'stimson': stimson, 'appenzeller': appenzeller, 'auditorium': auditorium, 'chapel': chapel,
            'engineering': engineering, 'hanok': hanok}
