// Original procedural design props. Rebuild with Node; no downloads or dependencies.
import * as T from './editor/vendor/three.module.js';
import fs from 'node:fs';
import crypto from 'node:crypto';
const root=new URL('./editor/models/',import.meta.url);
const catalog=JSON.parse(fs.readFileSync(new URL('catalog.json',root)));
const colors={wood:0x69503c,edge:0x342d28,cream:0xdad0ba,blue:0x497477,clay:0xb87350,yellow:0xd4a33d,red:0x923e32,green:0x75834c};
let pieces=[];
function add(g,color,x=0,y=0,z=0,rx=0){g.rotateX(rx);g.translate(x,y,z);pieces.push({g,color});}
function box(w,h,d,c,x=0,y=h/2,z=0){add(new T.BoxGeometry(w,h,d),c,x,y,z);}
function sphere(r,c,x,y,z,s=[1,1,1]){const g=new T.SphereGeometry(r,24,16);g.scale(...s);add(g,c,x,y,z);}
function save(id,name,anchor,description,extra={}){
 const buffers=[],views=[],accessors=[],meshes=[],materials=[];let bytes=0;
 const bounds=new T.Box3();
 function attr(array,type,size){const b=Buffer.from(array.buffer,array.byteOffset,array.byteLength);buffers.push(b);views.push({buffer:0,byteOffset:bytes,byteLength:b.length});bytes+=b.length;const a={bufferView:views.length-1,componentType:5126,count:array.length/size,type};if(type==='VEC3'){a.min=[0,1,2].map(k=>{let v=Infinity;for(let i=k;i<array.length;i+=3)v=Math.min(v,array[i]);return v;});a.max=[0,1,2].map(k=>{let v=-Infinity;for(let i=k;i<array.length;i+=3)v=Math.max(v,array[i]);return v;});}accessors.push(a);return accessors.length-1;}
 for(const {g:raw,color} of pieces){const g=raw.index?raw.toNonIndexed():raw;g.computeBoundingBox();bounds.union(g.boundingBox);const c=new T.Color(color);materials.push({pbrMetallicRoughness:{baseColorFactor:[c.r,c.g,c.b,1],metallicFactor:0,roughnessFactor:.85},doubleSided:false});meshes.push({primitives:[{attributes:{POSITION:attr(g.attributes.position.array,'VEC3',3),NORMAL:attr(g.attributes.normal.array,'VEC3',3)},material:materials.length-1}]});}
 const gltf={asset:{version:'2.0',generator:'Original local decor generator; CC0-1.0'},scene:0,scenes:[{nodes:meshes.map((_,i)=>i)}],nodes:meshes.map((_,i)=>({mesh:i})),meshes,materials,buffers:[{byteLength:bytes}],bufferViews:views,accessors};
 let json=Buffer.from(JSON.stringify(gltf));json=Buffer.concat([json,Buffer.alloc((4-json.length%4)%4,32)]);const bin=Buffer.concat(buffers);const out=Buffer.alloc(12+8+json.length+8+bin.length);out.writeUInt32LE(0x46546c67,0);out.writeUInt32LE(2,4);out.writeUInt32LE(out.length,8);out.writeUInt32LE(json.length,12);out.writeUInt32LE(0x4e4f534a,16);json.copy(out,20);out.writeUInt32LE(bin.length,20+json.length);out.writeUInt32LE(0x004e4942,24+json.length);bin.copy(out,28+json.length);
 fs.mkdirSync(new URL(id+'/',root),{recursive:true});fs.writeFileSync(new URL(id+'/model.glb',root),out);
 const dimensions=bounds.getSize(new T.Vector3()).toArray(),center=bounds.getCenter(new T.Vector3());
 const item={id,name,author:'Original procedural artwork for this project',license:'CC0-1.0',source_url:'/models/ORIGINAL-ASSETS.md',model_url:`/models/${id}/model.glb`,sha256:crypto.createHash('sha256').update(out).digest('hex'),dimensions_m:dimensions,model_offset_m:[-center.x,-bounds.min.y,-center.z],dimension_basis:'Authored metric design prop. Not a measured or purchasable product.',description,anchor_type:anchor,collision:{type:'box',dimensions_m:dimensions},...extra};
 const i=catalog.findIndex(x=>x.id===id);if(i<0)catalog.push(item);else catalog[i]=item;pieces=[];
}
box(.58,.035,.52,colors.wood,0,.565);box(.48,.025,.42,colors.wood,0,.19);
for(const x of [-.23,.23])for(const z of [-.20,.20]){box(.038,.56,.038,colors.edge,x,.28,z);box(.042,.014,.042,colors.edge,x,.007,z);}
save('side-table-v1','Walnut side table','floor','Original open-frame side table with a lower shelf.',{surface:{height_m:.5825,width_m:.54,depth_m:.48}});
box(.76,.56,.024,colors.edge,0,.28);box(.708,.508,.012,colors.cream,0,.28,.018);
box(.62,.42,.004,colors.blue,0,.28,.027);box(.62,.10,.006,colors.clay,0,.12,.03);
add(new T.CircleGeometry(.095,48),colors.yellow,.155,.375,.033);
// Abstract layered hills made from original triangles.
const hill=new T.BufferGeometry();hill.setAttribute('position',new T.Float32BufferAttribute([-.31,.17,.034,-.12,.36,.034,.12,.17,.034,-.04,.17,.034,.16,.29,.034,.31,.17,.034],3));hill.computeVertexNormals();add(hill,colors.green);
save('framed-painting-v1','Quiet hills · framed painting','wall','Original geometric landscape in a timber frame. Front faces local +Z.');
const profile=[[.055,0],[.07,.012],[.13,.06],[.165,.10],[.17,.105],[.162,.112],[.151,.098],[.12,.065],[.063,.025],[.05,.02]].map(p=>new T.Vector2(...p));
add(new T.LatheGeometry(profile,64),colors.cream);
for(const [x,y,z,c,r] of [[-.065,.119,.005,colors.red,.048],[.035,.132,.035,colors.green,.052],[.04,.106,-.063,colors.yellow,.046],[-.021,.155,-.025,colors.yellow,.044]]){sphere(r,c,x,y,z,[1,.9,1]);box(.005,.022,.005,colors.wood,x,y+r*.9,z);}
save('fruit-bowl-v1','Ceramic bowl & fruit','tabletop','Original ceramic bowl with four stylized apples and citrus.');
catalog[0].anchor_type='floor';catalog[0].collision={type:'box',dimensions_m:catalog[0].dimensions_m};
fs.writeFileSync(new URL('catalog.json',root),JSON.stringify(catalog,null,2)+'\n');
