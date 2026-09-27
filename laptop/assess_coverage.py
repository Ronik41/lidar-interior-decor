"""Measure pose/depth view overlap; retain private contact sheet and per-pair evidence."""
import argparse, json
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw

def load_frames(folder):
    return json.loads((folder/'Frames.json').read_text())['frames']

def matrix(f,key,n):
    return np.array(f[key]).reshape(n,n,order='F')

def depth_points(folder,f,stride=4):
    h,w=f['depth_height'],f['depth_width']
    d=np.fromfile(folder/f['depth_file'],dtype='<f4').reshape(h,w)[::stride,::stride]
    c=np.fromfile(folder/f['confidence_file'],dtype='u1').reshape(h,w)[::stride,::stride]
    v,u=np.mgrid[:h:stride,:w:stride];k=matrix(f,'depth_intrinsics_column_major',3)
    valid=np.isfinite(d)&(d>.2)&(d<5)&(c>=1)
    p=np.stack([(u-k[0,2])*d/k[0,0],-(v-k[1,2])*d/k[1,1],-d,np.ones_like(d)],-1)[valid]
    return (matrix(f,'camera_to_world_column_major',4)@p.T).T

def overlap(folder,a,b):
    pts=depth_points(folder,a)
    q=(np.linalg.inv(matrix(b,'camera_to_world_column_major',4))@pts.T).T
    k=matrix(b,'depth_intrinsics_column_major',3);z=-q[:,2]
    uv=np.stack([q[:,0]*k[0,0]/np.maximum(z,.001)+k[0,2],-q[:,1]*k[1,1]/np.maximum(z,.001)+k[1,2]],1).round().astype(int)
    w,h=b['depth_width'],b['depth_height'];ok=(z>.2)&(uv[:,0]>=0)&(uv[:,0]<w)&(uv[:,1]>=0)&(uv[:,1]<h)
    d=np.fromfile(folder/b['depth_file'],dtype='<f4').reshape(h,w)
    supported=np.zeros(len(q),bool);supported[ok]=np.abs(d[uv[ok,1],uv[ok,0]]-z[ok])<.15
    return float(supported.mean()) if len(q) else 0

def assess(folder,out):
    out.mkdir(parents=True,exist_ok=True);frames=load_frames(folder)
    poses=np.stack([matrix(f,'camera_to_world_column_major',4) for f in frames]);p=poses[:,:3,3]
    pair=[overlap(folder,a,b) for a,b in zip(frames[:-1],frames[1:])]
    forward=-poses[:,:3,2];yaw=np.arctan2(forward[:,0],forward[:,2]);bins=np.unique((np.mod(yaw,2*np.pi)/(2*np.pi)*12).astype(int))
    report={'frames':len(frames),'path_length_m':float(np.linalg.norm(np.diff(p,axis=0),axis=1).sum()),'position_span_xyz_m':np.ptp(p,axis=0).tolist(),'yaw_sectors_covered_of_12':len(bins),'adjacent_depth_overlap_fraction':pair,'median_adjacent_overlap':float(np.median(pair)),'pairs_below_50_percent_overlap':sum(x<.5 for x in pair),'method':'Fraction of medium/high-confidence source depths reprojecting within 15cm of next frame depth, range 0.2–5m; directional estimate, not completeness ground truth.'}
    (out/'coverage.json').write_text(json.dumps(report,indent=2))
    sheet=Image.new('RGB',(5*230,((len(frames)+4)//5)*340),(24,29,35));draw=ImageDraw.Draw(sheet)
    for i,f in enumerate(frames):
        im=Image.open(folder/f['rgb_file']).rotate(90,expand=True);im.thumbnail((220,306));x=(i%5)*230;y=(i//5)*340;sheet.paste(im,(x,y));draw.text((x+5,y+308),f'{i+1:03d}  t={f["timestamp_seconds"]-frames[0]["timestamp_seconds"]:.1f}s',fill='white')
    sheet.save(out/'contact-sheet.jpg');print(json.dumps(report,indent=2))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('folder',type=Path);p.add_argument('output',type=Path);a=p.parse_args();assess(a.folder,a.output)
