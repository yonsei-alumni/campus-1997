// Adapted from Ultra Water (https://github.com/Humpalumps/Ultra-Water, src/water/Caustics.js @ 30ea65e),
// MIT License, Copyright (c) 2026 Humpalumps (see ./LICENSE).
// Changes for the 활천 fountain: one caustic plane (the basin floor) in one MSAA target instead of three planes in
// two; the tile length, depth, grid and target size are constructor options; the refracted slopes are the sum of
// three cascades (the shorter ones' lengths divide the tile's, so the pattern still tiles); the sun is passed in
// world space each update. The splatting itself (B-spline slopes, refraction, area ratio) is unchanged.
import * as THREE from 'three';
import { rawPass } from './fullscreen.js';

// Wave-driven caustics by area-ratio splatting (Evan Wallace's WebGL water): a grid over one cascade period is
// refracted through the slopes onto a plane at the given depth, and every landed triangle adds (undisturbed area /
// landed area). The output, mipmapped + repeat and tiling every `length` metres, is the intensity relative to flat
// water, mean 1 by construction, so it multiplies direct sun light. The landing offset of flat water is subtracted,
// registering the pattern to the surface entry point: look up at uv = entryXZ / length.

const ETA = 1 / 1.33;
const MAX_RATIO = 16;  // firefly clamp (calibration knob; energy above it is dropped)
const f = (x) => x.toPrecision(9);   // GLSL float literal

const VERT = (L, r1, r2) => /* glsl */`
precision highp float;
in vec3 position;               // PlaneGeometry vertex: cell coords - uCells / 2
uniform highp sampler2D uSlope, uSlope2, uSlope3; // the tile's cascade and two shorter ones tiling ${r1}x and ${r2}x inside it
uniform vec3 uSun;              // towards the sun
uniform float uDepth, uCells, uLod, uMargin, uRes;
out vec2 vOld;

// cubic B-spline from 4 bilinear taps (GPU Gems 2, ch. 20). The landed intensity goes
// with the slope's derivative, which bilinear makes piecewise constant: every slope texel
// would land as its own bead along the caustic lines.
vec2 slopeBSpline(highp sampler2D tex, vec2 uv, float lod) {
  vec2 size = vec2(textureSize(tex, int(lod)));
  vec2 st = uv * size - 0.5, i = floor(st), f = st - i;
  vec2 f2 = f * f, f3 = f2 * f;
  vec2 w0 = (1.0 - 3.0 * f + 3.0 * f2 - f3) / 6.0, w1 = (4.0 - 6.0 * f2 + 3.0 * f3) / 6.0;
  vec2 w2 = (1.0 + 3.0 * f + 3.0 * f2 - 3.0 * f3) / 6.0, w3 = f3 / 6.0;
  vec2 g0 = w0 + w1, g1 = w2 + w3;
  vec2 h0 = (i - 0.5 + w1 / g0) / size, h1 = (i + 1.5 + w3 / g1) / size;
  return g0.y * (g0.x * textureLod(tex, h0, lod).xy + g1.x * textureLod(tex, vec2(h1.x, h0.y), lod).xy)
       + g1.y * (g0.x * textureLod(tex, vec2(h0.x, h1.y), lod).xy + g1.x * textureLod(tex, h1, lod).xy);
}

void main() {
  vec2 t = (position.xy + 0.5 * uCells + 0.5) / uCells;   // tile uv
  vec2 s = slopeBSpline(uSlope, t, uLod) + slopeBSpline(uSlope2, t * ${f(r1)}, 0.0) + slopeBSpline(uSlope3, t * ${f(r2)}, 0.0);
  vec3 r = refract(-uSun, normalize(vec3(-s.x, 1.0, -s.y)), ${f(ETA)});
  vec3 rf = refract(-uSun, vec3(0.0, 1.0, 0.0), ${f(ETA)});
  vec2 d = (r.xz / max(-r.y, 0.05) - rf.xz / -rf.y) * (uDepth / ${f(L)});
  d = clamp(d, -uMargin, uMargin);
  vOld = t * uRes;
  gl_Position = vec4((t + d) * 2.0 - 1.0, 0.0, 1.0);
}`;

const FRAG = /* glsl */`
precision highp float;
in vec2 vOld;
out vec4 outColor;

void main() {
  // raster space is the landed space at one texel per pixel, so the landed area is 1 and
  // the ratio is the undisturbed area (in texels) per pixel
  vec2 a = dFdx(vOld), b = dFdy(vOld);
  outColor = vec4(min(abs(a.x * b.y - a.y * b.x), ${f(MAX_RATIO)}), 0.0, 0.0, 0.0);
}`;

const _color = new THREE.Color();

export class WaveCaustics {
  // sim: OceanSim; cascades: indices of the tile cascade and two shorter ones (their lengths must divide the
  // tile's); depth: metres below the surface; cells: grid cells per tile; res: target size; samples: MSAA
  constructor(renderer, sim, { cascades = [0, 1, 2], depth = 0.4, cells = 128, margin = 6, res = 256, samples = 4 } = {}) {
    this.renderer = renderer;
    this.sim = sim;
    this.cascades = cascades;
    this.length = sim.lengths[cascades[0]];
    const [r1, r2] = cascades.slice(1).map((c) => Math.round(this.length / sim.lengths[c]));
    this.target = new THREE.WebGLRenderTarget(res, res, {
      type: THREE.HalfFloatType, format: THREE.RedFormat, samples, minFilter: THREE.LinearMipmapLinearFilter, magFilter: THREE.LinearFilter,
      wrapS: THREE.RepeatWrapping, wrapT: THREE.RepeatWrapping, generateMipmaps: true, depthBuffer: false,
    });
    this.texture = this.target.texture;
    this.slope = { value: null };
    this.slope2 = { value: null };
    this.slope3 = { value: null };
    this.sun = { value: new THREE.Vector3() };
    const mat = rawPass(FRAG, {
      uSlope: this.slope, uSlope2: this.slope2, uSlope3: this.slope3, uSun: this.sun, uRes: { value: res },
      uDepth: { value: depth }, uCells: { value: cells }, uLod: { value: Math.max(0, Math.log2(sim.N / cells)) },
      uMargin: { value: (margin - 1) / cells },
    }, {
      vertexShader: VERT(this.length, r1, r2), side: THREE.DoubleSide,   // folds past the focus land flipped
      blending: THREE.CustomBlending, blendSrc: THREE.OneFactor, blendDst: THREE.OneFactor,
    });
    const span = cells + 2 * margin;
    this.mesh = new THREE.Mesh(new THREE.PlaneGeometry(span, span, span, span), mat);
    this.mesh.frustumCulled = false;
    this.camera = new THREE.Camera();
  }

  // after sim.update(); sunDir (world) points towards the sun
  update(sunDir) {
    const r = this.renderer;
    const prevRT = r.getRenderTarget(), prevAlpha = r.getClearAlpha();
    r.getClearColor(_color);
    this.sun.value.copy(sunDir).normalize();
    [this.slope.value, this.slope2.value, this.slope3.value] = this.cascades.map((c) => this.sim.slope[c]);
    r.setClearColor(0x000000, 1);
    r.setRenderTarget(this.target);
    r.clear(true, false, false);
    r.render(this.mesh, this.camera);
    r.setRenderTarget(prevRT);
    r.setClearColor(_color, prevAlpha);
  }
}
