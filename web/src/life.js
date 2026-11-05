// Campus life: 1997 banners (현수막) across 백양로, students walking, cars on the road.
import * as THREE from 'three';
import { mulberry, wrapAngle } from './util.js';
import { play, locomotion } from './characters.js';

// ---------------------------------------------------------------- polyline helpers (campus frame)
const _a = new THREE.Vector2(), _b = new THREE.Vector2();

export class Path {
  constructor(pts, heightFn) {
    this.pts = pts.map(([x, y]) => new THREE.Vector2(x, y));
    this.cum = [0];
    for (let i = 1; i < this.pts.length; i++) this.cum.push(this.cum[i - 1] + this.pts[i].distanceTo(this.pts[i - 1]));
    this.length = this.cum[this.cum.length - 1];
    this.heightFn = heightFn;
    // cached heights every 2 m
    this.hs = [];
    for (let s = 0; s <= this.length + 2; s += 2) {
      const p = this.at(s);
      this.hs.push(heightFn(p.x, p.y));
    }
  }
  at(s, out = new THREE.Vector2()) {
    s = Math.max(0, Math.min(this.length, s));
    // binary search for the first vertex at or past s (called several times per walker and car every frame)
    const cum = this.cum;
    let lo = 1, hi = cum.length - 1;
    while (lo < hi) {
      const mid = (lo + hi) >> 1;
      if (cum[mid] < s) lo = mid + 1; else hi = mid;
    }
    const i = lo;
    const t = (s - this.cum[i - 1]) / (this.cum[i] - this.cum[i - 1] || 1);
    return out.copy(this.pts[i - 1]).lerp(this.pts[i], t);
  }
  dir(s, out = new THREE.Vector2()) {
    this.at(Math.max(0, s - 1), _a);
    return out.copy(this.at(Math.min(this.length, s + 1), _b)).sub(_a).normalize();
  }
  h(s) {
    const f = Math.max(0, s) / 2, i = Math.min(this.hs.length - 2, f | 0);
    return this.hs[i] + (this.hs[i + 1] - this.hs[i]) * (f - i);
  }
  offset(off) {
    const out = [];
    const step = 3, p = new THREE.Vector2(), d = new THREE.Vector2();
    for (let s = 0; s <= this.length; s += step) {
      this.at(s, p); this.dir(s, d);
      out.push([p.x - d.y * off, p.y + d.x * off]);
    }
    return out;
  }
}

// ---------------------------------------------------------------- banners
const BANNER_STYLE = {
  blue: { bg: '#1d3f9a', fg: '#ffffff', edge: '#0d2463' },
  white: { bg: '#f7f5ee', fg: '#1d2a6b', edge: '#c9c3b2', band: '#22348a' },
  // 1997 photo: white cloth, blue lettering, a yellow strip along the bottom with small red print
  white_yellow: { bg: '#f7f5ee', fg: '#1d2a6b', edge: '#c9c3b2', band: '#f1cf2c', bandFg: '#b8261e' },
  yellow: { bg: '#ffd83a', fg: '#1d3f9a', edge: '#c9a400' },
};
const FONT = '"Do Hyeon", "Jua", sans-serif';

function fitFont(x, text, size, maxW, min = 28) {
  x.font = `${size}px ${FONT}`;
  while (x.measureText(text).width > maxW && size > min) { size -= 2; x.font = `${size}px ${FONT}`; }
  return size;
}

// b: { text, sub?, marks?: ['경', '축'], color }
function bannerTexture(b) {
  const st = BANNER_STYLE[b.color] || BANNER_STYLE.white;
  const c = document.createElement('canvas');
  c.width = 2048; c.height = 192;
  const x = c.getContext('2d');
  const W = c.width, H = c.height;
  x.fillStyle = st.bg; x.fillRect(0, 0, W, H);
  x.fillStyle = st.edge; x.fillRect(0, 0, W, 8); x.fillRect(0, H - 8, W, 8);
  const marks = b.marks || null;
  const padX = marks ? 230 : 70;
  const bandH = st.band ? (b.color === 'white_yellow' ? 34 : 18) : 0;
  if (bandH) { x.fillStyle = st.band; x.fillRect(padX - 30, H - 8 - bandH, W - 2 * (padX - 30), bandH); }
  x.textAlign = 'center'; x.textBaseline = 'middle';
  let mainY = (H - bandH) / 2 + 6;
  if (b.sub && b.color !== 'white_yellow') {
    // small line above the main text (who is holding the event)
    fitFont(x, b.sub, 40, W * 0.55);
    x.fillStyle = st.fg; x.fillText(b.sub, W / 2, 34);
    mainY = 34 + (H - bandH - 34) / 2 + 12;
  }
  const big = b.sub && b.color === 'white_yellow' ? 96 : 112;
  fitFont(x, b.text, big, W - 2 * padX);
  x.fillStyle = st.fg;
  x.fillText(b.text, W / 2, b.sub && b.color === 'white_yellow' ? mainY - 22 : mainY);
  if (b.sub && b.color === 'white_yellow') {
    fitFont(x, b.sub, 40, W * 0.6);
    x.fillStyle = st.fg; x.fillText(b.sub, W / 2, mainY + 42);
  }
  if (bandH > 20 && st.bandFg) {
    x.font = `22px ${FONT}`; x.fillStyle = st.bandFg;
    x.fillText('일시 · 장소 · 주최  연세대학교', W / 2, H - 8 - bandH / 2 + 1);
  }
  if (marks) {
    // red circles with a white character at both ends (경 … 축)
    marks.forEach((m, i) => {
      const cx = i ? W - 120 : 120, cy = H / 2;
      x.fillStyle = '#d0232a'; x.beginPath(); x.arc(cx, cy, 66, 0, Math.PI * 2); x.fill();
      x.fillStyle = '#ffffff'; x.font = `92px ${FONT}`; x.fillText(m, cx, cy + 6);
    });
  }
  // cloth wrinkles
  const g = x.createLinearGradient(0, 0, W, 0);
  for (let i = 0; i <= 12; i++) g.addColorStop(i / 12, `rgba(0,0,0,${i % 2 ? 0.0 : 0.07})`);
  x.fillStyle = g; x.fillRect(0, 0, W, H);
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  t.anisotropy = 8;
  return t;
}

// banners can carry per-season texts ({seasons: {autumn: {text, color}}}): group.userData.setSeason swaps them
export function makeBanners(banners, lib, groundAt) {
  const group = new THREE.Group();
  group.name = 'banners';
  const cloths = [];
  const poleMat = lib.get('metal_dark');
  const poleGeo = new THREE.CylinderGeometry(0.06, 0.08, 6.6, 8);
  for (const b of banners) {
    const g = new THREE.Group();      // one banner (poles + cloth): hidden outside its season when it has `only`
    group.add(g);
    const A = new THREE.Vector3(b.a[0], 0, -b.a[1]), B = new THREE.Vector3(b.b[0], 0, -b.b[1]);
    A.y = groundAt(b.a[0], b.a[1]); B.y = groundAt(b.b[0], b.b[1]);
    for (const P of [A, B]) {
      const pole = new THREE.Mesh(poleGeo, poleMat);
      pole.position.set(P.x, P.y + 3.3, P.z);
      pole.castShadow = true;
      g.add(pole);
    }
    const len = A.distanceTo(B) - 0.2;
    const geo = new THREE.PlaneGeometry(len, 1.35, 24, 1);
    const pos = geo.attributes.position;
    for (let i = 0; i < pos.count; i++) {
      const u = pos.getX(i) / len + 0.5;
      pos.setY(i, pos.getY(i) - Math.sin(u * Math.PI) * 0.35);
      pos.setZ(i, Math.sin(u * Math.PI * 3) * 0.04);
    }
    geo.computeVertexNormals();
    const mat = new THREE.MeshStandardMaterial({ side: THREE.DoubleSide, roughness: 0.9 });
    cloths.push({ b, mat, g, key: null });
    const m = new THREE.Mesh(geo, mat);
    const mid = A.clone().add(B).multiplyScalar(0.5);
    m.position.set(mid.x, Math.max(A.y, B.y) + 5.6, mid.z);
    m.rotation.y = -Math.atan2(A.z - B.z, A.x - B.x);   // readable from the gate side
    m.castShadow = true;
    g.add(m);
  }
  group.userData.setSeason = (season) => {
    for (const c of cloths) {
      c.g.visible = (!c.b.only || c.b.only === season) && c.b.hide !== season;
      const spec = { ...c.b, ...(c.b.seasons?.[season] || {}) };
      const key = spec.text + spec.color;
      if (key === c.key) continue;
      c.key = key;
      c.mat.map?.dispose();
      c.mat.map = bannerTexture(spec);
      c.mat.needsUpdate = true;
    }
  };
  group.userData.setSeason(lib.season);
  return group;
}

// ---------------------------------------------------------------- students (Quaternius people, sim-office style)
// Walkers follow paths at their own pace and stop when you are in the way; groups stand and chat, nodding now and
// then. Far away people are hidden and their animation is not updated.
export class Crowd {
  constructor(scene, cast, ids, paths, groups, count, rndSeed = 3) {
    this.people = [];
    const rnd = mulberry(rndSeed);
    const pick = () => ids[Math.floor(rnd() * ids.length)];
    for (let i = 0; i < count; i++) {
      const a = cast.make(pick());
      const path = paths[Math.floor(rnd() * paths.length)];
      const p = { a, path, s: rnd() * path.length, dir: rnd() < 0.5 ? 1 : -1, speed: 1.15 + rnd() * 0.4, side: (rnd() - 0.5) * 0.8,
        heading: 0, walking: true, gestureAt: 5 + rnd() * 30, tick: i & 1 };
      a.mixer.setTime(rnd() * 2);
      scene.add(a.holder);
      this.people.push(p);
    }
    // standing groups (친구들과 수다): 2-4 people round a point, facing the middle
    for (const [gx, gy, h] of groups) {
      const n = 2 + Math.floor(rnd() * 3);
      for (let k = 0; k < n; k++) {
        const ang = (k / n) * Math.PI * 2 + rnd() * 0.4;
        const x = gx + Math.cos(ang) * 0.85, y = gy + Math.sin(ang) * 0.85;
        const a = cast.make(pick());
        a.mixer.setTime(rnd() * 2);
        a.holder.position.set(x, h, -y);
        const heading = Math.atan2(gx - x, -(gy - y));
        a.holder.rotation.y = heading;
        scene.add(a.holder);
        this.people.push({ a, walking: false, heading, home: heading, gestureAt: 3 + rnd() * 20, tick: k & 1, x, y });
      }
    }
    this.v = new THREE.Vector2();
    this.d = new THREE.Vector2();
    this.frame = 0;
  }
  // circles the player collides with (one reused circle per person: this runs every frame)
  movers(px, py, out = []) {
    out.length = 0;
    for (const p of this.people) {
      const x = p.a.holder.position.x, y = -p.a.holder.position.z;
      if (Math.abs(x - px) < 6 && Math.abs(y - py) < 6) {
        const c = (p.circle ||= { x: 0, y: 0, r: 0.3 });
        c.x = x; c.y = y;
        out.push(c);
      }
    }
    return out;
  }
  update(dt, t, player, camPos) {
    this.frame++;
    const v = this.v, d = this.d;
    for (const p of this.people) {
      const a = p.a, hp = a.holder.position;
      const far = (hp.x - camPos.x) ** 2 + (hp.z - camPos.z) ** 2;
      let speed = 0, want = null;
      if (p.walking) {
        p.path.at(p.s, v);
        p.path.dir(p.s, d).multiplyScalar(p.dir);
        // stop for the player standing in front, and look at them
        const tx = player.x - v.x, ty = player.y - v.y, td = Math.hypot(tx, ty);
        const ahead = (tx * d.x + ty * d.y) / (td || 1);
        const blocked = td < 1.3 && ahead > 0.2;
        if (!blocked) {
          speed = p.speed;
          p.s += p.dir * speed * dt;
          if (p.s > p.path.length) { p.s = p.path.length; p.dir = -1; }
          if (p.s < 0) { p.s = 0; p.dir = 1; }
          p.path.at(p.s, v);
          want = Math.atan2(d.x, -d.y);
        } else want = Math.atan2(tx, -ty);
        hp.set(v.x - d.y * p.side, p.path.h(p.s), -(v.y + d.x * p.side));
      } else {
        const tx = player.x - p.x, ty = player.y - p.y;
        want = Math.hypot(tx, ty) < 2.6 ? Math.atan2(tx, -ty) : p.home;      // turn to greet you
      }
      if (want !== null) {
        p.heading += wrapAngle(want - p.heading) * (1 - Math.exp(-dt * 7));
        a.holder.rotation.y = p.heading;
      }
      if (far > 190 * 190) { a.holder.visible = false; continue; }
      a.holder.visible = true;
      if (!p.walking && t > p.gestureAt) {
        p.gestureAt = t + 12 + Math.random() * 20;
        playGesture(a, Math.random() < 0.7 ? 'emote-yes' : 'interact-right');
      }
      locomotion(a, speed);
      // distant people animate at half rate
      if (far < 70 * 70) a.mixer.update(dt);
      else if ((this.frame & 1) === p.tick) a.mixer.update(dt * 2);
    }
  }
}

function playGesture(a, name) {
  if (!a.actions[name]) return;
  play(a, name, { once: true, fade: 0.3 });
}

// ---------------------------------------------------------------- traffic
// Cars from blender/cars.py: wheels spin with the distance travelled, brake lights come on when slowing,
// a seated driver (Quaternius 'sit' clip) behind the wheel; they keep their distance and stop for you.
// 1997 paint: lots of white, silver and dark navy, the mid-90s dark green (진녹색), a few wine / gunmetal / gold
export const CAR_COLORS = ['#eeeeea', '#f2f1ec', '#b9bdc3', '#a9aeb5', '#1b2333', '#2a2d33', '#6e1b1f', '#244a3a', '#1d3b30', '#3a3f45', '#b59a6a', '#2c4a78'];
// sedan 쏘나타Ⅱ type, sedan2 프린스 type, hatch 프라이드 type, tico 티코 type, van 그레이스 type (blender/cars.py)
const WEIGHTS = { sedan: 4, sedan2: 3, hatch: 3, tico: 2, taxi: 3, van: 2 };
// driver's hips in the car frame (blender/cars.py driver_seat, times CAR_SCALE 1.07)
const DRIVER = { sedan: [-0.05, 0.40], sedan2: [-0.03, 0.40], hatch: [-0.27, 0.39], tico: [-0.32, 0.33], taxi: [-0.05, 0.40], van: [0.98, 0.40] };

export class Traffic {
  constructor(scene, carGltfs, lanes, n = 12, cast = null, driverIds = [], rndSeed = 9) {
    this.cars = [];
    const rnd = mulberry(rndSeed);
    const bag = Object.entries(WEIGHTS).filter(([k]) => carGltfs[k]).flatMap(([k, w]) => Array(w).fill(k));
    for (let i = 0; i < n; i++) {
      const kind = bag[Math.floor(rnd() * bag.length)];
      const root = carGltfs[kind].scene.clone(true);
      const col = new THREE.Color(kind === 'taxi' ? '#ecebe4' : CAR_COLORS[Math.floor(rnd() * CAR_COLORS.length)]);
      const brake = [];
      const wheels = [];
      root.traverse((o) => {
        if (/^wheel_/.test(o.name)) wheels.push(o);
        if (!o.isMesh) return;
        o.castShadow = true;
        o.receiveShadow = true;
        if (o.material.name === 'car_paint') { o.material = o.material.clone(); o.material.color = col; }
        if (o.material.name === 'light_red') { o.material = o.material.clone(); brake.push(o.material); }
      });
      const box = new THREE.Box3().setFromObject(root);
      const len = box.max.x - box.min.x;
      let driver = null;
      if (cast && driverIds.length) {
        driver = cast.make(driverIds[Math.floor(rnd() * driverIds.length)]);
        play(driver, 'sit', { fade: 0 });
        const [dx, dy] = DRIVER[kind];
        // car frame: +X forward, Blender +Y (left, the driver's side) is three -Z; the 'sit' clip puts the hips 0.22 above
        // the holder, so 0.30 seats them low (~0.52 m) as in a real car and keeps the head under the roof
        driver.holder.position.set(dx, 0.30, -dy);
        driver.holder.rotation.y = Math.PI / 2;
        root.add(driver.holder);
      }
      scene.add(root);
      const lane = lanes[i % lanes.length];
      // wheel radius from the model, so the tyres roll without slipping
      const radius = wheels.length ? new THREE.Box3().setFromObject(wheels[0]).getSize(new THREE.Vector3()).y / 2 : 0.3;
      this.cars.push({ root, lane, s: (i / n) * lane.length * 2 % lane.length + rnd() * 20, speed: 8 + rnd() * 4,
        v: 8, len, wheels, brake, radius, driver, kind });
    }
  }
  update(dt, player) {
    const p = this.p ||= new THREE.Vector2(), d = this.d ||= new THREE.Vector2();
    for (const c of this.cars) {
      c.lane.at(c.s, p);
      c.lane.dir(c.s, d);
      // brake for the player standing in the lane ahead, and keep a gap to the car in front
      const rx = player.x - p.x, ry = player.y - p.y;
      const ahead = rx * d.x + ry * d.y, lateral = Math.abs(-rx * d.y + ry * d.x);
      const reach = c.len / 2 + 4;
      let target = c.speed;
      if (ahead > 0 && ahead < reach + 10 && lateral < 2.0) target = ahead < reach ? 0 : c.speed * (ahead - reach) / 10;
      for (const o of this.cars) {
        if (o === c || o.lane !== c.lane) continue;
        const gap = o.s - c.s - (o.len + c.len) / 2;
        if (gap > -1 && gap < 9) target = Math.min(target, gap < 3 ? 0 : o.v * 0.9);
      }
      const prev = c.v;
      c.v += (target - c.v) * Math.min(1, dt * (target < c.v ? 3.5 : 1.2));
      const braking = c.v < prev - 0.02 || c.v < 0.3;
      for (const m of c.brake) m.emissiveIntensity = braking ? 3.0 : 0.35;
      c.s += c.v * dt;
      if (c.s > c.lane.length) c.s = 0;
      c.lane.at(c.s, p);
      c.lane.dir(c.s, d);
      c.root.position.set(p.x, c.lane.h(c.s), -p.y);
      // car model: +X forward
      c.root.rotation.y = Math.atan2(d.y, d.x);
      for (const w of c.wheels) w.rotation.z -= (c.v * dt) / c.radius;
      if (c.driver) c.driver.mixer.update(dt);
    }
  }
  movers(px, py, out) {
    for (const c of this.cars) {
      const x = c.root.position.x, y = -c.root.position.z;
      if (Math.abs(x - px) > 12 || Math.abs(y - py) > 12) continue;
      const fx = Math.cos(c.root.rotation.y), fy = Math.sin(c.root.rotation.y);
      const n = Math.max(1, Math.round(c.len / 1.6));
      for (let k = 0; k < n; k++) {
        const t = (k / Math.max(1, n - 1) - 0.5) * (c.len - 1.6);
        out.push({ x: x + fx * t, y: y + fy * t, r: 0.9 });
      }
    }
    return out;
  }
}
