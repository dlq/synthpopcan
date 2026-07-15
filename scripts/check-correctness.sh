#!/bin/sh
set -eu

SYNTHPOPCAN_CORRECTNESS_EXTENDED=1 uv run pytest \
  tests/test_ipf_correctness.py \
  tests/test_model_correctness.py \
  tests/test_small_area_correctness.py \
  tests/test_reference_correctness.py \
  "$@"
