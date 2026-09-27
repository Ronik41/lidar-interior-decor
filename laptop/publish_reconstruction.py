#!/usr/bin/env python3
"""Register PRIVATE local candidate assets for the editor. Does not upload anything."""
import argparse,hashlib,json,shutil
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('output',type=Path);p.add_argument('--splat',type=Path);p.add_argument('--preferred',choices=['mesh','splat'],default='mesh');p.add_argument('--splat-selection',type=Path,help='Frozen dense selection used for the supplied splat');a=p.parse_args()
manifest=json.loads((a.source/'manifest.json').read_text())
index=a.source/('Frames.json' if (a.source/'Frames.json').exists() else 'DenseFrames.json')
frames=json.loads(index.read_text())['frames']
# Re-registering a capture preserves its explicitly reviewed viewpoint labels.
previous=a.output/'reconstruction.json'
old=json.loads(previous.read_text()) if previous.exists() else {}
views=old.get('viewpoints',[]) if old.get('source_scan_id')==manifest['scan_id'] else []
if not views:
 choices=[f for f in frames if f.get('capture_phase')=='held_out'] or frames
 choices=choices[::max(1,len(choices)//5)][:5]
 views=[{'label':f'Captured viewpoint {i+1}',**{key:f[key] for key in ['camera_to_world_column_major','intrinsics_column_major','image_width','image_height','rgb_file']}} for i,f in enumerate(choices)]
training_count=sum(f.get('capture_phase','train')=='train' for f in frames)
mesh_training_count=training_count
split_path=a.output/'split.json'
if split_path.exists():
 split=json.loads(split_path.read_text())
 if split['source_scan_id']!=manifest['scan_id'] or split['index_sha256']!=hashlib.sha256(index.read_bytes()).hexdigest():raise ValueError('Mesh split belongs to a different capture')
 mesh_training_count=len(split['train'])
if a.splat_selection:
 if not a.splat:raise ValueError('A splat selection requires a splat')
 from capture_selection import selected_split
 selected,_=selected_split(a.source,frames,json.loads(a.splat_selection.read_text()))
 training_count=len(selected)
if a.splat:
 shutil.copy2(a.splat,a.output/'room-splat.ply')
assets={}
for file in sorted((a.output/'mesh').rglob('*')):
 if file.is_file(): assets[file.relative_to(a.output).as_posix()]=hashlib.sha256(file.read_bytes()).hexdigest()
if a.splat:assets['room-splat.ply']=hashlib.sha256((a.output/'room-splat.ply').read_bytes()).hexdigest()
appearance=f'Mesh from {mesh_training_count} training RGB-D views'
if a.splat:appearance+=f'; splat from {training_count} training RGB views'
data={'schema_version':1,'source_scan_id':manifest['scan_id'],'frames_index_file':index.name,'frames_sha256':hashlib.sha256(index.read_bytes()).hexdigest(),'coordinate_system':'ARKit world meters, same capture session as RoomPlan; no estimated cross-session alignment','preferred':a.preferred,'mesh_url':'/reconstruction/mesh/room.gltf','splat_url':'/reconstruction/room-splat.ply' if a.splat else None,'viewpoints':views,'provenance':f'Local iPhone RGB-D reconstruction · {appearance} · RoomPlan from the same session is a separate editable layer. Gaps lack reliable reconstruction; unseen backs remain unknown.','assets':assets}
(a.output/'reconstruction.json').write_text(json.dumps(data,indent=2));print('Registered',len(assets),'private assets for',manifest['scan_id'])
