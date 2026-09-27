#!/usr/bin/env python3
"""Report same-session layer alignment, not independent dimensional accuracy."""
import argparse,json
from pathlib import Path
import numpy as np
import open3d as o3d
from assess_coverage import matrix
p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
room=json.loads((a.source/'Room.json').read_text());mesh=o3d.io.read_triangle_mesh(str(a.output/'colored-mesh.ply'));v=np.asarray(mesh.vertices)
rows=[]
for kind in ['walls','floors']:
 for i,s in enumerate(room[kind]):
  pose=np.array(s['transform']).reshape(4,4,order='F');local=(v-pose[:3,3])@pose[:3,:3]
  width,height=s['dimensions'][:2];inside=(np.abs(local[:,0])<width/2)&(np.abs(local[:,1])<height/2);d=np.abs(local[inside,2]);near=d[d<.20]
  rows.append({'kind':kind,'index':i+1,'source_width_m':width,'source_height_m':height,'mesh_vertices_inside_plane_bounds':len(d),'near_plane_vertices_within_20cm':len(near),'near_plane_median_abs_offset_m':float(np.median(near)) if len(near) else None})
eval=json.loads((a.output/'evaluation.json').read_text())
report={'coordinate_policy':'Unscaled ARKit metric world retained in depth fusion, Gaussian seeding, Nerfstudio cameras and RoomPlan layer. The same plan Y rotation is applied to both only for display. No cross-session alignment is assumed.','plane_offsets':rows,'median_of_held_out_median_depth_errors_m':float(np.median([x['median_depth_error_m'] for x in eval['views']])),'limitations':'Near-plane offsets use a 20cm association gate and can be biased by furniture or plane fitting. Held-out depth and poses share ARKit with training; neither is independent survey accuracy.'}
(a.output/'alignment.json').write_text(json.dumps(report,indent=2));print(json.dumps({k:v for k,v in report.items() if k!='plane_offsets'},indent=2))
