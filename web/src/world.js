// Loads the Blender-built GLBs, binds shared materials, merges static geometry into
// spatial chunks, and instances vegetation / props.
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { DRACOLoader } from 'three/addons/loaders/DRACOLoader.js';
import { mergeGeometries } from 'three/addons/utils/BufferGeometryUtils.js';
import { mulberry, placeMatrix, countBy, versioned } from './util.js';
import { SHADOW_LAYER } from './shadows.js';

const draco = new DRACOLoader().setDecoderPath('draco/');
export const gltfLoader = new GLTFLoader().setDRACOLoader(draco);
export const loadGLB = (url) => new Promise((res, rej) => gltfLoader.load(versioned(url), res, undefined, rej));

// A building that keeps its own shade of a shared material (the GLB names only the shared one): 연희관's rubble is
// the warm red-brown of reference/연희관_정면_2023.jpg, the other stone halls' the greyer stone of 핀슨관 · 성암관
const OWN = [[/^lm_yeonhui/, { stone_rubble: 'stone_rubble_brown' }]];
const ownMats = (o) => OWN.find(([re]) => re.test(o.name) || re.test(o.parent?.name ?? ''))?.[1];

// Our own GLBs carry material *names*; replace them with the shared library materials.
export function bindMaterials(root, lib, keepUnknown = false) {
  root.traverse((o) => {
    if (!o.isMesh) return;
    const mats = Array.isArray(o.material) ? o.material : [o.material];
    const own = ownMats(o);                        // (the loaded materials are shared between meshes: rename nothing)
    const out = mats.map((m) => (own?.[m.name] ?? ((lib.defs[m.name] || !keepUnknown) ? m.name : null)))
      .map((n, i) => (n ? lib.get(n) : mats[i]));
    o.material = Array.isArray(o.material) ? out : out[0];
  });
}

// Merge every mesh under root into one mesh per (material, chunk).
export function mergeStatic(root, { chunk = 160, castShadow = true, receiveShadow = true, name = 'static' } = {}) {
  root.updateMatrixWorld(true);
  const buckets = new Map();
  const box = new THREE.Box3(), c = new THREE.Vector3();
  root.traverse((o) => {
    if (!o.isMesh) return;
    const g = o.geometry.clone();
    g.applyMatrix4(o.matrixWorld);
    for (const k of Object.keys(g.attributes)) {
      if (!['position', 'normal', 'uv', 'color'].includes(k)) g.deleteAttribute(k);
    }
    if (!g.attributes.uv) g.setAttribute('uv', new THREE.Float32BufferAttribute(new Float32Array(g.attributes.position.count * 2), 2));
    if (o.material.vertexColors) {
      if (!g.attributes.color) g.setAttribute('color', new THREE.Float32BufferAttribute(new Float32Array(g.attributes.position.count * 3).fill(1), 3));
      else if (g.attributes.color.itemSize === 4) {
        const c4 = g.attributes.color, c3 = new Float32Array(c4.count * 3);
        for (let i = 0; i < c4.count; i++) { c3[i * 3] = c4.getX(i); c3[i * 3 + 1] = c4.getY(i); c3[i * 3 + 2] = c4.getZ(i); }
        g.setAttribute('color', new THREE.Float32BufferAttribute(c3, 3));
      }
    } else if (g.attributes.color) g.deleteAttribute('color');
    // keep the index (mergeGeometries needs all or none indexed): the Blender meshes share ~1/3 of their corners,
    // so de-indexing would cost 1.5x the vertices on the GPU and in every pass
    if (!g.index) g.setIndex(Array.from({ length: g.attributes.position.count }, (_, i) => i));
    box.setFromBufferAttribute(g.attributes.position);
    box.getCenter(c);
    const key = o.material.name + '|' + Math.floor(c.x / chunk) + '|' + Math.floor(c.z / chunk);
    if (!buckets.has(key)) buckets.set(key, { mat: o.material, geos: [] });
    buckets.get(key).geos.push(g);
  });
  const group = new THREE.Group();
  group.name = name;
  for (const [key, { mat, geos }] of buckets) {
    const merged = mergeGeometries(geos, false);
    if (!merged) { console.warn('mergeStatic: could not merge', key); continue; }
    merged.computeBoundingSphere();
    const m = new THREE.Mesh(merged, mat);
    m.castShadow = castShadow && !mat.name.startsWith('glass');
    m.receiveShadow = receiveShadow;
    m.name = key;
    group.add(m);
  }
  return group;
}

// ---------------------------------------------------------------------------- instancing, culled per instance
// three frustum-culls an InstancedMesh as a whole, and a kit's placements lie all over the campus (every parked car,
// shrub, lamp, tree and far hill clump of a kind in one mesh per part): all of them were drawn every frame, the ones
// behind the camera too. A CulledSet keeps the full list of placements and writes only those in a widened view into
// the one buffer its meshes share; cullInstances() checks again once the camera has turned or moved past the margin.
// The cached sun shadows need every placement, in view or not: with shadow maps on, each mesh has a shadow twin that
// draws the full list in the shadow pass only (shadows.js SHADOW_LAYER), and the mesh itself casts none.
const MARGIN = THREE.MathUtils.degToRad(12);   // the view is widened by this much on every side,
const PAD = 1.5;                               // and every placement's bounds by this many metres
const SETS = [];
let shadowTwins = false;
export const useShadowTwins = (on) => { shadowTwins = on; };   // before the kits are made (main.js)

// an InstancedMesh whose instance buffers a CulledSet provides
export function instancedPart(geo, mat) {
  const im = new THREE.InstancedMesh(geo, mat, 1);
  im.receiveShadow = true;
  return im;
}

export class CulledSet {
  // meshes: InstancedMeshes drawing the same placements; sphere: their joint bounds in the placements' own frame;
  // tinted: those of them that take a colour per placement; shadows: they cast shadows
  constructor(meshes, capacity, sphere, { tinted = [], shadows = false } = {}) {
    Object.assign(this, { meshes, tinted, capacity, sphere });
    this.count = 0;
    this.all = new Float32Array(capacity * 16);            // every placement
    this.bounds = new Float32Array(capacity * 4);          // its bounding sphere in the world: x, y, z, r
    this.view = new THREE.InstancedBufferAttribute(new Float32Array(capacity * 16), 16).setUsage(THREE.DynamicDrawUsage);
    this.colors = this.viewColors = null;                  // per placement, once one is given
    this.idx = new Int32Array(capacity);                   // placements in view now, and at the last check
    this.prev = new Int32Array(capacity);
    this.shown = -1;
    this.dirty = true;
    for (const m of meshes) {
      m.instanceMatrix = this.view;
      m.count = 0;
      m.frustumCulled = false;
      m.castShadow = shadows && !shadowTwins;
    }
    this.twins = [];
    if (shadows && shadowTwins) {
      this.allAttr = new THREE.InstancedBufferAttribute(this.all, 16);
      this.twins = meshes.map((m) => {
        const t = new THREE.InstancedMesh(m.geometry, m.material, 1);
        t.instanceMatrix = this.allAttr;
        t.count = 0;
        t.frustumCulled = false;
        t.castShadow = true;
        t.layers.set(SHADOW_LAYER);
        return t;
      });
    }
    SETS.push(this);
  }

  // placement i (and the world bounds that follow from it)
  setAt(i, m) {
    const e = m.elements, a = this.all, o = i * 16;
    for (let k = 0; k < 16; k++) a[o + k] = e[k];
    const { x, y, z } = this.sphere.center, b = this.bounds, q = i * 4;
    b[q] = e[0] * x + e[4] * y + e[8] * z + e[12];
    b[q + 1] = e[1] * x + e[5] * y + e[9] * z + e[13];
    b[q + 2] = e[2] * x + e[6] * y + e[10] * z + e[14];
    const s2 = Math.max(e[0] * e[0] + e[1] * e[1] + e[2] * e[2], e[4] * e[4] + e[5] * e[5] + e[6] * e[6], e[8] * e[8] + e[9] * e[9] + e[10] * e[10]);
    b[q + 3] = this.sphere.radius * Math.sqrt(s2) + PAD;
  }

  // its colour on the tinted meshes (white until given, as three's setColorAt)
  colorAt(i, color) {
    if (!this.tinted.length) return;
    if (!this.colors) {
      this.colors = new Float32Array(this.capacity * 3).fill(1);
      this.viewColors = new THREE.InstancedBufferAttribute(new Float32Array(this.capacity * 3), 3).setUsage(THREE.DynamicDrawUsage);
      for (const m of this.tinted) m.instanceColor = this.viewColors;
    }
    color.toArray(this.colors, i * 3);
  }

  // the first n placements are the list now (drawn from the next cullInstances)
  commit(n) {
    this.count = n;
    this.dirty = true;
    if (!this.allAttr) return;
    this.allAttr.needsUpdate = true;
    for (const t of this.twins) t.count = n;
  }

  addTo(parent) {
    for (const m of this.meshes) parent.add(m);
    for (const t of this.twins) parent.add(t);
  }

  cull(frustum) {
    const P = frustum.planes, b = this.bounds, idx = this.idx, prev = this.prev;
    let k = 0, changed = this.dirty;
    for (let i = 0, q = 0; i < this.count; i++, q += 4) {
      const x = b[q], y = b[q + 1], z = b[q + 2], r = -b[q + 3];
      let p = 0;
      for (; p < 6; p++) { const n = P[p].normal; if (n.x * x + n.y * y + n.z * z + P[p].constant < r) break; }
      if (p < 6) continue;
      if (!changed && (k >= this.shown || prev[k] !== i)) changed = true;
      idx[k++] = i;
    }
    if (!changed && k === this.shown) return;
    this.dirty = false;
    this.shown = k;
    this.idx = prev; this.prev = idx;
    for (const m of this.meshes) { m.count = k; m.visible = k > 0; }
    if (!k) return;                // (an empty update range would upload the whole buffer)
    copyRows(this.all, this.view, idx, k, 16);
    if (this.colors) copyRows(this.colors, this.viewColors, idx, k, 3);
  }
}

// rows idx[0..k) of src into the first k rows of a buffer attribute, uploading just those
function copyRows(src, attr, idx, k, w) {
  const dst = attr.array;
  for (let j = 0; j < k; j++) { const s = idx[j] * w, d = j * w; for (let c = 0; c < w; c++) dst[d + c] = src[s + c]; }
  attr.clearUpdateRanges();
  attr.addUpdateRange(0, k * w);
  attr.needsUpdate = true;
}

const _cullCam = new THREE.PerspectiveCamera(), _frustum = new THREE.Frustum(), _pv = new THREE.Matrix4();
const _at = new THREE.Vector3(1e9, 0, 0), _look = new THREE.Vector3(), _dir = new THREE.Vector3();
let _fov = 0, _aspect = 0;
// once a frame, after the camera is placed: every set again once the camera has turned or moved past the margins,
// otherwise only the sets whose lists changed
export function cullInstances(camera) {
  camera.updateMatrixWorld();
  camera.getWorldDirection(_dir);
  const moved = camera.position.distanceToSquared(_at) > (PAD * 0.8) ** 2 || _dir.dot(_look) < Math.cos(MARGIN * 0.7)
    || camera.fov !== _fov || camera.aspect !== _aspect;
  if (moved) {
    _at.copy(camera.position); _look.copy(_dir); _fov = camera.fov; _aspect = camera.aspect;
    const v = THREE.MathUtils.degToRad(camera.fov) / 2, h = Math.atan(Math.tan(v) * camera.aspect);
    const v2 = Math.min(v + MARGIN, 1.5), h2 = Math.min(h + MARGIN, 1.5);
    Object.assign(_cullCam, { fov: THREE.MathUtils.radToDeg(v2 * 2), aspect: Math.tan(h2) / Math.tan(v2), near: camera.near, far: camera.far });
    _cullCam.updateProjectionMatrix();
    _frustum.setFromProjectionMatrix(_pv.multiplyMatrices(_cullCam.projectionMatrix, camera.matrixWorldInverse));
  }
  for (const s of SETS) if (moved || s.dirty) s.cull(_frustum);
}

// A "kit" is a loaded GLB whose meshes become InstancedMesh parts sharing one list of placements.
export class InstancedKit {
  constructor(gltfScene, lib, capacity, { shadows = true, colors = false } = {}) {
    this.parts = [];
    const box = new THREE.Box3();
    gltfScene.updateMatrixWorld(true);
    gltfScene.traverse((o) => {
      if (!o.isMesh) return;
      const g = o.geometry.clone();
      g.applyMatrix4(o.matrixWorld);
      g.computeBoundingBox();
      box.union(g.boundingBox);
      this.parts.push(instancedPart(g, lib.instanced(o.material)));
    });
    // a car's paint takes the car's colour (colors); cloth whatever colour a placement brings (motorbike covers)
    const tinted = this.parts.filter((p) => (colors && p.material.name === 'car_paint') || p.material.name === 'cloth');
    this.inst = new CulledSet(this.parts, capacity, box.getBoundingSphere(new THREE.Sphere()), { tinted, shadows });
    this.capacity = capacity;
    this.count = 0;
  }
  add(matrix, color) {
    if (this.count >= this.capacity) return -1;
    this.inst.setAt(this.count, matrix);
    if (color) this.inst.colorAt(this.count, color);
    return this.count++;
  }
  commit() { this.inst.commit(this.count); }
  addTo(parent) { this.inst.addTo(parent); }
}

// ---------------------------------------------------------------------------- vegetation with impostor LOD
export class Forest {
  constructor(scene, renderer, lib, kits, trees, groundAt) {
    this.scene = scene;
    this.kits = kits;            // {species_variant: gltf.scene}
    this.lib = lib;
    this.items = [];             // {key, m4, x, z}: instance matrix and ground position (three XZ)
    const rnd = mulberry(42);
    for (const [sp, x, y, sc, rot] of trees) {
      const v = rnd() < 0.5 ? 0 : 1;
      const key = `${sp}_${v}`;
      if (!kits[key]) continue;
      const m4 = placeMatrix(new THREE.Matrix4(), x, groundAt(x, y) - 0.05, y, rot, sc);
      this.items.push({ key, m4, x, z: -y });
    }
    // near meshes
    this.near = {};
    const counts = countBy(this.items, (it) => it.key);
    for (const key of Object.keys(kits)) {
      if (!counts[key]) continue;
      const kit = new InstancedKit(kits[key], lib, counts[key]);
      kit.addTo(scene);
      this.near[key] = kit;
    }
    // impostors (billboard crosses rendered at runtime from the real tree models)
    this.impostors = {};
    this._buildImpostors(renderer);
    this.lastUpdate = new THREE.Vector3(1e9, 0, 0);
    this.nearDist = 230;
  }

  // Impostor cards: two crossed quads (side view) and a horizontal one (seen from above, for the bird's-eye view),
  // textured with renders of the real tree model.
  _buildImpostors(renderer) {
    const size = 256;
    for (const key of Object.keys(this.near)) {
      const src = this.kits[key];
      const box = new THREE.Box3().setFromObject(src);
      const w = Math.max(box.max.x - box.min.x, box.max.z - box.min.z), h = box.max.y - box.min.y;
      const half = Math.max(w / 2, h / 4) * 1.02, hw = (w / 2) * 1.02;
      const rt = new THREE.WebGLRenderTarget(size, size * 2, { samples: 4 });
      const rtTop = new THREE.WebGLRenderTarget(size, size, { samples: 4 });
      rt.texture.colorSpace = rtTop.texture.colorSpace = THREE.SRGBColorSpace;
      const cam = new THREE.OrthographicCamera(-half, half, half * 4, 0, 0.1, 200);
      cam.position.set(0, box.min.y, 60);
      cam.lookAt(0, box.min.y, 0);
      const camTop = new THREE.OrthographicCamera(-hw, hw, hw, -hw, 0.1, 400);
      camTop.up.set(0, 0, -1);
      camTop.position.set(0, box.max.y + 50, 0);
      camTop.lookAt(0, box.min.y, 0);
      const card = (geo, rtx, name) => {
        const mat = new THREE.MeshStandardMaterial({ map: rtx.texture, alphaTest: 0.5, side: THREE.DoubleSide, roughness: 1 });
        mat.name = name + key;
        geo.computeBoundingBox();
        return instancedPart(geo, mat);
      };
      // two crossed quads
      const qw = half * 2, qh = half * 4;
      const g1 = new THREE.PlaneGeometry(qw, qh);
      g1.translate(0, qh / 2 + box.min.y, 0);
      const g2 = g1.clone();
      g2.rotateY(Math.PI / 2);
      const im = card(mergeGeometries([g1, g2]), rt, 'impostor_');
      const gTop = new THREE.PlaneGeometry(hw * 2, hw * 2);
      gTop.rotateX(-Math.PI / 2);
      gTop.translate(0, box.min.y + h * 0.72, 0);
      const top = card(gTop, rtTop, 'impostor_top_');
      const bounds = im.geometry.boundingBox.clone().union(top.geometry.boundingBox).getBoundingSphere(new THREE.Sphere());
      const set = new CulledSet([im, top], this.near[key].capacity, bounds);   // (no shadows: the far trees cast none)
      set.addTo(this.scene);
      this.impostors[key] = { set, rt, rtTop, src, cam, camTop };
    }
    this.renderImpostors(renderer);
  }

  // (re)draw the impostor textures from the tree models, e.g. after a season change swapped the leaf textures
  renderImpostors(renderer) {
    const sc = new THREE.Scene();
    sc.add(new THREE.HemisphereLight(0xdfe8ff, 0x405030, 1.6));
    const dl = new THREE.DirectionalLight(0xffffff, 2.2);
    dl.position.set(3, 6, 4);
    sc.add(dl);
    const prevTarget = renderer.getRenderTarget();
    const prevClear = renderer.getClearColor(new THREE.Color()), prevAlpha = renderer.getClearAlpha();
    const prevTM = renderer.toneMapping;
    renderer.toneMapping = THREE.NoToneMapping;
    renderer.setClearColor(0x445533, 0);
    for (const { src, rt, rtTop, cam, camTop } of Object.values(this.impostors)) {
      const clone = src.clone(true);
      sc.add(clone);
      for (const [target, c] of [[rt, cam], [rtTop, camTop]]) {
        renderer.setRenderTarget(target);
        renderer.clear();
        renderer.render(sc, c);
      }
      sc.remove(clone);
    }
    renderer.setRenderTarget(prevTarget);
    renderer.setClearColor(prevClear, prevAlpha);
    renderer.toneMapping = prevTM;
  }

  update(camPos, force = false) {
    if (!force && camPos.distanceToSquared(this.lastUpdate) < 64) return;
    this.lastUpdate.copy(camPos);
    const nd2 = this.nearDist * this.nearDist;
    for (const k in this.near) this.near[k].count = 0;
    const ic = {};
    for (const k in this.impostors) ic[k] = 0;
    for (const it of this.items) {
      const d2 = (it.x - camPos.x) ** 2 + (it.z - camPos.z) ** 2;
      if (d2 < nd2) this.near[it.key].add(it.m4);
      else this.impostors[it.key].set.setAt(ic[it.key]++, it.m4);
    }
    for (const k in this.near) this.near[k].commit();
    for (const k in this.impostors) this.impostors[k].set.commit(ic[k]);
  }
}
