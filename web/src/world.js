// Loads the Blender-built GLBs, binds shared materials, merges static geometry into
// spatial chunks, and instances vegetation / props.
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { DRACOLoader } from 'three/addons/loaders/DRACOLoader.js';
import { mergeGeometries } from 'three/addons/utils/BufferGeometryUtils.js';
import { mulberry } from './terrain.js';

const draco = new DRACOLoader().setDecoderPath('draco/');
export const gltfLoader = new GLTFLoader().setDRACOLoader(draco);
export const loadGLB = (url) => new Promise((res, rej) => gltfLoader.load(url, res, undefined, rej));

// Our own GLBs carry material *names*; replace them with the shared library materials.
export function bindMaterials(root, lib, keepUnknown = false) {
  root.traverse((o) => {
    if (!o.isMesh) return;
    const mats = Array.isArray(o.material) ? o.material : [o.material];
    const out = mats.map((m) => (lib.defs[m.name] || !keepUnknown ? lib.get(m.name) : m));
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
    let g = o.geometry.clone();
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
    if (g.index) g = g.toNonIndexed();
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
    if (!merged) continue;
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
// A "kit" is a loaded GLB whose meshes become InstancedMesh parts sharing one transform list.
export class InstancedKit {
  constructor(gltfScene, lib, capacity, { shadows = true, colors = false } = {}) {
    this.parts = [];
    gltfScene.updateMatrixWorld(true);
    gltfScene.traverse((o) => {
      if (!o.isMesh) return;
      const g = o.geometry.clone();
      g.applyMatrix4(o.matrixWorld);
      const im = new THREE.InstancedMesh(g, o.material, capacity);
      im.count = 0;
      im.castShadow = shadows;
      im.receiveShadow = true;
      im.frustumCulled = false;
      this.parts.push(im);
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
  commit() {
    for (const p of this.parts) {
      p.count = this.count;
      p.instanceMatrix.needsUpdate = true;
      if (p.instanceColor) p.instanceColor.needsUpdate = true;
      p.computeBoundingSphere();
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
    this.items = [];             // {key, m4, pos, scale}
    const rnd = mulberry(42);
    const m4 = new THREE.Matrix4(), q = new THREE.Quaternion(), s = new THREE.Vector3(), p = new THREE.Vector3();
    const up = new THREE.Vector3(0, 1, 0);
    for (const [sp, x, y, sc, rot] of trees) {
      const v = rnd() < 0.5 ? 0 : 1;
      const key = `${sp}_${v}`;
      if (!kits[key]) continue;
      const h = groundAt(x, y);
      p.set(x, h - 0.05, -y);
      q.setFromAxisAngle(up, rot);
      s.setScalar(sc);
      m4.compose(p, q, s);
      this.items.push({ key, m4: m4.clone(), pos: p.clone(), scale: sc, sp });
    }
    // near meshes
    this.near = {};
    const counts = {};
    for (const it of this.items) counts[it.key] = (counts[it.key] || 0) + 1;
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

  _buildImpostors(renderer) {
    const size = 256;
    for (const key of Object.keys(this.near)) {
      const src = this.kits[key];
      const box = new THREE.Box3().setFromObject(src);
      const w = Math.max(box.max.x - box.min.x, box.max.z - box.min.z), h = box.max.y - box.min.y;
      const rt = new THREE.WebGLRenderTarget(size, size * 2, { samples: 4 });
      rt.texture.colorSpace = THREE.SRGBColorSpace;
      const sc = new THREE.Scene();
      const clone = src.clone(true);
      sc.add(clone);
      sc.add(new THREE.HemisphereLight(0xdfe8ff, 0x405030, 1.6));
      const dl = new THREE.DirectionalLight(0xffffff, 2.2);
      dl.position.set(3, 6, 4);
      sc.add(dl);
      const half = Math.max(w / 2, h / 4) * 1.02;
      const cam = new THREE.OrthographicCamera(-half, half, half * 4, 0, 0.1, 200);
      cam.position.set(0, box.min.y, 60);
      cam.lookAt(0, box.min.y, 0);
      cam.position.y = box.min.y;
      const prevTarget = renderer.getRenderTarget();
      const prevClear = renderer.getClearAlpha();
      const prevTM = renderer.toneMapping;
      renderer.toneMapping = THREE.NoToneMapping;
      renderer.setRenderTarget(rt);
      renderer.setClearColor(0x445533, 0);
      renderer.clear();
      renderer.render(sc, cam);
      // the crown seen from straight above, for a horizontal card (bird's-eye view)
      const hw = (w / 2) * 1.02;
      const rtTop = new THREE.WebGLRenderTarget(size, size, { samples: 4 });
      rtTop.texture.colorSpace = THREE.SRGBColorSpace;
      const camTop = new THREE.OrthographicCamera(-hw, hw, hw, -hw, 0.1, 400);
      camTop.up.set(0, 0, -1);
      camTop.position.set(0, box.max.y + 50, 0);
      camTop.lookAt(0, box.min.y, 0);
      renderer.setRenderTarget(rtTop);
      renderer.clear();
      renderer.render(sc, camTop);
      renderer.setRenderTarget(prevTarget);
      renderer.setClearAlpha(prevClear);
      renderer.toneMapping = prevTM;
      // two crossed quads
      const qw = half * 2, qh = half * 4;
      const g1 = new THREE.PlaneGeometry(qw, qh);
      g1.translate(0, qh / 2 + box.min.y, 0);
      const g2 = g1.clone();
      g2.rotateY(Math.PI / 2);
      const geo = mergeGeometries([g1, g2]);
      const mat = new THREE.MeshStandardMaterial({ map: rt.texture, alphaTest: 0.5, side: THREE.DoubleSide, roughness: 1 });
      mat.name = 'impostor_' + key;
      const im = new THREE.InstancedMesh(geo, mat, this.near[key].capacity);
      im.count = 0;
      im.castShadow = false;
      im.receiveShadow = true;
      im.frustumCulled = false;
      this.scene.add(im);
      const gTop = new THREE.PlaneGeometry(hw * 2, hw * 2);
      gTop.rotateX(-Math.PI / 2);
      gTop.translate(0, box.min.y + h * 0.72, 0);
      const matTop = new THREE.MeshStandardMaterial({ map: rtTop.texture, alphaTest: 0.5, side: THREE.DoubleSide, roughness: 1 });
      matTop.name = 'impostor_top_' + key;
      const top = new THREE.InstancedMesh(gTop, matTop, this.near[key].capacity);
      top.count = 0;
      top.castShadow = false;
      top.receiveShadow = true;
      top.frustumCulled = false;
      this.scene.add(top);
      this.impostors[key] = { im, rt, src, top, rtTop };
    }
  }

  rebuildImpostors(renderer) {
    for (const v of Object.values(this.impostors)) {
      v.im.parent.remove(v.im);
      v.top.parent.remove(v.top);
      v.rt.dispose();
      v.rtTop.dispose();
    }
    this._buildImpostors(renderer);
    this.lastUpdate.set(1e9, 0, 0);
  }

  update(camPos, force = false) {
    if (!force && camPos.distanceToSquared(this.lastUpdate) < 64) return;
    this.lastUpdate.copy(camPos);
    const nd2 = this.nearDist * this.nearDist;
    for (const k in this.near) this.near[k].count = 0;
    const ic = {};
    for (const k in this.impostors) ic[k] = 0;
    for (const it of this.items) {
      const d2 = (it.pos.x - camPos.x) ** 2 + (it.pos.z - camPos.z) ** 2;
      if (d2 < nd2) {
        const kit = this.near[it.key];
        kit.set(kit.count++, it.m4);
      } else {
        const imp = this.impostors[it.key];
        imp.top.setMatrixAt(ic[it.key], it.m4);
        imp.im.setMatrixAt(ic[it.key]++, it.m4);
      }
    }
    for (const k in this.near) this.near[k].commit();
    for (const k in this.impostors) {
      const { im, top } = this.impostors[k];
      im.count = top.count = ic[k];
      im.instanceMatrix.needsUpdate = true;
      top.instanceMatrix.needsUpdate = true;
    }
  }
}
