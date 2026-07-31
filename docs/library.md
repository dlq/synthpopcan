# Advanced Library Use

The Python library is for people who want to use SynthPopCan inside
**notebooks**, **scripts**, **research pipelines**, or **teaching materials**.
The command line remains the friendliest surface for one-off work, but the
library provides a **small beginner API** for common workflows and
**lower-level modules** for research code that needs more control.

This section does **not** repeat the methodological discussion from the command
line chapters. If we are new to a modelling approach, start with the
corresponding command-line page first:

- [IPF](ipf.md) explains calibration, impossible controls, non-convergence, and
  the interpretive limits of a successful fit.
- [Controls](controls.md) explains normalized control tables and category
  mappings.
- [Statistics Canada Sources](statcan.md) explains WDS and Census Profile source
  discovery.
- [Small-Area Linked Synthesis](small-area.md) explains household-first
  calibration, geography controls, integerization, and mapping.
- [Prepared Display Boundaries](geodata.md) explains verified display-only
  geometry and why it remains separate from canonical analytical boundaries.
- [External-Data Enrichment](enrichment.md) explains source authority,
  immutable resource revisions, geography-safe sidecars, and the limits of a
  successful join.
- [Tree Models](tree.md) explains household/person generation, tree and forest
  concepts, support, purity, and model quality.
- [Validate](validate.md) explains what validation reports do and do not prove.

Start with [Getting Started With the Beginner API](library-getting-started.md)
unless we already know we need **lower-level objects** such as `IPFMargin`,
`ControlTable`, or `FrequencyTreeModel`. This page is the advanced guide to the
full library surface.

```{admonition} These are composable workflow fragments
:class: note

The examples on this page are complete Python fragments, but most are not
standalone teaching programs. They use files introduced in the surrounding
section or values created by an earlier fragment. Replace research paths and
run the sections in order when they share variables such as `controls_path` or
`output_dir`. Live Statistics Canada examples require a network connection, and
microdata examples require appropriately controlled local source files.
```

## Import Style

For longer research code, import from the **module that owns a concept**:

```python
from pathlib import Path

from synthpopcan.controls import read_control_table
from synthpopcan.ipf import expand_records, fit_ipf
```

The module imports are usually clearer in longer research code because they
show whether a step belongs to controls, IPF, microdata, tree modelling, or
validation.

Use `synthpopcan.api` or `import synthpopcan as spc` for the beginner-friendly
workflow functions. Use modules such as `synthpopcan.ipf`,
`synthpopcan.controls`, and `synthpopcan.tree` when we need lower-level
objects or advanced options.

## Local Data and Sources

The local-data helpers let a notebook or research script check its expected
directories and inspect source-file structure before a modelling function reads
the data. The layout check is non-destructive and does not open private source
rows:

```python
from pathlib import Path

from synthpopcan.localdata import inspect_local_data_layout
from synthpopcan.sources import inspect_source_root, read_source_schema

data_root = Path("data")

for check in inspect_local_data_layout(data_root):
    print(check.status, check.name, check.path)

summary = inspect_source_root(data_root / "raw")
schema = read_source_schema(data_root / "raw" / "example.csv")

print(summary["files"], summary["extensions"])
print(schema["delimiter"], schema["columns"])
```

`inspect_source_root` counts files and extensions without parsing their rows.
`read_source_schema` reads the header and detects the delimiter, but does not
return source records. These are useful first checks when a project needs to
record what arrived before deciding how to normalize it.

```{admonition} Sampling is a disclosure decision
:class: warning

The lower-level `read_source_sample` function returns actual source rows. Unlike
the command-line `data sample` wrapper, it does not require an
`--allow-private` confirmation. Call it only when we have already decided that
showing those rows in a notebook, terminal, log, or saved output is appropriate.
```

For a public or fictional file, sampling can be explicit and small:

```python
from synthpopcan.sources import read_source_sample

preview = read_source_sample(data_root / "raw" / "example.csv", rows=3)
preview["rows"]
```

See [Data](data.md) for the local directory policy, privacy boundaries, and
command-line safeguards that also apply when we call these functions directly.

## Controls

Controls are the public library representation of **target totals**. A
`ControlTable` contains one or more `ControlMargin` objects; each margin contains
`ControlCell` objects with category labels and counts. Use these objects when
we want to inspect or transform controls before fitting.

```python
from pathlib import Path

from synthpopcan.controls import read_control_table, write_control_table

controls = read_control_table(Path("controls.csv"))

for margin in controls.margins:
    print(margin.name, margin.dimensions, len(margin.cells))

ipf_margins = controls.to_ipf_margins()
write_control_table(Path("normalized-controls.csv"), controls)
```

For source-specific control preparation, the library exposes the same adapters
used by the command line:

```python
from pathlib import Path

from synthpopcan.controls import (
    build_wds_category_mapping_template,
    inspect_wds_zip,
    read_wds_control_table,
)

inspection = inspect_wds_zip(Path("table.zip"))
print(inspection["dimension_candidates"])

template = build_wds_category_mapping_template(
    Path("table.zip"),
    dimensions=("Age group", "Gender"),
    preset="canonical",
)

controls = read_wds_control_table(
    Path("table.zip"),
    dimensions=("Age group", "Gender"),
    count_column="VALUE",
    margin_name="age_sex",
    category_mapping=template,
)
```

The category names in controls must match the category names in the seed records
that will be fitted. The [Controls](controls.md) chapter has more detail on
category mappings and common normalization problems.

## IPF

The IPF library surface is deliberately small. `IPFMargin` describes the target
cells, `fit_ipf` calibrates seed-record weights, and `IPFResult` stores the
records, weights, convergence flag, iteration count, and maximum residual.

```python
from pathlib import Path
import csv

from synthpopcan.controls import read_control_table
from synthpopcan.ipf import expand_records, fit_ipf, validate_margin_coverage

with Path("seed.csv").open(newline="") as handle:
    seed_records = list(csv.DictReader(handle))

controls = read_control_table(Path("controls.csv"))
margins = controls.to_ipf_margins()

validate_margin_coverage(seed_records, margins)
fit = fit_ipf(
    seed_records,
    margins,
    weight_field="WEIGHT",
    max_iterations=250,
    tolerance=0.01,
)

print(fit.converged, fit.iterations, fit.max_abs_error)

expanded_rows = expand_records(seed_records, fit.weights)
```

If `validate_margin_coverage` or `fit_ipf` raises a `ValueError` about a target
cell with no seed records, the controls cannot be represented by the seed sample
as given. The [IPF](ipf.md) chapter discusses this as a modelling problem, not
just a software error.

## Microdata

Microdata helpers load supported seed samples and export columns for IPF or tree
training. The library does not hide that these are source-specific adapters:
different Statistics Canada files encode households, people, geography, and
weights differently.

```python
from pathlib import Path

from synthpopcan.microdata import (
    export_seed_rows,
    read_statcan_2016_hierarchical_seed_sample,
)

sample = read_statcan_2016_hierarchical_seed_sample(Path("hierarchical.csv"))
print(sample.as_summary())

seed_rows, manifest = export_seed_rows(
    sample,
    columns=("AGEGRP", "SEX", "PR"),
)
print(manifest["rows_written"], manifest["columns"])
```

For tree modelling, first ask the source adapter which column blocks are
available, then resolve the blocks into explicit target and conditioning
columns. This example keeps the exported rows in memory so we can inspect the
design before writing files:

```python
from synthpopcan.microdata import (
    export_training_rows,
    resolve_tree_column_block_pair,
    suggest_tree_column_blocks,
)

suggestions = suggest_tree_column_blocks(sample)
print([block["name"] for block in suggestions["blocks"]])

(
    household_targets,
    household_conditions,
    person_targets,
    person_conditions,
    design_report,
) = resolve_tree_column_block_pair(
    sample,
    household_block="household_core",
    person_block="person_demographics",
)

person_training, person_manifest = export_training_rows(
    sample,
    level="person",
    target_columns=person_targets,
    conditioning_columns=person_conditions,
)
```

## Statistics Canada Sources

The `statcan` module is for discovery and download automation. It wraps
Statistics Canada WDS endpoints and registered 2016 and 2021 Census Profile
bulk products with small Python functions that return plain dataclasses,
dictionaries, and paths.

```python
from pathlib import Path

from synthpopcan.statcan import (
    fetch_census_profile,
    fetch_wds_metadata,
    fetch_wds_table,
    search_wds_tables,
    summarize_wds_metadata,
)

matches = search_wds_tables("age sex population", limit=5)
for match in matches:
    print(match.product_id, match.title_en)

metadata = fetch_wds_metadata(matches[0].product_id)
summary = summarize_wds_metadata(metadata)
print(summary["ipf_suitability"])

zip_path = fetch_wds_table(matches[0].product_id, Path("data/raw/statcan/wds"))
profile_path = fetch_census_profile(
    "ct",
    Path("data/raw/statcan/census/2021/profiles/ct"),
    census_year=2021,
)
```

Live source functions depend on Statistics Canada service availability and may
raise network or source-format errors. In reproducible research scripts, store
the downloaded source files and provenance manifests rather than relying on live
downloads during every run.

## Geography Identity

**Added in 0.7.0.** A geography code is not self-describing. The same
short identifier can be meaningless or misleading without its Census vintage,
level, and namespace. `GeographyUniverse` records the context shared by a file;
`GeographyIdentity` represents one identifier within that context.

```python
from synthpopcan.geography import (
    ensure_geography_compatible,
    statcan_geography_identity,
    statcan_geography_universe,
)

da_universe = statcan_geography_universe(
    2021,
    "da",
    "DAUID",
    dguid_column="DGUID",
)
left = da_universe.identity("24660001", dguid="2021S051224660001")
right = statcan_geography_identity(
    2021,
    "da",
    "24660001",
    dguid="2021S051224660001",
)

ensure_geography_compatible(left, right, require_same_identifier=True)
```

Compatibility checks reject different vintages, levels, namespaces, short
identifiers, or conflicting DGUIDs. They do not infer a parent/child
relationship: use an authoritative relationship product and
`GeographyRelationship` when connecting DA, CSD, CMA/CA, or other levels.

## Small-Area Synthesis

The lower-level small-area modules separate **control extraction**, **run
planning**, **calibration**, and **mapping**. That separation is useful when a
research notebook needs to inspect intermediate decisions or replace one stage
with a project-specific method. Start with the methodological discussion in
[Small-Area Linked Synthesis](small-area.md); the code below assumes we already
understand why the controls and candidate population must describe compatible
universes.

### Build and Inspect Geography Controls

The 2016 Census Profile adapter extracts household-size and tenure rows, filters
the requested geographies, and scales them to an explicit household target. We
should inspect `dropped_geographies` rather than silently accepting missing
margins.

```python
from pathlib import Path

from synthpopcan.small_area_controls import (
    extract_controls_from_profile,
    scale_and_validate_controls,
    write_controls_csv,
)

raw_controls = extract_controls_from_profile(
    Path("98-401-X2016043_English_CSV_data.csv"),
    geography_column="ct",
    geo_prefix="421",  # Quebec City CMA
)

scaled_controls, dropped_geographies = scale_and_validate_controls(
    raw_controls,
    target_total=338_000,
)
print("dropped", dropped_geographies[:10])

controls_path = Path("quebec-city-ct-controls.csv")
write_controls_csv(
    scaled_controls,
    controls_path,
    geography_column="ct",
    household_size_column="household_size_group",
)
```

The member IDs and total in this example are specific to the documented 2016
workflow. Keep the original profile, extraction choices, target total, and
dropped-geography list with the generated controls.

### Estimate Before Calibrating

Read the normalized controls and estimate the scale before generating a large
candidate population:

```python
from synthpopcan.controls import read_control_table
from synthpopcan.small_area_synthesis import estimate_small_area_run

controls = read_control_table(controls_path)
estimate = estimate_small_area_run(
    controls,
    geography_dimension="ct",
    candidate_households=50_000,
    pool_size=10_000,
)

print(estimate["target_geographies"])
print(estimate["estimated_total_output_rows"])
print(estimate["recommended_surface"])
for note in estimate["guidance"]:
    print(note)
```

The estimate is a planning aid, not a quality result. Candidate support,
convergence, and integerized residuals still need review after calibration.

### Calibrate Linked Candidate Files

Use `calibrate_linked_household_csvs` when a pipeline needs explicit input and
output paths or lower-level tuning. The function keeps people attached to their
household and returns the same machine-readable report used by the CLI.

```python
from synthpopcan.small_area_synthesis import calibrate_linked_household_csvs

output_dir = Path("quebec-city-population")
output_dir.mkdir(exist_ok=True)

report = calibrate_linked_household_csvs(
    households_path=Path("candidates/households.csv"),
    persons_path=Path("candidates/persons.csv"),
    controls_path=controls_path,
    geography_dimension="ct",
    geography_column="ct",
    households_out=output_dir / "households.csv",
    persons_out=output_dir / "persons.csv",
    report_out=output_dir / "report.json",
    pool_size=10_000,
    subsample_seed=42,
)

summary = report["summary"]
print(summary["non_converged_count"] == 0, summary["max_abs_error"])
```

If we also have compatible person controls, pass `person_controls_path`. Review
the input warnings and both fractional and integerized residual summaries in
the report before treating the output as usable.

### Prepare Boundaries and Render a Map

Boundary preparation is normally a one-time download. The rendering function
joins aggregate statistics to matching boundary IDs and writes a standalone
HTML file; individual synthetic records should not be interpreted as known
households at known locations.

```python
from synthpopcan.map_render import (
    prepare_boundaries_geojson,
    render_synthesis_map,
)
from synthpopcan.statcan import fetch_boundary_zip

boundary_dir = Path("data/derived/statcan/census/2021/boundaries")
shapefile = fetch_boundary_zip("ct", boundary_dir, census_year=2021)
geojson = prepare_boundaries_geojson(
    shapefile,
    id_field="CTUID",
    out_path=boundary_dir / "2021-boundary-ct.geojson",
    property_fields=("DGUID", "LANDAREA", "PRUID"),
)

map_path = render_synthesis_map(
    households_path=output_dir / "households.csv",
    persons_path=output_dir / "persons.csv",
    boundaries_path=geojson,
    geography_column="ct",
    geography_id_field="CTUID",
    out_path=Path("quebec-city-map.html"),
    title="Synthetic Quebec City Households",
)
```

For most notebooks, the top-level `spc.calibrate_small_area` and
`spc.render_small_area_map` wrappers are shorter. Use these module functions
when we need the intermediate reports, custom output paths, or explicit boundary
preparation shown here.

### Plan National DA or ADA Work

**Maintainer template: large official inputs required.** National DA and
ADA execution uses one shared planning contract while preserving each level's
different Census Profile source layout. The planner verifies source coverage,
uses the final 2021 DGRF for province/territory relationships, partitions the
national boundary file, and writes restartable batches.

```python
from pathlib import Path

from synthpopcan.national_small_area import (
    national_2021_profile_paths,
    prepare_canada_small_area_plan,
)

geography_level = "da"
profile_root = Path("data/raw/statcan/census/2021/profiles/da")
profile_paths = national_2021_profile_paths(profile_root, geography_level)

plan = prepare_canada_small_area_plan(
    profile_paths,
    Path("data/derived/statcan/census/2021/boundaries/2021-boundary-da.geojson"),
    Path("data/raw/statcan/census/2021/geography/relationships/2021_98260004.csv"),
    Path("data/work/canada-da-2021"),
    geography_level=geography_level,
    max_households_per_batch=100_000,
)

print(plan["coverage"])
print(plan["storage_estimate"])
```

`execute_canada_small_area_plan` is a lower-level executor that accepts a
project-supplied batch callback. The maintained prepared-model execution,
candidate-pool caching, worker limits, resume behavior, and national map are
assembled by `synthpopcan geo national-da run` and `national-ada run`; use
those commands unless we are deliberately implementing another batch backend.

## External-Data Enrichment

**Research template: replace every research path and source record.**
The enrichment library separates source meaning, exact resource bytes,
normalized layer structure, and the manifest that composes a layer with an
unchanged linked population.

```python
from pathlib import Path

from synthpopcan.enrichment import (
    import_normalized_layer,
    read_resource_record,
    read_source_profile,
)

source = read_source_profile(Path("source-profile.json"))
resource = read_resource_record(Path("resource-record.json"))

manifest, validation = import_normalized_layer(
    Path("synthetic-da-population"),
    Path("normalized-area-context.csv"),
    Path("area-context-enrichment"),
    source=source,
    resource=resource,
    layer_id="example.area-context.2025",
    layer_class="area-attributes",
    key_columns=("DAUID",),
    variables=("context_category",),
    base_geography=source.geography,
    observed_status="observed",
    reproduction_request={
        "workflow": "enrichment",
        "operation": "import-normalized-layer",
        "normalization_notebook": "prepare-area-context.ipynb",
    },
    limitations=("Area context is not person-level exposure.",),
)

print(validation["passed"], manifest.layers[0].row_count)
```

The lower-level function returns the validated in-memory manifest as well as
the report. Use `verify_enrichment_manifest` after copying or restoring the
bundle. Start with {doc}`enrichment` before using these objects; a technically
valid sidecar is not evidence that its variables support a substantive claim.

## Prepared Display Boundaries

**Added in 0.7.0; network required for an HTTPS catalogue.** The geodata
library retrieves the same display-only assets as the `geodata` command group:

```python
from synthpopcan.geodata import (
    fetch_display_boundaries,
    geodata_cache_dir,
    load_geodata_catalogue,
)

catalogue_url = (
    "https://github.com/dlq/synthpopcan/releases/download/"
    "geodata-v1/geodata-catalogue.json"
)

catalogue = load_geodata_catalogue(catalogue_url)
boundaries = fetch_display_boundaries(
    2021,
    "da",
    pruid="24",
    catalogue=catalogue_url,
)

print(catalogue["release_version"], boundaries, geodata_cache_dir())
```

The fetcher requires one exact year, geography level, and regional scope; it
does not choose a merely similar asset. It validates the compressed archive and
the unpacked GeoJSON against separate SHA-256 values, then installs the file
atomically in the cache.

Keep the catalogue metadata with the map provenance. These functions establish
which published display bytes we used; they do not establish that the geometry
matches a population's Census vintage, identifier namespace, or control
universe. Start with {doc}`geodata` for the coverage table and the distinction
between display and analytical geometry.

## Tree Models

The tree library exposes two model families: `FrequencyTreeModel`, which stores
conditional aggregate outcomes, and `CartTreeModel`, which stores a serialized
scikit-learn CART classifier. The command-line [Tree Models](tree.md) chapter
discusses the methodological risks; the library API gives us the objects needed
to train, audit, serialize, and generate from those models.

Portable frequency and CART models can be read and used for generation with the
base installation. Starting with `0.7.0`, calling
`train_cart_model` requires the optional `model-build` extra; frequency-model
training does not. See [Installation](installation.md) for the environment
command.

When we are ready to train from a file, the training CSV should contain the
same target and conditioning columns chosen in the microdata step above. The
command-line `microdata export-training` examples show one way to write that
CSV.

```python
from pathlib import Path

from synthpopcan.tree import (
    audit_tree_model,
    generate_tree_rows,
    read_tree_training_sample,
    train_frequency_model,
    write_tree_model,
)

sample = read_tree_training_sample(
    Path("person-training.csv"),
    level="person",
    target_columns=("AGEGRP", "SEX"),
    conditioning_columns=("PR", "household_size"),
    weight_column="WEIGHT",
)

model = train_frequency_model(sample, random_seed=42, min_support=10)
audit = audit_tree_model(model, min_support=50, max_purity=0.95)
print(audit["passed"], audit["summary"])

rows = generate_tree_rows(
    model,
    rows=1000,
    conditions={"PR": "24", "household_size": "2"},
    random_seed=42,
)

write_tree_model(Path("person-model.json"), model)
```

Linked household/person generation uses one household model and one person
model. The shared conditioning columns on the person model must be available in
generated household rows.

```python
from pathlib import Path

from synthpopcan.tree import (
    generate_linked_population,
    read_tree_model,
    validate_linked_population,
)

household_model = read_tree_model(Path("household-model.json"))
person_model = read_tree_model(Path("person-model.json"))

households, persons = generate_linked_population(
    household_model,
    person_model,
    households=500,
    household_conditions={"PR": "24"},
    random_seed=42,
)

link_report = validate_linked_population(households, persons)
print(link_report["passed"])
```

## Validation

Validation functions return JSON-serializable dictionaries so they can be saved,
printed, tested, or rendered in notebooks. They are checks on a particular
artifact, not a claim that a synthetic population is substantively correct.

This example continues with `controls` and `fit` from the **Controls** and
**IPF** sections above:

```python
from synthpopcan.validation import build_control_validation_report

report = build_control_validation_report(
    controls,
    fit.records,
    fit.weights,
    tolerance=0.01,
    artifact_kind="weights",
)

if not report["passed"]:
    for issue in report["issues"][:5]:
        print(issue["message"])
```

Tree-output validation compares generated distributions with a training view.

The next example continues with `person_training`, `person_targets`, and
`person_conditions` from **Microdata**, and `rows` from **Tree Models**:

```python
from synthpopcan.validation import build_tree_output_validation_report

report = build_tree_output_validation_report(
    training_rows=person_training,
    generated_rows=rows,
    target_columns=person_targets,
    conditioning_columns=person_conditions,
    weight_field="WEIGHT",
    tolerance=0.05,
)
```

See [Validate](validate.md) for the interpretive caveats that should accompany
validation reports in research notes.

## API Reference

The [API Reference](api.rst) is generated from docstrings with Sphinx autodoc.
It is the place to look for signatures, return types, and member-level notes
after we understand the workflow-level concepts above.
