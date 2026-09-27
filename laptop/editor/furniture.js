import * as THREE from './vendor/three.module.js';
import { GLTFLoader } from './vendor/GLTFLoader.js';

// +Y up, yaw about +Y, model bottom at the original RoomPlan floor Y.
export function placementMatrix(proposal) {
  const matrix=new THREE.Matrix4().makeRotationY(THREE.MathUtils.degToRad(proposal.yaw_degrees??proposal.anchor.yaw_degrees))
    .setPosition(...proposal.position_m);
  if(proposal.anchor.type==='wall'){const h=proposal.dimensions_m[1];matrix.multiply(new THREE.Matrix4().makeTranslation(0,h/2,0)).multiply(new THREE.Matrix4().makeRotationZ(THREE.MathUtils.degToRad(proposal.anchor.roll_degrees))).multiply(new THREE.Matrix4().makeTranslation(0,-h/2,0));}
  return matrix;
}

export class ProposalLayer {
  constructor(scene, onError) {
    this.root=new THREE.Group();scene.add(this.root);
    this.groups=new Map();this.cache=new Map();this.generation=0;this.onError=onError;
  }
  async model(item) {
    if(!this.cache.has(item.id)){
      const manager=new THREE.LoadingManager(),errors=[];
      manager.onError=url=>errors.push(url);
      this.cache.set(item.id,new GLTFLoader(manager).loadAsync(item.model_url).then(model=>{
        if(errors.length)throw new Error('One or more embedded model textures could not load');
        return model;
      }).catch(error=>{this.cache.delete(item.id);throw error;}));
    }
    return this.cache.get(item.id);
  }
  async update(state, selected, draw) {
    const generation=++this.generation;
    this.root.matrixAutoUpdate=false;this.root.matrix.fromArray(state.scene.scene_to_display);
    const changed=this.sceneId!==state.scene.id;this.sceneId=state.scene.id;
    const ids=new Set(changed?[]:state.proposals.map(p=>p.id));
    for(const [id,group] of this.groups)if(!ids.has(id)){
      group.traverse(o=>{if(o.userData.ownedGeometry)o.geometry.dispose();if(o.material)o.material.dispose();});
      this.root.remove(group);this.groups.delete(id);
    }
    for(const p of state.proposals) {
      let group=this.groups.get(p.id);
      if(!group) {
        let model;
        try{model=await this.model(p.model);}catch(error){this.onError(`Furniture model unavailable: ${error.message}. The saved footprint remains; reload to retry.`);return;}
        if(generation!==this.generation)return;
        group=new THREE.Group();group.matrixAutoUpdate=false;
        const chair=model.scene.clone(true);chair.position.add(new THREE.Vector3(...p.model.model_offset_m));
        chair.traverse(o=>{if(o.isMesh){
          o.material=o.material.clone();o.material.transparent=false;o.material.depthWrite=true;o.material.depthTest=true;
          o.userData.id=p.id;o.material.roughness=Math.max(.75,o.material.roughness||0);
        }});
        group.add(chair);
        if(p.model.anchor_type!=='wall'){
          const canvas=document.createElement('canvas');canvas.width=canvas.height=128;const ctx=canvas.getContext('2d');
          const gradient=ctx.createRadialGradient(64,64,8,64,64,64);gradient.addColorStop(0,'rgba(25,20,16,0.24)');gradient.addColorStop(.55,'rgba(25,20,16,0.12)');gradient.addColorStop(1,'rgba(25,20,16,0)');ctx.fillStyle=gradient;ctx.fillRect(0,0,128,128);
          const texture=new THREE.CanvasTexture(canvas);const shadow=new THREE.Mesh(new THREE.PlaneGeometry(p.dimensions_m[0]*1.15,p.dimensions_m[2]*1.15),new THREE.MeshBasicMaterial({map:texture,transparent:true,depthWrite:false,polygonOffset:true,polygonOffsetFactor:-1}));
          shadow.rotation.x=-Math.PI/2;shadow.position.y=.006;shadow.userData.ownedGeometry=true;group.add(shadow);
        }
        const [w,,d]=p.dimensions_m;
        const verts=[[-w/2,.012,-d/2],[w/2,.012,-d/2],[w/2,.012,d/2],[-w/2,.012,d/2],[-w/2,.012,-d/2]];
        const line=new THREE.Line(new THREE.BufferGeometry().setFromPoints(verts.map(v=>new THREE.Vector3(...v))),new THREE.LineBasicMaterial({color:0x23d9e7,depthTest:true}));
        line.userData.ownedGeometry=true;line.userData.accent=true;line.visible=false;group.add(line);
        this.groups.set(p.id,group);this.root.add(group);
      }
      group.userData.proposal=p;group.matrix.copy(placementMatrix(p));
    }
    this.highlight(selected);this.root.updateMatrixWorld(true);draw();
  }
  highlight(id) {
    for(const [key,group] of this.groups)group.traverse(o=>{
      if(o.userData.accent){o.visible=key===id;o.material.color.set(0x23d9e7);}
      if(o.isMesh && o.material.emissive)o.material.emissive.set(key===id?0x071a1e:0x000000);
    });
  }
}
