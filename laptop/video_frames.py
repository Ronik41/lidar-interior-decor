"""Opt-in video sidecar contract; decoded frame/PTS audit is a separate native step."""
import hashlib
import json
import math
import re
import struct
from dense_frames import camera, finite

MAX_BYTES = 2 * 1024**3


def extension_hashes(manifest):
    extension = manifest.get('video_frames')
    if extension is None:
        return {}
    if (not isinstance(extension, dict)
            or set(extension) != {'schema_version', 'index_file', 'sha256'}
            or type(extension['schema_version']) is not int or extension['schema_version'] != 1
            or extension['index_file'] != 'VideoFrames.json'):
        raise ValueError('Unsupported video extension')
    hashes = extension['sha256']
    if (not isinstance(hashes, dict) or not {'VideoFrames.json', 'Video.mov'} <= set(hashes)
            or len(hashes) > 1602
            or any(name not in {'VideoFrames.json', 'Video.mov'} and not re.fullmatch(
                r'Video-\d{5}\.(depth\.f32|confidence\.u8)', name) for name in hashes)):
        raise ValueError('Invalid video inventory')
    return hashes


def file_hash(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024*1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def validate_video(source, manifest):
    hashes = extension_hashes(manifest)
    if not hashes:
        return None
    total = 0
    for name, digest in hashes.items():
        path = source/name
        limit = MAX_BYTES if name == 'Video.mov' else 64*1024**2
        if (not isinstance(digest, str) or not re.fullmatch('[0-9a-f]{64}', digest)
                or path.is_symlink() or not path.is_file() or path.stat().st_size > limit
                or file_hash(path) != digest):
            raise ValueError('Missing or damaged video payload: ' + name)
        total += path.stat().st_size
    if total > MAX_BYTES:
        raise ValueError('Video byte budget exceeded')
    with (source/'Video.mov').open('rb') as stream:
        header = stream.read(32)
    if len(header) < 16 or header[4:8] != b'ftyp':
        raise ValueError('Video is not an ISO media container; decode audit required')
    index = json.loads((source/'VideoFrames.json').read_text())
    if (not isinstance(index, dict) or type(index.get('schema_version')) is not int
            or index['schema_version'] != 1 or index.get('capture_profile') != 'video-rgb-v1'
            or index.get('format') != 'hevc-mov' or index.get('video_file') != 'Video.mov'
            or index.get('target_fps') != 30 or index.get('depth_target_fps') != 2
            or index.get('duration_limit_seconds') not in (40, 390)):
        raise ValueError('Unsupported video contract')
    frames, events = index.get('frames'), index.get('phase_events')
    if (not isinstance(frames, list) or not 1 <= len(frames) <= 11700
            or type(index.get('saved_count')) is not int or index['saved_count'] != len(frames)):
        raise ValueError('Invalid video frame count')
    phases = ['perimeter', 'details', 'gaps', 'held_out']
    if not isinstance(events, list) or not 1 <= len(events) <= 4:
        raise ValueError('Missing video phase boundaries')
    previous_phase, previous_elapsed = -1, -1
    for event in events:
        phase, elapsed = event.get('phase'), event.get('elapsed_seconds')
        if (phase not in phases or phases.index(phase) <= previous_phase or not finite(elapsed)
                or elapsed <= previous_elapsed or not 0 <= elapsed < index['duration_limit_seconds']):
            raise ValueError('Video phases must advance irreversibly')
        previous_phase, previous_elapsed = phases.index(phase), elapsed
    if events[0]['phase'] != 'perimeter' or events[0]['elapsed_seconds'] != 0:
        raise ValueError('Video phases must begin at perimeter')
    origin = index.get('timestamp_origin_seconds')
    if not finite(origin) or origin != frames[0].get('timestamp_seconds'):
        raise ValueError('Invalid video timestamp origin')
    used = {'VideoFrames.json', 'Video.mov'}
    previous_ts = previous_elapsed = previous_slot = previous_pts = -1
    for n, frame in enumerate(frames):
        ts, elapsed, slot, pts = (frame.get(key) for key in ('timestamp_seconds', 'elapsed_seconds', 'slot', 'video_pts_value'))
        if (frame.get('frame_index') != n or not finite(ts) or ts <= previous_ts
                or not finite(elapsed) or elapsed <= previous_elapsed or not 0 <= elapsed < index['duration_limit_seconds']
                or type(slot) is not int or slot <= previous_slot or slot != math.floor(elapsed*30)
                or type(pts) is not int or pts <= previous_pts or frame.get('video_pts_timescale') != 1_000_000_000
                or abs(pts - round((ts-origin)*1_000_000_000)) > 2):
            raise ValueError('Video timestamps, frame indices and PTS disagree')
        previous_ts, previous_elapsed, previous_slot, previous_pts = ts, elapsed, slot, pts
        expected_phase = next(event['phase'] for event in reversed(events) if event['elapsed_seconds'] <= elapsed)
        if (frame.get('guidance_phase') != expected_phase
                or frame.get('capture_phase') != ('held_out' if expected_phase == 'held_out' else 'train')):
            raise ValueError('Video held-out boundary disagrees with guidance events')
        if frame.get('tracking_state') != 'normal':
            raise ValueError('Video saved with non-normal tracking')
        camera(frame)
        if (frame['image_width'], frame['image_height']) != (frames[0]['image_width'], frames[0]['image_height']):
            raise ValueError('Video dimensions changed')
        if any(type(frame.get(key)) is not bool for key in ('depth_available', 'confidence_available')):
            raise ValueError('Video depth availability must be explicit')
        if frame['confidence_available'] and not frame['depth_available']:
            raise ValueError('Video confidence without depth')
        def payload(kind, suffix):
            name = frame.get(kind+'_file')
            if name != f'Video-{n:05d}'+suffix or name not in hashes or name in used:
                raise ValueError('Invalid video depth payload reference')
            used.add(name)
            return (source/name).read_bytes()
        if frame['depth_available']:
            w, h = frame.get('depth_width'), frame.get('depth_height')
            if type(w) is not int or type(h) is not int or not 0 < w <= 8192 or not 0 < h <= 8192 or frame.get('depth_row_bytes') != w*4:
                raise ValueError('Invalid video depth dimensions')
            depth = payload('depth', '.depth.f32')
            if len(depth) != w*h*4 or not any(math.isfinite(v) and v > 0 for (v,) in struct.iter_unpack('<f', depth)):
                raise ValueError('Invalid video depth measurements')
            k, dk = frame['intrinsics_column_major'], frame.get('depth_intrinsics_column_major')
            if not isinstance(dk, list) or len(dk) != 9 or not all(map(finite, dk)):
                raise ValueError('Invalid video depth calibration')
            for i in range(9):
                scale = w/frame['image_width'] if i % 3 == 0 else h/frame['image_height'] if i % 3 == 1 else 1
                if not math.isclose(dk[i], k[i]*scale, rel_tol=1e-5, abs_tol=1e-5):
                    raise ValueError('Video depth intrinsics mismatch')
            if frame['confidence_available']:
                confidence = payload('confidence', '.confidence.u8')
                if frame.get('confidence_row_bytes') != w or len(confidence) != w*h or any(v > 2 for v in confidence):
                    raise ValueError('Invalid video confidence')
        for kind in ('depth', 'confidence'):
            if not frame[kind+'_available'] and kind+'_file' in frame:
                raise ValueError('Unavailable video depth references a payload')
    if used != set(hashes):
        raise ValueError('Unreferenced video payloads')
    return index
