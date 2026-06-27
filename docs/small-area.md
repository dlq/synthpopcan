# Small-Area Linked Synthesis

Small-area linked synthesis bridges two sources that do not contain the same
information:

- prepared linked household/person model packages can generate plausible
  synthetic households and people, but they do not know census tract or ADA
  locations by themselves;
- Census Profile tables contain public small-area totals, but they do not
  contain household/person microdata rows.

The current workflow has four steps:

1. **Generate** candidate linked household/person rows from a model package.
2. **Build controls** from the StatCan Census Profile (household size and tenure
   margins per target geography).
3. **Calibrate** candidate households to those controls, assigning each
   realized household to a census tract or ADA.
4. **Map** the output to a self-contained browser choropleth.

This first pass is intentionally household-first. Person rows inherit geography
from their assigned household. Person-level small-area calibration is a later
quality step.

## Step 0 — Prepare Boundary Files (once)

Before running `geo map`, you need a local boundary file for the target
geography.  `geo prepare-boundaries` downloads the StatCan 2016 boundary ZIP,
extracts the shapefile, and converts it from NAD83 / Statistics Canada Lambert
to WGS-84 GeoJSON in one step.  Run this once per geography level and reuse the
result across all maps.

```bash
synthpopcan geo prepare-boundaries \
  --geo-level ct \
  --out-dir data/boundaries/
```

This writes `data/boundaries/2016-boundary-ct.geojson`.  Pass it directly to
`geo map --boundaries`.  An internet connection is required for the download
(~10–50 MB depending on geography level).

Supported levels: `ct` (census tracts), `ada` (aggregate dissemination areas),
`da` (dissemination areas), `csd` (census subdivisions), `cd` (census
divisions), `pr` (provinces and territories).

If census profile data for controls is not yet downloaded, use the `statcan`
commands:

```bash
synthpopcan statcan census-profile fetch --geo-level ct
```

See `synthpopcan statcan --help` for the full list of available downloads.

## Step 1 — Generate Candidates

```bash
synthpopcan tree generate-from-package MODEL_PACKAGE.json \
  --households 50000 \
  --households-out candidate-households.csv \
  --persons-out candidate-persons.csv \
  --manifest-out candidate-manifest.json \
  --random-seed 462
```

## Step 2 — Build Controls from Census Profile

The `build-controls` command reads a StatCan 2247-variable Census Profile bulk
CSV, extracts household-size (members 52–56: 1, 2, 3, 4, 5-or-more persons) and
tenure (members 1618–1619: owner, renter) margins per geography, scales both to
the target household count, and writes:

- a long-format controls CSV ready for `calibrate-linked`;
- a recoded copy of the candidate CSV with `household_size` capped at 5 to
  match the Census categories.

Geographies missing either margin are dropped automatically, preventing the IPF
dimension-mismatch error in `calibrate-linked`.

```bash
synthpopcan geo build-controls \
  --profile 98-401-X2016044_English_CSV_data.csv \
  --geography-column ada \
  --geo-prefix 35 \
  --target 5500000 \
  --candidates candidate-households.csv
```

| Option | Description |
| --- | --- |
| `--profile` | StatCan Census Profile bulk CSV (2247-variable form). Fetch with `synthpopcan statcan census-profile fetch --geo-level ada`. |
| `--geography-column` | Target geography type: `ada`, `ct`, `csd`, `cd`, or `da`. Determines which `GEO_LEVEL` rows to read. |
| `--target` | Total household count to scale controls to (e.g. 5 500 000). |
| `--candidates` | Household CSV to recode; values above 5 are capped at 5. |
| `--geo-prefix` | Filter to geographies whose ID starts with this prefix. Use the two-digit province code for ADAs (e.g. `35`=Ontario, `24`=Quebec) or the three-digit CMA code for CTs (e.g. `535`=Toronto, `462`=Montreal). |
| `--controls-out` | Output controls CSV. Defaults to `<candidates-stem>-controls-<target>.csv`. |
| `--candidates-out` | Output recoded CSV. Defaults to `<candidates-stem>-recoded.csv`. |

The Census Profile for a given geography level can be downloaded free from
Statistics Canada's Census Profile, 2016 Census page.

## Step 3 — Calibrate to Controls

```bash
synthpopcan geo calibrate-linked \
  --households candidate-households-recoded.csv \
  --persons candidate-persons.csv \
  --controls candidate-households-controls-5500000.csv \
  --geography-dimension ada \
  --geography-column ada \
  --households-out synthetic-households.csv \
  --persons-out synthetic-persons.csv \
  --report small-area-report.json
```

The controls must be a normalized SynthPopCan control CSV. One dimension should
name the target geography, such as `ct` or `ada`. The remaining dimensions must
already exist in the candidate household CSV.

## Step 4 — Explore Results as an Interactive Map

The `map` command generates a self-contained MapLibre GL JS choropleth HTML file
from the synthesis output. It reprojects StatCan LCC boundary shapefiles to
WGS-84 automatically; no external GIS tools are required.

```bash
synthpopcan geo map \
  --households synthetic-households.csv \
  --persons synthetic-persons.csv \
  --boundaries /path/to/lct_000b16a_e.shp \
  --geography-column ct
```

Pass `--boundaries` either as a `.geojson` produced by `geo prepare-boundaries`
or as a path to the original StatCan `.shp` file (reprojection is automatic in
both cases).

The resulting file opens directly in any browser. It requires an internet
connection to fetch base-map tiles from OpenFreeMap but otherwise embeds all
data inline.

Variables shown (household-level, always): household count, average household
size, % homeowners, % detached dwellings, % needing major repairs, median
shelter cost.

Variables shown (person-level, when `--persons` is supplied): person count,
% children (≤14), % seniors (≥65), % immigrants, % visible minority, median
household income.

## Beginner API Shape

The calibration step is also available from the beginner API:

```python
from pathlib import Path

import synthpopcan as spc

summary = spc.calibrate_small_area_linked(
    households=Path("candidate-households-recoded.csv"),
    persons=Path("candidate-persons.csv"),
    controls=Path("candidate-households-controls-5500000.csv"),
    geography_dimension="ada",
    geography_column="ada",
    households_out=Path("synthetic-households.csv"),
    persons_out=Path("synthetic-persons.csv"),
    report_out=Path("small-area-report.json"),
)

summary["assigned_households"], summary["assigned_persons"]
```

Use the API when a notebook needs to keep prose, file choices, and generated
output together. Use the CLI when the output is large enough that streaming CSV
writing and progress feedback are more useful.

## Real-Data Runs

Completed runs against private benchmark data, stored under
`data/private/small-area/` (git-ignored):

| Run | Geography | Households | Persons | Controls | Map size |
| --- | --- | ---: | ---: | --- | ---: |
| Montreal CMA | Census tract (`ct`) | 1,830,000 | 4,170,389 | Tenure (`TENUR`) | — |
| Quebec | Aggregate dissemination area (`ada`) | 3,750,000 | 8,330,828 | Tenure (`TENUR`) | — |
| Toronto CMA | Census tract (`ct`) | 2,135,900 | 5,808,776 | Household size + tenure (Census Profile) | 3.2 MB |

The Toronto run was the first to use the full `build-controls` → `calibrate-linked` → `map`
pipeline. Controls were built from the 2016 Census Profile for CTs (2247-variable
bulk CSV, CMA prefix `535`), scaled to 2,135,910 households (the Toronto CMA
census total). 1,146 census tracts were calibrated; 0 were dropped for missing
margins.

All linked outputs passed `synthpopcan validate linked-output`.

The person counts are model-derived. They were not forced to exact official
population totals in this first pass. For example, the Quebec run creates
3,750,000 households and 8,330,828 people because persons are generated from the
household/person package and then copied into calibrated households.

## Current Limits

The current implementation is useful, but still a prototype for substantive
small-area analysis:

- it fits household-level controls only;
- persons inherit the assigned household geography;
- candidate-pool size affects the variety available inside each small area;
- DA-level runs are expected to be sparser than ADA-level runs and need stronger
  diagnostics.

The next quality work belongs in `PLANS.md`: person-level validation and
calibration, richer control mapping helpers, better residual diagnostics, and
performance guidance for province-scale runs.
