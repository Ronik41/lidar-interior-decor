#!/usr/bin/env python3
"""Prepare two fixed training selections from one dense capture with one common seed."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
from capture_selection import make_selections, selected_split
from import_scan import validate


def prepare(source, output):
    import open3d as o3d
    from reconstruct_room import reconstruct, prepare_brush
    manifest = validate(source)
    index = json.loads((source/'DenseFrames.json').read_text()); frames = index['frames']
    if index['duration_limit_seconds'] != 180 or index['elapsed_seconds'] < 179:
        raise ValueError('Need one complete three-minute pass, not the short reliability test')
    selections = make_selections(frames, hashlib.sha256((source/'DenseFrames.json').read_bytes()).hexdigest())
    low_train, tests = selected_split(source,frames,selections['2hz'])
    if not all(f['depth_available'] and f['confidence_available'] for f in low_train+tests):
        raise ValueError('The fixed geometry/evaluation subset is missing depth/confidence; report before changing the protocol')
    if output.exists(): raise ValueError('Ablation output exists; preserve all existing results')
    output.mkdir(parents=True)
    for name, selection in selections.items():
        (output/(name+'-selection.json')).write_text(json.dumps(selection,indent=2))
    low, dense = output/'2hz', output/'dense'
    reconstruct(source,low,selection=output/'2hz-selection.json')
    dense.mkdir()
    train, test = selected_split(source,frames,selections['dense'])
    mesh = o3d.io.read_triangle_mesh(str(low/'colored-mesh.ply'))
    prepare_brush(source,dense,train,test,mesh)
    # Force byte identity, rather than relying on repeated seed construction ordering.
    shutil.copy2(low/'brush-data/seed.ply',dense/'brush-data/seed.ply')
    shutil.copy2(output/'dense-selection.json',dense/'frame-selection.json')
    split = json.loads((low/'split.json').read_text()); split['train']=selections['dense']['train']
    (dense/'split.json').write_text(json.dumps(split,indent=2))
    common_test = low/'brush-data/transforms_test.json'
    if common_test.read_bytes() != (dense/'brush-data/transforms_test.json').read_bytes():
        raise ValueError('Held-out camera manifest differs')
    for f in low_train+tests:
        name=f['rgb_file']
        if (low/'brush-data/images'/name).read_bytes() != (dense/'brush-data/images'/name).read_bytes():
            raise ValueError('Shared image encoding differs')
    report = dict(source_scan_id=manifest['scan_id'], source=str(source.resolve()),
        index_sha256=selections['2hz']['index_sha256'],
        geometry_seed_sha256=hashlib.sha256((low/'brush-data/seed.ply').read_bytes()).hexdigest(),
        held_out_cameras_sha256=hashlib.sha256(common_test.read_bytes()).hexdigest(),
        low_train_count=len(low_train), dense_train_count=len(train), held_out_count=len(test),
        reserved_count=len(selections['dense']['excluded_held_out_frames']),
        settings=dict(steps=6000,max_resolution=960,max_splats=350000,sh_degree=2,refine_every=150,growth_stop_iter=4800),
        geometry='Exactly one unchanged 2 Hz training RGB-D fusion; identical seed bytes copied to both conditions.',
        fixed='Original ARKit poses, intrinsics, scale, held-out pixels and cameras; no pose experiment.',
        limitation='Fixed training steps give the denser condition fewer average updates per photo. One capture and one seed are not a repeated causal study.')
    (output/'protocol.json').write_text(json.dumps(report,indent=2)); print(json.dumps(report,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('output',type=Path);a=p.parse_args();prepare(a.source.resolve(),a.output.resolve())
