// Baked sun shadows: the whole campus's static sun shadow, cast on the ground, in one texture.
// The sun never moves, so the shadows of the buildings, the trees (their alpha-tested crowns: dappled, not solid), the
// shrubs, the props and the parked cars on the ground are drawn once, from above (bakeSunMap below, run by
// tools/bake_sun_shadows.mjs), into assets/textures/sun_shadow.png: 1 = sunlit, 0 = in shadow.
// Phones draw no shadow maps (main.js: the shadow pass crashes some GPU drivers), so there this is the only sun
// shadow; on the desktop it shades what the real-time map (shadows.js) leaves out: the ground beyond its reach and
// the shadows of the far trees, which are impostors that cast nothing.
import * as THREE from 'three';
import { versioned } from './util.js';

// the baked rectangle (campus x = east, y = north, metres; every building and tree, and their shadows to the
// north-west) and its size in texels: 31 cm texels
export const SUN_RECT = { x0: -440, y0: -505, x1: 560, y1: 745 };
export const SUN_SIZE = [3200, 4000];
const URL = 'assets/textures/sun_shadow.png';
// The map is the shadow on the top-most surface no higher than this above the terrain: the ground, and on it plinths,
// steps, shrubs, benches and parked car roofs (porch roofs and the like are higher: the ground under them is baked)
const LIFT = 1.6;

// The shader edit. SUN_MODE 0: ground (the terrain) takes the map as it is. 1: everything else static or moving,
// read where it stands; walls read the ground just in front of them (the texel under a wall is in the building's
// own shadow), and nothing higher than the baked surfaces takes it. 2: people, the whole body the light of the
// spot it stands on (no moving thing is in the map, so nobody darkens in their own shadow).
const VERT = `
  {
    vec4 sunW = vec4( transformed, 1.0 );
    #ifdef USE_BATCHING
    sunW = batchingMatrix * sunW;
    #endif
    #ifdef USE_INSTANCING
    sunW = instanceMatrix * sunW;
    #endif
    vSunW = ( modelMatrix * sunW ).xyz;
    vSunN = ( vec4( transformedNormal, 0.0 ) * viewMatrix ).xyz;
  }`;
const FRAG_DECL = `
  uniform sampler2D uSunMap, uSunGround;
  uniform vec4 uSunRect;      // x0, y0 (south-west corner), x1, y1 (north-east) of the map
  uniform vec3 uSunGroundF;   // the terrain heightfield: half size, step, vertices per side
  varying vec3 vSunW; varying vec3 vSunN;
  float sunGroundH( vec2 p ) {
    return texture2D( uSunGround, ( ( p + uSunGroundF.x ) / uSunGroundF.y + 0.5 ) / uSunGroundF.z ).r;
  }
  float sunBaked() {
    vec2 p = vec2( vSunW.x, -vSunW.z );
    float w = 1.0;
    #if SUN_MODE == 1
    vec3 n = normalize( vSunN );
    p += vec2( n.x, -n.z ) * 0.35;
    w = 1.0 - smoothstep( 1.0, ${LIFT.toFixed(2)}, vSunW.y - sunGroundH( p ) );
    #elif SUN_MODE == 2
    w = 1.0 - smoothstep( 2.2, 2.8, vSunW.y - sunGroundH( p ) );
    #endif
    #if defined( USE_SHADOWMAP ) && NUM_DIR_LIGHT_SHADOWS > 0
    // in the real-time shadow map and near the view that map alone (sharper, and it has the people and cars);
    // farther out, where its trees are impostors, both (where both see a caster they agree); outside it this alone
    vec3 sc = vDirectionalShadowCoord[ 0 ].xyz / vDirectionalShadowCoord[ 0 ].w;
    vec2 e = min( sc.xy, 1.0 - sc.xy );
    float inMap = smoothstep( 0.0, 0.04, min( e.x, e.y ) ) * step( sc.z, 1.0 );
    w *= 1.0 - inMap * ( 1.0 - smoothstep( 110.0, 150.0, distance( vSunW, cameraPosition ) ) );
    #endif
    if ( w <= 0.0 ) return 1.0;
    vec2 uv = vec2( ( p.x - uSunRect.x ) / ( uSunRect.z - uSunRect.x ), ( uSunRect.w - p.y ) / ( uSunRect.w - uSunRect.y ) );
    if ( uv.x < 0.0 || uv.x > 1.0 || uv.y < 0.0 || uv.y > 1.0 ) return 1.0;
    return mix( 1.0, texture2D( uSunMap, uv ).r, w );
  }`;
const SUN_LINE = 'getDirectionalLightInfo( directionalLight, directLight );';

function editShader(sh, uniforms, mode) {
  Object.assign(sh.uniforms, uniforms);
  sh.vertexShader = sh.vertexShader
    .replace('#include <common>', '#include <common>\nvarying vec3 vSunW; varying vec3 vSunN;')
    .replace('#include <project_vertex>', `#include <project_vertex>${VERT}`);
  // (the lights chunk is expanded here so the sun's line in it can be reached; another edit may have done it already.
  // The function goes after shadowmap_pars_fragment, where the real-time map's coordinates are declared.)
  sh.fragmentShader = sh.fragmentShader
    .replace('#include <lights_fragment_begin>', THREE.ShaderChunk.lights_fragment_begin)
    .replace('#include <shadowmap_pars_fragment>', `#include <shadowmap_pars_fragment>\n#define SUN_MODE ${mode}${FRAG_DECL}`)
    .replace(SUN_LINE, `${SUN_LINE}\n\t\tdirectLight.color *= sunBaked();`);
}

function groundTexture(hf) {
  const { n, data } = hf;
  const h = new Uint16Array(n * n);
  for (let i = 0; i < n * n; i++) h[i] = THREE.DataUtils.toHalfFloat(data[i]);
  const t = new THREE.DataTexture(h, n, n, THREE.RedFormat, THREE.HalfFloatType);
  t.minFilter = t.magFilter = THREE.LinearFilter;
  t.needsUpdate = true;
  return t;
}

export class SunMap {
  constructor(hf) {
    this.white = new THREE.DataTexture(new Uint8Array([255]), 1, 1, THREE.RedFormat);
    this.white.needsUpdate = true;
    const { x0, y0, x1, y1 } = SUN_RECT;
    this.uniforms = {
      uSunMap: { value: this.white },          // sunlit everywhere until the map has loaded
      uSunRect: { value: new THREE.Vector4(x0, y0, x1, y1) },
      uSunGround: { value: groundTexture(hf) },
      uSunGroundF: { value: new THREE.Vector3(hf.half, hf.step, hf.n) },
    };
    this.texture = null;
    this._on = true;
    this.patched = new WeakSet();
  }

  load() {
    new THREE.TextureLoader().load(versioned(URL), (t) => {
      t.format = THREE.RedFormat;
      t.colorSpace = THREE.NoColorSpace;
      t.flipY = false;                         // row 0 is the north edge
      t.wrapS = t.wrapT = THREE.ClampToEdgeWrapping;
      t.anisotropy = 8;
      t.needsUpdate = true;
      this.texture = t;
      if (this._on) this.uniforms.uSunMap.value = t;
    }, undefined, () => console.warn('no baked sun shadows:', URL));
    return this;
  }

  get on() { return this._on; }
  set on(v) { this._on = v; this.uniforms.uSunMap.value = v && this.texture ? this.texture : this.white; }

  // add the baked shadow to a lit material's sunlight (kept on top of the material's own shader edits)
  patch(m, mode = 1) {
    if (!m || !m.isMeshStandardMaterial || this.patched.has(m)) return;
    this.patched.add(m);
    const prev = m.onBeforeCompile, key = m.customProgramCacheKey();
    m.onBeforeCompile = (sh, r) => { prev.call(m, sh, r); editShader(sh, this.uniforms, mode); };
    m.customProgramCacheKey = () => `${key}|sun${mode}`;
    m.needsUpdate = true;
  }

  // every lit material in the scene but the far scenery and the see-through ones (glass, water)
  patchScene(root, skip = () => false) {
    root.traverse((o) => {
      if (!o.isMesh || skip(o)) return;
      for (const m of Array.isArray(o.material) ? o.material : [o.material]) {
        if (m.transparent || /^impostor_/.test(m.name)) continue;
        this.patch(m, m.name === 'person' ? 2 : 1);
      }
    });
  }
}

// ---------------------------------------------------------------------------- baking (tools/bake_sun_shadows.mjs)
// Draws the map in tiles with the game's own sun shadow map (shadows.js, the desktop path): for each tile the shadow
// frustum is put over it, every tree near it is switched to its full model, and the ground is drawn from straight
// above with a material that writes the shadow only. Moving things (people, cars, the ball) and the banners (they
// change with the month) are hidden. Returns {width, height, data}: row 0 = north, 0..255.
export async function bakeSunMap({ renderer, scene, sun, sunDir, shadows, forest, hf, hide = [], skip = () => false }) {
  const BAKE = 7;                                       // layer of the surfaces the top view sees
  const [W, H] = SUN_SIZE, { x0, y1 } = SUN_RECT;
  const texel = (SUN_RECT.x1 - x0) / W;
  const TILE = 400, SS = 2, N = TILE * SS;              // texels per tile side, supersampling
  renderer.setAnimationLoop(null);
  const hidden = [];
  for (const o of [...shadows.dyn.map((d) => d.root), ...hide]) if (o && o.visible) { o.visible = false; hidden.push(o); }
  // the receivers: everything solid but the trees and the far scenery
  const trees = new Set();
  for (const k of Object.values(forest.near)) for (const p of k.parts) trees.add(p);
  for (const { im, top } of Object.values(forest.impostors)) { trees.add(im); trees.add(top); }
  const recv = [];
  scene.traverse((o) => {
    if (!o.isMesh || trees.has(o) || skip(o)) return;
    const mats = Array.isArray(o.material) ? o.material : [o.material];
    if (mats.every((m) => m.transparent)) return;
    let v = true;
    for (let p = o; p; p = p.parent) if (!p.visible) v = false;
    if (!v) return;
    recv.push([o, o.receiveShadow]);
    o.layers.enable(BAKE);
    o.receiveShadow = true;
  });
  sun.layers.enable(BAKE);
  const uniforms = {
    uSunGround: { value: groundTexture(hf) }, uSunGroundF: { value: new THREE.Vector3(hf.half, hf.step, hf.n) },
  };
  const mat = new THREE.ShadowMaterial({ side: THREE.DoubleSide, fog: false });
  mat.transparent = false;
  mat.onBeforeCompile = (sh) => {
    Object.assign(sh.uniforms, uniforms);
    sh.vertexShader = sh.vertexShader
      .replace('#include <common>', '#include <common>\nvarying vec3 vSunW; varying vec3 vSunN;')
      .replace('#include <project_vertex>', `#include <project_vertex>${VERT}`);
    sh.fragmentShader = sh.fragmentShader
      .replace('#include <common>', `#include <common>
        uniform sampler2D uSunGround; uniform vec3 uSunGroundF; varying vec3 vSunW;
        float sunGroundH( vec2 p ) { return texture2D( uSunGround, ( ( p + uSunGroundF.x ) / uSunGroundF.y + 0.5 ) / uSunGroundF.z ).r; }`)
      .replace('gl_FragColor = vec4( color, opacity * ( 1.0 - getShadowMask() ) );', `
        if ( vSunW.y - sunGroundH( vec2( vSunW.x, -vSunW.z ) ) > ${LIFT.toFixed(2)} ) discard;
        gl_FragColor = vec4( vec3( getShadowMask() ), 1.0 );`);
  };
  const prevOverride = scene.overrideMaterial;
  scene.overrideMaterial = mat;
  const rt = new THREE.WebGLRenderTarget(N, N, { minFilter: THREE.NearestFilter, magFilter: THREE.NearestFilter, generateMipmaps: false });
  const half = (TILE * texel) / 2;
  const cam = new THREE.OrthographicCamera(-half, half, half, -half, 1, 2000);
  cam.up.set(0, 0, -1);                                 // screen up = north
  cam.layers.set(BAKE);
  const sh = sun.shadow, span = half * 1.45 + 20;
  Object.assign(sh.camera, { left: -span, right: span, top: span, bottom: -span });
  sh.camera.updateProjectionMatrix();
  shadows.span = span;
  const out = new Uint8Array(W * H), buf = new Uint8Array(N * N * 4);
  const prevNear = forest.nearDist, centre = new THREE.Vector3();
  renderer.setClearColor(0xffffff, 1);
  for (let ty = 0; ty < H / TILE; ty++) {
    for (let tx = 0; tx < W / TILE; tx++) {
      const cx = x0 + (tx + 0.5) * TILE * texel, cy = y1 - (ty + 0.5) * TILE * texel;
      const h = hf.height(cx, cy);
      centre.set(cx, h, -cy);
      // full trees within reach of the tile: its corners, the longest tree shadows and a crown
      forest.nearDist = half * 1.42 + 50;
      forest.update(centre, true);
      sun.target.position.copy(centre);
      sun.position.copy(centre).addScaledVector(sunDir, shadows.dist);
      shadows.req.focus.copy(centre);
      shadows.dirty = true;
      shadows.pending = shadows.req;                    // the static casters are drawn in the render below
      cam.position.set(cx, h + 900, -cy);
      cam.lookAt(cx, h, -cy);
      renderer.setRenderTarget(rt);
      renderer.render(scene, cam);
      renderer.readRenderTargetPixels(rt, 0, 0, N, N, buf);
      // 2x2 box filter; GL rows run from the bottom (south)
      for (let r = 0; r < TILE; r++) {
        const row = (ty * TILE + r) * W + tx * TILE, gr0 = (N - 1 - r * SS) * N, gr1 = gr0 - N;
        for (let c = 0; c < TILE; c++) {
          const a = (gr0 + c * SS) * 4, b = (gr1 + c * SS) * 4;
          out[row + c] = (buf[a] + buf[a + 4] + buf[b] + buf[b + 4] + 2) >> 2;
        }
      }
      await new Promise((res) => setTimeout(res, 0));
    }
  }
  renderer.setRenderTarget(null);
  scene.overrideMaterial = prevOverride;
  for (const [o, rs] of recv) { o.layers.disable(BAKE); o.receiveShadow = rs; }
  for (const o of hidden) o.visible = true;
  forest.nearDist = prevNear;
  shadows.invalidate();
  rt.dispose();
  return { width: W, height: H, data: out };
}
