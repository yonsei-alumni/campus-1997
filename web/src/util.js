// Small helpers shared by the game modules.
import * as THREE from 'three';

export const $ = (s) => document.querySelector(s);

// Phones / tablets: no shadow maps, smaller textures, fewer people, the touch stick.
export const MOBILE = matchMedia('(pointer: coarse)').matches;

export const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
export const wrapAngle = (a) => Math.atan2(Math.sin(a), Math.cos(a));

// localStorage can throw (private mode, blocked site data)
export function safeGet(k) { try { return localStorage.getItem(k); } catch { return null; } }
export function safeSet(k, v) { try { localStorage.setItem(k, v); } catch { /* ignore */ } }

// seeded PRNG: the same campus every visit
export function mulberry(a) {
  return function () {
    a |= 0; a = a + 0x6D2B79F5 | 0;
    let t = Math.imul(a ^ a >>> 15, 1 | a);
    t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t;
    return ((t ^ t >>> 14) >>> 0) / 4294967296;
  };
}

// {key: number of items} for a list, keyed by keyFn
export function countBy(list, keyFn) {
  const out = {};
  list.forEach((v, i) => { const k = keyFn(v, i); out[k] = (out[k] || 0) + 1; });
  return out;
}

export function polylineLength(pts) {
  let L = 0;
  for (let i = 1; i < pts.length; i++) L += Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]);
  return L;
}

// closest point to (x, y) on the segment a-b: [qx, qy, distance]
export function closestOnSegment(x, y, ax, ay, bx, by) {
  const ex = bx - ax, ey = by - ay;
  const t = clamp(((x - ax) * ex + (y - ay) * ey) / (ex * ex + ey * ey || 1), 0, 1);
  const qx = ax + ex * t, qy = ay + ey * t;
  return [qx, qy, Math.hypot(x - qx, y - qy)];
}

// instance matrix for an object standing at campus (x, y) on height h, turned by rot about the vertical
const _p = new THREE.Vector3(), _q = new THREE.Quaternion(), _s = new THREE.Vector3();
const UP = new THREE.Vector3(0, 1, 0);
export function placeMatrix(out, x, h, y, rot = 0, scale = 1) {
  _p.set(x, h, -y);
  _q.setFromAxisAngle(UP, rot);
  if (typeof scale === 'number') _s.setScalar(scale); else _s.copy(scale);
  return out.compose(_p, _q, _s);
}
