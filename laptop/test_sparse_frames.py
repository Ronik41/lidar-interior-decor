"""Synthetic extension/transport tests. These do not substitute for a phone scan."""
import contextlib
import copy
import hashlib
import io
import json
import struct
import tempfile
import unittest
import zipfile
from pathlib import Path
from import_scan import import_scan, validate
from sparse_frames import extension_hashes
from test_import_scan import make_fixture


class SparseFrameTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);self.scan=self.root/'scan'
        self.manifest=make_fixture(self.scan,rgb=True)
        rgb=b'\xff\xd8\xffsynthetic-not-an-image';depth=struct.pack('<4f',1.2,2.3,float('nan'),.9);confidence=bytes([2,1,0,2])
        self.frame={'timestamp_seconds':1.5,'image_width':4,'image_height':4,'depth_width':2,'depth_height':2,
                    'camera_to_world_column_major':[1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1],
                    'intrinsics_column_major':[3,0,0,0,3,0,2,2,1], 'depth_intrinsics_column_major':[1.5,0,0,0,1.5,0,1,1,1],
                    'depth_row_bytes':8,'confidence_row_bytes':2}
        self.hashes={}
        for prefix,suffix,data in [('rgb','.jpg',rgb),('depth','.depth.f32',depth),('confidence','.confidence.u8',confidence)]:
            name='Frame-0001'+suffix;(self.scan/name).write_bytes(data);digest=hashlib.sha256(data).hexdigest()
            self.frame[prefix+'_file']=name;self.frame[prefix+'_sha256']=digest;self.hashes[name]=digest
        self.index={'schema_version':1,'saved_count':1,'frames':[self.frame]};self.write_index()

    def write_index(self):
        data=json.dumps(self.index).encode();(self.scan/'Frames.json').write_bytes(data);self.hashes['Frames.json']=hashlib.sha256(data).hexdigest()
        self.manifest['sparse_frames']={'schema_version':1,'index_file':'Frames.json','sha256':self.hashes}
        (self.scan/'manifest.json').write_text(json.dumps(self.manifest))

    def test_extended_zip_and_repeat_import_preserve_all_sidecars(self):
        self.assertEqual(set(self.manifest['sha256']),{'Room.json','Room.usdz','Reference.jpg','Reference.json'})
        self.assertEqual(validate(self.scan),self.manifest)
        archive=self.root/'scan.zip'
        with zipfile.ZipFile(archive,'w') as z:
            for p in self.scan.iterdir():z.write(p,'RoomScan/'+p.name)
        with contextlib.redirect_stdout(io.StringIO()):
            imported=import_scan(archive,self.root/'out');self.assertEqual(import_scan(archive,self.root/'out'),imported)
        for p in self.scan.iterdir():self.assertEqual(p.read_bytes(),(imported/p.name).read_bytes())

    def test_zero_frames_is_explicit_and_legacy_packages_still_validate(self):
        self.index.update(saved_count=0,frames=[]);self.hashes={};self.write_index();validate(self.scan)
        self.manifest.pop('sparse_frames');(self.scan/'manifest.json').write_text(json.dumps(self.manifest));validate(self.scan)

    def test_corruption_does_not_publish(self):
        (self.scan/self.frame['depth_file']).write_bytes(b'bad')
        with self.assertRaisesRegex(ValueError,'damaged'):import_scan(self.scan,self.root/'out')
        self.assertFalse((self.root/'out').exists())

    def test_unsafe_extension_and_unreferenced_files_rejected(self):
        self.hashes['../extra']='0'*64;self.write_index()
        with self.assertRaisesRegex(ValueError,'inventory'):validate(self.scan)
        self.hashes.pop('../extra');self.index.update(saved_count=0,frames=[]);self.write_index()
        with self.assertRaisesRegex(ValueError,'Unreferenced'):validate(self.scan)

    def test_duplicate_timestamps_and_invalid_camera_rejected(self):
        self.index.update(saved_count=2,frames=[self.frame,copy.deepcopy(self.frame)]);self.write_index()
        with self.assertRaisesRegex(ValueError,'timestamps'):validate(self.scan)
        self.index.update(saved_count=1,frames=[self.frame]);self.frame['camera_to_world_column_major'][0]=float('nan');self.write_index()
        with self.assertRaisesRegex(ValueError,'camera'):validate(self.scan)

    def test_confidence_values_buffer_size_and_intrinsics_rejected(self):
        for name,data in [(self.frame['confidence_file'],bytes([9,1,0,2])),(self.frame['depth_file'],b'x')]:
            original=(self.scan/name).read_bytes();(self.scan/name).write_bytes(data);digest=hashlib.sha256(data).hexdigest()
            self.hashes[name]=digest;key='confidence_sha256' if 'confidence' in name else 'depth_sha256';old=self.frame[key];self.frame[key]=digest;self.write_index()
            with self.assertRaises(ValueError):validate(self.scan)
            (self.scan/name).write_bytes(original);self.hashes[name]=old;self.frame[key]=old
        self.frame['depth_intrinsics_column_major'][0]=500;self.write_index()
        with self.assertRaisesRegex(ValueError,'intrinsics'):validate(self.scan)

    def test_room_pass_requires_explicit_capture_phase_and_honors_sparse_limit(self):
        self.index['capture_profile']='room-pass-v1';self.write_index()
        with self.assertRaisesRegex(ValueError,'designation'):validate(self.scan)
        self.frame['capture_phase']='held_out';self.write_index();validate(self.scan)
        self.index['capture_profile']='unbounded';self.write_index()
        with self.assertRaisesRegex(ValueError,'profile'):validate(self.scan)
