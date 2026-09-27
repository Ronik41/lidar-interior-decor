#!/usr/bin/env python3
"""Validate and rigidly register a local classic Gaussian PLY to our RGB-D mesh.

Four PCA sign candidates, bounded robust ICP, no scale fitting. Inspect the
result against recognizable room features before accepting a benchmark.
"""
import argparse
import hashlib
import itertools
import json
import time
from pathlib import Path
import numpy as np
import open3d as o3d
from gaussian_ply import read_gaussian_ply
from benchmark_assets import rigid_matrix


def register(ply,reference,output):
    if output.exists():raise ValueError('Use a new manifest filename; existing benchmark registration is preserved')
    if output.parent.resolve()!=ply.parent.resolve():raise ValueError('Keep benchmark manifest beside its private PLY')
    start=time.monotonic();data,validation=read_gaussian_ply(ply)
    xyz=np.stack([data[name] for name in ['x','y','z']],1)
    sigma=np.exp(np.stack([data[f'scale_{i}'] for i in range(3)],1))
    selected=(data['opacity']>0)&(sigma.max(1)<.1)&(np.linalg.norm(xyz-np.median(xyz,axis=0),axis=1)<15)
    source=o3d.geometry.PointCloud(o3d.utility.Vector3dVector(xyz[selected]));mesh=o3d.io.read_triangle_mesh(str(reference/'colored-mesh.ply'))
    target=o3d.geometry.PointCloud(mesh.vertices)
    if len(source.points)<1000 or len(target.points)<1000:raise ValueError('Insufficient registration geometry')
    r=o3d.pipelines.registration;s=source.voxel_down_sample(.08);t=target.voxel_down_sample(.08)
    t.estimate_normals(o3d.geometry.KDTreeSearchParamHybrid(radius=.24,max_nn=40))
    sp,tp=np.asarray(s.points),np.asarray(t.points);sm,tm=sp.mean(0),tp.mean(0)
    _,sa=np.linalg.eigh(np.cov(sp.T));_,ta=np.linalg.eigh(np.cov(tp.T));candidates=[]
    for signs in itertools.product([-1,1],repeat=3):
        rot=ta@np.diag(signs)@sa.T
        if np.linalg.det(rot)<0:continue
        transform=np.eye(4);transform[:3,:3]=rot;transform[:3,3]=tm-rot@sm
        for gate in [.5,.25,.12]:
            result=r.registration_icp(s,t,gate,transform,r.TransformationEstimationPointToPlane(r.TukeyLoss(k=gate)),r.ICPConvergenceCriteria(max_iteration=60));transform=result.transformation
        candidates.append({'pca_signs':signs,'fitness':result.fitness,'rmse_m':result.inlier_rmse,'transform_row_major':transform.tolist()})
    best=max(candidates,key=lambda c:c['fitness']);transform=np.array(best['transform_row_major']);stages=[]
    for voxel,gate in [(.04,.12),(.025,.08)]:
        s=source.voxel_down_sample(voxel);t=target.voxel_down_sample(voxel)
        t.estimate_normals(o3d.geometry.KDTreeSearchParamHybrid(radius=voxel*3,max_nn=40))
        result=r.registration_icp(s,t,gate,transform,r.TransformationEstimationPointToPlane(r.TukeyLoss(k=gate)),r.ICPConvergenceCriteria(max_iteration=60));transform=result.transformation
        stages.append({'voxel_m':voxel,'gate_m':gate,'fitness':result.fitness,'rmse_m':result.inlier_rmse})
    if stages[-1]['fitness']<.4:raise ValueError('Insufficient geometric overlap; do not publish this registration')
    values=transform.flatten(order='F').tolist();rigid_matrix(values)
    meta=json.loads((reference/'reconstruction.json').read_text())
    report={'schema_version':1,'kind':'external-gaussian-benchmark','label':'Scaniverse · external benchmark',
            'model_file':ply.name,'model_sha256':validation['sha256'],'validation':validation,
            'reference_scan_id':meta['source_scan_id'],'reference_frames_sha256':meta['frames_sha256'],
            'reference_reconstruction_sha256':hashlib.sha256((reference/'reconstruction.json').read_bytes()).hexdigest(),
            'reference_mesh_sha256':hashlib.sha256((reference/'colored-mesh.ply').read_bytes()).hexdigest(),
            'source_to_reference_column_major':values,'source_to_reference_row_major':transform.tolist(),
            'scale':1,'transform_convention':'p_reference_ARKit = R * p_external + t; meters assumed then checked, never rescaled. Viewer additionally applies the same RoomPlan plan rotation to both layers.',
            'registration_summary':'Rigid PCA initialization + robust point-to-plane ICP against our second capture mesh; approximate alignment, scale fixed at 1.',
            'provenance':'Scaniverse PLY supplied by the user · externally produced, different capture · camera/processing history unavailable · rigidly registered to our second room scan; no rescaling. Shared viewpoints are comparison cameras, not known Scaniverse held-out views.',
            'method':{'source_filter':'opacity logit >0, largest Gaussian sigma <0.1 native units, within 15 units of median center; registration only, full unmodified PLY rendered',
                      'registration_source_centers':int(selected.sum()),'coarse_voxel_m':.08,'pca_candidates':candidates,
                      'coarse_gates_m':[.5,.25,.12],'max_iterations_per_stage':60,'fine_stages':stages,
                      'loss':'Tukey point-to-plane','seconds':time.monotonic()-start},
            'limits':'ICP residual measures fitted inlier agreement, not independent accuracy. Gaussian centers are appearance primitives, not certified surfaces. No capture-matched PSNR/SSIM comparison is possible.'}
    output.write_text(json.dumps(report,indent=2,allow_nan=False))
    print(json.dumps({'vertices':validation['vertices'],'transform':transform.tolist(),'stages':stages,'seconds':report['method']['seconds']},indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('ply',type=Path);p.add_argument('reference',type=Path);p.add_argument('manifest',type=Path)
    a=p.parse_args();register(a.ply,a.reference,a.manifest)
