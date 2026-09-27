"""Optional, explicitly registered external splat. No external service dependency."""
import hashlib
import json
import math
from pathlib import Path, PurePosixPath


def rigid_matrix(values):
    if not isinstance(values,list) or len(values)!=16 or any(type(v) not in (int,float) or not math.isfinite(v) for v in values):
        raise ValueError('Benchmark transform must contain 16 finite column-major numbers')
    if any(abs(values[i]-v)>1e-6 for i,v in zip([3,7,11,15],[0,0,0,1])):
        raise ValueError('Benchmark transform must be affine')
    r=[[values[col*4+row] for col in range(3)] for row in range(3)]
    for i in range(3):
        for j in range(3):
            if abs(sum(r[k][i]*r[k][j] for k in range(3))-(i==j))>1e-5:
                raise ValueError('Benchmark registration must be rigid; scale/shear is not allowed')
    det=r[0][0]*(r[1][1]*r[2][2]-r[1][2]*r[2][1])-r[0][1]*(r[1][0]*r[2][2]-r[1][2]*r[2][0])+r[0][2]*(r[1][0]*r[2][1]-r[1][1]*r[2][0])
    if abs(det-1)>1e-5:raise ValueError('Benchmark registration must preserve handedness')
    return values


class BenchmarkAssets:
    def __init__(self,manifest,store,reconstruction):
        manifest=Path(manifest).resolve();self.root=manifest.parent
        self.metadata=json.loads(manifest.read_text())
        m=self.metadata
        if not isinstance(m,dict):raise ValueError('Benchmark manifest must be an object')
        if m.get('schema_version')!=1 or m.get('kind')!='external-gaussian-benchmark':raise ValueError('Unsupported external benchmark manifest')
        for key in ['label','provenance','registration_summary','model_file']:
            if not isinstance(m.get(key),str) or not m[key].strip():raise ValueError('Missing benchmark field: '+key)
        if m.get('reference_scan_id')!=store.source['scan_id']:raise ValueError('Benchmark registration targets a different room scan')
        if m.get('reference_frames_sha256')!=reconstruction.metadata['frames_sha256']:raise ValueError('Benchmark reference cameras changed')
        if m.get('reference_reconstruction_sha256')!=hashlib.sha256((reconstruction.root/'reconstruction.json').read_bytes()).hexdigest():raise ValueError('Benchmark reference reconstruction changed')
        rigid_matrix(m.get('source_to_reference_column_major'))
        name=m.get('model_file','');relative=PurePosixPath(name)
        if not name or relative.is_absolute() or '..' in relative.parts or str(relative)!=name:raise ValueError('Unsafe benchmark model path')
        self.model=self.root/name
        if self.model.is_symlink() or not self.model.is_file() or not self.model.resolve().is_relative_to(self.root):raise ValueError('Missing or unsafe benchmark model')
        with self.model.open('rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
        if digest!=m.get('model_sha256'):raise ValueError('External benchmark checksum mismatch')
        validation=m.get('validation')
        if not isinstance(validation,dict) or validation.get('sha256')!=digest:raise ValueError('External PLY validation is missing or stale')

    def payload(self):
        m=self.metadata
        return {'label':m['label'],'url':'/benchmark/model.ply','source_to_reference_column_major':m['source_to_reference_column_major'],
                'provenance':m['provenance'],'model_sha256':m['model_sha256'],'registration_summary':m['registration_summary']}
