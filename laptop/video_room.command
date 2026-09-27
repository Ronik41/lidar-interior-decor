#!/bin/zsh
# Open the full video capture separately; previous scans/models are preserved.
cd "${0:A:h:h}" || exit 1
SCAN_ID=$(python3 -c 'import json; print(json.load(open("reconstructions/video-room-pass/mesh-result/reconstruction.json"))["source_scan_id"])') || exit 1
exec python3 laptop/edit_room.py "scans/$SCAN_ID" --reconstruction reconstructions/video-room-pass/mesh-result
