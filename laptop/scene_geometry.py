"""RoomPlan adapter: scene coordinates in metres, independent of render/review geometry."""
import copy
import math
from review_geometry import valid_vector, height_interval


def point(m, p):
    return [sum(m[c*4+r]*p[c] for c in range(3))+m[12+r] for r in range(3)]


def local(m, p):
    return [sum(m[c*4+r]*(p[r]-m[12+r]) for r in range(3)) for c in range(3)]


def rectangle(x, z, w, d, yaw):
    c,s=math.cos(math.radians(yaw)),math.sin(math.radians(yaw))
    return [[x+c*u+s*v,z-s*u+c*v] for u,v in [(-w/2,-d/2),(w/2,-d/2),(w/2,d/2),(-w/2,d/2)]]


def build_scene(scene_id, elements, floors, rotation):
    """Only this adapter knows RoomPlan's element schema. No room-specific identifiers."""
    scene={'schema_version':1,'id':scene_id,'units':'meters','up_axis':'Y',
           'scene_to_display':[math.cos(rotation),0,-math.sin(rotation),0,0,1,0,0,math.sin(rotation),0,math.cos(rotation),0,0,0,0,1],
           'floors':[], 'walls':[], 'objects':[], 'warnings':[]}
    for f in floors:
        source=next(e for e in elements if e['source']['identifier']==f['identifier'])
        if any('Floor polygon missing' in warning for warning in source['warnings']):
            scene['warnings'].append('No measured boundary for '+f['code']+'; bounding rectangle excluded from walking and new placement')
            continue
        scene['floors'].append(dict(copy.deepcopy(f),points=[[p[0],p[2]] for p in [point(f['transform'],v) for v in f['polygon']]]))
    for e in elements:
        if not e['spatial']:continue
        m=e['spatial']['transform'];w,h,d=e['dimensions_m']
        if e['kind']=='walls' and w and h and abs(m[5])>.98:
            holes=[]
            for child in elements:
                if child['kind'] not in ('doors','windows','openings') or not child['spatial'] or not all(child['dimensions_m'][:2]):continue
                cm=child['spatial']['transform'];cw,ch=child['dimensions_m'][:2]
                pts=[local(m,point(cm,[x,y,0])) for x in (-cw/2,cw/2) for y in (-ch/2,ch/2)]
                # Parent topology plus a geometric check; also handle missing parent IDs.
                if child['parent_identifier'] not in (None,e['source']['identifier']):continue
                if max(abs(p[2]) for p in pts)>.15:continue
                x0,x1=max(-w/2,min(p[0] for p in pts)),min(w/2,max(p[0] for p in pts))
                y0,y1=max(-h/2,min(p[1] for p in pts)),min(h/2,max(p[1] for p in pts))
                if x1<=x0 or y1<=y0:continue
                holes.append({'id':child['source']['identifier'],'kind':child['kind'],'rect':[x0,y0,x1,y1],
                              'passable':child['kind']=='openings' or (child['kind']=='doors' and child['spatial'].get('is_open') is True)})
            scene['walls'].append({'id':e['source']['identifier'],'code':e['code'],'transform':m,'width':w,'height':h,'holes':holes})
        if e['kind']=='objects' and all(v is not None for v in (w,h,d)):
            lo,hi=height_interval(e)
            yaw=math.degrees(math.atan2(-m[2],m[0]))
            upright=abs(m[5])>.98
            # High/medium confidence upright, solid, low enough to meet the walker body.
            reliable=e['confidence'] in ('high','medium') and upright and min(w,d)>.15 and h>.10
            scene['objects'].append({'id':e['source']['identifier'],'code':e['code'],'label':e['label'],
                'confidence':e['confidence'],'reliable':reliable,'points':rectangle(m[12],m[14],w,d,yaw),
                'box':{'x_m':m[12],'z_m':m[14],'width_m':w,'depth_m':d,'yaw_degrees':yaw},'bottom':lo,'top':hi})
    return scene


def validate_navigation(overrides, scene):
    if not isinstance(overrides,dict) or set(overrides)-{o['id'] for o in scene['objects']}:
        raise ValueError('Obstacle corrections must belong to this scene')
    for value in overrides.values():
        if not isinstance(value,dict) or set(value)-{'enabled','box'} or type(value.get('enabled')) is not bool:
            raise ValueError('Invalid obstacle correction')
        if 'box' in value:
            box=value['box']
            keys={'x_m','z_m','width_m','depth_m','yaw_degrees'}
            if not isinstance(box,dict) or set(box)!=keys or not valid_vector(list(box.values()),5):raise ValueError('Invalid obstacle box')
            if not (0<box['width_m']<=100 and 0<box['depth_m']<=100 and abs(box['x_m'])<=100 and abs(box['z_m'])<=100 and abs(box['yaw_degrees'])<=360):raise ValueError('Invalid obstacle dimensions')
