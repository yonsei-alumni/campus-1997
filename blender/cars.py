"""1990s Korean cars for the 1997 campus, modelled procedurally in Blender.

Each body is *lofted*: cross-sections (rounded rectangles with tumblehome) are sampled every few centimetres along
the car and joined into one smooth quad skin, so the wheel arches, hood line, plan-view rounding and greenhouse all
come out as continuous surfaces.  Window glass, black rubber/pillars and paint are assigned per face from the
window outlines of each model.  Details: lamp clusters with chrome bezels, grille, wrap-around bumpers, rub strips,
door seams and handles, mirrors, wipers, antenna, pre-2004 Korean two-line licence plates, a simple interior seen
through tinted glass, and four separate wheels (tyre with shoulders + steel rim + hubcap) whose origins sit on the
axle so the game can spin them.

Models (car-local frame: +X forward, +Y left, +Z up, ground at z=0):
  sedan   — 3-box mid-size saloon in the manner of a 1993-97 Korean mid-size sedan
  sedan2  — a squarer, older 3-box (late-80s/early-90s look)
  hatch   — 5-door compact hatchback (the small car everyone's family had)
  taxi    — the sedan with a roof sign and yellow commercial plates
  van     — one-box passenger van
  bus     — city bus with the route sign "연세대 · 신촌"
"""
import math
from mathutils import Vector
from common import MeshBuilder


def interp(pts, x):
    """piecewise-linear interpolation over [(x, y), ...] sorted by x descending or ascending."""
    p = sorted(pts)
    if x <= p[0][0]:
        return p[0][1]
    if x >= p[-1][0]:
        return p[-1][1]
    for (x0, y0), (x1, y1) in zip(p[:-1], p[1:]):
        if x0 <= x <= x1:
            t = (x - x0) / (x1 - x0)
            t = t * t * (3 - 2 * t) * 0.5 + t * 0.5          # gentle easing between control points
            return y0 + (y1 - y0) * t
    return p[-1][1]


def smoothstep(a, b, x):
    t = max(0.0, min(1.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)


def section(half_w, zb, zt, rb, rt, tumble=0.0, crown=0.0, n_arc=4, n_top=6):
    """Closed cross-section (y, z) around the car axis, counter-clockwise seen from +X."""
    h = max(0.004, zt - zb)
    rb = min(rb, h * 0.35, half_w * 0.4)
    rt = min(rt, h * 0.45, half_w * 0.4)
    wt = half_w - tumble
    right = []                                    # y >= 0 half from bottom centre to top centre
    right.append((0.0, zb))
    for i in range(n_arc + 1):                    # bottom corner
        a = -math.pi / 2 + (math.pi / 2) * i / n_arc
        right.append((half_w - rb + rb * math.cos(a), zb + rb + rb * math.sin(a)))
    for i in range(n_arc + 1):                    # top corner
        a = (math.pi / 2) * i / n_arc
        right.append((wt - rt + rt * math.cos(a), zt - rt + rt * math.sin(a)))
    for i in range(1, n_top + 1):                 # roof / hood crown
        y = (wt - rt) * (1 - i / n_top)
        right.append((y, zt + crown * (1 - (y / max(1e-3, wt)) ** 2)))
    left = [(-y, z) for (y, z) in reversed(right[1:-1])]
    return right + left


def loft(mb, xs, sec_fn, mat_fn, tag, cap_front=True, cap_back=True, cap_mat=None):
    secs = [[Vector((x, y, z)) for (y, z) in sec_fn(x)] for x in xs]
    n = len(secs[0])
    for i in range(len(xs) - 1):
        A, B = secs[i], secs[i + 1]
        axis = Vector((0, 0, (min(p.z for p in A) + max(p.z for p in A)) / 2))
        for k in range(n):
            k2 = (k + 1) % n
            q = [A[k], A[k2], B[k2], B[k]]
            c = sum(q, Vector()) / 4
            nrm = (q[1] - q[0]).cross(q[3] - q[0])
            if nrm.length < 1e-10:
                nrm = (q[2] - q[1]).cross(q[3] - q[1])
            if nrm.length < 1e-10:
                continue
            nrm.normalize()
            out = Vector((0, c.y, c.z - axis.z))
            if nrm.dot(out) < 0:
                q = q[::-1]
                nrm = -nrm
            mb.face([tuple(v) for v in q], mat_fn(c, nrm), smooth=tag)
    for S, sgn, do in ((secs[0], -1, cap_back), (secs[-1], 1, cap_front)):
        if not do:
            continue
        cen = sum(S, Vector()) / len(S)
        for k in range(n):
            tri = [cen, S[k], S[(k + 1) % n]]
            nrm = (tri[1] - tri[0]).cross(tri[2] - tri[0])
            if nrm.x * sgn < 0:
                tri = tri[::-1]
            mb.face([tuple(v) for v in tri], cap_mat or mat_fn(cen, Vector((sgn, 0, 0))), smooth=tag + 'cap')


def stations(x0, x1, step, extra=()):
    xs = set()
    x = x0
    while x < x1:
        xs.add(round(x, 4))
        x += step
    xs.add(round(x1, 4))
    for e in extra:
        if x0 < e < x1:
            xs.add(round(e, 4))
    return sorted(xs)


# ----------------------------------------------------------------------------- specs
SPECS = {
    'sedan': dict(
        L=4.70, W=1.75, axles=(1.38, -1.32), tyre=0.305, arch=0.375, sill=0.21, bumper_z=(0.27, 0.47),
        top=[(-2.35, 0.79), (-2.22, 0.87), (-1.45, 0.86), (0.86, 0.835), (1.60, 0.78), (2.24, 0.72), (2.35, 0.63)],
        roof=[(-1.50, 0.86), (-1.24, 1.13), (-0.95, 1.385), (-0.25, 1.41), (0.12, 1.385), (0.55, 1.12), (0.90, 0.84)],
        gh=(-1.50, 0.90), roof_w=0.64, belt_w=0.83,
        windshield=(0.16, 0.86), rear_window=(-1.46, -0.98), side=(-1.12, 0.74), pillars=[(-0.21, -0.11)],
        doors=[0.80, -0.16, -1.16], lamp_h=(0.56, 0.70), tail_h=(0.64, 0.79), grille_w=0.42, plate_rear_z=0.66),
    'sedan2': dict(
        L=4.55, W=1.71, axles=(1.33, -1.30), tyre=0.295, arch=0.365, sill=0.22, bumper_z=(0.26, 0.46),
        top=[(-2.275, 0.80), (-2.20, 0.89), (-1.40, 0.88), (0.80, 0.86), (1.55, 0.82), (2.22, 0.78), (2.275, 0.66)],
        roof=[(-1.42, 0.88), (-1.22, 1.20), (-1.02, 1.395), (-0.20, 1.40), (0.18, 1.39), (0.50, 1.18), (0.82, 0.86)],
        gh=(-1.42, 0.82), roof_w=0.66, belt_w=0.81,
        windshield=(0.22, 0.80), rear_window=(-1.38, -1.05), side=(-1.06, 0.68), pillars=[(-0.18, -0.08)],
        doors=[0.74, -0.13, -1.10], lamp_h=(0.58, 0.74), tail_h=(0.66, 0.80), grille_w=0.50, plate_rear_z=0.67),
    'hatch': dict(
        L=3.60, W=1.60, axles=(1.12, -1.17), tyre=0.28, arch=0.345, sill=0.21, bumper_z=(0.26, 0.45),
        top=[(-1.80, 0.80), (-1.72, 0.86), (0.62, 0.815), (1.20, 0.76), (1.72, 0.70), (1.80, 0.60)],
        roof=[(-1.77, 0.86), (-1.70, 1.20), (-1.55, 1.37), (-0.30, 1.40), (0.05, 1.37), (0.36, 1.10), (0.64, 0.815)],
        gh=(-1.77, 0.64), roof_w=0.60, belt_w=0.76,
        windshield=(0.06, 0.62), rear_window=(-1.76, -1.54), side=(-1.52, 0.50), pillars=[(-0.40, -0.31)],
        doors=[0.56, -0.36, -1.20], lamp_h=(0.55, 0.68), tail_h=(0.62, 0.84), grille_w=0.30, plate_rear_z=0.60, hatch=True),
    'van': dict(
        L=4.60, W=1.69, axles=(1.32, -1.28), tyre=0.30, arch=0.375, sill=0.24, bumper_z=(0.28, 0.50),
        top=[(-2.30, 0.92), (-2.25, 0.98), (1.60, 0.96), (1.98, 0.92), (2.25, 0.82), (2.30, 0.70)],
        roof=[(-2.29, 0.98), (-2.27, 1.70), (-2.20, 1.93), (0.70, 1.96), (1.05, 1.88), (1.40, 1.40), (1.62, 0.96)],
        gh=(-2.29, 1.62), roof_w=0.70, belt_w=0.82,
        windshield=(1.04, 1.60), rear_window=(-2.40, -2.20), side=(-2.05, 1.26), pillars=[(0.54, 0.64), (-0.74, -0.64)],
        doors=[1.20, 0.58, -0.60], lamp_h=(0.60, 0.76), tail_h=(0.62, 1.10), grille_w=0.40, plate_rear_z=0.72, van=True),
}
SPECS['taxi'] = dict(SPECS['sedan'], taxi=True)


def build_car(kind):
    sp = SPECS[kind]
    L, W = sp['L'], sp['W']
    hw = W / 2
    fa, ra = sp['axles']
    r_arch, tyre = sp['arch'], sp['tyre']
    cy_arch = tyre + 0.01
    mb = MeshBuilder('car_' + kind)

    def z_bot(x):
        z = sp['sill']
        z += (sp['bumper_z'][0] - sp['sill'] + 0.02) * smoothstep(L / 2 - 0.45, L / 2 - 0.15, abs(x))
        for ax in (fa, ra):
            d = abs(x - ax)
            if d < r_arch:
                z = max(z, cy_arch + math.sqrt(r_arch * r_arch - d * d) * 0.98)
        return z

    def z_top(x):
        return interp(sp['top'], x)

    def half_w(x):
        return hw - 0.11 * smoothstep(L / 2 - 0.40, L / 2, abs(x)) ** 1.6

    # ---------------- lower body
    xs = stations(-L / 2, L / 2, 0.04, extra=[fa - r_arch, fa + r_arch, ra - r_arch, ra + r_arch])

    def body_sec(x):
        return section(half_w(x), z_bot(x), z_top(x), 0.07, 0.06, tumble=0.02, crown=0.012)

    def body_mat(c, n):
        return 'car_paint'
    loft(mb, xs, body_sec, body_mat, 'body')

    # ---------------- greenhouse
    x0, x1 = sp['gh']
    xs2 = stations(x0, x1, 0.035)
    belt = lambda x: z_top(x) - 0.02

    def zr(x):
        return interp(sp['roof'], x)

    def gh_sec(x):
        zb, zt = belt(x), max(belt(x) + 0.003, zr(x))
        wb = min(sp['belt_w'], half_w(x) - 0.02)
        h = zt - zb
        wr = sp['roof_w'] + (wb - sp['roof_w']) * max(0.0, 1 - h / 0.12) if h < 0.12 else sp['roof_w']
        return section(wb, zb, zt, 0.01, 0.07, tumble=wb - wr, crown=0.015)

    ws, rw, sd = sp['windshield'], sp['rear_window'], sp['side']

    def window_kind(c, n, m):
        """'glass' if the face centre lies inside a window shrunk by margin m."""
        x, y, z = c.x, abs(c.y), c.z
        if abs(n.y) > 0.55:
            if not (belt(x) + 0.05 + m < z < zr(x) - 0.06 - m):
                return False
            if not (sd[0] + m < x < sd[1] - m):
                return False
            return not any(a - m < x < b + m for a, b in sp['pillars'])
        if abs(n.x) > 0.6 and sp.get('van') and x < 0:            # van rear door glass on the vertical back
            return 1.12 + m < z < 1.78 - m and y < sp['roof_w'] - 0.10 - m
        lim = sp['roof_w'] - 0.08 - m
        if ws[0] + m < x < ws[1] - m * 0.5 and y < lim * (0.92 + 0.08 * (x - ws[0]) / (ws[1] - ws[0])):
            return True
        if rw[0] + m * 0.5 < x < rw[1] - m and y < lim:
            return True
        return False

    def gh_mat(c, n):
        if window_kind(c, n, 0.0):
            return 'glass_car'
        if window_kind(c, n, -0.035):
            return 'trim_black'
        return 'car_paint'
    loft(mb, xs2, gh_sec, gh_mat, 'gh', cap_front=False, cap_back=False)

    # ---------------- wheel-well liners (hide the lofted arch tunnel) + underbody
    for ax in (fa, ra):
        mb.box((ax, 0, 0.42), (r_arch * 2 + 0.02, W - 0.36, 0.56), 'rubber', skip=('bottom',))
        for s in (-1, 1):                       # well walls
            mb.box((ax, s * (hw - 0.17), cy_arch + 0.1), (r_arch * 2, 0.02, r_arch * 1.2), 'rubber')
    mb.box((0, 0, sp['sill'] + 0.02), (L - 0.5, W - 0.2, 0.06), 'rubber', skip=('top',))

    # ---------------- fascia: grille, lamps, bumpers, plates
    xf = L / 2
    lz0, lz1 = sp['lamp_h']
    gw = sp['grille_w']
    # grille with chrome slats and an oval badge
    mb.box((xf - 0.035, 0, (lz0 + lz1) / 2), (0.05, gw * 2, lz1 - lz0 - 0.02), 'trim_black')
    for k in range(3):
        z = lz0 + 0.025 + k * (lz1 - lz0 - 0.05) / 2
        mb.box((xf - 0.006, 0, z), (0.012, gw * 2 - 0.04, 0.012), 'chrome')
    mb.box((xf, 0, (lz0 + lz1) / 2), (0.01, 0.10, 0.05), 'chrome')
    for s in (-1, 1):
        yc = s * (gw + 0.20)
        mb.box((xf - 0.03, yc, (lz0 + lz1) / 2), (0.06, 0.36, lz1 - lz0), 'chrome')                     # bezel
        mb.face([(xf + 0.001, yc - s * 0.17, lz0 + 0.012), (xf + 0.001, yc + s * 0.17, lz0 + 0.012),
                 (xf + 0.001, yc + s * 0.17, lz1 - 0.012), (xf + 0.001, yc - s * 0.17, lz1 - 0.012)][::(1 if s > 0 else -1)], 'light_white')
        ya = s * (half_w(xf - 0.05) - 0.06)                                                              # corner indicator
        mb.box((xf - 0.07, ya, (lz0 + lz1) / 2), (0.10, 0.07, lz1 - lz0 - 0.03), 'light_amber')
    # wrap-around bumpers
    bz0, bz1 = sp['bumper_z']
    for sx in (1, -1):
        xb = sx * (L / 2 + 0.03)
        mb.box((xb, 0, (bz0 + bz1) / 2), (0.14, W - 0.10, bz1 - bz0), 'plastic_grey')
        mb.box((xb + sx * 0.071, 0, bz1 - 0.05), (0.012, W - 0.16, 0.04), 'trim_black')
        for s in (-1, 1):
            mb.box((sx * (L / 2 - 0.16), s * (hw - 0.02), (bz0 + bz1) / 2), (0.36, 0.08, bz1 - bz0), 'plastic_grey')
    # tail lamps
    tz0, tz1 = sp['tail_h']
    xr = -L / 2
    for s in (-1, 1):
        y0, y1 = s * 0.30, s * (half_w(xr + 0.05) - 0.04)
        mb.box((xr + 0.02, (y0 + y1) / 2, (tz0 + tz1) / 2), (0.05, abs(y1 - y0), tz1 - tz0), 'light_red')
        mb.box((xr + 0.005, y1 - s * 0.10, (tz0 + tz1) / 2), (0.02, 0.14, tz1 - tz0 - 0.02), 'light_amber')
        mb.box((xr + 0.004, (y0 + y1) / 2 + s * 0.02, tz0 + 0.03), (0.02, 0.10, 0.04), 'lens_clear')
    if not sp.get('hatch') and not sp.get('van'):
        mb.box((xr + 0.01, 0, (tz0 + tz1) / 2), (0.03, 0.60, tz1 - tz0 - 0.02), 'trim_black')          # trunk garnish
    # plates (UV into the 2x2 plate atlas: 0/1 green private, 2 yellow commercial, 3 taxi roof sign)
    cell = 2 if sp.get('taxi') else (0 if kind in ('sedan', 'van') else 1)
    u0, v0 = (cell % 2) * 0.5, 0.5 if cell < 2 else 0.0          # Blender UVs (v up); the glTF export flips them
    pw, ph = 0.335, 0.165
    for sx, zc in ((1, (bz0 + bz1) / 2), (-1, sp['plate_rear_z'] if not sp.get('hatch') else 0.58)):
        x = sx * (L / 2 + (0.105 if sx > 0 else 0.03))
        q = [(x, -pw / 2 * sx, zc - ph / 2), (x, pw / 2 * sx, zc - ph / 2), (x, pw / 2 * sx, zc + ph / 2), (x, -pw / 2 * sx, zc + ph / 2)]
        mb.face(q, 'plate', uvs=[(u0, v0), (u0 + 0.5, v0), (u0 + 0.5, v0 + 0.5), (u0, v0 + 0.5)])

    # ---------------- sides: rub strips, door seams, handles, mirrors
    for s in (-1, 1):
        xa, xb = ra + r_arch + 0.05, fa - r_arch - 0.05
        ys = s * (hw - 0.005)
        mb.box(((xa + xb) / 2, ys, 0.47), (xb - xa, 0.03, 0.05), 'trim_black')
        for dx in sp['doors']:
            yv = s * (half_w(dx) + 0.002)
            q = [(dx - 0.005, yv, sp['sill'] + 0.06), (dx + 0.005, yv, sp['sill'] + 0.06), (dx + 0.005, yv, belt(dx)), (dx - 0.005, yv, belt(dx))]
            mb.face(q if s > 0 else q[::-1], 'trim_black')
        for dx in sp['doors'][:-1]:
            hx = dx - 0.22
            mb.box((hx, s * (half_w(hx) + 0.008), belt(hx) - 0.10), (0.14, 0.02, 0.03), 'chrome')
        mx = sd[1] - 0.02
        my = s * (half_w(mx) + 0.09)
        mb.box((mx, my, belt(mx) + 0.10), (0.07, 0.15, 0.10), 'car_paint')
        mb.box((mx - 0.036, my, belt(mx) + 0.10), (0.005, 0.13, 0.085), 'chrome')
        mb.box((mx + 0.02, s * (half_w(mx) + 0.02), belt(mx) + 0.05), (0.04, 0.05, 0.04), 'trim_black')
    # wipers & antenna
    for s in (-0.3, 0.35):
        x = ws[1] - 0.04
        mb.box((x - 0.05, s, belt(x) + 0.03), (0.04, 0.48, 0.012), 'trim_black')
    ax_ = sd[1] + 0.25
    mb.cylinder((ax_, -hw + 0.12), 0.004, z_top(ax_), z_top(ax_) + 0.75, 'metal_dark', seg=4, cap_top=True, smooth=False)

    # ---------------- interior seen through the glass
    zf = sp['sill'] + 0.12
    ws0 = ws[0] if not sp.get('van') else 1.0
    mb.box((ws0 - 0.05, 0, belt(ws0) - 0.10), (0.35, W - 0.30, 0.18), 'car_interior')        # dashboard
    bp = sp['pillars'][0][0] if not sp.get('van') else sp['pillars'][1][0]
    rows = [bp + 0.30, bp - 0.72] + ([bp - 1.55] if sp.get('van') else [])
    for i, rx in enumerate(rows):
        for s in ((-1, 1) if i == 0 else (0,)):
            yy = s * 0.36
            wseat = 0.48 if i == 0 else W - 0.42
            mb.box((rx, yy, zf + 0.22), (0.48, wseat, 0.14), 'car_interior')
            mb.box((rx - 0.24, yy, zf + 0.52), (0.12, wseat, 0.46), 'car_interior')
    # steering wheel (left-hand drive, driver on +Y)
    swx, swy, swz = ws0 - 0.38, 0.36, belt(ws0) + 0.02
    for k in range(10):
        a0, a1 = 2 * math.pi * k / 10, 2 * math.pi * (k + 1) / 10
        p0 = (swx + 0.05 * math.sin(a0), swy + 0.18 * math.cos(a0), swz + 0.18 * math.sin(a0))
        p1 = (swx + 0.05 * math.sin(a1), swy + 0.18 * math.cos(a1), swz + 0.18 * math.sin(a1))
        mb.box(tuple((Vector(p0) + Vector(p1)) / 2), ((Vector(p1) - Vector(p0)).length + 0.01, 0.03, 0.03), 'trim_black')

    # ---------------- taxi roof sign
    if sp.get('taxi'):
        zr0 = zr(-0.4) + 0.01
        mb.box((-0.40, 0, zr0 + 0.10), (0.26, 0.56, 0.20), 'light_amber', mats={'top': 'trim_black'})
        for s in (-1, 1):
            q = [(-0.53, s * 0.2805, zr0 + 0.02), (-0.27, s * 0.2805, zr0 + 0.02), (-0.27, s * 0.2805, zr0 + 0.18), (-0.53, s * 0.2805, zr0 + 0.18)]
            uv = [(1.0, 0.0), (0.5, 0.0), (0.5, 0.5), (1.0, 0.5)] if s > 0 else [(0.5, 0.5), (1.0, 0.5), (1.0, 0.0), (0.5, 0.0)]
            mb.face(q if s > 0 else q[::-1], 'plate', uvs=uv)

    wheels = [make_wheel(f'wheel_{n}', (x, s * (hw - 0.12), tyre), tyre, 0.19, s) for n, x, s in
              (('FL', fa, 1), ('FR', fa, -1), ('RL', ra, 1), ('RR', ra, -1))]
    return mb, wheels


def make_wheel(name, c, r, w, side):
    """Tyre with rounded shoulders, pressed-steel rim and a chrome hubcap. Built around the origin; the caller
    places the object at c (the axle), so the game can spin it about its local Y (glTF -Z) axis."""
    mb = MeshBuilder(name)
    seg = 22
    # lathe profile (radius, y) from inner edge, around the tyre, to the outer face
    hw = w / 2
    prof = [(r * 0.66, -hw * 0.95), (r * 0.80, -hw), (r * 0.93, -hw * 0.98), (r * 0.985, -hw * 0.8), (r, -hw * 0.45),
            (r, hw * 0.45), (r * 0.985, hw * 0.8), (r * 0.93, hw * 0.98), (r * 0.80, hw), (r * 0.66, hw * 0.95)]
    mats = ['rubber'] * (len(prof) - 1)

    def ring(rad, y, a):
        return (rad * math.cos(a), y, rad * math.sin(a))
    for k in range(seg):
        a0, a1 = 2 * math.pi * k / seg, 2 * math.pi * (k + 1) / seg
        for i in range(len(prof) - 1):
            (r0, y0), (r1, y1) = prof[i], prof[i + 1]
            q = [ring(r0, y0, a0), ring(r1, y1, a0), ring(r1, y1, a1), ring(r0, y0, a1)]
            mb.face(q, mats[i], smooth='tyre')
    # rim + hubcap on the outer face (side = +1: outer face at +Y)
    yo = side * hw * 0.92
    rim = [(r * 0.66, yo), (r * 0.60, yo - side * 0.02), (r * 0.40, yo - side * 0.03), (r * 0.36, yo + side * 0.005), (r * 0.30, yo + side * 0.012), (0.0, yo + side * 0.02)]
    rmats = ['metal', 'metal', 'chrome', 'chrome', 'chrome']
    for k in range(seg):
        a0, a1 = 2 * math.pi * k / seg, 2 * math.pi * (k + 1) / seg
        for i in range(len(rim) - 1):
            (r0, y0), (r1, y1) = rim[i], rim[i + 1]
            q = [ring(r0, y0, a0), ring(r1, y1, a0), ring(r1, y1, a1), ring(r0, y0, a1)]
            if side < 0:
                q = q[::-1]
            mb.face(q, rmats[i], smooth='rim%d' % i)
    # hubcap ventilation slots
    for k in range(8):
        a = 2 * math.pi * k / 8
        p = Vector(ring(r * 0.48, yo - side * 0.026, a))
        t = Vector((-math.sin(a), 0, math.cos(a)))
        u = Vector((math.cos(a), 0, math.sin(a)))
        q = [p - t * 0.03 - u * 0.012, p + t * 0.03 - u * 0.012, p + t * 0.03 + u * 0.012, p - t * 0.03 + u * 0.012]
        q = [tuple(v + Vector((0, side * 0.002, 0))) for v in q]
        mb.face(q if side > 0 else q[::-1], 'trim_black')
    # inner face disc (dark)
    yi = -side * hw * 0.92
    pts = [ring(r * 0.66, yi, 2 * math.pi * k / seg) for k in range(seg)]
    mb.face(pts if side < 0 else pts[::-1], 'trim_black')
    mb.wheel_pos = c
    return mb


# ----------------------------------------------------------------------------- city bus
def build_bus():
    L, W, H = 10.9, 2.49, 3.05
    hw = W / 2
    fa, ra = 3.45, -2.05
    tyre, r_arch = 0.50, 0.60
    mb = MeshBuilder('car_bus')

    def z_bot(x):
        z = 0.34
        for ax in (fa, ra):
            d = abs(x - ax)
            if d < r_arch:
                z = max(z, tyre + 0.02 + math.sqrt(r_arch * r_arch - d * d) * 0.98)
        return z

    def z_top(x):
        return H - 0.10 * smoothstep(L / 2 - 0.5, L / 2, abs(x))

    def half_w(x):
        return hw - 0.06 * smoothstep(L / 2 - 0.3, L / 2, abs(x))

    def sec(x):
        return section(half_w(x), z_bot(x), z_top(x), 0.10, 0.22, tumble=0.03, crown=0.05, n_top=8)

    pillars = [x for x in [-4.7 + i * 1.32 for i in range(8)]]
    doors = [(3.95, 4.95), (-0.25, 0.95)]

    def mat(c, n):
        x, z = c.x, c.z
        if n.x > 0.6:                            # front: windscreen + destination sign
            if 1.05 < z < 2.55 and abs(c.y) < hw - 0.10:
                return 'glass_bus'
            if z < 0.95:
                return 'bus_blue'
            return 'bus_white'
        if n.x < -0.6:
            if 1.55 < z < 2.55 and abs(c.y) < hw - 0.18:
                return 'glass_bus'
            return 'bus_blue' if z < 1.0 else 'bus_white'
        if abs(n.y) > 0.55:
            door = next(((a, b) for a, b in doors if a < x < b), None) if n.y < 0 else None
            if door and 0.45 < z < 2.60:
                a, b = door
                if min(x - a, b - x) < 0.07 or abs(x - (a + b) / 2) < 0.03 or z < 0.52 or z > 2.53:
                    return 'trim_black'
                return 'glass_bus'
            if 1.48 < z < 2.58 and -5.15 < x < 5.05:
                if any(abs(x - p) < 0.07 for p in pillars):
                    return 'trim_black'
                return 'glass_bus'
            if 1.40 < z < 1.48 or 2.58 < z < 2.62:
                return 'trim_black'
            if 1.22 < z < 1.32:
                return 'bus_red'
            return 'bus_blue' if z < 1.20 else 'bus_white'
        return 'bus_white'
    loft(mb, stations(-L / 2, L / 2, 0.06, extra=[fa - r_arch, fa + r_arch, ra - r_arch, ra + r_arch] + pillars), sec, mat, 'bus')
    for ax in (fa, ra):
        mb.box((ax, 0, 0.75), (r_arch * 2, W - 0.5, 0.9), 'rubber', skip=('bottom',))
    mb.box((0, 0, 0.36), (L - 1.0, W - 0.2, 0.06), 'rubber', skip=('top',))
    xf = L / 2
    for s in (-1, 1):
        mb.box((xf - 0.01, s * 0.95, 0.62), (0.04, 0.30, 0.14), 'light_white')
        mb.box((xf - 0.01, s * 0.75, 0.62), (0.04, 0.08, 0.14), 'light_amber')
        mb.box((-xf + 0.01, s * 1.0, 0.75), (0.04, 0.16, 0.40), 'light_red')
        mb.box((xf + 0.25, s * (hw + 0.10), 2.15), (0.06, 0.06, 0.30), 'trim_black')            # mirror arm
        mb.box((xf + 0.25, s * (hw + 0.15), 1.95), (0.04, 0.16, 0.32), 'trim_black')
    mb.box((xf + 0.04, 0, 0.42), (0.12, W - 0.1, 0.22), 'plastic_grey')
    mb.box((-xf - 0.04, 0, 0.42), (0.12, W - 0.1, 0.22), 'plastic_grey')
    for sx, zc in ((1, 0.70), (-1, 0.70)):
        x = sx * (L / 2 + 0.03)
        q = [(x, -0.17 * sx, zc - 0.08), (x, 0.17 * sx, zc - 0.08), (x, 0.17 * sx, zc + 0.08), (x, -0.17 * sx, zc + 0.08)]
        mb.face(q, 'plate', uvs=[(0.0, 0.0), (0.5, 0.0), (0.5, 0.5), (0.0, 0.5)])
    # front: windscreen, destination sign, lower panel; back: rear window (the loft caps are flat panels)
    xq = L / 2 + 0.004
    def panel(x, y0, y1, z0, z1, m, uv=None):
        sgn = 1 if x > 0 else -1
        q = [(x, -y1 * sgn, z0), (x, y1 * sgn, z0), (x, y1 * sgn, z1), (x, -y1 * sgn, z1)] if y0 is None else None
        mb.face(q, m, uvs=uv)
    wy = hw - 0.16
    panel(xq, None, wy, 1.05, 2.55, 'glass_bus')
    panel(xq + 0.002, None, wy + 0.04, 0.98, 1.05, 'trim_black')
    panel(xq + 0.002, None, wy - 0.10, 2.62, 2.92, 'bus_sign', uv=[(0, 0), (1, 0), (1, 1), (0, 1)])
    panel(xq, None, hw - 0.08, 0.36, 0.95, 'bus_blue')
    panel(-xq, None, hw - 0.22, 1.55, 2.55, 'glass_bus')
    panel(-xq, None, hw - 0.08, 0.36, 1.00, 'bus_blue')
    # seats in rows (through the glass)
    for i in range(8):
        x = -4.4 + i * 1.15
        for s in (-1, 1):
            mb.box((x, s * 0.65, 1.0), (0.45, 0.85, 0.12), 'car_interior')
            mb.box((x - 0.2, s * 0.65, 1.35), (0.10, 0.85, 0.6), 'car_interior')
    wheels = [make_wheel(f'wheel_{n}', (x, s * (hw - 0.22), tyre), tyre, 0.30, s) for n, x, s in
              (('FL', fa, 1), ('FR', fa, -1), ('RL', ra, 1), ('RR', ra, -1))]
    return mb, wheels
