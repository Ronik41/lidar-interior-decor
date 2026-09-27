"""Exercise corruption and saturated-opacity cases without private room data."""
import tempfile
import unittest
from pathlib import Path

try:
    import numpy as np
    from gaussian_ply import read_gaussian_ply
except ImportError:
    np = None


@unittest.skipIf(np is None, 'Offline PLY preparation requires optional NumPy')
class GaussianPlyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'synthetic.ply'
        self.names = ['x', 'y', 'z', 'f_dc_0', 'f_dc_1', 'f_dc_2', 'opacity',
                      'scale_0', 'scale_1', 'scale_2', 'rot_0', 'rot_1', 'rot_2', 'rot_3']
        self.data = np.zeros(2, dtype=[(n, '<f4') for n in self.names])
        self.data['rot_0'] = 1
        self.header = ('ply\nformat binary_little_endian 1.0\nelement vertex 2\n' +
                       ''.join(f'property float {n}\n' for n in self.names) + 'end_header\n').encode()

    def write(self):
        self.path.write_bytes(self.header + self.data.tobytes())

    def test_saturated_opacity_is_valid_and_source_stays_unchanged(self):
        self.data['opacity'] = [np.inf, -np.inf]
        self.write()
        before = self.path.read_bytes()
        _, report = read_gaussian_ply(self.path)
        self.assertEqual(report['positive_infinite_opacity_logits'], 1)
        self.assertEqual(report['negative_infinite_opacity_logits'], 1)
        self.assertEqual(report['spherical_harmonic_degree'], 0)
        self.assertEqual(self.path.read_bytes(), before)

    def test_nan_and_nonfinite_geometry_are_rejected(self):
        for field, value in [('opacity', np.nan), ('x', np.inf), ('f_dc_0', np.nan)]:
            self.data[field][0] = value
            self.write()
            with self.assertRaisesRegex(ValueError, 'nonfinite'):
                read_gaussian_ply(self.path)
            self.data[field][0] = 0

    def test_truncated_and_extra_bytes_are_rejected(self):
        self.write()
        raw = self.path.read_bytes()
        for changed in [raw[:-1], raw + b'\0']:
            self.path.write_bytes(changed)
            with self.assertRaisesRegex(ValueError, 'byte length'):
                read_gaussian_ply(self.path)

    def test_zero_quaternion_and_missing_color_are_rejected(self):
        self.data['rot_0'][0] = 0
        self.write()
        with self.assertRaisesRegex(ValueError, 'quaternion'):
            read_gaussian_ply(self.path)
        self.data['rot_0'][0] = 1
        self.header = self.header.replace(b'property float f_dc_0', b'property float f_rest_0')
        self.write()
        with self.assertRaisesRegex(ValueError, 'Missing'):
            read_gaussian_ply(self.path)
