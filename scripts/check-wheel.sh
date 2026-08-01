#!/bin/sh
set -eu

root=$(pwd)
wheel=$(find dist -maxdepth 1 -name 'synthpopcan-*.whl' -print | sort | tail -n 1)
sdist=$(find dist -maxdepth 1 -name 'synthpopcan-*.tar.gz' -print | sort | tail -n 1)
if [ -z "$wheel" ]; then
  echo "No SynthPopCan wheel found in dist/. Run 'uv build --wheel' first." >&2
  exit 1
fi
if [ -z "$sdist" ]; then
  echo "No SynthPopCan sdist found in dist/. Run 'uv build' first." >&2
  exit 1
fi

smoke_dir=$(mktemp -d "${TMPDIR:-/tmp}/synthpopcan-wheel-smoke.XXXXXX")
sdist_smoke_dir=$(mktemp -d "${TMPDIR:-/tmp}/synthpopcan-sdist-smoke.XXXXXX")
model_smoke_dir=$(mktemp -d "${TMPDIR:-/tmp}/synthpopcan-model-build-smoke.XXXXXX")
trap 'rm -rf "$smoke_dir" "$sdist_smoke_dir" "$model_smoke_dir"' EXIT
cp scripts/wheel_smoke.py "$smoke_dir/wheel_smoke.py"
cd "$smoke_dir"
UV_CACHE_DIR="${SYNTHPOPCAN_WHEEL_CACHE:-/tmp/synthpopcan-wheel-cache}" \
  SYNTHPOPCAN_SOURCE_ROOT="$root" \
  uv run --isolated --with "$root/$wheel" python wheel_smoke.py
echo "Installed wheel smoke command completed."

cp "$root/scripts/wheel_smoke.py" "$sdist_smoke_dir/distribution_smoke.py"
cd "$sdist_smoke_dir"
UV_CACHE_DIR="${SYNTHPOPCAN_WHEEL_CACHE:-/tmp/synthpopcan-wheel-cache}" \
  SYNTHPOPCAN_SOURCE_ROOT="$root" \
  uv run --isolated \
    --with "synthpopcan @ file://$root/$sdist" \
    python distribution_smoke.py
echo "Installed sdist smoke command completed."

cp "$root/scripts/model_build_smoke.py" "$model_smoke_dir/model_build_smoke.py"
cd "$model_smoke_dir"
UV_CACHE_DIR="${SYNTHPOPCAN_WHEEL_CACHE:-/tmp/synthpopcan-wheel-cache}" \
  SYNTHPOPCAN_SOURCE_ROOT="$root" \
  uv run --isolated \
    --with "synthpopcan[model-build] @ file://$root/$wheel" \
    python model_build_smoke.py
echo "Installed model-build smoke command completed."
