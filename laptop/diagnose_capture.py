#!/usr/bin/env python3
"""Depth-independent epipolar and RGB-D reprojection checks, plus capture motion.

SIFT/RANSAC observations are diagnostics, never inputs to pose refinement. No
held-out RGB/depth is used for optimization. Scores do not establish ground truth.
"""
import argparse,json,time
from pathlib import Path
import cv2
import numpy as np
from PIL import Image,ImageDraw
from assess_coverage import load_frames,matrix
from reconstruct_room import split_frames,extrinsic,read_depth
from pose_overrides import apply_poses

def stats(values):
    values=np.asarray(values,dtype=float);values=values[np.isfinite(values)]
    return dict(count=len(values),median=float(np.median(values)),p90=float(np.percentile(values,90)),maximum=float(values.max())) if len(values) else None

def intrinsics(frame,width=960):
    k=matrix(frame,'intrinsics_column_major',3).astype(float);k[:2]*=width/frame['image_width'];return k

def epipolar_error(first,second,uv1,uv2):
    transform=extrinsic(second)@np.linalg.inv(extrinsic(first));t=transform[:3,3]
    skew=np.array([[0,-t[2],t[1]],[t[2],0,-t[0]],[-t[1],t[0],0]])
    fundamental=np.linalg.inv(intrinsics(second)).T@skew@transform[:3,:3]@np.linalg.inv(intrinsics(first))
    a=np.column_stack([uv1,np.ones(len(uv1))]);b=np.column_stack([uv2,np.ones(len(uv2))])
    fa=a@fundamental.T;fb=b@fundamental
    return np.abs((b*fa).sum(1))/np.sqrt(np.maximum((fa[:,:2]**2).sum(1)+(fb[:,:2]**2).sum(1),1e-20))

def reprojection(first,second,uv1,uv2,depth):
    k=intrinsics(first);points=np.column_stack([uv1,np.ones(len(uv1))])@np.linalg.inv(k).T*depth[:,None]
    transform=extrinsic(second)@np.linalg.inv(extrinsic(first));points=points@transform[:3,:3].T+transform[:3,3]
    projected=points@intrinsics(second).T;projected=projected[:,:2]/projected[:,2,None]
    return np.linalg.norm(projected-uv2,axis=1)

def diagnose(source,output,poses=None):
    start=time.monotonic();cv2.setNumThreads(2);cv2.setRNGSeed(42)
    frames=load_frames(source);train,test=split_frames(frames);refined={f['rgb_file']:f for f in apply_poses(source,frames,poses)}
    output.mkdir(parents=True,exist_ok=True);extractor=cv2.SIFT_create(nfeatures=1400)
    features={};quality=[];previous=None
    for frame in frames:
        rgb=np.asarray(Image.open(source/frame['rgb_file']).convert('RGB').resize((960,720),Image.Resampling.LANCZOS));gray=cv2.cvtColor(rgb,cv2.COLOR_RGB2GRAY)
        keypoints,descriptors=extractor.detectAndCompute(gray,None)
        features[frame['rgb_file']]=(np.asarray([k.pt for k in keypoints]),descriptors)
        pose=matrix(frame,'camera_to_world_column_major',4)
        row=dict(frame=frame['rgb_file'],phase=frame['capture_phase'],sift_features=len(keypoints),laplacian_variance=float(cv2.Laplacian(gray,cv2.CV_64F).var()),dark_fraction=float((gray<15).mean()),bright_fraction=float((gray>245).mean()))
        if previous:
            old,old_pose=previous;dt=frame['timestamp_seconds']-old['timestamp_seconds']
            angle=np.degrees(np.arccos(np.clip((np.trace(old_pose[:3,:3].T@pose[:3,:3])-1)/2,-1,1)))
            row.update(speed_m_s=float(np.linalg.norm(pose[:3,3]-old_pose[:3,3])/dt),turn_degrees_s=float(angle/dt))
        previous=(frame,pose);quality.append(row)
    positions=np.array([matrix(f,'camera_to_world_column_major',4)[:3,3] for f in train]);directions=np.array([-matrix(f,'camera_to_world_column_major',4)[:3,2] for f in train])
    pairs=[]
    for i in range(0,len(train)-1,3):
        pairs.append((train[i],train[i+1],'adjacent_training'))
        distance=np.linalg.norm(positions-positions[i],axis=1);alignment=directions@directions[i]
        candidates=np.flatnonzero((np.abs(np.arange(len(train))-i)>20)&(distance<1.5)&(alignment>.7))
        if len(candidates):
            j=candidates[np.argmin(distance[candidates]+(1-alignment[candidates]))];pairs.append((train[i],train[j],'revisit_training'))
    # Coverage checks only: these test images never enter registration or training.
    for f in test:
        pose=matrix(f,'camera_to_world_column_major',4);distance=np.linalg.norm(positions-pose[:3,3],axis=1);alignment=directions@(-pose[:3,2])
        for j in np.argsort(distance+3*(1-alignment))[:3]:pairs.append((f,train[j],'held_out_support'))
    matcher=cv2.BFMatcher();rows=[];cache={}
    for index,(first,second,kind) in enumerate(pairs):
        uv1,desc1=features[first['rgb_file']];uv2,desc2=features[second['rgb_file']]
        if desc1 is None or desc2 is None:continue
        forward=matcher.knnMatch(desc1,desc2,k=2);back=matcher.knnMatch(desc2,desc1,k=2)
        backmap={a.queryIdx:a.trainIdx for pair in back if len(pair)==2 for a,b in [pair] if a.distance<.75*b.distance}
        good=[a for pair in forward if len(pair)==2 for a,b in [pair] if a.distance<.75*b.distance and backmap.get(a.trainIdx)==a.queryIdx]
        row=dict(first=first['rgb_file'],second=second['rgb_file'],kind=kind,mutual_matches=len(good))
        if len(good)<12:rows.append(row);continue
        a=np.array([uv1[m.queryIdx] for m in good]);b=np.array([uv2[m.trainIdx] for m in good])
        _,mask=cv2.findFundamentalMat(a,b,cv2.FM_RANSAC,1.5,.999)
        if mask is None:rows.append(row);continue
        a=a[mask.ravel()!=0];b=b[mask.ravel()!=0];row['ransac_matches']=len(a)
        depth=read_depth(source,first);pix=np.rint(a*[first['depth_width']/960,first['depth_height']/720]).astype(int)
        pix[:,0]=pix[:,0].clip(0,depth.shape[1]-1);pix[:,1]=pix[:,1].clip(0,depth.shape[0]-1);d=depth[pix[:,1],pix[:,0]]
        supported=d>0;aa=a[supported];bb=b[supported];dd=d[supported]
        row['depth_supported_matches']=len(aa)
        for name,lookup in [('baseline',lambda f:f),('registered',lambda f:refined[f['rgb_file']])]:
            f1,f2=lookup(first),lookup(second)
            row[name+'_epipolar_px']=stats(epipolar_error(f1,f2,a,b))
            row[name+'_rgbd_reprojection_px']=stats(reprojection(f1,f2,aa,bb,dd))
        cache[str(index)+'_first_uv']=a;cache[str(index)+'_second_uv']=b
        rows.append(row)
    np.savez_compressed(output/'diagnostic-correspondences.npz',**cache)
    aggregates={}
    for kind in ['adjacent_training','revisit_training','held_out_support']:
        subset=[r for r in rows if r['kind']==kind]
        aggregates[kind]={'pairs':len(subset),'successful_pairs':sum(r.get('ransac_matches',0)>=12 for r in subset)}
        for field in ['baseline_epipolar_px','registered_epipolar_px','baseline_rgbd_reprojection_px','registered_rgbd_reprojection_px']:
            aggregates[kind][field+'_pair_medians']=stats([r[field]['median'] for r in subset if r.get(field) and r.get('ransac_matches',0)>=12 and ('rgbd' not in field or r.get('depth_supported_matches',0)>=12)])
    report=dict(method='Mutual SIFT ratio .75 + independent fundamental RANSAC 1.5px; Sampson epipolar distance and high-confidence RGB-D reprojection at 960px width',
        limits='Feature checks mix pose, calibration, rolling shutter, matching and depth errors; not an independent survey. Laplacian variance depends on scene texture, not just motion blur. Revisit selection uses original poses. These correspondences were not optimized.',
        frame_quality=quality,pairs=rows,aggregate=aggregates,motion={key:stats([r[key] for r in quality if key in r]) for key in ['speed_m_s','turn_degrees_s']},seconds=time.monotonic()-start)
    (output/'diagnosis.json').write_text(json.dumps(report,indent=2));print(json.dumps({'motion':report['motion'],'aggregate':aggregates},indent=2))
    # Show the fastest rotations directly rather than declaring a sharpness threshold universal.
    fastest=sorted(quality,key=lambda r:r.get('turn_degrees_s',0),reverse=True)[:8]
    sheet=Image.new('RGB',(4*360,2*300),(25,30,35));draw=ImageDraw.Draw(sheet)
    for i,r in enumerate(fastest):
        im=Image.open(source/r['frame']).rotate(-90,expand=True);im.thumbnail((350,265));x=(i%4)*360;y=(i//4)*300;sheet.paste(im,(x,y+30));draw.text((x+4,y+6),f"{r['frame']} {r['turn_degrees_s']:.1f} deg/s",fill='white')
    sheet.save(output/'fast-turn-contact.jpg',quality=94)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('output',type=Path);p.add_argument('--poses',type=Path);a=p.parse_args();diagnose(a.source,a.output,a.poses)
