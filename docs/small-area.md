# Small-Area Linked Synthesis

Small-area linked synthesis is the workflow we use **after** we have generated
linked household/person candidate rows and **before** we want to interpret those
rows geographically. It assigns whole generated households to public census
geographies while keeping their linked person rows attached.

Use this page when the research question needs statements like "how many
synthetic households of each type are assigned to each census tract, aggregate
dissemination area, or dissemination area?" Do not use it as the first
generation step. Start with {doc}`tree-generate` when we still need candidate
households and people, and start with {doc}`controls` or {doc}`statcan` when we
still need to prepare public control totals.

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

```{admonition} Census tracts do not cover all of Canada
:class: note

CTs cover qualifying metropolitan areas and census agglomerations, not the
whole country. For province-wide or Canada-wide synthesis, use a wall-to-wall
geography such as **ADA** or **DA**, depending on the detail the research needs
and the controls the seed can support.
```

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
  synthetic households and people, but they do not know CT, ADA, or DA
  locations by themselves;
- Census Profile tables contain public small-area totals, but they do not
  contain household/person microdata rows.

The current workflow has six steps:

1. **Prepare boundaries** once when we want to map the result.
1. **Generate** candidate linked household/person rows from a model package.
1. **Build controls** from the StatCan Census Profile (household size and tenure
   margins per target geography).
1. **Estimate** the run size before launching a large calibration.
1. **Calibrate** candidate households to household controls and, when supplied,
   linked-person controls, assigning each realized household to a CT, ADA, or
   DA.
1. **Map** the output to a self-contained browser choropleth.

Calibration remains **household-first**. Person rows inherit geography from
their assigned household. Optional person controls refine the household weights
using linked-person category counts; they never separate people from their
household.

## Worked Workflow

**Runnable research workflow; network and time required.** The steps below use
the reviewed Quebec package and public 2016 Census Profile controls to produce a
census-tract population for Quebec City CMA (`421`). Enter them in order from
one project working directory. The downloads are public, but substantially
larger than the fictional installation and IPF examples.

The `338,000` household target makes the walkthrough concrete and runnable; it
is an illustrative rounded value, not a value SynthPopCan derives. For research
use, replace it with a target appropriate to the project's population universe
and keep the source citation with the controls.

(step-0-prepare-boundary-files-once)=

```{rubric} Step 0 — Prepare Boundary Files (once)
:class: workflow-step
```

Before running `geo map`, we need a local CT boundary file. `geo boundaries`
downloads the selected StatCan boundary ZIP,
extracts the shapefile, and converts it from NAD83 / Statistics Canada Lambert
to WGS-84 GeoJSON in one step. Run this once per geography level and reuse the
result across all maps.

```bash
synthpopcan geo boundaries \
  --geo-level ct \
  --out-dir data/derived/statcan/census/2016/boundaries/
```

This writes
`data/derived/statcan/census/2016/boundaries/2016-boundary-ct.geojson`. Pass it
directly to `geo map --boundaries`. An internet connection is required for the
download (~10–50 MB depending on geography level).

Supported levels: `ct` (census tracts), `ada` (aggregate dissemination areas),
`da` (dissemination areas), `csd` (census subdivisions), `cd` (census
divisions), `pr` (provinces and territories).

For 2016 CT and ADA products, the prepared GeoJSON retains every boundary-file
attribute. CT features include tract name, province, and CMA/CA identifiers and
names; ADA features include province and census-division identifiers and names.
The 2016 files predate DGUID and do not contain `LANDAREA`, so those fields must
not be inferred from the 2021 schema.

For a 2021 workflow, select the matching census vintage explicitly:

```bash
synthpopcan geo boundaries \
  --census-year 2021 \
  --geo-level ct \
  --out-dir data/derived/statcan/census/2021/boundaries/

synthpopcan geo boundaries \
  --census-year 2021 \
  --geo-level ada \
  --out-dir data/derived/statcan/census/2021/boundaries/

synthpopcan geo boundaries \
  --census-year 2021 \
  --geo-level csd \
  --out-dir data/derived/statcan/census/2021/boundaries/
```

These write national `2021-boundary-ct.geojson`, `2021-boundary-ada.geojson`,
and `2021-boundary-csd.geojson` files under
`data/derived/statcan/census/2021/boundaries/`. The CT product
contains all tracts in Canada's tracted CMAs and CAs; smaller untracted CAs
have no CTs. The ADA product covers all of Canada. Both retain StatCan's 2021
`DGUID`, authoritative land area in square kilometres (`LANDAREA`), and
province/territory code (`PRUID`) alongside the short geography identifier.
Keep boundary and Census Profile/control vintages aligned; do not calibrate
2021 controls against 2016 geography.

CSDs are the municipal or municipal-equivalent layer used for local public
health, service-access, and resource-allocation analysis. Fetch the national
profile and extract a province or other identifier-prefix slice as follows:

```bash
synthpopcan statcan census-profile fetch \
  --year 2021 \
  --geo-level csd-all \
  --out-dir data/raw/statcan/census/2021/profiles/csd/national/

synthpopcan geo controls \
  --profile data/raw/statcan/census/2021/profiles/csd/national/2021-census-profile-csd-all.csv \
  --geo-column csd \
  --geo-prefix 24 \
  --target TARGET_HOUSEHOLDS \
  --candidates candidates/
```

Here `24` selects Quebec CSD identifiers; use the corresponding two-digit
province or territory code for another region. Every CSD returned by the
current 2016 and 2021 control extraction joins to its vintage's national
boundary file. Some boundary features lack a complete household-size and
tenure vector because of empty geographies, suppression, or unavailable
characteristics, and are therefore intentionally omitted from calibration.

The national ADA geometry is detailed and much larger than the CT product. For
countrywide overview maps, `--coord-precision 3` reduces conversion time and
output size; retain the default precision when the extra spatial detail is
actually required. StatCan's [2021 Dissemination Geographies Relationship
File](https://www150.statcan.gc.ca/n1/en/catalogue/98260004) supplies the
official DGUID links from these areas to higher census geography levels.
Download its final 2021 CSV and provenance manifest with:

```bash
synthpopcan geo relationship-file \
  --out-dir data/raw/statcan/census/2021/geography/relationships/
```

Download the matching CT Census Profile at the same time:

```bash
synthpopcan statcan census-profile fetch \
  --geo-level ct \
  --out-dir data/raw/statcan/census/2016/profiles/ct
```

This writes
`data/raw/statcan/census/2016/profiles/ct/2016-census-profile-ct.csv` and a
provenance manifest beside it. Both commands in this step require a network
connection.

(step-1-generate-candidates)=

```{rubric} Step 1 — Generate Candidates
:class: workflow-step
```

```bash
synthpopcan models fetch quebec-2016-all-fields

synthpopcan models generate quebec-2016-all-fields \
  --households 50000 \
  --out candidates/ \
  --random-seed 421
```

The fetch requires a network connection the first time. Later runs reuse the
verified package in the local model cache. Candidate generation writes
`candidates/households.csv`, `candidates/persons.csv`, and `manifest.json`.

(step-2-build-controls-from-census-profile)=

```{rubric} Step 2 — Build Controls from Census Profile
:class: workflow-step
```

The `geo controls` command reads a StatCan 2247-variable Census Profile bulk
CSV, extracts household-size (members 52–56: 1, 2, 3, 4, 5-or-more persons) and
tenure (members 1618–1619: owner, renter) margins per geography, scales both to
the target household count, and writes:

- a long-format controls CSV ready for `geo calibrate`;
- a recoded linked-population directory whose `households.csv` has a
  `household_size_group` column
  where 5, 6, 7, and larger households are grouped as `5`, matching the Census
  categories while preserving the exact `household_size` column.

Geographies missing either margin are dropped automatically, preventing the IPF
dimension-mismatch error in `geo calibrate`.

```bash
synthpopcan geo controls \
  --profile data/raw/statcan/census/2016/profiles/ct/2016-census-profile-ct.csv \
  --geo-column ct \
  --geo-prefix 421 \
  --target 338000 \
  --candidates candidates/
```

This writes `candidates-controls-338000.csv` and `candidates-recoded/`. The
controls describe Quebec City census tracts; the recoded candidate households
contain `household_size_group` for the public five-or-more household-size
category while retaining exact `household_size`.

| Option | Description |
| --- | --- |
| `--profile` | StatCan Census Profile bulk CSV (2247-variable form). This walkthrough fetches the CT product in Step 0. |
| `--geo-column` | Target geography type: `ada`, `ct`, `csd`, `cd`, or `da`. Determines which `GEO_LEVEL` rows to read. |
| `--target` | Total household count to scale controls to (338 000 for this Quebec City example). |
| `--candidates` | Linked population directory to recode; exact `household_size` is preserved and `household_size_group` is added for Census Profile controls. |
| `--geo-prefix` | Filter to geographies whose ID starts with this prefix. Use the two-digit province code for ADAs (e.g. `35`=Ontario, `24`=Quebec) or the three-digit CMA code for CTs (e.g. `535`=Toronto, `462`=Montreal). |
| `--controls-out` | Output controls CSV. Defaults to `<candidates-name>-controls-<target>.csv`. |
| `--candidates-out` | Output recoded linked-population directory. Defaults to `<candidates-name>-recoded`. |

The Census Profile for a given geography level can be downloaded free from
[Statistics Canada's Census Profile, 2016 Census](https://www12.statcan.gc.ca/census-recensement/2016/dp-pd/prof/index.cfm?Lang=E) page.

(step-2-5-estimate-run-size)=

```{rubric} Step 2.5 — Estimate Run Size
:class: workflow-step
```

Before launching a large calibration, use `geo estimate` to check the scale
of the job. The command reads the controls, counts target geographies and
households, estimates person rows, and gives a plain recommendation about
whether to use the web app, CLI, or Python API.

```bash
synthpopcan geo estimate \
  --controls candidates-controls-338000.csv \
  --geo-dimension ct \
  --candidate-households 50000 \
  --pool-size 10000
```

Example summary:

```text
Target geographies: 181
Target households: 338,000
Estimated persons: 750,360
Estimated output rows: 1,088,360
Calibration pool: 10,000 of 50,000 candidates
Fits to run: 181
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
the effective seed and input/selected row counts are recorded in the calibration
report's `subsample` block. To check how sensitive the aggregate results are to
which candidates were drawn, run the calibration a few times with different
`--subsample-seed` values and compare the reports. Candidate generation remains
controlled separately by `--random-seed`. Without `--pool-size`, the full pool is
used and the subsample seed has no effect.

(step-3-calibrate-to-controls)=

```{rubric} Step 3 — Calibrate to Controls
:class: workflow-step
```

```bash
synthpopcan geo calibrate candidates-recoded/ \
  --controls candidates-controls-338000.csv \
  --geo-dimension ct \
  --geo-column ct \
  --pool-size 10000 \
  --out quebec-city-population/
```

When compatible person margins are available, add a second normalized control
file. **Template: replace the optional person-control path** with a file that
describes the same Quebec City CT universe:

```bash
synthpopcan geo calibrate candidates-recoded/ \
  --controls candidates-controls-338000.csv \
  --person-controls quebec-city-ct-age-sex-controls.csv \
  --geo-dimension ct \
  --geo-column ct \
  --pool-size 10000 \
  --out quebec-city-population-with-person-controls/
```

Household controls are fitted first. The optional second stage uses iterative
proportional updating over household indicators and linked-person category
counts. It changes household weights, never individual person weights, so a
selected household always carries all of its linked people into the assigned
geography.

`geo synthesize` accepts the same `--person-controls` option when
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

(step-4-explore-results-as-an-interactive-map)=

```{rubric} Step 4 — Explore Results as an Interactive Map
:class: workflow-step
```

The `map` command generates a self-contained MapLibre GL JS choropleth HTML file
from the synthesis output. It reprojects StatCan LCC boundary shapefiles to
WGS-84 automatically; no external GIS tools are required.

```bash
synthpopcan geo map quebec-city-population/ \
  --boundaries data/derived/statcan/census/2016/boundaries/2016-boundary-ct.geojson \
  --geo-column ct \
  --out quebec-city-ct-map.html \
  --title "Synthetic Quebec City Households"
```

Pass `--boundaries` either as a `.geojson` produced by `geo boundaries`
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

## Command Reference

### `geo boundaries`

Downloads a Statistics Canada boundary ZIP for a geography level, extracts the
shapefile, and writes a WGS-84 GeoJSON file for `geo map`.

```bash
synthpopcan geo boundaries \
  --census-year 2021 \
  --geo-level ada \
  --out-dir data/derived/statcan/census/2021/boundaries
```

Important options:

- `--geo-level`: boundary geography to prepare. Supported values include `ct`,
  `ada`, `da`, `csd`, `cd`, and `pr` for 2016. The current 2021 catalogue
  supports the national `ct`, `ada`, and `csd` products.
- `--census-year`: boundary vintage, either `2016` (the default for backward
  compatibility) or `2021`.
- `--out-dir`: directory for the prepared GeoJSON file.
- `--coord-precision`: coordinate precision for the written GeoJSON.
- `--url`: optional alternate StatCan ZIP URL, useful when a project maintains
  a documented local mirror.

Run this once per geography level and reuse the resulting file. The command
needs an internet connection for the boundary download.

### `geo relationship-file`

Downloads and extracts the final 2021 Dissemination Geographies Relationship
File. Its dissemination-block-level rows connect the `DGUID` retained in CT
and ADA boundaries to CMA/CA, province/territory, census division, census
subdivision, and other supported parent geographies.

```bash
synthpopcan geo relationship-file \
  --out-dir data/raw/statcan/census/2021/geography/relationships
```

### `geo controls`

Builds household-size and tenure controls from a Census Profile bulk CSV.
When `--candidates` is supplied, it also writes a linked population directory
whose household file includes a Census-compatible `household_size_group` column.

```bash
synthpopcan geo controls \
  --profile 98-401-X2016044_English_CSV_data.csv \
  --geo-column ada \
  --geo-prefix 24 \
  --target 3800000 \
  --candidates candidates/
```

Important options:

- `--profile`: Census Profile bulk CSV.
- `--geo-column`: target geography type, such as `ada`, `ct`, `csd`, `cd`, or
  `da`.
- `--target`: total household count used to scale the controls.
- `--geo-prefix`: optional prefix filter. Use province codes for ADAs and CMA
  codes for CTs.
- `--geo-level-value`: override the profile's `GEO_LEVEL` value only for a
  non-standard profile; ordinary 2016 bulk downloads are detected from
  `--geo-column`.
- `--controls-out`: explicit controls CSV path.
- `--candidates-out`: explicit recoded linked-population directory when
  `--candidates` is supplied.
- `--hhsize-cap`: household-size grouping cap, usually `5` for Census Profile
  controls.
- `--household-size-group-column`: grouped-size column name, default
  `household_size_group`.

### `geo estimate`

Estimates the size of a small-area run before calibration. Use it to decide
whether a run belongs in the web app, command line, or Python API.

```bash
synthpopcan geo estimate \
  --controls candidates-controls-5500000.csv \
  --geo-dimension ada \
  --candidate-households 50000 \
  --pool-size 10000
```

Important options:

- `--controls`: normalized controls CSV with one geography dimension.
- `--geo-dimension`: geography dimension in the controls, such as `ct` or
  `ada`.
- `--candidate-households`: planned candidate household count.
- `--pool-size`: optional calibration subsample size.
- `--average-persons-per-household`: person-row estimate used for planning.
- `--format summary|json`: readable summary or machine-readable estimate.

### `geo calibrate`

Calibrates an existing linked household/person population directory to household
controls, and optionally to compatible linked-person controls.

```bash
synthpopcan geo calibrate candidates-recoded/ \
  --controls household-controls.csv \
  --person-controls person-age-sex-controls.csv \
  --geo-dimension ada \
  --geo-column ada \
  --out synthetic-population/
```

Important options:

- `POPULATION`: directory containing candidate `households.csv` and `persons.csv`.
- `--controls`: household controls with a target geography dimension.
- `--person-controls`: optional person controls for joint household-weight
  refinement.
- `--geo-dimension`: geography dimension in the controls.
- `--geo-column`: geography column written to the assigned outputs.
- `--include-weights`: also write the potentially large `weights.csv` artifact.
- `--out`: directory for calibrated `households.csv`, `persons.csv`, and
  `report.json`.
- `--pool-size`: optional maximum number of candidate households used in each
  fit.
- `--subsample-seed`: reproducible seed for the `--pool-size` candidate
  subsample.
- `--max-iterations`: maximum IPF iterations for each geography; the default is
  `100`.
- `--tolerance`: convergence tolerance for each geography; the default is
  `1e-6`.
- `--format summary|json`: printed report format.

### `geo synthesize`

Generates linked candidates from a package and calibrates them in one command.
Use this when we do not need to inspect or keep an intermediate candidate
population directory.

```bash
synthpopcan geo synthesize montreal-cma-2016-all-fields \
  --households 100000 \
  --controls ct-controls.csv \
  --geo-dimension ct \
  --geo-column ct \
  --max-household-size 5 \
  --out synthetic-population/
```

Important options:

- `PACKAGE`: local linked model package JSON or model ID from `models list`.
- `--households`: candidate household count generated before calibration.
- `--controls`: household controls with a target geography dimension.
- `--person-controls`: optional linked-person controls.
- `--geo-dimension`: geography dimension in the controls.
- `--geo-column`: geography column written to the assigned outputs; defaults to
  `--geo-dimension`.
- `--out`: directory for calibrated `households.csv`, `persons.csv`, and
  `report.json`.
- `--include-weights`: also write the potentially large fitted weights CSV.
- `--random-seed`: candidate generation seed.
- `--pool-size`: optional maximum number of candidates used for calibration.
- `--subsample-seed`: reproducible seed for the calibration subsample.
- `--max-household-size`: group exact household sizes into a top-coded category,
  usually `5` for Census Profile controls.
- `--household-size-group-column`: grouped-size column used for calibration.
- `--format summary|json`: printed report format.

### `geo map`

Writes a self-contained HTML map from calibrated household/person outputs.

```bash
synthpopcan geo map synthetic-population/ \
  --boundaries data/derived/statcan/census/2016/boundaries/2016-boundary-ct.geojson \
  --geo-column ct \
  --out synthetic-ct-map.html
```

Important options:

- `POPULATION`: calibrated population directory, or an assigned household CSV.
- `--persons`: optional assigned person CSV for person-level map variables.
- `--boundaries`: StatCan shapefile, directory containing a shapefile, or
  prepared GeoJSON.
- `--geo-column`: geography ID column in the household CSV.
- `--geo-id-field`: boundary attribute matching the household geography ID.
- `--out`: destination HTML file.
- `--title`: title shown in the map panel.
- `--coord-precision`: output coordinate precision.

## Beginner API Shape

**Continue from the worked workflow.** The calibration step is also available
from the beginner API using the candidate, control, and boundary artifacts
created above:

```python
from pathlib import Path

import synthpopcan as spc

population = spc.LinkedPopulationFiles(
    households=Path("candidates-recoded/households.csv"),
    persons=Path("candidates-recoded/persons.csv"),
)
result = spc.calibrate_small_area(
    population,
    Path("candidates-controls-338000.csv"),
    geography_dimension="ct",
    output_dir=Path("quebec-city-api-population"),
    pool_size=10_000,
)

result.assigned_households, result.assigned_persons, result.converged
```

After calibration, the beginner API can also render the same kind of standalone
map as `geo map`:

```python
spc.render_small_area_map(
    households=result,
    boundaries="data/derived/statcan/census/2016/boundaries/2016-boundary-ct.geojson",
    geography_column="ct",
    geography_id_field="CTUID",
    out="quebec-city-api-map.html",
    title="Synthetic Quebec City Households",
)
```

Use the API when a notebook needs to keep prose, file choices, and generated
output together. Use the CLI when the output is large enough that streaming CSV
writing and progress feedback are more useful.

## Adapt the Walkthrough to Another CMA

The worked workflow uses Quebec City because it demonstrates an important
relationship between public sources. The PUMF does not identify Quebec City as
one of its individually coded CMAs, but the reviewed Quebec provincial package
can supply candidate household/person relationships, while the national Census
Profile supplies CT controls for CMA `421`.

The same pattern works for another Canadian CMA when a suitable provincial
package is available. Replace all of the following together:

- the reviewed model-package ID;
- the three-digit CMA prefix passed to `--geo-prefix`;
- the target household total and its citation;
- output names and method notes.

For example, Winnipeg uses prefix `602`, Halifax uses `205`, and Ottawa–Gatineau
uses `505`. Confirm the appropriate package with `synthpopcan models show`, and
do not assume that a provincial candidate model automatically represents every
local relationship equally well.

## Statistical Quality

When the fit converges and the diagnostics are acceptable, the outputs can be
useful for **aggregate exploration** and as inputs to carefully validated
microsimulations. That is a conditional research use, not a general guarantee
of suitability. Understanding what the calibration does and does not establish
is essential before using the result.

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

Potential uses, after substantive validation, include:

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

**Comparison to alternatives.** For the variables actually controlled,
calibration preserves more published geographic structure than assigning a
provincial sample to areas at random. That does not establish accuracy for
uncontrolled variables. Adding more well-matched margins can constrain more of
the result, but it can also expose incompatible totals, sparse candidate
support, and new disclosure concerns. Comparative research shows that method
performance depends on spatial scale, constraints, and the population being
modelled; there is no single calibration depth that characterizes the field or
guarantees a good result.

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

## Further Reading

- Statistics Canada's [2016 census geography chapter](https://www12.statcan.gc.ca/census-recensement/2016/ref/98-304/chap12-eng.cfm)
  explains how CTs, ADAs, DAs, CSDs, and other dissemination geographies relate.
- Tanton and Edwards' [introduction to spatial microsimulation](https://doi.org/10.1007/978-94-007-4623-7_1)
  places small-area population construction in its broader methodological
  history.
- Harland et al., [“Creating Realistic Synthetic Populations at Varying Spatial
  Scales”](https://doi.org/10.18564/jasss.1909), compares synthesis techniques
  and emphasizes that performance changes with method and geography.
- Chapuis, Taillandier, and Drogoul's [review of synthetic-population methods and
  practices](https://doi.org/10.18564/jasss.4762) surveys later approaches and
  their use in social simulation.
- Prédhumeau and Manley's [Canadian national synthetic-population
  study](https://doi.org/10.1038/s41597-023-02030-4) demonstrates province-by-province
  DA synthesis and validates a projected 2021 population at DA, city, and
  national scales; its [dataset record](https://doi.org/10.5281/zenodo.7572117)
  documents the released years, scenarios, files, and licence.
