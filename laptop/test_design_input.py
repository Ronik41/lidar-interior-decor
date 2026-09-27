"""Synthetic geometry and persistence tests; no private scan fixtures."""
import copy
import hashlib
import http.client
import json
import math
import tempfile
import threading
import unittest
from pathlib import Path

from design_input import DesignStore, transform_point
from edit_room import make_server
from test_import_scan import make_fixture


IDENTITY = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]


def element(identifier, category, dims, matrix=None):
    return {"identifier": identifier, "category": {category: {}}, "dimensions": dims,
            "transform": matrix or IDENTITY[:], "confidence": {"medium": {}}}


class DesignInputTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.scan = self.root / "scan"
        make_fixture(self.scan)
        # Width 4 along world Z, with a nonzero translation (2, 3, 5).
        self.matrix = [0, 0, 1, 0, 0, 1, 0, 0, -1, 0, 0, 0, 2, 3, 5, 1]
        self.room = {
            "walls": [element("wall", "wall", [4, 2.5, 0], self.matrix)],
            "doors": [element("door", "door", [1, 2, 0], self.matrix)],
            "openings": [element("opening", "opening", [1.5, 2.5, 0], self.matrix)],
            "windows": [],
            "objects": [element("chair", "chair", [1, 1.5, .5], self.matrix)],
            "floors": [element("floor", "floor", [4, 3, 0],
                               [1,0,0,0, 0,0,1,0, 0,-1,0,0, 2,0,5,1])],
        }
        self.room["floors"][0]["polygonCorners"] = [[-2,-1,0],[2,-1,0],[2,2,0],[-2,2,0]]
        self.write_room()

    def write_room(self):
        path = self.scan / "Room.json"
        path.write_text(json.dumps(self.room))
        manifest_path = self.scan / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["units"] = "meters"
        manifest["sha256"]["Room.json"] = hashlib.sha256(path.read_bytes()).hexdigest()
        manifest_path.write_text(json.dumps(manifest))
        self.store = DesignStore(self.scan, self.root / "design-inputs")

    def resolved(self, kind, doc=None):
        return next(e for e in self.store.payload(doc or self.store.new())["elements"] if e["kind"] == kind)

    def test_column_major_translation_and_rotation(self):
        self.assertEqual(transform_point(self.matrix, [2, 1, .5]), [1.5, 4, 7])
        wall = self.resolved("walls")["geometry"]["points"]
        self.assertAlmostEqual(math.dist(*wall), 4)
        self.assertAlmostEqual(wall[0][1], wall[1][1])
        self.assertAlmostEqual(math.dist(*self.resolved("doors")["geometry"]["points"]), 1)
        self.assertAlmostEqual(math.dist(*self.resolved("openings")["geometry"]["points"]), 1.5)

    def test_object_footprint_uses_depth_not_height(self):
        points = self.resolved("objects")["geometry"]["points"]
        edges = sorted(math.dist(p, points[(i+1)%4]) for i, p in enumerate(points))
        for actual, expected in zip(edges, [.5,.5,1,1]):
            self.assertAlmostEqual(actual, expected)

    def test_floor_polygon_is_local_xy_then_world_xz(self):
        points = self.resolved("floors")["geometry"]["points"]
        expected = [self.store.project(self.room["floors"][0]["transform"], p)
                    for p in self.room["floors"][0]["polygonCorners"]]
        self.assertEqual(points, expected)
        self.assertAlmostEqual(math.dist(points[0], points[1]), 4)
        self.assertAlmostEqual(math.dist(points[1], points[2]), 3)

    def test_corrections_decisions_roundtrip_and_source_unchanged(self):
        before = {p.name: p.read_bytes() for p in self.scan.iterdir()}
        doc = self.store.new()
        edit = next(e for e in doc["elements"] if e["source"]["identifier"] == "chair")
        edit["overrides"] = {"label":"Desk chair", "category":"office chair", "dimensions_m":{"x":1.2}, "note":"Synthetic correction"}
        edit["decision"] = "keep"
        preview = self.store.payload(doc)
        saved, name = self.store.save(doc, None)
        fresh_store = DesignStore(self.scan, self.root / "design-inputs")
        reopened = fresh_store.load(fresh_store.output / name)
        self.assertEqual(saved, reopened)
        self.assertEqual(preview["elements"], fresh_store.payload(reopened)["elements"])
        self.assertEqual(preview["bounds"], fresh_store.payload(reopened)["bounds"])
        self.assertEqual(before, {p.name:p.read_bytes() for p in self.scan.iterdir()})
        current = self.resolved("objects", reopened)
        self.assertEqual(current["original_category"], "chair")
        self.assertEqual(current["dimension_status"][0], "user correction (unverified)")
        self.assertEqual(current["source"]["json_pointer"], "/objects/0")

    def test_revisions_are_immutable_and_branch_from_opened_revision(self):
        first, name1 = self.store.save(self.store.new(), None)
        bytes1 = (self.store.output / name1).read_bytes()
        second, name2 = self.store.save(first, name1)
        third, name3 = self.store.save(first, name1)
        self.assertEqual((first["revision"],second["revision"],third["revision"]), (1,2,3))
        self.assertEqual(third["parent"]["file"], name1)
        self.assertEqual(third["parent"]["sha256"], hashlib.sha256(bytes1).hexdigest())
        self.assertEqual((self.store.output / name1).read_bytes(), bytes1)
        self.assertEqual(len(self.store.versions()), 3)
        self.assertNotEqual(name2, name3)

    def test_missing_data_does_not_invent_geometry_or_category(self):
        raw = self.room["objects"][0]
        raw.pop("category")
        raw["dimensions"][2] = None
        self.write_room()
        obj = self.resolved("objects")
        self.assertIsNone(obj["category"])
        self.assertEqual(obj["geometry"]["type"], "marker")
        self.assertEqual(len(obj["warnings"]), 2)
        doc = self.store.new()
        next(e for e in doc["elements"] if e["source"]["identifier"] == "chair")["overrides"] = {"dimensions_m":{"z":.7}}
        self.assertEqual(self.resolved("objects", doc)["geometry"]["type"], "polygon")
        raw.pop("transform")
        self.write_room()
        self.assertIsNone(self.resolved("objects")["geometry"])

    def test_floor_fallback_and_curved_wall_are_explicit(self):
        self.room["floors"][0].pop("polygonCorners")
        self.room["walls"][0]["curve"] = {"radius":2}
        self.write_room()
        self.assertIn("bounding-box estimate", self.resolved("floors")["warnings"][0])
        self.assertIn("approximation", self.resolved("walls")["warnings"][0])

    def test_dimension_correction_changes_footprint_without_moving_center(self):
        before = self.resolved("objects")
        doc = self.store.new()
        next(e for e in doc["elements"] if e["source"]["identifier"] == "chair")["overrides"] = {"dimensions_m":{"x":2}}
        after = self.resolved("objects", doc)
        self.assertEqual(after["center"],before["center"])
        self.assertNotEqual(after["geometry"],before["geometry"])
        self.assertEqual(after["original_dimensions_m"],before["original_dimensions_m"])

    def test_invalid_versions_source_links_decisions_and_numbers_rejected(self):
        mutations = [lambda d:d.update(schema_version=5), lambda d:d.update(schema_version=True),
                     lambda d:d["source"].update(room_sha256="wrong"),
                     lambda d:d["elements"][0]["source"].update(identifier="wrong"),
                     lambda d:d["elements"].pop(), lambda d:d["elements"][0].update(decision="remove"),
                     lambda d:d["elements"][-1].update(decision="maybe"),
                     lambda d:d["elements"][-1]["overrides"].update(transform=IDENTITY)]
        for value in [-1, 0, 101, float("nan"), float("inf"), True, "2"]:
            mutations.append(lambda d, v=value:d["elements"][-1]["overrides"].update(dimensions_m={"x":v}))
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                doc = self.store.new()
                mutation(doc)
                with self.assertRaises(ValueError):
                    self.store.save(doc, None)
        self.assertEqual(self.store.versions(), [])

    def test_duplicate_source_ids_rejected(self):
        self.room["objects"][0]["identifier"] = "wall"
        with self.assertRaisesRegex(ValueError,"unique"):
            self.write_room()

    def test_changed_raw_source_blocks_save_and_reopen(self):
        saved, name = self.store.save(self.store.new(), None)
        (self.scan / "Room.json").write_text("{}")
        for call in [lambda:self.store.save(saved,name), lambda:self.store.load(self.store.output/name)]:
            with self.assertRaisesRegex(ValueError,"damaged"):
                call()

    def test_source_output_and_path_traversal_rejected(self):
        with self.assertRaisesRegex(ValueError,"separate"):
            DesignStore(self.scan, self.scan)
        with self.assertRaises(ValueError):
            self.store.version_path("../../Room.json")

    def test_meter_units_required(self):
        p = self.scan / "manifest.json"
        m = json.loads(p.read_text()); m["units"] = "feet"; p.write_text(json.dumps(m))
        with self.assertRaisesRegex(ValueError,"meter"):
            DesignStore(self.scan, self.root / "out")

    def test_http_save_reopen_and_local_only_boundary(self):
        server = make_server(self.store, self.store.new(), None)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        self.addCleanup(server.server_close); self.addCleanup(server.shutdown)
        connection = http.client.HTTPConnection("127.0.0.1", server.server_port)
        self.addCleanup(connection.close)
        def request(method, path, body=None, headers=None):
            connection.request(method,path,json.dumps(body) if body is not None else None,headers or {})
            response = connection.getresponse()
            return response.status,json.loads(response.read())
        code, state = request("GET","/api/state")
        self.assertEqual(code,200)
        code, _ = request("POST","/api/save",{"document":state["document"]})
        self.assertEqual(code,403)
        headers={"X-Editor-Token":state["token"], "Origin":f"http://127.0.0.1:{server.server_port}"}
        state["document"]["elements"][-1]["decision"]="remove"
        code, saved = request("POST","/api/save",{"document":state["document"],"filename":None},headers)
        self.assertEqual(code,200)
        code, reopened = request("GET",f"/api/open?file={saved['filename']}")
        self.assertEqual(code,200);self.assertEqual(saved,reopened)
        code, _ = request("GET","/Room.json")
        self.assertEqual(code,404)
        code, _ = request("GET","/api/state",headers={"Host":"example.com"})
        self.assertEqual(code,403)
        headers["Origin"]="https://example.com"
        code, _ = request("POST","/api/save",{"document":state["document"]},headers)
        self.assertEqual(code,403)


if __name__ == "__main__":
    unittest.main()
