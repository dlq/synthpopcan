#!/bin/sh
set -eu

root=$(pwd)
wheel=$(find dist -maxdepth 1 -name 'synthpopcan-*.whl' -print | sort | tail -n 1)
if [ -z "$wheel" ]; then
  echo "No SynthPopCan wheel found in dist/. Run 'uv build --wheel' first." >&2
  exit 1
fi

smoke_dir=$(mktemp -d "${TMPDIR:-/tmp}/synthpopcan-wheel-smoke.XXXXXX")
trap 'rm -rf "$smoke_dir"' EXIT
cp scripts/wheel_smoke.py "$smoke_dir/wheel_smoke.py"
cd "$smoke_dir"
UV_CACHE_DIR="${SYNTHPOPCAN_WHEEL_CACHE:-/tmp/synthpopcan-wheel-cache}" \
  SYNTHPOPCAN_SOURCE_ROOT="$root" \
  uv run --isolated --with "$root/$wheel" python wheel_smoke.py
echo "Installed wheel smoke command completed."
