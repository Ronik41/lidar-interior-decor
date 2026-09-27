"""Optional v1 RGB-D extension. Legacy core payload hashes retain their contract."""
import hashlib
import json
import math
import re
import struct


def extension_hashes(manifest):
    extension = manifest.get('sparse_frames')
    if extension is None:
        return {}
    if (not isinstance(extension, dict) or set(extension) != {'schema_version','index_file','sha256'}
            or type(extension['schema_version']) is not int or extension['schema_version'] != 1
            or extension['index_file'] != 'Frames.json'):
        raise ValueError('Unsupported sparse frame extension')
    hashes = extension['sha256']
    if (not isinstance(hashes,dict) or not 1 <= len(hashes) <= 61 or 'Frames.json' not in hashes
            or any(name != 'Frames.json' and not re.fullmatch(r'Frame-\d{4}\.(jpg|depth\.f32|confidence\.u8)',name) for name in hashes)):
        raise ValueError('Invalid sparse frame file inventory')
    return hashes


def validate_sparse(source, manifest):
    hashes=extension_hashes(manifest)
    if not hashes:
        return
    for name,digest in hashes.items():
        path=source/name
        if (not isinstance(digest,str) or not re.fullmatch(r'[0-9a-f]{64}',digest)
                or path.is_symlink() or not path.is_file() or path.stat().st_size>64*1024*1024
                or hashlib.sha256(path.read_bytes()).hexdigest()!=digest):
            raise ValueError(f'Missing or damaged sparse frame: {name}')
    index=json.loads((source/'Frames.json').read_text())
    if not isinstance(index,dict) or type(index.get('schema_version')) is not int or index['schema_version']!=1:
        raise ValueError('Unsupported sparse frame index')
    frames=index.get('frames')
    if not isinstance(frames,list) or len(frames)>20 or type(index.get('saved_count')) is not int or index['saved_count']!=len(frames):
        raise ValueError('Invalid sparse frame count')
    used={'Frames.json'};previous=-math.inf
    for frame in frames:
        if not isinstance(frame,dict):raise ValueError('Invalid sparse frame record')
        timestamp=frame.get('timestamp_seconds')
        if type(timestamp) not in (int,float) or not math.isfinite(timestamp) or timestamp<=previous:
            raise ValueError('Sparse timestamps must be finite, unique and increasing')
        previous=timestamp
        for key,n in [('camera_to_world_column_major',16),('intrinsics_column_major',9),('depth_intrinsics_column_major',9)]:
            value=frame.get(key)
            if not isinstance(value,list) or len(value)!=n or any(type(x) not in (int,float) or not math.isfinite(x) for x in value):
                raise ValueError('Invalid sparse camera metadata: '+key)
        for key in ['image_width','image_height','depth_width','depth_height']:
            if type(frame.get(key)) is not int or not 0<frame[key]<=8192:raise ValueError('Invalid sparse frame dimensions')
        w,h=frame['depth_width'],frame['depth_height']
        if frame.get('depth_row_bytes')!=w*4 or frame.get('confidence_row_bytes')!=w:
            raise ValueError('Sparse buffers must be tightly packed')
        files=[]
        for key,suffix in [('rgb_file','.jpg'),('depth_file','.depth.f32'),('confidence_file','.confidence.u8')]:
            name=frame.get(key)
            if not isinstance(name,str) or name not in hashes or name in used or not name.endswith(suffix):
                raise ValueError('Invalid or duplicate sparse frame reference')
            used.add(name);files.append(name)
            checksum_key={'rgb_file':'rgb_sha256','depth_file':'depth_sha256','confidence_file':'confidence_sha256'}[key]
            if frame.get(checksum_key)!=hashes[name]:raise ValueError('Sparse frame checksum disagrees with manifest')
        rgb,depth,confidence=[(source/name).read_bytes() for name in files]
        if not rgb.startswith(b'\xff\xd8\xff') or len(depth)!=w*h*4 or len(confidence)!=w*h:
            raise ValueError('Invalid sparse buffer size or JPEG')
        if any(c>2 for c in confidence):raise ValueError('Invalid LiDAR confidence value')
        # Non-finite/nonpositive depth is retained as invalid, not silently fabricated.
        valid=sum(math.isfinite(v) and v>0 for (v,) in struct.iter_unpack('<f',depth))
        if not valid:raise ValueError('Sparse depth frame has no valid measurements')
        k,dk=frame['intrinsics_column_major'],frame['depth_intrinsics_column_major']
        if k[0]<=0 or k[4]<=0:raise ValueError('Invalid focal lengths')
        for i in range(9):
            scale=w/frame['image_width'] if i%3==0 else h/frame['image_height'] if i%3==1 else 1
            if not math.isclose(dk[i],k[i]*scale,rel_tol=1e-5,abs_tol=1e-5):raise ValueError('Depth intrinsics do not match image scaling')
    if used!=set(hashes):raise ValueError('Unreferenced sparse frame files')
