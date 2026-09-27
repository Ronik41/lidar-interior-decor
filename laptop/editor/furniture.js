import * as THREE from './vendor/three.module.js';
import { GLTFLoader } from './vendor/GLTFLoader.js';

// +Y up, yaw about +Y, model bottom at the original RoomPlan floor Y.
export function placementMatrix(proposal) {
  return new THREE.Matrix4().makeRotationY(THREE.MathUtils.degToRad(proposal.anchor.yaw_degrees))
    .setPosition(...proposal.position_m);
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
    this.root.rotation.y=state.document.plan_rotation_radians;
    const ids=new Set(state.proposals.map(p=>p.id));
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
          o.userData.id=p.id;
        }});
        group.add(chair);
        const [w,,d]=p.dimensions_m;
        const verts=[[-w/2,.012,-d/2],[w/2,.012,-d/2],[w/2,.012,d/2],[-w/2,.012,d/2],[-w/2,.012,-d/2]];
        const line=new THREE.Line(new THREE.BufferGeometry().setFromPoints(verts.map(v=>new THREE.Vector3(...v))),new THREE.LineBasicMaterial({color:0x23d9e7,depthTest:true}));
        line.userData.ownedGeometry=true;line.userData.accent=true;group.add(line);
        this.groups.set(p.id,group);this.root.add(group);
      }
      group.userData.proposal=p;group.matrix.copy(placementMatrix(p));
    }
    this.highlight(selected);this.root.updateMatrixWorld(true);draw();
  }
  highlight(id) {
    for(const [key,group] of this.groups)group.traverse(o=>{
      if(o.userData.accent)o.material.color.set(key===id?0x23d9e7:0x3294aa);
      if(o.isMesh && o.material.emissive)o.material.emissive.set(key===id?0x071a1e:0x000000);
    });
  }
}
