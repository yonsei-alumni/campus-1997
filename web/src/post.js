// Post-processing: N8AO ambient occlusion -> "1997 film" grade -> tone mapping/sRGB output.
import * as THREE from 'three';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { ShaderPass } from 'three/addons/postprocessing/ShaderPass.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';
import { N8AOPass } from 'n8ao';

const FilmShader = {
  uniforms: { tDiffuse: { value: null }, uTime: { value: 0 }, uFilm: { value: 0 }, uRes: { value: new THREE.Vector2(1, 1) } },
  vertexShader: `varying vec2 vUv; void main(){ vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position,1.0); }`,
  fragmentShader: `
    uniform sampler2D tDiffuse; uniform float uTime, uFilm; uniform vec2 uRes; varying vec2 vUv;
    float rnd(vec2 p){ return fract(sin(dot(p, vec2(12.9898,78.233)) + uTime*7.0) * 43758.5453); }
    void main(){
      vec4 c = texture2D(tDiffuse, vUv);
      // gentle spring haze for everyone
      c.rgb = mix(c.rgb, c.rgb * vec3(1.02, 1.0, 0.97), 0.6);
      if (uFilm > 0.0) {
        vec2 d = (vUv - 0.5);
        // slight lens softness + warm 35mm print look
        vec3 blur = (texture2D(tDiffuse, vUv + d * 0.004).rgb + texture2D(tDiffuse, vUv - d * 0.004).rgb) * 0.5;
        vec3 g = mix(c.rgb, blur, 0.5);
        float l = dot(g, vec3(0.299, 0.587, 0.114));
        g = mix(vec3(l), g, 0.82);                                 // desaturate
        g = g * vec3(1.08, 1.0, 0.86) + vec3(0.035, 0.02, 0.0);    // warm, lifted blacks
        g = pow(g, vec3(0.95));
        float vig = smoothstep(0.85, 0.25, length(d * vec2(1.25, 1.0)));
        g *= mix(0.62, 1.0, vig);
        g += (rnd(vUv * uRes) - 0.5) * 0.06;                       // grain
        c.rgb = mix(c.rgb, g, uFilm);
      }
      gl_FragColor = c;
    }`,
};

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
    this.film = new ShaderPass(FilmShader);
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
    c.addPass(this.film);
    c.addPass(this.output);
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
