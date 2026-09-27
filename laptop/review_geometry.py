"""3D evidence and selective review. No inferred accuracy or furniture geometry."""
import hashlib
import json
import math
import re


def valid_vector(value, n):
    return isinstance(value, list) and len(value) == n and all(type(x) in (int, float) and math.isfinite(x) for x in value)


def point(matrix, local):
    return [sum(matrix[c*4+r]*local[c] for c in range(3))+matrix[12+r] for r in range(3)]


def local_point(matrix, world):
    # RoomPlan transforms are rigid, column-major local-to-world matrices.
    delta = [world[i]-matrix[12+i] for i in range(3)]
    return [sum(matrix[c*4+r]*delta[r] for r in range(3)) for c in range(3)]


def enrich(element, raw, dims, original):
    matrix = raw.get("transform")
    element["spatial"] = None
    element["excluded"] = element["decision"] == "remove" or element["overrides"].get("excluded", False)
    element["measurement_accuracy"] = "unverified; category confidence is not measurement accuracy"
    if not valid_vector(matrix, 16):
        return
    polygon = None
    if element["kind"] == "floors" and all(d is not None for d in dims[:2]):
        corners = raw.get("polygonCorners")
        if isinstance(corners, list) and len(corners) >= 3 and all(valid_vector(p, 3) for p in corners):
            sx, sy = (dims[i]/original[i] if original[i] else 1 for i in range(2))
            polygon = [[p[0]*sx, p[1]*sy, p[2]] for p in corners]
        else:
            x, y = dims[:2]
            polygon = [[-x/2,-y/2,0],[x/2,-y/2,0],[x/2,y/2,0],[-x/2,y/2,0]]
    element["spatial"] = {"transform": matrix, "polygon": polygon,
                          "is_open": raw.get("category", {}).get("door", {}).get("isOpen") if isinstance(raw.get("category"), dict) else None}


def validate_observations(observations, elements, manifest):
    ids = {e["source"]["identifier"] for e in elements}
    if not isinstance(observations, dict) or set(observations)-ids:
        raise ValueError("Unknown reference color element")
    for item in observations.values():
        if not isinstance(item, dict) or set(item) != {"hex", "reference_sha256", "sample_uv", "note"}:
            raise ValueError("Invalid reference color evidence")
        if (not re.fullmatch(r"#[0-9a-fA-F]{6}", str(item["hex"]))
                or not manifest.get("rgb_reference_available")
                or item["reference_sha256"] != manifest["sha256"].get("Reference.jpg")
                or not valid_vector(item["sample_uv"], 2) or not all(0 <= v <= 1 for v in item["sample_uv"])
                or not isinstance(item["note"], str) or not 1 <= len(item["note"]) <= 1000):
            raise ValueError("Reference color must link to a verified photo and sample")


def polygon_area(p):
    return abs(sum(p[i][0]*p[(i+1)%len(p)][1]-p[(i+1)%len(p)][0]*p[i][1] for i in range(len(p)))/2) if len(p) > 2 else 0


def intersection(a, b):
    """Convex footprint clipping, avoiding false overlap from world AABBs."""
    subject = a[:]
    signed = sum(b[i][0]*b[(i+1)%len(b)][1]-b[(i+1)%len(b)][0]*b[i][1] for i in range(len(b)))
    direction = 1 if signed >= 0 else -1
    for i, edge in enumerate(b):
        end = b[(i+1)%len(b)]
        def distance(p):
            return direction*((end[0]-edge[0])*(p[1]-edge[1])-(end[1]-edge[1])*(p[0]-edge[0]))
        output = []
        if not subject:
            break
        previous, pd = subject[-1], distance(subject[-1])
        for current in subject:
            cd = distance(current)
            if (cd >= 0) != (pd >= 0):
                t = pd/(pd-cd)
                output.append([previous[j]+t*(current[j]-previous[j]) for j in range(2)])
            if cd >= 0:
                output.append(current)
            previous, pd = current, cd
        subject = output
    return subject


def height_interval(e):
    m, dims = e["spatial"]["transform"], e["dimensions_m"]
    extent = sum(abs(m[c*4+1])*dims[c]/2 for c in range(3))
    return m[13]-extent, m[13]+extent


def review_queue(elements, resolutions):
    issues = []
    def add(kind, members, title, detail, priority):
        # Changes to either object's geometry re-open an acknowledged overlap.
        signature = [kind, [(e["source"]["identifier"], e["dimensions_m"], e["category"]) for e in members]]
        key = hashlib.sha256(json.dumps(signature, sort_keys=True).encode()).hexdigest()[:24]
        issues.append({"id": key, "kind": kind, "elements": [e["source"]["identifier"] for e in members],
                       "title": title, "detail": detail, "priority": priority,
                       "status": resolutions.get(key, "pending")})
    active = [e for e in elements if not e["excluded"]]
    for e in active:
        if e["kind"] in ("doors", "openings", "windows") and e["confidence"] != "high":
            add("uncertain-aperture", [e], f'{e["code"]} · uncertain {e["category"]}',
                f'RoomPlan category confidence is {e["confidence"] or "missing"}. Check that this is a real passage or window. Dimensions remain unverified.', 0)
        elif e["confidence"] in ("low", None):
            add("category", [e], f'{e["code"]} · check {e["category"] or "category"}',
                f'RoomPlan category confidence is {e["confidence"] or "missing"}. Confirm the type, correct its label/category, or exclude it.', 2)
        if e["kind"] in ("doors", "openings", "windows"):
            parent = next((p for p in active if p["source"]["identifier"] == e["parent_identifier"] and p["kind"] == "walls"), None)
            if not parent or not parent["spatial"] or not e["spatial"]:
                add("aperture-parent", [e], f'{e["code"]} · missing parent wall', "No usable parent wall. Aperture shown separately; no wall cut is inferred.", 0)
            elif all(d is not None for d in e["dimensions_m"][:2]+parent["dimensions_m"][:2]):
                corners = [local_point(parent["spatial"]["transform"], point(e["spatial"]["transform"], [a*e["dimensions_m"][0]/2,b*e["dimensions_m"][1]/2,0])) for a in (-1,1) for b in (-1,1)]
                if any(abs(p[2]) > .15 or abs(p[0]) > parent["dimensions_m"][0]/2+.10 or abs(p[1]) > parent["dimensions_m"][1]/2+.10 for p in corners):
                    add("aperture-fit", [e, parent], f'{e["code"]} · aperture / wall conflict', "Estimated aperture extends beyond or away from its parent wall. Review both estimates; surface edits do not move connected elements.", 0)
    objects = [e for e in active if e["kind"] == "objects" and e["spatial"] and e["geometry"] and e["geometry"]["type"] == "polygon"]
    for i, a in enumerate(objects):
        for b in objects[i+1:]:
            # A detected parent/child can be a chair tucked under a table, or a sink in a cabinet.
            if a["parent_identifier"] == b["source"]["identifier"] or b["parent_identifier"] == a["source"]["identifier"]:
                continue
            ap, bp = a["geometry"]["points"], b["geometry"]["points"]
            area = polygon_area(intersection(ap, bp))
            ah, bh = height_interval(a), height_interval(b)
            vertical = min(ah[1],bh[1])-max(ah[0],bh[0])
            ratio = area/max(min(polygon_area(ap),polygon_area(bp)), 1e-9)
            if area > .025 and ratio > .15 and vertical > .08:
                add("overlap", [a,b], f'{a["code"]} + {b["code"]} · overlapping estimates',
                    f'Bounding boxes share {area:.2f} m² of footprint and {vertical:.2f} m of vertical extent. This can be duplicate detection or an ordinary arrangement; it is not proof of a collision.', 1)
    return sorted(issues, key=lambda q: (q["priority"], q["title"]))
