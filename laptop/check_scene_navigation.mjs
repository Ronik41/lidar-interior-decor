// Probe the same collision solver on a resolved local editor payload.
// Usage: node laptop/check_scene_navigation.mjs /path/to/payload.json
import fs from 'node:fs';
import assert from 'node:assert/strict';
import {NavigationWorld,closest,BODY_RADIUS} from './editor/navigation.js';
const state=JSON.parse(fs.readFileSync(process.argv[2]));
const nav=new NavigationWorld(state.scene,state.proposals,state.document.navigation_overrides);
const report={scene_id:state.scene.id,wall_stops:[],wall_slides:[],openings:[],floor_stops:[],placed_blocks:[]};
for(const b of nav.segments){
 const dx=b.b[0]-b.a[0],dz=b.b[1]-b.a[1],l=Math.hypot(dx,dz),t=[dx/l,dz/l];
 for(const fraction of [.2,.5,.8])for(const side of [-1,1]){
  const mid=[b.a[0]+dx*fraction,b.a[1]+dz*fraction],n=[-t[1]*side,t[0]*side],start=mid.map((v,i)=>v+n[i]*.65);
  if(!nav.valid(start))continue;
  const end=nav.move(start,n.map(v=>-v*1.3)),signed=(end[0]-mid[0])*n[0]+(end[1]-mid[1])*n[1];assert.ok(signed>=BODY_RADIUS-1e-6,'wall cannot be crossed');report.wall_stops.push({id:b.id,start,end});
  const slide=nav.move(start,n.map((v,i)=>-v*1.3+t[i]*.6));assert.ok(nav.valid(slide));const travelled=(slide[0]-start[0])*t[0]+(slide[1]-start[1])*t[1];if(travelled>.45)report.wall_slides.push({id:b.id,start,end:slide});
 }
}
for(const wall of state.scene.walls)for(const h of wall.holes.filter(h=>h.passable)){
 const m=wall.transform,n=[m[8],m[10]];let probe=null;
 for(const fraction of [.2,.35,.5,.65,.8])for(const offset of [.24,.3,.5]){
  const u=h.rect[0]+(h.rect[2]-h.rect[0])*fraction,mid=[m[0]*u+m[12],m[2]*u+m[14]],start=mid.map((v,i)=>v-n[i]*offset),target=mid.map((v,i)=>v+n[i]*offset);
  if(!nav.valid(start)||!nav.valid(target))continue;
  const end=nav.move(start,n.map(v=>v*offset*2));const passed=Math.hypot(end[0]-target[0],end[1]-target[1])<.05;assert.ok(passed,'usable doorway must remain passable');probe={id:h.id,status:'pass',start,end};break;
 }
 report.openings.push(probe||{id:h.id,status:'floor boundary or adjacent obstacle limits this crossing'});
}
for(const floor of state.scene.floors)for(let i=0;i<floor.points.length;i++){
 const a=floor.points[i],b=floor.points[(i+1)%floor.points.length],dx=b[0]-a[0],dz=b[1]-a[1],l=Math.hypot(dx,dz);
 for(const side of [-1,1]){const mid=[(a[0]+b[0])/2,(a[1]+b[1])/2],n=[-dz/l*side,dx/l*side],start=mid.map((v,i)=>v+n[i]*.7);if(!nav.valid(start))continue;const end=nav.move(start,n.map(v=>-v*2));assert.ok(nav.valid(end));report.floor_stops.push({start,end});}
}
for(const o of nav.obstacles.filter(o=>o.kind==='placed')){
 const center=o.points.reduce((a,p)=>a.map((v,i)=>v+p[i]/o.points.length),[0,0]);
 for(let i=0;i<o.points.length;i++){const a=o.points[i],b=o.points[(i+1)%o.points.length],mid=a.map((v,j)=>(v+b[j])/2),delta=mid.map((v,j)=>v-center[j]),len=Math.hypot(...delta),start=mid.map((v,j)=>v+delta[j]/len*.45);if(!nav.valid(start))continue;const end=nav.move(start,center.map((v,j)=>v-start[j]));assert.ok(nav.valid(end));assert.ok(Math.hypot(end[0]-center[0],end[1]-center[1])>.1);report.placed_blocks.push({id:o.id,start,end});}
}
assert.ok(report.wall_stops.length&&report.wall_slides.length&&report.floor_stops.length,'room needs demonstrable wall and floor probes');
if(state.proposals.some(p=>p.model.anchor_type==='floor'))assert.ok(report.placed_blocks.length,'floor furniture needs a collision probe');
console.log(JSON.stringify(report,null,2));
