#!/usr/bin/env python3
"""Approximate landmark scale/orientation checks; not independent survey accuracy."""
import argparse,json
from pathlib import Path
import numpy as np
import open3d as o3d
from gaussian_ply import read_gaussian_ply


def check(manifest,scan,reference,output):
    m=json.loads(manifest.read_text());data,_=read_gaussian_ply(manifest.parent/m['model_file'])
    p=np.stack([data[k] for k in ['x','y','z']],1);sigma=np.exp(np.stack([data[f'scale_{i}'] for i in range(3)],1))
    mask=(data['opacity']>0)&(sigma.max(1)<.1)&(np.linalg.norm(p-np.median(p,axis=0),axis=1)<15)
    transform=np.array(m['source_to_reference_row_major']);external=p[mask]@transform[:3,:3].T+transform[:3,3]
    mesh=o3d.io.read_triangle_mesh(str(reference/'colored-mesh.ply'));ours=np.asarray(mesh.vertices)
    room=json.loads((scan/'Room.json').read_text());rows=[]
    for kind,indices in [('walls',[0,1,2,7,9]),('floors',[0])]:
        for index in indices:
            element=room[kind][index];pose=np.array(element['transform']).reshape((4,4),order='F');width,height=element['dimensions'][:2]
            row={'landmark':f'{kind} {index+1}','reference_dimensions_m':[width,height]}
            for label,points in [('our_mesh',ours),('external',external)]:
                q=(points-pose[:3,3])@pose[:3,:3];inside=(np.abs(q[:,0])<width/2-.10)&(np.abs(q[:,1])<height/2-.10)&(np.abs(q[:,2])<.20)
                if kind=='walls':inside&=points[:,1]>-.25 # broad wall faces above most furniture
                selected=q[inside];row[label]={'points':len(selected),'signed_plane_offset_m':float(np.median(selected[:,2])) if len(selected) else None,'abs_offset_p90_m':float(np.percentile(np.abs(selected[:,2]),90)) if len(selected) else None}
            rows.append(row)
    widths=[]
    for a,b in [(0,9),(0,1)]:
        aa,bb=room['walls'][a],room['walls'][b];pa=np.array(aa['transform']).reshape(4,4,order='F');pb=np.array(bb['transform']).reshape(4,4,order='F')
        distance=float((pb[:3,3]-pa[:3,3])@pa[:3,2]);width={'walls':[a+1,b+1],'roomplan_separation_m':distance}
        ra=next(r for r in rows if r['landmark']==f'walls {a+1}');rb=next(r for r in rows if r['landmark']==f'walls {b+1}')
        for name in ['our_mesh','external']:
            offset_a=ra[name]['signed_plane_offset_m'];offset_b=rb[name]['signed_plane_offset_m']
            width[name+'_separation_m']=distance-offset_a-offset_b if offset_a is not None and offset_b is not None else None
        widths.append(width)
    furniture=[]
    for index in [5,11,15]:
        element=room['objects'][index];pose=np.array(element['transform']).reshape(4,4,order='F');dims=np.array(element['dimensions']);row={'object':index+1,'category':next(iter(element['category'])),'roomplan_dimensions_m':dims.tolist()}
        for label,points in [('our_mesh',ours),('external',external)]:
            local=(points-pose[:3,3])@pose[:3,:3]
            inside=np.all(np.abs(local)<dims/2+.12,axis=1)
            if index==5:inside&=np.abs(local[:,1]-dims[1]/2)<.07 # tabletop slab
            if index==11:inside&=np.abs(local[:,2]-dims[2]/2)<.08 # TV face slab
            q=local[inside]
            row[label]={'points':len(q),'central_96_percent_extent_m':(np.percentile(q,98,axis=0)-np.percentile(q,2,axis=0)).tolist() if len(q) else None}
        furniture.append(row)
    report={'transform_determinant':float(np.linalg.det(transform[:3,:3])),'scale_fixed':1,'source_Y_axis_in_reference':transform[:3,1].tolist(),
            'plane_checks':rows,'wall_separations':widths,'furniture_extents':furniture,
            'limits':'These are ROI/gate-dependent checks against RoomPlan estimates and the fitted reference mesh. Source centers were filtered for alignment, not for display. Furniture slabs include clutter and Gaussian centers are not certified surfaces. No independent dimensions, no optimized scale, no claim of exact registration.'}
    output.write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('manifest',type=Path);p.add_argument('scan',type=Path);p.add_argument('reference',type=Path);p.add_argument('output',type=Path);a=p.parse_args();check(a.manifest,a.scan,a.reference,a.output)
