"""Checks the experiment's isolation and fixed-camera comparison contract."""
import hashlib,json,tempfile,unittest
from pathlib import Path
try:
    import numpy as np
    from pose_overrides import apply_poses
    from compare_pose_experiment import verify_cameras
    from diagnose_capture import epipolar_error,reprojection
    AVAILABLE=True
except ImportError:AVAILABLE=False

@unittest.skipUnless(AVAILABLE,'optional reconstruction dependencies unavailable')
class PoseRefinementTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        (self.root/'Frames.json').write_text('immutable raw index')
        self.pose=np.eye(4).flatten(order='F').tolist()
        self.frames=[dict(rgb_file='train.jpg',capture_phase='train',camera_to_world_column_major=self.pose),dict(rgb_file='test.jpg',capture_phase='held_out',camera_to_world_column_major=self.pose)]
        self.path=self.root/'derived.json'
        self.data=dict(schema='room-camera-refinement-v1',index_sha256=hashlib.sha256((self.root/'Frames.json').read_bytes()).hexdigest(),poses={'train.jpg':self.pose})
    def tearDown(self):self.tmp.cleanup()
    def write(self):self.path.write_text(json.dumps(self.data))
    def test_only_training_pose_changes_and_raw_input_is_unmodified(self):
        changed=np.eye(4);changed[0,3]=.03;self.data['poses']['train.jpg']=changed.flatten(order='F').tolist();self.write()
        result=apply_poses(self.root,self.frames,self.path)
        self.assertEqual(result[1],self.frames[1]);self.assertEqual(self.frames[0]['camera_to_world_column_major'],self.pose)
        self.assertEqual(result[0]['camera_to_world_column_major'][12],.03)
    def test_rejects_test_pose_scale_and_wrong_source(self):
        self.data['poses']['test.jpg']=self.pose;self.write()
        with self.assertRaisesRegex(ValueError,'held-out'):apply_poses(self.root,self.frames,self.path)
        del self.data['poses']['test.jpg'];self.data['poses']['train.jpg']=[2*x for x in self.pose];self.write()
        with self.assertRaisesRegex(ValueError,'rigid'):apply_poses(self.root,self.frames,self.path)
        self.data['index_sha256']='wrong';self.write()
        with self.assertRaisesRegex(ValueError,'immutable'):apply_poses(self.root,self.frames,self.path)
    def test_same_camera_contract_refuses_changed_test_camera(self):
        for name in ['baseline','candidate']:
            folder=self.root/name;(folder/'brush-data').mkdir(parents=True)
            (folder/'split.json').write_text(json.dumps(dict(held_out=[],train=[])))
            (folder/'brush-data/transforms_test.json').write_text(json.dumps(dict(frames=[])))
        verify_cameras(self.root/'baseline',self.root/'candidate')
        (self.root/'candidate/brush-data/transforms_test.json').write_text(json.dumps(dict(frames=[],fl_x=100)))
        with self.assertRaisesRegex(ValueError,'camera'):verify_cameras(self.root/'baseline',self.root/'candidate')
    def test_projection_and_epipolar_geometry_for_known_camera_shift(self):
        k=np.array([[500,0,480],[0,500,360],[0,0,1]])
        a=dict(image_width=960,intrinsics_column_major=k.flatten(order='F').tolist(),camera_to_world_column_major=self.pose)
        moved=np.eye(4);moved[0,3]=.1;b={**a,'camera_to_world_column_major':moved.flatten(order='F').tolist()}
        uv=np.array([[500.,400.],[600.,200.]]);target=uv-np.array([25.,0.])
        np.testing.assert_allclose(reprojection(a,b,uv,target,np.array([2.,2.])),0,atol=1e-9)
        np.testing.assert_allclose(epipolar_error(a,b,uv,target),0,atol=1e-9)
        self.assertTrue(np.all(epipolar_error(a,b,uv,target+[0,10])>5))
