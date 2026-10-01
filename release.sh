#!/usr/bin/env bash
# Kept for muscle memory: builds and uploads to PyPI. The full release flow
# (version, notes, GitHub release) lives in build.sh -- see ./build.sh --help.
set -euo pipefail
cd "$(dirname "$0")"
./build.sh build
./build.sh pypi
