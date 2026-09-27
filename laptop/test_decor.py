"""Scene adapter, immutable attachments, safety validation and alternate scene isolation."""
import copy
import json
import math
import tempfile
import unittest
from pathlib import Path
from uuid import uuid4
from design_input import DesignStore
from furniture import MODELS
from make_alternate_scene import create


class DecorTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.scan=create(self.root/'alternate');self.store=DesignStore(self.scan,self.root/'designs')

    def prop(self,asset,anchor):
        m=MODELS[asset]
        return dict(id='proposal-'+str(uuid4()),asset_id=asset,asset_sha256=m['sha256'],dimensions_m=m['dimensions_m'],anchor=anchor)

    def document(self):
        doc=self.store.new()
        table=self.prop('side-table-v1',dict(floor_identifier='synthetic-floor',x_m=11,z_m=7,yaw_degrees=30))
        art=self.prop('framed-painting-v1',dict(type='wall',wall_identifier='partition',u_m=-1.5,bottom_m=1.3,side=1,roll_degrees=10))
        fruit=self.prop('fruit-bowl-v1',dict(type='tabletop',support_identifier=table['id'],x_m=0,z_m=0,yaw_degrees=20))
        doc['proposals']=[art,fruit,table] # Child can precede parent.
        return doc

    def test_attachments_survive_save_and_reopen_and_table_transform(self):
        doc=self.document();before=self.store.payload(doc)['proposals'];saved,name=self.store.save(doc,None)
        raw=(self.store.output/name).read_bytes();fresh=DesignStore(self.scan,self.root/'designs');loaded=fresh.load(fresh.output/name)
        self.assertEqual(before,fresh.payload(loaded)['proposals'])
        table=loaded['proposals'][2];table['anchor'].update(x_m=12,z_m=7.5,yaw_degrees=90)
        after=fresh.payload(loaded)['proposals'];self.assertEqual(after[1]['position_m'],[12,MODELS['side-table-v1']['surface']['height_m'],7.5]);self.assertEqual(after[1]['yaw_degrees'],110)
        self.assertEqual(before[0],after[0]);fresh.save(loaded,name);self.assertEqual((self.store.output/name).read_bytes(),raw)

    def test_painting_rejects_edges_openings_windows_and_rotation(self):
        for edit in [dict(u_m=2.9),dict(u_m=0),dict(bottom_m=2.6),dict(bottom_m=.1,roll_degrees=90),dict(wall_identifier='foreign')]:
            doc=self.document();doc['proposals'][0]['anchor'].update(edit)
            with self.subTest(edit=edit),self.assertRaises(ValueError):self.store.payload(doc)
        for kind in ('windows','doors'):
            original=copy.deepcopy(self.store.scene['walls'][0]['holes']);self.store.scene['walls'][0]['holes'][0].update(kind=kind,passable=False)
            doc=self.document();doc['proposals'][0]['anchor']['u_m']=0
            with self.assertRaises(ValueError):self.store.payload(doc)
            self.store.scene['walls'][0]['holes']=original

    def test_wall_mount_offset_is_explicit_and_bounded(self):
        doc=self.document();original=self.store.payload(doc)['proposals'][0]
        doc['proposals'][0]['anchor']['mount_offset_m']=.08
        changed=self.store.payload(doc)['proposals'][0]
        self.assertAlmostEqual(math.dist(original['position_m'],changed['position_m']),.066)
        for value in [True,float('nan'),-.1,.2]:
            doc['proposals'][0]['anchor']['mount_offset_m']=value
            with self.assertRaises(ValueError):self.store.payload(doc)

    def test_fruit_requires_support_or_explicit_confirmation(self):
        for anchor in [dict(type='tabletop',support_identifier='missing',x_m=0,z_m=0,yaw_degrees=0),dict(floor_identifier='synthetic-floor',x_m=11,z_m=7,yaw_degrees=0),dict(type='confirmed_surface',floor_identifier='synthetic-floor',x_m=11,z_m=7,yaw_degrees=0,height_m=.7,confirmed=False)]:
            doc=self.document();doc['proposals'][1]['anchor']=anchor
            with self.assertRaises(ValueError):self.store.payload(doc)
        doc=self.document();doc['proposals'][1]['anchor']['x_m']=.5
        with self.assertRaises(ValueError):self.store.payload(doc)
        doc=self.document();doc['proposals'].pop()
        with self.assertRaises(ValueError):self.store.payload(doc)
        doc=self.document();doc['proposals'][1]['anchor']=dict(type='confirmed_surface',floor_identifier='synthetic-floor',x_m=11,z_m=7,yaw_degrees=0,height_m=.72,confirmed=True)
        self.assertAlmostEqual(self.store.payload(doc)['proposals'][1]['position_m'][1],.72)

    def test_obstacle_correction_persists_and_foreign_ids_rejected(self):
        doc=self.document();doc['navigation_overrides']={'synthetic-cabinet':{'enabled':False,'box':dict(x_m=11,z_m=6,width_m=.5,depth_m=.7,yaw_degrees=12)}}
        saved,name=self.store.save(doc,None);self.assertEqual(self.store.load(self.store.output/name)['navigation_overrides'],doc['navigation_overrides'])
        for value in [{'foreign':{'enabled':False}}, {'synthetic-cabinet':{'enabled':'false'}},{'synthetic-cabinet':{'enabled':True,'box':dict(x_m=float('nan'),z_m=6,width_m=.5,depth_m=.7,yaw_degrees=12)}}]:
            bad=copy.deepcopy(doc);bad['navigation_overrides']=value
            with self.assertRaises(ValueError):self.store.payload(bad)

    def test_second_scene_has_different_geometry_and_no_first_placements(self):
        doc=self.document();self.store.save(doc,None)
        second=create(self.root/'second');path=second/'manifest.json';manifest=json.loads(path.read_text());manifest['scan_id']=str(uuid4());path.write_text(json.dumps(manifest))
        path=second/'Room.json';room=json.loads(path.read_text());room['walls'][0]['dimensions'][0]=4;room['floors'][0]['polygonCorners'][0][0]=-2;path.write_text(json.dumps(room))
        import hashlib
        manifest['sha256']['Room.json']=hashlib.sha256(path.read_bytes()).hexdigest();(second/'manifest.json').write_text(json.dumps(manifest))
        other=DesignStore(second,self.root/'designs');payload=other.payload(other.new())
        self.assertNotEqual(payload['scene']['id'],self.store.scene['id']);self.assertNotEqual(payload['scene']['walls'],self.store.scene['walls']);self.assertEqual(payload['proposals'],[]);self.assertEqual(other.versions(),[])
        with self.assertRaises(ValueError):other.payload(doc)
        bad=self.document();bad['scene_id']='foreign'
        with self.assertRaises(ValueError):self.store.payload(bad)

    def test_old_schema_three_upgrades_without_rewriting(self):
        doc=self.store.new();doc['schema_version']=3;doc.pop('scene_id');doc.pop('navigation_overrides');doc['proposals']=[self.prop('sheen-chair-v1',dict(floor_identifier='synthetic-floor',x_m=11,z_m=7,yaw_degrees=0))]
        path=self.root/'old.json';path.write_text(json.dumps(doc));raw=path.read_bytes();new=self.store.payload(self.store.load(path));self.assertEqual(new['document']['schema_version'],4);self.assertEqual(path.read_bytes(),raw);self.assertEqual(new['document']['proposals'],doc['proposals'])


if __name__=='__main__':unittest.main()
