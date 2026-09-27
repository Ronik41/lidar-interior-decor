#!/usr/bin/env python3
"""Fixed train-only connectivity diagnostic for the dense capture ablation; no pose fitting."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time
import joint_rgb_tracks as tracks

# Same reliability thresholds in both conditions. Temporal neighbors use seconds
# so the 8 Hz condition is not restricted to a shorter time horizon than 2 Hz.
PROTOCOL = dict(tracks.PROTOCOL, temporal_offsets_seconds=[.5,1.,2.,4.],
                revisit_min_gap_seconds=10., diagnostic='dense-ablation-v1',
                acceptance='Diagnostic only: compare fraction of cameras connected and supported; never adjust poses or training settings.',
                detail_views=['four furniture, four kitchen, four ceiling held-out frames; never opened here'])
PROTOCOL.pop('temporal_offsets'); PROTOCOL.pop('revisit_min_gap_frames')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('condition',type=Path);p.add_argument('output',type=Path)
    p.add_argument('--worker',action='store_true',help=argparse.SUPPRESS);a=p.parse_args()
    tracks.PROTOCOL=PROTOCOL
    # At most 1200 training cameras; the existing bridge traversal is recursive.
    sys.setrecursionlimit(10000)
    if a.worker:
        passed=tracks.worker(a.source,a.condition,a.output)
        sys.exit(0)  # a disconnected graph is a recorded result, not a failed execution
    a.output.mkdir(parents=True,exist_ok=False)
    (a.output/'protocol.json').write_text(json.dumps(PROTOCOL,indent=2))
    command=[sys.executable,__file__,str(a.source),str(a.condition),str(a.output),'--worker'];start=time.monotonic()
    with (a.output/'process.log').open('w') as log:
        try:code=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,timeout=600).returncode
        except subprocess.TimeoutExpired:code='timeout'
    (a.output/'run.json').write_text(json.dumps(dict(command=command,exit_code=code,seconds=time.monotonic()-start),indent=2))
    print('Connectivity diagnostic:',code,'Evidence:',a.output)
    sys.exit(0 if code==0 else 1)
