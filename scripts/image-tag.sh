#!/usr/bin/env bash
# Print the app image tag: a hash of the committed files the image is built from.
# Changes to the app's README or tests keep the tag, so they don't need a new image.
# Keep this list in step with the COPY lines in app/Dockerfile.
set -euo pipefail
cd "$(dirname "$0")/.."
git ls-tree HEAD app/Dockerfile app/requirements.txt app/demo app/certs | git hash-object --stdin | cut -c1-7
