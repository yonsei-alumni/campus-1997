// Post-processing: N8AO ambient occlusion -> SMAA -> small bloom -> "1997 film" grade -> tone mapping/sRGB output.
import * as THREE from 'three';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { ShaderPass } from 'three/addons/postprocessing/ShaderPass.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';
import { SMAAPass } from 'three/addons/postprocessing/SMAAPass.js';
import { Pass, FullScreenQuad } from 'three/addons/postprocessing/Pass.js';
import { N8AOPass } from 'n8ao';
import { MOBILE } from './util.js';

const FilmShader = {
  uniforms: {
    tDiffuse: { value: null }, tBloom: { value: null }, uBloom: { value: 0 },
    uTime: { value: 0 }, uFilm: { value: 0 }, uRes: { value: new THREE.Vector2(1, 1) },
  },
  vertexShader: `varying vec2 vUv; void main(){ vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position,1.0); }`,
  fragmentShader: `
    uniform sampler2D tDiffuse, tBloom; uniform float uTime, uFilm, uBloom; uniform vec2 uRes; varying vec2 vUv;
    float rnd(vec2 p){ return fract(sin(dot(p, vec2(12.9898,78.233)) + uTime*7.0) * 43758.5453); }
    void main(){
      vec4 c = texture2D(tDiffuse, vUv);
      // the bloom is added here (linear, before the grade and the tone mapping) instead of in a full-screen pass of its own
      vec3 bl = uBloom > 0.0 ? texture2D(tBloom, vUv).rgb * uBloom : vec3(0.0);
      c.rgb += bl;
      // gentle spring haze for everyone
      c.rgb = mix(c.rgb, c.rgb * vec3(1.02, 1.0, 0.97), 0.6);
      if (uFilm > 0.0) {
        vec2 d = (vUv - 0.5);
        // slight lens softness + warm 35mm print look
        vec3 blur = (texture2D(tDiffuse, vUv + d * 0.004).rgb + texture2D(tDiffuse, vUv - d * 0.004).rgb) * 0.5 + bl;
        vec3 g = mix(c.rgb, blur, 0.5);
        float l = dot(g, vec3(0.299, 0.587, 0.114));
        g = mix(vec3(l), g, 0.82);                                 // desaturate
        // warm, lifted blacks (lifted less since the height fog hazes the distance itself: no milky double haze)
        g = g * vec3(1.08, 1.0, 0.86) + vec3(0.024, 0.014, 0.0);
        g = pow(g, vec3(0.95));
        float vig = smoothstep(0.85, 0.25, length(d * vec2(1.25, 1.0)));
        g *= mix(0.62, 1.0, vig);
        g += (rnd(vUv * uRes) - 0.5) * 0.06;                       // grain
        c.rgb = mix(c.rgb, g, uFilm);
      }
      gl_FragColor = c;
    }`,
};

// SMAA on the linear HDR colour that N8AO leaves: it has to come before the film grade (it would take the grain for
// edges), so before the tone mapping too. Edges are looked for on a display-like encoding of that colour (on raw
// linear values a dark frame on dark glass is no edge), and the two sides are mixed tone-mapped and back (Karis)
// instead of in the gamma-2.2 space the three.js port assumes for an already encoded input.
function hdrSMAA(w, h) {
  const p = new SMAAPass(w, h);
  // edges and blend weights fit in 8 bits as in the reference (the port keeps two half-float screens for them)
  for (const rt of [p.edgesRT, p.weightsRT]) rt.texture.type = THREE.UnsignedByteType;
  const e = p.materialEdges, b = p.materialBlend;
  e.fragmentShader = e.fragmentShader
    .replace(/texture2D\( colorTex, ([^)]+) \)\.rgb/g, 'smaaEnc( colorTex, $1 )')
    .replace('vec4 SMAAColorEdgeDetectionPS', `vec3 smaaEnc( sampler2D t, vec2 uv ) { vec3 c = max( texture2D( t, uv ).rgb, 0.0 ); return sqrt( c / ( 1.0 + c ) ); }
      vec4 SMAAColorEdgeDetectionPS`);
  b.fragmentShader = b.fragmentShader
    .replace('C.xyz = pow(C.xyz, vec3(2.2));', 'C.xyz /= 1.0 + max( C.x, max( C.y, C.z ) );')
    .replace('Cop.xyz = pow(Cop.xyz, vec3(2.2));', 'Cop.xyz /= 1.0 + max( Cop.x, max( Cop.y, Cop.z ) );')
    .replace('mixed.xyz = pow(mixed.xyz, vec3(1.0 / 2.2));', 'mixed.xyz /= max( 1.0 - max( mixed.x, max( mixed.y, mixed.z ) ), 1e-4 );');
  return p;
}

// A small bloom of only what is far brighter than the rest (sunlit white walls and concrete, the sky round the sun,
// bright clouds, the light on car roofs): AgX squeezes those to a flat pale grey, and a higher exposure would lift
// the shade too. Two levels only instead of UnrealBloomPass's five: a half-resolution bright pass (a tight glow) and
// a quarter-resolution Gaussian of it (a wider one, ~20 pixels), so it stays a photo's halation, not a haze. The result
// is a half-resolution texture that the film pass adds (Bloom.texture); nothing is drawn into the composer's buffers.
const quadVS = `varying vec2 vUv; void main(){ vUv = uv; gl_Position = vec4(position.xy, 0.0, 1.0); }`;
const DownFS = `
  uniform sampler2D tSrc; uniform vec2 uTexel; uniform float uThreshold, uKnee; varying vec2 vUv;
  #ifdef PREFILTER
  // what is brighter than the threshold (luminance, so that red flowers and shirts in the sun stay out), faded in over
  // uKnee; each tap weighted down by its brightness (Karis) so that a single glint on a car does not flicker as a blob
  vec4 tap(vec2 uv) {
    vec3 c = texture2D(tSrc, uv).rgb;
    float l = dot(c, vec3(0.2126, 0.7152, 0.0722));
    c *= smoothstep(uThreshold, uThreshold + uKnee, l);
    float w = 1.0 / (1.0 + l);
    return vec4(c * w, w);
  }
  #else
  vec4 tap(vec2 uv) { return vec4(texture2D(tSrc, uv).rgb, 1.0); }
  #endif
  void main() {
    // four bilinear taps one source texel off the centre: a 4x4 box of the source
    vec4 s = tap(vUv + uTexel * vec2(-1.0, -1.0)) + tap(vUv + uTexel * vec2(1.0, -1.0))
           + tap(vUv + uTexel * vec2(-1.0, 1.0)) + tap(vUv + uTexel * vec2(1.0, 1.0));
    gl_FragColor = vec4(s.rgb / s.a, 1.0);
  }`;
const BlurFS = `
  uniform sampler2D tSrc; uniform vec2 uDir; varying vec2 vUv;
  void main() {
    // 9-tap Gaussian from five bilinear fetches
    gl_FragColor = vec4(texture2D(tSrc, vUv).rgb * 0.2270270270
      + (texture2D(tSrc, vUv + uDir * 1.3846153846).rgb + texture2D(tSrc, vUv - uDir * 1.3846153846).rgb) * 0.3162162162
      + (texture2D(tSrc, vUv + uDir * 3.2307692308).rgb + texture2D(tSrc, vUv - uDir * 3.2307692308).rgb) * 0.0702702703, 1.0);
  }`;
const UpFS = `
  uniform sampler2D tHalf, tQuarter; varying vec2 vUv;
  void main() { gl_FragColor = vec4((texture2D(tHalf, vUv).rgb + texture2D(tQuarter, vUv).rgb) * 0.5, 1.0); }`;

class Bloom extends Pass {
  constructor() {
    super();
    this.needsSwap = false;
    const opt = { type: THREE.HalfFloatType, depthBuffer: false };
    this.half = new THREE.WebGLRenderTarget(1, 1, opt);
    this.quarter = new THREE.WebGLRenderTarget(1, 1, opt);
    this.quarter2 = new THREE.WebGLRenderTarget(1, 1, opt);
    this.out = new THREE.WebGLRenderTarget(1, 1, opt);
    // luminance before tone mapping: sunlit white walls 1.0-1.2, the sky round the sun 1.25, sunlit paving and the
    // blue sky below 0.85, sunlit lawns and leaves below 0.5
    this.threshold = { value: 0.85 };
    this.knee = { value: 0.35 };
    const down = (prefilter) => new THREE.ShaderMaterial({
      defines: prefilter ? { PREFILTER: '' } : {},
      uniforms: { tSrc: { value: null }, uTexel: { value: new THREE.Vector2() }, uThreshold: this.threshold, uKnee: this.knee },
      vertexShader: quadVS, fragmentShader: DownFS, depthTest: false, depthWrite: false,
    });
    this.prefilter = down(true);
    this.down = down(false);
    const blur = (src) => new THREE.ShaderMaterial({
      uniforms: { tSrc: { value: src.texture }, uDir: { value: new THREE.Vector2() } },
      vertexShader: quadVS, fragmentShader: BlurFS, depthTest: false, depthWrite: false,
    });
    this.blurH = blur(this.quarter);
    this.blurV = blur(this.quarter2);
    this.up = new THREE.ShaderMaterial({
      uniforms: { tHalf: { value: this.half.texture }, tQuarter: { value: this.quarter.texture } },
      vertexShader: quadVS, fragmentShader: UpFS, depthTest: false, depthWrite: false,
    });
    this.down.uniforms.tSrc.value = this.half.texture;
    this.quad = new FullScreenQuad(null);
  }
  get texture() { return this.out.texture; }
  setSize(w, h) {
    const hw = Math.max(1, Math.ceil(w / 2)), hh = Math.max(1, Math.ceil(h / 2));
    const qw = Math.max(1, Math.ceil(w / 4)), qh = Math.max(1, Math.ceil(h / 4));
    this.half.setSize(hw, hh);
    this.out.setSize(hw, hh);
    this.quarter.setSize(qw, qh);
    this.quarter2.setSize(qw, qh);
    this.prefilter.uniforms.uTexel.value.set(1 / w, 1 / h);
    this.down.uniforms.uTexel.value.set(1 / hw, 1 / hh);
    this.blurH.uniforms.uDir.value.set(1 / qw, 0);
    this.blurV.uniforms.uDir.value.set(0, 1 / qh);
  }
  _draw(renderer, material, target) {
    this.quad.material = material;
    renderer.setRenderTarget(target);
    this.quad.render(renderer);
  }
  render(renderer, writeBuffer, readBuffer) {
    this.prefilter.uniforms.tSrc.value = readBuffer.texture;
    this._draw(renderer, this.prefilter, this.half);
    this._draw(renderer, this.down, this.quarter);
    this._draw(renderer, this.blurH, this.quarter2);
    this._draw(renderer, this.blurV, this.quarter);
    this._draw(renderer, this.up, this.out);
  }
}
const BLOOM = 0.2;

export class Post {
  constructor(renderer, scene, camera) {
    const size = renderer.getDrawingBufferSize(new THREE.Vector2());
    const rt = new THREE.WebGLRenderTarget(size.x, size.y, { type: THREE.HalfFloatType });
    this.composer = new EffectComposer(renderer, rt);
    this.ao = new N8AOPass(scene, camera, size.x, size.y);
    this.ao.configuration.aoRadius = 2.2;
    this.ao.configuration.distanceFalloff = 1.0;
    this.ao.configuration.intensity = 2.2;
    this.ao.configuration.halfRes = true;
    this.ao.configuration.gammaCorrection = false;
    this.ao.setQualityMode('Medium');
    // N8AO turns on its transparency mode when the scene holds any transparent material (glass doors, car glass, the
    // tennis fence, the fountain spray): every frame it then walks the whole scene five times and draws it twice
    // more (a third of a phone's frame time) only to lift the AO off those few see-through pixels
    this.ao.autoDetectTransparency = false;
    this.ao.configuration.transparencyAware = false;
    this.render = new RenderPass(scene, camera);
    // The N8AO path has no MSAA (below), so it gets SMAA, and the small bloom; not on phones, where every full-screen
    // pass counts (the RenderPass path keeps its 4x MSAA and goes without bloom)
    this.smaa = MOBILE ? null : hdrSMAA(size.x, size.y);
    this.bloom = MOBILE ? null : new Bloom();
    this.film = new ShaderPass(FilmShader);
    this.film.uniforms.tBloom.value = this.bloom?.texture ?? null;
    this.output = new OutputPass();
    this.hq = true;
    this._build();
  }
  _build() {
    const c = this.composer;
    // MSAA only where the scene itself is drawn into the composer's targets (RenderPass). N8AO draws the scene into
    // its own single-sample target and then fills these with full-screen passes only: 4 samples there would just be
    // 4x the memory (two half-float screens) and a resolve after every pass.
    const samples = this.hq ? 0 : 4;
    for (const rt of [c.renderTarget1, c.renderTarget2]) {
      if (rt.samples !== samples) { rt.samples = samples; rt.dispose(); }
    }
    c.passes.length = 0;
    c.addPass(this.hq ? this.ao : this.render);
    if (this.hq && this.smaa) c.addPass(this.smaa);
    if (this.hq && this.bloom) c.addPass(this.bloom);
    c.addPass(this.film);
    c.addPass(this.output);
    this.film.uniforms.uBloom.value = this.hq && this.bloom ? BLOOM : 0;
  }
  setHQ(v) { this.hq = v; this._build(); }
  setFilm(v) { this.film.uniforms.uFilm.value = v ? 1 : 0; }
  setSize(w, h) {
    this.composer.setSize(w, h);
    this.film.uniforms.uRes.value.set(w * this.composer._pixelRatio, h * this.composer._pixelRatio);
  }
  draw(t) {
    this.film.uniforms.uTime.value = t;
    this.composer.render();
  }
}
