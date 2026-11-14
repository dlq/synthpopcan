#!/bin/sh
set -eu

SYNTHPOPCAN_CORRECTNESS_EXTENDED=1 uv run python scripts/test_runner.py \
  correctness -- "$@"
