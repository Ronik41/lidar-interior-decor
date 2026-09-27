"""Selection must preserve the ending, exact depth seed and honest evaluation labels."""
import unittest
from video_reconstruction import selection


def fixture(held_out=False):
    frames=[]
    for n in range(900):
        frames.append(dict(frame_index=n,elapsed_seconds=n/30,
            capture_phase='held_out' if held_out and n>=600 else 'train',
            depth_available=n%15==0,confidence_available=n%15==0))
    return {'frames':frames}


class VideoSelectionTests(unittest.TestCase):
    def test_complete_recording_end_is_training_without_invented_holdout(self):
        index=fixture();plan=selection(index)
        self.assertEqual(plan['evaluation_kind'],'training_reprojection')
        self.assertEqual(plan['excluded_held_out_ids'],[])
        self.assertEqual(plan['dense_ids'][0],0)
        self.assertEqual(plan['dense_ids'][-1],899)
        self.assertTrue(set(plan['diagnostic_ids']) <= set(plan['dense_ids']))
        self.assertEqual(len(plan['diagnostic_ids']),12)
        self.assertTrue(set(plan['geometry_ids']) <= set(plan['dense_ids']))
        self.assertEqual(plan['geometry_ids'],list(range(0,900,15)))

    def test_explicit_test_phase_is_excluded_from_both_training_inputs(self):
        plan=selection(fixture(True))
        self.assertEqual(plan['evaluation_kind'],'held_out')
        self.assertEqual(plan['dense_ids'][-1],599)
        self.assertFalse(set(plan['dense_ids']) & set(plan['excluded_held_out_ids']))
        self.assertFalse(set(plan['geometry_ids']) & set(plan['excluded_held_out_ids']))
        self.assertTrue(set(plan['diagnostic_ids']) <= set(plan['excluded_held_out_ids']))

    def test_no_depth_does_not_silently_replace_geometry_seed(self):
        index=fixture()
        for f in index['frames']:f['depth_available']=False
        with self.assertRaisesRegex(ValueError,'No depth'):
            selection(index)

    def test_selection_does_not_mutate_source_phase_or_timestamps(self):
        import copy
        index=fixture();before=copy.deepcopy(index);selection(index)
        self.assertEqual(before,index)
