#!/usr/bin/env python3
"""One bounded rigid photometric registration, using training frames only.

The baseline depth mesh anchors world coordinates. No intrinsic, scale, mesh
deformation, image warp, or held-out pose is optimized. Output is a sidecar.
"""
import argparse
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path


def worker(source, baseline, output):
    import numpy as np
    import open3d as o3d
    from PIL import Image
    from assess_coverage import load_frames, matrix
    from reconstruct_room import split_frames, read_depth, extrinsic, CV_FROM_AR
    from import_scan import validate
    validate(source)
    train, _ = split_frames(load_frames(source))
    frozen = json.loads((baseline / 'split.json').read_text())
    assert [f['rgb_file'] for f in train] == frozen['train']
    mesh = o3d.io.read_triangle_mesh(str(baseline / 'colored-mesh.ply'))
    images, parameters = [], []
    for frame in train:
        width, height = 640, 480
        color = np.asarray(Image.open(source / frame['rgb_file']).convert('RGB').resize((width, height), Image.Resampling.LANCZOS))
        # Nearest upsampling retains measured depth; it adds no new depth detail.
        depth = np.asarray(Image.fromarray(read_depth(source, frame)).resize((width, height), Image.Resampling.NEAREST))
        images.append(o3d.geometry.RGBDImage.create_from_color_and_depth(
            o3d.geometry.Image(color), o3d.geometry.Image(depth),
            depth_scale=1., depth_trunc=4.5, convert_rgb_to_intensity=False))
        k = matrix(frame, 'intrinsics_column_major', 3).copy()
        k[0] *= width / frame['image_width']; k[1] *= height / frame['image_height']
        parameter = o3d.camera.PinholeCameraParameters()
        parameter.intrinsic = o3d.camera.PinholeCameraIntrinsic(width, height, k[0, 0], k[1, 1], k[0, 2], k[1, 2])
        parameter.extrinsic = extrinsic(frame)
        parameters.append(parameter)
    trajectory = o3d.camera.PinholeCameraTrajectory(); trajectory.parameters = parameters
    options = o3d.pipelines.color_map.RigidOptimizerOption(
        maximum_iteration=50, maximum_allowable_depth=4.5,
        depth_threshold_for_visibility_check=.06,
        depth_threshold_for_discontinuity_check=.1,
        half_dilation_kernel_size_for_discontinuity_map=3,
        invisible_vertex_color_knn=0)
    start = time.monotonic()
    with o3d.utility.VerbosityContextManager(o3d.utility.VerbosityLevel.Debug):
        _, refined = o3d.pipelines.color_map.run_rigid_optimizer(mesh, images, trajectory, options)
    poses, proposals, changes = {}, {}, []
    for frame, parameter in zip(train, refined.parameters):
        old = matrix(frame, 'camera_to_world_column_major', 4)
        new = np.linalg.inv(parameter.extrinsic) @ CV_FROM_AR
        translation = float(np.linalg.norm(new[:3, 3] - old[:3, 3]))
        angle = float(np.degrees(np.arccos(np.clip((np.trace(old[:3, :3].T @ new[:3, :3]) - 1) / 2, -1, 1))))
        accepted = bool(np.isfinite(new).all() and translation <= .15 and angle <= 5)
        proposals[frame['rgb_file']] = new.flatten(order='F').tolist()
        poses[frame['rgb_file']] = (new if accepted else old).flatten(order='F').tolist()
        changes.append(dict(frame=frame['rgb_file'],translation_m=translation,rotation_degrees=angle,accepted=accepted))
    report = dict(schema='room-camera-refinement-v1',index_sha256=hashlib.sha256((source / 'Frames.json').read_bytes()).hexdigest(),
        method='Open3D 0.20 rigid color-map camera registration against fixed training-only baseline mesh',
        parameters=dict(iterations=50,image_width=640,visibility_depth_tolerance_m=.06,maximum_change_m=.15,maximum_change_degrees=5),
        policy='Train only. Test cameras, intrinsics, scale and raw package unchanged. Unseen color filling disabled. Fixed baseline geometry anchors world frame.',
        optimization_seconds=time.monotonic()-start,poses=poses,proposed_poses=proposals,changes=changes)
    (output / 'pose-refinement.json').write_text(json.dumps(report, indent=2, allow_nan=False))
    print(json.dumps({k: report[k] for k in ['method','parameters','optimization_seconds']},indent=2), flush=True)
    print('Accepted',sum(x['accepted'] for x in changes),'of',len(changes),flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('source',type=Path); parser.add_argument('baseline',type=Path); parser.add_argument('output',type=Path)
    parser.add_argument('--timeout',type=int,default=600); parser.add_argument('--worker',action='store_true',help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.worker:
        worker(args.source.resolve(),args.baseline.resolve(),args.output.resolve())
    else:
        args.output.mkdir(parents=True,exist_ok=False)
        command = [sys.executable,__file__,str(args.source),str(args.baseline),str(args.output),'--worker']
        start=time.monotonic(); report=dict(command=command,budget_seconds=args.timeout)
        with (args.output/'registration.log').open('w') as log:
            try:
                result=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,timeout=args.timeout)
                report['exit_code']=result.returncode
            except subprocess.TimeoutExpired:
                report['exit_code']='timeout'
        report['seconds']=time.monotonic()-start
        (args.output/'registration-run.json').write_text(json.dumps(report,indent=2))
        print(json.dumps(report,indent=2))
        sys.exit(0 if report['exit_code']==0 else 1)
