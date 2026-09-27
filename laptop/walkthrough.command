#!/bin/zsh
# Launch the local room reconstruction selected by the private asset manifest.
cd "${0:A:h:h}" || exit 1
SCAN_ID=$(python3 -c 'import json; print(json.load(open("reconstructions/room-pass/reconstruction.json"))["source_scan_id"])') || exit 1
exec python3 laptop/edit_room.py "scans/$SCAN_ID" --reconstruction reconstructions/room-pass
