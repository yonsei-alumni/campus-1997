// Loads the Blender-built GLBs, binds shared materials, merges static geometry into
// spatial chunks, and instances vegetation / props.
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { DRACOLoader } from 'three/addons/loaders/DRACOLoader.js';
import { mergeGeometries } from 'three/addons/utils/BufferGeometryUtils.js';
import { mulberry, placeMatrix, countBy, versioned } from './util.js';

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

// ---------------------------------------------------------------------------- instancing
function instanced(geo, mat, capacity, castShadow) {
  const im = new THREE.InstancedMesh(geo, mat, capacity);
  im.count = 0;
  im.castShadow = castShadow;
  im.receiveShadow = true;
  im.frustumCulled = false;
  return im;
}

// A "kit" is a loaded GLB whose meshes become InstancedMesh parts sharing one transform list.
export class InstancedKit {
  constructor(gltfScene, lib, capacity, { shadows = true, colors = false } = {}) {
    this.parts = [];
    gltfScene.updateMatrixWorld(true);
    gltfScene.traverse((o) => {
      if (!o.isMesh) return;
      const g = o.geometry.clone();
      g.applyMatrix4(o.matrixWorld);
      this.parts.push(instanced(g, lib.instanced(o.material), capacity, shadows));
    });
    this.capacity = capacity;
    this.count = 0;
    this.colors = colors;
  }
  add(matrix, color) {
    if (this.count >= this.capacity) return -1;
    for (const p of this.parts) {
      p.setMatrixAt(this.count, matrix);
      if (color && ((this.colors && p.material.name === 'car_paint') || p.material.name === 'cloth')) p.setColorAt(this.count, color);
    }
    return this.count++;
  }
  set(i, matrix) {
    for (const p of this.parts) p.setMatrixAt(i, matrix);
  }
  // bounds: only for kits placed once (the forest re-commits as you walk; its parts are never frustum culled)
  commit(bounds = true) {
    for (const p of this.parts) {
      p.count = this.count;
      p.instanceMatrix.needsUpdate = true;
      if (p.instanceColor) p.instanceColor.needsUpdate = true;
      if (bounds) p.computeBoundingSphere();
    }
  }
  addTo(parent) {
    for (const p of this.parts) parent.add(p);
  }
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
        const im = instanced(geo, mat, this.near[key].capacity, false);
        this.scene.add(im);
        return im;
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
      this.impostors[key] = { im, top, rt, rtTop, src, cam, camTop };
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
      if (d2 < nd2) {
        const kit = this.near[it.key];
        kit.set(kit.count++, it.m4);
      } else {
        const imp = this.impostors[it.key];
        imp.top.setMatrixAt(ic[it.key], it.m4);
        imp.im.setMatrixAt(ic[it.key]++, it.m4);
      }
    }
    for (const k in this.near) this.near[k].commit(false);
    for (const k in this.impostors) {
      const { im, top } = this.impostors[k];
      im.count = top.count = ic[k];
      im.instanceMatrix.needsUpdate = true;
      top.instanceMatrix.needsUpdate = true;
    }
  }
}
