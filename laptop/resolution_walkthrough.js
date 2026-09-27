import * as THREE from './vendor/three.module.js';
import { OrbitControls } from './vendor/OrbitControls.js';
import { SparkRenderer, SplatMesh } from './vendor/spark.module.js';

const $=id=>document.getElementById(id);
const config=await (await fetch('/config')).json();
if(!config.model_urls.candidate){
  document.querySelector('h1').textContent='Preserved baseline · resolution audit';
  document.querySelector('header p').textContent='The 1440 run stopped before exporting a candidate. This is the preserved baseline only. Saved training cameras match the photos; moved viewpoints are qualitative checks only. Dark background means missing coverage. This comparison tool has no collision constraint.';
  $('model').querySelector('[value="candidate"]').disabled=true;
  $('model').querySelector('[value="candidate"]').textContent='1440 run stopped · no model';
  $('switch').disabled=true;
  $('capture').textContent='Save baseline view locally';
}
const scene=new THREE.Scene(), camera=new THREE.PerspectiveCamera();
const renderer=new THREE.WebGLRenderer({antialias:true,preserveDrawingBuffer:true});
renderer.setPixelRatio(1);renderer.setSize(720,960);renderer.setClearColor(0x202830,1);
renderer.outputColorSpace=THREE.SRGBColorSpace;
renderer.domElement.setAttribute('aria-label','Resolution comparison room. Drag to orbit or scroll to approach.');
$('host').append(renderer.domElement);
const controls=new OrbitControls(camera,renderer.domElement);controls.enableDamping=false;
controls.minDistance=.1;controls.maxDistance=20;controls.maxPolarAngle=Math.PI*.99;
const spark=new SparkRenderer({renderer,depthTest:true,depthWrite:false});scene.add(spark);
const models={};let active='baseline',busy=false;
const views=config.frames.map((frame,i)=>({frame,label:`Training view ${i+1} · ${frame.file_path.split('/').pop()}`}));
for(const [index,label] of [[0,'Artwork'],[4,'Chair / table'],[5,'Kitchen / ceiling']])
  views.push({frame:config.frames[index],label:`Navigated · ${label} · qualitative`,offset:[.25,0,-.15]});
views.forEach((v,i)=>$('view').add(new Option(v.label,String(i))));
function cameraState(){camera.updateMatrixWorld(true);return {matrix_world:camera.matrixWorld.toArray(),projection:camera.projectionMatrix.toArray(),render_size:[720,960]};}
function stateText(){$('camera').textContent=JSON.stringify(cameraState());}
controls.addEventListener('change',stateText);
function go(index){
  const v=views[index],f=v.frame;
  // Camera metadata is row-major in Nerfstudio JSON. ARKit/NeRF cameras
  // use +Y up and -Z forward. Rotate local Z +90 degrees to display the
  // sensor raster upright, matching every static comparison's clockwise turn.
  const pose=new THREE.Matrix4().set(...f.transform_matrix.flat());
  pose.multiply(new THREE.Matrix4().makeRotationZ(Math.PI/2));
  pose.decompose(camera.position,camera.quaternion,camera.scale);
  if(v.offset)camera.position.add(new THREE.Vector3(...v.offset).applyQuaternion(camera.quaternion));
  camera.up.set(0,1,0);
  const w=720,h=960,s=w/f.h,fx=f.fl_y*s,fy=f.fl_x*s,cx=(f.h-f.cy)*s,cy=f.cx*s,n=.02;
  camera.near=n;camera.far=100;camera.aspect=w/h;
  camera.projectionMatrix.makePerspective(-cx*n/fx,(w-cx)*n/fx,cy*n/fy,-(h-cy)*n/fy,n,100);
  camera.projectionMatrixInverse.copy(camera.projectionMatrix).invert();
  controls.target.copy(camera.position).add(new THREE.Vector3(0,0,-2).applyQuaternion(camera.quaternion));
  // Do not call controls.update here: its world-up convention would remove
  // the captured camera's small roll. It is only used after real navigation.
  stateText();$('name').value=index>=config.frames.length?`navigation-${index-config.frames.length+1}`:`training-view-${index+1}`;
}
async function selectModel(key){
  $('status').textContent=`Loading ${key}…`;
  if(!models[key]){const mesh=new SplatMesh({url:config.model_urls[key]});await mesh.initialized;scene.add(mesh);models[key]=mesh;}
  for(const [name,mesh] of Object.entries(models))mesh.visible=name===key;
  active=key;$('model').value=key;
  await new Promise(resolve=>setTimeout(resolve,700));
  $('status').textContent=`${key==='baseline'?'Baseline 960':'Experimental 1440'} · exact shared camera · 720 × 960 pixels`;
  stateText();
}
async function act(fn){if(busy)return;busy=true;try{await fn();}catch(e){$('status').textContent=e.message;console.error(e);}finally{busy=false;}}
$('model').onchange=()=>act(()=>selectModel($('model').value));
$('switch').onclick=()=>act(()=>selectModel(active==='baseline'?'candidate':'baseline'));
$('go').onclick=()=>{if(!busy)go(Number($('view').value));};
function step(x,z){if(busy)return;const delta=new THREE.Vector3(x,0,z).applyQuaternion(camera.quaternion);camera.position.add(delta);controls.target.add(delta);stateText();}
$('left').onclick=()=>step(-.25,0);$('right').onclick=()=>step(.25,0);$('forward').onclick=()=>step(0,-.25);$('back').onclick=()=>step(0,.25);
$('capture').onclick=()=>act(async()=>{
  controls.enabled=false;
  const before=cameraState(), previous=active,images={};
  try{
    for(const key of Object.keys(config.model_urls)){
      await selectModel(key);renderer.render(scene,camera);images[key]=renderer.domElement.toDataURL('image/png');
    }
    const after=cameraState();
    if(JSON.stringify(before)!==JSON.stringify(after))throw new Error('Camera moved; pair refused');
    const response=await fetch('/capture',{method:'POST',headers:{'Content-Type':'application/json','X-Capture-Token':config.capture_token},body:JSON.stringify({name:$('name').value,view_label:views[Number($('view').value)].label,camera_before:before,camera_after:after,images})});
    const result=await response.json();if(!response.ok)throw new Error(result.error);
    await selectModel(previous);$('status').textContent=`Saved ${Object.keys(images).join(' / ')} at the recorded camera: ${result.saved}`;
  }finally{controls.enabled=true;}
});
renderer.setAnimationLoop(()=>renderer.render(scene,camera));
go(0);await act(()=>selectModel('baseline'));
