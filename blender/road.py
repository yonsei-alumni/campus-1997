"""1997 백양로 (reference/1997_백양로_항공사진.jpg aerial photo): two-lane asphalt road without a median, raised boxwood
verges, wide paver sidewalks, an outer planting strip for the ginkgo row, lane paint, zebra crossings and the
painted speed bump inside the gate."""
import math
import numpy as np
from mathutils import Vector
from common import MeshBuilder, CAMPUS


def smooth_line(pts, step=2.0, iters=3):
    P = [Vector((x, y)) for x, y in pts]
    for _ in range(iters):           # Chaikin, keep endpoints
        Q = [P[0]]
        for a, b in zip(P[:-1], P[1:]):
            Q += [a.lerp(b, 0.25), a.lerp(b, 0.75)]
        Q.append(P[-1])
        P = Q
    # resample uniformly
    seg = [(P[i + 1] - P[i]).length for i in range(len(P) - 1)]
    total = sum(seg)
    out = []
    s = 0.0
    i, acc = 0, 0.0
    while s <= total:
        while i < len(seg) - 1 and acc + seg[i] < s:
            acc += seg[i]
            i += 1
        t = (s - acc) / seg[i] if seg[i] > 0 else 0
        out.append((s, P[i].lerp(P[i + 1], min(1, t))))
        s += step
    return out


def build():
    R = CAMPUS['baekyangro']
    ps, ph = np.array(R['profile_s']), np.array(R['profile_h'])
    # the profile was computed on the raw polyline; arc length is close enough after smoothing
    samples = smooth_line(R['pts'])
    med, lane, curb = R['median'], R['lane'], R['curb']
    verge, walk, strip = R.get('verge', 0.0), R['walk'], R.get('strip', 0.0)
    e_lane = med + lane
    e_curb = e_lane + curb
    e_verge = e_curb + verge
    e_walk = e_verge + walk
    e_strip = e_walk + strip
    VZ, WZ = 0.32, 0.15            # verge planter top, sidewalk top (above the asphalt)
    mb = MeshBuilder('baekyangro')
    marks = MeshBuilder('baekyangro_paint')
    L = samples[-1][0]
    crossings = list(R.get('crossings', []))
    gaps = R.get('gaps', [])
    bump = R.get('bump')
    frames = []
    for k, (s, p) in enumerate(samples):
        q0 = samples[max(0, k - 1)][1]
        q1 = samples[min(len(samples) - 1, k + 1)][1]
        t = (q1 - q0).normalized()
        n = Vector((-t.y, t.x))          # left normal
        h = float(np.interp(s, ps, ph))
        frames.append((s, p, t, n, h))

    def pt(f, off, dz):
        s, p, t, n, h = f
        q = p + n * off
        return (q.x, q.y, h + dz)

    def in_cross(s, pad=0.0):
        return any(abs(s - c) < 3.0 + pad for c in crossings)

    def in_gap(s, side):
        return any(sd == side and abs(s - g) < hw for g, sd, hw in gaps)

    for a, b in zip(frames[:-1], frames[1:]):
        sm = (a[0] + b[0]) / 2
        cross = in_cross(sm)
        for side in (-1, 1):
            o = lambda v: v * side
            flip = side < 0

            def band(o0, o1, z0, z1, mat):
                q = [pt(a, o(o0), z0), pt(b, o(o0), z0), pt(b, o(o1), z1), pt(a, o(o1), z1)]
                if flip:
                    q = [q[1], q[0], q[3], q[2]]
                mb.face(q, mat)

            def riser(off, z0, z1, mat, outward=True):
                # vertical face along the road at offset `off`; outward=True faces away from the centre line
                q = [pt(a, o(off), z0), pt(b, o(off), z0), pt(b, o(off), z1), pt(a, o(off), z1)]
                if outward != flip:
                    q = [q[1], q[0], q[3], q[2]]
                mb.face(q, mat)

            if med > 0:
                band(0, med, 0, 0, 'asphalt')
            band(med, e_lane, 0, 0, 'asphalt')
            if cross or in_gap(sm, side):
                # pedestrian crossing / side-road entrance: the verge is paved flush with the sidewalk
                riser(e_lane, 0, WZ, 'curb', outward=False)
                band(e_lane, e_verge, WZ, WZ, 'pavers')
            else:
                # granite curb, then the raised boxwood verge with its own kerb
                riser(e_lane, 0, VZ, 'curb', outward=False)
                band(e_lane, e_curb, VZ, VZ, 'curb')
                band(e_curb, e_verge - 0.2, VZ, VZ, 'dirt')
                band(e_verge - 0.2, e_verge, VZ, VZ, 'curb')
                riser(e_verge, WZ, VZ, 'curb', outward=True)
            band(e_verge, e_walk, WZ, WZ, 'pavers')
            # outer planting strip (ginkgo + hedge), then a skirt down to the terrain
            band(e_walk, e_walk + 0.18, WZ + 0.05, WZ + 0.05, 'curb')
            riser(e_walk, WZ, WZ + 0.05, 'curb', outward=False)
            band(e_walk + 0.18, e_strip, WZ, WZ, 'dirt')
            riser(e_strip, -0.8, WZ, 'curb', outward=True)

    # paint ---------------------------------------------------------------
    def strip_(s0, s1, off, width, mat, dz=0.012):
        fa = min(frames, key=lambda f: abs(f[0] - s0))
        fb = min(frames, key=lambda f: abs(f[0] - s1))
        if fa is fb:
            return
        q = [pt(fa, off - width / 2, dz), pt(fb, off - width / 2, dz), pt(fb, off + width / 2, dz), pt(fa, off + width / 2, dz)]
        marks.face(q, mat)

    def at(s):
        return min(frames, key=lambda f: abs(f[0] - s))

    def blank(s, pad):
        return in_cross(s, pad) or (bump is not None and abs(s - bump) < 2.5 + pad)
    # white dashed centre line, solid yellow edge lines along both curbs
    s = 6.0
    while s < L - 6:
        if not blank(s, 2) and not blank(s + 3, 2):
            strip_(s, s + 3.0, 0.0, 0.15, 'paint_white')
        s += 8.0
    for side in (-1, 1):
        s = 4.0
        while s < L - 4:
            if not blank(s, 1.5) and not in_gap(s, side):
                strip_(s, s + 2.0, side * (e_lane - 0.35), 0.15, 'paint_yellow')
            s += 2.0

    def quad_at(f, o0, o1, t0, t1, mat):
        s, p, t, n, h = f
        q0 = p + n * o0 + t * t0
        q1 = p + n * o1 + t * t0
        q2 = p + n * o1 + t * t1
        q3 = p + n * o0 + t * t1
        marks.face([(q0.x, q0.y, h + 0.012), (q3.x, q3.y, h + 0.012), (q2.x, q2.y, h + 0.012), (q1.x, q1.y, h + 0.012)], mat)

    # zebra crossings + stop lines
    for c in crossings:
        f = at(c)
        o = -e_lane + 0.5
        while o < e_lane - 0.4:
            quad_at(f, o, o + 0.5, -2.0, 2.0, 'paint_white')
            o += 1.0
        for side in (-1, 1):
            fb = at(c - side * 4.5)
            o0, o1 = (0.0, e_lane) if side > 0 else (-e_lane, 0.0)
            quad_at(fb, o0, o1, -0.2, 0.2, 'paint_white')
    def hump(f, o0, o1, mat, half=0.9, flat=0.5, rise=0.09):
        # a real raised bump: flat top with sloping sides (a 9 cm rise over 1.8 m), stripes painted on it
        s, p, t, n, h = f
        P = lambda o, d, z: (lambda q: (q.x, q.y, h + z))(p + n * o + t * d)
        prof = [(-half, 0.012), (-flat, rise), (flat, rise), (half, 0.012)]
        for (d0, z0), (d1, z1) in zip(prof, prof[1:]):
            marks.face([P(o0, d0, z0), P(o0, d1, z1), P(o1, d1, z1), P(o1, d0, z0)], mat)
    # speed bump near the gate, raised, with alternating yellow / white blocks across the road (1997 photo)
    if bump is not None:
        f = at(bump)
        o, k = -e_lane, 0
        while o < e_lane - 0.01:
            hump(f, o, min(e_lane, o + 0.9), 'paint_yellow' if k % 2 else 'paint_white')
            o += 0.9
            k += 1
        # ◇ "crossing ahead" diamonds and lane arrows beyond the bump
        for side in (-1, 1):
            s0, p0, t0, n0, h0 = at(bump + (26 if side > 0 else 40))
            c0 = p0 + n0 * (-side * lane * 0.5)
            dia = [c0 - t0 * 1.6, c0 + n0 * 0.9, c0 + t0 * 1.6, c0 - n0 * 0.9]
            inner = [c0 - t0 * 1.3, c0 + n0 * 0.65, c0 + t0 * 1.3, c0 - n0 * 0.65]
            for i in range(4):
                a0, a1, b1, b0 = dia[i], dia[(i + 1) % 4], inner[(i + 1) % 4], inner[i]
                marks.face([(v.x, v.y, h0 + 0.012) for v in (b0, b1, a1, a0)], 'paint_white')
    return [mb, marks], crossings
