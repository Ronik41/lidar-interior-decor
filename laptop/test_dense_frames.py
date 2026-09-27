"""Synthetic integrity/leakage regressions, not evidence of physical capture."""
import contextlib
import copy
import hashlib
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from capture_selection import make_selections, selected_split
from dense_frames import validate_dense
from import_scan import import_scan
from test_import_scan import make_fixture


class DenseFrameTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name); self.source = self.root/'scan'
        self.manifest = make_fixture(self.source)
        self.frame = dict(slot=0, elapsed_seconds=.04, timestamp_seconds=100.04,
                          capture_phase='train', tracking_state='normal', image_width=4, image_height=4,
                          camera_to_world_column_major=[1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1],
                          intrinsics_column_major=[3,0,0,0,3,0,2,2,1], depth_available=False, confidence_available=False)
        self.payload = b'\xff\xd8\xffsynthetic-header-only'
        self.frame.update(rgb_file='Dense-00000.jpg', rgb_sha256=hashlib.sha256(self.payload).hexdigest())
        (self.source/self.frame['rgb_file']).write_bytes(self.payload)
        self.index = dict(schema_version=1, capture_profile='dense-rgb-v1', format='jpeg-image-sequence',
                          target_fps=8, training_seconds=150, duration_limit_seconds=180, saved_count=1, frames=[self.frame])
        self.save()

    def save(self):
        data = json.dumps(self.index).encode(); (self.source/'DenseFrames.json').write_bytes(data)
        self.manifest['dense_frames'] = dict(schema_version=1, index_file='DenseFrames.json',
            sha256={'DenseFrames.json': hashlib.sha256(data).hexdigest(), self.frame['rgb_file']: self.frame['rgb_sha256']})
        (self.source/'manifest.json').write_text(json.dumps(self.manifest))

    def test_rgb_only_sequence_is_optional_and_roundtrips(self):
        package = self.root/'scan.zip'
        with zipfile.ZipFile(package, 'w') as z:
            for path in self.source.iterdir(): z.write(path, 'scan/'+path.name)
        with contextlib.redirect_stdout(io.StringIO()):
            imported = import_scan(package, self.root/'imports')
            self.assertEqual(imported, import_scan(package, self.root/'imports'))
        for path in self.source.iterdir(): self.assertEqual(path.read_bytes(), (imported/path.name).read_bytes())

    def test_corruption_prevents_publication(self):
        (self.source/self.frame['rgb_file']).write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'damaged'): import_scan(self.source, self.root/'imports')
        self.assertFalse((self.root/'imports').exists())

    def test_phase_timestamp_and_pose_tampering_rejected(self):
        for key, value in [('capture_phase', 'held_out'), ('timestamp_seconds', float('nan')),
                           ('camera_to_world_column_major', [2]+self.frame['camera_to_world_column_major'][1:])]:
            with self.subTest(key=key):
                old = self.frame[key]; self.frame[key] = value; self.save()
                with self.assertRaises(ValueError): validate_dense(self.source, self.manifest)
                self.frame[key] = old

    def test_unavailable_depth_cannot_reference_payload(self):
        self.frame['depth_file'] = 'Dense-00000.depth.f32'; self.save()
        with self.assertRaisesRegex(ValueError, 'Unavailable'): validate_dense(self.source, self.manifest)


class DenseSelectionTests(unittest.TestCase):
    def frames(self):
        return [dict(rgb_file=f'Dense-{i:05d}.jpg', elapsed_seconds=i/8+.02,
                     capture_phase='train' if i < 1200 else 'held_out') for i in range(1440)]

    def test_nested_training_and_identical_twelve_tests(self):
        selection = make_selections(self.frames(), 'hash')
        low, dense = selection['2hz'], selection['dense']
        self.assertEqual(len(low['train']), 300); self.assertEqual(len(dense['train']), 1200)
        self.assertLess(set(low['train']), set(dense['train']))
        self.assertEqual(low['held_out'], dense['held_out']); self.assertEqual(len(low['held_out']), 12)
        self.assertFalse(set(dense['train']) & set(dense['excluded_held_out_frames']))
        self.assertEqual(len(dense['excluded_held_out_frames']), 240)

    def test_missing_test_time_stops_instead_of_substituting_training(self):
        frames = [f for f in self.frames() if not 157 < f['elapsed_seconds'] < 160]
        with self.assertRaisesRegex(ValueError, 'Missing held-out'): make_selections(frames, 'hash')

    def test_modified_selection_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp); payload = json.dumps(dict(frames=self.frames())).encode()
            (folder/'DenseFrames.json').write_bytes(payload)
            selections = make_selections(self.frames(), hashlib.sha256(payload).hexdigest())
            selected_split(folder, self.frames(), selections['2hz'])
            modified = copy.deepcopy(selections['2hz']); modified['train'].append(modified['held_out'][0])
            with self.assertRaisesRegex(ValueError, 'frozen'): selected_split(folder, self.frames(), modified)
