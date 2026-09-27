"""Proposal persistence, anchoring and conservative warnings; synthetic fixtures."""
import copy
import hashlib
import json
import math
import unittest
from uuid import uuid4

import test_design_input as fixtures
from design_input import DesignStore
from furniture import CATALOG, contained, floor_y, verify_models
from review_geometry import polygon_area


class FurnitureTests(unittest.TestCase):
    setUp = fixtures.DesignInputTests.setUp
    write_room = fixtures.DesignInputTests.write_room

    def document(self, x=3, z=5, yaw=0):
        model = CATALOG[0]
        doc = self.store.new()
        doc['proposals'] = [{'id': 'proposal-'+str(uuid4()), 'asset_id': model['id'],
                             'asset_sha256': model['sha256'], 'dimensions_m': model['dimensions_m'][:],
                             'anchor': {'floor_identifier': 'floor', 'x_m': x, 'z_m': z, 'yaw_degrees': yaw}}]
        return doc

    def test_local_asset_identity(self):
        verify_models()
        self.assertTrue(CATALOG[0]['model_url'].startswith('/models/'))

    def test_anchor_and_rotated_footprint_share_metre_frame(self):
        p = self.store.payload(self.document(yaw=73))['proposals'][0]
        self.assertEqual(p['position_m'], [3,0,5])
        self.assertAlmostEqual(polygon_area(p['geometry']['points']), p['dimensions_m'][0]*p['dimensions_m'][2])
        self.assertEqual(p['center'], self.store.project(fixtures.IDENTITY, [3,0,5]))
        self.assertEqual(p['warnings'], [])

    def test_slight_floor_tilt_solves_plane_height(self):
        floor = copy.deepcopy(self.store.floors[0])
        floor['transform'][8:11] = [.01,-math.sqrt(1-.01**2),0]
        self.assertAlmostEqual(floor_y(floor,3,5), .01/math.sqrt(1-.01**2))

    def test_review_floor_edits_do_not_move_original_anchor(self):
        doc=self.document()
        next(e for e in doc['elements'] if e['source']['identifier']=='floor')['overrides']={'excluded':True,'dimensions_m':{'x':1}}
        self.assertEqual(self.store.payload(doc)['proposals'][0]['position_m'], [3,0,5])

    def test_warning_for_outside_floor_and_concave_notch(self):
        self.assertIn('outside', self.store.payload(self.document(x=4))['proposals'][0]['warnings'][0])
        floor=[[0,0],[3,0],[3,3],[2,3],[2,1],[1,1],[1,3],[0,3]]
        self.assertFalse(contained([[.5,.5],[2.5,.5],[2.5,2.5],[.5,2.5]],floor))

    def test_detected_object_warns_even_when_reviewed_removed(self):
        self.room['objects'][0]['transform'][13]=.5;self.write_room()
        doc=self.document(x=2)
        next(e for e in doc['elements'] if e['decision'])['decision']='remove'
        warnings=self.store.payload(doc)['proposals'][0]['warnings']
        self.assertTrue(any('detected' in w and 'remains in the splat' in w for w in warnings))

    def test_wall_proximity_and_vertical_separation(self):
        doc=self.document(x=2)
        self.assertFalse(any('wall overlap' in w for w in self.store.payload(doc)['proposals'][0]['warnings']))
        self.room['walls'][0]['transform'][13]=1;self.write_room()
        doc=self.document(x=2)
        self.assertTrue(any('wall overlap' in w for w in self.store.payload(doc)['proposals'][0]['warnings']))

    def test_two_proposals_warn_without_altering_either(self):
        doc=self.document();other=copy.deepcopy(doc['proposals'][0]);other['id']='proposal-'+str(uuid4());doc['proposals'].append(other)
        proposals=self.store.payload(doc)['proposals']
        self.assertTrue(all(any('proposal' in w for w in p['warnings']) for p in proposals))

    def test_cold_reopen_move_remove_immutable_parent_and_source(self):
        before={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in self.scan.iterdir()}
        first,name=self.store.save(self.document(),None);raw=(self.store.output/name).read_bytes()
        moved=copy.deepcopy(first);moved['proposals'][0]['anchor'].update(x_m=3.1,yaw_degrees=90)
        second,name2=self.store.save(moved,name)
        fresh=DesignStore(self.scan,self.root/'design-inputs')
        loaded=fresh.load(fresh.output/name2)
        self.assertEqual(second,loaded)
        self.assertEqual(loaded['parent']['sha256'],hashlib.sha256(raw).hexdigest())
        loaded['proposals']=[];third,name3=fresh.save(loaded,name2)
        self.assertEqual(fresh.payload(third)['proposals'],[])
        self.assertEqual((self.store.output/name).read_bytes(),raw)
        self.assertEqual(before,{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in self.scan.iterdir()})

    def test_schema_two_loads_and_upgrades_without_rewriting(self):
        old=self.store.new();old['schema_version']=2;old.pop('proposals')
        self.store.output.mkdir(parents=True);path=self.store.output/'revision-0001.design.json'
        old['revision']=1;path.write_text(json.dumps(old));before=path.read_bytes()
        loaded=self.store.payload(self.store.load(path),path.name)
        self.assertEqual(loaded['document']['schema_version'],3)
        self.assertEqual(loaded['proposals'],[])
        self.assertEqual(path.read_bytes(),before)

    def test_invalid_identity_scale_floor_and_numbers_rejected(self):
        mutations=[lambda p:p.update(asset_id='../private'),lambda p:p.update(asset_sha256='bad'),
                   lambda p:p.update(dimensions_m=[1,1,1]),lambda p:p['anchor'].update(floor_identifier='wall'),
                   lambda p:p['anchor'].update(y_m=3),lambda p:p['anchor'].update(yaw_degrees=361)]
        for v in [float('nan'),float('inf'),True,'1',101]:
            mutations.append(lambda p,v=v:p['anchor'].update(x_m=v))
        for mutate in mutations:
            doc=self.document();mutate(doc['proposals'][0])
            with self.assertRaises(ValueError):self.store.save(doc,None)
        doc=self.document();doc['proposals']*=2
        with self.assertRaises(ValueError):self.store.save(doc,None)
        self.assertEqual(self.store.versions(),[])


if __name__=='__main__':
    unittest.main()
