"""Protect scan association and the private asset boundary."""
import hashlib,json,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from reconstruction_assets import ReconstructionAssets

class AssetTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);self.scan=self.root/'scan';self.scan.mkdir();(self.scan/'Frames.json').write_text('{}')
        self.store=SimpleNamespace(scan=self.scan,source={'scan_id':'same-session'})
        (self.root/'room.gltf').write_text('{}')
        self.metadata={'source_scan_id':'same-session','frames_sha256':hashlib.sha256(b'{}').hexdigest(),'assets':{'room.gltf':hashlib.sha256(b'{}').hexdigest()},'mesh_url':'/reconstruction/room.gltf'}
    def load(self):
        (self.root/'reconstruction.json').write_text(json.dumps(self.metadata));return ReconstructionAssets(self.root,self.store)
    def test_session_and_frame_provenance_are_required(self):
        self.load();self.metadata['source_scan_id']='different-session'
        with self.assertRaisesRegex(ValueError,'different RoomPlan'):self.load()
        self.metadata['source_scan_id']='same-session';(self.scan/'Frames.json').write_text('{"changed":true}')
        with self.assertRaisesRegex(ValueError,'provenance'):self.load()
    def test_private_file_inventory_rejects_escape_and_tampering(self):
        self.metadata['assets']={'../outside':hashlib.sha256(b'{}').hexdigest()}
        with self.assertRaisesRegex(ValueError,'Unsafe'):self.load()
        self.metadata['assets']={'room.gltf':hashlib.sha256(b'{}').hexdigest()};(self.root/'room.gltf').write_text('changed')
        with self.assertRaisesRegex(ValueError,'checksum'):self.load()
    def test_unlisted_model_cannot_be_served(self):
        self.metadata['mesh_url']='/reconstruction/private.jpg'
        with self.assertRaisesRegex(ValueError,'Unlisted'):self.load()
    def test_dense_index_is_explicit_and_hash_bound(self):
        self.metadata['frames_index_file']='DenseFrames.json'
        with self.assertRaisesRegex(ValueError,'provenance'):self.load()
        (self.scan/'DenseFrames.json').write_text('{}');self.load()
        (self.scan/'DenseFrames.json').write_text('{"changed":true}')
        with self.assertRaisesRegex(ValueError,'provenance'):self.load()
    def test_frame_index_cannot_escape_scan(self):
        self.metadata['frames_index_file']='../Frames.json'
        with self.assertRaisesRegex(ValueError,'Unsupported'):self.load()
