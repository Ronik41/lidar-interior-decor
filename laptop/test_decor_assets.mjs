import assert from 'node:assert/strict';
import fs from 'node:fs';
import * as T from './editor/vendor/three.module.js';
import {placementMatrix} from './editor/furniture.js';
const catalog=JSON.parse(fs.readFileSync(new URL('./editor/models/catalog.json',import.meta.url)));
for(const item of catalog.slice(1)){
 const buffer=fs.readFileSync(new URL('./editor'+item.model_url,import.meta.url)),gltf=JSON.parse(buffer.subarray(20,20+buffer.readUInt32LE(12)).toString());
 const box=new T.Box3();for(const mesh of gltf.meshes)for(const p of mesh.primitives){const a=gltf.accessors[p.attributes.POSITION];box.union(new T.Box3(new T.Vector3(...a.min),new T.Vector3(...a.max)));}
 const size=box.getSize(new T.Vector3()).toArray();size.forEach((v,i)=>assert.ok(Math.abs(v-item.dimensions_m[i])<1e-8,item.id+' actual bounds'));
 box.translate(new T.Vector3(...item.model_offset_m));assert.ok(Math.abs(box.min.y)<1e-8);const centre=box.getCenter(new T.Vector3());assert.ok(Math.abs(centre.x)<1e-8&&Math.abs(centre.z)<1e-8);assert.equal(item.collision.type,'box');assert.ok(item.anchor_type);assert.equal(item.license,'CC0-1.0');
}
const art=catalog.find(m=>m.anchor_type==='wall'),position=[2,1,3],h=art.dimensions_m[1];
for(const roll of [-90,-15,0,45,180]){const m=placementMatrix({position_m:position,yaw_degrees:72,dimensions_m:art.dimensions_m,anchor:{type:'wall',roll_degrees:roll}}),center=new T.Vector3(0,h/2,0).applyMatrix4(m);assert.ok(center.distanceTo(new T.Vector3(2,1+h/2,3))<1e-8,'wall rotation preserves mounting centre');}
console.log('PASS: local decor GLB bounds, floor contact origins, catalog metadata, wall rotation centre.');
