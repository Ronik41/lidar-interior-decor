import * as THREE from './vendor/three.module.js';
import { OrbitControls } from './vendor/OrbitControls.js';
import { GLTFLoader } from './vendor/GLTFLoader.js';
import { ProposalLayer } from './furniture.js';

export class RoomScene {
  constructor(host, onSelect, onPlace, onError) {
    this.host=host; this.onSelect=onSelect; this.selected=null; this.cutaway=true; this.showExcluded=true;
    this.renderer=new THREE.WebGLRenderer({antialias:true,alpha:true,preserveDrawingBuffer:true});
    this.renderer.setPixelRatio(Math.min(devicePixelRatio,2));
    this.renderer.setClearColor(0xe7ebe7,1);
    this.renderer.outputColorSpace=THREE.SRGBColorSpace;
    host.append(this.renderer.domElement);
    this.renderer.domElement.setAttribute('aria-label','Interactive room model. Drag to orbit, scroll to zoom, Shift-drag to pan. Select an element to inspect.');
    this.renderer.domElement.tabIndex=0;
    this.scene=new THREE.Scene();
    this.camera=new THREE.PerspectiveCamera(42,1,.02,250);
    this.controls=new OrbitControls(this.camera,this.renderer.domElement);
    this.controls.enableDamping=false; this.controls.minDistance=.3; this.controls.maxDistance=60;
    this.controls.maxPolarAngle=Math.PI*.495;
    this.controls.addEventListener('change',()=>this.draw());
    this.scene.add(new THREE.HemisphereLight(0xffffff,0x87968b,2.2));
    const light=new THREE.DirectionalLight(0xffffff,2.1);light.position.set(3,7,4);this.scene.add(light);
    this.captureRoot=new THREE.Group();this.scene.add(this.captureRoot);this.layerMode="roomplan";this.navigation="orbit";this.overlay=false;
    this.root=new THREE.Group();this.scene.add(this.root);this.groups=new Map();this.labels=[];
    this.proposals=new ProposalLayer(this.scene,onError);this.onPlace=onPlace;
    this.floorPick=new THREE.Group();this.floorPick.visible=false;this.scene.add(this.floorPick);
    this.placementMarker=new THREE.Group();this.scene.add(this.placementMarker);
    this.ray=new THREE.Raycaster();this.pointer=new THREE.Vector2();
    let down;
    this.renderer.domElement.addEventListener('pointerdown',e=>{
      down=[e.clientX,e.clientY];
      if(!this.placement && this.navigation==='walk' && e.button===0){this.lookDrag=[e.clientX,e.clientY];this.renderer.domElement.setPointerCapture(e.pointerId);}
    });
    this.renderer.domElement.addEventListener('pointermove',e=>{
      if(this.placement){this.previewPlacement(e);return;}
      if(!this.lookDrag)return;
      const dx=e.clientX-this.lookDrag[0],dy=e.clientY-this.lookDrag[1];this.lookDrag=[e.clientX,e.clientY];
      const direction=this.controls.target.clone().sub(this.camera.position).normalize();
      const yaw=Math.atan2(direction.x,direction.z)-dx*.004;
      const pitch=THREE.MathUtils.clamp(Math.asin(direction.y)-dy*.004,-1.4,1.4);
      this.controls.target.copy(this.camera.position).add(new THREE.Vector3(Math.sin(yaw)*Math.cos(pitch),Math.sin(pitch),Math.cos(yaw)*Math.cos(pitch)).multiplyScalar(2));
      this.camera.lookAt(this.controls.target);this.draw();
    });
    this.renderer.domElement.addEventListener('pointercancel',()=>{this.lookDrag=null;});
    this.renderer.domElement.addEventListener('pointerup',e=>{
      this.lookDrag=null;
      if(e.button!==0 || !down || Math.hypot(e.clientX-down[0],e.clientY-down[1])>5)return;
      if(this.placement){const hit=this.floorHit(e);if(hit)this.onPlace(hit);return;}
      const rect=this.renderer.domElement.getBoundingClientRect();
      this.pointer.set((e.clientX-rect.left)/rect.width*2-1,-(e.clientY-rect.top)/rect.height*2+1);
      this.ray.setFromCamera(this.pointer,this.camera);
      const proposalHits=this.ray.intersectObjects(this.proposals.root.children,true).filter(h=>h.object.isMesh && h.object.userData.id);
      if(proposalHits[0]){this.onSelect(proposalHits[0].object.userData.id);return;}
      const hits=this.ray.intersectObjects(this.root.visible?this.root.children:[],true).filter(h=>h.object.isMesh && h.object.userData.id && !h.object.userData.ghost && h.object.visible && this.groups.get(h.object.userData.id)?.visible);
      if(hits[0])this.onSelect(hits[0].object.userData.id);
    });
    this.renderer.domElement.addEventListener('keydown',e=>{
      if(this.layerMode!=='roomplan' && 'wasdqe'.includes(e.key.toLowerCase()) && e.key.length===1){
        e.preventDefault();const key=e.key.toLowerCase(),forward=this.controls.target.clone().sub(this.camera.position);forward.y=0;forward.normalize();
        const right=forward.clone().cross(new THREE.Vector3(0,1,0));const delta=new THREE.Vector3();
        if(key==='w')delta.copy(forward);if(key==='s')delta.copy(forward).negate();if(key==='a')delta.copy(right).negate();if(key==='d')delta.copy(right);if(key==='q')delta.y=-1;if(key==='e')delta.y=1;
        delta.multiplyScalar(e.shiftKey?.5:.2);this.camera.position.add(delta);this.controls.target.add(delta);this.camera.lookAt(this.controls.target);this.draw();return;
      }
      if(['ArrowLeft','ArrowRight','ArrowUp','ArrowDown','+','-'].includes(e.key))e.preventDefault();
      const offset=this.camera.position.clone().sub(this.controls.target);
      if(e.key==='ArrowLeft'||e.key==='ArrowRight')offset.applyAxisAngle(new THREE.Vector3(0,1,0),e.key==='ArrowLeft'?.15:-.15);
      if(e.key==='ArrowUp'||e.key==='+')offset.multiplyScalar(.9);
      if(e.key==='ArrowDown'||e.key==='-')offset.multiplyScalar(1.1);
      this.camera.position.copy(this.controls.target).add(offset);this.controls.update();
    });
    new ResizeObserver(()=>this.resize()).observe(host);
  }
  setPlacement(placement) {
    this.placement=placement;this.lookDrag=null;
    this.controls.enabled=!placement && this.navigation==='orbit';
    this.renderer.domElement.style.cursor=placement?'crosshair':'';
    this.placementMarker.traverse(o=>{o.geometry?.dispose();o.material?.dispose();});this.placementMarker.clear();
    if(placement){
      const [w,,d]=placement.dimensions_m;
      const points=[[-w/2,.015,-d/2],[w/2,.015,-d/2],[w/2,.015,d/2],[-w/2,.015,d/2],[-w/2,.015,-d/2]];
      const line=new THREE.Line(new THREE.BufferGeometry().setFromPoints(points.map(p=>new THREE.Vector3(...p))),new THREE.LineBasicMaterial({color:0x23d9e7,depthTest:true}));
      this.placementMarker.add(line);
    }
    this.placementMarker.visible=false;this.draw();
  }
  floorHit(event) {
    const rect=this.renderer.domElement.getBoundingClientRect();
    this.pointer.set((event.clientX-rect.left)/rect.width*2-1,-(event.clientY-rect.top)/rect.height*2+1);
    this.ray.setFromCamera(this.pointer,this.camera);this.floorPick.updateMatrixWorld(true);
    const hit=this.ray.intersectObjects(this.floorPick.children,true)[0];
    if(!hit)return null;
    const p=this.floorPick.worldToLocal(hit.point.clone());
    return {floor_identifier:hit.object.userData.floorId,x_m:p.x,z_m:p.z,world:hit.point};
  }
  previewPlacement(event) {
    const hit=this.floorHit(event);this.placementMarker.visible=!!hit;
    if(hit){this.placementMarker.position.copy(hit.world);this.placementMarker.rotation.y=this.state.document.plan_rotation_radians+THREE.MathUtils.degToRad(this.placement.yaw_degrees||0);}
    this.draw();
  }
  material(e) {
    const m=new THREE.MeshStandardMaterial({color:e.color.hex,roughness:1,metalness:0,side:THREE.DoubleSide,transparent:true});
    if(e.color.origin==='unknown') {
      const canvas=document.createElement('canvas');canvas.width=canvas.height=64;
      const c=canvas.getContext('2d');c.fillStyle='#ffffff';c.fillRect(0,0,64,64);c.strokeStyle='#bdc6c5';c.lineWidth=2;
      for(let x=-64;x<128;x+=16){c.beginPath();c.moveTo(x,0);c.lineTo(x+64,64);c.stroke();}
      const texture=new THREE.CanvasTexture(canvas);texture.wrapS=texture.wrapT=THREE.RepeatWrapping;texture.repeat.set(3,3);texture.colorSpace=THREE.SRGBColorSpace;m.map=texture;
    }
    return m;
  }
  mesh(geometry,material,e,group) {
    const mesh=new THREE.Mesh(geometry,material);mesh.userData.id=e.source.identifier;group.add(mesh);
    const lineMat=e.excluded?new THREE.LineDashedMaterial({color:0xa46758,dashSize:.06,gapSize:.04}):new THREE.LineBasicMaterial({color:0x687b75,transparent:true,opacity:.65});
    const edges=new THREE.LineSegments(new THREE.EdgesGeometry(geometry,25),lineMat);edges.computeLineDistances();group.add(edges);
    return mesh;
  }
  wallGeometry(e,elements) {
    const [width,height]=e.dimensions_m;
    const inv=new THREE.Matrix4().fromArray(e.spatial.transform).invert();
    const holes=[];
    for(const child of elements.filter(c=>['doors','openings','windows'].includes(c.kind) && c.parent_identifier===e.source.identifier && !c.excluded && c.spatial && c.dimensions_m[0] && c.dimensions_m[1])) {
      const m=new THREE.Matrix4().fromArray(child.spatial.transform),[w,h]=child.dimensions_m;
      const pts=[[-w/2,-h/2],[w/2,-h/2],[w/2,h/2],[-w/2,h/2]].map(p=>new THREE.Vector3(...p,0).applyMatrix4(m).applyMatrix4(inv));
      // A bounded rectangle is only cut when the supplied planes are coplanar.
      if(pts.some(p=>Math.abs(p.z)>.15))continue;
      const x0=Math.max(-width/2,Math.min(...pts.map(p=>p.x))),x1=Math.min(width/2,Math.max(...pts.map(p=>p.x)));
      const y0=Math.max(-height/2,Math.min(...pts.map(p=>p.y))),y1=Math.min(height/2,Math.max(...pts.map(p=>p.y)));
      if(x1>x0 && y1>y0)holes.push([x0,y0,x1,y1]);
    }
    const xs=[...new Set([-width/2,width/2,...holes.flatMap(h=>[h[0],h[2]])])].sort((a,b)=>a-b);
    const ys=[...new Set([-height/2,height/2,...holes.flatMap(h=>[h[1],h[3]])])].sort((a,b)=>a-b);
    const vertices=[],uvs=[];
    for(let i=0;i<xs.length-1;i++)for(let j=0;j<ys.length-1;j++) {
      const [x0,x1,y0,y1]=[xs[i],xs[i+1],ys[j],ys[j+1]],cx=(x0+x1)/2,cy=(y0+y1)/2;
      if(holes.some(h=>cx>h[0] && cx<h[2] && cy>h[1] && cy<h[3]))continue;
      for(const [x,y] of [[x0,y0],[x1,y0],[x1,y1],[x0,y0],[x1,y1],[x0,y1]]){vertices.push(x,y,0);uvs.push((x+width/2)/width,(y+height/2)/height);}
    }
    const g=new THREE.BufferGeometry();g.setAttribute('position',new THREE.Float32BufferAttribute(vertices,3));g.setAttribute('uv',new THREE.Float32BufferAttribute(uvs,2));g.computeVertexNormals();return g;
  }
  update(state,selected) {
    const first=!this.state;this.state=state;this.selected=selected;
    this.root.traverse(o=>{o.geometry?.dispose();if(o.material){o.material.map?.dispose();o.material.dispose();}});
    this.root.clear();for(const item of this.labels)item.el.remove();this.labels=[];this.groups.clear();
    this.root.rotation.y=state.document.plan_rotation_radians;this.captureRoot.rotation.y=this.root.rotation.y;
    this.floorPick.traverse(o=>{o.geometry?.dispose();o.material?.dispose();});this.floorPick.clear();
    this.floorPick.rotation.y=this.root.rotation.y;
    for(const floor of state.placement_floors){
      const mesh=new THREE.Mesh(new THREE.ShapeGeometry(new THREE.Shape(floor.polygon.map(p=>new THREE.Vector2(p[0],p[1])))),new THREE.MeshBasicMaterial({side:THREE.DoubleSide}));
      mesh.matrixAutoUpdate=false;mesh.matrix.fromArray(floor.transform);mesh.userData.floorId=floor.identifier;this.floorPick.add(mesh);
    }
    this.proposals.update(state,selected,()=>this.draw());
    for(const e of state.elements) {
      if(!e.spatial)continue;
      const group=new THREE.Group();group.matrixAutoUpdate=false;group.matrix.fromArray(e.spatial.transform);group.userData.element=e;this.root.add(group);this.groups.set(e.source.identifier,group);
      const dims=e.dimensions_m,material=this.material(e);let geometry;
      if((e.kind==='objects'?dims:dims.slice(0,2)).some(v=>v==null)) {
        geometry=new THREE.SphereGeometry(.045,10,8);
      } else if(e.kind==='objects') {
        geometry=new THREE.BoxGeometry(...dims);
      } else if(e.kind==='floors') {
        geometry=new THREE.ShapeGeometry(new THREE.Shape(e.spatial.polygon.map(p=>new THREE.Vector2(p[0],p[1]))));
      } else if(e.kind==='walls') {
        geometry=this.wallGeometry(e,state.elements);
      } else {
        geometry=new THREE.PlaneGeometry(dims[0],dims[1]);
      }
      const mesh=this.mesh(geometry,material,e,group);
      if(e.kind==='openings' || (e.kind==='doors' && e.spatial.is_open))mesh.userData.aperture=true;
      if(e.kind==='objects' || ['doors','openings'].includes(e.kind)) {
        const el=document.createElement('button');el.className='scene-label';el.textContent=e.code;el.title=e.label;el.setAttribute('aria-label',`${e.code} ${e.label} in 3D`);el.onclick=()=>this.onSelect(e.source.identifier);this.host.append(el);this.labels.push({el,group,e});
      }
    }
    this.root.updateMatrixWorld(true);
    const box=new THREE.Box3().setFromObject(this.root);this.center=box.getCenter(new THREE.Vector3());this.size=box.getSize(new THREE.Vector3());
    if(first)this.fit();else this.highlight(selected);
    this.resize();
  }
  async loadReconstruction(metadata) {
    this.reconstruction=metadata;
    const model=await new GLTFLoader().loadAsync(metadata.mesh_url);
    this.meshScan=model.scene;this.captureRoot.add(this.meshScan);
    this.setLayer('mesh');this.setNavigation('walk');this.goToView(0);
  }
  async setLayer(mode) {
    const benchmark=mode==='benchmark';
    const member=benchmark?'benchmarkScan':'splatScan';
    if((mode==='splat'||benchmark) && !this[member]){
      const url=benchmark?this.reconstruction?.benchmark?.url:this.reconstruction?.splat_url;
      if(!url)throw new Error('No registered Gaussian candidate is available');
      const {SparkRenderer,SplatMesh}=await import('./vendor/spark.module.js');
      if(!this.spark){this.spark=new SparkRenderer({renderer:this.renderer,depthTest:true,depthWrite:false,onDirty:()=>this.requestDraw()});this.scene.add(this.spark);}
      const model=new SplatMesh({url});await model.initialized;
      if(benchmark){
        // Object transform rotates positions, Gaussian covariance and SH view directions together.
        new THREE.Matrix4().fromArray(this.reconstruction.benchmark.source_to_reference_column_major).decompose(model.position,model.quaternion,model.scale);
      }
      this[member]=model;this.captureRoot.add(model);
    }
    this.layerMode=mode;this.root.visible=mode==='roomplan'||this.overlay;
    this.captureRoot.visible=mode!=='roomplan';if(this.meshScan)this.meshScan.visible=mode==='mesh';if(this.splatScan)this.splatScan.visible=mode==='splat';if(this.benchmarkScan)this.benchmarkScan.visible=benchmark;
    if(mode==='roomplan'){this.setNavigation('orbit');this.fit();}
    this.renderer.setClearColor(mode==='roomplan'?0xe7ebe7:0x202830,1);this.draw();
  }
  setNavigation(mode){this.navigation=mode;this.controls.enabled=!this.placement && mode==='orbit';this.renderer.domElement.setAttribute('aria-label',mode==='walk'?'Interactive scanned room. Drag to look. W A S D move, Q and E move down and up.':'Interactive room model. Drag to orbit, scroll to zoom, Shift-drag to pan.');this.camera.up.set(0,1,0);this.controls.maxPolarAngle=mode==='orbit'&&this.layerMode==='roomplan'?Math.PI*.495:Math.PI*.99;this.draw();}
  goToView(index){
    const v=this.reconstruction?.viewpoints[index];if(!v)return;
    this.onViewChange?.(index);
    const pose=new THREE.Matrix4().fromArray(v.camera_to_world_column_major);
    this.captureRoot.updateMatrixWorld(true);pose.premultiply(this.captureRoot.matrixWorld);
    this.camera.position.setFromMatrixPosition(pose);const dir=new THREE.Vector3(0,0,-1).transformDirection(pose);
    this.camera.up.set(0,1,0);this.controls.target.copy(this.camera.position).addScaledVector(dir,2);this.camera.fov=62;this.camera.updateProjectionMatrix();this.camera.lookAt(this.controls.target);this.draw();
  }
  fit() {
    if(!this.center)return;
    this.controls.target.copy(this.center);this.controls.target.y-=this.size.y*.12;
    const radius=Math.max(this.size.x,this.size.z,3);
    this.camera.position.copy(this.controls.target).add(new THREE.Vector3(radius*.38,radius*.55,radius*.80));
    this.camera.near=.02;this.camera.updateProjectionMatrix();this.controls.update();this.draw();
  }
  focus(id) {
    const group=this.proposals.groups.get(id)||this.groups.get(id);if(!group)return;
    const center=new THREE.Box3().setFromObject(group).getCenter(new THREE.Vector3());
    if(this.layerMode!=='roomplan' && this.reconstruction?.viewpoints.length){
      // Review from a recorded camera position instead of fitting a box from outside the scan.
      let best=0,bestScore=Infinity;
      this.captureRoot.updateMatrixWorld(true);
      this.reconstruction.viewpoints.forEach((v,index)=>{
        const pose=new THREE.Matrix4().fromArray(v.camera_to_world_column_major).premultiply(this.captureRoot.matrixWorld);
        const position=new THREE.Vector3().setFromMatrixPosition(pose),toElement=center.clone().sub(position);
        const distance=toElement.length(),direction=new THREE.Vector3(0,0,-1).transformDirection(pose);
        const alignment=direction.dot(toElement.normalize());
        const score=distance+Math.max(0,1-alignment)*3+(distance<.4?10:0);
        if(score<bestScore){bestScore=score;best=index;}
      });
      this.goToView(best);this.controls.target.copy(center);this.camera.lookAt(center);this.draw();return;
    }
    const delta=this.camera.position.clone().sub(this.controls.target).normalize();
    const e=group.userData.proposal||group.userData.element;
    const distance=Math.max(2.2,...e.dimensions_m.filter(Number.isFinite).map(x=>x*2));
    this.controls.target.copy(center);this.camera.position.copy(center).add(delta.multiplyScalar(distance));this.controls.update();this.draw();
  }
  highlight(id,related=[]) {
    this.selected=id;this.related=related;this.proposals.highlight(id);
    for(const [key,g] of this.groups)g.traverse(o=>{
      if(o.isLineSegments){o.material.color.set(key===id?0xc77825:related.includes(key)?0xa87735:0x687b75);o.material.opacity=key===id || related.includes(key)?1:.65;}
      if(o.isMesh)o.material.emissive.set(key===id?0x34200a:related.includes(key)?0x151007:0x000000);
    });this.draw();
  }
  resize() {
    const w=this.host.clientWidth,h=this.host.clientHeight;if(!w||!h)return;
    this.renderer.setSize(w,h);this.camera.aspect=w/h;this.camera.updateProjectionMatrix();this.draw();
  }
  requestDraw(){if(this.drawPending)return;this.drawPending=true;requestAnimationFrame(()=>{this.drawPending=false;this.draw();});}
  draw() {
    if(!this.state || !this.center)return;
    this.root.updateMatrixWorld(true);
    const camDirection=this.camera.position.clone().sub(this.center);
    for(const [id,g] of this.groups) {
      const e=g.userData.element;g.visible=!e.excluded || this.showExcluded;
      const pos=new THREE.Vector3().setFromMatrixPosition(g.matrixWorld);
      const outward=pos.clone().sub(this.center);outward.y=0;
      const ghost=e.kind==='walls' && this.cutaway && outward.dot(camDirection)>0 && id!==this.selected;
      g.traverse(o=>{
        if(o.isMesh){o.material.visible=this.layerMode==='roomplan';o.material.opacity=e.excluded?.09:ghost?.12:o.userData.aperture?.09:1;o.material.depthWrite=!e.excluded && !ghost && !o.userData.aperture;o.userData.ghost=ghost;}
        if(o.isLineSegments)o.material.opacity=e.excluded?.35:ghost?.25:1;
      });
    }
    this.renderer.render(this.scene,this.camera);
    for(const {el,group,e} of this.labels) {
      const pos=new THREE.Vector3(0,(e.dimensions_m[1]||0)/2+.08,0).applyMatrix4(group.matrixWorld).project(this.camera);
      el.hidden=!this.root.visible || !group.visible || pos.z>1 || pos.z< -1 || Math.abs(pos.x)>.98 || Math.abs(pos.y)>.94;
      el.style.left=`${(pos.x+1)*50}%`;el.style.top=`${(-pos.y+1)*50}%`;
      el.classList.toggle('selected',e.source.identifier===this.selected);
      el.classList.toggle('related',this.related?.includes(e.source.identifier));
    }
  }
}
