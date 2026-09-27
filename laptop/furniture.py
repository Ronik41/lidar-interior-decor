"""Local furniture proposals in the original scan frame; conservative estimates only."""
import copy
import hashlib
import json
import math
import re
from pathlib import Path

from review_geometry import valid_vector, point, intersection, polygon_area, height_interval
from scene_geometry import point as world_point, rectangle

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


def validate_proposals(proposals, floors, source_ids, scene=None):
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
        a=p['anchor']
        if not isinstance(a,dict):raise ValueError('Invalid anchor')
        kind=model['anchor_type']
        if kind=='floor':
            if set(a)!={'floor_identifier','x_m','z_m','yaw_degrees'}:raise ValueError('Invalid floor anchor')
            if not any(f['identifier']==a['floor_identifier'] for f in floors):raise ValueError('Proposal requires an original horizontal RoomPlan floor')
            numbers=[a['x_m'],a['z_m'],a['yaw_degrees']]
        elif kind=='wall':
            if set(a)-{'mount_offset_m'}!={'type','wall_identifier','u_m','bottom_m','side','roll_degrees'} or a['type']!='wall' or type(a['side']) is not int or a['side'] not in (-1,1):raise ValueError('Invalid wall anchor')
            if not valid_vector([a.get('mount_offset_m',.014)],1) or not .005<=a.get('mount_offset_m',.014)<=.15:raise ValueError('Wall mount offset must be 0.005–0.15 m')
            numbers=[a['u_m'],a['bottom_m'],a['roll_degrees']]
        elif a.get('type')=='tabletop':
            if set(a)!={'type','support_identifier','x_m','z_m','yaw_degrees'}:raise ValueError('Invalid tabletop anchor')
            numbers=[a['x_m'],a['z_m'],a['yaw_degrees']]
        elif a.get('type')=='confirmed_surface':
            if set(a)!={'type','floor_identifier','x_m','z_m','yaw_degrees','height_m','confirmed'} or a['confirmed'] is not True:raise ValueError('Confirm the support surface height explicitly')
            if not any(f['identifier']==a['floor_identifier'] for f in floors):raise ValueError('Unknown floor for confirmed surface')
            if not valid_vector([a['height_m']],1) or not .15<=a['height_m']<=2.5:raise ValueError('Surface height must be 0.15–2.5 m above floor')
            numbers=[a['x_m'],a['z_m'],a['yaw_degrees']]
        else:raise ValueError('Fruit requires a known table or an explicitly confirmed surface height')
        if not valid_vector(numbers,3) or any(abs(v)>100 for v in numbers[:2]) or abs(numbers[2])>360:raise ValueError('Placement must be finite; coordinates within 100 m, rotation within ±360°')
    for p in proposals:
        resolve_anchor(p, proposals, floors, scene)


def resolve_anchor(p, proposals, floors, scene):
    a=p['anchor'];model=MODELS[p['asset_id']];w,h,d=model['dimensions_m']
    kind=model['anchor_type']
    if kind=='wall':
        wall=next((v for v in (scene or {}).get('walls',[]) if v['id']==a['wall_identifier']),None)
        if wall is None:raise ValueError('Wall anchor must belong to this scene')
        roll=math.radians(a['roll_degrees']);ew=abs(w*math.cos(roll))+abs(h*math.sin(roll));eh=abs(h*math.cos(roll))+abs(w*math.sin(roll))
        cx,cy=a['u_m'],a['bottom_m']-wall['height']/2+h/2
        box=[cx-ew/2,cy-eh/2,cx+ew/2,cy+eh/2];margin=.08
        if box[0]<-wall['width']/2+margin or box[2]>wall['width']/2-margin or box[1]<-wall['height']/2+margin or box[3]>wall['height']/2-margin:raise ValueError('Keep the whole painting within its wall segment (8 cm margin)')
        for hole in wall['holes']:
            x0,y0,x1,y1=hole['rect']
            if box[0]<x1+margin and box[2]>x0-margin and box[1]<y1+margin and box[3]>y0-margin:raise ValueError('Painting overlaps or is too close to a door, window or opening')
        m=wall['transform'];position=world_point(m,[cx,a['bottom_m']-wall['height']/2,a['side']*(d/2+a.get('mount_offset_m',.014))])
        yaw=math.degrees(math.atan2(m[8],m[10]))+(180 if a['side']==-1 else 0)
        return position,yaw,wall['code']
    if a.get('type')=='tabletop':
        support=next((v for v in proposals if v['id']==a['support_identifier']),None)
        if not support or MODELS.get(support['asset_id'],{}).get('anchor_type')!='floor' or 'surface' not in MODELS[support['asset_id']]:raise ValueError('Choose an existing authored table surface; remove its fruit before deleting the table')
        surface=MODELS[support['asset_id']]['surface']
        footprint=rectangle(a['x_m'],a['z_m'],w,d,a['yaw_degrees'])
        if any(abs(x)>surface['width_m']/2 or abs(z)>surface['depth_m']/2 for x,z in footprint):raise ValueError('Keep the whole fruit bowl on the table surface')
        pos,yaw,code=resolve_anchor(support,proposals,floors,scene);r=math.radians(yaw)
        return [pos[0]+math.cos(r)*a['x_m']+math.sin(r)*a['z_m'],pos[1]+surface['height_m'],pos[2]-math.sin(r)*a['x_m']+math.cos(r)*a['z_m']],yaw+a['yaw_degrees'],'table '+support['id'][-8:]
    floor=next(f for f in floors if f['identifier']==a['floor_identifier'])
    y=floor_y(floor,a['x_m'],a['z_m'])+a.get('height_m',0)
    if a.get('type')=='confirmed_surface':
        poly=[[world_point(floor['transform'],v)[i] for i in (0,2)] for v in floor['polygon']]
        if not contained(rectangle(a['x_m'],a['z_m'],w,d,a['yaw_degrees']),poly):raise ValueError('Confirmed surface must lie within the floor boundary')
    return [a['x_m'],y,a['z_m']],a['yaw_degrees'],floor['code']+(' · confirmed surface' if a.get('type') else '')


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


def resolve_proposals(proposals, floors, original_elements, rotation, scene=None):
    result = []
    rc, rs = math.cos(rotation), math.sin(rotation)
    def project(x,z):
        return [rc*x+rs*z, -rs*x+rc*z]
    for index, p in enumerate(proposals):
        a, model = p['anchor'], MODELS[p['asset_id']]
        position,yaw_degrees,anchor_code=resolve_anchor(p,proposals,floors,scene)
        x,y,z=position
        floor=next((f for f in floors if f['identifier']==a.get('floor_identifier')),None)
        w,h,d = model['dimensions_m']
        roll=math.radians(a.get('roll_degrees',0));cw=abs(w*math.cos(roll))+abs(h*math.sin(roll));ch=abs(h*math.cos(roll))+abs(w*math.sin(roll))
        yaw = math.radians(yaw_degrees); c,s = math.cos(yaw),math.sin(yaw)
        footprint = [project(position[0]+c*x+s*z, position[2]-s*x+c*z)
                     for x,z in [(-cw/2,-d/2),(cw/2,-d/2),(cw/2,d/2),(-cw/2,d/2)]]
        warnings = []
        if floor and not contained(footprint, floor['plan_points']):
            warnings.append('Footprint extends outside the estimated RoomPlan floor.')
        for e in original_elements:
            if not e['spatial'] or not e['geometry']:
                continue
            if e['kind'] == 'objects' and e['geometry']['type'] == 'polygon' and all(v is not None for v in e['dimensions_m']):
                lo,hi = height_interval(e)
                area = polygon_area(intersection(footprint, e['geometry']['points']))
                if area > .0001 and min(y+h,hi)-max(y,lo) > .01:
                    warnings.append(f"Estimated overlap with detected {e['code']} · {e['label']} ({area:.2f} m²). Captured item remains in the splat.")
            if e['kind'] == 'walls' and e['geometry']['type'] == 'line' and e['source']['identifier']!=a.get('wall_identifier'):
                m=e['spatial']['transform']; height=e['dimensions_m'][1]
                if height and min(y+h,m[13]+height/2)>max(y,m[13]-height/2) and near_wall(footprint,*e['geometry']['points']):
                    warnings.append(f"Estimated wall overlap / proximity: {e['code']} (6 cm plane buffer; openings not subtracted).")
        result.append(dict(copy.deepcopy(p), model=copy.deepcopy(model), code=f'P{index+1:02d}',
                           position_m=position, yaw_degrees=yaw_degrees, floor_code=anchor_code,
                           collision={'points':rectangle(x,z,cw,d,yaw_degrees),'bottom':y+(h-ch)/2,'top':y+(h+ch)/2},
                           center=project(x,z), geometry={'type':'polygon','points':footprint}, warnings=warnings))
    for i,a in enumerate(result):
        for b in result[i+1:]:
            if min(a['position_m'][1]+a['dimensions_m'][1],b['position_m'][1]+b['dimensions_m'][1])-max(a['position_m'][1],b['position_m'][1])>.01 and polygon_area(intersection(a['geometry']['points'],b['geometry']['points'])) > .0001:
                a['warnings'].append(f"Estimated overlap with proposal {b['code']}.")
                b['warnings'].append(f"Estimated overlap with proposal {a['code']}.")
    return result
