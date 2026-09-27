#!/bin/zsh
# Same second guided-route room, optionally opening one immutable design revision.
cd "${0:A:h:h}" || exit 1
SCAN_ID=b589d427-b891-4654-acd7-616eacb02e8a
SOURCE="scans/$SCAN_ID"
if [[ -n "$1" ]]; then
  if [[ ! "$1" =~ '^revision-[0-9]{4,}\.design\.json$' ]]; then
    print -u2 'Pass a saved revision filename, e.g. revision-0002.design.json'
    exit 1
  fi
  SOURCE="design-inputs/$SCAN_ID/$1"
fi
exec python3 laptop/edit_room.py "$SOURCE" --reconstruction reconstructions/guided-pass-2
