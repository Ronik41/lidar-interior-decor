#!/usr/bin/env python3
"""Local AVFoundation video audit, optionally extract explicitly selected frame indices."""
import argparse
import subprocess
from pathlib import Path
from import_scan import validate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('scan', type=Path)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--indices', type=Path, help='JSON array of frame_index values; preserve held-out labels')
    parser.add_argument('--output', type=Path, help='New directory for sensor-native PNGs')
    args = parser.parse_args()
    manifest = validate(args.scan)
    if 'video_frames' not in manifest:
        parser.error('Scan contains no video extension')
    if bool(args.indices) != bool(args.output):
        parser.error('--indices and --output must be supplied together')
    source = Path(__file__).with_suffix('.swift')
    binary = source.parent/'.build'/'audit_video'
    binary.parent.mkdir(exist_ok=True)
    if not binary.exists() or binary.stat().st_mtime < source.stat().st_mtime:
        subprocess.run(['xcrun', 'swiftc', '-parse-as-library', str(source), '-o', str(binary)], check=True)
    command = [str(binary), str(args.scan.resolve()), str(args.report.resolve())]
    if args.indices:
        command += [str(args.indices.resolve()), str(args.output.resolve())]
    subprocess.run(command, check=True)


if __name__ == '__main__':
    main()
