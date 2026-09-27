"""Guard external registration, privacy boundaries and optional operation."""
import copy,hashlib,json,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from benchmark_assets import BenchmarkAssets,rigid_matrix


class BenchmarkTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        (self.root/'reconstruction.json').write_text('{}');(self.root/'external.ply').write_bytes(b'private-model')
        self.digest=hashlib.sha256(b'private-model').hexdigest();self.identity=[1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1]
        self.meta={'schema_version':1,'kind':'external-gaussian-benchmark','reference_scan_id':'room','reference_frames_sha256':'frames',
                   'reference_reconstruction_sha256':hashlib.sha256(b'{}').hexdigest(),'source_to_reference_column_major':self.identity,
                   'model_file':'external.ply','model_sha256':self.digest,'validation':{'sha256':self.digest},
                   'label':'External benchmark','provenance':'Unknown capture','registration_summary':'Rigid only'}
        self.store=SimpleNamespace(source={'scan_id':'room'});self.recon=SimpleNamespace(root=self.root,metadata={'frames_sha256':'frames'})
    def load(self):
        path=self.root/'benchmark.json';path.write_text(json.dumps(self.meta));return BenchmarkAssets(path,self.store,self.recon)
    def test_valid_rigid_registration_and_explicit_url(self):
        self.meta['source_to_reference_column_major'][12:15]=[1,-2,3]
        self.assertEqual(self.load().payload()['url'],'/benchmark/model.ply')
    def test_no_scale_reflection_shear_or_nonfinite_transform(self):
        for index,value in [(0,2),(0,-1),(1,.1),(5,float('nan')),(15,2)]:
            matrix=self.identity.copy();matrix[index]=value
            with self.assertRaises(ValueError):rigid_matrix(matrix)
    def test_wrong_reference_and_changed_cameras_are_rejected(self):
        self.meta['reference_scan_id']='other'
        with self.assertRaisesRegex(ValueError,'different room'):self.load()
        self.meta['reference_scan_id']='room';self.meta['reference_frames_sha256']='changed'
        with self.assertRaisesRegex(ValueError,'cameras changed'):self.load()
    def test_reference_viewpoint_changes_require_reregistration(self):
        (self.root/'reconstruction.json').write_text('{"changed":true}')
        with self.assertRaisesRegex(ValueError,'reference reconstruction changed'):self.load()
    def test_asset_escape_tamper_and_symlink_rejected(self):
        original=copy.deepcopy(self.meta)
        for name in ['../external.ply','/tmp/private.ply']:
            self.meta['model_file']=name
            with self.assertRaisesRegex(ValueError,'Unsafe'):self.load()
        self.meta=original;(self.root/'alias.ply').symlink_to(self.root/'external.ply');self.meta['model_file']='alias.ply'
        with self.assertRaisesRegex(ValueError,'unsafe'):self.load()
        self.meta['model_file']='external.ply';(self.root/'external.ply').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'checksum'):self.load()
    def test_validation_must_match_the_asset(self):
        self.meta['validation']['sha256']='different'
        with self.assertRaisesRegex(ValueError,'validation'):self.load()
    def test_malformed_manifest_is_reported(self):
        original=copy.deepcopy(self.meta)
        for meta in [[],dict(original,model_file=None),dict(original,provenance=''),dict(original,validation=None)]:
            self.meta=meta
            with self.assertRaises(ValueError):self.load()
