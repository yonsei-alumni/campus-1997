// Fallen leaves and petals (issue #18): October's ginkgo carpet and April's cherry petals under the trees.
// tools/build_campus.py bakes where they lie (ground_leaves.png over the splat's rectangle at 1 m: R ginkgo, G cherry,
// B the other broadleaves), tools/make_textures.py paints the ginkgo leaf tile (litter_ginkgo.png, alpha = each leaf's
// rank) and the petals are a dot pattern here. The near terrain's splat shader (terrain.js) and 백양로's own road mesh
// (its asphalt and pavers, materials.js) both lay the month's layer with litter().
import * as THREE from 'three';

// how much of each layer the month shows: x ginkgo leaves, y cherry petals, z the other broadleaves' leaves
export const FALL = { spring: [0, 1, 0], summer: [0, 0, 0], autumn: [1, 0, 0.75] };
// library materials that get the layer too (백양로's carriageway and sidewalks)
export const LITTER_MATS = new Set(['asphalt', 'pavers']);

// shared by every material that lays the layer (MaterialLibrary.uniforms); the rectangle is the splat's (terrain.js)
export function litterUniforms(loadTex) {
  return {
    uLeaf: { value: loadTex('assets/textures/ground_leaves.png', { srgb: false, repeat: false }) },
    uLitter: { value: loadTex('assets/textures/litter_ginkgo.png') },
    uLeafRect: { value: new THREE.Vector4(0, 0, 1, 1) },
    uFall: { value: new THREE.Vector3() },
  };
}

export const LITTER_GLSL = `
  uniform sampler2D uLeaf, uLitter;
  uniform vec4 uLeafRect;
  uniform vec3 uFall;
  float litHash(vec2 p) { vec3 p3 = fract(vec3(p.xyx) * .1031); p3 += dot(p3, p3.yzx + 33.33); return fract((p3.x + p3.y) * p3.z); }
  float litNoise(vec2 p) {
    vec2 i = floor(p), f = fract(p);
    f = f * f * (3.0 - 2.0 * f);
    return mix(mix(litHash(i), litHash(i + vec2(1.0, 0.0)), f.x), mix(litHash(i + vec2(0.0, 1.0)), litHash(i + vec2(1.0, 1.0)), f.x), f.y);
  }
  // one layer of petals: a petal in some cells of a grid of 1/s m, as many as the density d asks for
  float litPetals(vec2 q, float d, inout float tone) {
    vec2 c = floor(q), f = fract(q) - 0.5;
    float h = litHash(c);
    if (h >= d) return 0.0;
    vec2 o = vec2(litHash(c + 7.31), litHash(c + 3.97)) - 0.5;
    float a = h * 41.0, ca = cos(a), sa = sin(a);
    vec2 p = f - o * 0.36;
    p = vec2(ca * p.x - sa * p.y, sa * p.x + ca * p.y);
    tone = litHash(c + 11.3);
    return 1.0 - smoothstep(0.27, 0.34, length(p * vec2(1.0, 1.5)));
  }
  // the month's fallen leaves / petals at campus point wp (x east, y north): their coverage (0..1), and their colour
  // in col. (Call it in uniform control flow: the screen-space derivatives are taken before any branch.)
  float litter(vec2 wp, out vec3 col) {
    col = vec3(0.0);
    vec2 dwx = dFdx(wp), dwy = dFdy(wp);
    float px = sqrt(length(dwx) * length(dwy));                // metres per pixel on the ground
    vec2 luv = vec2((wp.x - uLeafRect.x) / (uLeafRect.z - uLeafRect.x), (uLeafRect.w - wp.y) / (uLeafRect.w - uLeafRect.y));
    vec3 m = texture2D(uLeaf, luv).rgb * uFall * step(0.0, luv.x) * step(luv.x, 1.0) * step(0.0, luv.y) * step(luv.y, 1.0);
    if (m.x + m.y + m.z < 0.004) return 0.0;
    // fray the soft 1 m mask: drifts and bare patches rather than smooth discs
    float nz = litNoise(wp * 0.43) * 0.6 + litNoise(wp * 1.7 + 5.3) * 0.4;
    float cov = 0.0;
    if (m.x + m.z > 0.004) {
      // a leaf of the tile shows where its rank clears the threshold that covers a share d of the ground (the
      // tile's coverage above rank t is about 1 - exp(-4.6 (1 - t))). Once the leaves shrink to a pixel or two
      // the mip levels average the ranks, and the share itself takes over.
      float near = 1.0 - smoothstep(0.005, 0.016, px);
      mat2 tr = mat2(0.8, -0.6, 0.6, 0.8) * 1.1;                    // turned, for the other leaves
      vec4 lg = textureGrad(uLitter, wp * 1.25, dwx * 1.25, dwy * 1.25);   // 0.8 m tiles
      vec4 lo = textureGrad(uLitter, tr * wp + 0.37, tr * dwx, tr * dwy);
      float dg = clamp(m.x * (0.6 + 1.0 * nz), 0.0, 1.0);
      float dO = clamp(m.z * (0.3 + 0.9 * nz), 0.0, 0.8);
      float tg = 1.0 + log(max(1.0 - 0.97 * dg, 0.001)) / 4.6;
      float to = 1.0 + log(max(1.0 - 0.97 * dO, 0.001)) / 4.6;
      float cg = mix(dg * 0.97, smoothstep(tg - 0.03, tg + 0.01, lg.a), near) * smoothstep(0.0, 0.04, dg);
      float co = mix(dO * 0.97, smoothstep(to - 0.03, to + 0.01, lo.a), near) * smoothstep(0.0, 0.04, dO);
      // the zelkovas', oaks' and cherries' leaves rust-brown, a maple's red here and there
      vec3 oc = lo.rgb * mix(vec3(0.78, 0.46, 0.26), vec3(0.85, 0.3, 0.16), step(0.8, litHash(floor(wp * 0.25))));
      cov = 1.0 - (1.0 - cg) * (1.0 - co);
      col = (lg.rgb * 0.82 * cg + oc * co * (1.0 - cg)) / max(cov, 1e-4);
    }
    if (m.y > 0.004) {
      // petals 1-2 cm long: a pattern while they are a few pixels across, their share of the ground beyond
      // (drifted into little heaps and swept thin between them)
      float dp = clamp(m.y * (0.4 + 1.0 * nz) * (0.5 + 0.8 * litNoise(wp * 2.9 + 1.7)), 0.0, 1.0);
      float tone = 0.0, t2 = 0.0;
      float cp = max(litPetals(wp * 38.0, dp, tone), litPetals(wp * 47.0 + 0.5, dp, t2));
      cp = mix(dp * 0.45, cp, 1.0 - smoothstep(0.004, 0.011, px));                 // (two layers: ~0.45 d)
      vec3 pc = mix(vec3(0.88, 0.52, 0.62), vec3(0.95, 0.76, 0.82), max(tone, t2));
      col = mix(col, pc, cp);
      cov = 1.0 - (1.0 - cov) * (1.0 - cp);
    }
    return cov;
  }`;

// the layer on a library material (백양로's asphalt and pavers): on its upward faces, over the diffuse colour, with
// the leaves' own roughness and the texture's relief pressed flat under them
export function litterEdit(uniforms) {
  const { uLeaf, uLitter, uLeafRect, uFall } = uniforms;
  return (sh) => {
    Object.assign(sh.uniforms, { uLeaf, uLitter, uLeafRect, uFall });
    sh.vertexShader = sh.vertexShader
      .replace('#include <common>', '#include <common>\nvarying vec3 vLitW;')
      .replace('#include <worldpos_vertex>', `#include <worldpos_vertex>
        {
          vec4 lw = vec4(transformed, 1.0);
          #ifdef USE_INSTANCING
            lw = instanceMatrix * lw;
          #endif
          vLitW = (modelMatrix * lw).xyz;
        }`);
    sh.fragmentShader = sh.fragmentShader
      .replace('#include <common>', `#include <common>\nvarying vec3 vLitW;\nfloat litCov = 0.0;\n${LITTER_GLSL}`)
      .replace('#include <color_fragment>', `#include <color_fragment>
        {
          vec3 litCol;
          float up = smoothstep(0.55, 0.85, dot(viewMatrix[1].xyz, normalize(vNormal)));
          litCov = litter(vec2(vLitW.x, -vLitW.z), litCol) * up;
          diffuseColor.rgb = mix(diffuseColor.rgb, litCol, litCov);
        }`)
      .replace('#include <roughnessmap_fragment>', `#include <roughnessmap_fragment>
        roughnessFactor = mix(roughnessFactor, 0.8, litCov);`)
      .replace('#include <normal_fragment_maps>',
        THREE.ShaderChunk.normal_fragment_maps.replace('mapN.xy *= normalScale;', 'mapN.xy *= normalScale * (1.0 - 0.8 * litCov);'));
  };
}
