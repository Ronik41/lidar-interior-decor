"""Local furniture proposals in the original scan frame; conservative estimates only."""
import copy
import hashlib
import json
import math
import re
from pathlib import Path

from review_geometry import valid_vector, point, intersection, polygon_area, height_interval

MODEL_ROOT = Path(__file__).with_name('editor') / 'models'
CATALOG = json.loads((MODEL_ROOT / 'catalog.json').read_text())
MODELS = {item['id']: item for item in CATALOG}


def verify_models():
    for item in CATALOG:
        path = MODEL_ROOT / item['model_url'].removeprefix('/models/')
        if hashlib.sha256(path.read_bytes()).hexdigest() != item['sha256']:
            raise ValueError('Local furniture asset checksum mismatch: ' + item['name'])


def floor_anchors(elements):
    """Anchor to original RoomPlan floor, unaffected by review exclusions/resizing."""
    floors = []
    for e in elements:
        if e['kind'] != 'floors' or not e['spatial'] or not e['spatial']['polygon']:
            continue
        m = e['spatial']['transform']
        # Refuse non-horizontal/degenerate estimates rather than invent a floor.
        if abs(m[9]) < .98:
            continue
        floors.append({'identifier': e['source']['identifier'], 'code': e['code'],
                       'transform': m, 'polygon': e['spatial']['polygon'],
                       'plan_points': e['geometry']['points']})
    return floors


def floor_y(floor, x, z):
    m = floor['transform']
    return m[13] - (m[8]*(x-m[12]) + m[10]*(z-m[14])) / m[9]


def validate_proposals(proposals, floors, source_ids):
    if not isinstance(proposals, list) or len(proposals) > 100:
        raise ValueError('Expected at most 100 furniture proposals')
    ids = set(source_ids)
    for p in proposals:
        if not isinstance(p, dict) or set(p) != {'id', 'asset_id', 'asset_sha256', 'dimensions_m', 'anchor'}:
            raise ValueError('Invalid furniture proposal fields')
        if not isinstance(p['id'], str) or not re.fullmatch(r'proposal-[a-f0-9-]{36}', p['id']) or p['id'] in ids:
            raise ValueError('Furniture proposals need unique identifiers')
        ids.add(p['id'])
        model = MODELS.get(p['asset_id']) if isinstance(p['asset_id'], str) else None
        if not model or p['asset_sha256'] != model['sha256'] or p['dimensions_m'] != model['dimensions_m']:
            raise ValueError('Furniture identity, dimensions or asset checksum mismatch')
        a = p['anchor']
        if not isinstance(a, dict) or set(a) != {'floor_identifier', 'x_m', 'z_m', 'yaw_degrees'}:
            raise ValueError('Invalid floor anchor')
        if not any(f['identifier'] == a['floor_identifier'] for f in floors):
            raise ValueError('Proposal requires an original horizontal RoomPlan floor')
        if not valid_vector([a['x_m'], a['z_m'], a['yaw_degrees']], 3) or any(abs(a[k]) > 100 for k in ('x_m', 'z_m')) or abs(a['yaw_degrees']) > 360:
            raise ValueError('Placement must be finite; X/Z within 100 m, heading within ±360°')


def segment_distance(p, a, b):
    dx, dy = b[0]-a[0], b[1]-a[1]
    t = max(0, min(1, ((p[0]-a[0])*dx+(p[1]-a[1])*dy) / max(dx*dx+dy*dy, 1e-20)))
    return math.hypot(p[0]-a[0]-t*dx, p[1]-a[1]-t*dy)


def cross(a, b, p):
    return (b[0]-a[0])*(p[1]-a[1]) - (b[1]-a[1])*(p[0]-a[0])


def crosses(a, b, c, d):
    return cross(a,b,c)*cross(a,b,d) < -1e-12 and cross(c,d,a)*cross(c,d,b) < -1e-12


def edges(poly):
    return zip(poly, poly[1:] + poly[:1])


def inside(p, poly):
    if any(segment_distance(p, a, b) < 1e-7 for a,b in edges(poly)):
        return True
    odd = False
    for a,b in edges(poly):
        if (a[1] > p[1]) != (b[1] > p[1]) and p[0] < (b[0]-a[0])*(p[1]-a[1])/(b[1]-a[1])+a[0]:
            odd = not odd
    return odd


def contained(footprint, floor):
    return all(inside(p, floor) for p in footprint) and not any(crosses(a,b,c,d) for a,b in edges(footprint) for c,d in edges(floor))


def near_wall(poly, a, b):
    return (inside(a, poly) or inside(b, poly)
            or any(crosses(a,b,c,d) for c,d in edges(poly))
            or min([segment_distance(p,a,b) for p in poly]
                   + [segment_distance(p,c,d) for p in (a,b) for c,d in edges(poly)]) <= .06)


def resolve_proposals(proposals, floors, original_elements, rotation):
    result = []
    rc, rs = math.cos(rotation), math.sin(rotation)
    def project(x,z):
        return [rc*x+rs*z, -rs*x+rc*z]
    for index, p in enumerate(proposals):
        a, model = p['anchor'], MODELS[p['asset_id']]
        floor = next(f for f in floors if f['identifier'] == a['floor_identifier'])
        y = floor_y(floor, a['x_m'], a['z_m'])
        w,h,d = model['dimensions_m']
        yaw = math.radians(a['yaw_degrees']); c,s = math.cos(yaw),math.sin(yaw)
        footprint = [project(a['x_m']+c*x+s*z, a['z_m']-s*x+c*z)
                     for x,z in [(-w/2,-d/2),(w/2,-d/2),(w/2,d/2),(-w/2,d/2)]]
        warnings = []
        if not contained(footprint, floor['plan_points']):
            warnings.append('Footprint extends outside the estimated RoomPlan floor.')
        for e in original_elements:
            if not e['spatial'] or not e['geometry']:
                continue
            if e['kind'] == 'objects' and e['geometry']['type'] == 'polygon' and all(v is not None for v in e['dimensions_m']):
                lo,hi = height_interval(e)
                area = polygon_area(intersection(footprint, e['geometry']['points']))
                if area > .0001 and min(y+h,hi)-max(y,lo) > .01:
                    warnings.append(f"Estimated overlap with detected {e['code']} · {e['label']} ({area:.2f} m²). Captured item remains in the splat.")
            if e['kind'] == 'walls' and e['geometry']['type'] == 'line':
                m=e['spatial']['transform']; height=e['dimensions_m'][1]
                if height and min(y+h,m[13]+height/2)>max(y,m[13]-height/2) and near_wall(footprint,*e['geometry']['points']):
                    warnings.append(f"Estimated wall overlap / proximity: {e['code']} (6 cm plane buffer; openings not subtracted).")
        result.append(dict(copy.deepcopy(p), model=copy.deepcopy(model), code=f'P{index+1:02d}',
                           position_m=[a['x_m'], y, a['z_m']], floor_code=floor['code'],
                           center=project(a['x_m'],a['z_m']), geometry={'type':'polygon','points':footprint}, warnings=warnings))
    for i,a in enumerate(result):
        for b in result[i+1:]:
            if polygon_area(intersection(a['geometry']['points'],b['geometry']['points'])) > .0001:
                a['warnings'].append(f"Estimated overlap with proposal {b['code']}.")
                b['warnings'].append(f"Estimated overlap with proposal {a['code']}.")
    return result
