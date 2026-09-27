#!/bin/zsh
# Open the separately preserved TV/couch capture, using its own RoomPlan layer.
cd "${0:A:h:h}" || exit 1
SCAN_ID=$(python3 -c 'import json; print(json.load(open("reconstructions/tv-couch-pass/2hz/reconstruction.json"))["source_scan_id"])') || exit 1
exec python3 laptop/edit_room.py "scans/$SCAN_ID" --reconstruction reconstructions/tv-couch-pass/2hz
