import assert from 'node:assert/strict';
import { RoomScene } from './editor/scene.js';
import { photoProjection } from './editor/reference.js';
import * as THREE from './editor/vendor/three.module.js';
const identity=[1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1];
const wall={source:{identifier:'wall'},dimensions_m:[4,3,0],spatial:{transform:identity}};
const door={source:{identifier:'door'},kind:'doors',parent_identifier:'wall',dimensions_m:[1,2,0],spatial:{transform:identity.slice()},excluded:false};
door.spatial.transform[13]=-.5;
const geometry=()=>RoomScene.prototype.wallGeometry(wall,[wall,door]);
function area(g){const p=g.getAttribute('position');let a=0;for(let i=0;i<p.count;i+=3)a+=Math.abs((p.getX(i+1)-p.getX(i))*(p.getY(i+2)-p.getY(i))-(p.getY(i+1)-p.getY(i))*(p.getX(i+2)-p.getX(i)))/2;return a;}
assert.equal(area(geometry()),10,'Door removes exactly its 2 m² opening from a 12 m² wall');
door.excluded=true;assert.equal(area(geometry()),12,'Excluding the detection restores the wall plane');
door.excluded=false;door.spatial.transform[14]=.3;assert.equal(area(geometry()),12,'Noncoplanar door is not cut into the wall');
door.spatial.transform[14]=0;door.spatial.transform[12]=2;assert.equal(area(geometry()),11,'Out-of-bounds opening is clipped to the wall span');
const ref={camera_to_world_column_major:identity,intrinsics_column_major:[100,0,0,0,100,0,100,50,1],image_width:200,image_height:100};
const e={spatial:{transform:identity.slice()}};e.spatial.transform[14]=-2;
assert.deepEqual(photoProjection(e,ref),[.5,.5]);e.spatial.transform[13]=.5;assert.deepEqual(photoProjection(e,ref),[.5,.25]);
e.spatial.transform[14]=2;assert.equal(photoProjection(e,ref),null,'Behind-camera elements have no reference claim');
console.log('PASS: wall cuts, excluded apertures, off-plane apertures, boundary clipping, and ARKit photo projection.');

// Switching already-loaded photographic layers must preserve the comparison camera.
const camera=new THREE.PerspectiveCamera(62,1.5,.02,250);camera.position.set(1,2,3);camera.lookAt(0,1,0);
const before={position:camera.position.toArray(),quaternion:camera.quaternion.toArray(),fov:camera.fov,aspect:camera.aspect};
const context={camera,root:new THREE.Group(),captureRoot:new THREE.Group(),meshScan:new THREE.Group(),splatScan:new THREE.Group(),benchmarkScan:new THREE.Group(),renderer:{setClearColor(){}},draw(){},overlay:false};
for(const mode of ['benchmark','splat','mesh','benchmark']){
  await RoomScene.prototype.setLayer.call(context,mode);
  assert.deepEqual({position:camera.position.toArray(),quaternion:camera.quaternion.toArray(),fov:camera.fov,aspect:camera.aspect},before);
  assert.equal(context.benchmarkScan.visible,mode==='benchmark');assert.equal(context.splatScan.visible,mode==='splat');
}
console.log('PASS: benchmark switching preserves camera pose/FOV/aspect and displays one photographic layer.');
