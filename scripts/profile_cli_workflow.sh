#!/bin/sh
# Reproduce the complete, cached-input Montreal workflow under a CPU profiler.
# Usage: scripts/profile_cli_workflow.sh FRESH_RUN_DIR SOURCE_RUN_DIR
set -eu
PROFILE=${SYNTHPOPCAN_PROFILE:-1}
WORKERS=${SYNTHPOPCAN_FIT_WORKERS:-2}
SOLVER=${SYNTHPOPCAN_JOINT_SOLVER:-hybrid}
POLARS_THREADS=${POLARS_MAX_THREADS:-}
R=$(mkdir -p "$1" && cd "$1" && pwd)
SOURCE=$(cd "$2" && pwd)
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT"
export SYNTHPOPCAN_MODEL_CACHE="$SOURCE/cache/models"
export SYNTHPOPCAN_GEODATA_CACHE="$SOURCE/cache/geodata"
export OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1
export OMP_NUM_THREADS=1 NUMBA_NUM_THREADS=1
for stage in controls candidates population; do
  if [ -e "$R/$stage" ]; then
    echo "Choose a fresh run directory; $R/$stage already exists." >&2
    exit 1
  fi
done
mkdir -p "$R/profiles" "$R/logs"
printf 'stage\tstart_epoch\tfinish_epoch\telapsed_seconds\n' > "$R/stage-times.tsv"
run() {
  stage=$1
  shift
  start=$(date +%s)
  printf '%s START %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" "$stage"
  if [ "$PROFILE" = 1 ]; then
    /usr/bin/time -p "$ROOT/.venv/bin/python" -m scalene run \
      --cpu-only --profile-all --profile-only "$ROOT/src/synthpopcan" \
      --no-stacks --profile-interval 60 --outfile "$R/profiles/$stage.json" \
      -m synthpopcan.cli --- "$@" > "$R/logs/$stage.log" 2> "$R/logs/$stage.stderr"
  else
    /usr/bin/time -p "$ROOT/.venv/bin/synthpopcan" "$@" \
      > "$R/logs/$stage.log" 2> "$R/logs/$stage.stderr"
  fi
  finish=$(date +%s)
  printf '%s\t%s\t%s\t%s\n' "$stage" "$start" "$finish" "$((finish-start))" >> "$R/stage-times.tsv"
  printf '%s DONE %s (%ss)\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" "$stage" "$((finish-start))"
}
run prepare-controls geo prepare-controls "$SOURCE/inputs/official-98-401-X2021007_eng_CSV.zip" \
  --cma 462 --source-profile statcan-hierarchical-2021 \
  --normalization observed-proportional --incomplete-geographies exclude \
  --profile-sha256 5d29811e5c3171cb16c9564bfbce0a08da45d1584810be2bd74764cbd2329ffc \
  --out "$R/controls"
run generate-candidates models generate montreal-cma-2021-all-fields \
  --households 100000 --random-seed 20211102 --out "$R/candidates"
if [ "$PROFILE" = 1 ]; then
  export SYNTHPOPCAN_PROFILE_WORKERS="$R/profiles/workers"
fi
export POLARS_MAX_THREADS=${POLARS_THREADS:-4}
run calibrate geo calibrate "$R/candidates" --controls "$R/controls" \
  --geo-dimension ct --geo-column ct --pool-size 20000 --subsample-seed 42 \
  --augment-support --workers "$WORKERS" --joint-solver "$SOLVER" --max-iterations 3000 --tolerance 0.01 --out "$R/population"
unset SYNTHPOPCAN_PROFILE_WORKERS
export POLARS_MAX_THREADS=${POLARS_THREADS:-2}
run maps geo map "$R/population" --both --person-profile statcan-hierarchical-2021 \
  --boundaries "$SOURCE/cache/geodata/2021-boundary-ct-display-topo.geojson" \
  --geo-column ct --census-vintage 2021 --geo-level ct --geo-namespace statcan:census:2021:ct \
  --out "$R/montreal-cma-2021.html" \
  --title 'Montréal CMA 2021 — synthetic private-household population (CLI only)'
printf '%s COMPLETE\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
