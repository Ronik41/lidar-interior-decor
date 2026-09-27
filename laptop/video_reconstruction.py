#!/usr/bin/env python3
"""Prepare one unchanged-settings reconstruction from locally decoded video.

The full recording remains immutable. Selection is temporal, never selected for
image quality. No implicit train/test split is invented when the capture has none.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import time


def selection(index):
    frames = index['frames']
    train = [f for f in frames if f['capture_phase'] == 'train']
    reserved = [f for f in frames if f['capture_phase'] == 'held_out']
    if not train:
        raise ValueError('No training video frames')
    bins = {}
    for f in train:
        key = int(f['elapsed_seconds']*8)
        previous = bins.get(key)
        # At most 2 Hz native depth is included as an exact nested geometry subset.
        if previous is None or (f['depth_available'] and f['confidence_available']
                                and not (previous['depth_available'] and previous['confidence_available'])):
            bins[key] = f
    rgbd = [f for f in train if f['depth_available'] and f['confidence_available']]
    if not rgbd:
        raise ValueError('No depth/confidence frames for unchanged geometry seed')
    dense_ids = sorted({f['frame_index'] for f in bins.values()} |
                       {f['frame_index'] for f in rgbd} |
                       {train[0]['frame_index'], train[-1]['frame_index']})
    candidates = reserved or [f for f in train if f['frame_index'] in dense_ids]
    # Freeze twelve uniformly spaced views before inspecting reconstruction results.
    first, last = candidates[0]['elapsed_seconds'], candidates[-1]['elapsed_seconds']
    targets = [first+(last-first)*(n+.5)/12 for n in range(12)]
    diagnostic = [min(candidates, key=lambda f: abs(f['elapsed_seconds']-t))['frame_index'] for t in targets]
    if len(set(diagnostic)) != 12:
        raise ValueError('Capture too short for twelve distinct diagnostic views')
    return dict(schema_version=1, dense_ids=dense_ids, geometry_ids=[f['frame_index'] for f in rgbd],
                diagnostic_ids=diagnostic, excluded_held_out_ids=[f['frame_index'] for f in reserved],
                evaluation_kind='held_out' if reserved else 'training_reprojection',
                target_rgb_hz=8, diagnostic_targets_seconds=targets,
                policy='Earliest RGB per 0.125s bin, preferring exact depth frames; all training depth pairs and first/last training frames retained. No image-quality selection. Capture phase boundaries preserved.',
                metric_policy='Reserved phase excluded from reconstruction.' if reserved else
                'No held-out capture exists. Diagnostic cameras are training cameras. Scores describe fitted-view agreement only, not novel-view quality.')


def prepare(source, output):
    from import_scan import validate, file_hash
    from reconstruct_room import fuse_frames, prepare_brush
    import open3d as o3d
    manifest = validate(source)
    index_path = source/'VideoFrames.json'
    index = json.loads(index_path.read_text())
    plan = selection(index)
    if output.exists():
        raise ValueError('Output exists; preserve previous capture and reconstructions')
    output.mkdir(parents=True)
    plan.update(source_scan_id=manifest['scan_id'], video_frames_sha256=file_hash(index_path),
                video_sha256=file_hash(source/'Video.mov'))
    (output/'video-selection.json').write_text(json.dumps(plan, indent=2))
    chosen = sorted(set(plan['dense_ids']+plan['diagnostic_ids']))
    (output/'decode-selection.json').write_text(json.dumps(chosen))
    decoded = output/'decoded'
    subprocess.run(['python3', str(Path(__file__).with_name('audit_video.py')), str(source),
                    '--report', str(output/'decode-audit.json'), '--indices', str(output/'decode-selection.json'),
                    '--output', str(decoded)], check=True)
    records = []
    for n in chosen:
        f = dict(index['frames'][n], rgb_file=f'Video-{n:05d}.png')
        for key in ('depth_file','confidence_file'):
            if key in f:
                shutil.copy2(source/f[key], decoded/f[key])
        records.append(f)
    derived = dict(schema_version=1, source_scan_id=manifest['scan_id'],
                   video_frames_sha256=plan['video_frames_sha256'], video_sha256=plan['video_sha256'],
                   extraction='AVFoundation sequential HEVC decode; one verified PTS per metadata record; sensor-native PNG without pose/calibration changes',
                   frames=records,
                   sha256={p.name:file_hash(p) for p in sorted(decoded.iterdir()) if p.is_file()})
    (decoded/'DerivedFrames.json').write_text(json.dumps(derived, indent=2))
    by_id = {f['frame_index']: f for f in records}
    geometry = [by_id[n] for n in plan['geometry_ids']]
    dense = [by_id[n] for n in plan['dense_ids']]
    diagnostic = [by_id[n] for n in plan['diagnostic_ids']]
    mesh_out = output/'mesh-result'; mesh_out.mkdir()
    split = dict(source_scan_id=manifest['scan_id'], index_sha256=plan['video_frames_sha256'],
                 train=[f['rgb_file'] for f in geometry],
                 held_out=[f['rgb_file'] for f in diagnostic] if plan['evaluation_kind']=='held_out' else [],
                 diagnostic_views=[f['rgb_file'] for f in diagnostic],
                 excluded_held_out_frames=[f'Video-{n:05d}.png' for n in plan['excluded_held_out_ids']],
                 evaluation_kind=plan['evaluation_kind'], policy=plan['metric_policy'])
    (mesh_out/'split.json').write_text(json.dumps(split, indent=2))
    started = time.monotonic()
    # Same fusion, filtering, texture assignment and seed defaults as prior runs.
    fuse_frames(decoded, mesh_out, geometry, diagnostic, .025, manifest['scan_id'], started)
    report=json.loads((mesh_out/'mesh-report.json').read_text())
    report['evaluation_kind']=plan['evaluation_kind'];report['diagnostic_frames']=report.pop('test_frames')
    (mesh_out/'mesh-report.json').write_text(json.dumps(report,indent=2))
    dense_out = output/'dense'; dense_out.mkdir()
    mesh = o3d.io.read_triangle_mesh(str(mesh_out/'colored-mesh.ply'))
    prepare_brush(decoded, dense_out, dense, diagnostic, mesh)
    shutil.copy2(mesh_out/'brush-data/seed.ply', dense_out/'brush-data/seed.ply')
    split['train'] = [f['rgb_file'] for f in dense]
    (dense_out/'split.json').write_text(json.dumps(split, indent=2))
    protocol = dict(plan, geometry_seed_sha256=file_hash(dense_out/'brush-data/seed.ply'),
                    diagnostic_cameras_sha256=file_hash(dense_out/'brush-data/transforms_test.json'),
                    settings=dict(steps=6000,max_resolution=960,max_splats=350000,sh_degree=2,refine_every=150,growth_stop_iter=4800),
                    geometry_count=len(geometry),rgb_count=len(dense),diagnostic_count=len(diagnostic),
                    preparation_seconds=time.monotonic()-started)
    (output/'protocol.json').write_text(json.dumps(protocol, indent=2))
    print(f"Prepared {len(dense)} RGB views, {len(geometry)} depth views; diagnostics: {plan['evaluation_kind']}")


def verify_prepared(source, output):
    """Bind extracted pixels and every unchanged camera back to the original movie."""
    from import_scan import validate, file_hash
    manifest=validate(source);index=json.loads((source/'VideoFrames.json').read_text())
    expected=selection(index)
    expected.update(source_scan_id=manifest['scan_id'],video_frames_sha256=file_hash(source/'VideoFrames.json'),
                    video_sha256=file_hash(source/'Video.mov'))
    plan=json.loads((output/'video-selection.json').read_text())
    if plan != expected:raise ValueError('Video selection differs from the frozen temporal protocol')
    decoded=output/'decoded';derived=json.loads((decoded/'DerivedFrames.json').read_text())
    chosen=sorted(set(plan['dense_ids']+plan['diagnostic_ids']))
    exact=[dict(index['frames'][n],rgb_file=f'Video-{n:05d}.png') for n in chosen]
    if derived['frames'] != exact:raise ValueError('Derived camera metadata changed from raw video')
    names={f['rgb_file'] for f in exact}
    names.update(f[key] for f in exact for key in ('depth_file','confidence_file') if key in f)
    if names != set(derived['sha256']):raise ValueError('Derived payload inventory changed')
    for name,expected_hash in derived['sha256'].items():
        if file_hash(decoded/name) != expected_hash:raise ValueError('Decoded payload changed: '+name)
    audit=json.loads((output/'decode-audit.json').read_text())
    if not audit['passed'] or audit['decoded_frame_count'] != len(index['frames']) or audit['maximum_pts_error_seconds'] > .000001:
        raise ValueError('Video decode audit did not pass')
    return plan,derived


def evaluate(source, output, splat_renders=None):
    from evaluate_reconstruction import render_mesh_views, compare
    plan,derived=verify_prepared(source,output)
    decoded=output/'decoded'
    by_id={f['frame_index']:f for f in derived['frames']}
    out=output/'mesh-result'
    if splat_renders:
        compare(decoded,out,splat_renders)
    else:
        render_mesh_views(decoded,out,[by_id[n] for n in plan['geometry_ids']],
                          [by_id[n] for n in plan['diagnostic_ids']])


def publish(source, output):
    from import_scan import validate, file_hash
    manifest=validate(source);plan,_=verify_prepared(source,output)
    if file_hash(source/'VideoFrames.json') != plan['video_frames_sha256'] or manifest['scan_id'] != plan['source_scan_id']:
        raise ValueError('Source changed')
    frames=json.loads((source/'VideoFrames.json').read_text())['frames']
    out=output/'mesh-result'
    splat=output/'dense/splat/export_6000.ply'
    if (out/'reconstruction.json').exists():raise ValueError('Registration already exists')
    shutil.copy2(splat,out/'room-splat.ply')
    assets={p.relative_to(out).as_posix():file_hash(p) for p in (out/'mesh').rglob('*') if p.is_file()}
    assets['room-splat.ply']=file_hash(out/'room-splat.ply')
    views=[]
    for i,n in enumerate(plan['diagnostic_ids']):
        f=frames[n]
        views.append(dict(label=f"{'Held-out' if plan['evaluation_kind']=='held_out' else 'Training'} view {i+1} · {f['elapsed_seconds']:.0f}s",
                          rgb_file=f'Video-{n:05d}.png',**{k:f[k] for k in ['camera_to_world_column_major','intrinsics_column_major','image_width','image_height']}))
    data=dict(schema_version=1,source_scan_id=manifest['scan_id'],frames_index_file='VideoFrames.json',
              frames_sha256=plan['video_frames_sha256'],coordinate_system='Original ARKit meters; same session as RoomPlan; no pose refinement or alignment',
              preferred='splat',mesh_url='/reconstruction/mesh/room.gltf',splat_url='/reconstruction/room-splat.ply',viewpoints=views,assets=assets,
              provenance=f"Local video reconstruction · {len(plan['dense_ids'])} RGB views, {len(plan['geometry_ids'])} depth views · {plan['metric_policy']} RoomPlan is a separate editable layer. Missing surfaces remain unknown.")
    (out/'reconstruction.json').write_text(json.dumps(data,indent=2))
    print('Registered video reconstruction:',out)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['prepare','evaluate','publish']);p.add_argument('source',type=Path);p.add_argument('output',type=Path);p.add_argument('--splat-renders',type=Path);a=p.parse_args()
    if a.action=='prepare':prepare(a.source.resolve(),a.output.resolve())
    elif a.action=='evaluate':evaluate(a.source.resolve(),a.output.resolve(),a.splat_renders)
    else:publish(a.source.resolve(),a.output.resolve())
