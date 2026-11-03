"""The cars on Seoul streets in 1997, modelled procedurally in Blender.

Each body is *lofted*: cross-sections (rounded rectangles with tumblehome) are sampled every few centimetres along
the car and joined into one smooth quad skin, so the wheel arches, hood line, plan-view rounding and greenhouse all
come out as continuous surfaces.  Window glass, black rubber/pillars and paint are assigned per face from the
window outlines of each model.  Bumpers are lofted too, so they wrap round the corners; lamps are strips laid on
the body surface, so flush wrap-around lamps follow the plan-view rounding.  Details: grilles of the period,
rub strips, door seams and handles, mirrors, wipers, antenna, pre-2004 Korean two-line licence plates, a simple
interior seen through tinted glass, and four separate wheels (tyre with shoulders + full wheel cover or steel rim)
whose origins sit on the axle so the game can spin them.

Models (car-local frame: +X forward, +Y left, +Z up, ground at z=0), each in the manner of (not a copy of) a car
that filled 1997 Seoul:
  sedan   — rounded mid-size saloon of 1993-97 (쏘나타Ⅱ type): body-coloured wrap-around bumpers with a rub band,
            slim flush headlamps wrapping into amber corners, a low narrow grille, a full-width tail-lamp band
  sedan2  — square older mid-size saloon (프린스 type): upright chrome grille with vertical bars between
            rectangular lamps, chrome window surrounds and bumper strips, grey bumpers
  hatch   — boxy 5-door compact (프라이드 type): near-vertical tailgate, black bumpers, steel wheels
  tico    — the tiny 800 cc car (티코 type): short round nose, tall glasshouse, 12-inch wheels
  taxi    — the sedan with a roof sign "개인" and yellow commercial plates
  van     — one-box passenger van (그레이스 type)
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


def sec_radii(half_w, zb, zt, rb, rt):
    h = max(0.004, zt - zb)
    return min(rb, h * 0.35, half_w * 0.4), min(rt, h * 0.45, half_w * 0.4)


def section(half_w, zb, zt, rb, rt, tumble=0.0, crown=0.0, n_arc=4, n_top=6, zsplits=()):
    """Closed cross-section (y, z) around the car axis, counter-clockwise seen from +X.
    zsplits: extra points on the flank (so a rub band can get its own faces)."""
    rb, rt = sec_radii(half_w, zb, zt, rb, rt)
    wt = half_w - tumble
    right = []                                    # y >= 0 half from bottom centre to top centre
    right.append((0.0, zb))
    for i in range(n_arc + 1):                    # bottom corner
        a = -math.pi / 2 + (math.pi / 2) * i / n_arc
        right.append((half_w - rb + rb * math.cos(a), zb + rb + rb * math.sin(a)))
    z0, z1 = zb + rb, zt - rt
    for z in sorted(zsplits):                     # flank, from the bottom corner up to the top corner (clamped,
        z = min(max(z, z0 + 0.002), z1 - 0.002)   # so every section of a loft has the same point count)
        right.append((half_w + (wt - half_w) * (z - z0) / max(1e-4, z1 - z0), z))
    for i in range(n_arc + 1):                    # top corner
        a = (math.pi / 2) * i / n_arc
        right.append((wt - rt + rt * math.cos(a), zt - rt + rt * math.sin(a)))
    for i in range(1, n_top + 1):                 # roof / hood crown
        y = (wt - rt) * (1 - i / n_top)
        right.append((y, zt + crown * (1 - (y / max(1e-3, wt)) ** 2)))
    left = [(-y, z) for (y, z) in reversed(right[1:-1])]
    return right + left


def section_y(half_w, zb, zt, rb, rt, tumble, z):
    """half-width of section() at height z (ignoring the crown); -1 outside the section."""
    if z <= zb or z >= zt:
        return -1.0
    rb, rt = sec_radii(half_w, zb, zt, rb, rt)
    wt = half_w - tumble
    if z < zb + rb:
        return half_w - rb + math.sqrt(max(0.0, rb * rb - (zb + rb - z) ** 2))
    if z > zt - rt:
        return wt - rt + math.sqrt(max(0.0, rt * rt - (z - zt + rt) ** 2))
    return half_w + (wt - half_w) * (z - zb - rb) / max(1e-4, zt - rt - zb - rb)


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
# style keys: bumper 'body' | 'grey' | 'black'; lamps 'flush' | 'box'; grille 'slot' | 'chrome' | 'slit';
# tail 'band' | 'blocks' | 'vertical'; trim (window surrounds, rub strips, handles) 'black' | 'chrome';
# wheel 'cover' | 'steel'; plan = (inset, length) of the plan-view corner rounding; body_r = flank corner radii
SPECS = {
    'sedan': dict(
        L=4.70, W=1.75, axles=(1.36, -1.34), tyre=0.305, arch=0.375, sill=0.22, bumper_z=(0.25, 0.50),
        top=[(-2.35, 0.78), (-2.26, 0.875), (-1.50, 0.885), (0.92, 0.845), (1.60, 0.795), (2.20, 0.72), (2.35, 0.665)],
        roof=[(-1.56, 0.885), (-1.22, 1.17), (-0.88, 1.385), (-0.20, 1.41), (0.18, 1.385), (0.62, 1.10), (1.00, 0.845)],
        gh=(-1.56, 1.00), roof_w=0.63, belt_w=0.83, gh_rt=0.10,
        windshield=(0.20, 0.97), rear_window=(-1.52, -0.94), side=(-1.16, 0.82), pillars=[(-0.20, -0.10)],
        doors=[0.88, -0.15, -1.18], lamp_h=(0.535, 0.625), tail_h=(0.60, 0.73), grille_w=0.25, plate_rear_z=0.625,
        plan=(0.13, 0.48), body_r=(0.08, 0.10), bumper='body', lamps='flush', grille='slot', tail='band',
        trim='black', wheel='cover', rub_z=0.42, mirror='car_paint'),
    'sedan2': dict(
        L=4.62, W=1.72, axles=(1.33, -1.30), tyre=0.295, arch=0.365, sill=0.22, bumper_z=(0.26, 0.47),
        top=[(-2.31, 0.84), (-2.24, 0.90), (-1.40, 0.895), (0.80, 0.865), (1.55, 0.835), (2.22, 0.80), (2.31, 0.745)],
        roof=[(-1.42, 0.895), (-1.22, 1.20), (-1.02, 1.395), (-0.20, 1.40), (0.18, 1.39), (0.50, 1.18), (0.82, 0.865)],
        gh=(-1.42, 0.82), roof_w=0.66, belt_w=0.81, gh_rt=0.05,
        windshield=(0.22, 0.80), rear_window=(-1.38, -1.05), side=(-1.06, 0.68), pillars=[(-0.18, -0.08)],
        doors=[0.74, -0.13, -1.10], lamp_h=(0.575, 0.695), tail_h=(0.64, 0.79), grille_w=0.30, plate_rear_z=0.64,
        plan=(0.07, 0.28), body_r=(0.06, 0.045), bumper='grey', lamps='box', grille='chrome', tail='blocks',
        trim='chrome', wheel='cover', rub_z=0.40, mirror='trim_black'),
    'hatch': dict(
        L=3.56, W=1.60, axles=(1.10, -1.20), tyre=0.275, arch=0.34, sill=0.21, bumper_z=(0.24, 0.44),
        top=[(-1.78, 0.82), (-1.73, 0.875), (0.60, 0.835), (1.20, 0.785), (1.70, 0.735), (1.78, 0.68)],
        roof=[(-1.76, 0.875), (-1.745, 1.22), (-1.68, 1.42), (-0.30, 1.45), (0.05, 1.43), (0.36, 1.12), (0.62, 0.835)],
        gh=(-1.76, 0.64), roof_w=0.62, belt_w=0.77, gh_rt=0.05, rw_z0=0.98,
        windshield=(0.08, 0.62), rear_window=(-1.77, -1.62), side=(-1.54, 0.50), pillars=[(-0.40, -0.31)],
        doors=[0.56, -0.36, -1.22], lamp_h=(0.52, 0.635), tail_h=(0.53, 0.84), grille_w=0.24, plate_rear_z=0.58,
        plan=(0.07, 0.26), body_r=(0.06, 0.05), bumper='black', lamps='box', grille='slit', tail='vertical',
        trim='black', wheel='steel', rub_z=0.40, mirror='trim_black', hatch=True),
    'tico': dict(
        L=3.34, W=1.40, axles=(1.02, -1.315), tyre=0.255, arch=0.315, sill=0.20, bumper_z=(0.22, 0.425),
        top=[(-1.67, 0.80), (-1.625, 0.86), (0.52, 0.825), (1.00, 0.79), (1.55, 0.705), (1.67, 0.645)],
        roof=[(-1.65, 0.86), (-1.635, 1.20), (-1.57, 1.375), (-0.35, 1.40), (0.00, 1.375), (0.30, 1.10), (0.56, 0.825)],
        gh=(-1.65, 0.58), roof_w=0.54, belt_w=0.665, gh_rt=0.10, rw_z0=0.97,
        windshield=(0.04, 0.56), rear_window=(-1.66, -1.52), side=(-1.47, 0.47), pillars=[(-0.45, -0.37)],
        doors=[0.52, -0.41, -1.16], lamp_h=(0.49, 0.585), tail_h=(0.52, 0.80), grille_w=0.17, plate_rear_z=0.56,
        plan=(0.14, 0.46), body_r=(0.07, 0.09), bumper='black', lamps='box', grille='slit', tail='vertical',
        trim='black', wheel='steel', rub_z=0.38, mirror='trim_black', hatch=True),
    'van': dict(
        L=4.60, W=1.69, axles=(1.32, -1.28), tyre=0.30, arch=0.375, sill=0.24, bumper_z=(0.28, 0.50),
        top=[(-2.30, 0.92), (-2.25, 0.98), (1.60, 0.96), (1.98, 0.92), (2.25, 0.82), (2.30, 0.74)],
        roof=[(-2.29, 0.98), (-2.27, 1.70), (-2.20, 1.93), (0.70, 1.96), (1.05, 1.88), (1.40, 1.40), (1.62, 0.96)],
        gh=(-2.29, 1.62), roof_w=0.70, belt_w=0.82, gh_rt=0.07,
        windshield=(1.04, 1.60), rear_window=(-2.40, -2.20), side=(-2.05, 1.26), pillars=[(0.54, 0.64), (-0.74, -0.64)],
        doors=[1.20, 0.58, -0.60], lamp_h=(0.58, 0.69), tail_h=(0.56, 0.86), grille_w=0.38, plate_rear_z=0.72,
        plan=(0.09, 0.32), body_r=(0.07, 0.06), bumper='grey', lamps='box', grille='slot', tail='vertical',
        trim='black', wheel='steel', rub_z=0.44, mirror='trim_black', van=True),
}
SPECS['taxi'] = dict(SPECS['sedan'], taxi=True)

# where the seated driver goes (car frame: x forward, y left), for web/src/life.js DRIVER
def driver_seat(kind):
    sp = SPECS[kind]
    x = 0.92 if sp.get('van') else sp['pillars'][0][0] + 0.15
    return round(x, 2), (0.36 if sp['W'] > 1.5 else 0.31)


def build_car(kind):
    sp = SPECS[kind]
    L, W = sp['L'], sp['W']
    hw = W / 2
    fa, ra = sp['axles']
    r_arch, tyre = sp['arch'], sp['tyre']
    cy_arch = tyre + 0.01
    p_in, p_len = sp['plan']
    brb, brt = sp['body_r']
    TUMBLE = 0.02
    chrome_trim = sp['trim'] == 'chrome'
    trim_mat = 'chrome' if chrome_trim else 'trim_black'
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
        return hw - p_in * smoothstep(L / 2 - p_len, L / 2, abs(x)) ** 1.6

    def body_y(x, z):
        return section_y(half_w(x), z_bot(x), z_top(x), brb, brt, TUMBLE, z)

    def surf_x(sx, y, z):
        """|x| of the body surface at (y, z) on the front (sx=1) or back (sx=-1)."""
        hi, lo = L / 2, L / 2 - p_len - 0.1
        if body_y(sx * hi, z) >= y:
            return hi
        if body_y(sx * lo, z) < y:
            return lo
        for _ in range(28):
            m = (hi + lo) / 2
            if body_y(sx * m, z) >= y:
                lo = m
            else:
                hi = m
        return (hi + lo) / 2

    def surf_pt(sx, y, z, off):
        e = 0.004
        u0, u1 = surf_x(sx, y - e, z), surf_x(sx, y + e, z)
        t = Vector((sx * (u1 - u0), 2 * e))
        n = Vector((sx * t.y, -sx * t.x)).normalized()
        u = surf_x(sx, y, z)
        return (sx * u + n.x * off, y + n.y * off, z)

    def strip(sx, y0, y1, z0, z1, mat, off=0.004, n=None, sides=(-1, 1)):
        """a lamp/trim strip on the body surface between y0 < y1 (y >= 0), mirrored to both sides."""
        n = n or max(1, int(math.ceil((y1 - y0) / 0.04)))
        ys = [y0 + (y1 - y0) * i / n for i in range(n + 1)]
        for s in sides:
            for ya, yb in zip(ys[:-1], ys[1:]):
                q = [surf_pt(sx, ya, z0, off), surf_pt(sx, yb, z0, off), surf_pt(sx, yb, z1, off), surf_pt(sx, ya, z1, off)]
                q = [(x, s * y, z) for x, y, z in q]
                mb.face(q if s * sx > 0 else q[::-1], mat)

    def wrap_end(sx, z):
        """the y at which a wrap-around lamp ends, a little before the flank."""
        return min(body_y(sx * (L / 2 - p_len * 0.85), z), half_w(sx * (L / 2 - p_len * 0.85))) - 0.012

    # ---------------- lower body
    xs = stations(-L / 2, L / 2, 0.04, extra=[fa - r_arch, fa + r_arch, ra - r_arch, ra + r_arch])

    def body_sec(x):
        return section(half_w(x), z_bot(x), z_top(x), brb, brt, tumble=TUMBLE, crown=0.012)
    loft(mb, xs, body_sec, lambda c, n: 'car_paint', 'body')

    # ---------------- greenhouse
    x0, x1 = sp['gh']
    extra = [x0 + 0.006 * i for i in range(1, 18)] if sp.get('hatch') else []
    xs2 = stations(x0, x1, 0.035, extra=extra)
    belt = lambda x: z_top(x) - 0.02

    def zr(x):
        return interp(sp['roof'], x)

    def gh_sec(x):
        zb, zt = belt(x), max(belt(x) + 0.003, zr(x))
        wb = min(sp['belt_w'], half_w(x) - 0.02)
        h = zt - zb
        wr = sp['roof_w'] + (wb - sp['roof_w']) * max(0.0, 1 - h / 0.12) if h < 0.12 else sp['roof_w']
        return section(wb, zb, zt, 0.01, sp['gh_rt'], tumble=wb - wr, crown=0.018)

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
            if 'rw_z0' in sp and not (sp['rw_z0'] + m < z < zr(x + 0.10) - 0.06 - m):    # tailgate glass
                return False
            return True
        return False

    def gh_mat(c, n):
        if window_kind(c, n, 0.0):
            return 'glass_car'
        if window_kind(c, n, -0.022 if chrome_trim else -0.035):
            return 'trim_black'
        if chrome_trim and window_kind(c, n, -0.045):
            return 'chrome'
        return 'car_paint'
    loft(mb, xs2, gh_sec, gh_mat, 'gh', cap_front=False, cap_back=False)

    # ---------------- wheel-well liners (hide the lofted arch tunnel) + underbody
    for ax in (fa, ra):
        mb.box((ax, 0, 0.42), (r_arch * 2 + 0.02, W - 0.36, 0.56), 'rubber', skip=('bottom',))
        for s in (-1, 1):                       # well walls
            mb.box((ax, s * (hw - 0.17), cy_arch + 0.1), (r_arch * 2, 0.02, r_arch * 1.2), 'rubber')
    mb.box((0, 0, sp['sill'] + 0.02), (L - 0.5, W - 0.2, 0.06), 'rubber', skip=('top',))

    # ---------------- bumpers: lofted, wrapping round the corners
    bz0, bz1 = sp['bumper_z']
    bmat = {'body': 'car_paint', 'grey': 'plastic_grey', 'black': 'plastic_grey'}[sp['bumper']]
    ext = 0.06 if sp['bumper'] == 'body' else 0.07
    band = (bz1 - 0.10, bz1 - 0.055)          # the rub band (black, or chrome on the older saloon)

    for sx in (1, -1):
        start = (fa + r_arch + 0.03) if sx > 0 else -(ra - r_arch - 0.03)
        xe = L / 2 + ext

        def bsec(u, sx=sx, xe=xe):
            k = smoothstep(L / 2 - p_len - 0.05, xe, u)
            wb = min(hw, half_w(sx * min(u, L / 2)) + 0.012) - 0.10 * k ** 2.2
            soft = 0.03 * smoothstep(xe - 0.07, xe, u)
            return section(wb, bz0 + soft, bz1 - soft, 0.05, 0.045, tumble=0.006, crown=0.004,
                           zsplits=band if sp['bumper'] == 'body' else ())

        us = stations(start, xe, 0.035)

        def bmat_fn(c, n):
            if sp['bumper'] == 'body' and band[0] < c.z < band[1] and abs(n.x) < 0.75:
                return 'trim_black'
            return bmat
        sub = MeshBuilder('tmp')
        loft(sub, us, bsec, bmat_fn, 'bump%d' % sx, cap_front=True, cap_back=False)
        for idx, mat, uvs, smooth in sub.faces:      # mirror the rear one by flipping x (and winding)
            pts = [tuple(sub.verts[i]) for i in idx]
            if sx < 0:
                pts = [(-x, y, z) for x, y, z in pts][::-1]
            mb.face(pts, mat, smooth=('bump%d' % sx) if smooth else False)
        xf_ = sx * (xe + 0.002)
        bw = W / 2 - 0.16                        # the band across the flat face (split round the plate)
        for y0, y1 in ((0.20, bw),):
            for s in (-1, 1):
                if sp['bumper'] == 'body':
                    mb.box((xf_, s * (y0 + y1) / 2, sum(band) / 2), (0.006, y1 - y0, band[1] - band[0]), 'trim_black')
                elif sp['trim'] == 'chrome':
                    mb.box((xf_, s * (y0 + y1) / 2, bz1 - 0.06), (0.006, y1 - y0, 0.035), 'chrome')
        if sx > 0 and sp['bumper'] == 'body':     # air intake under the plate
            mb.box((xf_ - 0.01, 0, bz0 + 0.075), (0.012, 0.90, 0.05), 'trim_black')
        if sp['trim'] == 'chrome':
            mb.box((xf_, 0, bz1 - 0.06), (0.006, 0.40, 0.035), 'chrome')

    # ---------------- fascia: lamps and grille
    xf = L / 2
    lz0, lz1 = sp['lamp_h']
    lzc = (lz0 + lz1) / 2
    gw = sp['grille_w']
    flat = body_y(xf, lzc) - 0.005             # half-width of the flat front face at lamp height
    if sp['lamps'] == 'flush':
        we = wrap_end(1, lzc)
        strip(1, gw + 0.03, we - 0.16, lz0, lz1, 'light_white', n=8)
        strip(1, we - 0.16, we, lz0, lz1, 'light_amber', n=5)
        strip(1, gw + 0.015, we + 0.008, lz0 - 0.012, lz1 + 0.012, 'trim_black', off=0.002, n=12)
        strip(1, gw + 0.03, we - 0.17, lz0 - 0.004, lz0 + 0.004, 'chrome', off=0.005, n=8)      # lens split
    else:
        y_out = min(flat - 0.07, gw + 0.03 + (0.36 if L > 4 else 0.24))
        bez = 'chrome' if chrome_trim else 'trim_black'
        strip(1, gw + 0.02, y_out + 0.015, lz0 - 0.015, lz1 + 0.015, bez, off=0.003, n=4)
        strip(1, gw + 0.035, y_out, lz0, lz1, 'light_white', off=0.006, n=4)
        if L > 4:                                 # rectangular quad-lamp look: a divider
            ym = gw + 0.035 + (y_out - gw - 0.035) * 0.55
            strip(1, ym - 0.006, ym + 0.006, lz0, lz1, bez, off=0.008, n=1)
        we = wrap_end(1, lzc)
        strip(1, y_out + 0.02, we, lz0 + 0.005, lz1 - 0.005, 'light_amber', off=0.005)
    # grille
    if sp['grille'] == 'slot':
        gz0, gz1 = lz0 + 0.01, lz1 - 0.01
        mb.box((xf - 0.01, 0, (gz0 + gz1) / 2), (0.03, gw * 2, gz1 - gz0), 'trim_black')
        for z in (gz0, gz1):
            mb.box((xf + 0.004, 0, z), (0.012, gw * 2 + 0.02, 0.01), 'chrome')
        mb.box((xf + 0.002, 0, (gz0 + gz1) / 2), (0.01, gw * 2 - 0.04, 0.008), 'chrome')
        mb.box((xf + 0.008, 0, (gz0 + gz1) / 2), (0.01, 0.09, 0.05), 'chrome')                      # oval-ish badge
    elif sp['grille'] == 'chrome':
        gz0, gz1 = lz0 - 0.01, lz1 + 0.01
        mb.box((xf + 0.005, 0, (gz0 + gz1) / 2), (0.03, gw * 2, gz1 - gz0), 'trim_black')
        for z in (gz0, gz1):
            mb.box((xf + 0.012, 0, z), (0.03, gw * 2 + 0.03, 0.022), 'chrome')
        for s in (-1, 1):
            mb.box((xf + 0.012, s * (gw + 0.005), (gz0 + gz1) / 2), (0.03, 0.02, gz1 - gz0), 'chrome')
        nb = int(gw * 2 / 0.045)
        for i in range(1, nb):
            mb.box((xf + 0.016, -gw + i * 2 * gw / nb, (gz0 + gz1) / 2), (0.01, 0.008, gz1 - gz0 - 0.02), 'chrome')
        mb.box((xf + 0.03, 0, (gz0 + gz1) / 2), (0.012, 0.07, 0.07), 'chrome')                        # badge
        mb.box((xf - 0.05, 0, z_top(xf - 0.05) + 0.02), (0.05, 0.03, 0.04), 'chrome')               # hood ornament
    else:                                        # 'slit': two thin openings in the body-coloured nose panel
        for k, z in enumerate((lzc + 0.022, lzc - 0.015)):
            mb.box((xf + 0.001, 0, z), (0.01, gw * 2 - k * 0.04, 0.018), 'trim_black')
        mb.box((xf + 0.004, 0, lzc + 0.003), (0.01, 0.07, 0.03), 'chrome')

    # ---------------- tail lamps
    tz0, tz1 = sp['tail_h']
    tzc = (tz0 + tz1) / 2
    xr = -L / 2
    if sp['tail'] == 'band':                     # full-width band; the plate sits in its centre garnish
        we = wrap_end(-1, tzc)
        strip(-1, 0.22, we, tz0 - 0.01, tz1 + 0.01, 'trim_black', off=0.002, n=14)
        strip(-1, 0.23, 0.32, tz0, tz1, 'lens_clear', n=2)
        strip(-1, 0.32, we - 0.13, tz0, tz1, 'light_red', n=8)
        strip(-1, we - 0.13, we, tz0 + (tz1 - tz0) * 0.45, tz1, 'light_amber', n=4)
        strip(-1, we - 0.13, we, tz0, tz0 + (tz1 - tz0) * 0.45, 'light_red', n=4)
        strip(-1, 0.0, 0.22, tz0 - 0.01, tz1 + 0.01, 'trim_black', off=0.002, n=4)                  # garnish round the plate
    elif sp['tail'] == 'blocks':
        we = wrap_end(-1, tzc)
        strip(-1, 0.30, we, tz0 - 0.012, tz1 + 0.012, 'chrome', off=0.002, n=10)
        strip(-1, 0.31, 0.42, tz0, tz1, 'lens_clear', n=2)
        strip(-1, 0.42, we - 0.14, tz0, tz1, 'light_red', n=6)
        strip(-1, we - 0.14, we, tz0, tz1, 'light_amber', n=4)
        mb.box((xr - 0.004, 0, tz1 - 0.035), (0.01, 0.58, 0.05), 'trim_black')                      # garnish
    else:                                        # 'vertical': tall lamps on the rear corners
        we = min(wrap_end(-1, tzc), body_y(-L / 2, tzc) + 0.03)
        y0 = max(0.25, we - (0.20 if sp.get('van') else 0.16))
        strip(-1, y0 - 0.012, we + 0.006, tz0 - 0.012, tz1 + 0.012, 'trim_black', off=0.002, n=5)
        h3 = (tz1 - tz0) / 3
        strip(-1, y0, we, tz0 + 2 * h3, tz1, 'light_red', n=4)
        strip(-1, y0, we, tz0 + h3, tz0 + 2 * h3, 'light_amber', n=4)
        strip(-1, y0, we, tz0, tz0 + h3, 'light_red', n=4)
        strip(-1, y0 + 0.02, y0 + 0.09, tz0 + 0.02, tz0 + h3 - 0.02, 'lens_clear', off=0.006, n=1)

    # ---------------- plates (UV into the 2x2 plate atlas: 0/1 green private, 2 yellow commercial, 3 taxi roof sign)
    cell = 2 if sp.get('taxi') else (0 if kind in ('sedan', 'van', 'sedan2') else 1)
    u0, v0 = (cell % 2) * 0.5, 0.5 if cell < 2 else 0.0          # Blender UVs (v up); the glTF export flips them
    pw, ph = 0.335, 0.165
    zr_plate = sp['plate_rear_z']
    for sx, zc in ((1, (bz0 + bz1) / 2 - (0.01 if sp['bumper'] == 'body' else 0.0)), (-1, zr_plate)):
        x = sx * (L / 2 + (ext + 0.006 if sx > 0 else 0.014))
        if sx < 0:
            mb.box((-L / 2 - 0.003, 0, zc), (0.01, pw + 0.04, ph + 0.03), 'trim_black')               # plate recess
        q = [(x, -pw / 2 * sx, zc - ph / 2), (x, pw / 2 * sx, zc - ph / 2), (x, pw / 2 * sx, zc + ph / 2), (x, -pw / 2 * sx, zc + ph / 2)]
        mb.face(q, 'plate', uvs=[(u0, v0), (u0 + 0.5, v0), (u0 + 0.5, v0 + 0.5), (u0, v0 + 0.5)])

    # ---------------- sides: rub strips, door seams, handles, mirrors
    for s in (-1, 1):
        xa, xb = ra + r_arch + 0.03, fa - r_arch - 0.03
        zc = sp['rub_z']
        ys = s * (body_y((xa + xb) / 2, zc) + 0.008)
        mb.box(((xa + xb) / 2, ys, zc), (xb - xa, 0.025, 0.045), 'trim_black')
        if chrome_trim:
            mb.box(((xa + xb) / 2, ys + s * 0.013, zc + 0.012), (xb - xa, 0.004, 0.008), 'chrome')
        for dx in sp['doors']:
            yv = s * (half_w(dx) + 0.002)
            q = [(dx - 0.005, yv, sp['sill'] + 0.06), (dx + 0.005, yv, sp['sill'] + 0.06), (dx + 0.005, yv, belt(dx)), (dx - 0.005, yv, belt(dx))]
            mb.face(q if s > 0 else q[::-1], 'trim_black')
        for dx in sp['doors'][:-1]:
            hx = dx - 0.22
            mb.box((hx, s * (half_w(hx) + 0.006), belt(hx) - 0.09), (0.13, 0.016, 0.028), trim_mat)
        mx = sd[1] - 0.04
        my = s * (half_w(mx) + 0.08)
        mz = belt(mx) + 0.09
        mb.box((mx, my, mz), (0.07, 0.15, 0.10), sp['mirror'])
        mb.box((mx - 0.036, my, mz), (0.005, 0.13, 0.085), 'chrome')
        mb.box((mx + 0.03, s * (half_w(mx) + 0.02), belt(mx) + 0.04), (0.08, 0.05, 0.06), 'trim_black')   # sail
    # wipers & antenna
    for s in (-0.3, 0.35):
        x = ws[1] - 0.04
        mb.box((x - 0.05, s, belt(x) + 0.03), (0.04, 0.48, 0.012), 'trim_black')
    ax_ = sd[1] + 0.25
    mb.cylinder((ax_, -hw + 0.12), 0.004, z_top(ax_), z_top(ax_) + 0.75, 'metal_dark', seg=4, cap_top=True, smooth=False)

    # ---------------- interior seen through the glass
    zf = sp['sill'] + 0.12
    dx_, dy_ = driver_seat(kind)
    xd = ws[1] - 0.17                                                                         # under the windscreen base
    mb.box((xd, 0, belt(xd) - 0.10), (0.34, W - 0.30, 0.18), 'car_interior')                 # dashboard
    rows = [dx_ + 0.15, 0.10, -0.85, -1.70] if sp.get('van') else [dx_ + 0.15, dx_ - 0.75]
    seat_w = min(0.48, W / 2 - 0.22)
    for i, rx in enumerate(rows):
        for s in ((-1, 1) if i == 0 else (0,)):
            yy = s * 0.36 if W > 1.5 else s * 0.31
            wseat = seat_w if i == 0 else W - 0.42
            mb.box((rx, yy, zf + 0.22), (0.48, wseat, 0.14), 'car_interior')
            mb.box((rx - 0.24, yy, zf + 0.52), (0.12, wseat, 0.46), 'car_interior')
    # steering wheel (left-hand drive, driver on +Y)
    swx = min(dx_ + 0.50, xd - 0.22)
    swy, swz = dy_, belt(swx) + 0.02
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

    tw = 0.165 if W < 1.5 else 0.19
    wheels = [make_wheel(f'wheel_{n}', (x, s * (hw - 0.12), tyre), tyre, tw, s, sp['wheel']) for n, x, s in
              (('FL', fa, 1), ('FR', fa, -1), ('RL', ra, 1), ('RR', ra, -1))]
    return mb, wheels


def make_wheel(name, c, r, w, side, style='steel'):
    """Tyre with rounded shoulders and either a 1990s plastic full wheel cover (silver, ring of slots) or a
    pressed-steel rim with a small chrome centre cap. Built around the origin; the caller places the object at c
    (the axle), so the game can spin it about its local Y (glTF -Z) axis."""
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
    # face of the wheel (side = +1: outer face at +Y)
    yo = side * hw * 0.92
    if style == 'cover':
        rim = [(r * 0.68, yo), (r * 0.66, yo + side * 0.008), (r * 0.56, yo + side * 0.014), (r * 0.30, yo + side * 0.012),
               (r * 0.20, yo + side * 0.016), (0.0, yo + side * 0.02)]
        rmats = ['metal', 'metal', 'metal', 'chrome', 'chrome']
    else:
        rim = [(r * 0.66, yo), (r * 0.60, yo - side * 0.02), (r * 0.40, yo - side * 0.03), (r * 0.26, yo - side * 0.025),
               (r * 0.22, yo + side * 0.01), (0.0, yo + side * 0.015)]
        rmats = ['metal_dark', 'metal_dark', 'metal_dark', 'chrome', 'chrome']
    for k in range(seg):
        a0, a1 = 2 * math.pi * k / seg, 2 * math.pi * (k + 1) / seg
        for i in range(len(rim) - 1):
            (r0, y0), (r1, y1) = rim[i], rim[i + 1]
            q = [ring(r0, y0, a0), ring(r1, y1, a0), ring(r1, y1, a1), ring(r0, y0, a1)]
            if side < 0:
                q = q[::-1]
            mb.face(q, rmats[i], smooth='rim%d' % i)
    if style == 'cover':                         # a ring of slots in the cover
        for k in range(12):
            a = 2 * math.pi * k / 12
            p = Vector(ring(r * 0.45, yo + side * 0.0145, a))
            t = Vector((-math.sin(a), 0, math.cos(a)))
            u = Vector((math.cos(a), 0, math.sin(a)))
            q = [p - t * 0.022 - u * 0.03, p + t * 0.022 - u * 0.03, p + t * 0.022 + u * 0.03, p - t * 0.022 + u * 0.03]
            q = [tuple(v + Vector((0, side * 0.002, 0))) for v in q]
            mb.face(q if side > 0 else q[::-1], 'trim_black')
    else:                                        # vent holes in the steel disc
        for k in range(6):
            a = 2 * math.pi * k / 6
            p = Vector(ring(r * 0.47, yo - side * 0.028, a))
            t = Vector((-math.sin(a), 0, math.cos(a)))
            u = Vector((math.cos(a), 0, math.sin(a)))
            q = [p - t * 0.02 - u * 0.018, p + t * 0.02 - u * 0.018, p + t * 0.02 + u * 0.018, p - t * 0.02 + u * 0.018]
            q = [tuple(v + Vector((0, side * 0.002, 0))) for v in q]
            mb.face(q if side > 0 else q[::-1], 'trim_black')
    # inner face disc (dark)
    yi = -side * hw * 0.92
    pts = [ring(r * 0.66, yi, 2 * math.pi * k / seg) for k in range(seg)]
    mb.face(pts if side < 0 else pts[::-1], 'trim_black')
    mb.wheel_pos = c
    return mb
