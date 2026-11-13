# Small-Area Execution and Command Reference

Small-area linked synthesis is the workflow we use **after** we have generated
linked household/person candidate rows and **before** we want to interpret those
rows geographically. It assigns whole generated households to public census
geographies while keeping their linked person rows attached.

Use this page when the research question needs statements like "how many
synthetic households of each type are assigned to each census tract, aggregate
dissemination area, dissemination area, or census subdivision?" Do not use it as the first
generation step. Start with {doc}`tree-generate` when we still need candidate
households and people, and start with {doc}`controls` or {doc}`statcan` when we
still need to prepare public control totals.

Statistics Canada divides Canada into a nested hierarchy of geographic units.
The ones relevant to this workflow are:

- **Census tract (CT):** a small, relatively stable urban area containing
  roughly 2,500–8,000 people. Census tracts exist only in census metropolitan
  areas and census agglomerations — large and medium-sized cities.
- **Census subdivision (CSD):** a municipality or municipal-equivalent area.
  CSD controls are useful when a research question follows municipal,
  service-delivery, or local-government geography.
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
:alt: A Canadian census geography ladder showing broad geographies, CSD, CT, ADA, and DA calibration geographies, and DB placement later.
:align: center

For SynthPopCan, CSD, CT, ADA, and DA can be calibration geographies. Dissemination
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
  synthetic households and people, but they do not know CSD, CT, ADA, or DA
  locations by themselves;
- Census Profile tables contain public small-area totals, but they do not
  contain household/person microdata rows.

The current workflow has six steps:

1. **Prepare boundaries** once when we want to map the result.
1. **Generate** candidate linked household/person rows from a model package.
1. **Build controls** from the StatCan Census Profile (the compatible
   household-size/tenure pair, or all nine reviewed household margins from an
   expanded pack).
1. **Estimate** the run size before launching a large calibration.
1. **Calibrate** candidate households to household controls and, when supplied,
   linked-person controls, assigning each realized household to a CSD, CT, ADA,
   or DA.
1. **Map** the output to a self-contained browser choropleth.

Calibration remains **household-first**. Person rows inherit geography from
their assigned household. Optional person controls refine the household weights
using linked-person category counts; they never separate people from their
household.

The current preparer implements household size and tenure by default and all
nine compatible household margins when an expanded pack is selected. The
{doc}`small-area-control-coverage` inventory records which other all-fields
attributes have potential 2016 and 2021 Profile controls, how widely their
source universes are available, and which fields remain uncontrolled.

## Reviewed Control Packs

A **control pack** is a reviewed definition of which margins may be fitted
together. It records the Census vintage and geography level, source rows,
category mappings, population universes, candidate-field derivations,
suppression policy, and known limitations. It does **not** contain Census
counts. Household and person counts remain ordinary normalized control CSVs so
we can inspect, cite, replace, and hash the exact values used by one study.

SynthPopCan includes 24 definition-only packs: eight stable core packs, eight
additive expanded-housing packs, and eight broad packs, one of each
for every combination of the 2016 or 2021 Census and CSD, CT, ADA, or DA
geography. Each core pack combines:

- private-household size, top-coded to the published five-or-more category;
- private-household tenure; and
- broad linked-person age by sex (2016) or gender (2021), coarsened to the
  reviewed common categories.

Each expanded pack retains those three margins and adds dwelling type,
condominium status, bedrooms, rooms, housing suitability, construction period,
and repair condition. Those seven families share the private-household or
occupied-private-dwelling universe and can be fitted together without changing
the household-first calibration contract.

Each broad pack additionally controls citizenship, immigrant status,
generation status, and visible-minority status. Their Profile roots already
measure people in private households, so they can refine the same whole-
household weights without introducing an age-restricted or immigrant-only
universe.

`geo controls --control-pack` prepares the household table. Prepare the pack's
person margins as a separate normalized `person-controls.csv`, then build the
bound universe evidence before calibration. The command's next-step output
shows all three required paths; it never substitutes household counts for
person counts.

List and inspect them before preparing counts:

```bash
synthpopcan geo control-packs list
synthpopcan geo control-packs show \
  statcan-2021-broad-da-v1
```

The broad age source is a total-population Profile vector, while the modelled
population contains people in private households. A pack therefore requires a
strict evidence JSON record for every included geography. The record must show
that published total population equals published persons in private households
for that geography, bind the exact household and person control-table hashes,
and identify exclusions. A minimal source file used to build that record has
this shape:

```json
{
  "geographies": {
    "24660244": {
      "total_population": 610,
      "persons_in_private_households": 610
    }
  },
  "excluded_geographies": {
    "24660245": "suppressed person-control cell"
  }
}
```

The numbers above only illustrate the file shape; they are not published
controls. Build the bound record from the study's reviewed values, then plan
against the actual linked candidates before fitting:

```bash
PACK=statcan-2021-core-private-household-da-v1

synthpopcan geo control-packs evidence "$PACK" \
  --controls household-controls.csv \
  --person-controls person-controls.csv \
  --universe-evidence universe-evidence.json \
  --out control-pack-evidence.json

synthpopcan geo control-packs plan "$PACK" candidates/ \
  --controls household-controls.csv \
  --person-controls person-controls.csv \
  --evidence control-pack-evidence.json

synthpopcan geo calibrate candidates/ \
  --controls household-controls.csv \
  --person-controls person-controls.csv \
  --control-pack "$PACK" \
  --control-pack-evidence control-pack-evidence.json \
  --geo-dimension da \
  --geo-column DAUID \
  --out calibrated-population/
```

The planner fails closed on a wrong vintage or geography namespace, changed
control bytes, incomplete or duplicate category vectors, unreconciled margin
totals, missing fields, unsupported positive cells, broken linkage, or a
private-household universe mismatch. It applies reviewed helper derivations
without overwriting raw fields. For example, `household_size` and `AGEGRP`
remain visible but are reported as **coarsened to a control**; only the fitted
helper dimensions carry the corresponding control status. All other fields
remain explicitly uncontrolled.

Raw normalized controls remain supported when no pack is selected. That path
is useful for project-specific methods, but it does not inherit the built-in
pack's source, universe, or local-claim review.

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
  --geo-level da \
  --out-dir data/derived/statcan/census/2021/boundaries/

synthpopcan geo boundaries \
  --census-year 2021 \
  --geo-level csd \
  --out-dir data/derived/statcan/census/2021/boundaries/
```

These write national `2021-boundary-ct.geojson`, `2021-boundary-ada.geojson`,
`2021-boundary-da.geojson`, and `2021-boundary-csd.geojson` files under
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
boundary file. Some boundary features lack a complete required control vector
because of empty geographies, suppression, or unavailable characteristics, and
are therefore intentionally omitted from calibration.

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

### Bounded Québec 2021 DA proof

The release evidence intentionally uses eight DAs rather than attempting a
province-wide fit: four in Montréal CSD and four in a non-CMA/CA Québec CSD.
The selections come from the final 2021 DGRF, not code prefixes or spatial
guessing. Prepare the official inputs once:

```bash
synthpopcan statcan census-profile fetch \
  --year 2021 \
  --geo-level da-quebec \
  --out-dir data/raw/statcan/census/2021/profiles/da/quebec/

synthpopcan geo boundaries \
  --census-year 2021 \
  --geo-level da \
  --out-dir data/derived/statcan/census/2021/boundaries/

synthpopcan geo relationship-file \
  --out-dir data/raw/statcan/census/2021/geography/relationships/
```

Then prepare the bounded controls, boundary subset, relationship records, and
checksummed evidence manifest:

```bash
uv run python scripts/prove_quebec_da_2021.py \
  --profile data/raw/statcan/census/2021/profiles/da/quebec/2021-census-profile-da-quebec.csv \
  --boundaries data/derived/statcan/census/2021/boundaries/2021-boundary-da.geojson \
  --relationships data/raw/statcan/census/2021/geography/relationships/2021_98260004.csv \
  --out data/work/proofs/quebec-da-2021 \
  --target-households 800
```

The preparer streams the selected features from the national GeoJSON instead
of loading its hundreds of megabytes into memory. Preparation alone is not a
correctness claim: the next release-evidence step must generate and calibrate
the linked population, validate identifiers and household/person linkage,
review convergence and residuals, and render the bounded map.

```bash
synthpopcan models fetch quebec-2021-all-fields

synthpopcan geo synthesize quebec-2021-all-fields \
  --households 800 \
  --controls data/work/proofs/quebec-da-2021/controls.csv \
  --geo-dimension da \
  --geo-column DAUID \
  --census-vintage 2021 \
  --geo-level da \
  --geo-namespace statcan:census:2021:da \
  --max-household-size 5 \
  --random-seed 202107 \
  --subsample-seed 42 \
  --out data/work/proofs/quebec-da-2021/population

synthpopcan geo map data/work/proofs/quebec-da-2021/population \
  --boundaries data/work/proofs/quebec-da-2021/boundaries.geojson \
  --geo-column DAUID \
  --geo-id-field geo_id \
  --census-vintage 2021 \
  --geo-level da \
  --geo-namespace statcan:census:2021:da \
  --out data/work/proofs/quebec-da-2021/population/map.html

uv run python scripts/finalize_quebec_da_2021.py \
  --proof data/work/proofs/quebec-da-2021
```

Finalization independently rechecks the linked household/person files, the
exact selected DA universe, fractional and realized residuals, convergence,
parent-CSD summaries, artifact hashes, and map size before changing the proof
manifest status from `prepared` to `completed`.

### National 2021 DA and ADA execution

```{admonition} Added in 0.7.0
:class: note

National DA/ADA orchestration is a maintainer-scale, restartable workflow. Its
execution evidence does not establish universal prepared-model fitness.
```

The same geography contract supports every province and territory. National
DA execution uses StatCan's six official regional profile products; ADA uses
the single national ADA profile. Both source adapters feed the same planner,
which divides work into the 13 provinces and territories and further bounded
household batches. They share plan and batch schemas, checksums, resource
estimates, resume state, model conditioning, linked validation, and optional
maps. Neither attempts one monolithic national fit.

Fetch or reuse the regional profiles:

```bash
synthpopcan geo national-da fetch-profiles \
  --out-dir data/raw/statcan/census/2021/profiles/da/

synthpopcan geo national-ada fetch-profiles \
  --out-dir data/raw/statcan/census/2021/profiles/ada/
```

Prepare the national plan. This scans every regional profile, uses the final
DGRF for authoritative DA-to-province/territory relationships, partitions the
national boundary file in one pass, excludes and reports incomplete controls,
and writes an atomic manifest for each restartable batch:

```bash
synthpopcan geo national-da prepare \
  --profiles-dir data/raw/statcan/census/2021/profiles/da/ \
  --boundaries data/derived/statcan/census/2021/boundaries/2021-boundary-da.geojson \
  --relationships data/raw/statcan/census/2021/geography/relationships/2021_98260004.csv \
  --max-households-per-batch 100000 \
  --out data/work/canada-da-2021/

synthpopcan geo national-ada prepare \
  --profiles-dir data/raw/statcan/census/2021/profiles/ada/ \
  --boundaries data/derived/statcan/census/2021/boundaries/2021-boundary-ada.geojson \
  --relationships data/raw/statcan/census/2021/geography/relationships/2021_98260004.csv \
  --max-households-per-batch 100000 \
  --out data/work/canada-ada-2021/
```

Run or resume the plan with a reviewed 2021 model:

```bash
synthpopcan models fetch canada-2021-all-fields

synthpopcan geo national-da run canada-2021-all-fields \
  --plan data/work/canada-da-2021/plan.json

synthpopcan geo national-ada run canada-2021-all-fields \
  --plan data/work/canada-ada-2021/plan.json
```

The Canada 2021 package is the appropriate broad national candidate model; the
province-specific packages remain available when a study requires separately
reviewed provincial candidate pools. Neither choice removes the need to review
PUMF coverage, sparse categories, calibration residuals, and fitness for the
research question. By default, each batch conditions the national model on its
province code before calibration. Generation happens once per PUMF condition,
not once per batch: the runner creates an evidence-checked reusable pool of
10,000 linked candidate households for each province or combined northern
condition and records its model hash, seed, category support, row counts, file
hashes, and phase timings. A resumed run verifies those files before use and
can skip loading the large model package entirely. Use
`--candidate-pool-size` for a documented sensitivity analysis or
`--force-candidate-pools` after intentionally changing generation assumptions.
Pool preparation excludes generated PUMF households with `TENUR=8`, which the
official 2021 hierarchical PUMF metadata defines as “Not available,” together
with their linked persons. The pool manifest records every exclusion. Those
rows must not remain outside the owner/renter control universe or be
misclassified as renters.

The hierarchical PUMF exposes Yukon,
Northwest Territories, and Nunavut only as the combined northern category
`PR=70`; their batches therefore share that candidate pool while retaining
separate territory-specific DA controls. This is an explicit source limitation,
not evidence of territory-specific microdata. Unsupported categories fail
instead of falling back to an unconditioned national mixture. Use `--limit 1`
for a first batch and inspect convergence, realized residuals, linkage, output
size, and the report before resuming. `--workers` controls bounded
batch-process parallelism while `--fit-workers` controls geography fitting
within each process. Start conservatively because every process reads
candidates and realizes a population independently.

### Batch checkpoints and recovery

Use one coordinator per plan directory. The coordinator owns the batch
manifests and may run multiple workers through `--workers`.

| Persisted transition | Condition |
| --- | --- |
| `planned`, `failed`, or leftover `running` → `running` | The coordinator selects the batch and records the next attempt before starting it. |
| `running` → `completed` | The worker returns result evidence after installing the validated output directory. The coordinator records that evidence in `batch.json`. |
| `running` → `failed` | The callback raises or a parallel worker exits without returning evidence, including exit code zero. A later execution can retry the batch. |
| `running` → `planned` | The coordinator handles an interrupt during execution, or a parallel worker cannot start. |
| `completed` → `planned` | An explicit reset of a non-converged batch moves the prior result into `superseded_results`. Normal resume skips completed batches. |

The national worker writes into a temporary sibling directory, validates
household/person linkage, records hashes, then renames the directory into
place. Readers select completed results from `batch.json`. File presence alone
does not commit an attempt. If the process dies after the rename and before the
batch checkpoint, the next run fits the batch again and replaces the abandoned
output. If it dies after the batch checkpoint and before `plan.json` is
refreshed, resume skips the committed batch and rebuilds the plan status from
the batch manifests. Abrupt termination during staging can leave an unused
temporary directory.

Before starting more batches, resume checks the size and SHA-256 of the
household, person, and report files recorded by the built-in worker. This
includes completed batches outside the current selection because their results
can still contribute to national summaries. If an artifact is missing or
changed, restore the original file or run a fresh plan in a new directory.

The plan status is a summary of the batch manifests. It is `completed` when
all batches are completed, `failed` when any failed, `partial` when some are
completed, and `planned` otherwise. Atomic renames cover these process restart
cases. The workflow does not guarantee durability across machine or filesystem
failure.

Detailed per-batch maps are deferred and opt-in with `--maps`. After a complete
plan, the default `--national-map` writes the familiar polygon choropleth as
`national-map.html` alongside `national-geography-summary.csv` and
`national-summary.json`. The embedded polygons are a display-only derivative.
The renderer prefers topology-preserving prepared boundaries found in the
plan; a jurisdiction-scoped map can retrieve the matching `geodata-v1` asset
when its catalogue is configured. Otherwise, the renderer falls back to a
fixed-grid display conversion of the canonical boundary. In every route, the
canonical StatCan source is unchanged and remains the analytical geometry.

The lighter `national-points-map.html` is retained as a secondary overview.
Its markers are the bounding-box centres of the unchanged canonical features;
the point layer is a display index, not an analytical geography. Partial runs
still update the CSV and JSON summaries but do not rescan the national boundary
file for either map.

The normal map command accepts either the completed `plan.json` or its
directory; boundaries, geography identity, and the 161 household/person batch
pairs are inferred:

```bash
synthpopcan geo map data/work/canada-ada-2021
```

This is the same supported map product used for a single linked-population
pair. It streams each batch once and caches `national-map-statistics.csv` with
source-artifact evidence. The selector includes households, persons, average
household size, median household income, median shelter cost, homeownership,
detached dwellings, major repairs, children, seniors, immigrants, and visible
minorities. A repeat invocation reuses the statistics when batch hashes match.

When only one province or territory has finished, render that completed subset
explicitly instead of presenting it as a Canada-wide result. For example, a
completed Québec DA subset can be mapped from an otherwise partial plan:

```bash
synthpopcan geo map data/work/canada-da-2021 --jurisdiction QC \
  --out data/work/canada-da-2021/quebec-da-map.html
```

The map includes only the requested completed jurisdictions; it does not
impute or draw pending batches as if they had been synthesized.

The beginner Python API uses the same path:

```python
import synthpopcan as spc

map_path = spc.render_small_area_map(
    households="data/work/canada-ada-2021/plan.json",
)
```

The command
checks the plan's conservative disk estimate before starting and requires an
explicit `--allow-low-disk` override when available space is below it.
Use `--jurisdiction ON` or `--jurisdiction 35` to run only one jurisdiction;
this also permits a separately reviewed province-specific model to execute its
own batches before the shared plan is resumed with another model.

The national plan is a collection of independently validated outputs, not a
claim that every DA or ADA has publishable controls. Empty, suppressed, zero, or
incomplete household-size and tenure vectors remain visible in the coverage
report and are never silently imputed.
Preparation fails if any DA or ADA with usable controls lacks a boundary. The
four DA records in the 2021 DGRF that are absent from the DA cartographic
boundary product have zero-area, unavailable profile values and are reported
among the excluded DAs.

DA and ADA now have operational parity. Their only intentional differences are
their StatCan source adapters: DA selects six regional profile products and the
DGRF's DA relationship column, while ADA selects one national profile and the
ADA relationship column. A plan is bound to one explicit geography identity;
`national-da run` rejects an ADA plan and `national-ada run` rejects a DA plan.

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
CSV. By default it extracts the compatible household-size and tenure margins.
Select an expanded pack to extract nine household margins: size, tenure,
dwelling type, condominium, bedrooms, rooms, housing suitability, construction
period, and repair condition. It applies each pack's vintage-specific category
mapping, requires every root and child row, and reconciles each child vector to
its published root within the strict worst-case bound for Statistics Canada's
base-five randomized rounding. A subtotal can therefore never be counted again
beside its children. It then scales every complete margin to the target
household count and writes:

- a long-format controls CSV ready for `geo calibrate`;
- a recoded linked-population directory whose `households.csv` has a
  `household_size_group` column
  where 5, 6, 7, and larger households are grouped as `5`, matching the Census
  categories while preserving the exact `household_size` column.

Geographies missing any required margin are dropped automatically, preventing
the IPF dimension-mismatch error in `geo calibrate`.
Calibration preflight also rejects candidate category values absent from a
control margin. Otherwise those rows would retain unconstrained weights and
could prevent the fitted margin total from reaching its target.

```bash
synthpopcan geo controls \
  --profile data/raw/statcan/census/2016/profiles/ct/2016-census-profile-ct.csv \
  --geo-column ct \
  --geo-prefix 421 \
  --target 338000 \
  --control-pack statcan-2016-expanded-private-household-housing-ct-v1 \
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
| `--control-pack` | Optional reviewed core or expanded pack. Expanded housing packs extract all nine household margins; omission preserves the household-size/tenure path. |
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
Recommended interface: CLI or Python API
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

For repeated or large maps, {doc}`geodata` can fetch a smaller, checksummed
display-only boundary from the published `geodata-v1` catalogue. Use canonical
Statistics Canada boundaries for analytical selection and reconciliation; use
the prepared copy only for presentation.

```bash
synthpopcan geo map quebec-city-population/ \
  --boundaries data/derived/statcan/census/2016/boundaries/2016-boundary-ct.geojson \
  --geo-column ct \
  --out quebec-city-ct-map.html \
  --title "Synthetic Quebec City Households"
```

Pass `--boundaries` either as a `.geojson` produced by `geo boundaries`
or as a path to the original StatCan `.shp` file (reprojection is automatic in
both cases). It may also be the verified `.geojson` path printed by
`synthpopcan geodata fetch` when the map uses the same Census vintage and
geography universe.

The resulting file opens directly in any browser. It requires an internet
connection to fetch base-map tiles from [OpenFreeMap](https://openfreemap.org/) but otherwise embeds all
data inline.

Polygon maps offer **People per km²** (the default when available) and
**Households per km²** when the boundary attributes contain a finite, positive
`LANDAREA` in km². Densities use that published land area, rather than the
area of simplified display polygons. Missing or invalid land area leaves
density unknown; those features are transparent on the selected density layer.
Density colours use a logarithmic `log(1 + density)` scale to show rural
and urban variation together, while retaining genuine zeros. The legend
labels this scale and shows ticks in the original people/households per km²
units. Tooltips retain the original density values; other variables keep
linear colour scales over each variable’s observed range, as labelled in the
legend. Colours show relative variation within the selected variable; they
cannot be compared numerically between different variables.
Maps without person data default to household density when available, then
fall back to totals if land area is unavailable.

Variables shown (household-level, always): household count, average household
size, % homeowners, % detached dwellings, % needing major repairs, median
shelter cost.

Variables shown (person-level, when `--persons` is supplied): person count,
% people under 20, % seniors (≥65), % immigrants, % visible minority, median
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
  supports the national `ct`, `ada`, `da`, and `csd` products.
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

- `--out-dir`: required directory for the extracted relationship CSV and
  provenance.
- `--url`: optional alternate URL for a documented mirror of the same product.

### `geo national-da` and `geo national-ada`

Coordinate 2021 DA or ADA preparation and synthesis across all 13 provinces
and territories:

- `fetch-profiles` retrieves the level's official profile product or products;
- `prepare` reconciles profiles, DGRF relationships, and national boundaries,
  then writes bounded restartable batches and storage estimates; and
- `run` executes unfinished batches, validates linked outputs, records hashes,
  and optionally creates maps.

This interface supplies national execution mechanics. Scientific suitability
of the selected model outside its training population remains a separate
review decision.

Both groups expose the same subcommands and options:

**`fetch-profiles`**

- `--out-dir`: required profile cache root.
- `--force`: redownload a file that is already present.

DA fetches the six registered regional products. ADA fetches the registered
national product.

**`prepare`**

- `--profiles-dir`: required directory containing the registered 2021 product
  files for the selected level.
- `--boundaries`: required national WGS-84 DA or ADA GeoJSON.
- `--relationships`: required final 2021 DGRF CSV.
- `--out`: required national plan directory.
- `--max-households-per-batch`: maximum target households in one restartable
  batch; default `100000`.

**`run MODEL`**

- `MODEL`: reviewed package path or model-catalogue ID.
- `--plan`: required `plan.json` written by `prepare`.
- `--limit`: run at most this many unfinished batches, useful for a first
  evidence run.
- `--jurisdiction`: province/territory PRUID or abbreviation; repeat to select
  several jurisdictions.
- `--random-seed`: base generation seed; each candidate condition receives a
  deterministic derived seed.
- `--condition-by-jurisdiction/--no-condition-by-jurisdiction`: condition a
  national model on the PUMF province or combined northern category; enabled
  by default.
- `--continue-on-error`: record a failed batch and continue.
- `--candidate-pool-size`: reusable linked candidate households per PUMF
  condition; default `10000`.
- `--workers`: concurrent batch processes, from 1 through 8.
- `--fit-workers`: fitting threads inside each batch process, from 1 through 8.
- `--force-candidate-pools`: rebuild candidate pools even when their evidence
  still matches.
- `--maps/--no-maps`: enable or disable detailed per-batch maps; disabled by
  default.
- `--national-map/--no-national-map`: enable or disable the final national
  polygon map; enabled by default after complete execution.
- `--allow-low-disk`: override the plan's conservative free-space check.

Use `--limit 1 --workers 1` for the first run. Inspect its batch manifest,
linkage validation, fractional and realized residuals, and disk use before
increasing concurrency or resuming the complete plan.

### `geo controls`

Builds household-size and tenure controls from a Census Profile bulk CSV, or
all reviewed household margins declared by `--control-pack`.
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
- `--control-pack`: optional reviewed pack identifier. Its Census vintage and
  geography must match the Profile and `--geo-column`.
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

### `geo control-packs`

Inspects and applies the reviewed definition-only pack contracts introduced in
0.9:

- `list [--format summary|json]` lists the 24 built-ins;
- `show PACK [--out pack.json]` renders a built-in or strict local manifest;
- `evidence PACK --controls ... --person-controls ... --universe-evidence ... --out ...` binds a pack to the exact normalized counts and companion
  private-household population evidence; and
- `plan PACK POPULATION --controls ... --person-controls ... --evidence ...`
  checks compatibility and feasibility without fitting. Use `--persons` when
  `POPULATION` is a household CSV rather than a linked-population directory.

`plan` exits with status 1 when any required source, universe, field, vector,
geography, linkage, or support check fails. `--format json` retains the complete
machine-readable issue list.

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
- `--control-pack`: optional built-in identifier or strict local pack manifest.
  For a broad pack or a local manifest, supply person controls and
  `--control-pack-evidence`. A standalone built-in marital-status pack
  uses its source CSV as evidence.
- `--control-pack-evidence`: strict JSON bound to the selected pack and the
  exact household/person control tables. A non-passing plan stops before fit.
- `--geo-dimension`: geography dimension in the controls.
- `--geo-column`: geography column written to the assigned outputs.
- `--census-vintage`, `--geo-level`, `--geo-namespace`, and
  `--geo-dguid-column`: explicit Census geography universe. Supply the first
  three together for a Census workflow; the DGUID column is optional.
- `--include-weights`: also write the potentially large `weights.csv` artifact.
- `--out`: directory for calibrated `households.csv`, `persons.csv`, their
  linked-population `manifest.json`, and `report.json`.
- `--pool-size`: optional maximum number of candidate households used in each
  fit.
- `--subsample-seed`: reproducible seed for the `--pool-size` candidate
  subsample.
- `--max-iterations`: maximum strict iterations per fitting stage for each
  geography; the CLI default is `16`.
- `--tolerance`: convergence tolerance for each geography; the default is
  `1e-6`.
- `--format summary|json`: printed report format.

#### Diagnose infeasible linked fits

For a `household_size_group` margin, calibration checks whether the
household-size targets can accommodate the person total. The lower bound
counts each 5+ household as five people. The upper bound uses the largest
linked candidate household in each positive size group when all those
groups are represented.

- If the person target is **below the minimum**, check that the Census
  vintage and private-household universe agree, then review any rounding or
  normalization. Document any target reconciliation or exclude the tract.
- If the person target is **above the candidate maximum**, use a model or
  pool that supplies larger linked households in the required size groups,
  review the targets, or exclude the tract. More draws from a model with
  the same size cap cannot raise this bound.
- If a positive cell **loses support under structural zeros**, review the
  zero controls and add compatible candidates. If the zeros are rounded
  observations, `--zero-target-policy observed` can produce an approximate
  fit with residuals against the original targets.
- If the run **completes without convergence**, use `report.json` to locate
  the geography and margins with the largest residuals. Check joint
  feasibility under the selected zero policy before raising the iteration
  limit. Whole-household swaps can reduce realized residuals. Fractional
  convergence is reported separately.

#### Marital status for persons aged 15 and older

Use `geo calibrate --marital-status-controls marital.json` with normalized
household and person control CSVs and explicit Census vintage, geography level,
and namespace. This first path accepts independently reviewed, reconciled
private-household targets supplied by the study. It is available through
`SmallAreaCalibrationRequest.marital_status_controls_path` in Python too.

The JSON document has schema version `synthpopcan-marital-status-controls-v1`.
It contains an `age_eligibility` map from the candidate model's `AGEGRP` codes
to booleans and a `crosswalk` from its `MarStH` (2016) or `MARSTH` (2021)
codes to the reviewed categories. In `targets`, supply one record per person
control geography with these fields.

| Field | Contents |
| --- | --- |
| `geography` | Versioned `GeographyIdentity` object with the short identifier, vintage, level, and namespace. Omit the optional DGUID. |
| `all_private_household_persons` | Independently evidenced private-household person count, matching every existing person margin. |
| `age_15_plus_persons` and `under_15_persons` | Independently evidenced counts that sum to the private-household total. |
| `eligible_counts` | One count per crosswalk category, including observed zeros. The vector sums to the age-15+ count. |
| `under_15_not_applicable` | Explicit target for under-15 candidates, matching the independently evidenced under-15 count. |
| `source_evidence` | Reference identifying the source revision, universe, and any reviewed reconciliation. |

Candidate rows with unknown age codes or unmapped eligible marital-status
codes fail preflight. The added `marital_status_15_plus` column labels younger
people as `under_15_not_applicable` and the fit continues to assign whole
households. The report records fitted and realized residuals and the input
document's hash. Use normalized CSVs without a reviewed pack or prepared
controls directory for this path.

The built-in CT packs use a separate source CSV path. List their identifiers
with `synthpopcan geo control-packs marital-status`. For example, use
`--control-pack statcan-2021-marital-status-ct-v1 --marital-status-controls tract-cells.csv`
alongside the normalized household and person controls. The 2016 pack uses
`statcan-2016-marital-status-ct-v1`. These conditional packs have their own
input contract and are applied by `geo calibrate`.

For a joint fit with a matching broad CT pack, bind its evidence to the
unchanged household and person control CSVs, then select the marital-status
pack separately. For 2021, the relevant options are:

```bash
synthpopcan geo calibrate candidate-households.csv --persons candidate-persons.csv \
  --controls broad-households.csv --person-controls broad-persons.csv \
  --control-pack statcan-2021-broad-ct-v1 --control-pack-evidence broad-evidence.json \
  --marital-status-pack statcan-2021-marital-status-ct-v1 \
  --marital-status-controls tract-cells.csv --geo-dimension ct \
  --include-weights --out calibrated/
```

For linked normalized CSV calibration, add `--integerization swap` to
reduce realized control residuals. It starts with midpoint rounding and
searches up to 100 improving whole-household swaps per geography. The search
preserves the starting household count and uses candidates with positive
fitted weights. It minimizes the sum of squared control-cell residuals, so
individual cells can trade off against one another. Check the realized
residuals and fractional convergence separately. The default is
`--integerization midpoint`.

The broad pack supplies the Census geography identity and validates its
evidence before the conditional margin is appended. Joint calibration expects
the matching hierarchical PUMF age codes and retains them in the output. Both
sources must support each selected tract and agree on its private-household
person total and under-15 target. See the
[release acceptance scope](https://github.com/dlq/synthpopcan/blob/main/plans/2026-08-01-expanded-small-area-controls.md#marital-status-release-acceptance)
for the tested combination and its limits.

Download the matching IVT from the
[2016 deposit](https://doi.org/10.5683/SP3/CDKEOF) or
[2021 deposit](https://doi.org/10.5683/SP3/UHEPKL). From a source checkout,
run the pinned extraction tool. It verifies the deposited IVT hash and
preserves unavailable values as blank CSV cells.

```bash
uv run --no-project --with pyivt==0.0.8 python scripts/extract_marital_status_tracts.py \
  2021 EO3559_2021_Table1_Final.ivt tract-cells.csv
```

The pack uses the published all-ages total as its anchor. It sums disjoint
adult age rows, then apportions that total between adults and children by
largest remainder. It apportions the reconciled adult total across the four
marital-status categories by the same method. Bounds of 52 people for the age
discrepancy and 308 for the adult category discrepancy come from the maximum
base-five rounding error of four per cell on both sides. These are admission
bounds for reconciliation. Adjusted counts are derived targets. The report
retains the observed totals and category sums alongside the adjusted counts
and the input CSV hash.

Every selected tract must have all required source cells and a matching
all-ages total in the supplied person margins. A blank, suppressed, duplicate,
or invalid required cell stops calibration before fitting. To use a subset,
select the same supported tracts in both control tables. Numeric zeros stay
zero through apportionment. In the default fit they act as structural zeros.
For a fit that allows residuals against published zeros, explicitly select
`--zero-target-policy observed`.

The standard 2016 and 2021 Census marital-status products cover the
population aged 15 and over, including people in collective dwellings. Use
them as private-household targets only where independently reviewed evidence
establishes that the populations coincide. Equality of published rounded
counts alone does not establish that condition. See the
[2016 CT table](https://www150.statcan.gc.ca/n1/en/catalogue/98-400-X2016036)
and [2021 reference guide](https://www12.statcan.gc.ca/census-recensement/2021/ref/98-500/002/98-500-x2021002-eng.pdf).

### Education controls for census tracts

List the education packs with `synthpopcan geo control-packs education`.
For normalized linked CSV calibration, add `--education-pack` and
`--education-profile`. The profile can be the matching Statistics Canada
tract ZIP or its extracted English CSV. For example:

```bash
synthpopcan geo calibrate candidate-households.csv --persons candidate-persons.csv \
  --controls broad-households.csv --person-controls broad-persons.csv \
  --control-pack statcan-2021-broad-ct-v1 --control-pack-evidence broad-evidence.json \
  --education-pack statcan-2021-education-ct-v1 --education-profile tract-profile.zip \
  --geo-dimension ct --joint-solver hybrid --integerization swap \
  --include-weights --out calibrated/
```

Use matching 2016 identifiers and Profile for a 2016 fit. The education pack
controls eight `HDGREE` categories among private-household residents aged
15 and over. It writes `education_15_plus` on realized persons and labels
children `under_15_not_applicable`. The report preserves the raw Profile rows,
the normalized targets, and the Profile hash. Selected tracts must have
complete education counts, compatible all-ages and under-15 targets, and
linked candidates with supported age and eligible education codes.

### Labour-force status controls for census tracts

List the packs with `synthpopcan geo control-packs labour-force-status`.
For linked normalized CSV calibration, use the matching vintage of
`--labour-force-pack statcan-2021-labour-force-status-ct-v1` and
`--labour-force-profile tract-profile.zip` with `geo calibrate`. The input
may also be the extracted English Profile CSV. These options can accompany
the matching broad pack and its evidence, and `--integerization swap`.

The pack writes `labour_force_status_15_plus` with employed, unemployed,
or outside the labour force for adults, and `under_15_not_applicable`
for children. The report includes the published rows, derived targets,
and Profile hash. Tracts with unavailable counts or incompatible
all-ages and under-15 targets fail before fitting.

### Work-activity controls for census tracts

List the packs with `synthpopcan geo control-packs work-activity`. For
linked normalized CSV calibration, use `--work-activity-pack statcan-2021-work-activity-ct-v1` and `--work-activity-profile tract-profile.zip` with `geo calibrate`. Use the corresponding 2016
identifier and Profile for 2016 tracts. The Profile can be the official
tract ZIP or its extracted English CSV. The options can accompany the
matching broad pack and its evidence, and `--integerization swap`.

The pack writes `work_activity_15_plus` on realized persons. It groups
private-household residents aged 15 and over into did not work, worked
full year and full time, and worked part year and/or part time during
calendar year 2015 (2016 Census) or 2020 (2021 Census). Children use
`under_15_not_applicable`. The report records published counts, reconciled
targets, and the Profile hash. A selected tract needs observed counts and
exact agreement with the all-ages and under-15 targets of the other
controls. If a tract fails, inspect the reported rows and use compatible
controls for that tract or omit the work-activity pack for its fit.

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
- `--control-pack`: optional built-in identifier or strict local pack manifest.
  Requires person controls and `--control-pack-evidence`.
- `--control-pack-evidence`: strict bound evidence JSON. Candidate derivations
  and the complete plan run after candidate generation and any pool subsample.
- `--geo-dimension`: geography dimension in the controls.
- `--geo-column`: geography column written to the assigned outputs; defaults to
  `--geo-dimension`.
- `--census-vintage`, `--geo-level`, `--geo-namespace`, and
  `--geo-dguid-column`: explicit Census geography universe recorded in the
  output report and linked-population manifest.
- `--out`: directory for calibrated `households.csv`, `persons.csv`, their
  linked-population `manifest.json`, and `report.json`.
- `--include-weights`: also write the potentially large fitted weights CSV.
- `--random-seed`: candidate generation seed.
- `--condition`: fixed package condition in `COLUMN=VALUE` form; repeat for
  multiple conditions.
- `--pool-size`: optional maximum number of candidates used for calibration.
- `--subsample-seed`: reproducible seed for the calibration subsample.
- `--max-household-size`: group exact household sizes into a top-coded category,
  usually `5` for Census Profile controls.
- `--household-size-group-column`: grouped-size column used for calibration.
- `--max-iterations` and `--tolerance`: per-geography fitting limits.
- `--format summary|json`: printed report format.

### `geo map`

Writes a self-contained HTML map from calibrated household/person outputs.

In the combined household/person view, percentages require complete
observations for the relevant field in each geography. Missing or invalid demographic fields remain unknown, and variables
with no observed values are omitted from the selector. Unknown income is not
zero income: the median household income remains unknown when a household's
person-income observations are incomplete. Observed zero income remains zero.
Observed zero shelter costs remain in shelter-cost medians. Income codes
`88888888` (unavailable) and `99999999` (not applicable) remain unknown.
The immigrant percentage counts the immigrant category only; non-permanent
residents are a separate source category.

For source-specific coding, supply binary `age_under_20`, `age_65_plus`, and
`visible_minority` person columns. These take precedence over the legacy
`AGEGRP` and `VISMIN` interpretations; blank or invalid supplied indicators
remain unknown. In particular, hierarchical PUMF age codes use 13 substantive
bands and require explicit indicators for these map statistics. Raw source
fields can be retained alongside the indicators.

```bash
synthpopcan geo map synthetic-population/ \
  --boundaries data/derived/statcan/census/2016/boundaries/2016-boundary-ct.geojson \
  --geo-column ct \
  --out synthetic-ct-map.html
```

#### A complete workflow using CLI commands only

Version `1.1.4` and later support four main CLI stages: prepare controls, generate
candidates, calibrate/assign, and generate both maps. No custom Python scripts
are needed. The initial supported source is the **2021 hierarchical PUMF**
with **2021 Census tracts selected by CMA**, or **province-wide aggregate
dissemination areas (ADAs)**, or **Canada-wide ADAs**.

From the source checkout, install the optional acceleration and feasibility
dependencies with `uv sync --extra performance` before running these examples.

For a CMA/CT run, the Profile input is an official CT Profile ZIP containing one
`English_CSV_data.csv` member, or an extracted CSV with both the CMA and CT
rows. Download it with `statcan census-profile fetch`, or supply a verified
local file if the website returns a browser security challenge. Preparation
records its SHA-256; `--profile-sha256` can enforce a known digest.

Fetch the model and boundaries once, then use a fresh output directory:

```bash
CLI=.venv/bin/synthpopcan
R=runs/montreal-cli
PROFILE=/absolute/path/to/98-401-X2021007_eng_CSV.zip

$CLI geo prepare-controls "$PROFILE" --cma 462 \
  --source-profile statcan-hierarchical-2021 \
  --normalization observed-proportional --incomplete-geographies exclude \
  --out "$R/controls"
$CLI models generate montreal-cma-2021-all-fields \
  --households 100000 --random-seed 20211102 --out "$R/candidates"
$CLI geo calibrate "$R/candidates" --controls "$R/controls" \
  --geo-dimension ct --pool-size 20000 --subsample-seed 42 --augment-support \
  --workers 2 --joint-solver hybrid \
  --max-iterations 16 --tolerance 0.01 --out "$R/population"
$CLI geo map "$R/population" --both \
  --person-profile statcan-hierarchical-2021 \
  --boundaries /absolute/path/to/2021-ct-boundaries.geojson --geo-column ct \
  --census-vintage 2021 --geo-level ct --geo-namespace statcan:census:2021:ct \
  --out "$R/montreal.html"
```

Passing the prepared controls directory makes `geo calibrate` screen whole
households, prepare the age/gender subset, fit each universe-specific batch,
combine assignments, validate linkage and independently audit the realized
controls. It infers Census 2021 CT identity and retains batch reports under
`population/work/`. `workflow.json` records completion or failure. The optional
support augmentation requires `synthpopcan[performance]` and adds
feasible whole-household supports to the age/gender pool without subsequently
subsampling it. The other batch uses the requested random pool size.

Install `synthpopcan[performance]` to automatically accelerate large IPU fits,
independent audits and linked map statistics with Numba and bounded Polars.
It includes the SciPy dependency needed for support augmentation. Existing
commands and fitting settings stay the same; the first eligible fit in each
worker pays its compilation cost. Without the extra, the NumPy and streaming
CSV implementations remain available. See [installation](installation.md).

`--workers` sets one to eight fitting threads per batch. `--joint-solver hybrid`
tries up to 50 damped entropy-dual Newton steps (bounded by `--max-iterations`).
It accepts a result only when every original household/person constraint meets
`--tolerance`; otherwise it discards that attempt and starts the existing IPU
fit from its original initial weights. `ipu` remains the default for compatibility.
The report records the requested and effective method for each geography.

Identical household control-contribution profiles are fitted as summed weights
and expanded in their initial proportions. Every original household remains
available for integer selection; grouping does not merge their attributes.
The optional HiGHS support stage disables expensive presolve, retrying with
presolve when a numerical or incomplete solve requires it. Feasibility status
and effective presolve settings are retained. Equivalent LP bases can select
different extra supports, so optimized runs need not reproduce old row hashes.

For a whole province, use `--province` instead of `--cma`. Census tracts do
not cover rural Québec; ADAs provide a province-wide geography. The ADA Profile
product contains no provincial root, so also supply the official
Canada/provinces/territories Profile CSV or ZIP with `--province-profile`:

```bash
R=runs/quebec-cli

$CLI geo prepare-controls /absolute/path/to/98-401-X2021012_eng_CSV.zip \
  --province 24 \
  --province-profile /absolute/path/to/98-401-X2021001_English_CSV_data.csv \
  --source-profile statcan-hierarchical-2021 \
  --normalization observed-proportional --incomplete-geographies exclude \
  --out "$R/controls"
$CLI models generate quebec-2021-all-fields \
  --households 500000 --random-seed 20211102 --out "$R/candidates"
$CLI geo calibrate "$R/candidates" --controls "$R/controls" \
  --geo-dimension ada --pool-size 20000 --subsample-seed 42 --augment-support \
  --workers 2 --joint-solver hybrid --zero-target-policy observed \
  --max-iterations 16 --tolerance 0.01 --out "$R/population"
$CLI geo map "$R/population" --both \
  --person-profile statcan-hierarchical-2021 \
  --boundaries /absolute/path/to/2021-boundary-ada-qc-display-topo.geojson \
  --geo-column ada --geo-id-field geo_id --census-vintage 2021 --geo-level ada \
  --geo-namespace statcan:census:2021:ada --out "$R/quebec.html"
```

For independently rounded Census counts, an explicit
`--zero-target-policy observed` on `geo calibrate` keeps all targets unchanged
and first tries the normal structural-zero fit. If zero exclusions leave a
positive target unsupported, or strict fitting does not converge, a
fixed-household-total entropy/least-squares fit
can return an approximate population and report every residual, including at
zero targets. Optimizer success is not control convergence. The default
`structural` policy still rejects unsupported hard zeros. Initial zero donor
weights remain zero under either policy.

With observed mode and `--augment-support`, both candidate pools retain
whole-household witnesses for rare positive categories. Zero-compatible
witnesses are preferred; any observed-only witness and its conflicting zero
cells are recorded. This is category-support evidence, not an LP feasibility
certificate. Structural mode retains its existing age/gender LP route.

The provincial path retains each ADA's published occupied-private-dwelling
count. Other complete observed category vectors are normalized to that area's
household or private-person total. Unavailable areas are reported explicitly;
their households are never redistributed into other ADAs. The plan records the
provincial totals, observed-area coverage, unknown household counts and any
known target shortfall. Summed rounded private-person counts can differ from
the province's private-person total. Unknown counts remain unknown.

For advanced stage-by-stage operation, the separate `geo prepare-candidates`,
`geo combine` and `geo audit` commands remain available; `geo calibrate` still
accepts an individual normalized CSV with `--person-controls`. Use only the
batches present in `controls/plan.json` and combine disjoint assignments.

The candidate household count is a **pool size**, not the final number of
households. The CMA's occupied-private-dwelling count supplies the household
target. Complete observed tract household vectors are proportionally allocated
to that common total; private-person vectors use each tract's published
private-household-person total. `--normalization observed-proportional` is
explicit because this adjusts prepared targets. Raw rows remain in
`selected-profile.csv`, with each original and normalized vector in the batch's
`normalization.json`. Missing/suppressed counts are never imputed. The default
`--incomplete-geographies error` stops preparation; the example explicitly uses
`exclude` to omit unavailable tracts and record every exclusion in `plan.json`.
The CMA household target is allocated over the retained tracts, so inspect
that coverage and allocation before interpreting the result.

Nine household control dimensions cover size, tenure, dwelling type,
condominium, bedrooms, rooms, suitability, construction period and repair.
Four person control dimensions cover citizenship, immigration, generation and
visible-minority status. Age-by-gender is added only where the all-person and
private-household-person roots are equal. The preparation code uses the
hierarchical 2021 age/gender codes explicitly and leaves frozen v1 pack
definitions unchanged. Education, employment, language and income remain
modelled attributes rather than additional calibration claims.

`prepare-candidates` excludes whole households containing unknown control
values and records exclusions and their reasons. This can change the candidate
distribution. Omitting `--pool-size` retains all complete households. For a
smaller random pool, use `--pool-size` and `--subsample-seed`. An optional
`--augment-support` adds whole-household nonnegative linear-feasibility supports
for supplied `--controls` and `--person-controls`; install
`synthpopcan[performance]` first. This diagnostic does not generate final
weights or alter infeasible targets. Its report retains infeasible geographies.
Use the augmented pool without further subsampling during calibration.

Calibration checks candidate identifiers and household links before
subsampling. A category with only zero targets can be absent from the
candidate pool. Every positive target still needs support.

When calibrating from a prepared directory, the plan and batch totals must
agree with the control tables. If `preparation.json` is present, calibration
also verifies the recorded fingerprints of the plan and control files. Final
population files are staged until linkage validation and the independent
audit finish. The prepared workflow records `running` in `workflow.json`
when it claims a fresh output directory. It records `complete` after moving
the final files into place, with the manifest moved last. A handled error
records `failed`. An error while moving final files removes the files already
moved. An abrupt stop can leave `running` and some files in place, so check
`workflow.json` before using the result. Keep the work files for inspection
and use a fresh output directory to retry.

Combination checks disjoint geography sets, compatible licensing, unique IDs
and household/person linkage. It retains source calibration reports, including
non-convergence. The independent audit writes every realized cell's residual
and reports unexpected categories. Neither command makes infeasible integer
constraints exact or silently adjusts the prepared targets.

Preparation, combination and audit publish their output directories only on
success and refuse to overwrite completed results. Each writes
`preparation.json` with the CLI arguments, input hashes and output hashes.
Completed stages can be reused by running the next CLI command directly.

#### Person attributes by census tract

Use `--person-profile statcan-hierarchical-2021` to aggregate the **person
records directly**, with the explicit 2021 hierarchical PUMF codebook. This
view accepts `persons.csv` as the population input and does not require a
household table:

```bash
synthpopcan geo map synthetic-population/persons.csv \
  --person-profile statcan-hierarchical-2021 \
  --boundaries data/derived/statcan/census/2021/boundaries/2021-boundary-ct.geojson \
  --geo-column ct \
  --census-vintage 2021 --geo-level ct --geo-namespace statcan:census:2021:ct \
  --out population-attributes-map.html
```

The selector includes population density and totals, age bands, women+/men+,
citizenship, immigrant status, generation, visible-minority share, marital
status, education, labour-force rates, personal and employment income, and
mother-tongue/home-language components. It defaults to people per km² where
published land area is available.

Education, labour, marital-status, and income measures use people aged 15+.
Unemployment uses known labour-force participants as its denominator. Income
medians use individual income in 2020, including observed zero and negative
values. Missing and inapplicable codes are excluded; they do not become zeros.
The selected measure's note states its denominator, and its tooltip shows the
number of valid records, the denominator, and the age-eligible population.
Language responses can overlap. Age remains in published bands; exact ages
are not inferred. These layers describe synthetic records; agreement with
local Census data depends on the calibration controls used.

The profile is explicit because the legacy map's raw age/gender coding differs
from the hierarchical 2021 PUMF. Ordinary `geo map` calls retain their existing
combined household/person view. Person-profile views currently support a
single linked population or person CSV, rather than a national-plan input.

To generate both household and population views in one invocation, use
`--both` with a linked population directory and the explicit person profile:

```bash
synthpopcan geo map synthetic-population/ --both \
  --person-profile statcan-hierarchical-2021 \
  --boundaries data/derived/statcan/census/2021/boundaries/2021-boundary-ct.geojson \
  --geo-column ct \
  --census-vintage 2021 --geo-level ct --geo-namespace statcan:census:2021:ct \
  --out synthetic-ct-map.html
```

This writes `synthetic-ct-map-households.html` (the existing combined
household/person view) and `synthetic-ct-map-population.html` (person attributes
only). Both paths are reported. Without `--out`, a population directory gets
`map-households.html` and `map-population.html`. A household CSV is also
accepted when paired with `--persons persons.csv`; its default output stem is
`<households-stem>-map`. An explicit `--title` gets a household/population suffix
to distinguish the views. National plans do not currently support `--both`.

Important options:

- `POPULATION`: calibrated population directory, or an assigned household CSV.
- `--both`: generate household and population views together; requires
  `--person-profile` and linked household/person CSVs.
- `--person-profile statcan-hierarchical-2021`: use a person-attribute view;
  `POPULATION` may then be an assigned person CSV directly.
- `--persons`: optional assigned person CSV for person-level map variables.
- `--boundaries`: StatCan shapefile, directory containing a shapefile, or
  prepared GeoJSON.
- `--geo-column`: geography ID column in the household CSV.
- `--geo-id-field`: boundary attribute matching the household geography ID;
  inferred for standard StatCan columns such as `ct`, `ada`, `da`, and `csd`.
- `--census-vintage`, `--geo-level`, `--geo-namespace`, and
  `--geo-dguid-column`: explicit geography identity embedded in a single-run
  map. A national plan supplies these values itself.
- `--out`: destination HTML file; with `--both`, its stem is the shared prefix
  for the two suffixed HTML filenames.
- `--title`: title shown in the map panel.
- `--coord-precision`: output coordinate precision.
- `--jurisdiction`: one or more completed province/territory codes when
  `POPULATION` is a partial national DA or ADA plan.

For a completed national plan, `--boundaries`, `--geo-column`, and
`--geo-id-field` are inferred. For a single population, the ID field is also
inferred from a standard StatCan `--geo-column`. The default coordinate
precision is 5 for a single population and 3 for a national plan.

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

For a reviewed pack, use the same explicit counts and evidence in planning and
calibration:

```python
pack = spc.read_control_pack("statcan-2021-core-private-household-da-v1")
pack_population = spc.LinkedPopulationFiles(
    households=Path("reviewed-2021-candidates/households.csv"),
    persons=Path("reviewed-2021-candidates/persons.csv"),
)
household_controls = spc.read_controls("household-controls.csv")
person_controls = spc.read_controls("person-controls.csv")
universe_counts = {
    "24660244": {
        "total_population": 610,
        "persons_in_private_households": 610,
    }
}
evidence = spc.build_control_pack_evidence(
    pack,
    household_controls,
    person_controls,
    geographies=universe_counts,
)
plan = spc.plan_control_pack(
    pack,
    pack_population,
    household_controls,
    person_controls,
    evidence=evidence,
)
if not plan["passed"]:
    raise ValueError(plan["issues"])

result = spc.calibrate_small_area(
    pack_population,
    household_controls,
    person_controls=person_controls,
    control_pack=pack,
    control_pack_evidence=evidence,
    geography_dimension="da",
    geography_column="DAUID",
    output_dir="bounded-da-population",
)
```

As in the JSON example above, the counts are placeholders showing the API
shape, not reusable evidence for a real geography.

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

## Troubleshooting

**The profile, relationship file, and boundaries do not join:** confirm that
all three products use the same Census vintage and requested geography level.
Do not repair a mismatch by truncating identifiers or joining on a convenient
prefix.

**Preparation reports incomplete controls:** suppressed, zero, or missing
household-size or tenure vectors are excluded and reported. Review the exact
geographies and source values; do not impute them merely to make the plan
complete.

**Preparation finds usable controls without boundaries:** the planner stops
because those households could not be represented in the map and geography
evidence. Confirm that the boundary file is the registered national product and
that its identifiers were preserved during conversion.

**A DA plan is refused by `national-ada`, or vice versa:** use the command group
matching the plan's geography identity. DA and ADA share execution mechanics,
not identifiers or source products.

**Model conditioning fails for a jurisdiction:** inspect the package's
supported `PR` conditions. The territories share the hierarchical PUMF's
combined `PR=70` candidate condition; territorial controls remain separate.
Do not disable conditioning unless a research review supports an unconditioned
candidate pool.

**The run stops for low disk space:** compare free space with the plan's
`recommended_free_space_bytes`. Move the workspace, reduce the bounded scope,
or free space before using `--allow-low-disk`; the override does not reduce the
actual output.

**A partial national map is refused or misleading:** pass one or more completed
`--jurisdiction` values. A national map is produced automatically only when the
whole plan is complete.

**A prepared national-map boundary is unavailable:** configure the published
geodata catalogue as described in {doc}`geodata`, place a matching
`*-display-topo.geojson` in the plan's `boundaries/` directory, or retain the
canonical-boundary fallback. Do not substitute a display asset from another
Census vintage, level, or jurisdiction.

**One or more fits do not converge:** inspect candidate category support,
control universes, largest residuals, and the realized integer result. More
iterations cannot make structurally incompatible controls fit.

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

**What the 0.9 report adds.** `methodological_diagnostics` independently
recomputes fractional and realized counts from candidate rows and emitted
weights. For each geography it records weight concentration and Kish effective
sample size, candidate reuse, supported rare categories, declared zero-target
constraints, and every assessed cell. Linked-person contributions are summed
inside each candidate household before that household's weight is applied.
`field_status` says `targeted` or `uncontrolled`; `claim_status` remains
`not-assessed` because a fitted margin and small residual do not by themselves
establish source validity or local representativeness. See
{doc}`methodological-validation` for the oracle, integerization, multi-scale,
and external-comparison evidence.

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

### Completion, convergence and coverage

`geo prepare-controls --incomplete-geographies exclude` prints a concise warning
on stderr and points to `plan.json` for individual exclusions. Province coverage
also reports known omitted households and areas with unknown household counts;
unknown counts are not treated as zero. The default remains `error`.

`geo calibrate` reports completion separately from fractional-fit convergence.
For prepared controls it prints household and person targets, generated counts,
and signed differences (generated minus target). The independent realized audit
reports exact control-cell matches separately: a converged fractional fit does
not guarantee an exact integer population. Detailed residuals and area statuses
remain in the report. These messages use stderr, preserving JSON stdout.

Exit status zero means the command completed and wrote its outputs. It does not
mean every geography converged or every realized control matched. Non-converged
outputs remain available for inspection and map generation. Invalid inputs,
unsupported strict controls and invalid household/person linkage still fail.
The default zero-target policy remains `structural`; `observed` explicitly permits
reported approximation without changing the prepared targets.

### Broad Canada-wide ADA workflow

`geo prepare-controls --canada` selects ADAs across every province and territory.
Supply the separate Canada/province Census Profile using `--national-profile`.
The country root is observed directly (ALT_GEO_CODE `01`, DGUID
`2021A000011124`); rounded ADA totals never replace it. Use the published
`canada-2021-all-fields` model, then the same `geo calibrate` and `geo map --both`
stages as for a province. Explicit `--incomplete-geographies exclude` and
`--zero-target-policy observed` retain the same warnings and residual reporting.
The resulting population covers private households, with coverage gaps stated
in the plan; it does not synthesize residents of collective dwellings.

A complete national example, using a fresh output directory and verified local
inputs, is:

```bash
CLI=.venv/bin/synthpopcan
R=runs/canada-cli

$CLI geo prepare-controls /absolute/path/to/98-401-X2021012_eng_CSV.zip \
  --canada \
  --national-profile /absolute/path/to/98-401-X2021001_English_CSV_data.csv \
  --source-profile statcan-hierarchical-2021 \
  --normalization observed-proportional --incomplete-geographies exclude \
  --out "$R/controls"
$CLI models generate canada-2021-all-fields \
  --households 500000 --random-seed 20211102 --out "$R/candidates"
$CLI geo calibrate "$R/candidates" --controls "$R/controls" \
  --geo-dimension ada --pool-size 20000 --subsample-seed 42 --augment-support \
  --workers 2 --joint-solver hybrid --zero-target-policy observed \
  --max-iterations 16 --tolerance 0.01 --out "$R/population"
$CLI geo map "$R/population" --both \
  --person-profile statcan-hierarchical-2021 \
  --boundaries /absolute/path/to/2021-boundary-ada-display-topo.geojson \
  --geo-column ada --geo-id-field geo_id --census-vintage 2021 --geo-level ada \
  --geo-namespace statcan:census:2021:ada --out "$R/canada.html"
```

The 500,000 generated households are the candidate pool. The retained published
household controls determine the final population size; exclusions and realized
person-target differences remain in the reports.

### Iteration limits and observed approximation

`geo calibrate` and `geo synthesize` default to 16 strict iterations per stage. Use
`--max-iterations 1000` (or another positive value) for a larger budget. The
limit applies to the preliminary household fit as well as the linked fit;
`household_stage` records preliminary convergence, iterations and residuals
separately. A low budget is not proof that a non-converged system is infeasible.

With explicit `--zero-target-policy observed`, strict non-convergence can now
use the fixed-household-total entropy/least-squares approximation, keeping all
original targets and prior zeros. At higher budgets, a strict attempt compares
weights after 150 and 300 sweeps; stationary weights trigger reported
approximation, while moving weights retain the remaining requested budget.
The approximate solver has a separate 100-step trust-region Newton budget;
`--max-iterations` controls strict fitting, not this numerical optimizer. Centered
orthogonal coordinates remove redundant control directions without changing
the original objective or targets. The report records both budgets, strict
iteration counts, the fallback reason and optimizer termination. Optimizer
success remains separate from control convergence. The structural policy stays
strict and does not opt into this approximation.

Large plain CSV combination and linkage projection can use the optional
`performance` extra's bounded native parser. Unusual CSV records retain the
reference parser's validation and error semantics. Final files are independently
checked for identifier uniqueness, household links and sizes; combination also
checks inherited geography. SQLite validation uses an on-demand cache bounded
at 256 MiB. Weight diagnostic definitions are unchanged; float64 reductions may
differ in the last few bits from scalar sums. Unbounded integer reuse totals
retain their reference calculation when necessary.

With the optional performance extra, large pandas string tables can be written
in bounded 65,536-row native chunks. Other dtypes and unsupported values retain
pandas serialization. The emitted CSV bytes and integrity accounting follow the
same contract. Paired HTML views share geometry within that invocation while
keeping their feature properties independent. No process-wide geometry cache
is retained.

Native linkage validation extracts bounded 4,096-record batches directly from
parsed buffers. Population combination matches household/person geography with
per-source native lookup expressions. Reference fallback and final-file checks
remain active; completed source lookup tables are released before validation.

Native readers use bounded 8 MiB input buffers and NumPy carriage-return safety
checks. The scratch validation database uses 16 KiB pages within the existing
256 MiB cache bound; duplicate recovery and ordered diagnostics are unchanged.
