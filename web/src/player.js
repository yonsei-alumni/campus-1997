// Third-person walker in the manner of sim-office (office/engine/movement.js + camera.js):
// ↑↓ / W S walk forward and back, ← → / A D turn, Shift runs; the camera follows behind and above.
// Mouse drag swings the camera round (it settles back behind you when you walk), the wheel zooms.
// Collisions: building footprints and circles (trees, lamps, statues, people); ground follows the
// terrain, the 백양로 curbs and the amphitheater terraces through a BVH raycast.
import * as THREE from 'three';
import { computeBoundsTree, acceleratedRaycast } from 'three-mesh-bvh';
import { locomotion } from './characters.js';

THREE.BufferGeometry.prototype.computeBoundsTree = computeBoundsTree;
THREE.Mesh.prototype.raycast = acceleratedRaycast;

const RADIUS = 0.32, STEP = 0.55;
export const WALK = 2.4, RUN = 6.2, TURN = 2.3;

export class Colliders {
  constructor(cell = 24) {
    this.cell = cell;
    this.grid = new Map();
  }
  _keys(minx, miny, maxx, maxy) {
    const c = this.cell, out = [];
    for (let i = Math.floor(minx / c); i <= Math.floor(maxx / c); i++)
      for (let j = Math.floor(miny / c); j <= Math.floor(maxy / c); j++) out.push(i + ',' + j);
    return out;
  }
  _put(o, minx, miny, maxx, maxy) {
    for (const k of this._keys(minx, miny, maxx, maxy)) {
      if (!this.grid.has(k)) this.grid.set(k, []);
      this.grid.get(k).push(o);
    }
  }
  addPolygon(pts) {   // campus frame [[x,y],...]
    let minx = 1e9, miny = 1e9, maxx = -1e9, maxy = -1e9;
    for (const [x, y] of pts) { minx = Math.min(minx, x); maxx = Math.max(maxx, x); miny = Math.min(miny, y); maxy = Math.max(maxy, y); }
    this._put({ type: 'poly', pts }, minx, miny, maxx, maxy);
  }
  addCircle(x, y, r) {
    this._put({ type: 'circle', x, y, r }, x - r, y - r, x + r, y + r);
  }
  near(x, y) {
    const c = this.cell;
    const res = new Set();
    for (let i = -1; i <= 1; i++)
      for (let j = -1; j <= 1; j++) {
        const a = this.grid.get((Math.floor(x / c) + i) + ',' + (Math.floor(y / c) + j));
        if (a) a.forEach((o) => res.add(o));
      }
    return res;
  }
  insideBuilding(x, y) {
    const a = this.grid.get(Math.floor(x / this.cell) + ',' + Math.floor(y / this.cell));
    return !!a && a.some((o) => o.type === 'poly' && pointInPoly(x, y, o.pts));
  }
  // push a circle (x,y,r) out of every collider (and the moving circles); returns corrected [x,y]
  resolve(x, y, r, movers = []) {
    for (let it = 0; it < 3; it++) {
      for (const o of this.near(x, y)) {
        if (o.type === 'circle') {
          const dx = x - o.x, dy = y - o.y, d = Math.hypot(dx, dy), m = o.r + r;
          if (d < m && d > 1e-6) { x = o.x + dx / d * m; y = o.y + dy / d * m; }
        } else {
          const p = o.pts;
          const inside = pointInPoly(x, y, p);
          let best = 1e9, bx = 0, by = 0;
          for (let i = 0; i < p.length; i++) {
            const [ax, ay] = p[i], [cx, cy] = p[(i + 1) % p.length];
            const ex = cx - ax, ey = cy - ay;
            const t = Math.max(0, Math.min(1, ((x - ax) * ex + (y - ay) * ey) / (ex * ex + ey * ey || 1)));
            const qx = ax + ex * t, qy = ay + ey * t;
            const d = Math.hypot(x - qx, y - qy);
            if (d < best) { best = d; bx = qx; by = qy; }
          }
          if (inside) {
            const dx = bx - x, dy = by - y, d = Math.hypot(dx, dy) || 1;
            x = bx + dx / d * r; y = by + dy / d * r;
          } else if (best < r) {
            const dx = x - bx, dy = y - by, d = best || 1;
            x = bx + dx / d * r; y = by + dy / d * r;
          }
        }
      }
      for (const m of movers) {
        const dx = x - m.x, dy = y - m.y, d = Math.hypot(dx, dy), mm = m.r + r;
        if (d < mm && d > 1e-6) { x = m.x + dx / d * mm; y = m.y + dy / d * mm; }
      }
    }
    return [x, y];
  }
}

export function pointInPoly(x, y, p) {
  let c = false;
  for (let i = 0, j = p.length - 1; i < p.length; j = i++) {
    const [xi, yi] = p[i], [xj, yj] = p[j];
    if ((yi > y) !== (yj > y) && x < (xj - xi) * (y - yi) / (yj - yi) + xi) c = !c;
  }
  return c;
}

export class Player {
  constructor(camera, dom, colliders, walkables, hf, actor) {
    this.camera = camera;
    this.dom = dom;
    this.col = colliders;
    this.walk = walkables;
    this.hf = hf;
    this.setActor(actor);
    this.vy = 0;
    this.speed = 0;
    this.heading = 0;                 // facing: forward = (sin h, cos h) in three's XZ
    this.keys = new Set();
    this.enabled = false;
    this.stick = new THREE.Vector2();
    this.movers = [];
    this.ray = new THREE.Raycaster();
    this.ray.firstHitOnly = true;
    this.down = new THREE.Vector3(0, -1, 0);
    // camera rig
    this.cam = { pos: new THREE.Vector3(), look: new THREE.Vector3(), ready: false, orbit: 0, lift: 0, dist: 5.4, drag: null };
    addEventListener('keydown', (e) => { if (!/INPUT|TEXTAREA/.test(e.target.tagName)) this.keys.add(e.code); if (/Arrow|Space/.test(e.code) && this.enabled) e.preventDefault(); });
    addEventListener('keyup', (e) => this.keys.delete(e.code));
    addEventListener('blur', () => this.keys.clear());
    dom.addEventListener('pointerdown', (e) => {
      if (!this.enabled || e.target !== dom) return;
      this.cam.drag = { id: e.pointerId, x: e.clientX, y: e.clientY };
      dom.setPointerCapture(e.pointerId);
    });
    dom.addEventListener('pointermove', (e) => {
      const d = this.cam.drag;
      if (!d || d.id !== e.pointerId) return;
      this.cam.orbit -= (e.clientX - d.x) * 0.006;
      this.cam.lift = Math.max(-0.35, Math.min(1.1, this.cam.lift + (e.clientY - d.y) * 0.004));
      d.x = e.clientX; d.y = e.clientY;
    });
    const up = () => { this.cam.drag = null; };
    dom.addEventListener('pointerup', up);
    dom.addEventListener('pointercancel', up);
    dom.addEventListener('wheel', (e) => {
      if (!this.enabled) return;
      e.preventDefault();
      this.cam.dist = Math.max(2.4, Math.min(16, this.cam.dist * (e.deltaY > 0 ? 1.1 : 0.9)));
    }, { passive: false });
  }

  setActor(actor) {
    if (this.actor) {
      const old = this.actor.holder;
      actor.holder.position.copy(old.position);
      old.parent?.remove(old);
    }
    this.actor = actor;
    this.pos = actor.holder.position;
  }

  // campus (x east, y north) placement; yaw: view direction with forward = (-sin yaw, -cos yaw) in three (0 = north)
  teleport(x, y, yaw = null) {
    const h = this.groundAt(x, -y, 400);
    this.pos.set(x, h ?? this.hf.height(x, y), -y);
    this.vy = 0;
    if (yaw !== null) this.heading = yaw + Math.PI;
    this.actor.holder.rotation.y = this.heading;
    this.cam.ready = false;
    this.cam.orbit = 0;
  }

  groundAt(x, z, from = null) {
    const top = from ?? this.pos.y + STEP;
    this.ray.set(new THREE.Vector3(x, top, z), this.down);
    this.ray.far = from ? 1000 : STEP + 60;
    const hits = this.ray.intersectObjects(this.walk, false);
    return hits.length ? hits[0].point.y : null;
  }

  input() {
    const k = this.keys;
    let fwd = 0, turn = 0;
    if (k.has('ArrowUp') || k.has('KeyW')) fwd += 1;
    if (k.has('ArrowDown') || k.has('KeyS')) fwd -= 1;
    if (k.has('ArrowLeft') || k.has('KeyA')) turn += 1;
    if (k.has('ArrowRight') || k.has('KeyD')) turn -= 1;
    if (this.stick.lengthSq() > 0.01) { fwd += -this.stick.y; turn += -this.stick.x * 0.9; }
    const run = k.has('ShiftLeft') || k.has('ShiftRight') || this.stick.length() > 0.95;
    return { fwd: Math.max(-1, Math.min(1, fwd)), turn: Math.max(-1, Math.min(1, turn)), run };
  }

  update(dt) {
    const inp = this.enabled ? this.input() : { fwd: 0, turn: 0, run: false };
    this.heading += inp.turn * TURN * dt;
    const target = inp.fwd * (inp.run && inp.fwd > 0 ? RUN : WALK * (inp.fwd < 0 ? 0.6 : 1));
    this.speed += (target - this.speed) * Math.min(1, dt * 10);
    if (Math.abs(this.speed) < 0.05 && !target) this.speed = 0;
    let nx = this.pos.x + Math.sin(this.heading) * this.speed * dt;
    let nz = this.pos.z + Math.cos(this.heading) * this.speed * dt;
    if (this.speed) {
      const [cx, cy] = this.col.resolve(nx, -nz, RADIUS, this.movers);
      nx = cx; nz = -cy;
    }
    // ground: step up curbs and terraces, fall down slopes
    this.vy -= 14 * dt;
    let ny = this.pos.y + this.vy * dt;
    const g = this.groundAt(nx, nz) ?? this.hf.height(nx, -nz);
    if (ny <= g + 0.02 || (this.vy <= 0 && ny < g + 0.35)) { ny = g; this.vy = 0; }
    this.pos.set(nx, ny, nz);
    this.actor.holder.rotation.y = this.heading;
    locomotion(this.actor, this.speed, WALK + 0.5);
    this.actor.mixer.update(dt);
    this.updateCamera(dt, inp);
  }

  updateCamera(dt, inp = { fwd: 0, turn: 0 }) {
    const c = this.cam, p = this.pos;
    // walking: the camera swings back behind you
    if (!c.drag && (inp.fwd || inp.turn)) c.orbit *= Math.exp(-dt * 1.6);
    const a = this.heading + c.orbit;
    const back = c.dist * Math.cos(0.36 + c.lift * 0.5), high = 1.25 + c.dist * Math.sin(0.36 + c.lift * 0.5);
    const want = new THREE.Vector3(p.x - Math.sin(a) * back, p.y + high, p.z - Math.cos(a) * back);
    // keep the camera out of buildings: walk the line from the head and stop before a wall
    const head = new THREE.Vector3(p.x, p.y + 1.5, p.z);
    const steps = 12;
    for (let i = 1; i <= steps; i++) {
      const q = head.clone().lerp(want, i / steps);
      if (this.col.insideBuilding(q.x, -q.z)) { want.copy(head.clone().lerp(want, Math.max(0, (i - 1.5) / steps))); want.y += 0.6; break; }
    }
    const gy = this.hf.height(want.x, -want.z);
    if (want.y < gy + 0.6) want.y = gy + 0.6;
    const look = new THREE.Vector3(p.x + Math.sin(this.heading) * 1.2, p.y + 1.45, p.z + Math.cos(this.heading) * 1.2);
    const k = c.ready ? 1 - Math.exp(-dt * 4.5) : 1;
    c.ready = true;
    c.pos.lerp(want, k);
    c.look.lerp(look, k);
    this.camera.position.copy(c.pos);
    this.camera.lookAt(c.look);
  }

  // campus frame helpers
  get x() { return this.pos.x; }
  get y() { return -this.pos.z; }
  // view direction for the heading-up minimap (old first-person convention: forward = (-sin yaw, -cos yaw))
  get yaw() { return this.heading + this.cam.orbit + Math.PI; }
}
