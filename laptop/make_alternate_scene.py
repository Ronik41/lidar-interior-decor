#!/usr/bin/env python3
"""Small public synthetic RoomPlan package for adapter/UI verification. No scans."""
import hashlib
import json
from pathlib import Path
from test_import_scan import make_fixture


def create(root):
    root=Path(root);make_fixture(root)
    room=json.loads(Path(__file__).with_name('fixtures').joinpath('alternate-room.json').read_text())
    (root/'Room.json').write_text(json.dumps(room))
    path=root/'manifest.json';manifest=json.loads(path.read_text())
    manifest['scan_id']='11111111-2222-4333-8444-555555555555'
    manifest['units']='meters';manifest['sha256']['Room.json']=hashlib.sha256((root/'Room.json').read_bytes()).hexdigest()
    path.write_text(json.dumps(manifest))
    return root


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('output',type=Path);args=p.parse_args()
    if args.output.exists():p.error('Choose a new output directory')
    print(create(args.output))
