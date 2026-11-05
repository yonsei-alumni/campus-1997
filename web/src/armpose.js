// Procedural arm pose for the shared Quaternius rig: both hands go to given points (two-bone IK), blended over the clip's own arm
// motion. The bones run along their local +Y, so a bone is "aimed" by turning its +Y towards a world direction. Call update()
// each frame AFTER the animation mixer has run and before the frame is rendered.
import * as THREE from 'three';

const _p = new THREE.Quaternion(), _w = new THREE.Quaternion(), _r = new THREE.Quaternion();
const _a = new THREE.Vector3(), _b = new THREE.Vector3(), _c = new THREE.Vector3(), _d = new THREE.Vector3();
const UP = new THREE.Vector3(0, 1, 0);

function aim(bone, dir) {
  bone.parent.getWorldQuaternion(_p);
  _w.copy(_p).multiply(bone.quaternion);
  _a.copy(UP).applyQuaternion(_w);
  _r.setFromUnitVectors(_a, dir);
  _w.premultiply(_r);
  bone.quaternion.copy(_p.invert().multiply(_w)).normalize();
  bone.updateWorldMatrix(false, true);
}

export class ArmPose {
  constructor(actor) {
    this.setActor(actor);
  }

  setActor(actor) {
    this.actor = actor;
    const f = (n) => actor.root.getObjectByName(n);
    this.arms = ['L', 'R'].map((s) => ({ up: f('UpperArm' + s), low: f('LowerArm' + s), wrist: f('Wrist' + s), s }));
    this.body = f('Body');
    this.ok = this.arms.every((a) => a.up && a.low && a.wrist) && !!this.body;
  }

  // targets: [leftHandWorld, rightHandWorld]; hints: matching elbow direction hints (world vectors); w: 0..1 blend
  // bodyUp: metres to lift the hips (a hop)
  apply(targets, hints, w, bodyUp = 0) {
    if (!this.ok || (w <= 0.001 && !bodyUp)) return;
    this.actor.holder.updateMatrixWorld(true);
    if (bodyUp) this.body.position.y += bodyUp;
    if (w <= 0.001) return;
    this.arms.forEach((arm, i) => {
      const q0 = arm.up.quaternion.clone(), q1 = arm.low.quaternion.clone();
      arm.up.getWorldPosition(_b);                         // shoulder joint
      arm.low.getWorldPosition(_c);                        // elbow
      arm.wrist.getWorldPosition(_d);
      const l1 = _b.distanceTo(_c), l2 = _c.distanceTo(_d);
      const S = _b.clone(), H = targets[i].clone();
      const v = H.clone().sub(S);
      let d = v.length();
      d = Math.min(Math.max(d, Math.abs(l1 - l2) + 0.02), l1 + l2 - 0.01);
      v.normalize();
      const a = (l1 * l1 - l2 * l2 + d * d) / (2 * d);
      const h = Math.sqrt(Math.max(0, l1 * l1 - a * a));
      const pole = hints[i].clone();
      pole.addScaledVector(v, -pole.dot(v)).normalize();
      const E = S.clone().addScaledVector(v, a).addScaledVector(pole, h);
      const Hn = S.clone().addScaledVector(v, d);
      aim(arm.up, E.clone().sub(S).normalize());
      aim(arm.low, Hn.sub(E).normalize());
      if (w < 0.999) {                                     // blend towards the pose from the clip's own arms
        const n0 = arm.up.quaternion.clone(), n1 = arm.low.quaternion.clone();
        arm.up.quaternion.copy(q0).slerp(n0, w);
        arm.low.quaternion.copy(q1).slerp(n1, w);
        arm.up.updateWorldMatrix(false, true);
      }
    });
  }
}
