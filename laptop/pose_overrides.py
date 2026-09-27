"""Validated, train-only derived poses; raw camera records never change."""
import hashlib
import json
from pathlib import Path
import numpy as np


def apply_poses(folder, frames, path):
    if path is None:
        return frames
    data = json.loads(Path(path).read_text())
    digest = hashlib.sha256((Path(folder) / 'Frames.json').read_bytes()).hexdigest()
    if data.get('schema') != 'room-camera-refinement-v1' or data.get('index_sha256') != digest:
        raise ValueError('Pose refinement does not match this immutable frame index')
    poses = data['poses']
    allowed = {f['rgb_file'] for f in frames if f.get('capture_phase') == 'train'}
    if set(poses) != allowed:
        raise ValueError('Derived poses must cover exactly the training frames; held-out cameras are immutable')
    result = []
    for frame in frames:
        frame = dict(frame)
        if frame['rgb_file'] in poses:
            values = poses[frame['rgb_file']]
            if len(values) != 16:
                raise ValueError('Pose must contain 16 column-major values')
            matrix = np.asarray(values, dtype=float).reshape(4, 4, order='F')
            rotation = matrix[:3, :3]
            if (not np.isfinite(matrix).all() or not np.allclose(matrix[3], [0, 0, 0, 1])
                    or not np.allclose(rotation.T @ rotation, np.eye(3), atol=1e-5)
                    or not np.isclose(np.linalg.det(rotation), 1, atol=1e-5)):
                raise ValueError('Pose must be a finite, rigid meter-space transform')
            frame['camera_to_world_column_major'] = values
        result.append(frame)
    return result
