#!/usr/bin/env bash
# Run the renderer's tests in the stock base image (Python 3.9.25, bleach 6.1.0 as in IRIS),
# without network, with the renderer's source mounted read-only (SPEC §11).
#
#   scripts/test-renderer.sh [<unittest arguments>]
set -euo pipefail
cd "$(dirname "$0")/.."

base=$(sed -n 's/^FROM //p' Dockerfile)
docker run --rm --network none \
    --volume "$PWD/renderer:/src:ro" \
    --env PYTHONPATH=/src:/src/tests --env PYTHONDONTWRITEBYTECODE=1 \
    --entrypoint python "$base" -m unittest discover --start-directory /src/tests "$@"
