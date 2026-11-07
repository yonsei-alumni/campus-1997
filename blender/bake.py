"""Per-corner shading data for the halls and landmarks, read by web/src/materials.js (MaterialLibrary.baked).

One float colour attribute, exported as COLOR_0:
  R  ambient occlusion: how much of the hemisphere over the surface the buildings leave open within AO_DIST (a
     Cycles bake).  Only buildings occlude: the open ground already lights the walls through the hemisphere light's
     ground colour (web/src/main.js), and counting the terrain would darken the lower storeys of every wall.  A face
     looking down (a soffit, the ceiling of a pilotis or a porch) does see the ground under it close by, in the
     building's own shade: that share is added from its height over the terrain.
  G  depth under the ledge above (a sill, a coping, a band) in fade lengths, / D_RANGE   } rain streaks running
  B  position along that ledge, -1..1 under it, (u + U_RANGE) / (2 U_RANGE)             } down from the ledge
  A  1 (free)
White (1, 1, 1, 1) reads as open and under no ledge: what the web app gives a mesh without the attribute.  (The
height over the ground, for the soil splashed up the walls, the web app reads from its own terrain.)

G and B are linear in position over a face, so the corners carry them exactly.  The occlusion is not: a large flat
quad (a 60 m band of glass behind the piers of 중앙도서관, the soffit of 학생회관's pilotis) is split into a grid of
about STEP for the bake and thinned back to the fewest grid lines that reproduce it (an open wall: its corners only).
A large flat n-gon (a roof inside its parapets) takes one value from points inside it.
"""
import bpy, math, time
import numpy as np
import common
from common import MATS

AO_DIST = 10.0         # m: occluders farther than this do not count
AO_SAMPLES = 128       # rays per vertex
SPLIT = 4.0            # m: a flat quad longer than this is split for the bake (the halls' bays and storeys are not)
STEP = 1.5             # m: into a grid this fine
AO_TOL = 0.08          # thin a grid while its coarser cells stay this close to every node
DOWN_W = 0.6           # share of a downward face's light that the shaded ground under it takes away
D_RANGE, U_RANGE = 16.0, 8.0
FADE = 1.6             # m: how far the streaks under a ledge run down (at most the face's height)
QUANT = (64, 256, 256, 1)  # levels per channel
LEDGE_DEPTH = 0.65     # m: deepest upward face that still counts as a ledge (sills, copings, bands, treads)
# halls that were new in 1997 (bid -> share of their materials' weathering, exported as the object's extras):
# 대우관 was finished in 1996, 제3공학관 and 제2인문관 were going up
AGE = {'242897922': 0.1, '224955691': 0.15, '246156119': 0.15}


def _front_only(name):
    """Materials the web app draws one-sided (glass, frames): their face is always the side that counts."""
    d = MATS.get(name.split('.')[0], {})
    return not ('tex' in d or 'leaf' in d or d.get('side') == 'double')


def _is_leaf(name):
    return 'leaf' in MATS.get(name.split('.')[0], {})


def _ground(x, y):
    """common.ground over arrays"""
    T, TH, TS = common._T, common._TH, common._TS
    fx = np.clip((x + TH) / TS, 0, T.shape[1] - 1.001)
    fy = np.clip((y + TH) / TS, 0, T.shape[0] - 1.001)
    i, j = fx.astype(np.int64), fy.astype(np.int64)
    ax, ay = fx - i, fy - j
    return (T[j, i] * (1 - ax) * (1 - ay) + T[j, i + 1] * ax * (1 - ay)
            + T[j + 1, i] * (1 - ax) * ay + T[j + 1, i + 1] * ax * ay)


# ----------------------------------------------------------------------------- mesh arrays
class _Mesh:
    """A mesh as plain arrays: co (V,3), ls (loop start per face), lv (vertex per loop), mi, sm, uv (L,2) or None"""

    def __init__(self, co, ls, lv, mi, sm, uv):
        self.co, self.ls, self.lv, self.mi, self.sm, self.uv = co, ls, lv, mi, sm, uv
        self.lt = np.diff(np.append(ls, len(lv)))
        self.lf = np.repeat(np.arange(len(ls)), self.lt)          # face of every loop

    @staticmethod
    def read(me):
        nv, nl, nf = len(me.vertices), len(me.loops), len(me.polygons)
        co = np.empty(nv * 3, np.float32)
        me.vertices.foreach_get('co', co)
        ls = np.empty(nf, np.int32)
        me.polygons.foreach_get('loop_start', ls)
        lv = np.empty(nl, np.int32)
        me.loops.foreach_get('vertex_index', lv)
        mi = np.empty(nf, np.int32)
        me.polygons.foreach_get('material_index', mi)
        sm = np.empty(nf, bool)
        me.polygons.foreach_get('use_smooth', sm)
        uv = None
        if me.uv_layers:
            uv = np.empty(nl * 2, np.float32)
            me.uv_layers[0].data.foreach_get('uv', uv)
            uv = uv.reshape(-1, 2)
        order = np.argsort(ls, kind='stable')                     # (faces are stored in loop order already)
        return _Mesh(co.reshape(-1, 3).astype(np.float64), ls[order], lv, mi[order], sm[order], uv)

    def write(self, name, mats, col=None):
        me = bpy.data.meshes.new(name)
        me.vertices.add(len(self.co))
        me.vertices.foreach_set('co', self.co.astype(np.float32).ravel())
        me.loops.add(len(self.lv))
        me.loops.foreach_set('vertex_index', self.lv.astype(np.int32))
        me.polygons.add(len(self.ls))
        me.polygons.foreach_set('loop_start', self.ls.astype(np.int32))
        me.update(calc_edges=True)
        for m in mats:
            me.materials.append(m)
        me.polygons.foreach_set('material_index', self.mi.astype(np.int32))
        me.polygons.foreach_set('use_smooth', self.sm.astype(bool))
        if self.uv is not None:
            me.uv_layers.new(name='UVMap').data.foreach_set('uv', self.uv.astype(np.float32).ravel())
        if col is not None:
            ca = me.color_attributes.new('bake', 'FLOAT_COLOR', 'CORNER')
            ca.data.foreach_set('color', col.astype(np.float32).ravel())
            me.color_attributes.active_color = ca
            me.color_attributes.render_color_index = me.color_attributes.active_color_index
        me.validate(clean_customdata=False)
        me.update()
        return me

    def normals(self, co):
        """unit face normals (Newell) for vertex positions co"""
        p = co[self.lv]
        nxt = np.arange(len(self.lv)) + 1
        last = self.ls + self.lt - 1
        nxt[last] = self.ls
        q = p[nxt]
        n = np.zeros((len(self.ls), 3))
        for k, (a, b) in enumerate(((1, 2), (2, 0), (0, 1))):
            n[:, k] = np.bincount(self.lf, (p[:, a] - q[:, a]) * (p[:, b] + q[:, b]), len(self.ls))
        return n / np.maximum(np.linalg.norm(n, axis=1), 1e-12)[:, None]


# ----------------------------------------------------------------------------- 1. split large flat faces
def _newell(c):
    n = np.zeros(3)
    for p, q in zip(c, np.roll(c, -1, 0)):
        n += ((p[1] - q[1]) * (p[2] + q[2]), (p[2] - q[2]) * (p[0] + q[0]), (p[0] - q[0]) * (p[1] + q[1]))
    ln = np.linalg.norm(n)
    return n / ln if ln > 1e-12 else None


def _probes(c, nrm):
    """Up to 9 points inside the flat polygon c, 5 mm off its face, each as a tiny triangle facing as it does"""
    ax = c[1] - c[0]
    ax /= max(np.linalg.norm(ax), 1e-9)
    ay = np.cross(nrm, ax)
    q = np.column_stack(((c - c[0]) @ ax, (c - c[0]) @ ay))
    lo, hi = q.min(0), q.max(0)
    g = np.linspace(0.12, 0.88, 4)
    cand = lo + (hi - lo) * np.array([(x, y) for x in g for y in g])
    inside = np.zeros(len(cand), bool)                     # even-odd rule
    for (x0, y0), (x1, y1) in zip(q, np.roll(q, -1, 0)):
        cross = (y0 > cand[:, 1]) != (y1 > cand[:, 1])
        xs = x0 + (cand[:, 1] - y0) * (x1 - x0) / np.where(y1 != y0, y1 - y0, 1e-12)
        inside ^= cross & (cand[:, 0] < xs)
    pts = cand[inside][::2][:9] if inside.any() else q.mean(0)[None]
    p = c[0] + pts[:, :1] * ax + pts[:, 1:] * ay + nrm * 0.005
    return np.stack((p, p + ax * 0.02, p + ay * 0.02), 1).reshape(-1, 3)


def _densify(m, M):
    """-> (dense mesh, grids, probes).  A large flat quad becomes a grid of about STEP; every other face is copied
    with its own vertices, faces keeping their order (a grid's faces stand in its quad's place).  A large flat n-gon
    (a roof inside its parapets, whose corners all sit in the corners' shade) is sampled at a few points inside instead,
    by tiny triangles after all the faces.
    grid: dict(f, grid (nu, nv), v0 first node, k nodes, W (k, 4) node weights of the quad's corners -- linear in
    position, so they carry UVs and the streak fields exactly -- faces (local quads));  probes: {face: vertex ids}"""
    cow = m.co @ M[:3, :3].T + M[:3, 3]
    co = [m.co]
    ls, lv, mi, sm, uv, patches, probe = [], [], [], [], [], [], {}
    nv_, nl_ = len(m.co), 0
    for f in range(len(m.ls)):
        a, n = m.ls[f], m.lt[f]
        ids = m.lv[a:a + n]
        pt = None
        if not m.sm[f] and n >= 4:
            c = cow[ids]
            nrm = _newell(c)
            flat = nrm is not None and np.abs((c - c[0]) @ nrm).max() < 0.01
            if flat and n == 4:
                lu = max(np.linalg.norm(c[1] - c[0]), np.linalg.norm(c[2] - c[3]))
                lv_ = max(np.linalg.norm(c[3] - c[0]), np.linalg.norm(c[2] - c[1]))
                nu, nv = int(math.ceil(lu / STEP)), int(math.ceil(lv_ / STEP))
                if max(lu, lv_) > SPLIT:
                    s, t = np.meshgrid(np.linspace(0, 1, nu + 1), np.linspace(0, 1, nv + 1))
                    s, t = s.ravel()[:, None], t.ravel()[:, None]
                    W = np.hstack(((1 - s) * (1 - t), s * (1 - t), s * t, (1 - s) * t))
                    i, j = np.meshgrid(np.arange(nu), np.arange(nv))
                    i, j = i.ravel(), j.ravel()
                    F = np.stack((j * (nu + 1) + i, j * (nu + 1) + i + 1, (j + 1) * (nu + 1) + i + 1,
                                  (j + 1) * (nu + 1) + i), 1)
                    pt = dict(grid=(nu, nv), W=W, faces=F)
            elif flat and (c.max(0) - c.min(0)).max() > SPLIT:
                probe[f] = _probes(m.co[ids], _newell(m.co[ids]))
        if pt is None:
            ls.append(np.array([nl_]))
            lv.append(ids)
            mi.append([m.mi[f]])
            sm.append([m.sm[f]])
            if m.uv is not None:
                uv.append(m.uv[a:a + n])
            nl_ += n
            continue
        W, F = pt['W'], pt['faces']
        pt.update(f=f, v0=nv_, k=len(W))
        patches.append(pt)
        co.append(W @ m.co[ids])
        ls.append(nl_ + 4 * np.arange(len(F)))
        lv.append((F + nv_).ravel())
        mi.append([m.mi[f]] * len(F))
        sm.append([False] * len(F))
        if m.uv is not None:
            uv.append((W @ m.uv[a:a + n])[F.ravel()])
        nv_ += len(W)
        nl_ += F.size
    for f, P in probe.items():                              # (the bake reads their first corners)
        k = len(P) // 3
        co.append(P)
        ls.append(nl_ + 3 * np.arange(k))
        lv.append(nv_ + np.arange(3 * k))
        mi.append([m.mi[f]] * k)
        sm.append([False] * k)
        if m.uv is not None:
            uv.append(np.zeros((3 * k, 2)))
        probe[f] = nv_ + 3 * np.arange(k)
        nv_ += 3 * k
        nl_ += 3 * k
    d = _Mesh(np.vstack(co), np.concatenate(ls), np.concatenate(lv), np.concatenate(mi),
              np.concatenate(sm).astype(bool), np.vstack(uv) if m.uv is not None else None)
    return d, patches, probe


# ----------------------------------------------------------------------------- 2. bake
def _bake_pass(ob, name):
    ca = ob.data.color_attributes.new(name, 'FLOAT_COLOR', 'POINT')
    ob.data.color_attributes.active_color = ca
    bpy.ops.object.bake(type='AO')
    a = np.empty(len(ob.data.vertices) * 4, np.float32)
    ob.data.color_attributes[name].data.foreach_get('color', a)
    return a.reshape(-1, 4)[:, 0].astype(np.float64)


def _bake_both_sides(meshes, scene_objs):
    """AO per vertex of every dense mesh (world space), baked as one object: Cycles syncs the whole scene for each
    object it bakes"""
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'
    sc.cycles.device = 'CPU'
    sc.cycles.samples = AO_SAMPLES
    if sc.world is None:
        sc.world = bpy.data.worlds.new('bake')
    sc.world.light_settings.distance = AO_DIST
    sc.render.bake.target = 'VERTEX_COLORS'
    off = np.cumsum([0] + [len(d.co) for d in meshes])
    loff = np.cumsum([0] + [len(d.lv) for d in meshes])
    allm = _Mesh(np.vstack([d.co for d in meshes]),
                 np.concatenate([d.ls + lo for d, lo in zip(meshes, loff)]),
                 np.concatenate([d.lv + o for d, o in zip(meshes, off)]),
                 np.zeros(sum(len(d.ls) for d in meshes), np.int32),
                 np.concatenate([d.sm for d in meshes]), None)
    tmp = bpy.data.objects.new('bake_tmp', allm.write('bake_tmp', []))
    sc.collection.objects.link(tmp)
    hide = [o for o in scene_objs if not o.hide_render]
    for o in hide:
        o.hide_render = True
    bpy.ops.object.select_all(action='DESELECT')
    tmp.select_set(True)
    bpy.context.view_layer.objects.active = tmp
    # the GLB faces wind either way (the web draws the walls double-sided): bake both sides, keep the open one
    front = _bake_pass(tmp, 'ao_front')
    tmp.data.flip_normals()
    back = _bake_pass(tmp, 'ao_back')
    for o in hide:
        o.hide_render = False
    me = tmp.data
    bpy.data.objects.remove(tmp)
    bpy.data.meshes.remove(me)
    return ([front[off[i]:off[i + 1]] for i in range(len(meshes))],
            [back[off[i]:off[i + 1]] for i in range(len(meshes))])


# ----------------------------------------------------------------------------- 3. ledges and rain streaks
def _streaks(m, cow, n_eff):
    """The G and B channels per loop of the original mesh: under which ledge each wall face lies"""
    dep = np.ones(len(m.lv))
    along = np.ones(len(m.lv))
    cell = 4.0
    ledges, grid = [], {}
    for f in np.where(n_eff[:, 2] > 0.9)[0]:
        xy = cow[m.lv[m.ls[f]:m.ls[f] + m.lt[f]], :2]
        best = None
        for k in range(len(xy)):
            e = xy[(k + 1) % len(xy)] - xy[k]
            L = math.hypot(*e)
            if L < 1e-3:
                continue
            ax = e / L
            a, b = xy @ ax, xy @ np.array((-ax[1], ax[0]))
            ea, eb = a.max() - a.min(), b.max() - b.min()
            if best is None or ea * eb < best[0]:
                best = (ea * eb, max(ea, eb), min(ea, eb))
        if best is None or best[2] > LEDGE_DEPTH or best[1] < 0.3:
            continue
        z = cow[m.lv[m.ls[f]:m.ls[f] + m.lt[f]], 2].mean()
        li = len(ledges)
        ledges.append((z, xy))
        lo, hi = np.floor(xy.min(0) / cell).astype(int), np.floor(xy.max(0) / cell).astype(int)
        for gx in range(lo[0], hi[0] + 1):
            for gy in range(lo[1], hi[1] + 1):
                grid.setdefault((gx, gy), []).append(li)
    if not ledges:
        return dep, along
    for f in np.where(np.abs(n_eff[:, 2]) < 0.15)[0]:
        a, n = m.ls[f], m.lt[f]
        p = cow[m.lv[a:a + n]]
        ztop, zbot = p[:, 2].max(), p[:, 2].min()
        nf = n_eff[f, :2] / max(np.linalg.norm(n_eff[f, :2]), 1e-9)
        tf = np.array((-nf[1], nf[0]))
        fs = p[:, :2] @ tf
        lo, hi = np.floor(p[:, :2].min(0) / cell).astype(int), np.floor(p[:, :2].max(0) / cell).astype(int)
        cand = set()
        for gx in range(lo[0], hi[0] + 1):
            for gy in range(lo[1], hi[1] + 1):
                cand.update(grid.get((gx, gy), ()))
        best = None
        for li in cand:
            z, xy = ledges[li]
            if not (z - 0.3 <= ztop <= z + 0.02):
                continue
            dd = (xy - p[0, :2]) @ nf
            if not (-0.03 <= dd.max() <= 0.7 and dd.min() >= -0.6):
                continue
            ls_ = xy @ tf
            ov = min(ls_.max(), fs.max()) - max(ls_.min(), fs.min())
            if ov > 0.15 and (best is None or ov > best[0]):
                best = (ov, z, ls_.min(), ls_.max())
        if best is None:
            continue
        _, z, l0, l1 = best
        u = (fs - (l0 + l1) / 2) / max((l1 - l0) / 2, 0.05)
        if np.abs(u).max() > U_RANGE:
            continue
        fade = min(FADE, max(0.3, ztop - zbot))
        dep[a:a + n] = np.clip((z - p[:, 2]) / fade / D_RANGE, 0, 1)
        along[a:a + n] = (u + U_RANGE) / (2 * U_RANGE)
    return dep, along


def _coarsest(g):
    """The fewest grid lines (index arrays along u and v, ends included) whose bilinear cells reproduce every node of
    the grid g (nv+1, nu+1) within AO_TOL"""
    nv, nu = g.shape[0] - 1, g.shape[1] - 1

    def lines(n, k):
        return np.unique(np.r_[np.arange(0, n, k), n])

    def interp(idx, n):                                       # fine index -> (cell start, cell end, weight)
        c = np.clip(np.searchsorted(idx, np.arange(n + 1), side='right') - 1, 0, len(idx) - 2)
        return idx[c], idx[c + 1], (np.arange(n + 1) - idx[c]) / (idx[c + 1] - idx[c])

    steps = lambda n: sorted({n} | {2 ** e for e in range(int(math.log2(max(n, 1))) + 1)}, reverse=True)
    best = None
    for ku in steps(nu):
        for kv in steps(nv):
            iu, jv = lines(nu, ku), lines(nv, kv)
            if best is not None and len(iu) * len(jv) >= len(best[0]) * len(best[1]):
                continue
            u0, u1, wu = interp(iu, nu)
            v0, v1, wv = interp(jv, nv)
            wu, wv = wu[None, :], wv[:, None]
            est = (g[np.ix_(v0, u0)] * (1 - wu) * (1 - wv) + g[np.ix_(v0, u1)] * wu * (1 - wv)
                   + g[np.ix_(v1, u1)] * wu * wv + g[np.ix_(v1, u0)] * (1 - wu) * wv)
            if np.abs(est - g).max() < AO_TOL:
                best = (iu, jv)
    return best if best is not None else (np.arange(nu + 1), np.arange(nv + 1))


# ----------------------------------------------------------------------------- driver
def bake(objs):
    """Write the 'bake' colour attribute on every mesh object in objs (in place; large quads may be split).
    Objects named walk_* (invisible walk surfaces) neither receive nor occlude."""
    t0 = time.time()
    hidden = [o for o in objs if o.name.startswith('walk')]
    objs = [o for o in objs if o.type == 'MESH' and o not in hidden and len(o.data.polygons)]
    for ob in objs:
        if ob.get('bid') in AGE:
            ob['weather'] = AGE[ob['bid']]
    orig, dense, world = {}, {}, []
    for ob in objs:
        m = _Mesh.read(ob.data)
        M = np.array(ob.matrix_world)
        d, patches, probe = _densify(m, M)
        orig[ob.name], dense[ob.name] = (m, M, list(ob.data.materials)), (d, patches, probe)
        w = _Mesh(d.co @ M[:3, :3].T + M[:3, 3], d.ls, d.lv, d.mi, d.sm, None)
        world.append(w)
    t1 = time.time()
    front, back = _bake_both_sides(world, objs + hidden)
    t2 = time.time()
    nv0 = nv1 = npatch = nmerge = 0
    for ob, aoF, aoB in zip(objs, front, back):
        m, M, mats = orig[ob.name]
        d, patches, probe = dense[ob.name]
        R3, T3 = M[:3, :3], M[:3, 3]
        cod = d.co @ R3.T + T3
        nd = d.normals(cod)
        # the open side of every original face (a patch as a whole); one-sided materials keep their front
        pmap = {p['f']: p for p in patches}
        cnt = np.ones(len(m.ls), np.int64)
        for p in patches:
            cnt[p['f']] = len(p['faces'])
        owner = np.repeat(np.arange(len(m.ls)), cnt)              # dense face -> original face
        owner = np.concatenate([owner] + [np.full(len(v), f) for f, v in probe.items()])
        sF = np.bincount(owner[d.lf], aoF[d.lv], len(m.ls))
        sB = np.bincount(owner[d.lf], aoB[d.lv], len(m.ls))
        fwd = sF >= sB
        front_only = np.array([_front_only(x.name) for x in mats] + [True])
        fwd |= front_only[np.minimum(m.mi, len(mats))]
        sign = np.where(fwd, 1.0, -1.0)
        ao = np.where(fwd[owner[d.lf]], aoF[d.lv], aoB[d.lv])
        # average the corners that coincide (same place, same facing): a face's corners were baked apart from
        # those of its neighbours, and the noise would show as steps along the seams
        ne = nd[d.lf] * sign[owner[d.lf]][:, None]
        key = np.hstack((np.round(cod[d.lv] / 0.02), np.round(ne * 3))).astype(np.int64)
        _, inv = np.unique(key, axis=0, return_inverse=True)
        inv = inv.ravel()
        ao = (np.bincount(inv, ao) / np.bincount(inv))[inv]
        # rain streaks, from the original faces with their open side
        com = m.co @ R3.T + T3
        n_eff = m.normals(com) * sign[:, None]
        dep, along = _streaks(m, com, n_eff)
        # assemble: faces as they were, each grid thinned to what its corners or a coarser grid reproduce
        aov = np.zeros(len(d.co))
        aov[d.lv] = ao                                            # (a node is shared only within its grid)
        for p in patches:
            nu, nv = p['grid']
            g = aov[p['v0']:p['v0'] + p['k']].reshape(nv + 1, nu + 1)
            if nu > 1 and nv > 1:                                 # soften the bake noise inside the grid
                inner = sum(g[1 + dj:nv + dj, 1 + di:nu + di] for dj in (-1, 0, 1) for di in (-1, 0, 1)) / 9
                g[1:nv, 1:nu] = 0.5 * g[1:nv, 1:nu] + 0.5 * inner
            p['ao'] = g.ravel()
            p['sub'] = _coarsest(g)
            p['merge'] = len(p['sub'][0]) == 2 and len(p['sub'][1]) == 2
        # a probed n-gon: one value, from the more open of its probes (a roof half under 백주년기념관's drum)
        flat = {f: np.percentile((aoF if fwd[f] else aoB)[v], 70) for f, v in probe.items()}
        co, ls, lv, mi, sm, uv, col = [m.co], [], [], [], [], [], []
        nl_, nv_ = 0, len(m.co)
        cnt_o = np.ones(len(m.ls), np.int64)
        dl = 0                                                    # running dense loop index
        for f in range(len(m.ls)):
            a, n = m.ls[f], m.lt[f]
            p = pmap.get(f)
            if p is None or p['merge']:
                ls.append([nl_])
                lv.append(m.lv[a:a + n])
                mi.append([m.mi[f]])
                sm.append([m.sm[f]])
                if m.uv is not None:
                    uv.append(m.uv[a:a + n])
                if f in flat:
                    r = np.full(n, flat[f])
                elif p is None:
                    r = ao[dl:dl + n]
                else:
                    nu, nv = p['grid']
                    r = p['ao'][[0, nu, p['k'] - 1, nv * (nu + 1)]]
                col.append(np.column_stack((r, dep[a:a + n], along[a:a + n], np.ones(n))))
                nl_ += n
            else:
                nu, nv = p['grid']                                # the coarser grid on a subset of the nodes
                iu, jv = p['sub']
                sel = (jv[:, None] * (nu + 1) + iu[None, :]).ravel()
                cu = len(iu)
                i, j = np.meshgrid(np.arange(cu - 1), np.arange(len(jv) - 1))
                i, j = i.ravel(), j.ravel()
                F = np.stack((j * cu + i, j * cu + i + 1, (j + 1) * cu + i + 1, (j + 1) * cu + i), 1)
                Ws = p['W'][sel]
                co.append(d.co[p['v0'] + sel])
                ls.append(nl_ + 4 * np.arange(len(F)))
                lv.append(F.ravel() + nv_)
                mi.append([m.mi[f]] * len(F))
                sm.append([False] * len(F))
                loc = F.ravel()
                if m.uv is not None:
                    uv.append((Ws @ m.uv[a:a + n])[loc])
                col.append(np.column_stack((p['ao'][sel][loc], (Ws @ dep[a:a + n])[loc], (Ws @ along[a:a + n])[loc],
                                            np.ones(F.size))))
                cnt_o[f] = len(F)
                nv_ += len(sel)
                nl_ += F.size
            dl += n if p is None else p['faces'].size
        out = _Mesh(np.vstack(co), np.concatenate(ls).astype(np.int64), np.concatenate(lv).astype(np.int64),
                    np.concatenate(mi), np.concatenate(sm).astype(bool), np.vstack(uv) if m.uv is not None else None)
        col = np.vstack(col)
        cow = out.co @ R3.T + T3
        h = cow[:, 2] - _ground(cow[:, 0], cow[:, 1])
        hl = h[out.lv]
        # the ground under a face that looks down, within reach and in the building's shade (the open side of
        # each output face is its original face's)
        nfo = out.normals(cow)
        own_o = np.repeat(np.arange(len(m.ls)), cnt_o)
        nz = nfo[out.lf, 2] * sign[own_o[out.lf]]
        down = np.clip(-nz, 0, 1) * (1 - np.clip(hl / AO_DIST, 0, 1) ** 2)
        col[:, 0] = np.minimum(col[:, 0], 1 - DOWN_W * down)
        # no finer than each channel needs: the GLB keeps them as 16-bit integers, which Draco packs losslessly, and
        # fewer distinct values pack smaller (occlusion in 1/64, the streak fields in 1/256)
        for c, q in enumerate(QUANT):
            col[:, c] = np.round(col[:, c] * q) / q
        leaf = np.array([_is_leaf(mats[i].name) if i < len(mats) else False for i in range(max(len(mats), 1))])
        if leaf.any():
            col[leaf[np.minimum(out.mi[out.lf], len(leaf) - 1)]] = 1.0
        old = ob.data
        ob.data = out.write(old.name, mats, col)
        bpy.data.meshes.remove(old)
        nv0 += len(m.co)
        npatch += len(patches)
        nmerge += sum(p['merge'] for p in patches)
        nv1 += len(out.co)
    print('bake: %d objects, vertices %d -> %d, %d large faces split (%d merged back), split %.1fs, Cycles %.1fs, '
          'assemble %.1fs' % (len(objs), nv0, nv1, npatch, nmerge, t1 - t0, t2 - t1, time.time() - t2))
