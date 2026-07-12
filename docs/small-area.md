# Small-Area Linked Synthesis

Statistics Canada divides Canada into a nested hierarchy of geographic units.
The ones relevant to this workflow are:

- **Census tract (CT):** a small, relatively stable urban area containing
  roughly 2,500–8,000 people. Census tracts exist only in census metropolitan
  areas and census agglomerations — large and medium-sized cities.
- **Aggregate dissemination area (ADA):** a grouping of dissemination areas
  designed to cover all of Canada, including rural areas where census tracts
  do not exist. ADAs typically contain 5,000–15,000 people.
- **Dissemination area (DA):** the smallest standard geographic unit for which
  Statistics Canada releases census data, typically 400–700 people. DAs are
  building blocks for ADAs.

```{figure} _static/geography-ladder.svg
:alt: A Canadian census geography ladder showing broad geographies, CT, ADA, and DA calibration geographies, and DB placement later.
:align: center

For SynthPopCan, CT, ADA, and DA are calibration geographies. Dissemination
blocks are useful later for spatial placement after households have been
calibrated to a larger small area.
```

Small-area synthesis **assigns generated households** to one of these units.
The Census Profile provides the public aggregate totals, or **controls**, that
anchor each unit's household composition, and the workflow uses those controls
to decide which generated candidates go where.

Small-area linked synthesis bridges **two sources that do not contain the same
information**:

- prepared linked household/person model packages can generate plausible
  synthetic households and people, but they do not know census tract or ADA
  locations by themselves;
- Census Profile tables contain public small-area totals, but they do not
  contain household/person microdata rows.

The current workflow has four steps:

1. **Generate** candidate linked household/person rows from a model package.
1. **Build controls** from the StatCan Census Profile (household size and tenure
   margins per target geography).
1. **Calibrate** candidate households to household controls and, when supplied,
   linked-person controls, assigning each realized household to a census tract
   or ADA.
1. **Map** the output to a self-contained browser choropleth.

Calibration remains **household-first**. Person rows inherit geography from
their assigned household. Optional person controls refine the household weights
using linked-person category counts; they never separate people from their
household.

## Step 0 — Prepare Boundary Files (once)

Before running `geo map`, we need a local boundary file for the target
geography. `geo prepare-boundaries` downloads the StatCan 2016 boundary ZIP,
extracts the shapefile, and converts it from NAD83 / Statistics Canada Lambert
to WGS-84 GeoJSON in one step. Run this once per geography level and reuse the
result across all maps.

```bash
synthpopcan geo prepare-boundaries \
  --geo-level ct \
  --out-dir data/boundaries/
```

This writes `data/boundaries/2016-boundary-ct.geojson`. Pass it directly to
`geo map --boundaries`. An internet connection is required for the download
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
- a recoded copy of the candidate CSV with a `household_size_group` column
  where 5, 6, 7, and larger households are grouped as `5`, matching the Census
  categories while preserving the exact `household_size` column.

Geographies missing either margin are dropped automatically, preventing the IPF
dimension-mismatch error in `calibrate-linked`.

```bash
synthpopcan geo build-controls \
  --profile 98-401-X2016044_English_CSV_data.csv \
  --geo-column ada \
  --geo-prefix 35 \
  --target 5500000 \
  --candidates candidate-households.csv
```

| Option | Description |
| --- | --- |
| `--profile` | StatCan Census Profile bulk CSV (2247-variable form). Fetch with `synthpopcan statcan census-profile fetch --geo-level ada`. |
| `--geo-column` | Target geography type: `ada`, `ct`, `csd`, `cd`, or `da`. Determines which `GEO_LEVEL` rows to read. |
| `--target` | Total household count to scale controls to (e.g. 5 500 000). |
| `--candidates` | Household CSV to recode; exact `household_size` is preserved and `household_size_group` is added for Census Profile controls. |
| `--geo-prefix` | Filter to geographies whose ID starts with this prefix. Use the two-digit province code for ADAs (e.g. `35`=Ontario, `24`=Quebec) or the three-digit CMA code for CTs (e.g. `535`=Toronto, `462`=Montreal). |
| `--controls-out` | Output controls CSV. Defaults to `<candidates-stem>-controls-<target>.csv`. |
| `--candidates-out` | Output recoded CSV. Defaults to `<candidates-stem>-recoded.csv`. |

The Census Profile for a given geography level can be downloaded free from
[Statistics Canada's Census Profile, 2016 Census](https://www12.statcan.gc.ca/census-recensement/2016/dp-pd/prof/index.cfm?Lang=E) page.

## Step 2.5 — Estimate Run Size

Before launching a large calibration, use `geo estimate-run` to check the scale
of the job. The command reads the controls, counts target geographies and
households, estimates person rows, and gives a plain recommendation about
whether to use the web app, CLI, or Python API.

```bash
synthpopcan geo estimate-run \
  --controls candidate-households-controls-5500000.csv \
  --geo-dimension ada \
  --candidate-households 50000 \
  --pool-size 10000
```

Example summary:

```text
Target geographies: 1,115
Target households: 3,750,000
Estimated persons: 8,325,000
Estimated output rows: 12,075,000
Calibration pool: 10,000 of 50,000 candidates
Fits to run: 1,115
Recommended surface: CLI or Python API
Guidance:
  - Calibration will fit 10,000 candidate households for each target geography.
  - Keep the web app for small demos; use the CLI or Python API for large linked CSV outputs.
```

Use `--format json` when a notebook, shell script, or workflow manager needs the
same information in machine-readable form. For exploratory province-scale runs,
start with `--pool-size 10000`; increase it only if validation reports show poor
fit or too little household variety.

When `--pool-size` is smaller than the candidate pool, calibration draws a random
subsample of candidates. That draw is reproducible by default (seed `42`), and
the effective seed is recorded in the calibration report's `subsample` block. To
check how sensitive the aggregate results are to which candidates were drawn, run
the calibration a few times with different `--subsample-seed` values and compare
the reports. Without `--pool-size`, the full pool is used and the seed has no
effect.

Contributors can exercise the tracked calibration benchmark with:

```bash
uv run python scripts/benchmarks.py small-area
uv run python scripts/benchmarks.py small-area --province-scale
```

The province-scale profile records 10,000 retained candidates, 1,200 target
geographies, 4.5 million target households, a 180-second fit budget, and a
512 MiB retained-weight budget. Timing is opt-in because it depends on the
machine; fixture shape and memory estimates are checked by the default tests.

## Step 3 — Calibrate to Controls

```bash
synthpopcan geo calibrate-linked \
  --households candidate-households-recoded.csv \
  --persons candidate-persons.csv \
  --controls candidate-households-controls-5500000.csv \
  --geo-dimension ada \
  --geo-column ada \
  --households-out synthetic-households.csv \
  --persons-out synthetic-persons.csv \
  --report small-area-report.json
```

When compatible person margins are available, add a second normalized control
file:

```bash
synthpopcan geo calibrate-linked \
  --households candidate-households-recoded.csv \
  --persons candidate-persons.csv \
  --controls household-controls.csv \
  --person-controls person-age-sex-controls.csv \
  --geo-dimension ada \
  --geo-column ada \
  --households-out synthetic-households.csv \
  --persons-out synthetic-persons.csv \
  --report small-area-report.json
```

Household controls are fitted first. The optional second stage uses iterative
proportional updating over household indicators and linked-person category
counts. It changes household weights, never individual person weights, so a
selected household always carries all of its linked people into the assigned
geography.

`geo synthesize-from-package` accepts the same `--person-controls` option when
generation and calibration should remain one command.

The controls must be a normalized SynthPopCan control CSV. One dimension should
name the target geography, such as `ct` or `ada`. The remaining dimensions must
already exist in the candidate household CSV.

Before fitting, SynthPopCan checks that candidate rows contain the
non-geography control columns, categories, and supported cross-category cells.
It also reports inconsistent margin totals, sparse target geographies, sparse
candidate support, and person rows with missing or orphaned household links. If
the household controls require
`household_size_group`, for example, but the candidates only have exact
`household_size`, the command stops with a specific fix instead of failing deep
inside the IPF step.

When controls come from Census Profile household-size categories, the household
size dimension is usually `household_size_group`, not exact `household_size`.
The grouped column lets IPF fit the public `5 or more persons` category without
throwing away the exact size of generated households.

The JSON report includes input checks, a top-level convergence summary, and a
`largest_residuals` list. With person controls it labels every margin as
`household` or `person`, and reports both the fractional fit and the realized
integer household selection. Start with those rows when reviewing fit quality:
each residual names the geography, margin, category, target total, fitted total,
and remaining difference after calibration. Non-converged geographies usually
mean the controls conflict, categories were not mapped consistently, or the
candidate pool does not contain enough matching household types.

## Step 4 — Explore Results as an Interactive Map

The `map` command generates a self-contained MapLibre GL JS choropleth HTML file
from the synthesis output. It reprojects StatCan LCC boundary shapefiles to
WGS-84 automatically; no external GIS tools are required.

```bash
synthpopcan geo map \
  --households synthetic-households.csv \
  --persons synthetic-persons.csv \
  --boundaries /path/to/lct_000b16a_e.shp \
  --geo-column ct
```

Pass `--boundaries` either as a `.geojson` produced by `geo prepare-boundaries`
or as a path to the original StatCan `.shp` file (reprojection is automatic in
both cases).

The resulting file opens directly in any browser. It requires an internet
connection to fetch base-map tiles from [OpenFreeMap](https://openfreemap.org/) but otherwise embeds all
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
    person_controls=Path("person-age-sex-controls.csv"),  # optional
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

## Example: Quebec City CMA at Census-Tract Level

Quebec City (CMA 421) is a good illustration of the full two-command workflow.
The PUMF does not contain a Quebec City CMA code — only the five largest CMAs
are individually coded in the public microdata. But the Quebec provincial model
covers all Quebec households, and the publicly available 2016 Census Profile
contains CT-level household-size and tenure margins for every CMA in Canada.
Together they are enough to produce a calibrated, CT-level synthetic population
for Quebec City.

**Prerequisites:**

- Quebec provincial model package (installed or downloaded):
  `quebec-2016-all-fields-package.json`
- National CT Census Profile CSV:
  `98-401-X2016043_English_CSV_data.csv`
  (download free from StatCan, or use `synthpopcan statcan census-profile fetch --geo-level ct`)

**Step 1 — Build CT controls (Quebec City prefix = 421)**

```bash
synthpopcan geo build-controls \
  --profile 98-401-X2016043_English_CSV_data.csv \
  --geo-column ct \
  --geo-prefix 421 \
  --target 338000 \
  --controls-out quebec-city-ct-controls.csv
```

This extracts 181 census tracts and scales household-size and tenure margins
to 338 000 households (the approximate 2016 Quebec City CMA total).

**Step 2 — Generate candidates and calibrate**

```bash
synthpopcan geo synthesize-from-package \
  quebec-2016-all-fields-package.json \
  --households 338000 \
  --controls quebec-city-ct-controls.csv \
  --geo-dimension ct \
  --geo-column ct \
  --max-household-size 5 \
  --households-out quebec-city-synthetic-households.csv \
  --persons-out quebec-city-synthetic-persons.csv \
  --report quebec-city-calibration-report.json
```

`--max-household-size 5` adds a `household_size_group` column before calibration
so generated households of size 5, 6, 7, and larger all fit the Census
Profile's "5 or more persons" category. The original exact `household_size`
column remains in the household output.

The same pattern works for any Canadian CMA whose provincial model is
available: substitute the CMA code prefix (e.g. `602` for Winnipeg, `205` for
Halifax, `505` for Ottawa) and the matching provincial package
(`manitoba-2016-all-fields-package.json`, etc.).

## Statistical Quality

The outputs are spatially coherent synthetic populations suitable for aggregate
analysis and microsimulation inputs. Understanding what the calibration does and
does not guarantee is important before using them for research.

**What is guaranteed.** Converged fractional household weights reproduce the
supplied household margins to the requested tolerance. When person controls are
provided, the joint refinement also reproduces those linked-person margins to
the requested tolerance while preserving whole households. The report checks
the final integerized household selection separately because integerization can
reintroduce small residuals.

**What is not calibrated.** Attributes absent from either control file still
come from the broad-geography joint distribution learned by the model. Adding
age and sex controls, for example, does not calibrate income, immigration
status, visible-minority status, or shelter costs. Within-geography
distributions for uncontrolled attributes remain model estimates, not observed
small-area facts.

**Practical guidance.**

These outputs are appropriate for:

- agent-based models or microsimulations that need geographically anchored
  synthetic microdata as input;
- housing policy or service-demand scenarios where household size and tenure
  are the primary drivers;
- estimating how many households of a given type live in each geography when
  no better data is available.

Use caution for:

- CT- or ADA-level analysis of non-calibrated variables (e.g. income
  distribution or visible-minority composition by tract);
- drawing conclusions about specific geographies from individual synthetic
  records;
- any claim requiring person-level geographic accuracy.

**Comparison to alternatives.** These populations are better than drawing a
provincial random sample and assigning geographies at random, because the
geographic distribution reflects real Census structure. They are not as
accurate as a synthetic population calibrated on many margins (age × sex ×
geography, income × geography, etc.), which would require either restricted
master-file access or substantially more Census Profile variables as controls.
Most published synthetic population work operates at roughly this level of
calibration.

## Current Limits

- Person controls adjust household selection; SynthPopCan does not detach or
  independently reweight people inside a household.
- Household and person controls must cover the same target geographies and
  describe compatible population universes and reference periods.
- Candidate-pool size limits the household combinations available inside each
  small area. Sparse-support warnings should be treated as substantive review
  findings, not cosmetic messages.
- Integerization can leave small realized residuals even when the fractional
  joint fit converges; both summaries belong with the output.
- DA-level runs remain more disclosure-sensitive and structurally sparse than
  CT- or ADA-level runs.
