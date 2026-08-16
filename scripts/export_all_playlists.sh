#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/.."
PLAYLISTS_CSV="$SCRIPT_DIR/playlists.csv"
EXPORT_DIR="${1:-}"

if [ ! -f "$PLAYLISTS_CSV" ]; then
    echo "Error: $PLAYLISTS_CSV not found." >&2
    exit 1
fi

mapfile -t PLAYLISTS < <(python3 -c "
import csv, sys
with open(sys.argv[1], newline='', encoding='utf-8') as f:
    for row in csv.reader(f):
        if row and row[0]:
            print(row[0])
" "$PLAYLISTS_CSV")

for playlist in "${PLAYLISTS[@]}"; do
    echo "=> Exporting: $playlist"
    if [ -n "$EXPORT_DIR" ]; then
        python3 "$SCRIPT_DIR/sporganize.py" -e "$playlist" --export-dir "$EXPORT_DIR"
    else
        python3 "$SCRIPT_DIR/sporganize.py" -e "$playlist"
    fi
done
