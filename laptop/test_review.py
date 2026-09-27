"""Review persistence, photo provenance, and geometry conflict regressions."""
import copy
import json
import unittest
import test_design_input as fixtures
from review_geometry import intersection, polygon_area


class ReviewTests(unittest.TestCase):
    setUp = fixtures.DesignInputTests.setUp
    write_room = fixtures.DesignInputTests.write_room
    resolved = fixtures.DesignInputTests.resolved
    def test_schema_one_upgrade_keeps_immutable_parent(self):
        old=self.store.new();old.pop('scene_id');old.pop('navigation_overrides');old['schema_version']=1;old.pop('proposals');old.pop('reviews');old.pop('reference_observations');old['revision']=1
        self.store.output.mkdir(parents=True);path=self.store.output/'revision-0001.design.json';path.write_text(json.dumps(old))
        before=path.read_bytes();loaded=self.store.load(path);new=self.store.payload(loaded,path.name)['document']
        self.assertEqual(new['schema_version'],4)
        new['elements'][0]['overrides']['color']={'hex':'#445566','origin':'user'}
        saved,name=self.store.save(new,path.name)
        self.assertEqual(saved['parent']['file'],path.name);self.assertEqual(path.read_bytes(),before)
        self.assertEqual(self.store.load(self.store.output/name),saved)

    def test_surface_color_exclusion_and_review_persist(self):
        self.room['doors'][0]['parentIdentifier']='wall';self.write_room()
        doc=self.store.new();issue=self.store.payload(doc)['review_queue'][0]
        doc['reviews'][issue['id']]='skipped'
        doc['elements'][0]['overrides']={'color':{'hex':'#eddfcf','origin':'user'}}
        door=next(e for e in doc['elements'] if e['source']['identifier']=='door');door['overrides']['excluded']=True
        saved,name=self.store.save(doc,None);loaded=self.store.load(self.store.output/name)
        self.assertEqual(loaded,saved)
        e=self.store.payload(loaded)['elements'][0]
        self.assertEqual(e['color']['origin'],'user');self.assertEqual(e['confidence'],'medium')
        self.assertEqual(e['measurement_accuracy'],'unverified; category confidence is not measurement accuracy')
        self.assertNotIn('door',[i for q in self.store.payload(loaded)['review_queue'] for i in q['elements']])

    def test_observed_color_requires_matching_rgb_hash(self):
        doc=self.store.new();doc['reference_observations']={'chair':{'hex':'#ffffff','reference_sha256':'0'*64,'sample_uv':[.5,.5],'note':'Synthetic'}}
        with self.assertRaisesRegex(ValueError,'verified photo'):self.store.validate_document(doc)
        doc=self.store.new();doc['elements'][0]['overrides']['color']={'hex':'blue','origin':'user'}
        with self.assertRaisesRegex(ValueError,'user color'):self.store.validate_document(doc)
        doc['elements'][0]['overrides']['color']={'hex':'#aaaaaa','origin':'reference'}
        with self.assertRaisesRegex(ValueError,'user color'):self.store.validate_document(doc)

    def test_low_category_review_does_not_imply_dimension_error(self):
        self.room['objects'][0]['confidence']={'low':{}};self.write_room()
        payload=self.store.payload(self.store.new());e=payload['elements'][-1]
        self.assertEqual(e['dimension_status'],['RoomPlan estimate']*3)
        self.assertEqual(e['color']['origin'],'unknown')
        self.assertTrue(any(q['kind']=='category' and q['elements']==['chair'] for q in payload['review_queue']))

    def test_overlaps_ignore_vertical_separation_and_detected_parent_child(self):
        a=self.room['objects'][0];a['dimensions']=[1,1,1]
        b=copy.deepcopy(a);b['identifier']='second';b['transform'][12]+=.4;self.room['objects'].append(b);self.write_room()
        overlaps=lambda:[q for q in self.store.payload(self.store.new())['review_queue'] if q['kind']=='overlap']
        self.assertEqual(len(overlaps()),1)
        b['transform'][13]+=2;self.write_room();self.assertEqual(overlaps(),[])
        b['transform'][13]-=2;b['parentIdentifier']='chair';self.write_room();self.assertEqual(overlaps(),[])

    def test_review_acknowledgement_reopens_after_geometry_change(self):
        self.room['objects'][0]['confidence']={'low':{}};self.write_room();doc=self.store.new()
        q=next(q for q in self.store.payload(doc)['review_queue'] if q['kind']=='category')
        doc['reviews'][q['id']]='confirmed'
        self.assertEqual(next(q for q in self.store.payload(doc)['review_queue'] if q['kind']=='category')['status'],'confirmed')
        doc['elements'][-1]['overrides']['dimensions_m']={'x':2}
        self.assertEqual(next(q for q in self.store.payload(doc)['review_queue'] if q['kind']=='category')['status'],'pending')

    def test_clipping_does_not_flag_disjoint_rotated_footprints(self):
        a=[[0,1],[1,0],[2,1],[1,2]];b=[[1.8,2.8],[2.8,1.8],[3.8,2.8],[2.8,3.8]]
        self.assertEqual(polygon_area(intersection(a,b)),0)
        self.assertAlmostEqual(polygon_area(intersection(a,a)),2)

    def test_floor_spatial_polygon_preserves_concave_source(self):
        e=self.resolved('floors');self.assertEqual(e['spatial']['polygon'],self.room['floors'][0]['polygonCorners'])
        self.assertEqual(e['spatial']['transform'],self.room['floors'][0]['transform'])
