"""Guard the scientific controls and preservation boundaries of the single trial."""
import json
from pathlib import Path
import tempfile
import unittest
import numpy as np
from PIL import Image
from resolution_experiment import crop, digest, verify, verify_command


class ResolutionControlsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve(); self.base = self.root/'base'; self.out = self.root/'candidate'
        self.raw = self.root/'raw'; self.raw.mkdir()
        for path in (self.base/'dense/brush-data', self.base/'dense/splat', self.out/'brush-data'):
            path.mkdir(parents=True)
        for name in ('transforms_train.json', 'transforms_test.json', 'seed.ply'):
            for p in (self.base/'dense/brush-data', self.out/'brush-data'):
                (p/name).write_bytes(b'original-'+name.encode())
        (self.raw/'Video.mov').write_bytes(b'private-video')
        self.cmd = ['brush',str(self.base/'dense/brush-data'),'--total-steps','6000','--max-resolution','960','--max-splats','350000','--export-path',str(self.base/'dense/splat')]
        (self.base/'dense/splat/run.json').write_text(json.dumps(dict(command=self.cmd)))
        protocol = dict(base=str(self.base), source=str(self.raw), candidate_files={p.name:digest(p) for p in (self.out/'brush-data').iterdir()},
                        baseline_files={'dense/brush-data/seed.ply':digest(self.base/'dense/brush-data/seed.ply')},
                        raw_files={'Video.mov':digest(self.raw/'Video.mov')})
        (self.out/'protocol.json').write_text(json.dumps(protocol))

    def test_frozen_seed_and_cameras_are_enforced(self):
        verify(self.out, full=True)
        for name in ('transforms_train.json','transforms_test.json','seed.ply'):
            p = self.out/'brush-data'/name; old=p.read_bytes(); p.write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError,'Frozen camera/seed changed'): verify(self.out)
            p.write_bytes(old)

    def test_raw_payload_change_is_detected(self):
        (self.raw/'Video.mov').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'Preserved file changed'): verify(self.out, full=True)

    def test_only_resolution_and_output_paths_may_change(self):
        cmd=list(self.cmd);cmd[1]=str(self.out/'brush-data');cmd[-1]=str(self.out/'splat');cmd[cmd.index('--max-resolution')+1]='1440'
        verify_command(self.base,self.out,cmd)
        for key,value in [('--total-steps','6001'),('--max-splats','500000'),('--max-resolution','1920')]:
            bad=list(cmd);bad[bad.index(key)+1]=value
            with self.assertRaisesRegex(ValueError,'Training arguments differ'): verify_command(self.base,self.out,bad)

    def test_crops_preserve_same_field_of_view_at_both_resolutions(self):
        yy,xx=np.mgrid[:720,:960]
        im=Image.fromarray(np.stack((xx%256,yy%256,(xx+yy)%256),axis=2).astype('uint8'))
        native=im.resize((1920,1440),Image.Resampling.NEAREST)
        box=[90,600,510,960]
        low=crop(im,box);high=crop(native,box).resize(low.size,Image.Resampling.NEAREST)
        np.testing.assert_array_equal(np.asarray(low),np.asarray(high))


if __name__=='__main__': unittest.main()
