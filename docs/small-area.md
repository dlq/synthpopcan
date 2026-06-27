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
  --geo-dimension ada \
  --geo-column ada \
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
  --geo-column ct
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

`--max-household-size 5` recodes any generated household of size 6 or 7 to 5
before calibration, matching the Census Profile's "5 or more persons" category.

The same pattern works for any Canadian CMA whose provincial model is
available: substitute the CMA code prefix (e.g. `602` for Winnipeg, `205` for
Halifax, `505` for Ottawa) and the matching provincial package
(`manitoba-2016-all-fields-package.json`, etc.).

## Real-Data Runs

Completed runs against private benchmark data, stored under
`data/private/small-area/` (git-ignored):

| Run | Geography | Households | Persons | Controls | Map size |
| --- | --- | ---: | ---: | --- | ---: |
| Montreal CMA | Census tract (`ct`) | 1,830,000 | 4,170,389 | Tenure (`TENUR`) | — |
| Quebec | Aggregate dissemination area (`ada`) | 3,750,000 | 8,330,828 | Tenure (`TENUR`) | — |
| Toronto CMA | Census tract (`ct`) | 2,135,900 | 5,808,776 | Household size + tenure (Census Profile) | 3.2 MB |
| Quebec City CMA | Census tract (`ct`) | 337,994 | 727,586 | Household size + tenure (Census Profile) | — |

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

## Statistical Quality

The outputs are spatially coherent synthetic populations suitable for aggregate
analysis and microsimulation inputs. Understanding what the calibration does and
does not guarantee is important before using them for research.

**What is guaranteed.** The two calibrated margins — household size and tenure
(owner/renter) — are reproduced exactly at every target geography by
construction. IPF converges to near-zero error for both margins at every CT or
ADA. Every geography in the output has the right household-size distribution and
the right owner/renter split.

**What is not calibrated.** All other attributes — person demographics (age,
sex, income, immigrant status, visible minority status), dwelling type, shelter
costs — come from the provincial joint distribution as learned by the tree
model. The model does not know that large households in one CT skew younger
than those in another. It assigns household types weighted to match each
geography's hhsize/tenure profile, but the within-geography conditional
distributions of all other variables are provincial averages, not
geography-specific.

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
