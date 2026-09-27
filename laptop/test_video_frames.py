"""Integrity, phase leakage and camera/PTS checks independent of codec smoke test."""
import contextlib
import io
import json
import struct
import tempfile
import unittest
import zipfile
from pathlib import Path
from import_scan import import_scan, validate
from test_import_scan import make_fixture
from video_frames import file_hash, validate_video


class VideoFrameTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.source = self.root/'source'
        self.manifest = make_fixture(self.source)
        # Header-only synthetic payload: native audit separately exercises real HEVC.
        (self.source/'Video.mov').write_bytes(b'\x00\x00\x00\x14ftypqt  '+bytes(16))
        self.index = {'schema_version': 1, 'capture_profile': 'video-rgb-v1', 'format': 'hevc-mov',
                      'video_file': 'Video.mov', 'target_fps': 30, 'depth_target_fps': 2,
                      'duration_limit_seconds': 390, 'saved_count': 3, 'timestamp_origin_seconds': 100,
                      'phase_events': [{'phase': 'perimeter', 'elapsed_seconds': 0},
                                       {'phase': 'details', 'elapsed_seconds': 2},
                                       {'phase': 'held_out', 'elapsed_seconds': 250}], 'frames': []}
        for n, elapsed, ts, phase in [(0, 1, 100, 'perimeter'), (1, 5, 104, 'details'), (2, 250.5, 349.5, 'held_out')]:
            self.index['frames'].append({'frame_index': n, 'slot': int(elapsed*30), 'elapsed_seconds': elapsed,
                'timestamp_seconds': ts, 'video_pts_value': int((ts-100)*1e9), 'video_pts_timescale': 1_000_000_000,
                'capture_phase': 'held_out' if phase == 'held_out' else 'train', 'guidance_phase': phase,
                'tracking_state': 'normal', 'image_width': 1920, 'image_height': 1440,
                'camera_to_world_column_major': [1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1],
                'intrinsics_column_major': [1000,0,0,0,1000,0,960,720,1],
                'depth_available': False, 'confidence_available': False})
        self.save()

    def save(self):
        (self.source/'VideoFrames.json').write_text(json.dumps(self.index))
        self.manifest['video_frames'] = {'schema_version': 1, 'index_file': 'VideoFrames.json',
            'sha256': {name: file_hash(self.source/name) for name in ['Video.mov', 'VideoFrames.json', *[p.name for p in self.source.glob('Video-*')]]}}
        (self.source/'manifest.json').write_text(json.dumps(self.manifest))

    def test_import_and_reopen_preserves_movie_metadata_and_core(self):
        with contextlib.redirect_stdout(io.StringIO()):
            destination = import_scan(self.source, self.root/'scans')
            self.assertEqual(destination, import_scan(self.source, self.root/'scans'))
        self.assertEqual(validate(destination), self.manifest)
        self.assertEqual((destination/'VideoFrames.json').read_bytes(), (self.source/'VideoFrames.json').read_bytes())
        self.assertEqual((destination/'Room.json').read_bytes(), (self.source/'Room.json').read_bytes())

    def test_zip_accepts_video_and_rejects_traversal(self):
        archive = self.root/'input.zip'
        with zipfile.ZipFile(archive, 'w') as z:
            for file in self.source.iterdir():
                z.write(file, 'scan/'+file.name)
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertTrue(import_scan(archive, self.root/'scans').is_dir())
        with zipfile.ZipFile(archive, 'a') as z:
            z.writestr('../escape', b'no')
        with self.assertRaisesRegex(ValueError, 'Unsafe'):
            import_scan(archive, self.root/'other')

    def test_heldout_cannot_be_relabeled_for_training(self):
        self.index['frames'][-1]['capture_phase'] = 'train'; self.save()
        with self.assertRaisesRegex(ValueError, 'held-out'):
            validate_video(self.source, self.manifest)

    def test_return_to_training_phase_rejected(self):
        self.index['phase_events'].append({'phase': 'perimeter', 'elapsed_seconds': 260}); self.save()
        with self.assertRaisesRegex(ValueError, 'irreversibly'):
            validate_video(self.source, self.manifest)

    def test_pts_does_not_match_arkit_clock(self):
        self.index['frames'][1]['video_pts_value'] += 1_000_000; self.save()
        with self.assertRaisesRegex(ValueError, 'PTS'):
            validate_video(self.source, self.manifest)

    def test_duplicate_frame_timestamp_rejected(self):
        self.index['frames'][1]['timestamp_seconds'] = 100; self.save()
        with self.assertRaisesRegex(ValueError, 'PTS'):
            validate_video(self.source, self.manifest)

    def test_corrupt_movie_rejected(self):
        with (self.source/'Video.mov').open('ab') as stream:
            stream.write(b'corruption')
        with self.assertRaisesRegex(ValueError, 'damaged'):
            validate_video(self.source, self.manifest)

    def test_depth_and_confidence_calibration(self):
        frame = self.index['frames'][0]
        frame.update(depth_available=True, confidence_available=True,
            depth_file='Video-00000.depth.f32', confidence_file='Video-00000.confidence.u8',
            depth_width=2, depth_height=2, depth_row_bytes=8, confidence_row_bytes=2,
            depth_intrinsics_column_major=[1000/960,0,0,0,1000/720,0,1,1,1])
        (self.source/frame['depth_file']).write_bytes(struct.pack('<ffff', 1,2,3,4))
        (self.source/frame['confidence_file']).write_bytes(bytes([0,1,2,2]))
        self.save()
        self.assertEqual(validate_video(self.source, self.manifest)['saved_count'], 3)
        frame['depth_intrinsics_column_major'][0] *= 2; self.save()
        with self.assertRaisesRegex(ValueError, 'intrinsics mismatch'):
            validate_video(self.source, self.manifest)

    def test_camera_scale_and_unlisted_depth_rejected(self):
        self.index['frames'][0]['camera_to_world_column_major'][0] = 2; self.save()
        with self.assertRaisesRegex(ValueError, 'orthonormal'):
            validate_video(self.source, self.manifest)
        self.index['frames'][0]['camera_to_world_column_major'][0] = 1
        self.index['frames'][0]['depth_file'] = 'Video-00000.depth.f32'; self.save()
        with self.assertRaisesRegex(ValueError, 'Unavailable'):
            validate_video(self.source, self.manifest)


if __name__ == '__main__':
    unittest.main()
