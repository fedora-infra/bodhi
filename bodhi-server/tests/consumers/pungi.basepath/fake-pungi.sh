#!/bin/sh

# Called with:
# $0 --config /path/to/pungi.conf --quiet --print-output-dir --target-dir /compose/dir --old-composes /compose/dir --no-latest-link --label update-label

set -e

compose_dir="$6"

mkdir -p "$compose_dir"/compose/metadata
touch "$compose_dir"/compose/metadata/composeinfo.json
echo "Compose dir: $compose_dir"
