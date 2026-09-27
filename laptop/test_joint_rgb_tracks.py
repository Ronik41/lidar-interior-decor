"""Verify connectivity rejection and report serialization without private photos."""
import json
import unittest
try:
    import numpy as np
    from joint_rgb_tracks import components, bridges, track_graph, spatial_support
    AVAILABLE=True
except ImportError:
    AVAILABLE=False


@unittest.skipUnless(AVAILABLE, 'Optional reconstruction environment required')
class JointTrackTests(unittest.TestCase):
    def setup_graph(self):
        frames=[{'timestamp_seconds':i*.5} for i in range(40)]
        positions=np.column_stack([np.arange(40)*.1,np.zeros(40),np.zeros(40)])
        return frames,positions

    def test_connected_revisited_multiview_graph_passes_and_serializes(self):
        frames,positions=self.setup_graph()
        tracks=[{'nodes':[(i,k) for i in range(40)]} for k in range(30)]
        graph=track_graph(tracks,frames,positions)
        self.assertTrue(graph['passed'])
        self.assertEqual(graph['component_sizes'],[40])
        self.assertEqual(graph['bridges'],[])
        json.dumps(graph)

    def test_separate_textured_groups_do_not_establish_room_connectivity(self):
        frames,positions=self.setup_graph()
        tracks=[{'nodes':[(i,k) for i in group]} for group in [range(20),range(20,40)] for k in range(30)]
        graph=track_graph(tracks,frames,positions)
        self.assertFalse(graph['passed'])
        self.assertEqual(graph['component_sizes'],[20,20])
        self.assertFalse(graph['gates']['all_temporal_blocks'])
        self.assertFalse(graph['gates']['all_populated_spatial_cells'])
        json.dumps(graph)  # includes integer-valued cells originating in NumPy

    def test_weak_shared_tracks_are_not_graph_edges(self):
        frames,positions=self.setup_graph()
        tracks=[{'nodes':[(i,k) for i in range(40)]} for k in range(14)]
        graph=track_graph(tracks,frames,positions)
        self.assertFalse(graph['passed'])
        self.assertEqual(graph['edges'],[])

    def test_single_edge_bridge_is_identified(self):
        groups,adjacency=components(6,[(0,1),(1,2),(2,0),(2,3),(3,4),(4,5),(5,3)])
        self.assertEqual(groups,[list(range(6))])
        self.assertEqual(bridges(adjacency,set(range(6))),[[2,3]])

    def test_image_support_rejects_a_small_cluster(self):
        cells,area=spatial_support(np.array([[10.,10.],[12.,10.],[12.,13.],[10.,13.]]),960,720)
        self.assertEqual(cells,1)
        self.assertLess(area,.001)
