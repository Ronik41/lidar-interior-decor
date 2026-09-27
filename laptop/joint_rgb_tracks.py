#!/usr/bin/env python3
"""One fixed, train-only feature-track connectivity gate before any pose fitting.

No retry, threshold relaxation, camera optimization, or held-out image access.
Private observations and failures are retained for inspection.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import itertools
import json
from pathlib import Path
import subprocess
import sys
import time

import cv2
import numpy as np
from PIL import Image, ImageDraw
from assess_coverage import load_frames, matrix
from reconstruct_room import split_frames, read_depth, extrinsic
from import_scan import validate
from capture_selection import load_selection, selected_split


PROTOCOL = dict(
    image_width=960, sift_features=2000, ratio=.75, seed=42,
    temporal_offsets=[1, 2, 4, 8], revisit_min_gap_frames=20,
    revisit_max_distance_m=2., revisit_min_view_dot=.5, revisit_neighbors=6,
    fundamental_threshold_px=1.5, fundamental_confidence=.999, fundamental_iterations=10000,
    min_pair_inliers=30, min_pair_inlier_fraction=.5, min_pair_grid_cells=6,
    min_pair_hull_fraction=.08, min_track_views=3, min_track_depth_views=2,
    min_track_baseline_m=.03, max_track_world_median_m=.06, max_track_world_p90_m=.12,
    max_track_reprojection_median_px=8., max_track_reprojection_p90_px=20.,
    max_bundle_tracks=8000, balanced_tracks_per_camera=30,
    min_edge_shared_tracks=15, min_main_component_fraction=.95,
    min_camera_track_observations=30, min_supported_camera_fraction=.95,
    min_main_component_revisit_edges=3, max_graph_bridges=0,
    temporal_block_seconds=5., min_spatial_cell_frames=3, spatial_cell_m=1.,
    tracking_timeout_seconds=600, optimization_timeout_seconds=1200,
    reconstruction_settings='Existing mesh defaults; 6000 steps / 960px / SH2 / 350000 splats / seed 42',
    acceptance='All three preselected detail views visibly clearer; mean SSIM nondecreasing; median held-out depth residual <= baseline +0.02m',
    detail_views=['Frame-0303.jpg', 'Frame-0308.jpg', 'Frame-0333.jpg'],
)


def components(n, edges):
    adjacency = [set() for _ in range(n)]
    for a, b in edges:
        adjacency[a].add(b); adjacency[b].add(a)
    result = []; unseen = set(range(n))
    while unseen:
        todo = [min(unseen)]; part = set()
        while todo:
            node = todo.pop()
            if node in part: continue
            part.add(node); unseen.discard(node); todo.extend(adjacency[node] - part)
        result.append(sorted(part))
    return sorted(result, key=len, reverse=True), adjacency


def bridges(adjacency, members):
    order = {}; low = {}; result = []
    def visit(node, parent=None):
        order[node] = low[node] = len(order)
        for nxt in sorted(adjacency[node]):
            if nxt == parent or nxt not in members: continue
            if nxt in order: low[node] = min(low[node], order[nxt])
            else:
                visit(nxt, node); low[node] = min(low[node], low[nxt])
                if low[nxt] > order[node]: result.append([node, nxt])
    if members: visit(min(members))
    return result


def track_graph(tracks, frames, positions):
    counts = Counter(); observations = np.zeros(len(frames), int)
    for tr in tracks:
        cams = sorted(c for c, _ in tr['nodes'])
        observations[cams] += 1
        counts.update(itertools.combinations(cams, 2))
    edges = {pair: count for pair, count in counts.items() if count >= PROTOCOL['min_edge_shared_tracks']}
    groups, adjacency = components(len(frames), edges); main = set(groups[0])
    temporal = np.array([int((f['timestamp_seconds']-frames[0]['timestamp_seconds'])//PROTOCOL['temporal_block_seconds']) for f in frames])
    cells = np.floor(positions[:, [0, 2]]/PROTOCOL['spatial_cell_m']).astype(int)
    cells = [tuple(map(int,c)) for c in cells]; cell_counts = Counter(cells)
    missing_cells = [list(cell) for cell, count in cell_counts.items() if count >= PROTOCOL['min_spatial_cell_frames'] and not any(cells[i] == cell for i in main)]
    missing_blocks = sorted(set(temporal.tolist())-set(temporal[list(main)].tolist()))
    def is_revisit(a,b):
        if 'revisit_min_gap_seconds' in PROTOCOL:
            return abs(frames[a]['timestamp_seconds']-frames[b]['timestamp_seconds']) >= PROTOCOL['revisit_min_gap_seconds']
        return abs(a-b) >= PROTOCOL['revisit_min_gap_frames']
    revisit = [(a, b) for a, b in edges if a in main and b in main and is_revisit(a,b)]
    bridge_pairs = bridges(adjacency, main)
    supported = int((observations >= PROTOCOL['min_camera_track_observations']).sum())
    gates = dict(
        main_component_fraction=len(main)/len(frames) >= PROTOCOL['min_main_component_fraction'],
        sufficient_observations_fraction=supported/len(frames) >= PROTOCOL['min_supported_camera_fraction'],
        all_temporal_blocks=not missing_blocks, all_populated_spatial_cells=not missing_cells,
        revisits_connect=len(revisit) >= PROTOCOL['min_main_component_revisit_edges'],
        no_single_edge_bridges=len(bridge_pairs) <= PROTOCOL['max_graph_bridges'],
    )
    return dict(passed=all(gates.values()), gates=gates, component_sizes=[len(c) for c in groups], components=groups,
                main_fraction=len(main)/len(frames), supported_cameras=supported, camera_track_counts=observations.tolist(),
                missing_temporal_blocks=missing_blocks, missing_populated_spatial_cells=missing_cells,
                main_revisit_edges=len(revisit), bridges=bridge_pairs,
                edges=[dict(first=a, second=b, tracks=count) for (a,b),count in edges.items()])


def spatial_support(uv, width, height):
    cells = np.floor(uv/[width/4, height/3]).astype(int).clip([0,0],[3,2])
    return len(set(map(tuple,cells))), float(cv2.contourArea(cv2.convexHull(uv.astype('f4')))/(width*height))


def draw_graph(output, graph, positions):
    """Local evidence using the existing Pillow dependency, without plotting extras."""
    canvas=Image.new('RGB',(1500,780),(22,29,34));draw=ImageDraw.Draw(canvas)
    palette=['#e5b567','#79bcdb','#aa9add','#b4cb87','#f18f80','#7ac8b5','#dca2c8','#ddd481']
    membership={c:k for k,g in enumerate(graph['components']) for c in g}
    draw.text((25,20),'RELIABLE RGB TRACK CONNECTIVITY | fixed pre-optimization gate',fill='white')
    draw.text((25,45),f"Largest component: {len(graph['components'][0])}/{len(positions)} cameras | Gate: {'PASS' if graph['passed'] else 'FAIL'}",fill='white')
    bounds=[(55,125,730,670),(815,125,1460,670)]
    arrays=[np.column_stack([np.arange(len(positions)),positions[:,0]]),positions[:,[0,2]]]
    maps=[]
    for panel,data in zip(bounds,arrays):
        x0,y0,x1,y1=panel;low=data.min(0);span=np.maximum(np.ptp(data,axis=0),.01)
        xy=(data-low)/span*[x1-x0,-(y1-y0)]+[x0,y1];maps.append(xy)
        draw.rectangle(panel,outline='#63727b')
        for axis in range(2):
            for tick in range(5):
                value=low[axis]+span[axis]*tick/4
                if axis==0:
                    x=x0+(x1-x0)*tick/4;draw.text((x-12,y1+10),f'{value:.1f}',fill='#c7d0d4')
                else:
                    y=y1-(y1-y0)*tick/4;draw.text((x0-35,y-5),f'{value:.1f}',fill='#c7d0d4')
        for row in graph['edges']:
            a,b=row['first'],row['second'];draw.line([tuple(xy[a]),tuple(xy[b])],fill='#34434c',width=1)
        for i,(x,y) in enumerate(xy):
            color=palette[membership[i]%len(palette)] if len(graph['components'][membership[i]])>1 else '#a7adb2'
            draw.ellipse((x-3,y-3,x+3,y+3),fill=color)
    draw.text((180,90),'Chronology: training camera index vs ARKit X (m)',fill='white')
    draw.text((880,90),'Path: ARKit X vs Z (m); axes independently scaled',fill='white')
    draw.text((35,718),'Component sizes: '+', '.join(map(str,[len(g) for g in graph['components'][:12]]))+' ...',fill='white')
    draw.text((35,744),'Same colour = one connected component (palette cycles). Grey = isolated. These are track links, not physical walls.',fill='#c7d0d4')
    canvas.save(output/'track-connectivity.png')


def report_cached(source, baseline, output):
    """Recover reporting only; never extract or rematch features or fit a pose."""
    if (output/'track-report.json').exists():raise ValueError('An existing track report is immutable')
    if json.loads((output/'protocol.json').read_text())!=PROTOCOL:raise ValueError('Frozen track protocol changed')
    frames,evaluation=split_frames(load_frames(source));split=json.loads((baseline/'split.json').read_text())
    if [f['rgb_file'] for f in frames]!=split['train'] or [f['rgb_file'] for f in evaluation]!=split['held_out']:raise ValueError('Frozen split changed')
    tracks=json.loads((output/'tracks.json').read_text());data=np.load(output/'tracks.npz');pairs=json.loads((output/'pairs.json').read_text())
    expected=[c for tr in tracks for c,_ in tr['nodes']]
    if not np.array_equal(data['camera'],expected) or len(data['points'])!=len(tracks):raise ValueError('Cached track observations are inconsistent')
    graph=track_graph(tracks,frames,data['positions'])
    with (output/'tracks.npz').open('rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
    report=dict(protocol=PROTOCOL,source_scan_id=split['source_scan_id'],index_sha256=hashlib.sha256((source/'Frames.json').read_bytes()).hexdigest(),
                frame_names=[f['rgb_file'] for f in frames],reserved_frames_never_opened_for_features=split['excluded_held_out_frames'],
                training_cameras=len(frames),candidate_pairs=len(pairs),accepted_pairs=sum(r['accepted'] for r in pairs),
                bundle_tracks=len(tracks),observations=len(data['camera']),graph=graph,cached_tracks_sha256=digest,
                reporting_recovery='Matching and track selection ran once. Initial JSON report hit a NumPy integer serialization error after writing pairs.json, tracks.json and tracks.npz. This report uses only those unchanged caches; rejection counters were not persisted. No feature rematching, threshold changes or pose optimization.',
                limitations='These fixed matcher/reliability gates did not establish room-wide connectivity. Failure does not prove that another reconstruction system cannot use the raw images.')
    (output/'track-report.json').write_text(json.dumps(report,indent=2));draw_graph(output,graph,data['positions'])
    print(json.dumps({k:graph[k] for k in ['passed','gates','component_sizes','main_fraction','supported_cameras','main_revisit_edges','bridges']},indent=2))
    return graph['passed']


def worker(source, baseline, output):
    start = time.monotonic(); cv2.setNumThreads(2); cv2.setRNGSeed(PROTOCOL['seed'])
    validate(source)
    all_frames = load_frames(source)
    selection = baseline/'frame-selection.json'
    frames,evaluation = selected_split(source,all_frames,load_selection(selection)) if selection.exists() else split_frames(all_frames)
    split = json.loads((baseline/'split.json').read_text())
    if [f['rgb_file'] for f in frames] != split['train'] or [f['rgb_file'] for f in evaluation] != split['held_out']:
        raise ValueError('Frozen split does not match source')
    excluded = [f['rgb_file'] for f in all_frames if f.get('capture_phase') == 'held_out']
    if excluded != split['excluded_held_out_frames']: raise ValueError('Reserved phase changed')
    poses = np.stack([matrix(f,'camera_to_world_column_major',4) for f in frames]); positions = poses[:,:3,3]
    directions = -poses[:,:3,2]; E = np.stack([extrinsic(f) for f in frames]); K=[]; features=[]
    detector = cv2.SIFT_create(nfeatures=PROTOCOL['sift_features'])
    for i,f in enumerate(frames):
        width=PROTOCOL['image_width']; height=round(width*f['image_height']/f['image_width'])
        gray=np.asarray(Image.open(source/f['rgb_file']).convert('L').resize((width,height),Image.Resampling.LANCZOS))
        kp,desc=detector.detectAndCompute(gray,None); uv=np.asarray([k.pt for k in kp],dtype='f4').reshape(-1,2)
        k=matrix(f,'intrinsics_column_major',3).copy();k[0]*=width/f['image_width'];k[1]*=height/f['image_height'];K.append(k)
        if f.get('confidence_available',True) and f.get('depth_available',True):
            dep=read_depth(source,f);pix=np.rint(uv*[f['depth_width']/width,f['depth_height']/height]).astype(int)
            pix=np.clip(pix,[0,0],[f['depth_width']-1,f['depth_height']-1]);depth=dep[pix[:,1],pix[:,0]]
        else:depth=np.zeros(len(uv))
        world=(np.column_stack([uv,np.ones(len(uv))])@np.linalg.inv(k).T*depth[:,None]-E[i,:3,3])@E[i,:3,:3]
        features.append(dict(uv=uv,desc=desc,depth=depth,world=world,height=height))
        if i%40==0: print('Training features',i+1,'/',len(frames),flush=True)
    K=np.array(K)
    candidates={}
    times=np.array([f['timestamp_seconds'] for f in frames])
    for i in range(len(frames)):
        if 'temporal_offsets_seconds' in PROTOCOL:
            if i+1<len(frames):candidates[(i,i+1)]='adjacent'
            for offset in PROTOCOL['temporal_offsets_seconds']:
                j=int(np.argmin(np.abs(times-times[i]-offset)))
                if j>i and abs(times[j]-times[i]-offset)<=.25:candidates[(i,j)]='temporal'
        else:
            for offset in PROTOCOL['temporal_offsets']:
                if i+offset<len(frames): candidates[(i,i+offset)]='temporal'
        distance=np.linalg.norm(positions-positions[i],axis=1);dot=directions@directions[i]
        revisit_gap=(np.abs(times-times[i])>=PROTOCOL['revisit_min_gap_seconds']) if 'revisit_min_gap_seconds' in PROTOCOL else (np.abs(np.arange(len(frames))-i)>=PROTOCOL['revisit_min_gap_frames'])
        valid=np.flatnonzero(revisit_gap & (distance<PROTOCOL['revisit_max_distance_m']) & (dot>PROTOCOL['revisit_min_view_dot']))
        score=distance[valid]+(1-dot[valid])
        for j in valid[np.argsort(score)[:PROTOCOL['revisit_neighbors']]]:candidates[tuple(sorted((i,int(j))))]='revisit'
    matcher=cv2.BFMatcher(cv2.NORM_L2);rows=[];links=[]
    def ratio_matches(a,b):
        if a is None or b is None or len(a)<2 or len(b)<2:return {}
        return {pair[0].queryIdx:pair[0].trainIdx for pair in matcher.knnMatch(a,b,k=2) if len(pair)==2 and pair[0].distance<PROTOCOL['ratio']*pair[1].distance}
    for number,((i,j),kind) in enumerate(sorted(candidates.items())):
        fa,fb=features[i],features[j];ab=ratio_matches(fa['desc'],fb['desc']);ba=ratio_matches(fb['desc'],fa['desc'])
        pairs=np.array([(a,b) for a,b in ab.items() if ba.get(b)==a],dtype=int).reshape(-1,2)
        row=dict(first=i,second=j,kind=kind,mutual_matches=len(pairs),accepted=False)
        if len(pairs)>=PROTOCOL['min_pair_inliers']:
            aa,bb=fa['uv'][pairs[:,0]],fb['uv'][pairs[:,1]]
            _,mask=cv2.findFundamentalMat(aa,bb,cv2.USAC_MAGSAC,PROTOCOL['fundamental_threshold_px'],PROTOCOL['fundamental_confidence'],PROTOCOL['fundamental_iterations'])
            if mask is not None:
                good=mask.ravel()!=0;selected=pairs[good];aa,bb=aa[good],bb[good]
                if len(selected)>=3:
                    cells_a,hull_a=spatial_support(aa,960,fa['height']);cells_b,hull_b=spatial_support(bb,960,fb['height'])
                    row.update(inliers=len(selected),inlier_fraction=float(good.mean()),grid_cells=[cells_a,cells_b],hull_fraction=[hull_a,hull_b])
                    row['accepted']=bool(len(selected)>=PROTOCOL['min_pair_inliers'] and good.mean()>=PROTOCOL['min_pair_inlier_fraction'] and min(cells_a,cells_b)>=PROTOCOL['min_pair_grid_cells'] and min(hull_a,hull_b)>=PROTOCOL['min_pair_hull_fraction'])
                    if row['accepted']:links.extend(((i,int(a)),(j,int(b))) for a,b in selected)
        rows.append(row)
        if number%100==0:print('Pairs',number+1,'/',len(candidates),'accepted',sum(r['accepted'] for r in rows),flush=True)
    (output/'pairs.json').write_text(json.dumps(rows,indent=2))
    parent={}
    def root(node):
        parent.setdefault(node,node)
        while parent[node]!=node:parent[node]=parent[parent[node]];node=parent[node]
        return node
    for a,b in links:
        ra,rb=root(a),root(b)
        if ra!=rb:parent[rb]=ra
    groups=defaultdict(list)
    for node in parent:groups[root(node)].append(node)
    accepted=[];rejected=Counter()
    for nodes in groups.values():
        cams=[c for c,_ in nodes]
        if len(set(cams))!=len(cams):rejected['conflicting_same_image_feature']+=1;continue
        if len(cams)<PROTOCOL['min_track_views']:rejected['short']+=1;continue
        nodes=sorted(nodes);cams=np.array([c for c,_ in nodes]);uv=np.array([features[c]['uv'][k] for c,k in nodes]);depth=np.array([features[c]['depth'][k] for c,k in nodes]);supported=depth>0
        if supported.sum()<PROTOCOL['min_track_depth_views']:rejected['insufficient_high_confidence_depth']+=1;continue
        if np.max(np.linalg.norm(positions[cams][:,None]-positions[cams][None,:],axis=2))<PROTOCOL['min_track_baseline_m']:rejected['insufficient_baseline']+=1;continue
        world=np.array([features[c]['world'][k] for c,k in nodes])[supported];point=np.median(world,axis=0);scatter=np.linalg.norm(world-point,axis=1)
        if np.median(scatter)>PROTOCOL['max_track_world_median_m'] or np.percentile(scatter,90)>PROTOCOL['max_track_world_p90_m']:rejected['inconsistent_metric_support']+=1;continue
        q=np.einsum('nij,j->ni',E[cams,:3,:3],point)+E[cams,:3,3]
        if (q[:,2]<=.1).any():rejected['behind_camera']+=1;continue
        projected=np.einsum('nij,nj->ni',K[cams],q);error=np.linalg.norm(projected[:,:2]/projected[:,2,None]-uv,axis=1)
        if np.median(error)>PROTOCOL['max_track_reprojection_median_px'] or np.percentile(error,90)>PROTOCOL['max_track_reprojection_p90_px']:rejected['inconsistent_reprojection']+=1;continue
        accepted.append(dict(nodes=nodes,point=point.tolist(),median_error_px=float(np.median(error)),p90_error_px=float(np.percentile(error,90)),world_median_m=float(np.median(scatter))))
    # Balanced fixed cap for the single bundle solve. Its actual graph must pass too.
    ranked=sorted(range(len(accepted)),key=lambda t:(-min(len(accepted[t]['nodes']),20),accepted[t]['median_error_px']))
    per_camera=defaultdict(list)
    for t in ranked:
        for c,_ in accepted[t]['nodes']:per_camera[c].append(t)
    chosen=set()
    for rank in range(PROTOCOL['balanced_tracks_per_camera']):
        for c in range(len(frames)):
            if rank<len(per_camera[c]) and len(chosen)<PROTOCOL['max_bundle_tracks']:chosen.add(per_camera[c][rank])
    for t in ranked:
        if len(chosen)>=PROTOCOL['max_bundle_tracks']:break
        chosen.add(t)
    tracks=[accepted[t] for t in sorted(chosen)]
    graph=track_graph(tracks,frames,positions)
    obs_camera=[];obs_track=[];obs_uv=[];obs_depth=[]
    for t,tr in enumerate(tracks):
        for c,k in tr['nodes']:
            obs_camera.append(c);obs_track.append(t);obs_uv.append(features[c]['uv'][k]);obs_depth.append(features[c]['depth'][k])
    np.savez_compressed(output/'tracks.npz',camera=np.array(obs_camera),track=np.array(obs_track),uv=np.array(obs_uv),depth=np.array(obs_depth),points=np.array([t['point'] for t in tracks]),intrinsics=K,extrinsics=E,positions=positions)
    (output/'tracks.json').write_text(json.dumps(tracks))
    index=source/('DenseFrames.json' if selection.exists() else 'Frames.json')
    report=dict(protocol=PROTOCOL,source_scan_id=split['source_scan_id'],index_sha256=hashlib.sha256(index.read_bytes()).hexdigest(),
                frame_names=[f['rgb_file'] for f in frames],reserved_frames_never_opened_for_features=excluded,
                training_cameras=len(frames),candidate_pairs=len(rows),accepted_pairs=sum(r['accepted'] for r in rows),
                feature_components=len(groups),rejected_tracks=dict(rejected),reliable_tracks=len(accepted),bundle_tracks=len(tracks),observations=len(obs_camera),
                graph=graph,seconds=time.monotonic()-start,
                limitations='Train-only SIFT/F geometry and high-confidence depth consistency; no manual semantic reflection mask, no independent ground truth. Passing connectivity does not establish unbiased poses or full surface coverage.')
    (output/'track-report.json').write_text(json.dumps(report,indent=2));print(json.dumps({k:report[k] for k in ['candidate_pairs','accepted_pairs','reliable_tracks','bundle_tracks','observations','seconds']},indent=2),flush=True)
    print(json.dumps({k:graph[k] for k in ['passed','gates','component_sizes','main_fraction','supported_cameras','main_revisit_edges','bridges']},indent=2),flush=True)
    draw_graph(output,graph,positions)
    return graph['passed']


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('baseline',type=Path);p.add_argument('output',type=Path);p.add_argument('--worker',action='store_true',help=argparse.SUPPRESS);p.add_argument('--report-cached',action='store_true',help='Recover a failed report from the fixed cached tracks; no feature extraction or optimization');a=p.parse_args()
    if a.report_cached:sys.exit(0 if report_cached(a.source,a.baseline,a.output) else 2)
    if a.worker:sys.exit(0 if worker(a.source,a.baseline,a.output) else 2)
    a.output.mkdir(parents=True,exist_ok=False)
    (a.output/'protocol.json').write_text(json.dumps(PROTOCOL,indent=2))
    command=[sys.executable,__file__,str(a.source),str(a.baseline),str(a.output),'--worker'];start=time.monotonic()
    with (a.output/'track-build.log').open('w') as log:
        try:code=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,timeout=PROTOCOL['tracking_timeout_seconds']).returncode
        except subprocess.TimeoutExpired:code='timeout'
    (a.output/'run.json').write_text(json.dumps(dict(command=command,exit_code=code,seconds=time.monotonic()-start),indent=2))
    print('Track gate exit:',code,'Evidence:',a.output,flush=True)
    sys.exit(0 if code==0 else 1)
