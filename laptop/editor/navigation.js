// Collision has no dependency on Three, splats, mesh triangles, or a particular room.
export const EYE_HEIGHT=1.60, BODY_HEIGHT=1.75, BODY_RADIUS=.22;
const distance=(a,b)=>Math.hypot(a[0]-b[0],a[1]-b[1]);
const edges=p=>p.map((v,i)=>[v,p[(i+1)%p.length]]);
export function closest(p,a,b){const x=b[0]-a[0],z=b[1]-a[1],t=Math.max(0,Math.min(1,((p[0]-a[0])*x+(p[1]-a[1])*z)/(x*x+z*z||1)));return [a[0]+t*x,a[1]+t*z];}
export function inside(p,poly){let hit=false;for(const [a,b] of edges(poly)){if(distance(p,closest(p,a,b))<1e-8)return true;if((a[1]>p[1])!==(b[1]>p[1])&&p[0]<(b[0]-a[0])*(p[1]-a[1])/(b[1]-a[1])+a[0])hit=!hit;}return hit;}
export function floorHeight(f,p){const m=f.transform;return m[13]-(m[8]*(p[0]-m[12])+m[10]*(p[1]-m[14]))/m[9];}
function world(m,x,y,z){return [m[0]*x+m[4]*y+m[8]*z+m[12],m[1]*x+m[5]*y+m[9]*z+m[13],m[2]*x+m[6]*y+m[10]*z+m[14]];}
export function boxPoints(box){const r=box.yaw_degrees*Math.PI/180,c=Math.cos(r),s=Math.sin(r);return [[-1,-1],[1,-1],[1,1],[-1,1]].map(([x,z])=>[box.x_m+c*x*box.width_m/2+s*z*box.depth_m/2,box.z_m-s*x*box.width_m/2+c*z*box.depth_m/2]);}
export class NavigationWorld {
 constructor(scene,proposals=[],overrides={}){
  this.scene=scene;this.radius=BODY_RADIUS;this.segments=[];this.obstacles=[];
  for(const wall of scene.walls){
   const m=wall.transform;const mid=[m[12],m[14]],floor=scene.floors.find(f=>inside(mid,f.points))||scene.floors[0];
   if(!floor)continue;const fy=floorHeight(floor,mid);
   const gaps=wall.holes.filter(h=>h.passable && world(m,0,h.rect[1],0)[1]<=fy+.18 && world(m,0,h.rect[3],0)[1]>=fy+BODY_HEIGHT).map(h=>[h.rect[0],h.rect[2]]).sort((a,b)=>a[0]-b[0]);
   let cursor=-wall.width/2;
   const add=(a,b)=>{if(b-a<1e-6)return;const p=world(m,a,0,0),q=world(m,b,0,0);this.segments.push({a:[p[0],p[2]],b:[q[0],q[2]],id:wall.id,kind:'wall'});};
   for(const [a,b] of gaps){add(cursor,a);cursor=Math.max(cursor,b);}add(cursor,wall.width/2);
  }
  for(const o of scene.objects){const override=overrides[o.id];if(!(override?.enabled??o.reliable))continue;this.obstacles.push({...o,points:override?.box?boxPoints(override.box):o.points,kind:'captured'});}
  for(const p of proposals){const [w,h,d]=p.model.collision.dimensions_m;this.obstacles.push({id:p.id,kind:'placed',points:boxPoints({x_m:p.position_m[0],z_m:p.position_m[2],width_m:w,depth_m:d,yaw_degrees:p.yaw_degrees??p.anchor.yaw_degrees??0}),bottom:p.position_m[1],top:p.position_m[1]+h,...p.collision});}
  const pts=scene.floors.flatMap(f=>f.points);this.bounds=pts.length?[Math.min(...pts.map(p=>p[0])),Math.min(...pts.map(p=>p[1])),Math.max(...pts.map(p=>p[0])),Math.max(...pts.map(p=>p[1]))]:[0,0,0,0];
 }
 floorAt(p){return this.scene.floors.find(f=>inside(p,f.points));}
 barriers(p){
  const floor=this.floorAt(p);const y=floor?floorHeight(floor,p):0;
  const result=[...this.segments];
  for(const o of this.obstacles)if(o.top>y+.10&&o.bottom<y+BODY_HEIGHT)for(const [a,b] of edges(o.points))result.push({a,b,id:o.id,kind:o.kind});
  for(const f of this.scene.floors)for(const [a,b] of edges(f.points)){
   // Shared floor edges inside a second polygon do not form a boundary.
   const q=closest(p,a,b);if(this.scene.floors.some(other=>other!==f&&inside(q,other.points)))continue;
   result.push({a,b,id:f.identifier,kind:'edge'});
  }
  return result;
 }
 valid(p){
  const floor=this.floorAt(p);if(!floor)return false;
  const y=floorHeight(floor,p);
  if(this.obstacles.some(o=>o.top>y+.10&&o.bottom<y+BODY_HEIGHT&&inside(p,o.points)))return false;
  return this.barriers(p).every(b=>distance(p,closest(p,b.a,b.b))>=this.radius-1e-7);
 }
 nearest(p){
  if(this.valid(p))return p.slice();
  // Re-entry after Orbit / saved camera / changed obstacles: deterministic closest valid grid sample.
  const [x0,z0,x1,z1]=this.bounds;let best=null,score=Infinity;const step=Math.max(.08,Math.sqrt((x1-x0)*(z1-z0)/18000));
  for(let x=x0+this.radius;x<x1;x+=step)for(let z=z0+this.radius;z<z1;z+=step){const q=[x,z],d=distance(p,q);if(d<score&&this.valid(q)){best=q;score=d;}}
  return best;
 }
 move(start,delta){
  if(!this.valid(start))return this.nearest(start);
  let p=start.slice();const n=Math.max(1,Math.ceil(Math.hypot(...delta)/.035));const step=delta.map(v=>v/n);
  for(let i=0;i<n;i++){
   let d=step.slice();
   for(let j=0;j<4;j++){
    const q=[p[0]+d[0],p[1]+d[1]];if(this.valid(q)){p=q;break;}
    let corrected=false;
    for(const b of this.barriers(q)){
     const close=closest(q,b.a,b.b);if(distance(q,close)>=this.radius)continue;
     const prev=closest(p,b.a,b.b),len=distance(p,prev);if(len<1e-8)continue;
     const nx=(p[0]-prev[0])/len,nz=(p[1]-prev[1])/len,dot=d[0]*nx+d[1]*nz;
     if(dot<0){d[0]-=dot*nx;d[1]-=dot*nz;corrected=true;}
    }
    if(!corrected||Math.hypot(...d)<1e-9)break;
   }
  }
  return p;
 }
}
