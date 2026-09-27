#!/usr/bin/env python3
"""Audit a private room pass without changing its files or reconstruction settings."""
import argparse,collections,hashlib,json
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw
from import_scan import validate
from assess_coverage import matrix
from reconstruct_room import split_frames

def verify_split(source,reconstruction,train,test,held):
    """Check the actual prepared dataset, including all withheld images and cameras."""
    split=json.loads((reconstruction/'split.json').read_text())
    expected={'train':[f['rgb_file'] for f in train], 'held_out':[f['rgb_file'] for f in test],
              'excluded_held_out_frames':[f['rgb_file'] for f in held]}
    for key,names in expected.items():
        if split[key]!=names:raise ValueError(f'Reconstruction split differs: {key}')
    if split['index_sha256']!=hashlib.sha256((source/'Frames.json').read_bytes()).hexdigest():
        raise ValueError('Reconstruction is not pinned to this frame index')
    if (reconstruction/'pose-refinement.json').exists():raise ValueError('This capture-only comparison requires original poses')
    for phase,frames in [('train',train),('test',test)]:
        data=json.loads((reconstruction/f'brush-data/transforms_{phase}.json').read_text())['frames']
        if [Path(f['file_path']).name for f in data]!=[f['rgb_file'] for f in frames]:
            raise ValueError(f'Brush {phase} split differs')
        for actual,original in zip(data,frames):
            k=matrix(original,'intrinsics_column_major',3)
            if not np.array_equal(actual['transform_matrix'],matrix(original,'camera_to_world_column_major',4)):
                raise ValueError('Prepared camera pose differs from capture')
            if [actual[key] for key in ['w','h','fl_x','fl_y','cx','cy']]!=[original['image_width'],original['image_height'],k[0,0],k[1,1],k[0,2],k[1,2]]:
                raise ValueError('Prepared calibration differs from capture')
    texture_names={p.name for p in (reconstruction/'mesh/textures').glob('*.jpg')}
    if not texture_names<=set(expected['train']):raise ValueError('Non-training photograph used as texture')
    return dict(split_matches_capture=True,brush_cameras_match_capture=True,texture_images_train_only=True,
                excluded_frames=len(held),evaluation_frames=len(test))

def audit(source,output,diagnostics=None,reconstruction=None):
    manifest=validate(source);index=json.loads((source/'Frames.json').read_text());frames=index['frames'];train,test=split_frames(frames)
    held=[f for f in frames if f.get('capture_phase')=='held_out']
    if len(train)+len(held)!=len(frames):raise ValueError('Unexpected capture phase')
    phases=[f['capture_phase'] for f in frames]
    if phases!=['train']*len(train)+['held_out']*len(held):raise ValueError('Capture phases must form one train segment then one held-out segment')
    timestamps=np.array([f['timestamp_seconds'] for f in frames]);steps=np.diff(timestamps)
    if not np.all(steps>0):raise ValueError('Capture timestamps must strictly increase')
    depth_valid=[];confidence_high=[];rotation_error=[];position=[];rates=[]
    for frame in frames:
        with Image.open(source/frame['rgb_file']) as im:
            if im.size!=(frame['image_width'],frame['image_height']):raise ValueError('JPEG dimensions disagree with calibration')
            im.verify()
        shape=(frame['depth_height'],frame['depth_width']);d=np.fromfile(source/frame['depth_file'],dtype='<f4').reshape(shape);c=np.fromfile(source/frame['confidence_file'],dtype='u1').reshape(shape)
        depth_valid.append(float((np.isfinite(d)&(d>0)).mean()));confidence_high.append(float((c==2).mean()))
        pose=matrix(frame,'camera_to_world_column_major',4);r=pose[:3,:3]
        error=max(float(np.abs(r.T@r-np.eye(3)).max()),abs(float(np.linalg.det(r))-1))
        if error>1e-4 or not np.allclose(pose[3],[0,0,0,1]):raise ValueError('Nonrigid camera pose')
        rotation_error.append(error);position.append(pose[:3,3])
    poses=np.array([matrix(f,'camera_to_world_column_major',4) for f in frames]);position=np.array(position)
    speeds=np.linalg.norm(np.diff(position,axis=0),axis=1)/steps
    for a,b,dt in zip(poses[:-1],poses[1:],steps):
        rates.append(float(np.degrees(np.arccos(np.clip((np.trace(a[:3,:3].T@b[:3,:3])-1)/2,-1,1)))/dt))
    def stats(x):return dict(minimum=float(np.min(x)),median=float(np.median(x)),p90=float(np.percentile(x,90)),maximum=float(np.max(x)))
    logs=[]
    if diagnostics:
        # Match this capture interval; do not mix earlier sessions from an append-only log.
        logs=[line for line in diagnostics.read_text().splitlines() if index['started_at']<=line[:20]<=index['ended_at'] or (line[:20]>index['ended_at'] and manifest['scan_id'] in line)]
    polls=[line for line in logs if ' Room pass;' in line]
    report=dict(scan_id=manifest['scan_id'],started_at=index['started_at'],ended_at=index['ended_at'],profile=index.get('capture_profile'),guidance_version=index.get('guidance_version'),motion_coaching_warning_samples=index.get('motion_coaching_warning_samples'),
        core_hashes=len(manifest['sha256']),extension_hashes=len(manifest.get('sparse_frames',{}).get('sha256',{})),index_sha256=hashlib.sha256((source/'Frames.json').read_bytes()).hexdigest(),
        frame_sets=len(frames),train_frames=len(train),excluded_held_out_frames=len(held),evaluated_held_out_frames=[f['rgb_file'] for f in test],
        split_policy='All capture-designated held-out RGB/depth excluded from fusion, textures, seeds and optimization; every fifth held-out view evaluated, unchanged policy.',
        timestamps_strictly_increasing=bool(np.all(steps>0)),timestamp_span_seconds=float(timestamps[-1]-timestamps[0]),sample_intervals_seconds=stats(steps),held_out_span_seconds=held[-1]['timestamp_seconds']-held[0]['timestamp_seconds'],
        frame_tracking_states=dict(collections.Counter(f.get('tracking_state') for f in frames)),skipped=index.get('skipped'),write_errors=index.get('write_errors'),thermal_stop=index.get('thermal_guard'),
        encode_milliseconds=stats(index['encode_milliseconds']),valid_depth_fraction=stats(depth_valid),high_confidence_fraction=stats(confidence_high),max_rotation_rigidity_error=max(rotation_error),
        speed_m_s=stats(speeds),turn_degrees_s=stats(rates),path_length_m=float(np.linalg.norm(np.diff(position,axis=0),axis=1).sum()),
        sampled_tracking_polls=len(polls),normal_tracking_polls=sum('tracking=normal' in line for line in polls),nominal_thermal_polls=sum('thermal=0' in line for line in polls),
        roomplan_error_nil=any('RoomPlan session ended; error=nil' in line for line in logs),saved_package_logged=any('Saved package:' in line for line in logs),
        limits='Tracking admission and five-second polls do not measure every frame or prove zero performance impact. Motion is between saved poses, not exposure-time blur. Confidence is not metric survey accuracy.')
    if reconstruction:report['prepared_dataset']=verify_split(source,reconstruction,train,test,held)
    output.mkdir(parents=True,exist_ok=True);(output/'capture-audit.json').write_text(json.dumps(report,indent=2))
    if logs:(output/'capture-session-log.txt').write_text('\n'.join(logs)+'\n')
    for label,selected in [('held-out-contact',test),('training-overview',train[::20])]:
        sheet=Image.new('RGB',(6*220,((len(selected)+5)//6)*315),(24,29,35));draw=ImageDraw.Draw(sheet)
        for i,f in enumerate(selected):
            im=Image.open(source/f['rgb_file']).rotate(-90,expand=True);im.thumbnail((210,280));x=(i%6)*220;y=(i//6)*315;sheet.paste(im,(x,y+30));draw.text((x+4,y+7),f['rgb_file'],fill='white')
        sheet.save(output/(label+'.jpg'),quality=95)
    print(json.dumps(report,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('output',type=Path);p.add_argument('--diagnostics',type=Path);p.add_argument('--reconstruction',type=Path);a=p.parse_args();audit(a.source,a.output,a.diagnostics,a.reconstruction)
