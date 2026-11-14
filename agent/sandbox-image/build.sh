#!/bin/sh
# Build Repro Bot's sandbox image with rootless Podman (takes a few minutes, about 2 GB).
# Proxy variables in the environment are passed to the build automatically.
set -eu
cd "$(dirname "$0")"
TAG=localhost/repro-sandbox:2   # keep in step with FULL_IMAGE in agent/sandbox.py
podman build --pull=missing -t "$TAG" -f Containerfile .
podman run --rm "$TAG" sh -c \
  'python --version && conda --version && uv --version && R --version | head -1 && pandoc --version | head -1 && gcc --version | head -1 && jupyter nbconvert --version'
