#!/usr/bin/env python3
"""Render the textured mesh at pre-reserved camera poses; compare held-out photographs."""
import argparse,json,time
from pathlib import Path
import numpy as np
import open3d as o3d
from PIL import Image,ImageDraw
from skimage.metrics import structural_similarity
from assess_coverage import load_frames,matrix
from reconstruct_room import split_frames,extrinsic,read_depth
from pose_overrides import apply_poses

def render_mesh(folder,out):
    start=time.monotonic();poses=out/'pose-refinement.json';frames=apply_poses(folder,load_frames(folder),poses if poses.exists() else None);train,test=split_frames(frames)
    mesh=o3d.io.read_triangle_mesh(str(out/'colored-mesh.ply'));verts=np.asarray(mesh.vertices);tri=np.asarray(mesh.triangles)
    best=np.load(out/'texture-assignment.npz')['best_frame'];scene=o3d.t.geometry.RaycastingScene();scene.add_triangles(o3d.t.geometry.TriangleMesh.from_legacy(mesh))
    render_dir=out/'mesh-held-out';render_dir.mkdir(exist_ok=True)
    photos=[np.asarray(Image.open(folder/f['rgb_file']).convert('RGB')) for f in train]
    measures=[]
    for f in test:
        w,h=960,720;k=matrix(f,'intrinsics_column_major',3).copy();k[0]*=w/f['image_width'];k[1]*=h/f['image_height']
        rays=scene.create_rays_pinhole(o3d.core.Tensor(k),o3d.core.Tensor(extrinsic(f)),w,h);hit=scene.cast_rays(rays)
        face=hit['primitive_ids'].numpy();t=hit['t_hit'].numpy();valid=np.isfinite(t)
        # Unobserved backs are not textured in the browser; match its front-face rendering.
        normal=hit['primitive_normals'].numpy();direction=rays.numpy()[:,:,3:]
        valid &= (normal*direction).sum(2)<0
        yy,xx=np.where(valid)
        uvb=hit['primitive_uvs'].numpy()[valid];ids=face[valid];p=verts[tri[ids,0]]*(1-uvb.sum(1))[:,None]+verts[tri[ids,1]]*uvb[:,0,None]+verts[tri[ids,2]]*uvb[:,1,None]
        rgb=np.full((h,w,3),[32,40,48],dtype='u1');rgb[valid]=[87,97,107]
        for chosen in np.unique(best[ids]):
            if chosen<0:continue
            mask=best[ids]==chosen;sf=train[chosen];e=extrinsic(sf);q=p[mask]@e[:3,:3].T+e[:3,3];sk=matrix(sf,'intrinsics_column_major',3)
            uv=q[:,:2]/q[:,2,None]*[sk[0,0],sk[1,1]]+[sk[0,2],sk[1,2]];uv=np.rint(uv).astype(int);im=photos[chosen];uv[:,0]=uv[:,0].clip(0,im.shape[1]-1);uv[:,1]=uv[:,1].clip(0,im.shape[0]-1)
            rgb[yy[mask],xx[mask]]=im[uv[:,1],uv[:,0]]
        name=Path(f['rgb_file']).stem;Image.fromarray(rgb).save(render_dir/(name+'.png'))
        np.savez_compressed(render_dir/(name+'-depth.npz'),depth=t,valid=valid)
        ref=np.asarray(Image.open(folder/f['rgb_file']).resize((w,h),Image.Resampling.LANCZOS));Image.fromarray(ref).save(render_dir/(name+'-reference.png'))
        d=read_depth(folder,f);dr=np.asarray(Image.fromarray(d).resize((w,h),Image.Resampling.NEAREST));dv=(dr>0)&valid
        mse=np.mean((rgb.astype(float)-ref.astype(float))**2)
        measures.append({'frame':f['rgb_file'],'mesh_coverage_fraction':float(valid.mean()),'mesh_psnr_full_db':float(10*np.log10(255**2/max(mse,1e-9))),'mesh_ssim_full':float(structural_similarity(ref,rgb,channel_axis=2,data_range=255)),'median_depth_error_m':float(np.median(np.abs(dr[dv]-t[dv]))) if dv.any() else None,'depth_error_p90_m':float(np.percentile(np.abs(dr[dv]-t[dv]),90)) if dv.any() else None})
        print('Rendered',name,flush=True)
    report={'held_out_policy':json.loads((out/'split.json').read_text())['policy'],'mesh_render_seconds':time.monotonic()-start,'views':measures}
    (out/'evaluation.json').write_text(json.dumps(report,indent=2))

def compare(folder,out,splats):
    report=json.loads((out/'evaluation.json').read_text());rows=[]
    for r in report['views']:
        stem=Path(r['frame']).stem;ref=Image.open(out/'mesh-held-out'/(stem+'-reference.png'));mesh=Image.open(out/'mesh-held-out'/(stem+'.png'));splat=Image.open(splats/(stem+'.png')).convert('RGB')
        if splat.size!=ref.size:raise ValueError('Candidate comparison must use matching resolution')
        ar=np.asarray(ref);br=np.asarray(splat);mse=np.mean((ar.astype(float)-br.astype(float))**2)
        r.update(splat_psnr_full_db=float(10*np.log10(255**2/max(mse,1e-9))),splat_ssim_full=float(structural_similarity(ar,br,channel_axis=2,data_range=255)))
        # Sensor images are landscape-native with roll; rotate all three equally for readable room details.
        row=Image.new('RGB',(3*480,680),(22,27,32));draw=ImageDraw.Draw(row)
        for i,(label,im) in enumerate([('HELD-OUT PHOTO',ref),('RGB-D MESH',mesh),('GAUSSIAN SPLAT',splat)]):
            im=im.rotate(-90,expand=True);im.thumbnail((470,626));row.paste(im,(i*480,38));draw.text((i*480+8,8),label+' · '+stem,fill='white')
        (out/'comparison').mkdir(exist_ok=True);row.save(out/'comparison'/(stem+'.jpg'),quality=94);rows.append(row)
    report['aggregate']={k:float(np.mean([v[k] for v in report['views']])) for k in ['mesh_coverage_fraction','mesh_psnr_full_db','mesh_ssim_full','splat_psnr_full_db','splat_ssim_full']}
    report['metric_limits']='Same-session ARKit poses and LiDAR are not independent survey ground truth. PSNR/SSIM use full held-out images including unknown pixels. Reflections/exposure changes and calibration/pose error affect these numbers. Qualitative corner/detail inspection and navigation are required.'
    (out/'evaluation.json').write_text(json.dumps(report,indent=2));print(json.dumps(report['aggregate'],indent=2))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('output',type=Path);p.add_argument('--splat-renders',type=Path);a=p.parse_args()
    if not a.splat_renders:render_mesh(a.source,a.output)
    else:compare(a.source,a.output,a.splat_renders)
