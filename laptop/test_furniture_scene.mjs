import assert from 'node:assert/strict';
import fs from 'node:fs';
import * as THREE from './editor/vendor/three.module.js';
import { placementMatrix } from './editor/furniture.js';

// World-space model geometry stays at authored size; floor origin is not box center.
const catalog=JSON.parse(fs.readFileSync(new URL('./editor/models/catalog.json',import.meta.url)))[0];
const buffer=fs.readFileSync(new URL('./editor/models/sheen-chair/SheenChair.glb',import.meta.url));
const gltf=JSON.parse(buffer.subarray(20,20+buffer.readUInt32LE(12)).toString());
const bounds=new THREE.Box3();
for(const n of gltf.nodes){
  if(n.mesh===undefined)continue;
  const matrix=new THREE.Matrix4().compose(new THREE.Vector3(...(n.translation||[0,0,0])),new THREE.Quaternion(...(n.rotation||[0,0,0,1])),new THREE.Vector3(...(n.scale||[1,1,1])));
  for(const p of gltf.meshes[n.mesh].primitives){
    const a=gltf.accessors[p.attributes.POSITION];
    bounds.union(new THREE.Box3(new THREE.Vector3(...a.min),new THREE.Vector3(...a.max)).applyMatrix4(matrix));
  }
}
const size=bounds.getSize(new THREE.Vector3()).toArray();
size.forEach((v,i)=>assert.ok(Math.abs(v-catalog.dimensions_m[i])<1e-8));
bounds.translate(new THREE.Vector3(...catalog.model_offset_m));
assert.ok(Math.abs(bounds.min.y)<1e-9);
assert.ok(Math.abs(bounds.getCenter(new THREE.Vector3()).x)<1e-9);
assert.ok(Math.abs(bounds.getCenter(new THREE.Vector3()).z)<1e-9);
for(const yaw of [0,37,90,-120]){
  const position=[1,-1.538,-5.5];
  const m=placementMatrix({position_m:position,anchor:{yaw_degrees:yaw}});
  assert.deepEqual(new THREE.Vector3().applyMatrix4(m).toArray(),position);
  const w=catalog.dimensions_m[0],d=catalog.dimensions_m[2],r=yaw*Math.PI/180;
  const corner=new THREE.Vector3(w/2,0,d/2).applyMatrix4(m);
  assert.ok(Math.abs(corner.x-(position[0]+Math.cos(r)*w/2+Math.sin(r)*d/2))<1e-9);
  assert.ok(Math.abs(corner.z-(position[2]-Math.sin(r)*w/2+Math.cos(r)*d/2))<1e-9);
}
console.log('Furniture GLB bounds, floor origin, and yaw/footprint correspondence pass.');
