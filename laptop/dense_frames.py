"""Optional dense image-sequence contract; independent of the unchanged sparse mode."""
import hashlib
import json
import math
import re
import struct

MAX_BYTES = 1536 * 1024 * 1024


def extension_hashes(manifest):
    if not isinstance(manifest, dict):
        raise ValueError('Expected scan manifest JSON object')
    extension = manifest.get('dense_frames')
    if extension is None:
        return {}
    if (not isinstance(extension, dict)
            or set(extension) != {'schema_version', 'index_file', 'sha256'}
            or type(extension['schema_version']) is not int or extension['schema_version'] != 1
            or extension['index_file'] != 'DenseFrames.json'):
        raise ValueError('Unsupported dense frame extension')
    hashes = extension['sha256']
    if (not isinstance(hashes, dict) or not 1 <= len(hashes) <= 4321
            or 'DenseFrames.json' not in hashes
            or any(name != 'DenseFrames.json' and not re.fullmatch(
                r'Dense-\d{5}\.(jpg|depth\.f32|confidence\.u8)', name) for name in hashes)):
        raise ValueError('Invalid dense frame inventory')
    return hashes


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def camera(frame):
    for key, n in [('camera_to_world_column_major', 16), ('intrinsics_column_major', 9)]:
        values = frame.get(key)
        if not isinstance(values, list) or len(values) != n or not all(map(finite, values)):
            raise ValueError('Invalid dense camera metadata: ' + key)
    pose, k = frame['camera_to_world_column_major'], frame['intrinsics_column_major']
    if any(abs(pose[i] - expected) > 1e-5 for i, expected in [(3, 0), (7, 0), (11, 0), (15, 1)]):
        raise ValueError('Dense camera pose is not affine')
    columns = [pose[i:i+3] for i in (0, 4, 8)]
    for i in range(3):
        for j in range(3):
            if abs(sum(a*b for a, b in zip(columns[i], columns[j])) - int(i == j)) > 1e-3:
                raise ValueError('Dense camera rotation is not orthonormal')
    a, b, c = columns
    det = a[0]*(b[1]*c[2]-b[2]*c[1])-b[0]*(a[1]*c[2]-a[2]*c[1])+c[0]*(a[1]*b[2]-a[2]*b[1])
    if abs(det-1) > 1e-3 or k[0] <= 0 or k[4] <= 0 or abs(k[8]-1) > 1e-5:
        raise ValueError('Invalid dense calibration or handedness')
    for key in ('image_width', 'image_height'):
        if type(frame.get(key)) is not int or not 0 < frame[key] <= 8192:
            raise ValueError('Invalid dense image dimensions')


def validate_dense(source, manifest):
    hashes = extension_hashes(manifest)
    if not hashes:
        return None
    total = 0
    for name, digest in hashes.items():
        path = source/name
        if (not isinstance(digest, str) or not re.fullmatch('[0-9a-f]{64}', digest)
                or path.is_symlink() or not path.is_file() or path.stat().st_size > 64*1024*1024
                or hashlib.sha256(path.read_bytes()).hexdigest() != digest):
            raise ValueError('Missing or damaged dense frame: ' + name)
        if name != 'DenseFrames.json':
            total += path.stat().st_size
    if total > MAX_BYTES:
        raise ValueError('Dense frame byte budget exceeded')
    index = json.loads((source/'DenseFrames.json').read_text())
    if (not isinstance(index, dict) or type(index.get('schema_version')) is not int
            or index['schema_version'] != 1 or index.get('capture_profile') != 'dense-rgb-v1'
            or index.get('format') != 'jpeg-image-sequence' or index.get('target_fps') != 8
            or index.get('training_seconds') != 150 or index.get('duration_limit_seconds') not in (40, 180)):
        raise ValueError('Unsupported dense capture contract')
    frames = index.get('frames')
    if (not isinstance(frames, list) or len(frames) > 1440
            or type(index.get('saved_count')) is not int or index['saved_count'] != len(frames)):
        raise ValueError('Invalid dense frame count')
    used = {'DenseFrames.json'}
    previous = previous_elapsed = -1
    previous_slot = -1
    for frame in frames:
        if not isinstance(frame, dict):
            raise ValueError('Invalid dense frame record')
        timestamp, elapsed, slot = (frame.get(key) for key in ('timestamp_seconds', 'elapsed_seconds', 'slot'))
        if (not finite(timestamp) or timestamp <= previous or not finite(elapsed)
                or elapsed <= previous_elapsed or not 0 <= elapsed < index['duration_limit_seconds']
                or type(slot) is not int or slot <= previous_slot or slot != math.floor(elapsed*8)):
            raise ValueError('Dense timestamps, slots and elapsed time must increase consistently')
        previous, previous_elapsed, previous_slot = timestamp, elapsed, slot
        if frame.get('capture_phase') != ('held_out' if elapsed >= 150 else 'train'):
            raise ValueError('Dense held-out phase disagrees with monotonic capture time')
        if frame.get('tracking_state') != 'normal':
            raise ValueError('Dense saved frame has non-normal tracking')
        camera(frame)
        def payload(kind, suffix):
            name = frame.get(kind+'_file')
            if (name != f'Dense-{slot:05d}'+suffix or name not in hashes or name in used
                    or frame.get(kind+'_sha256') != hashes[name]):
                raise ValueError('Invalid dense payload reference: ' + kind)
            used.add(name)
            return (source/name).read_bytes()
        rgb = payload('rgb', '.jpg')
        if not rgb.startswith(b'\xff\xd8\xff'):
            raise ValueError('Dense RGB is not JPEG')
        if any(type(frame.get(key)) is not bool for key in ('depth_available', 'confidence_available')):
            raise ValueError('Dense depth availability must be explicit')
        if frame['confidence_available'] and not frame['depth_available']:
            raise ValueError('Confidence without depth')
        if frame['depth_available']:
            w, h = frame.get('depth_width'), frame.get('depth_height')
            if (type(w) is not int or type(h) is not int or not 0 < w <= 8192 or not 0 < h <= 8192
                    or frame.get('depth_row_bytes') != w*4):
                raise ValueError('Invalid packed dense depth dimensions')
            depth = payload('depth', '.depth.f32')
            if len(depth) != w*h*4 or not any(math.isfinite(v) and v > 0 for (v,) in struct.iter_unpack('<f', depth)):
                raise ValueError('Dense depth has invalid size or no measurements')
            k, dk = frame['intrinsics_column_major'], frame.get('depth_intrinsics_column_major')
            if not isinstance(dk, list) or len(dk) != 9 or not all(map(finite, dk)):
                raise ValueError('Invalid dense depth calibration')
            for i in range(9):
                scale = w/frame['image_width'] if i % 3 == 0 else h/frame['image_height'] if i % 3 == 1 else 1
                if not math.isclose(dk[i], k[i]*scale, rel_tol=1e-5, abs_tol=1e-5):
                    raise ValueError('Dense depth intrinsics scaling mismatch')
            if frame['confidence_available']:
                confidence = payload('confidence', '.confidence.u8')
                if frame.get('confidence_row_bytes') != w or len(confidence) != w*h or any(v > 2 for v in confidence):
                    raise ValueError('Invalid dense depth confidence')
        for kind in ('depth', 'confidence'):
            if not frame[kind+'_available'] and any(kind+suffix in frame for suffix in ('_file', '_sha256')):
                raise ValueError('Unavailable dense payload has a file reference')
    if used != set(hashes):
        raise ValueError('Unreferenced dense payloads')
    return index
