import contextlib
import hashlib
import io
import json
import struct
import tempfile
import unittest
import zipfile
from pathlib import Path

from import_scan import import_scan, validate

SCAN_ID = "12345678-1234-1234-1234-123456789abc"


def synthetic_usdz():
    """A real, aligned USDZ container with a cube; not a captured room."""
    contents = b'''#usda 1.0
(
    defaultPrim = "Fixture"
    metersPerUnit = 1
    upAxis = "Y"
)
def Xform "Fixture" {
    def Cube "SyntheticBox" {
        double size = 2
    }
}
'''
    stream = io.BytesIO()
    item = zipfile.ZipInfo("Fixture.usda")
    padding = (-30 - len(item.filename) - 4) % 64
    item.extra = struct.pack("<HH", 0x1986, padding) + bytes(padding)
    with zipfile.ZipFile(stream, "w") as model:
        model.writestr(item, contents)
    return stream.getvalue()


def make_fixture(source, rgb=False):
    source.mkdir()
    files = {
        "Room.json": json.dumps({"walls": [{"identifier": "synthetic-wall"}],
                                  "fixture_note": "Synthetic transport fixture, not a RoomPlan scan"}).encode(),
        "Room.usdz": synthetic_usdz(),
    }
    if rgb:
        files["Reference.jpg"] = b"\xff\xd8\xff\xe0synthetic-jpeg-header\xff\xd9"
        files["Reference.json"] = json.dumps({
            "timestamp_seconds": 123.5,
            "image_width": 1920, "image_height": 1440,
            "camera_to_world_column_major": [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1],
            "intrinsics_column_major": [1000, 0, 0, 0, 1000, 0, 960, 720, 1],
        }).encode()
    for name, contents in files.items():
        (source / name).write_bytes(contents)
    manifest = {"schema_version": 1, "scan_id": SCAN_ID, "rgb_reference_available": rgb,
                "sha256": {name: hashlib.sha256(contents).hexdigest() for name, contents in files.items()}}
    (source / "manifest.json").write_text(json.dumps(manifest))
    return manifest


class ImportScanTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "RoomScan-test"
        self.archive = self.root / "scans"
        self.output = contextlib.redirect_stdout(io.StringIO())
        self.output.__enter__()
        self.addCleanup(self.output.__exit__, None, None, None)

    def manifest(self, change):
        path = self.source / "manifest.json"
        value = json.loads(path.read_text())
        change(value)
        path.write_text(json.dumps(value))

    def rehash(self, name):
        self.manifest(lambda m: m["sha256"].update({name: hashlib.sha256((self.source / name).read_bytes()).hexdigest()}))

    def test_folder_import_is_idempotent_and_detects_corruption(self):
        make_fixture(self.source)
        first = import_scan(self.source, self.archive)
        self.assertEqual(first, import_scan(self.source, self.archive))
        self.assertEqual((first / "Room.json").read_bytes(), (self.source / "Room.json").read_bytes())
        (self.source / "Room.usdz").write_bytes(b"corrupted")
        with self.assertRaisesRegex(ValueError, "damaged"):
            import_scan(self.source, self.archive)

    def test_zip_flat_and_nested(self):
        make_fixture(self.source, rgb=True)
        for prefix in ("", "RoomScan-test/"):
            with self.subTest(prefix=prefix):
                package = self.root / "scan.zip"
                with zipfile.ZipFile(package, "w", zipfile.ZIP_DEFLATED) as archive:
                    for file in self.source.iterdir():
                        archive.write(file, prefix + file.name)
                result = import_scan(package, self.archive)
                self.assertTrue(validate(result)["rgb_reference_available"])

    def test_missing_file_does_not_publish_destination(self):
        make_fixture(self.source)
        (self.source / "Room.usdz").unlink()
        with self.assertRaisesRegex(ValueError, "damaged"):
            import_scan(self.source, self.archive)
        self.assertFalse((self.archive / SCAN_ID).exists())

    def test_id_collision_preserves_original(self):
        make_fixture(self.source)
        original = import_scan(self.source, self.archive)
        original_json = (original / "Room.json").read_bytes()
        (self.source / "Room.json").write_text('{"walls": [1, 2]}')
        self.rehash("Room.json")
        with self.assertRaisesRegex(ValueError, "different contents"):
            import_scan(self.source, self.archive)
        self.assertEqual(original_json, (original / "Room.json").read_bytes())

    def test_rgb_requires_complete_pair_and_metadata(self):
        make_fixture(self.source, rgb=True)
        self.manifest(lambda m: m["sha256"].pop("Reference.json"))
        with self.assertRaisesRegex(ValueError, "RGB"):
            validate(self.source)
        self.rehash("Reference.json")
        (self.source / "Reference.json").write_text('{}')
        self.rehash("Reference.json")
        with self.assertRaisesRegex(ValueError, "camera metadata"):
            validate(self.source)

    def test_invalid_manifest_and_room_shapes(self):
        make_fixture(self.source)
        for value in (None, [], "text"):
            (self.source / "manifest.json").write_text(json.dumps(value))
            with self.assertRaisesRegex(ValueError, "JSON object"):
                validate(self.source)
        self.source.joinpath("manifest.json").write_text('{}')
        with self.assertRaisesRegex(ValueError, "version"):
            validate(self.source)

    def test_damaged_model_with_updated_hash_is_rejected(self):
        make_fixture(self.source)
        (self.source / "Room.usdz").write_bytes(b"not a model")
        self.rehash("Room.usdz")
        with self.assertRaisesRegex(ValueError, "USDZ"):
            validate(self.source)

    def test_empty_room_is_rejected(self):
        make_fixture(self.source)
        (self.source / "Room.json").write_text('{"walls": []}')
        self.rehash("Room.json")
        with self.assertRaisesRegex(ValueError, "walls"):
            validate(self.source)

    def test_zip_traversal_and_symlink_rejected(self):
        for entry in ("../escape", "/tmp/escape", "link"):
            with self.subTest(entry=entry):
                package = self.root / "unsafe.zip"
                with zipfile.ZipFile(package, "w") as archive:
                    info = zipfile.ZipInfo(entry)
                    if entry == "link":
                        info.external_attr = 0o120777 << 16
                    archive.writestr(info, b"target")
                with self.assertRaisesRegex(ValueError, "Unsafe"):
                    import_scan(package, self.archive)

    def test_symlink_payload_rejected(self):
        make_fixture(self.source)
        model = self.source / "Room.usdz"
        saved = self.root / "saved.usdz"
        model.rename(saved)
        model.symlink_to(saved)
        with self.assertRaisesRegex(ValueError, "damaged"):
            validate(self.source)

    def test_bad_zip_is_rejected(self):
        package = self.root / "bad.zip"
        package.write_bytes(b"partial transfer")
        with self.assertRaises(zipfile.BadZipFile):
            import_scan(package, self.archive)

    def test_missing_or_multiple_manifests_rejected(self):
        for count in (0, 2):
            package = self.root / "scan.zip"
            with zipfile.ZipFile(package, "w") as archive:
                for index in range(count):
                    archive.writestr(f"{index}/manifest.json", "{}")
            with self.assertRaisesRegex(ValueError, "exactly one"):
                import_scan(package, self.archive)


if __name__ == "__main__":
    unittest.main()
