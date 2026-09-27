"""Local, versioned RoomPlan review data. Raw packages are read-only inputs."""

import copy
import datetime as dt
import json
import math
import os
import re
import tempfile
from pathlib import Path

from import_scan import file_hash, read_object, validate
from review_geometry import enrich, review_queue, validate_observations

COLLECTIONS = ("walls", "doors", "openings", "windows", "floors", "objects")
PREFIX = dict(zip(COLLECTIONS, ("W", "D", "O", "G", "F", "")))
FORMAT = "roomplan-design-input"
COORDINATES = "meters; RoomPlan column-major local-to-world; top-down world X/Z"


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def enum_name(value):
    if isinstance(value, dict) and len(value) == 1:
        return next(iter(value))
    return value if isinstance(value, str) and value else None


def vector(value, size):
    return isinstance(value, list) and len(value) == size and all(finite(v) for v in value)


def transform_point(matrix, point):
    return [sum(matrix[c * 4 + r] * point[c] for c in range(3)) + matrix[12 + r]
            for r in range(3)]


def hull(points):
    """Convex silhouette of a projected object bounding box."""
    points = sorted(set(tuple(p) for p in points))
    if len(points) <= 2:
        return [list(p) for p in points]
    def cross(o, a, b):
        return (a[0]-o[0])*(b[1]-o[1]) - (a[1]-o[1])*(b[0]-o[0])
    lower, upper = [], []
    for sequence, target in ((points, lower), (reversed(points), upper)):
        for p in sequence:
            while len(target) >= 2 and cross(target[-2], target[-1], p) <= 0:
                target.pop()
            target.append(p)
    return [list(p) for p in lower[:-1] + upper[:-1]]


class DesignStore:
    def __init__(self, scan, output_root):
        self.scan = Path(scan).resolve()
        self.manifest = validate(self.scan)
        if self.manifest.get("units") != "meters":
            raise ValueError("Scan must explicitly declare meter units")
        self.source = {
            "scan_id": self.manifest["scan_id"],
            "room_file": "Room.json",
            "room_sha256": file_hash(self.scan / "Room.json"),
            "manifest_sha256": file_hash(self.scan / "manifest.json"),
        }
        self.output = Path(output_root).resolve() / self.source["scan_id"]
        if self.output == self.scan or self.scan in self.output.parents:
            raise ValueError("Design output must be separate from the raw scan")
        self.room = read_object(self.scan / "Room.json")
        self.elements = []
        seen = set()
        for collection in COLLECTIONS:
            rows = self.room.get(collection, [])
            if not isinstance(rows, list):
                raise ValueError(f"Expected an array: {collection}")
            for index, raw in enumerate(rows):
                if not isinstance(raw, dict):
                    raise ValueError(f"Invalid {collection} element")
                identifier = raw.get("identifier")
                if not isinstance(identifier, str) or not identifier or identifier in seen:
                    raise ValueError("Source elements need unique identifiers")
                seen.add(identifier)
                self.elements.append({
                    "source": {"identifier": identifier, "collection": collection,
                               "json_pointer": f"/{collection}/{index}"},
                    "code": f"{PREFIX[collection]}{index+1:02d}", "raw": raw,
                })
        # A fixed rotation only, never nonuniform scaling or geometry snapping.
        walls = [e["raw"] for e in self.elements if e["source"]["collection"] == "walls"
                 and vector(e["raw"].get("transform"), 16)
                 and vector(e["raw"].get("dimensions"), 3)]
        longest = max(walls, key=lambda w: w["dimensions"][0], default=None)
        angle = math.atan2(longest["transform"][2], longest["transform"][0]) if longest else 0
        self.rotation = (angle + math.pi / 2) % math.pi - math.pi / 2
        self.observations = {}
        observations_path = self.output / "reference-observations.json"
        if observations_path.exists():
            evidence = read_object(observations_path)
            if evidence.get("source") != self.source:
                raise ValueError("Reference color evidence does not match this scan")
            self.observations = evidence.get("observations", {})
            validate_observations(self.observations, self.elements, self.manifest)

    def verify(self):
        if validate(self.scan) != self.manifest or file_hash(self.scan / "manifest.json") != self.source["manifest_sha256"]:
            raise ValueError("The source scan has changed; reopen the verified original")

    def new(self):
        return {
            "format": FORMAT, "schema_version": 2, "revision": 0,
            "saved_at": None, "parent": None, "source": copy.deepcopy(self.source),
            "coordinates": COORDINATES, "plan_rotation_radians": self.rotation,
            "reference_observations": copy.deepcopy(self.observations), "reviews": {},
            "elements": [{"source": copy.deepcopy(e["source"]), "overrides": {},
                          "decision": "unsure" if e["source"]["collection"] == "objects" else None}
                         for e in self.elements],
        }

    def validate_document(self, doc):
        expected = self.new()
        if isinstance(doc, dict) and type(doc.get("schema_version")) is int and doc["schema_version"] == 1:
            expected.pop("reference_observations")
            expected.pop("reviews")
            expected["schema_version"] = 1
        if not isinstance(doc, dict) or set(doc) != set(expected):
            raise ValueError("Invalid design-input fields")
        for key in ("format", "schema_version", "source", "coordinates", "plan_rotation_radians"):
            if doc[key] != expected[key] or (key == "schema_version" and type(doc[key]) is not int):
                raise ValueError(f"Unsupported or mismatched design input: {key}")
        if type(doc["revision"]) is not int or doc["revision"] < 0:
            raise ValueError("Invalid revision")
        if doc["saved_at"] is not None and not isinstance(doc["saved_at"], str):
            raise ValueError("Invalid save timestamp")
        parent = doc["parent"]
        if parent is not None and (not isinstance(parent, dict) or set(parent) != {"file", "sha256"}
                or not isinstance(parent["file"], str) or not re.fullmatch(r"revision-\d{4,}\.design\.json", parent["file"])
                or not isinstance(parent["sha256"], str) or not re.fullmatch(r"[a-f0-9]{64}", parent["sha256"])):
            raise ValueError("Invalid parent revision")
        edits = doc["elements"]
        if not isinstance(edits, list) or len(edits) != len(self.elements):
            raise ValueError("Design must retain every source element")
        for base, edit in zip(self.elements, edits):
            if (not isinstance(edit, dict) or set(edit) != {"source", "overrides", "decision"}
                    or edit["source"] != base["source"]):
                raise ValueError("Source element links must remain unchanged")
            is_object = base["source"]["collection"] == "objects"
            if edit["decision"] not in (("keep", "remove", "unsure") if is_object else (None,)):
                raise ValueError("Invalid furniture decision")
            changes = edit["overrides"]
            allowed = {"label", "category", "dimensions_m", "note"}
            if doc["schema_version"] == 2:
                allowed |= {"color", "excluded"}
            if not isinstance(changes, dict) or set(changes) - allowed:
                raise ValueError("Unsupported override")
            if "excluded" in changes and (is_object or type(changes["excluded"]) is not bool):
                raise ValueError("Invalid structure exclusion")
            color = changes.get("color")
            if color is not None and (not isinstance(color, dict) or set(color) != {"hex", "origin"}
                    or color["origin"] != "user" or not isinstance(color["hex"], str)
                    or not re.fullmatch(r"#[0-9a-fA-F]{6}", color["hex"])):
                raise ValueError("Invalid user color")
            for key in ("label", "category", "note"):
                if key in changes and (not isinstance(changes[key], str) or not changes[key].strip()
                                       or len(changes[key]) > (1000 if key == "note" else 100)):
                    raise ValueError(f"Invalid {key} correction")
            dims = changes.get("dimensions_m", {})
            if not isinstance(dims, dict) or set(dims) - (set("xyz") if is_object else set("xy")):
                raise ValueError("Invalid dimension axes")
            for value in dims.values():
                if not finite(value) or not 0 < value <= 100:
                    raise ValueError("Corrected dimensions must be finite, greater than 0 and at most 100 meters")
        if doc["schema_version"] == 2:
            validate_observations(doc["reference_observations"], self.elements, self.manifest)
            reviews = doc["reviews"]
            if (not isinstance(reviews, dict) or len(reviews) > 1000
                    or any(not re.fullmatch(r"[a-f0-9]{24}", key)
                           or value not in ("confirmed", "corrected", "excluded", "skipped")
                           for key, value in reviews.items())):
                raise ValueError("Invalid review resolutions")
        return doc

    def upgrade(self, doc):
        self.validate_document(doc)
        doc = copy.deepcopy(doc)
        if doc["schema_version"] == 1:
            doc.update(schema_version=2, reference_observations=copy.deepcopy(self.observations), reviews={})
        return doc

    def project(self, matrix, point):
        x, _, z = transform_point(matrix, point)
        c, s = math.cos(self.rotation), math.sin(self.rotation)
        return [c*x+s*z, -s*x+c*z]

    def resolved(self, base, edit):
        raw, changes = base["raw"], edit["overrides"]
        kind = base["source"]["collection"]
        category = enum_name(raw.get("category"))
        raw_dims = raw.get("dimensions", [])
        dims = [v if finite(v) and v > 0 else None for v in raw_dims] if isinstance(raw_dims, list) and len(raw_dims) == 3 else [None]*3
        original_dims = dims[:]
        for axis, value in changes.get("dimensions_m", {}).items():
            dims["xyz".index(axis)] = value
        warnings = []
        required = dims if kind == "objects" else dims[:2]
        if any(v is None for v in required):
            warnings.append("Missing dimensions; footprint unavailable until corrected")
        if category is None:
            warnings.append("RoomPlan category is missing")
        if raw.get("curve") is not None:
            warnings.append("Curved surface shown as a straight chord approximation")
        matrix = raw.get("transform")
        geometry, center = None, None
        if not vector(matrix, 16):
            warnings.append("Missing or invalid transform; not placed on plan")
        else:
            center = self.project(matrix, [0, 0, 0])
            if all(v is not None for v in required):
                x, y, z = dims
                if kind == "objects":
                    points = [self.project(matrix, [a*x/2, b*y/2, c*z/2])
                              for a in (-1, 1) for b in (-1, 1) for c in (-1, 1)]
                    geometry = {"type": "polygon", "points": hull(points)}
                elif kind == "floors":
                    corners = raw.get("polygonCorners")
                    if isinstance(corners, list) and len(corners) >= 3 and all(vector(p, 3) for p in corners):
                        sx = x / original_dims[0] if original_dims[0] else 1
                        sy = y / original_dims[1] if original_dims[1] else 1
                        points = [self.project(matrix, [p[0]*sx, p[1]*sy, p[2]]) for p in corners]
                    else:
                        points = [self.project(matrix, p) for p in
                                  ([-x/2, -y/2, 0], [x/2, -y/2, 0], [x/2, y/2, 0], [-x/2, y/2, 0])]
                        warnings.append("Floor polygon missing; displayed rectangle is a bounding-box estimate")
                    geometry = {"type": "polygon", "points": points}
                else:
                    geometry = {"type": "line", "points": [self.project(matrix, [-x/2, 0, 0]), self.project(matrix, [x/2, 0, 0])]}
            if geometry is None:
                geometry = {"type": "marker", "points": [center]}
        if kind != "objects" and changes.get("dimensions_m"):
            warnings.append("Surface resized about its center; connected elements are not moved")
        result = {"source": base["source"], "code": base["code"], "kind": kind,
                "label": changes.get("label", category or "Unknown"),
                "category": changes.get("category", category), "original_category": category,
                "confidence": enum_name(raw.get("confidence")),
                "dimensions_m": dims, "original_dimensions_m": original_dims,
                "dimension_status": ["user correction (unverified)" if axis in changes.get("dimensions_m", {})
                                     else "RoomPlan estimate" if value is not None else "not supplied"
                                     for axis, value in zip("xyz", dims)],
                "parent_identifier": raw.get("parentIdentifier"),
                "decision": edit["decision"], "overrides": changes,
                "geometry": geometry, "center": center, "warnings": warnings}
        enrich(result, raw, dims, original_dims)
        return result

    def payload(self, doc, filename=None):
        doc = self.upgrade(doc)
        elements = [self.resolved(base, edit) for base, edit in zip(self.elements, doc["elements"])]
        for e in elements:
            observation = doc["reference_observations"].get(e["source"]["identifier"])
            e["color"] = (dict(e["overrides"]["color"], certainty="user choice, not observed") if "color" in e["overrides"]
                          else dict(observation, origin="reference", certainty="observed patch; approximate whole-element color") if observation
                          else {"hex": "#bec7c6" if e["kind"] == "objects" else "#d8ddd9", "origin": "unknown", "certainty": "unknown; neutral hatched placeholder"})
            e["reference_observation"] = observation
        points = [p for e in elements if e["geometry"] for p in e["geometry"]["points"]]
        bounds = [min(p[0] for p in points), min(p[1] for p in points),
                  max(p[0] for p in points), max(p[1] for p in points)] if points else [-1, -1, 1, 1]
        return {"document": doc, "elements": elements, "bounds": bounds,
                "review_queue": review_queue(elements, doc["reviews"]),
                "reference": dict(read_object(self.scan / "Reference.json"), url="/reference.jpg") if self.manifest["rgb_reference_available"] else None,
                "filename": filename, "output_directory": str(self.output),
                "scan_directory": str(self.scan), "versions": self.versions(),
                "captured_at": self.manifest.get("captured_at"),
                "missing_collections": [k for k in COLLECTIONS if k not in self.room]}

    def versions(self):
        return sorted(p.name for p in self.output.glob("revision-*.design.json")
                      if re.fullmatch(r"revision-\d{4,}\.design\.json", p.name))

    def version_path(self, name):
        if not isinstance(name, str) or not re.fullmatch(r"revision-\d{4,}\.design\.json", name):
            raise ValueError("Choose a saved revision filename")
        path = self.output / name
        if path.is_symlink():
            raise ValueError("Saved revisions cannot be symlinks")
        return path

    def load(self, path):
        self.verify()
        doc = read_object(Path(path))
        self.validate_document(doc)
        return doc

    def save(self, document, base_filename):
        self.verify()
        doc = self.upgrade(document)
        parent = None
        if base_filename is not None:
            path = self.version_path(base_filename)
            previous = self.load(path)
            if previous["revision"] != doc["revision"]:
                raise ValueError("Base revision does not match the loaded file")
            parent = {"file": path.name, "sha256": file_hash(path)}
        elif doc["revision"] != 0:
            raise ValueError("A saved document needs its base revision")
        self.output.mkdir(parents=True, exist_ok=True)
        revision = max((int(n.split('-')[1].split('.')[0]) for n in self.versions()), default=0) + 1
        doc.update(saved_at=dt.datetime.now(dt.timezone.utc).isoformat(), parent=parent)
        # Atomic publication with no overwrites, even with two editor processes.
        while True:
            doc["revision"] = revision
            name = f"revision-{revision:04d}.design.json"
            fd, temporary = tempfile.mkstemp(prefix=".saving-", dir=self.output)
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as stream:
                    json.dump(doc, stream, indent=2, allow_nan=False)
                    stream.write("\n")
                    stream.flush()
                    os.fsync(stream.fileno())
                try:
                    os.link(temporary, self.output / name)
                except FileExistsError:
                    revision += 1
                    continue
                return doc, name
            finally:
                os.unlink(temporary)
