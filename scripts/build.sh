#!/usr/bin/env bash
# Build the image with the classic builder, as CI and the release do.
#
#   scripts/build.sh [<tag>]        default tag: iris-web-2x:dev
#
# The labels take the version from VERSION, the revision from HEAD (with "-dirty" when the
# working tree differs from it) and the creation time from HEAD's committer time.
set -euo pipefail
cd "$(dirname "$0")/.."

tag=${1:-iris-web-2x:dev}
revision=$(git rev-parse HEAD)
[ -z "$(git status --porcelain)" ] || revision="$revision-dirty"

DOCKER_BUILDKIT=0 docker build \
    --build-arg IMAGE_VERSION="$(cat VERSION)" \
    --build-arg REVISION="$revision" \
    --build-arg CREATED="$(git log -1 --format=%cI)" \
    --tag "$tag" .
