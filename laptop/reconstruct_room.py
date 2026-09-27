#!/usr/bin/env python3
"""Bounded train-only RGB-D fusion, photo texture projection and Brush preparation.
ARKit world meters are retained. No hole filling, inferred backs, pose rescaling or test leakage.
"""
import argparse, hashlib, json, time
from pathlib import Path
import numpy as np
import open3d as o3d
from PIL import Image
from scipy.ndimage import maximum_filter, minimum_filter
from assess_coverage import load_frames, matrix
from import_scan import validate
from pose_overrides import apply_poses
from capture_selection import load_selection, selected_split

CV_FROM_AR = np.diag([1., -1., -1., 1.])

def split_frames(frames):
    if any(f.get('capture_phase')=='held_out' for f in frames):
        train=[f for f in frames if f.get('capture_phase')=='train']
        test=[f for f in frames if f.get('capture_phase')=='held_out'][::5]
    else:
        # Frozen chronological holdout for the initial sparse diagnostic only.
        test=[f for i,f in enumerate(frames) if i%5==3]
        train=[f for i,f in enumerate(frames) if i%5!=3]
    if not train or not test: raise ValueError('Need disjoint training and held-out frames')
    assert not set(f['rgb_file'] for f in train)&set(f['rgb_file'] for f in test)
    return train,test

def read_depth(folder,f,confidence=2):
    h,w=f['depth_height'],f['depth_width']
    d=np.fromfile(folder/f['depth_file'],dtype='<f4').reshape(h,w).copy()
    c=np.fromfile(folder/f['confidence_file'],dtype='u1').reshape(h,w)
    # Suppress depth discontinuities before fusion: noisy object boundaries make floaters.
    edge=maximum_filter(d,3)-minimum_filter(d,3)>.12
    d[(c<confidence)|~np.isfinite(d)|(d<.2)|(d>4.5)|edge]=0
    return d

def extrinsic(f): return CV_FROM_AR@np.linalg.inv(matrix(f,'camera_to_world_column_major',4))

def prepare_brush(folder,out,train,test,mesh):
    target=out/'brush-data';target.mkdir(exist_ok=True);(target/'images').mkdir(exist_ok=True)
    def entry(f):
        k=matrix(f,'intrinsics_column_major',3)
        im=Image.open(folder/f['rgb_file']);im.thumbnail((960,960));im.save(target/'images'/f['rgb_file'],quality=95)
        return dict(file_path='images/'+f['rgb_file'],w=f['image_width'],h=f['image_height'],fl_x=k[0,0],fl_y=k[1,1],cx=k[0,2],cy=k[1,2],transform_matrix=matrix(f,'camera_to_world_column_major',4).tolist())
    # Seed from TRAINING mesh only; Open3D colored points are accepted by Brush's PLY reader.
    seed=o3d.geometry.PointCloud(mesh.vertices);seed.colors=mesh.vertex_colors
    seed=seed.voxel_down_sample(.035)
    if len(seed.points)>160000: seed=seed.uniform_down_sample(int(np.ceil(len(seed.points)/160000)))
    o3d.io.write_point_cloud(str(target/'seed.ply'),seed,write_ascii=False)
    (target/'transforms_train.json').write_text(json.dumps({'camera_model':'OPENCV','ply_file_path':'seed.ply','frames':[entry(f) for f in train]}))
    (target/'transforms_test.json').write_text(json.dumps({'camera_model':'OPENCV','frames':[entry(f) for f in test]}))
    return len(seed.points)

def texture_mesh(folder,out,train,mesh):
    """Select one depth-supported photo per triangle; export unlit photographic glTF."""
    target=out/'mesh';target.mkdir(exist_ok=True);(target/'textures').mkdir(exist_ok=True)
    vertices=np.asarray(mesh.vertices);tri=np.asarray(mesh.triangles);centers=vertices[tri].mean(axis=1)
    mesh.compute_triangle_normals();normals=np.asarray(mesh.triangle_normals)
    best=np.full(len(tri),-1,int);score=np.zeros(len(tri))
    for index,f in enumerate(train):
        e=extrinsic(f);k=matrix(f,'depth_intrinsics_column_major',3)
        p=centers@e[:3,:3].T+e[:3,3];z=p[:,2];uv=p[:,:2]/np.maximum(z[:,None],.001)*[k[0,0],k[1,1]]+[k[0,2],k[1,2]]
        w,h=f['depth_width'],f['depth_height'];px=np.rint(uv).astype(int)
        ok=(z>.2)&(z<4.5)&(px[:,0]>2)&(px[:,0]<w-3)&(px[:,1]>2)&(px[:,1]<h-3)
        d=read_depth(folder,f);ids=np.flatnonzero(ok);observed=d[px[ids,1],px[ids,0]]
        ok[ids]=(observed>0)&(np.abs(observed-z[ids])<.09)
        cam=matrix(f,'camera_to_world_column_major',4)[:3,3];view=cam-centers;view/=np.maximum(np.linalg.norm(view,axis=1)[:,None],1e-6)
        facing=np.abs((view*normals).sum(1));border=np.minimum.reduce([uv[:,0]/w,1-uv[:,0]/w,uv[:,1]/h,1-uv[:,1]/h])
        quality=ok*facing*np.maximum(border,0)/np.maximum(z*z,.04)
        update=quality>score;score[update]=quality[update];best[update]=index
    binary=bytearray();views=[];accessors=[];primitives=[];materials=[];images=[];textures=[]
    def attribute(data,kind):
        data=np.ascontiguousarray(data,dtype='<f4');offset=len(binary);binary.extend(data.tobytes());views.append({'buffer':0,'byteOffset':offset,'byteLength':data.nbytes,'target':34962})
        acc={'bufferView':len(views)-1,'componentType':5126,'count':len(data),'type':kind}
        if kind=='VEC3':acc.update(min=data.min(0).tolist(),max=data.max(0).tolist())
        accessors.append(acc);return len(accessors)-1
    for chosen in np.unique(best):
        mask=best==chosen;points=vertices[tri[mask]].reshape(-1,3)
        attrs={'POSITION':attribute(points,'VEC3')}
        mat={'name':'Unknown photo coverage','doubleSided':False,'extensions':{'KHR_materials_unlit':{}},'pbrMetallicRoughness':{'baseColorFactor':[.34,.38,.42,1],'metallicFactor':0,'roughnessFactor':1}}
        if chosen>=0:
            f=train[chosen];p=points@extrinsic(f)[:3,:3].T+extrinsic(f)[:3,3];k=matrix(f,'intrinsics_column_major',3)
            uv=p[:,:2]/np.maximum(p[:,2,None],.001)*[k[0,0],k[1,1]]+[k[0,2],k[1,2]];uv/=[f['image_width'],f['image_height']]
            attrs['TEXCOORD_0']=attribute(uv,'VEC2')
            name=f['rgb_file'];im=Image.open(folder/name);im.thumbnail((1280,1280));im.save(target/'textures'/name,quality=94)
            images.append({'uri':'textures/'+name});textures.append({'source':len(images)-1,'sampler':0})
            mat['name']='Observed RGB '+name;mat['pbrMetallicRoughness']['baseColorTexture']={'index':len(textures)-1};mat['pbrMetallicRoughness']['baseColorFactor']=[1,1,1,1]
        materials.append(mat);primitives.append({'attributes':attrs,'material':len(materials)-1,'mode':4})
    (target/'mesh.bin').write_bytes(binary)
    model={'asset':{'version':'2.0','generator':'Local train-only RGB-D TSDF + depth-checked photo projection'},'extensionsUsed':['KHR_materials_unlit'],'scene':0,'scenes':[{'nodes':[0]}],'nodes':[{'mesh':0}],'meshes':[{'primitives':primitives}],'buffers':[{'uri':'mesh.bin','byteLength':len(binary)}],'bufferViews':views,'accessors':accessors,'materials':materials,'images':images,'textures':textures,'samplers':[{'magFilter':9729,'minFilter':9987,'wrapS':33071,'wrapT':33071}]}
    (target/'room.gltf').write_text(json.dumps(model))
    np.savez_compressed(out/'texture-assignment.npz',best_frame=best)
    return {'triangles_with_photo':int((best>=0).sum()),'triangles_unknown_color':int((best<0).sum()),'source_photos_used':len(images)}

def reconstruct(folder,out,voxel=.025,poses=None,selection=None):
    if (out/'colored-mesh.ply').exists():raise ValueError('Reconstruction already exists; use a new output directory to preserve the baseline')
    start=time.monotonic();manifest=validate(folder);frames=apply_poses(folder,load_frames(folder),poses)
    chosen=load_selection(selection)
    if chosen and poses:raise ValueError('Dense ablation freezes the original ARKit poses')
    train,test=selected_split(folder,frames,chosen) if chosen else split_frames(frames)
    out.mkdir(parents=True,exist_ok=True)
    if chosen:(out/'frame-selection.json').write_text(json.dumps(chosen,indent=2))
    if poses:
        target=out/'pose-refinement.json'
        if Path(poses).resolve()!=target.resolve():target.write_bytes(Path(poses).read_bytes())
    index=folder/('DenseFrames.json' if chosen else 'Frames.json')
    split={'source_scan_id':manifest['scan_id'],'index_sha256':hashlib.sha256(index.read_bytes()).hexdigest(),'train':[f['rgb_file'] for f in train],'held_out':[f['rgb_file'] for f in test],'excluded_held_out_frames':[f['rgb_file'] for f in frames if f.get('capture_phase')=='held_out'],'policy':'Held-out RGB and depth excluded from mesh, texture, seed, and splat training; all captures in final test phase excluded even if not selected for evaluation.'}
    (out/'split.json').write_text(json.dumps(split,indent=2))
    return fuse_frames(folder,out,train,test,voxel,manifest['scan_id'],start)


def fuse_frames(folder,out,train,test,voxel,source_scan_id,start):
    """Shared fixed fusion implementation; callers establish immutable source/split."""
    c=o3d.core
    volume=o3d.t.geometry.VoxelBlockGrid(attr_names=('tsdf','weight','color'),attr_dtypes=(c.float32,c.float32,c.float32),attr_channels=((1),(1),(3)),voxel_size=voxel,block_resolution=16,block_count=3000,device=c.Device('CPU:0'))
    for i,f in enumerate(train):
        depth=read_depth(folder,f);w,h=f['depth_width'],f['depth_height'];k=matrix(f,'depth_intrinsics_column_major',3)
        color=np.asarray(Image.open(folder/f['rgb_file']).convert('RGB').resize((w,h),Image.Resampling.LANCZOS))
        dep=o3d.t.geometry.Image(c.Tensor(depth[:,:,None]))
        col=o3d.t.geometry.Image(c.Tensor(color.astype('f4')/255.))
        intr=c.Tensor(k,dtype=c.float64);ext=c.Tensor(extrinsic(f),dtype=c.float64)
        blocks=volume.compute_unique_block_coordinates(dep,intr,ext,1.,4.5,4.)
        volume.integrate(blocks,dep,col,intr,intr,ext,1.,4.5,4.)
        if i%25==0:print('Fused',i+1,'/',len(train),flush=True)
    mesh=volume.extract_triangle_mesh(weight_threshold=1.).to_legacy();mesh.remove_degenerate_triangles();mesh.remove_duplicated_triangles();mesh.remove_unreferenced_vertices()
    labels,counts,_=mesh.cluster_connected_triangles();small=np.asarray(counts)[np.asarray(labels)]<80
    removed=int(small.sum());mesh.remove_triangles_by_mask(small);mesh.remove_unreferenced_vertices()
    if not len(mesh.triangles):raise ValueError('No supported mesh surface survived')
    mesh.compute_vertex_normals()
    colors=np.asarray(mesh.vertex_colors)
    if colors.size and (colors.min()<0 or colors.max()>1.001): raise ValueError('Fusion color must remain normalized RGB')
    o3d.io.write_triangle_mesh(str(out/'colored-mesh.ply'),mesh)
    fusion_seconds=time.monotonic()-start
    seeds=prepare_brush(folder,out,train,test,mesh)
    photo=texture_mesh(folder,out,train,mesh)
    report={'fusion_backend':'Open3D tensor VoxelBlockGrid CPU','source_scan_id':source_scan_id,'train_frames':len(train),'test_frames':len(test),'vertices':len(mesh.vertices),'triangles':len(mesh.triangles),'small_component_triangles_removed':removed,'seed_points':seeds,'voxel_m':voxel,'confidence_minimum':2,'range_m':[.2,4.5],'fusion_seconds':fusion_seconds,'total_seconds':time.monotonic()-start,'bounds_m':[mesh.get_min_bound().tolist(),mesh.get_max_bound().tolist()],**photo}
    (out/'mesh-report.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('output',type=Path);p.add_argument('--voxel',type=float,default=.025);p.add_argument('--poses',type=Path);a=p.parse_args();reconstruct(a.source.resolve(),a.output.resolve(),a.voxel,a.poses)
