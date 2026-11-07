// Shared PBR material library, built from data/materials.json (same file Blender uses).
import * as THREE from 'three';
import { MOBILE, versioned } from './util.js';

const texLoader = new THREE.TextureLoader();
const cache = new Map();
const pending = new Set();
export const texturesReady = () => Promise.all([...pending]);

// Phones: the whole 2K texture set is ~1 GB of GPU memory with mipmaps -> upload smaller copies.
const MOBILE_MAX_TEX = 1024;

// downscale an image so its longest side is at most `max` (returns the image itself if it already fits)
export function shrinkImage(img, max) {
  const w = img && img.width, h = img && img.height;
  if (!w || !h || Math.max(w, h) <= max) return img;
  const s = max / Math.max(w, h);
  const c = document.createElement('canvas');
  c.width = Math.max(1, Math.round(w * s));
  c.height = Math.max(1, Math.round(h * s));
  const x = c.getContext('2d');
  x.imageSmoothingQuality = 'high';
  x.drawImage(img, 0, 0, c.width, c.height);
  return c;
}

// NOTE: flipY=false everywhere -> matches glTF UV convention (v=0 at the top of the image)
export function loadTex(url, { srgb = true, repeat = true, flipY = false, mobileMax = MOBILE_MAX_TEX } = {}) {
  const key = url + srgb + flipY;
  if (!cache.has(key)) {
    let done;
    const pr = new Promise((r) => (done = r));
    pending.add(pr);
    const t = texLoader.load(versioned(url), (tx) => {
      if (MOBILE) { tx.image = shrinkImage(tx.image, mobileMax); tx.needsUpdate = true; }
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
  spring: { short: '4월 · 벚꽃', grass: [0.17, 0.25, 0.075], date: "'97 4 15" },
  summer: { short: '5월 · 신록', grass: [0.13, 0.22, 0.06], date: "'97 5 21" },
  autumn: { short: '10월 · 은행잎', grass: [0.21, 0.2, 0.08], date: "'97 10 28" },
};
for (const s of Object.values(SEASONS)) s.label = `1997년 ${s.short}`;

// species -> available seasonal atlas suffixes
const LEAF_VARIANTS = {
  ginkgo: ['spring', 'autumn'], zelkova: ['spring', 'autumn'], cherry: ['spring', 'autumn'],
  maple: ['spring', 'autumn'], oak: ['spring', 'autumn'], pine: [], ivy: ['spring', 'autumn'], boxwood: [],
  azalea: ['summer'], azalea_red: [],
};

export function leafUrl(species, season, young = false) {
  const v = LEAF_VARIANTS[species] || [];
  // young trees (1997's lawn planting) still wear April's light, sparse leaves in May
  if (young && season === 'summer' && v.includes('spring')) return `assets/textures/leaf_${species}_spring.png`;
  // 철쭉 bloom red from late April through May; green leaves in October
  if (species === 'azalea_red') return season === 'autumn' ? `assets/textures/leaf_azalea_summer.png` : `assets/textures/leaf_azalea_red.png`;
  if (species === 'azalea') return season === 'spring' ? `assets/textures/leaf_azalea.png` : `assets/textures/leaf_azalea_summer.png`;
  if (v.includes(season)) return `assets/textures/leaf_${species}_${season}.png`;
  return `assets/textures/leaf_${species}.png`;
}

// ---------------------------------------------------------------------------- shader patches
// A material's shader edits stack (one no longer replaces another), and the program cache key names them all: by
// default three keys a program by onBeforeCompile's source text, which is the same for every material with one kind
// of patch whatever values it bakes in (the bark's foliage glow 0 and the leaves' 0.09 could share one program).
const PATCHES = new WeakMap();
export function patchShader(m, key, edit) {
  if (!PATCHES.has(m)) PATCHES.set(m, []);
  const list = PATCHES.get(m);
  list.push({ key, edit });
  m.onBeforeCompile = (sh) => { for (const p of list) p.edit(sh); };
  m.customProgramCacheKey = () => list.map((p) => p.key).join('|');
}

// replace the diffuse map read: `body` gets the texel in sampledDiffuseColor and applies it to diffuseColor
function patchMap(m, key, uniforms, decl, body) {
  patchShader(m, key, (sh) => {
    Object.assign(sh.uniforms, uniforms);
    sh.fragmentShader = sh.fragmentShader
      .replace('#include <common>', `#include <common>\n${decl}`)
      .replace('#include <map_fragment>', `vec4 sampledDiffuseColor = texture2D( map, vMapUv );${body}`);
  });
}

// ---------------------------------------------------------------------------- wind
// One clock for everything the wind stirs (leaves, branches, the banners' cloth, life.js): main.js sets it every frame.
export const windTime = { value: 0 };

// The static shadow map (shadows.js) is drawn once with nothing displaced (three's shadow pass does not run
// onBeforeCompile either), so a vertex the wind moved looks its shadow up where it rests: a leaf keeps its own light
// and shade instead of swaying in and out of its own shadow. `windW`: the world-space offset the vertex shader added.
export const restShadow = (vs) => vs.replace('#include <shadowmap_vertex>', `
  #ifdef USE_SHADOWMAP
    worldPosition.xyz -= windW;
  #endif
  #include <shadowmap_vertex>
  #ifdef USE_SHADOWMAP
    worldPosition.xyz += windW;
  #endif`);

// Wind in the instanced plants (trees, shrubs; their impostors are rendered from the plain meshes and stay still, as do
// the ivy and hedges merged into the buildings): the whole plant leans downwind by the square of the height above its
// foot (h^2/(h^2+60): trunks barely move, crown tips 10-20 cm), two slow sines whose phase runs downwind with the
// plant's position (a gust travels along the 백양로 ginkgo row, neighbours out of step), under a slow gust swell.
// Leaves (flutter: metres) also flutter on their own, shrubs hardly (smoothstep on the height).
function sway(m, flutter) {
  patchShader(m, `sway${flutter}`, (sh) => {
    sh.uniforms.uWindT = windTime;
    sh.vertexShader = restShadow(sh.vertexShader
      .replace('#include <common>', `#include <common>
        uniform float uWindT;
        vec3 windSway(vec3 o, vec3 r) {
          const vec2 dir = vec2(0.92, -0.38);                     // towards the east-north-east (three xz)
          float h = max(r.y, 0.0), t = uWindT;
          float along = dot(o.xz, dir);
          float ph = along * 0.2 + sin(o.x * 0.37 + o.z * 0.53) * 1.6;
          float gust = 0.7 + 0.3 * sin(t * 0.21 - along * 0.01);
          float bend = 0.22 * h * h / (h * h + 60.0) * gust;
          float s = 0.7 * sin(t * 1.1 - ph) + 0.3 * sin(t * 2.3 - ph * 1.7 + 1.3);   // downwind
          float c = 0.3 * sin(t * 1.7 - ph * 0.8 + 2.1);                            // across
          vec3 w = vec3(dir.x * s - dir.y * c, 0.0, dir.y * s + dir.x * c) * bend;
          ${flutter > 0 ? `float f = dot(r, vec3(1.7, 1.1, 2.3)) + ph;
          w += vec3(sin(t * 4.3 + f), 0.5 * sin(t * 3.7 + f * 1.3), sin(t * 5.1 + f * 0.8 + 1.0))
            * (${flutter.toFixed(3)} * smoothstep(0.3, 5.0, h) * gust);` : ''}
          return w;
        }`)
      .replace('#include <begin_vertex>', `#include <begin_vertex>
        vec3 windW = vec3(0.0);
        #ifdef USE_INSTANCING
        {
          mat3 im = mat3(instanceMatrix);                         // a turn about the vertical and a uniform scale
          windW = windSway(instanceMatrix[3].xyz, im * position);
          transformed += transpose(im) * windW / dot(im[0], im[0]);
        }
        #endif`));
  });
}

// Foliage: a touch of wrap lighting / translucency so canopies don't go black, and a dithered fade
// close to the camera so the third-person camera never looks through a wall of leaves or a trunk; the wind (sway).
function foliage(m, glow = 0.09, flutter = 0.03) {
  sway(m, flutter);
  patchShader(m, `foliage${glow}`, (sh) => {
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
  });
}

// Window glass (materials.json `rooms`): a room behind every pane, the sky over it by Fresnel. Blender gives window
// glass pane UVs (blender/common.py pane_uv): the whole part names a pane (a random number per window), the fraction
// runs across it, and v from 32 marks a hall behind tall glazing. Each pane takes a cell of the room atlas
// (tools/make_window_atlas.py: rows 0-2 rooms, row 3 halls), lit like a surface just behind the glass, or by its own
// light where the lights are on. The glass reflects the environment by Fresnel (ior 1.5, both faces of a pane: F0 ~
// 0.08), every pane tilted a hair so that neighbours mirror a different patch of sky. three ignores envMapIntensity
// with scene.environment, so the glass scales its own IBL radiance.
// a room pane's cell: dark rooms, blinds and pale green curtains (학생회관) more often; 8, 13, 15 have the lights on
const ROOM_CELLS = '0, 0, 1, 1, 2, 3, 4, 5, 6, 6, 7, 8, 9, 10, 11, 11';
function windowGlass(d) {
  const m = new THREE.MeshPhysicalMaterial({
    map: loadTex('assets/textures/' + d.rooms, { repeat: false }),
    roughness: d.rough ?? 0.05,
    metalness: 0,
    ior: 1.5,
  });
  // both faces of the pane reflect (F0 0.04 each); the back face's light crosses the tinted glass (학생회관's green)
  const t = new THREE.Color(...(d.tint || [0.66, 0.69, 0.69]));
  const tm = Math.max(t.r, t.g, t.b);
  m.specularColor.setRGB(1 + t.r / tm, 1 + t.g / tm, 1 + t.b / tm);
  const u = {
    uRoomTint: { value: t },                       // what the (dusty) glass lets through
    uRoomLit: { value: d.lit ?? 0.45 },            // a room with the lights on
    uGlassEnv: { value: d.env ?? 2.0 },            // the reflection, x scene.environmentIntensity
  };
  m.userData.rooms = u;                            // (to tune from the console)
  patchShader(m, 'rooms', (sh) => {
    Object.assign(sh.uniforms, u);
    sh.fragmentShader = sh.fragmentShader
      .replace('#include <common>', `#include <common>
        uniform vec3 uRoomTint;
        uniform float uRoomLit, uGlassEnv;
        const int ROOM_CELLS[16] = int[16](${ROOM_CELLS});
        uint paneMix(uint n) { n ^= n >> 16; n *= 0x7feb352du; n ^= n >> 15; n *= 0x846ca68bu; n ^= n >> 16; return n; }
        float paneHash(vec2 p, uint k) {
          uvec2 q = uvec2(ivec2(p) + 4096);
          return float(paneMix(q.x * 1973u + q.y * 9277u + k * 26699u) >> 8) / 16777216.0;
        }`)
      .replace('#include <map_fragment>', `
        vec2 paneUv = vec2(vMapUv.x, 1.0 - vMapUv.y);              // (glTF flips v)
        vec2 pane = floor(paneUv), fp = fract(paneUv);
        int cell = pane.y > 31.5 ? 12 + int(paneHash(pane, 1u) * 4.0) : ROOM_CELLS[int(paneHash(pane, 1u) * 16.0)];
        if (paneHash(pane, 2u) < 0.5) fp.x = 1.0 - fp.x;            // mirrored rooms: twice the variety
        vec2 cuv = (vec2(float(cell % 4), float(cell / 4)) + 0.02 + vec2(fp.x, 1.0 - fp.y) * 0.96) * 0.25;
        // gradients of the continuous uv: no mip seam where the fraction wraps between two panes of one face
        vec3 room = textureGrad(map, cuv, dFdx(paneUv) * 0.24, dFdy(paneUv) * 0.24).rgb;
        room *= uRoomTint * (0.75 + 0.5 * paneHash(pane, 3u));
        float glassF = 0.08 + 0.92 * pow(1.0 - saturate(abs(dot(normalize(vNormal), normalize(vViewPosition)))), 5.0);
        float roomOn = (cell == 8 || cell == 13 || cell == 15) ? 1.0 : 0.0;
        diffuseColor.rgb = room * (1.0 - roomOn) * (1.0 - glassF);
        vec3 roomGlow = room * roomOn * uRoomLit * (1.0 - glassF);
        vec3 paneTilt = (vec3(paneHash(pane, 4u), paneHash(pane, 5u), paneHash(pane, 6u)) - 0.5) * 0.05;`)
      .replace('#include <normal_fragment_maps>', `#include <normal_fragment_maps>
        normal = normalize(normal + mat3(viewMatrix) * paneTilt);`)
      .replace('#include <emissivemap_fragment>', `#include <emissivemap_fragment>
        totalEmissiveRadiance += roomGlow;`)
      .replace('#include <lights_fragment_maps>', `#include <lights_fragment_maps>
        // the HDRI's horizon is open haze; the campus's is trees and buildings: dim what the glass mirrors low
        vec3 glassR = (vec4(reflect(-geometryViewDir, geometryNormal), 0.0) * viewMatrix).xyz;
        radiance *= uGlassEnv * mix(0.35, 1.0, smoothstep(-0.05, 0.4, glassR.y));`);
  });
  return m;
}

export class MaterialLibrary {
  constructor(defs) {
    this.defs = defs;
    this.mats = new Map();
    this.instancedMats = new Map();
    this.leafMats = [];
    this.season = 'summer';
    this.uniforms = { uGrass: { value: new THREE.Color(...SEASONS.summer.grass) }, uWindT: windTime };
  }

  // three keeps one compiled-program slot per material. One drawn both by plain meshes and by InstancedMeshes (the
  // metal of a building's railings and of the instanced lamps, the parked and the moving cars' parts) has its program
  // looked up again at every switch between the two, many times a frame. Instanced kits (world.js) draw with their
  // own copy, kept in step with the original (the season's leaf textures).
  instanced(m) {
    if (this.mats.get(m.name) !== m) return m;          // not a library material (a prop's own)
    let v = this.instancedMats.get(m);
    if (!v) {
      v = m.clone();
      v.onBeforeCompile = m.onBeforeCompile;            // (clone() keeps neither)
      v.customProgramCacheKey = m.customProgramCacheKey;
      this.instancedMats.set(m, v);
      if (this.leafMats.includes(m)) this.leafMats.push(v);
    }
    return v;
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
      m.normalScale.set(d.nor ?? 0.9, d.nor ?? 0.9);
      if (d.recolor) {
        // grass: keep the texture's detail, but drive the hue from the seasonal colour
        patchMap(m, 'recolor', { uGrass: this.uniforms.uGrass }, 'uniform vec3 uGrass;', `
          float lum = dot(sampledDiffuseColor.rgb, vec3(0.299, 0.587, 0.114));
          diffuseColor.rgb = uGrass * (0.45 + 1.6 * lum);`);
      } else if (d.sat !== undefined) {
        // grey down a warm photo texture (e.g. the 1997 granite / concrete of 공학관, 중앙도서관, 백주년기념관)
        patchMap(m, 'sat', { uSat: { value: d.sat } }, 'uniform float uSat;', `
          float lumS = dot(sampledDiffuseColor.rgb, vec3(0.299, 0.587, 0.114));
          sampledDiffuseColor.rgb = mix(vec3(lumS), sampledDiffuseColor.rgb, uSat);
          diffuseColor *= sampledDiffuseColor;`);
      } else if (d.contrast !== undefined) {
        // tone a texture's detail down towards its own average colour (the 1997 roads' even asphalt)
        patchMap(m, 'contrast', { uContrast: { value: d.contrast } }, 'uniform float uContrast;', `
          sampledDiffuseColor.rgb = mix(texture2D( map, vMapUv, 9.0 ).rgb, sampledDiffuseColor.rgb, uContrast);
          diffuseColor *= sampledDiffuseColor;`);
      }
      if (name.startsWith('bark')) foliage(m, 0.0, 0);         // trunks and branches bend with the leaves, no flutter
    } else if (d.leaf) {
      const species = d.leaf;
      m = new THREE.MeshStandardMaterial({
        map: loadTex(leafUrl(species, this.season, !!d.young), { repeat: !!d.opaque }),
        alphaTest: d.opaque ? 0 : 0.42,
        transparent: false,
        side: THREE.DoubleSide,
        roughness: 0.82,
        vertexColors: true,
        color: new THREE.Color(...(d.tint || [1, 1, 1])),
      });
      m.userData.species = species;
      m.userData.opaque = !!d.opaque;
      m.userData.young = !!d.young;
      m.userData.tint = d.tint || [1, 1, 1];
      m.userData.tintAutumn = d.tintAutumn || m.userData.tint;
      foliage(m, 0.09, d.opaque ? 0 : 0.03);                  // (a clipped hedge's solid body does not flutter)
      this.leafMats.push(m);
    } else if (d.rooms) {
      m = windowGlass(d);
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

  setSeason(season) {
    this.season = season;
    this.uniforms.uGrass.value.setRGB(...SEASONS[season].grass);
    for (const m of this.leafMats) {
      const t = loadTex(leafUrl(m.userData.species, season, m.userData.young), { repeat: m.userData.opaque });
      m.map = t;
      m.color.setRGB(...(season === 'autumn' ? m.userData.tintAutumn : m.userData.tint));
      m.needsUpdate = true;
    }
  }
}
