#!/bin/sh
set -eu

root=$(pwd -P)
version=$(uv run --locked python -c 'import tomllib; print(tomllib.load(open("pyproject.toml", "rb"))["project"]["version"])')
uv run --locked python scripts/build_release_evidence.py \
  --check-source-version \
  --version "$version"

set -- dist/synthpopcan-*.whl
if [ "$#" -ne 1 ] || [ ! -f "$1" ]; then
  echo "dist/ must contain exactly one SynthPopCan wheel." >&2
  exit 1
fi
wheel=$1
case ${wheel##*/} in
  synthpopcan-"$version"-*.whl) ;;
  *)
    echo "Wheel filename does not match project version $version: $wheel" >&2
    exit 1
    ;;
esac

set -- dist/synthpopcan-*.tar.gz
if [ "$#" -ne 1 ] || [ ! -f "$1" ]; then
  echo "dist/ must contain exactly one SynthPopCan sdist." >&2
  exit 1
fi
sdist=$1
case ${sdist##*/} in
  synthpopcan-"$version".tar.gz) ;;
  *)
    echo "Sdist filename does not match project version $version: $sdist" >&2
    exit 1
    ;;
esac

smoke_dir=$(mktemp -d "${TMPDIR:-/tmp}/synthpopcan-wheel-smoke.XXXXXX")
sdist_smoke_dir=$(mktemp -d "${TMPDIR:-/tmp}/synthpopcan-sdist-smoke.XXXXXX")
model_smoke_dir=$(mktemp -d "${TMPDIR:-/tmp}/synthpopcan-model-build-smoke.XXXXXX")
case_study_smoke_dir=$(mktemp -d "${TMPDIR:-/tmp}/synthpopcan-case-study-smoke.XXXXXX")
trap 'rm -rf "$smoke_dir" "$sdist_smoke_dir" "$model_smoke_dir" "$case_study_smoke_dir"' EXIT
cp scripts/wheel_smoke.py "$smoke_dir/wheel_smoke.py"
cd "$smoke_dir"
UV_CACHE_DIR="${SYNTHPOPCAN_WHEEL_CACHE:-/tmp/synthpopcan-wheel-cache}" \
  SYNTHPOPCAN_EXPECTED_VERSION="$version" \
  SYNTHPOPCAN_SOURCE_ROOT="$root" \
  uv run --isolated --with "$root/$wheel" python wheel_smoke.py
echo "Installed wheel smoke command completed."

cp "$root/scripts/wheel_smoke.py" "$sdist_smoke_dir/distribution_smoke.py"
cd "$sdist_smoke_dir"
UV_CACHE_DIR="${SYNTHPOPCAN_WHEEL_CACHE:-/tmp/synthpopcan-wheel-cache}" \
  SYNTHPOPCAN_EXPECTED_VERSION="$version" \
  SYNTHPOPCAN_SOURCE_ROOT="$root" \
  uv run --isolated \
    --with "synthpopcan @ file://$root/$sdist" \
    python distribution_smoke.py
echo "Installed sdist smoke command completed."

cp "$root/scripts/model_build_smoke.py" "$model_smoke_dir/model_build_smoke.py"
cd "$model_smoke_dir"
UV_CACHE_DIR="${SYNTHPOPCAN_WHEEL_CACHE:-/tmp/synthpopcan-wheel-cache}" \
  SYNTHPOPCAN_EXPECTED_VERSION="$version" \
  SYNTHPOPCAN_SOURCE_ROOT="$root" \
  uv run --isolated \
    --with "synthpopcan[model-build] @ file://$root/$wheel" \
    python model_build_smoke.py
echo "Installed model-build smoke command completed."

cp "$root/scripts/case_study_wheel_smoke.py" \
  "$case_study_smoke_dir/case_study_wheel_smoke.py"
cd "$case_study_smoke_dir"
UV_CACHE_DIR="${SYNTHPOPCAN_WHEEL_CACHE:-/tmp/synthpopcan-wheel-cache}" \
  SYNTHPOPCAN_EXPECTED_VERSION="$version" \
  SYNTHPOPCAN_SOURCE_ROOT="$root" \
  uv run --isolated \
    --with "synthpopcan @ file://$root/$wheel" \
    python case_study_wheel_smoke.py
echo "Installed-wheel fictional case-study interface smoke command completed."
