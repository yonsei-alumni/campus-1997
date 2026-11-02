"""Bronze statues of the 1997 campus, modelled from photographs.

언더우드 동상 (Horace G. Underwood, at the entrance of the Underwood courtyard; photos: Wikimedia Commons
"Horace_Grant_Underwood_statue_in_Yonsei_Univ_main_campus.jpg", "Underwood_statue.JPG"): a man in a morning coat with
tails and a buttoned waistcoat, both arms held out in front of him, palms up, on a bronze plate on a tapering light
granite pedestal with a moulded cap, a bronze plaque on the front and a broad base.  The figure is the CC0 Quaternius
"Ultimate Modular Men" Suit character, posed and frozen in bronze.

독수리상 (unveiled 9 May 1970; Yonsei: "12.3m high with a 2.5t bronze eagle on a rectangular prism tower. The eagle is
2.6m tall and 5.2m wide ... the statue of Yonseian carved on all four sides"; photos: 2024 campus photo, the 1997 aerial
photo, the 2024 virtual campus): a bronze eagle with its wings raised in a wide V, primaries spread like fingers,
gripping a rock on top of a tall white square column that stands on a pedestal with figures carved on its four faces.

Both return Blender objects in their local frame (front = -Y, ground at z = 0); blender/build.py places them.
"""
import math
import os
import random

import bpy
from mathutils import Matrix, Quaternion, Vector

from common import MeshBuilder, material, ROOT

SUIT = os.path.join(ROOT, 'assets_src', 'quaternius', 'ultimate-modular-characters', 'Suit.gltf')


# ----------------------------------------------------------------------------- helpers
def _bake(ob):
    """Apply every modifier (and an armature deform) into a new plain mesh object."""
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg), preserve_all_data_layers=False, depsgraph=dg)
    out = bpy.data.objects.new(ob.name + '_baked', me)
    out.matrix_world = ob.matrix_world.copy()
    bpy.context.scene.collection.objects.link(out)
    return out


def _join(objs, name):
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.join()
    ob = bpy.context.view_layer.objects.active
    ob.name = name
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    return ob


def _set_material(ob, name):
    ob.data.materials.clear()
    ob.data.materials.append(material(name))
    for p in ob.data.polygons:
        p.material_index = 0


def _skin(name, verts, edges, radii, root=0):
    """A skin-modifier tube (organic limbs and bodies) with subdivision, baked to a mesh."""
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in verts], edges, [])
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    sk = ob.modifiers.new('skin', 'SKIN')
    sk.branch_smoothing = 0.6
    sk.use_smooth_shade = True
    for i, r in enumerate(radii):
        me.skin_vertices[0].data[i].radius = r if isinstance(r, (tuple, list)) else (r, r)
        me.skin_vertices[0].data[i].use_root = (i == root)
    sub = ob.modifiers.new('sub', 'SUBSURF')
    sub.levels = 2
    sub.render_levels = 2
    baked = _bake(ob)
    bpy.data.objects.remove(ob)
    for p in baked.data.polygons:
        p.use_smooth = True
    return baked


def loft(mb, rings, mat, cap0=True, cap1=True, tag=None):
    """Connect rings of points (same count, consistent winding) with quads; optional flat end caps."""
    tag = tag or 'loft%d' % len(mb.faces)
    n = len(rings[0])
    for a, b in zip(rings[:-1], rings[1:]):
        for i in range(n):
            j = (i + 1) % n
            mb.face([a[i], a[j], b[j], b[i]], mat, smooth=tag)
    if cap0:
        mb.face(list(reversed(rings[0])), mat)
    if cap1:
        mb.face(list(rings[-1]), mat)


# ============================================================================= 언더우드 동상
def _rotate_bone_to(arm, pb, target):
    """Turn a pose bone about its head so its axis points along `target`, a world direction (Blender Z-up;
    the imported glTF armature itself is rotated from Y-up, so convert into armature space first)."""
    bpy.context.view_layer.update()
    M = pb.matrix.copy()
    cur = (M.to_3x3() @ Vector((0, 1, 0))).normalized()
    want = (arm.matrix_world.to_3x3().inverted() @ target).normalized()
    q = cur.rotation_difference(want)
    h = M.translation.copy()
    pb.matrix = Matrix.Translation(h) @ q.to_matrix().to_4x4() @ Matrix.Translation(-h) @ M
    bpy.context.view_layer.update()


def _twist_bone(pb, deg):
    """Roll a pose bone about its own axis."""
    bpy.context.view_layer.update()
    M = pb.matrix.copy()
    ax = (M.to_3x3() @ Vector((0, 1, 0))).normalized()
    h = M.translation.copy()
    pb.matrix = Matrix.Translation(h) @ Matrix.Rotation(math.radians(deg), 4, ax) @ Matrix.Translation(-h) @ M
    bpy.context.view_layer.update()


def underwood_figure(height=2.45):
    """The posed Quaternius Suit man as one bronze mesh, feet at z=0, facing -Y."""
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=SUIT, merge_vertices=True, import_shading='SMOOTH')
    new = [o for o in bpy.data.objects if o not in before]
    arm = next(o for o in new if o.type == 'ARMATURE')
    meshes = [o for o in new if o.type == 'MESH' and o.name.startswith('Suit_')]
    # start from the relaxed idle pose, then hold the arms out in welcome (both photos)
    arm.animation_data_create()
    arm.animation_data.action = bpy.data.actions.get('Idle_Neutral')
    bpy.context.scene.frame_set(1)
    bpy.context.view_layer.update()
    basis = {pb.name: pb.matrix_basis.copy() for pb in arm.pose.bones}
    arm.animation_data.action = None
    for pb in arm.pose.bones:
        pb.matrix_basis = basis[pb.name]
    bpy.context.view_layer.update()
    # armature space: the character faces -Y, its left (.L) is +X
    for side, sx in (('L', 1), ('R', -1)):
        P = arm.pose.bones
        _rotate_bone_to(arm, P['UpperArm.' + side], Vector((0.34 * sx, -0.42, -0.84)))
        _rotate_bone_to(arm, P['LowerArm.' + side], Vector((0.36 * sx, -0.93, 0.04)))
        _rotate_bone_to(arm, P['Wrist.' + side], Vector((0.34 * sx, -0.93, 0.1)))
        _twist_bone(P['LowerArm.' + side], -70 * sx)          # palms turned up
        # open hands: straighten the fingers a little
        for f in ('Index', 'Middle', 'Ring', 'Pinky'):
            for k in (1, 2, 3):
                b = P.get(f'{f}{k}.{side}')
                if b:
                    b.matrix_basis = Matrix.Identity(4)
    # a slight lift of the chin, as in the photos
    _twist_bone(arm.pose.bones['Neck'], 0)
    baked = []
    for m in meshes:
        b = _bake(m)
        b.matrix_world = m.matrix_world.copy()
        baked.append(b)
    for o in new:
        bpy.data.objects.remove(o, do_unlink=True)
    ob = _join(baked, 'underwood_figure')
    # normalise: feet on z=0, centred, scaled to the statue's height
    bb = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
    z0, z1 = min(v.z for v in bb), max(v.z for v in bb)
    cx = (min(v.x for v in bb) + max(v.x for v in bb)) / 2
    s = height / (z1 - z0)
    me = ob.data
    feet_y = 0.0
    for v in me.vertices:
        z = (v.co.z - z0) / (z1 - z0)
        fat = 1.0 + 0.16 * math.exp(-((z - 0.55) / 0.2) ** 2)     # fuller chest and waist under the coat
        p = Vector(((v.co.x - cx) * fat, v.co.y * fat, v.co.z - z0))
        if z > 0.84:                                              # a smaller head: an adult, not the stylised youth
            pivot = Vector((0, 0, 0.84 * (z1 - z0)))
            p = pivot + (p - pivot) * 0.84
        v.co = p * s
    _set_material(ob, 'bronze_patina')
    return ob, s


def underwood_coat(fig, H):
    """The skirt of the morning coat: open in front, cut away over the hips, hanging to the backs of the knees.
    Sized from the figure's own hips so it sits on the body."""
    vs = [v.co for v in fig.data.vertices]
    def extent(z0, z1):
        band = [v for v in vs if z0 * H < v.z < z1 * H and abs(v.x) < 0.3 * H / 2.45]
        return (max(abs(v.x) for v in band), min(v.y for v in band), max(v.y for v in band))
    hx, hy0, hy1 = extent(0.5, 0.56)
    cy = (hy0 + hy1) / 2
    rx, ry = hx + 0.02, (hy1 - hy0) / 2 + 0.03
    mb = MeshBuilder('underwood_coat')
    mat = 'bronze_patina'
    zw = 0.585 * H                                        # waist seam
    # angle 0 = +X (his left), 90 = +Y (back), 270 = -Y (front); the front is open between 240 and 300 degrees
    angs = [math.radians(a) for a in [300 + k * 300 / 24 for k in range(25)]]
    def hem(a):
        back = max(0.0, math.cos(a - math.pi / 2))        # 1 at the back, 0 at the sides and front
        return 0.42 * H - 0.15 * H * back ** 0.6           # sides cut away higher, tails to the knees
    rows = 6
    outer, inner = [], []
    for j in range(rows + 1):
        t = j / rows
        o_row, i_row = [], []
        for a in angs:
            z = zw + (hem(a) - zw) * t
            flare = 1 + 0.32 * t
            x = math.cos(a) * rx * flare
            y = cy + math.sin(a) * ry * flare + 0.04 * t * max(0, math.sin(a))
            o_row.append(Vector((x, y, z)))
            i_row.append(Vector((x * 0.93, cy + (y - cy) * 0.9, z)))
        outer.append(o_row)
        inner.append(i_row)
    n = len(angs)
    for j in range(rows):
        for k in range(n - 1):
            mb.face([outer[j][k], outer[j + 1][k], outer[j + 1][k + 1], outer[j][k + 1]], mat, smooth='coat_o')
            mb.face([inner[j][k + 1], inner[j + 1][k + 1], inner[j + 1][k], inner[j][k]], mat, smooth='coat_i')
    for k in range(n - 1):                                 # hem edge
        mb.face([outer[rows][k], inner[rows][k], inner[rows][k + 1], outer[rows][k + 1]], mat)
    for k in (0, n - 1):                                   # front edges
        for j in range(rows):
            q = [outer[j][k], inner[j][k], inner[j + 1][k], outer[j + 1][k]]
            mb.face(q if k == 0 else q[::-1], mat)
    # the back vent between the two tails
    mb.face([Vector((0, cy + ry * 1.3, hem(math.pi / 2) - 0.01)), Vector((0.01, cy + ry * 1.32, zw - 0.25 * (zw - hem(math.pi / 2)))),
             Vector((-0.01, cy + ry * 1.32, zw - 0.25 * (zw - hem(math.pi / 2))))], mat)
    return mb


def underwood_pedestal():
    """Granite pedestal: broad base, tapering shaft with a bronze plaque, moulded cap; round steps around it."""
    mb = MeshBuilder('underwood_pedestal')
    G, Gd = 'granite_light', 'stone_granite'
    # two low round steps (the courtyard entrance)
    mb.cylinder((0, 0), 3.4, -0.6, 0.14, G, seg=48, smooth=False)
    mb.cylinder((0, 0), 2.7, 0.14, 0.28, G, seg=48, smooth=False)
    mb.box((0, 0, 0.28 + 0.3), (2.3, 2.3, 0.6), G)                  # base block
    mb.box((0, 0, 0.88 + 0.1), (2.0, 2.0, 0.2), G)                  # base moulding
    # tapering shaft 1.7 -> 1.5 m
    z0, z1, w0, w1 = 1.08, 3.0, 0.85, 0.75
    c0 = [(-w0, -w0), (w0, -w0), (w0, w0), (-w0, w0)]
    c1 = [(-w1, -w1), (w1, -w1), (w1, w1), (-w1, w1)]
    for i in range(4):
        a0, b0, a1, b1 = c0[i], c0[(i + 1) % 4], c1[i], c1[(i + 1) % 4]
        mb.face([(a0[0], a0[1], z0), (b0[0], b0[1], z0), (b1[0], b1[1], z1), (a1[0], a1[1], z1)], G)
    mb.box((0, 0, 3.06), (1.66, 1.66, 0.12), G)                     # neck band
    mb.box((0, 0, 3.27), (2.02, 2.02, 0.3), G)                      # cornice
    mb.box((0, 0, 3.47), (1.8, 1.8, 0.1), G)
    # bronze plate under the feet and the plaque on the front (-Y)
    mb.box((0, 0, 3.58), (1.0, 0.82, 0.12), 'bronze_patina')
    y = -(w0 + (w1 - w0) * 0.45) - 0.03
    mb.box((0, y, 2.0), (0.8, 0.05, 1.05), 'bronze_patina')
    return mb


def underwood_statue():
    fig, s = underwood_figure()                 # feet at z = 0
    coat = underwood_coat(fig, 2.45).build()    # measured on the figure at ground level
    for ob in (fig, coat):
        ob.data.transform(Matrix.Translation((0, 0, 3.64)))     # onto the bronze plate on the pedestal
    return [fig, coat, underwood_pedestal().build()]


# ============================================================================= 독수리상
def _airfoil(le, chord_dir, up, chord, th, n=8):
    """Closed ring of a thin wing section: leading edge `le`, chord along chord_dir, thickness along up."""
    pts = []
    for k in range(n):
        a = 2 * math.pi * k / n
        u = (1 - math.cos(a)) / 2                       # 0 at the leading edge, 1 at the trailing edge
        bulge = th * (1 - u) ** 0.7 * (0.35 + u) * 1.8
        pts.append(le + chord_dir * (chord * u) + up * (bulge * (1 if a < math.pi else -0.45)))
    return pts


def eagle_body():
    """Body, neck, head and the feathered legs as one skin-modifier tube (eagle-local, wings separate)."""
    head_turn = math.radians(35)          # the head looks over its left shoulder (as in the 2024 photo)
    hr = Matrix.Rotation(head_turn, 3, 'Z')
    # the body leans forward over the rock, chest out, like the bronze in the photos
    neck = Vector((0, -0.5, 1.42))
    V = [
        Vector((0, 0.72, 0.78)),           # 0 tail root
        Vector((0, 0.36, 0.86)),           # 1 rump
        Vector((0, 0.0, 0.98)),            # 2 belly
        Vector((0, -0.3, 1.18)),           # 3 chest
        neck,                              # 4 neck
        neck + hr @ Vector((0, -0.14, 0.14)),  # 5 head
        Vector((0.14, -0.02, 0.8)),        # 6 L thigh
        Vector((0.17, -0.06, 0.48)),       # 7 L feathered "trousers"
        Vector((0.18, -0.1, 0.2)),         # 8 L ankle
        Vector((-0.14, -0.02, 0.8)),       # 9 R thigh
        Vector((-0.17, -0.06, 0.48)),      # 10 R
        Vector((-0.18, -0.1, 0.2)),        # 11 R ankle
    ]
    E = [(0, 1), (1, 2), (2, 3), (3, 4), (4, 5), (2, 6), (6, 7), (7, 8), (2, 9), (9, 10), (10, 11)]
    R = [(0.18, 0.1), (0.34, 0.3), (0.42, 0.4), (0.42, 0.38), (0.2, 0.21), (0.18, 0.19),
         (0.2, 0.2), (0.18, 0.18), (0.07, 0.07), (0.2, 0.2), (0.18, 0.18), (0.07, 0.07)]
    body = _skin('eagle_body', V, E, R, root=2)
    mb = MeshBuilder('eagle_parts')
    M = 'bronze_patina'
    # hooked beak from the head, turned with it
    hd = V[5]
    fwd = hr @ Vector((0, -1, 0))
    rings = []
    for k in range(6):
        t = k / 5
        c = hd + fwd * (0.12 + 0.22 * t) + Vector((0, 0, -0.02 - 0.16 * t ** 2.2))
        w = 0.085 * (1 - t) + 0.008
        h = 0.11 * (1 - t) + 0.01
        side = hr @ Vector((1, 0, 0))
        rings.append([c + side * w, c + Vector((0, 0, h * 0.6)), c - side * w, c - Vector((0, 0, h * 0.5))])
    loft(mb, rings, M, cap0=False)
    # brow ridges (the eagle's fierce look)
    for sx in (-1, 1):
        side = hr @ Vector((sx, 0, 0))
        p = hd + fwd * 0.1 + side * 0.09 + Vector((0, 0, 0.06))
        mb.box(tuple(p), (0.07, 0.12, 0.03), M, rotz=head_turn)
    # tail: a fan of broad feathers, slightly spread and pointing down behind the legs
    root = V[0]
    for k in range(7):
        a = math.radians(-24 + k * 8)
        d = Vector((math.sin(a) * 0.9, math.cos(a) * 0.55, -0.62)).normalized()
        rings = []
        for j in range(5):
            t = j / 4
            c = root + d * (0.95 * t)
            w = 0.075 + 0.05 * math.sin(t * math.pi * 0.8)
            side = d.cross(Vector((0, 0, 1))).normalized()
            up = side.cross(d).normalized()
            rings.append([c + side * w, c + up * 0.025, c - side * w, c - up * 0.02])
        loft(mb, rings, M)
    # talons gripping the rock: three forward toes and a hind toe on each foot
    for sx in (-1, 1):
        ank = Vector((0.18 * sx, -0.1, 0.2))
        for (dx, dy) in ((0.12 * sx, -0.25), (0.0, -0.3), (-0.1 * sx, -0.24), (0.02 * sx, 0.24)):
            rings = []
            for j in range(6):
                t = j / 5
                c = ank + Vector((dx * t, dy * t, -0.2 * t - 0.12 * t * t))
                r = 0.045 * (1 - t) + 0.008
                rings.append([c + Vector((r, 0, 0)), c + Vector((0, r, 0)), c + Vector((-r, 0, 0)), c + Vector((0, -r, 0))])
            loft(mb, rings, M, cap0=False)
    return body, mb


def eagle_wing(sx, span=2.7, dihedral=34.0):
    """One wing raised in a V: a broad inner wing with scalloped secondaries, then six spread primaries."""
    mb = MeshBuilder(f'eagle_wing_{sx}')
    M = 'bronze_patina'
    shoulder = Vector((0.26 * sx, -0.2, 1.3))
    a = math.radians(dihedral)
    out = Vector((sx * math.cos(a), -0.08, math.sin(a))).normalized()    # along the leading edge (a little forward)
    # chord: mostly downward and a little back, so the broad feathered surface faces forward (raised, mantling
    # wings) instead of showing only its edge from the front
    back = Vector((-sx * 0.12, 0.5, -0.86)).normalized()
    back = (back - out * back.dot(out)).normalized()
    up = out.cross(back).normalized() * (1 if sx > 0 else -1)
    hand = 0.62
    rings = []
    N = 14
    for k in range(N + 1):
        t = hand * k / N
        # the leading edge bows forward at the wrist; the inner wing is broad, narrowing toward the hand
        le = shoulder + out * (span * t) + Vector((0, -0.12 * math.sin(t / hand * math.pi), 0.08 * math.sin(t / hand * math.pi)))
        chord = 1.45 - 0.3 * (t / hand) ** 1.5
        chord += 0.07 * abs(math.sin(t * 22))            # scalloped trailing edge (secondary feathers)
        th = 0.13 * (1 - 0.5 * t / hand)
        rings.append(_airfoil(le, back, up, chord, th))
    if sx < 0:
        rings = [list(reversed(r)) for r in rings]
    loft(mb, rings, M)
    # primaries: long separate feathers fanning from the hand, curling up at the tips
    wrist = shoulder + out * (span * hand)
    for i in range(6):
        base = wrist + back * (0.08 + 0.17 * i)
        fan = math.radians(-4 + i * 12)                  # leading primary points out, the rest sweep back
        d = (out * math.cos(fan) + back * math.sin(fan)).normalized()
        L = 1.45 - 0.1 * i
        rings = []
        for j in range(6):
            t = j / 5
            c = base + d * (L * t) + up * (0.12 * t * t)
            w = 0.15 * (1 - t ** 3.2) ** 0.5 + 0.02         # broad feather with a rounded tip
            side = d.cross(up).normalized()
            rings.append([c + side * w, c + up * 0.03, c - side * w, c - up * 0.015])
        if sx < 0:
            rings = [list(reversed(r)) for r in rings]
        loft(mb, rings, M)
    # coverts: a thick ridge of small feathers along the leading edge over the shoulder
    rings = []
    for k in range(8):
        t = 0.45 * k / 7
        c = shoulder + out * (span * t) + back * 0.1 + up * 0.05
        r = 0.12 * (1 - t)
        rings.append([c + back * r, c + up * r, c - back * r * 0.5, c - up * r * 0.6])
    if sx < 0:
        rings = [list(reversed(r)) for r in rings]
    loft(mb, rings, M)
    return mb


def eagle_rock():
    """Bronze rock the eagle grips, sitting on the column cap."""
    rnd = random.Random(70)
    mb = MeshBuilder('eagle_rock')
    seg, rings_n = 12, 7
    P = []
    for j in range(rings_n + 1):
        th = math.pi * j / rings_n
        row = []
        for i in range(seg):
            ph = 2 * math.pi * i / seg
            r = 1 + rnd.uniform(-0.12, 0.12)
            row.append(Vector((0.62 * r * math.sin(th) * math.cos(ph), 0.5 * r * math.sin(th) * math.sin(ph), 0.0 + 0.32 * r * (1 - math.cos(th)) * 0.9)))
        P.append(row)
    for j in range(rings_n):
        for i in range(seg):
            k = (i + 1) % seg
            mb.face([P[j][i], P[j][k], P[j + 1][k], P[j + 1][i]], 'bronze_patina', smooth='rock')
    return mb


def eagle_figure(width=5.2):
    """The bronze eagle, perched on its rock, feet at z=0, facing -Y, scaled to the published 5.2 m width."""
    body, parts = eagle_body()
    objs = [body, parts.build(), eagle_wing(1).build(), eagle_wing(-1).build()]
    ob = _join(objs, 'eagle')
    bb = [Vector(c) for c in ob.bound_box]
    w = max(v.x for v in bb) - min(v.x for v in bb)
    zmin = min(v.z for v in bb)
    s = width / w
    for v in ob.data.vertices:
        v.co = Vector((v.co.x * s, v.co.y * s, (v.co.z - zmin) * s))
    _set_material(ob, 'bronze_patina')
    return ob


def _relief_figure(mb, P, s, z, h, pose, mat):
    """A standing figure in raised relief on a wall: P(s, z, d) maps wall coords (along, up, outward)."""
    d = 0.09
    def slab(s0, s1, z0, z1, dd=d):
        mb.quad(P(s0, z0, dd), P(s1, z0, dd), P(s1, z1, dd), P(s0, z1, dd), mat)
        mb.quad(P(s0, z0, 0), P(s0, z0, dd), P(s0, z1, dd), P(s0, z1, 0), mat)
        mb.quad(P(s1, z0, dd), P(s1, z0, 0), P(s1, z1, 0), P(s1, z1, dd), mat)
        mb.quad(P(s0, z1, 0), P(s0, z1, dd), P(s1, z1, dd), P(s1, z1, 0), mat)
    u = h / 8                                            # head unit
    slab(s - 0.6 * u, s + 0.6 * u, z + 7 * u, z + 8 * u, d * 1.2)        # head
    slab(s - 1.0 * u, s + 1.0 * u, z + 4.2 * u, z + 6.8 * u)             # torso
    slab(s - 0.85 * u, s - 0.1 * u, z, z + 4.2 * u)                      # legs
    slab(s + 0.1 * u, s + 0.85 * u, z, z + 4.2 * u)
    if pose == 'raise':                                                  # one arm raised toward the eagle
        slab(s + 1.0 * u, s + 1.45 * u, z + 6.2 * u, z + 9.4 * u)
        slab(s - 1.45 * u, s - 1.0 * u, z + 3.8 * u, z + 6.6 * u)
    elif pose == 'book':                                                 # holding a book at the chest
        slab(s - 1.4 * u, s + 1.4 * u, z + 5.0 * u, z + 5.8 * u, d * 1.5)
    else:                                                                # arms at the sides
        slab(s + 1.0 * u, s + 1.4 * u, z + 3.9 * u, z + 6.6 * u)
        slab(s - 1.4 * u, s - 1.0 * u, z + 3.9 * u, z + 6.6 * u)


def eagle_tower():
    """Stepped square platform, a pedestal with 'Yonseian' figures carved on its four faces, the tall white column."""
    mb = MeshBuilder('eagle_tower')
    W, Wd = 'stone_white', 'granite_light'
    for k, (w, z) in enumerate(((6.4, 0.0), (5.3, 0.2), (4.2, 0.4))):
        mb.box((0, 0, z + 0.1 - (0.6 if k == 0 else 0) / 2), (w, w, 0.2 + (0.6 if k == 0 else 0)), Wd)
    mb.box((0, 0, 0.6 + 0.15), (2.9, 2.9, 0.3), W)
    zp0, zp1, hw = 0.9, 3.3, 1.2                          # pedestal with the reliefs
    mb.box((0, 0, (zp0 + zp1) / 2), (2 * hw, 2 * hw, zp1 - zp0), W)
    mb.box((0, 0, zp1 + 0.12), (2.7, 2.7, 0.24), W)
    corners = [(-hw, -hw), (hw, -hw), (hw, hw), (-hw, hw)]
    poses = [('raise', 'book', 'side'), ('side', 'raise', 'book'), ('book', 'side', 'raise'), ('raise', 'side', 'book')]
    for i in range(4):
        a, b = Vector((*corners[i], 0)), Vector((*corners[(i + 1) % 4], 0))
        t = (b - a)
        L = t.length
        t.normalize()
        n = Vector((t.y, -t.x, 0))

        def P(s, z, d=0.0, a=a, t=t, n=n):
            p = a + t * s + n * d
            return (p.x, p.y, z)
        # a recessed frame, then three figures
        for (s0, s1, z0, z1) in ((0.12, L - 0.12, zp0 + 0.12, zp0 + 0.2), (0.12, L - 0.12, zp1 - 0.2, zp1 - 0.12)):
            mb.quad(P(s0, z0, 0.03), P(s1, z0, 0.03), P(s1, z1, 0.03), P(s0, z1, 0.03), Wd)
        for k, pose in enumerate(poses[i]):
            _relief_figure(mb, P, L * (0.22 + 0.28 * k), zp0 + 0.32, 1.75, pose, W)
    # the column: square, slightly tapering, with a cap that carries the eagle's rock
    z0, z1 = zp1 + 0.24, 9.35
    w0, w1 = 0.6, 0.5
    c0 = [(-w0, -w0), (w0, -w0), (w0, w0), (-w0, w0)]
    c1 = [(-w1, -w1), (w1, -w1), (w1, w1), (-w1, w1)]
    for i in range(4):
        a0, b0, a1, b1 = c0[i], c0[(i + 1) % 4], c1[i], c1[(i + 1) % 4]
        mb.face([(a0[0], a0[1], z0), (b0[0], b0[1], z0), (b1[0], b1[1], z1), (a1[0], a1[1], z1)], W)
    mb.box((0, 0, z1 + 0.12), (1.3, 1.3, 0.24), W)
    # the dedication on the back (+Y) of the pedestal: a dark inset panel
    mb.box((0, hw + 0.02, 2.1), (1.4, 0.04, 1.1), 'bronze_patina')
    return mb, z1 + 0.24


def eagle_statue():
    tower, top = eagle_tower()
    rock = eagle_rock().build()
    rock.data.transform(Matrix.Translation((0, 0, top)))
    eagle = eagle_figure()
    eagle.location.z = top + 0.18
    bpy.context.view_layer.update()
    bpy.ops.object.select_all(action='DESELECT')
    eagle.select_set(True)
    bpy.context.view_layer.objects.active = eagle
    bpy.ops.object.transform_apply(location=True, rotation=False, scale=False)
    return [tower.build(), rock, eagle]
