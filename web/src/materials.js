// Shared PBR material library, built from data/materials.json (same file Blender uses).
import * as THREE from 'three';
import { MOBILE, versioned, mulberry } from './util.js';
import { FALL, LITTER_MATS, litterUniforms, litterEdit } from './litter.js';

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
  if (list.some((p) => p.key === key)) return;        // once per material (an instanced copy shares its original's list)
  list.push({ key, edit });
  m.onBeforeCompile = (sh) => { for (const p of list) p.edit(sh); };
  m.customProgramCacheKey = () => list.map((p) => p.key).join('|');
}

// the same, for a material that may carry a hand-written onBeforeCompile (terrain's, people's): that one becomes the
// first edit of the stack instead of being replaced
export function patchShaderOwn(m, key, edit) {
  if (!PATCHES.has(m) && Object.hasOwn(m, 'onBeforeCompile')) patchShader(m, m.customProgramCacheKey(), m.onBeforeCompile);
  patchShader(m, key, edit);
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
    Object.assign(this.uniforms, litterUniforms(loadTex));     // the month's fallen leaves (litter.js)
  }

  // three keeps one compiled-program slot per material. One drawn both by plain meshes and by InstancedMeshes (the
  // metal of a building's railings and of the instanced lamps, the parked and the moving cars' parts) has its program
  // looked up again at every switch between the two, many times a frame. Instanced kits (world.js) draw with their
  // own copy, kept in step with the original (the season's leaf textures).
  instanced(m) {
    if (this.mats.get(m.name) !== m) return pcss(m);    // not a library material (a prop's own)
    let v = this.instancedMats.get(m);
    if (!v) {
      v = m.clone();
      v.onBeforeCompile = m.onBeforeCompile;            // (clone() keeps neither)
      v.customProgramCacheKey = m.customProgramCacheKey;
      // the copy shares the original's patch list: a patch added to either later (the baked sun shadow's, from
      // main.js) lands once in the shared list instead of once there and once more on the copy
      if (PATCHES.has(m)) PATCHES.set(v, PATCHES.get(m));
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
      if (LITTER_MATS.has(name)) patchShader(m, 'litter', litterEdit(this.uniforms));
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
    pcss(m);
    m.name = name;
    globalPatch(m);
    this.mats.set(name, m);
    return m;
  }

  setSeason(season) {
    this.season = season;
    this.uniforms.uGrass.value.setRGB(...SEASONS[season].grass);
    this.uniforms.uFall.value.fromArray(FALL[season]);
    for (const m of this.leafMats) {
      const t = loadTex(leafUrl(m.userData.species, season, m.userData.young), { repeat: m.userData.opaque });
      m.map = t;
      m.color.setRGB(...(season === 'autumn' ? m.userData.tintAutumn : m.userData.tint));
      m.needsUpdate = true;
    }
  }
}

// ---------------------------------------------------------------------------- contact-hardening sun shadows (PCSS)
// The sun is a disc 0.53° across, so a shadow's penumbra widens with the gap between what casts it and what it falls
// on: sharp at a walker's feet and the foot of a trunk, softer under a high canopy or off a roof edge. three's
// webgl_shadowmap_pcss example (blocker search -> penumbra estimate -> filter of that radius), for the sun's
// orthographic shadow camera: map depth is linear, so the penumbra radius is just the blocker-receiver gap along the
// light times tan(0.265°). Taps compare against the receiver's own plane (slope from screen derivatives), so the
// search disc, wider than the old PCF kernel, does not find the ground itself on sloped and grazing-lit faces; the
// filter's taps are bilinear so the penumbra stays smooth without noise. Desktop HQ only (updatePcss, from main.js);
// the static shadow cache (shadows.js) keeps the same depth map, so it works unchanged.
export const PCSS = {
  sunDeg: 0.53,       // the sun's angular diameter
  reach: 45,          // farthest blocker considered, metres along the light (the tallest halls and trees, sun at ~48°)
  minTexels: 0.5,     // smallest filter radius: below this the map's texels would show as steps
  uniform: { value: new THREE.Vector4() },  // x: radius (uv) per unit of map depth (0: off), y: search radius (uv),
};                                          // z: smallest radius (uv), w: largest |d depth / d uv| of a receiver plane

const vogel = (n) => Array.from({ length: n }, (_, i) => {
  const r = Math.sqrt((i + 0.5) / n), a = i * 2.39996323;
  return `vec2(${(r * Math.cos(a)).toFixed(4)}, ${(r * Math.sin(a)).toFixed(4)})`;
}).join(', ');

// Fetches per pixel: 4 + PCSS_RING to find the blockers (the old PCFSoft kernel read 16), and only in a penumbra
// 4 * PCSS_TAPS more for the filter (its centre tap reuses the search's four texels).
const PCSS_RING = 8, PCSS_TAPS = 6;
const PCSS_CHUNK = THREE.ShaderChunk.shadowmap_pars_fragment.replace('float getShadow(', 'float getShadowPCF(') + /* glsl */`
#ifdef USE_SHADOWMAP
  uniform vec4 uPcss;
  const vec2 PCSS_RING[ ${PCSS_RING} ] = vec2[]( ${vogel(PCSS_RING)} );
  const vec2 PCSS_TAPS[ ${PCSS_TAPS} ] = vec2[]( ${vogel(PCSS_TAPS)} );
  // depth test of one point, bilinear over the four texels round it
  float pcssTap( sampler2D map, vec2 size, vec2 uv, float z ) {
    vec2 t = uv * size - 0.5, f = fract( t ), e = 1.0 / size, b = ( floor( t ) + 0.5 ) * e;
    vec4 s = step( vec4( z ), vec4(
      unpackRGBAToDepth( texture2D( map, b ) ), unpackRGBAToDepth( texture2D( map, b + vec2( e.x, 0.0 ) ) ),
      unpackRGBAToDepth( texture2D( map, b + vec2( 0.0, e.y ) ) ), unpackRGBAToDepth( texture2D( map, b + e ) ) ) );
    return mix( mix( s.x, s.y, f.x ), mix( s.z, s.w, f.x ), f.y );
  }
  float getShadow( sampler2D shadowMap, vec2 shadowMapSize, float shadowIntensity, float shadowBias, float shadowRadius,
    vec4 shadowCoord ) {
    if ( uPcss.x <= 0.0 ) {
      return getShadowPCF( shadowMap, shadowMapSize, shadowIntensity, shadowBias, shadowRadius, shadowCoord );
    }
    vec3 c = shadowCoord.xyz / shadowCoord.w;
    c.z += shadowBias;
    // the receiver's plane in the map: depth change per uv (clamped for grazing faces and leaf cards seen edge-on)
    vec3 cx = dFdx( c ), cy = dFdy( c );
    float det = cx.x * cy.y - cx.y * cy.x;
    vec2 dz = abs( det ) > 1e-14 ? vec2( cy.y * cx.z - cx.y * cy.z, cx.x * cy.z - cy.x * cx.z ) / det : vec2( 0.0 );
    dz = clamp( dz, - uPcss.w, uPcss.w );
    if ( c.x < 0.0 || c.x > 1.0 || c.y < 0.0 || c.y > 1.0 || c.z > 1.0 ) return 1.0;
    // 1. blockers: the mean depth of what is nearer the sun, in the four texels round the point (so thin casters, a
    // pole or a leg, are never stepped over) and on a ring out to the widest penumbra
    vec2 t = c.xy * shadowMapSize - 0.5, f = fract( t ), e = 1.0 / shadowMapSize, b = ( floor( t ) + 0.5 ) * e;
    vec4 d4 = vec4(
      unpackRGBAToDepth( texture2D( shadowMap, b ) ), unpackRGBAToDepth( texture2D( shadowMap, b + vec2( e.x, 0.0 ) ) ),
      unpackRGBAToDepth( texture2D( shadowMap, b + vec2( 0.0, e.y ) ) ), unpackRGBAToDepth( texture2D( shadowMap, b + e ) ) );
    vec4 blk = vec4( lessThan( d4, vec4( c.z ) ) );
    float sum = dot( blk, d4 ), n = dot( blk, vec4( 1.0 ) );
    for ( int i = 0; i < ${PCSS_RING}; i ++ ) {
      vec2 o = PCSS_RING[ i ] * uPcss.y;
      float d = unpackRGBAToDepth( texture2D( shadowMap, c.xy + o ) );
      if ( d < c.z + dot( dz, o ) ) { sum += d; n += 1.0; }
    }
    if ( n == 0.0 ) return 1.0;
    if ( n == ${4 + PCSS_RING}.0 ) return 1.0 - shadowIntensity;
    // 2. penumbra radius from the gap (similar triangles with the sun's disc), 3. filter over it: the four texels
    // above as the centre tap, and a disc of taps round it
    float r = clamp( ( c.z - sum / n ) * uPcss.x, uPcss.z, uPcss.y );
    vec4 s = 1.0 - blk;
    float lit = mix( mix( s.x, s.y, f.x ), mix( s.z, s.w, f.x ), f.y );
    for ( int i = 0; i < ${PCSS_TAPS}; i ++ ) {
      vec2 o = PCSS_TAPS[ i ] * r;
      lit += pcssTap( shadowMap, shadowMapSize, c.xy + o, c.z + dot( dz, o ) );
    }
    return mix( 1.0, lit / ${PCSS_TAPS + 1}.0, shadowIntensity );
  }
#endif
`;

// give a material the PCSS shadow lookup (once; a hand-written onBeforeCompile, as terrain's and people's, is kept
// as the first edit). Returns the material.
export function pcss(m) {
  if (PATCHES.get(m)?.some((p) => p.key === 'pcss')) return m;
  patchShaderOwn(m, 'pcss', (sh) => {
    sh.uniforms.uPcss = PCSS.uniform;
    sh.fragmentShader = sh.fragmentShader.replace('#include <shadowmap_pars_fragment>', PCSS_CHUNK);
  });
  return m;
}

// per frame: the light's current frustum (it widens in the bird's-eye view) and map size; on: desktop HQ
export function updatePcss(light, on) {
  const u = PCSS.uniform.value, sh = light.shadow, cam = sh.camera;
  if (!on) { u.x = 0; return; }
  const w = cam.right - cam.left, depth = cam.far - cam.near, k = Math.tan(PCSS.sunDeg * Math.PI / 360) / w;
  u.set(k * depth, k * PCSS.reach, PCSS.minTexels / sh.mapSize.x, 4 * w / depth);
}

// ---------------------------------------------------------------------------- atmosphere: cloud shadows, height fog
// One set of uniforms shared by every material in the scene (globalPatch), updated once a frame from main.js:
//  - cloud shadows (#16): only the sunlight is dimmed under clouds drifting over the campus. A tileable
//    two-channel fBm texture is read twice where the sun ray through the pixel meets the cloud layer (so walls and
//    hillsides get the shadow of the cloud above them): a rotated 1.7 km tile that gathers the clouds into clusters
//    and clear gaps and bends the second read, a 480 m tile of cloud shapes; no 480 m repeat shows from the air.
//    A light factor, not a caster: independent of the (cached) shadow maps, and on phones too.
//  - height fog (#17): replaces three's uniform FogExp2. The haze thins with height (its extinction integrated along
//    the view ray from the camera's height to the pixel's), so the city in the valleys is hazy and the summits clearer,
//    and a high view looks down through thinner air. Its colour is the sky photo's horizon (makeSky blends to the same
//    y97FogColor): bright and warm towards the sun, a darker blue-grey away from it.
const CLOUD_TILE = 480, CLOUD_TILE_B = 1730;             // metres
const CLOUD_WIND = new THREE.Vector2(4.4, -2.6);         // m/s in three's XZ (z = -north): from the west-south-west
const CLOUD_WIND_B = new THREE.Vector2(3.1, -2.2);       // the large tile lags behind: the cloud shapes slowly change
export const ATMOS = {
  uCloudTex: { value: null },
  // 1/tiles, strength (share of the sunlight a cloud takes: thin fair-weather clouds), threshold (~1/3 of sky cloudy)
  uCloud: { value: new THREE.Vector4(1 / CLOUD_TILE, 1 / CLOUD_TILE_B, 0.4, 0.62) },
  uCloudOff: { value: new THREE.Vector4() },             // drift of the two tiles, in texture units
  uSunW: { value: new THREE.Vector3(0, 1, 0) },          // towards the sun, world
  // extinction at height 0 (1/m: from the campus ~28 % haze over 안산 1.7 km off, ~65 % on the hills 7 km off, as
  // in the May 1997 photo of 백양로; ~7 % over the campus seen from 200 m up), its falloff with height (1/m)
  uFogH: { value: new THREE.Vector2(2.5e-4, 1 / 550) },
  uFogAway: { value: new THREE.Color().setRGB(0.27, 0.3, 0.39) },   // linear: the horizon away from the sun
  uFogSun: { value: new THREE.Color().setRGB(0.69, 0.68, 0.66) },   // and round the sun's azimuth (warmer)
  uFogGlow: { value: new THREE.Color().setRGB(0.22, 0.17, 0.1) },   // forward scattering close to the sun
};

// GLSL shared by the patched materials and the sky dome
export const ATMOS_GLSL = /* glsl */`
#define Y97_ATMOS
#define Y97_CLOUD_H 1500.0
uniform sampler2D uCloudTex;
uniform vec4 uCloud, uCloudOff;
uniform vec3 uSunW;
uniform vec2 uFogH;
uniform vec3 uFogAway, uFogSun, uFogGlow;
// factor on the sun's direct light at world point p
float y97Cloud(vec3 p) {
  vec2 q = p.xz + uSunW.xz * ((Y97_CLOUD_H - p.y) / uSunW.y);
  vec2 b = texture2D(uCloudTex, mat2(0.8, 0.6, -0.6, 0.8) * q * uCloud.y + uCloudOff.zw).rg - 0.5;
  float a = texture2D(uCloudTex, q * uCloud.x + uCloudOff.xy + b * 0.15).r;
  return 1.0 - uCloud.z * smoothstep(uCloud.w - 0.1, uCloud.w + 0.1, a + b.y);
}
// in-scattered colour seen along unit direction dir (world): the horizon of the sky photo
vec3 y97FogColor(vec3 dir) {
  float s = dot(dir, uSunW);
  float w = clamp((1.0 + s) * 0.6, 0.0, 1.0);
  return mix(uFogAway, uFogSun, w * w * w) + uFogGlow * pow(max(s, 0.0), 12.0);
}
// share of the fog colour over rel = pixel - camera (world): extinction uFogH.x * exp(-uFogH.y * height), integrated
float y97FogAmount(vec3 rel) {
  float x = uFogH.y * rel.y;
  float f = abs(x) > 1e-4 ? (1.0 - exp(-x)) / x : 1.0 - 0.5 * x;
  return 1.0 - exp(-uFogH.x * exp(-uFogH.y * cameraPosition.y) * length(rel) * f);
}
`;

const ATMOS_DONE = new WeakSet();
const DEFAULT_OBC = THREE.Material.prototype.onBeforeCompile;
function atmosEdit(sh) {
  if (sh.fragmentShader.includes('Y97_ATMOS')) return;     // (once, whatever wraps whom)
  Object.assign(sh.uniforms, ATMOS);
  // world position from the view-space one every material has here (instancing, skinning, morphs included)
  sh.vertexShader = sh.vertexShader
    .replace('#include <common>', '#include <common>\nvarying vec3 vY97World;')
    .replace('#include <fog_vertex>', '#include <fog_vertex>\nvY97World = (mvPosition.xyz - viewMatrix[3].xyz) * mat3(viewMatrix);');
  sh.fragmentShader = sh.fragmentShader
    .replace('#include <common>', `#include <common>\nvarying vec3 vY97World;\n${ATMOS_GLSL}`)
    // The cloud factor rides on the sun's colour wherever three's light loop (or a patched copy of it) fetches it, and
    // on the sky light: the HDRI holds the sun too (70 % of what it throws on the ground), which a cloud also hides.
    // Wrappers + macros, so the chunks stay untouched. Only in the fogged main scene: the impostor and portrait
    // renders (no fog) must not bake a cloud in.
    .replace('#include <lights_pars_begin>', `#include <lights_pars_begin>
#ifdef USE_FOG
float y97CloudPx = -1.0;
float y97CloudHere() { if (y97CloudPx < 0.0) y97CloudPx = y97Cloud(vY97World); return y97CloudPx; }
#if NUM_DIR_LIGHTS > 0
void y97DirectionalLightInfo( const in DirectionalLight directionalLight, out IncidentLight light ) {
  getDirectionalLightInfo( directionalLight, light );
  light.color *= y97CloudHere();
}
#define getDirectionalLightInfo y97DirectionalLightInfo
#endif
#if defined( USE_ENVMAP ) && defined( ENVMAP_TYPE_CUBE_UV ) && defined( STANDARD )
float y97SkySun() { return 1.0 - 0.7 * (1.0 - y97CloudHere()); }
vec3 y97IBLIrradiance( const in vec3 normal ) { return getIBLIrradiance( normal ) * y97SkySun(); }
vec3 y97IBLRadiance( const in vec3 viewDir, const in vec3 normal, const in float roughness ) {
  return getIBLRadiance( viewDir, normal, roughness ) * y97SkySun();
}
#define getIBLIrradiance y97IBLIrradiance
#define getIBLRadiance y97IBLRadiance
#endif
#endif`)
    .replace('#include <fog_fragment>', `#ifdef USE_FOG
{
  vec3 fogRel = vY97World - cameraPosition;
  gl_FragColor.rgb = mix(gl_FragColor.rgb, y97FogColor(normalize(fogRel)), y97FogAmount(fogRel));
}
#endif`);
}

// Give a material the shared atmosphere (cloud shadows + height fog). Safe to call more than once and on any material;
// an onBeforeCompile set by hand before (terrain, people, banners) stays, as the first edit of the stack.
export function globalPatch(m) {
  if (!m || ATMOS_DONE.has(m) || m.fog === false || m.isRawShaderMaterial) return m;
  if (m.isShaderMaterial ? !m.vertexShader.includes('#include <fog_vertex>') || !m.fragmentShader.includes('#include <fog_fragment>')
    : !(m.isMeshStandardMaterial || m.isMeshLambertMaterial || m.isMeshPhongMaterial || m.isMeshBasicMaterial || m.isMeshToonMaterial)) return m;
  ATMOS_DONE.add(m);
  if (/(^|\|)atmos(\||$)/.test(m.customProgramCacheKey())) return m;   // a library material's instanced copy
  if (!PATCHES.has(m) && m.onBeforeCompile !== DEFAULT_OBC) {
    const own = m.onBeforeCompile;
    PATCHES.set(m, [{ key: `own${hashString(own.toString())}`, edit: own }]);
  }
  patchShader(m, 'atmos', atmosEdit);
  m.needsUpdate = true;
  return m;
}

function hashString(s) {
  let h = 2166136261;
  for (let i = 0; i < s.length; i++) h = Math.imul(h ^ s.charCodeAt(i), 16777619);
  return (h >>> 0).toString(36);
}

// sunDir: unit vector towards the sun (world)
export function setupAtmosphere(sunDir) {
  ATMOS.uSunW.value.copy(sunDir);
  ATMOS.uCloudTex.value = cloudTexture();
}

// once a frame: the clouds drift (offsets wrapped to [0, 1) texture units: no precision loss over a long session)
export function updateAtmosphere(dt) {
  const o = ATMOS.uCloudOff.value;
  // the large tile is read rotated (the mat2 in y97Cloud): its drift in its own axes
  const bx = 0.8 * CLOUD_WIND_B.x - 0.6 * CLOUD_WIND_B.y, by = 0.6 * CLOUD_WIND_B.x + 0.8 * CLOUD_WIND_B.y;
  o.x -= CLOUD_WIND.x * dt / CLOUD_TILE; o.y -= CLOUD_WIND.y * dt / CLOUD_TILE;
  o.z -= bx * dt / CLOUD_TILE_B; o.w -= by * dt / CLOUD_TILE_B;
  o.set(o.x - Math.floor(o.x), o.y - Math.floor(o.y), o.z - Math.floor(o.z), o.w - Math.floor(o.w));
}

// 256² tileable fBm of periodic gradient noise (4 octaves, 3 to 24 cells across), two independent channels, each
// scaled to mean 0.5 and spread 0.18 (so the threshold in uCloud sets the share of sky that is cloud)
function cloudTexture(N = 256) {
  const rnd = mulberry(1997);
  const octaves = [3, 6, 12, 24];
  const fade = (t) => t * t * t * (t * (t * 6 - 15) + 10);
  const data = new Uint8Array(N * N * 2);
  const v = new Float32Array(N * N);
  for (let ch = 0; ch < 2; ch++) {
    const grads = octaves.map((p) => Float32Array.from({ length: p * p }, () => rnd() * Math.PI * 2));
    let s1 = 0, s2 = 0;
    for (let j = 0; j < N; j++) {
      for (let i = 0; i < N; i++) {
        let sum = 0, amp = 1;
        octaves.forEach((p, o) => {
          const x = (i / N) * p, y = (j / N) * p;
          const x0 = Math.floor(x), y0 = Math.floor(y), fx = x - x0, fy = y - y0;
          const g = (cx, cy, dx, dy) => { const a = grads[o][(cy % p) * p + (cx % p)]; return Math.cos(a) * dx + Math.sin(a) * dy; };
          const u = fade(fx), w = fade(fy);
          const n0 = g(x0, y0, fx, fy) * (1 - u) + g(x0 + 1, y0, fx - 1, fy) * u;
          const n1 = g(x0, y0 + 1, fx, fy - 1) * (1 - u) + g(x0 + 1, y0 + 1, fx - 1, fy - 1) * u;
          sum += amp * (n0 * (1 - w) + n1 * w);
          amp *= 0.5;
        });
        v[j * N + i] = sum;
        s1 += sum; s2 += sum * sum;
      }
    }
    const mean = s1 / (N * N), sd = Math.sqrt(s2 / (N * N) - mean * mean);
    for (let k = 0; k < N * N; k++) data[k * 2 + ch] = Math.round(THREE.MathUtils.clamp(0.5 + ((v[k] - mean) / sd) * 0.18, 0, 1) * 255);
  }
  const t = new THREE.DataTexture(data, N, N, THREE.RGFormat, THREE.UnsignedByteType);
  t.wrapS = t.wrapT = THREE.RepeatWrapping;
  t.minFilter = THREE.LinearMipmapLinearFilter;
  t.magFilter = THREE.LinearFilter;
  t.generateMipmaps = true;
  t.needsUpdate = true;
  return t;
}
