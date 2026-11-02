// Shared PBR material library, built from data/materials.json (same file Blender uses).
import * as THREE from 'three';

const texLoader = new THREE.TextureLoader();
const cache = new Map();
const pending = new Set();
export const texturesReady = () => Promise.all([...pending]);

// NOTE: flipY=false everywhere -> matches glTF UV convention (v=0 at the top of the image)
export function loadTex(url, { srgb = true, repeat = true, flipY = false } = {}) {
  const key = url + srgb + flipY;
  if (!cache.has(key)) {
    let done;
    const pr = new Promise((r) => (done = r));
    pending.add(pr);
    const t = texLoader.load(url, (tx) => {
      // clones share the image Source but keep their own version -> bump them once data exists
      for (const c of tx.userData.clones || []) c.needsUpdate = true;
      pending.delete(pr); done();
    }, undefined, () => { pending.delete(pr); done(); });
    t.userData.clones = [];
    t.flipY = flipY;
    t.colorSpace = srgb ? THREE.SRGBColorSpace : THREE.NoColorSpace;
    if (repeat) t.wrapS = t.wrapT = THREE.RepeatWrapping;
    t.anisotropy = 8;
    cache.set(key, t);
  }
  return cache.get(key);
}

function tiled(url, tile, srgb) {
  const base = loadTex(url, { srgb });
  const t = base.clone();                         // shares the image Source
  t.repeat.set(1 / tile, 1 / tile);
  if (base.image && base.image.complete !== false && base.image.width) t.needsUpdate = true;
  else base.userData.clones.push(t);
  return t;
}

export const SEASONS = {
  spring: { label: '1997년 4월 · 벚꽃', grass: [0.17, 0.25, 0.075], date: "'97 4 15" },
  summer: { label: '1997년 5월 · 신록', grass: [0.13, 0.22, 0.06], date: "'97 5 21" },
  autumn: { label: '1997년 10월 · 은행잎', grass: [0.21, 0.2, 0.08], date: "'97 10 28" },
};

// species -> available seasonal atlas suffixes
const LEAF_VARIANTS = {
  ginkgo: ['spring', 'autumn'], zelkova: ['spring', 'autumn'], cherry: ['spring', 'autumn'],
  maple: ['spring', 'autumn'], oak: ['spring', 'autumn'], pine: [], ivy: ['autumn'], boxwood: [],
  azalea: ['summer'], azalea_red: [],
};

export function leafUrl(species, season) {
  const v = LEAF_VARIANTS[species] || [];
  // 철쭉 bloom red from late April through May; green leaves in October
  if (species === 'azalea_red') return season === 'autumn' ? `assets/textures/leaf_azalea_summer.png` : `assets/textures/leaf_azalea_red.png`;
  if (species === 'azalea') return season === 'spring' ? `assets/textures/leaf_azalea.png` : `assets/textures/leaf_azalea_summer.png`;
  if (v.includes(season)) return `assets/textures/leaf_${species}_${season}.png`;
  return `assets/textures/leaf_${species}.png`;
}

export class MaterialLibrary {
  constructor(defs, envIntensity = 1) {
    this.defs = defs;
    this.mats = new Map();
    this.leafMats = [];
    this.recolorMats = [];
    this.season = 'summer';
    this.uniforms = { uGrass: { value: new THREE.Color(...SEASONS.summer.grass) } };
  }

  get(name) {
    if (this.mats.has(name)) return this.mats.get(name);
    const d = this.defs[name];
    let m;
    if (!d) {
      m = new THREE.MeshStandardMaterial({ color: 0xff00ff });
      console.warn('unknown material', name);
    } else if (d.tex) {
      const base = `assets/textures/pbr/${d.tex}/`;
      m = new THREE.MeshStandardMaterial({
        map: tiled(base + 'diff.jpg', d.tile, true),
        normalMap: tiled(base + 'nor.jpg', d.tile, false),
        roughnessMap: tiled(base + 'rough.jpg', d.tile, false),
        roughness: 1.0,
        color: new THREE.Color(...(d.tint || [1, 1, 1])),
        side: THREE.DoubleSide,
      });
      m.normalScale.set(0.9, 0.9);
      if (d.recolor) this._recolor(m);
      else if (d.sat !== undefined) this._desaturate(m, d.sat);
      if (name.startsWith('bark')) this._foliage(m, 0.0);
    } else if (d.leaf) {
      const species = d.leaf;
      m = new THREE.MeshStandardMaterial({
        map: loadTex(leafUrl(species, this.season), { repeat: !!d.opaque }),
        alphaTest: d.opaque ? 0 : 0.42,
        transparent: false,
        side: THREE.DoubleSide,
        roughness: 0.82,
        vertexColors: true,
      });
      m.userData.species = species;
      m.userData.opaque = !!d.opaque;
      this._foliage(m);
      this.leafMats.push(m);
    } else if (d.image) {
      m = new THREE.MeshStandardMaterial({ map: loadTex('assets/textures/' + d.image, { repeat: false }), roughness: d.rough ?? 0.6 });
      if (d.emissiveMap) {
        m.emissiveMap = m.map;
        m.emissive = new THREE.Color(0.35, 0.35, 0.35);
      }
    } else {
      const P = d.clearcoat ? THREE.MeshPhysicalMaterial : THREE.MeshStandardMaterial;
      m = new P({
        color: new THREE.Color(...(d.color || [0.8, 0.8, 0.8])),
        roughness: d.rough ?? 0.8,
        metalness: d.metal ?? 0,
        side: d.side === 'double' ? THREE.DoubleSide : THREE.FrontSide,
      });
      if (d.clearcoat) { m.clearcoat = d.clearcoat; m.clearcoatRoughness = d.clearcoatRough ?? 0.08; }
      if (d.opacity !== undefined) { m.transparent = true; m.opacity = d.opacity; m.depthWrite = false; }
      if (d.emissive) {
        m.emissive = new THREE.Color(...d.emissive);
        m.emissiveIntensity = d.emissiveIntensity ?? 1;
      }
      if (name.startsWith('glass')) {
        m.metalness = 0.35;
        m.envMapIntensity = d.env ?? 1.5;
      }
    }
    m.name = name;
    this.mats.set(name, m);
    return m;
  }

  // Grass: keep the texture's detail, but drive the hue from a seasonal colour.
  // grey down a warm photo texture (e.g. the 1997 granite / concrete of 공학관, 중앙도서관, 백주년기념관)
  _desaturate(m, sat) {
    m.userData.uSat = { value: sat };
    m.onBeforeCompile = (sh) => {
      sh.uniforms.uSat = m.userData.uSat;
      sh.fragmentShader = sh.fragmentShader
        .replace('#include <common>', '#include <common>\nuniform float uSat;')
        .replace('#include <map_fragment>', `
          vec4 sampledDiffuseColor = texture2D( map, vMapUv );
          float lumS = dot(sampledDiffuseColor.rgb, vec3(0.299, 0.587, 0.114));
          sampledDiffuseColor.rgb = mix(vec3(lumS), sampledDiffuseColor.rgb, uSat);
          diffuseColor *= sampledDiffuseColor;
        `);
    };
  }

  _recolor(m) {
    m.onBeforeCompile = (sh) => {
      sh.uniforms.uGrass = this.uniforms.uGrass;
      sh.fragmentShader = sh.fragmentShader
        .replace('#include <common>', '#include <common>\nuniform vec3 uGrass;')
        .replace('#include <map_fragment>', `
          vec4 sampledDiffuseColor = texture2D( map, vMapUv );
          float lum = dot(sampledDiffuseColor.rgb, vec3(0.299, 0.587, 0.114));
          diffuseColor.rgb = uGrass * (0.45 + 1.6 * lum);
        `);
    };
    this.recolorMats.push(m);
  }

  // Foliage: a touch of wrap lighting / translucency so canopies don't go black, and a dithered fade
  // close to the camera so the third-person camera never looks through a wall of leaves or a trunk.
  _foliage(m, glow = 0.09) {
    m.onBeforeCompile = (sh) => {
      sh.fragmentShader = sh.fragmentShader
        .replace('#include <clipping_planes_fragment>', `#include <clipping_planes_fragment>
          {
            float camD = length(vViewPosition);
            float keep = smoothstep(1.2, 3.4, camD);
            vec2 q = floor(gl_FragCoord.xy);
            float dither = fract(dot(q, vec2(0.0671, 0.00584)) * 52.98);
            if (keep < 0.999 && dither > keep) discard;
          }`)
        .replace('#include <emissivemap_fragment>', `#include <emissivemap_fragment>
         totalEmissiveRadiance += diffuseColor.rgb * ${glow.toFixed(3)};`);
    };
  }

  setSeason(season) {
    this.season = season;
    this.uniforms.uGrass.value.setRGB(...SEASONS[season].grass);
    for (const m of this.leafMats) {
      const t = loadTex(leafUrl(m.userData.species, season), { repeat: m.userData.opaque });
      m.map = t;
      m.needsUpdate = true;
    }
  }
}
