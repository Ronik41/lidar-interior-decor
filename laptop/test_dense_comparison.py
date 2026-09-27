"""Reject confounded camera/seed/settings comparisons before generating evidence."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
try:
    from compare_dense_ablation import verify
except ImportError:
    verify = None


@unittest.skipIf(verify is None, 'Optional reconstruction runtime required')
class DenseComparisonTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        cameras=b'{"frames": [{"file_path": "images/test.jpg"}]}'
        for name,train in [('2hz',['a.jpg']),('dense',['a.jpg','b.jpg'])]:
            p=self.root/name;(p/'brush-data/images').mkdir(parents=True);(p/'splat').mkdir()
            for image in train+['test.jpg']:(p/'brush-data/images'/image).write_bytes(b'shared pixels')
            (p/'brush-data/seed.ply').write_bytes(b'common seed')
            (p/'brush-data/transforms_test.json').write_bytes(cameras)
            (p/'brush-data/transforms_train.json').write_text(json.dumps(dict(frames=[dict(file_path='images/'+image,transform_matrix='unchanged') for image in train])))
            selection=dict(index_sha256='index',train=train,held_out=['test.jpg'],excluded_held_out_frames=['test.jpg'],evaluation_targets_seconds=[151.25],regions=['furniture'])
            (p/'frame-selection.json').write_text(json.dumps(selection))
            command=['brush','dataset','--total-steps','6000','--start-iter','0','--max-resolution','960',
                     '--max-splats','350000','--sh-degree','2','--refine-every','150','--growth-stop-iter','4800','--eval-every','6000']
            (p/'splat/run.json').write_text(json.dumps(dict(exit_code=0,command=command)))
        (self.root/'protocol.json').write_text(json.dumps(dict(geometry_seed_sha256=hashlib.sha256(b'common seed').hexdigest(),held_out_cameras_sha256=hashlib.sha256(cameras).hexdigest())))

    def test_identical_controls_accept(self): verify(self.root)

    def test_changed_seed_or_photo_rejected(self):
        for relative in ('seed.ply','images/a.jpg','images/test.jpg','transforms_test.json'):
            path=self.root/'dense/brush-data'/relative;old=path.read_bytes();path.write_bytes(b'changed')
            with self.subTest(relative=relative),self.assertRaises(ValueError):verify(self.root)
            path.write_bytes(old)

    def test_changed_training_setting_rejected(self):
        path=self.root/'dense/splat/run.json';run=json.loads(path.read_text());i=run['command'].index('--max-splats')
        run['command'][i+1]='500000';path.write_text(json.dumps(run))
        with self.assertRaisesRegex(ValueError,'configuration'):verify(self.root)

    def test_changed_shared_training_camera_rejected(self):
        path=self.root/'dense/brush-data/transforms_train.json';data=json.loads(path.read_text());data['frames'][0]['transform_matrix']='adjusted'
        path.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError,'Shared training camera'):verify(self.root)
