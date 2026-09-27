"""Validate the classic float32 Gaussian PLY dialect used by local benchmarks.

NumPy is needed only for offline preparation; the viewer remains stdlib-only.
"""
import hashlib
from pathlib import Path
import numpy as np


def read_gaussian_ply(path):
    path=Path(path)
    with path.open('rb') as stream:
        header=[]
        while stream.tell()<65536:
            line=stream.readline().decode('ascii').strip();header.append(line)
            if line=='end_header':break
            if not line:raise ValueError('Incomplete Gaussian PLY header')
        else:raise ValueError('Gaussian PLY header too large')
        if header[:2]!=['ply','format binary_little_endian 1.0']:raise ValueError('Expected binary little-endian PLY')
        elements=[line.split() for line in header if line.startswith('element ')]
        if len(elements)!=1 or elements[0][1]!='vertex':raise ValueError('Expected Gaussian vertices without mesh faces')
        count=int(elements[0][2]);props=[line.split() for line in header if line.startswith('property ')]
        if not 0<count<=10_000_000 or any(len(p)!=3 or p[1]!='float' for p in props):raise ValueError('Unsupported Gaussian vertex layout')
        names=[p[2] for p in props]
        required=['x','y','z','f_dc_0','f_dc_1','f_dc_2','opacity','scale_0','scale_1','scale_2','rot_0','rot_1','rot_2','rot_3']
        if len(set(names))!=len(names) or not set(required)<=set(names):raise ValueError('Missing or duplicate Gaussian properties')
        offset=stream.tell()
        if path.stat().st_size!=offset+count*len(names)*4:raise ValueError('PLY byte length does not match header')
        data=np.fromfile(stream,dtype=[(name,'<f4') for name in names],count=count)
    for name in names:
        valid=~np.isnan(data[name]) if name=='opacity' else np.isfinite(data[name])
        if not valid.all():raise ValueError('Invalid nonfinite Gaussian field: '+name)
    quat=np.stack([data[f'rot_{i}'] for i in range(4)],1);norm=np.linalg.norm(quat,axis=1)
    if (norm<1e-6).any():raise ValueError('Zero Gaussian rotation quaternion')
    scales=np.stack([data[f'scale_{i}'] for i in range(3)],1)
    if np.max(scales)>20 or np.min(scales)<-100:raise ValueError('Unsupported Gaussian log-scale range')
    rest=[name for name in names if name.startswith('f_rest_')]
    degree={0:0,9:1,24:2,45:3}.get(len(rest))
    if degree is None or set(rest)!={f'f_rest_{i}' for i in range(len(rest))}:raise ValueError('Unsupported spherical harmonic layout')
    xyz=np.stack([data[name] for name in ['x','y','z']],1)
    with path.open('rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
    report={'sha256':digest,'bytes':path.stat().st_size,'header_bytes':offset,'vertices':count,'float_properties':names,
            'spherical_harmonic_degree':degree,'positive_infinite_opacity_logits':int(np.isposinf(data['opacity']).sum()),
            'negative_infinite_opacity_logits':int(np.isneginf(data['opacity']).sum()),
            'opacity_policy':'Infinite logits are valid sigmoid saturation (alpha 1 or 0); NaN is rejected. No source values changed.',
            'quaternion_norm_range':[float(norm.min()),float(norm.max())],
            'center_bounds_native':[xyz.min(0).tolist(),xyz.max(0).tolist()],
            'header_comments':[line for line in header if line.startswith(('comment ','obj_info '))],
            'limitations':'No source photographs, camera poses, intrinsics, capture duration, train/test split, depth confidence, processing settings or measured unit declaration in this PLY.'}
    return data,report
