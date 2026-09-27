"""Frozen, time-based dense capture ablation; no image-quality driven selection."""
import hashlib
import json

EVALUATION_TIMES = [151.25 + 2.5*i for i in range(12)]


def make_selections(frames, index_hash):
    train = [f for f in frames if f['capture_phase'] == 'train']
    reserved = [f for f in frames if f['capture_phase'] == 'held_out']
    if not train or not reserved:
        raise ValueError('A full pass with the final held-out phase is required')
    low = {}
    for f in train:
        low.setdefault(int(f['elapsed_seconds']*2), f)  # earliest accepted frame in each 0.5s bin
    evaluation = []
    for t in EVALUATION_TIMES:
        frame = min(reserved, key=lambda f: abs(f['elapsed_seconds']-t))
        if abs(frame['elapsed_seconds']-t) > .5:
            raise ValueError(f'Missing held-out coverage near {t:.2f}s; do not move the test window')
        evaluation.append(frame['rgb_file'])
    if len(set(evaluation)) != 12:
        raise ValueError('Repeated held-out evaluation frame')
    common = dict(schema_version=1, index_sha256=index_hash, index_file='DenseFrames.json',
                  held_out=evaluation, excluded_held_out_frames=[f['rgb_file'] for f in reserved],
                  evaluation_targets_seconds=EVALUATION_TIMES,
                  regions=['furniture']*4+['kitchen']*4+['ceiling']*4,
                  policy='All final-phase RGB/depth excluded from fitting, seeding, texturing and training. Twelve nearest predeclared test times, maximum 0.5s deviation.')
    return {name: dict(common, condition=name, train=[f['rgb_file'] for f in selected])
            for name, selected in [('2hz', list(low.values())), ('dense', train)]}


def selected_split(folder, frames, selection):
    index = folder/selection['index_file']
    if selection['index_file'] != 'DenseFrames.json' or hashlib.sha256(index.read_bytes()).hexdigest() != selection['index_sha256']:
        raise ValueError('Capture selection source changed')
    expected = make_selections(frames, selection['index_sha256'])[selection['condition']]
    if selection != expected:
        raise ValueError('Capture selection differs from the frozen time-based protocol')
    by_name = {f['rgb_file']: f for f in frames}
    return ([by_name[name] for name in selection['train']], [by_name[name] for name in selection['held_out']])


def load_selection(path):
    return json.loads(path.read_text()) if path else None
