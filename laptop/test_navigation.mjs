import assert from 'node:assert/strict';
import {NavigationWorld,BODY_RADIUS,inside} from './editor/navigation.js';
const identity=[1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1];
const floor={identifier:'floor',points:[[-3,-4],[3,-4],[3,4],[-3,4]],transform:[1,0,0,0,0,0,1,0,0,-1,0,0,0,0,0,1]};
const wall={id:'wall',transform:[...identity.slice(0,12),0,1.4,0,1],width:6,height:2.8,holes:[{rect:[-.6,-1.4,.6,.9],passable:true,kind:'openings'}]};
const scene={id:'synthetic',floors:[floor],walls:[wall],objects:[]};
const nav=new NavigationWorld(scene);
let p=nav.move([1,-1],[0,5]);assert.ok(p[1]<=-BODY_RADIUS&&p[1]>-.27,'walk into wall stops');
p=nav.move([1,-1],[1.2,2]);assert.ok(p[0]>2&&p[1]<=-BODY_RADIUS,'diagonal wall slide');
p=nav.move([0,-1],[0,2]);assert.ok(p[1]>.99,'opening is passable');
p=nav.move([0,-1],[0,-10]);assert.ok(p[1]>=-4+BODY_RADIUS&&p[1]<-3.7,'floor edge stops');
const closed=structuredClone(scene);closed.walls[0].holes[0].passable=false;
assert.ok(new NavigationWorld(closed).move([0,-1],[0,2])[1]<0,'closed door/window blocks');
const chair={id:'chair',position_m:[0,0,-2],yaw_degrees:0,anchor:{},model:{collision:{dimensions_m:[.827,.687,.57]}}};
const furnished=new NavigationWorld(scene,[chair]);p=furnished.move([0,-3],[0,2]);assert.ok(p[1]<-2.4,'placed chair blocks');
for(let i=0;i<100;i++){const angle=i*2.39996;p=furnished.move([2,-3],[Math.cos(angle)*10,Math.sin(angle)*10]);assert.ok(furnished.valid(p),'long moves never tunnel through thin barriers');}
const badObject={id:'bad',reliable:true,points:[[-.5,-3],[.5,-3],[.5,-1],[-.5,-1]],bottom:0,top:1};
const obstructed={...scene,objects:[badObject]};assert.ok(!new NavigationWorld(obstructed).valid([0,-2]));assert.ok(new NavigationWorld(obstructed,[],{bad:{enabled:false}}).valid([0,-2]),'ignore correction reopens route');
const corrected=new NavigationWorld(obstructed,[],{bad:{enabled:true,box:{x_m:2,z_m:-2,width_m:.5,depth_m:.5,yaw_degrees:10}}});assert.ok(corrected.valid([0,-2]));assert.ok(!corrected.valid([2,-2]));
const concave={...scene,walls:[],floors:[{...floor,points:[[0,0],[4,0],[4,4],[3,4],[3,1],[1,1],[1,4],[0,4]]}]};
const notch=new NavigationWorld(concave);p=notch.move([.5,2],[3,0]);assert.ok(p[0]<1,'cannot cross concave notch');
const rotated=structuredClone(scene),angle=.73,c=Math.cos(angle),s=Math.sin(angle),rotate=p=>[c*p[0]+s*p[1]+20,-s*p[0]+c*p[1]-10];
rotated.id='alternate';rotated.floors[0].points=rotated.floors[0].points.map(rotate);rotated.walls[0].transform=[c,0,-s,0,0,1,0,0,s,0,c,0,20,1.4,-10,1];
const another=new NavigationWorld(rotated);assert.ok(!another.valid([0,-1]));assert.ok(another.valid(rotate([0,-1])));assert.equal(another.obstacles.length,0,'room swap does not leak placed furniture');
p=another.move(rotate([1,-1]),[s*2,c*2]);const localZ=s*(p[0]-20)+c*(p[1]+10);assert.ok(localZ<-.21,'rotated wall blocks in scene coordinates');
console.log('PASS: stop, diagonal slide, opening, closed door, floor edge, rotated chair, no tunnelling, obstacle correction, concave floor, alternate transformed room.');

// Exercise the actual camera movement/entry path with a non-identity display transform.
const {RoomScene}=await import('./editor/scene.js');const T=await import('./editor/vendor/three.module.js');
const display=new T.Matrix4().makeRotationY(.63).toArray();
const ctx={state:{scene:{...scene,scene_to_display:display}},nav,camera:new T.PerspectiveCamera(),controls:{target:new T.Vector3()},draw(){}};
for(const name of ['toScene','toDisplay','walk','constrainCamera'])ctx[name]=RoomScene.prototype[name];
ctx.camera.position.copy(ctx.toDisplay(new T.Vector3(1,20,-1)));ctx.controls.target.copy(ctx.camera.position).add(new T.Vector3(0,0,1));ctx.constrainCamera();
assert.ok(Math.abs(ctx.toScene(ctx.camera.position).y-1.6)<1e-9,'Walk entry clamps eye height');
ctx.walk(new T.Vector3(0,0,4).applyAxisAngle(new T.Vector3(0,1,0),.63));
const cameraPoint=ctx.toScene(ctx.camera.position);assert.ok(cameraPoint.z<-.21&&Math.abs(cameraPoint.y-1.6)<1e-9,'camera uses solver in scene coordinates');
console.log('PASS: actual RoomScene camera path respects transformed scene collision and fixed eye height.');
