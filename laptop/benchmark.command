#!/bin/zsh
# Optional local comparison; the normal app needs no Scaniverse installation.
cd "${0:A:h:h}" || exit 1
SCAN_ID=$(python3 -c 'import json; print(json.load(open("reconstructions/guided-pass-2/reconstruction.json"))["source_scan_id"])') || exit 1
exec python3 laptop/edit_room.py "scans/$SCAN_ID" --reconstruction reconstructions/guided-pass-2 --benchmark reconstructions/scaniverse-classic/benchmark.json
