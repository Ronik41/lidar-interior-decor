#!/usr/bin/env python3
"""Decode and audit an opt-in dense package without modifying any capture data."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
from import_scan import validate


def distribution(values):
    a = np.asarray(values, dtype=float)
    if not len(a): return None
    return dict(mean=float(a.mean()), median=float(np.median(a)), p95=float(np.percentile(a, 95)), maximum=float(a.max()))


def audit(source, output):
    manifest = validate(source)
    if 'dense_frames' not in manifest: raise ValueError('No dense extension was saved')
    index = json.loads((source/'DenseFrames.json').read_text()); frames = index['frames']
    output.mkdir(parents=True, exist_ok=True)
    if (output/'audit.json').exists(): raise ValueError('Audit already exists; preserve it and use a new output')
    for f in frames:
        with Image.open(source/f['rgb_file']) as im:
            im.load()
            if im.size != (f['image_width'], f['image_height']): raise ValueError('Encoded image/calibration resolution mismatch')
    telemetry = index['telemetry']; timestamps = [f['timestamp_seconds'] for f in frames]
    first = next((t['elapsed_seconds'] for t in telemetry if t['tracking_state'] == 'normal'), None)
    steady = [t for t in telemetry if first is not None and t['elapsed_seconds'] >= first]
    tracking = dict(Counter(t['tracking_state'] for t in telemetry)); thermal = dict(Counter(t['thermal_state'] for t in telemetry))
    fps = (len(frames)-1)/(timestamps[-1]-timestamps[0]) if len(frames)>1 else 0
    writer_skips = index['skipped'].get('writer busy', 0)
    complete = index['status'] in ('scan completed', 'duration limit') and index['elapsed_seconds'] >= index['duration_limit_seconds']-.5
    gates = dict(roomplan_export_valid=True, all_payload_hashes_and_jpegs_valid=True,
                 enough_saved_duration=len(frames)>1 and timestamps[-1]-timestamps[0] >= index['duration_limit_seconds']-10,
                 saved_fps_at_least_7_5=fps >= 7.5,
                 writer_skips_at_most_5_percent=writer_skips/max(1, len(steady)) <= .05,
                 no_write_errors=not index['write_errors'], thermal_no_serious_or_critical=all(int(t)<2 for t in thermal),
                 finished_without_guard=complete,
                 tracking_normal_after_acquisition_at_least_95_percent=sum(t['tracking_state']=='normal' for t in steady)/max(1,len(steady)) >= .95)
    poses = np.array([f['camera_to_world_column_major'] for f in frames]).reshape(-1,4,4).transpose(0,2,1) if frames else np.empty((0,4,4))
    coverage = {}
    if len(poses)>1:
        positions = poses[:,:3,3]; forward = -poses[:,:3,2]
        yaw = np.arctan2(forward[:,0],forward[:,2]); pitch = np.arcsin(forward[:,1].clip(-1,1))
        coverage = dict(path_length_m=float(np.linalg.norm(np.diff(positions,axis=0),axis=1).sum()),
                        span_xyz_m=np.ptp(positions,axis=0).tolist(),
                        yaw_sectors_of_12=int(len(np.unique((np.mod(yaw,2*np.pi)/(2*np.pi)*12).astype(int)))),
                        upward_frames_above_30_degrees=int((pitch > np.pi/6).sum()),
                        pitch_range_degrees=np.degrees([pitch.min(),pitch.max()]).tolist(),
                        limitation='ARKit pose coverage and drift-sensitive path length, not visible-surface completeness or feature connectivity.')
    report = dict(scan_id=manifest['scan_id'], app_build=index.get('app_build'), capture_profile=index['capture_profile'],
        guidance_version=index.get('guidance_version'), format=index['format'],
        index_sha256=hashlib.sha256((source/'DenseFrames.json').read_bytes()).hexdigest(),
        saved=len(frames), elapsed_seconds=index['elapsed_seconds'], duration_limit_seconds=index['duration_limit_seconds'],
        actual_saved_fps=fps, saved_per_total_elapsed_second=len(frames)/max(.001,index['elapsed_seconds']),
        timestamp_gap_seconds=distribution(np.diff(timestamps)), skipped=index['skipped'],
        missed_schedule_slots=index['missed_schedule_slots'], write_errors=index['write_errors'],
        encode_write_ms=distribution(index['encode_write_milliseconds']),
        jpeg_encode_ms=distribution([f['jpeg_encode_milliseconds'] for f in frames]),
        tracking_attempts=tracking, thermal_attempts=thermal, first_normal_elapsed_seconds=first,
        depth_count=sum(f['depth_available'] for f in frames), confidence_count=sum(f['confidence_available'] for f in frames),
        phases=dict(Counter(f['capture_phase'] for f in frames)), coverage=coverage,
        guidance_events=index['guidance_events'], physical_hud_confirmation='Must be recorded separately from the user; software telemetry alone is insufficient.',
        image_sequence_reliability_gates=gates, image_sequence_passes=all(gates.values()),
        format_decision='Image sequence supported by this run' if all(gates.values()) else 'Image sequence not yet validated; do not start the full pass',
        limits='These gates test frame transport and coexistence with RoomPlan, not reconstruction quality. Video has not been benchmarked. Unsampled native AR frames are intentional; target-slot drops are counted.')
    (output/'audit.json').write_text(json.dumps(report,indent=2))
    if frames:
        chosen = [frames[i] for i in np.linspace(0,len(frames)-1,min(12,len(frames))).astype(int)]
        sheet=Image.new('RGB',(960,((len(chosen)+3)//4)*350),(22,27,32)); draw=ImageDraw.Draw(sheet)
        for i,f in enumerate(chosen):
            im=Image.open(source/f['rgb_file']).rotate(-90,expand=True); im.thumbnail((230,308))
            x,y=(i%4)*240,(i//4)*350; sheet.paste(im,(x,y+35))
            draw.text((x+4,y+5),f"{f['elapsed_seconds']:.1f}s {f['capture_phase']}",fill='white')
        sheet.save(output/'contact-sheet.jpg',quality=94)
    print(json.dumps(report,indent=2)); return report


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('output',type=Path);a=p.parse_args();audit(a.source,a.output)
