"""Run with .venv-reconstruction/bin/python; skipped without optional reconstruction dependencies."""
import unittest
try:
 import numpy as np
 import open3d as o
 from reconstruct_room import split_frames,CV_FROM_AR
 AVAILABLE=True
except ImportError:AVAILABLE=False

@unittest.skipUnless(AVAILABLE,'optional reconstruction runtime not installed in this Python')
class PipelineTests(unittest.TestCase):
 def test_held_out_capture_phase_never_enters_training(self):
  frames=[{'rgb_file':str(i),'capture_phase':'train' if i<30 else 'held_out'} for i in range(40)]
  train,test=split_frames(frames)
  self.assertEqual(len(train),30);self.assertEqual([x['rgb_file'] for x in test],['30','35'])
  self.assertTrue(all(x['capture_phase']=='train' for x in train))
 def test_arkit_forward_maps_to_positive_depth(self):
  np.testing.assert_equal(CV_FROM_AR@np.array([1,2,-3,1]),[1,-2,3,1])
 def test_metric_plane_fuses_with_normalized_color(self):
  c=o.core;v=o.t.geometry.VoxelBlockGrid(attr_names=('tsdf','weight','color'),attr_dtypes=(c.float32,)*3,attr_channels=((1),(1),(3)),voxel_size=.04,block_resolution=16,block_count=1000)
  d=o.t.geometry.Image(c.Tensor(np.full((48,64,1),2,dtype='f4')));col=o.t.geometry.Image(c.Tensor(np.full((48,64,3),.5,dtype='f4')))
  k=c.Tensor([[45.,0,32],[0,45.,24],[0,0,1]],dtype=c.float64);e=c.Tensor(np.eye(4),dtype=c.float64)
  b=v.compute_unique_block_coordinates(d,k,e,1.,4.5,4.);v.integrate(b,d,col,k,k,e,1.,4.5,4.)
  m=v.extract_triangle_mesh(weight_threshold=.5).to_legacy()
  self.assertGreater(len(m.vertices),100);self.assertLess(abs(np.median(np.asarray(m.vertices)[:,2])-2),.04)
  self.assertAlmostEqual(float(np.median(np.asarray(m.vertex_colors))),.5,places=3)
