# Library

The Python library is for people who want to use SynthPopCan inside notebooks,
scripts, reproducible research pipelines, or teaching materials. The command
line remains the friendliest surface for one-off work, but the library exposes
the same central concepts as Python objects: control tables, IPF margins, seed
samples, tree training samples, fitted models, generated rows, and validation
reports.

This section does not repeat the methodological discussion from the command
line chapters. If you are new to a modelling approach, start with the
corresponding command-line page first:

- [IPF](ipf.md) explains calibration, impossible controls, non-convergence, and
  the interpretive limits of a successful fit.
- [Controls](controls.md) explains normalized control tables and category
  mappings.
- [Statistics Canada Sources](statcan.md) explains WDS and Census Profile source
  discovery.
- [Tree Models](tree.md) explains household/person generation, tree and forest
  concepts, support, purity, and model quality.
- [Validate](validate.md) explains what validation reports do and do not prove.

The examples below show the same workflows as Python code.

## Import Style

For short notebooks, teaching examples, and early exploration, start with the
small top-level API:

```python
import synthpopcan as spc

controls = spc.read_controls("controls.csv")
fit = spc.fit_ipf("seed.csv", controls)
spc.write_weights(fit, "weights.csv")
```

This beginner surface accepts ordinary paths where possible and returns plain
Python objects. It is intentionally smaller than the full project.

For longer research code, import from the module that owns a concept:

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
`synthpopcan.controls`, and `synthpopcan.tree` when you need lower-level
objects or advanced options.

## Controls

Controls are the public library representation of target totals. A
`ControlTable` contains one or more `ControlMargin` objects; each margin contains
`ControlCell` objects with category labels and counts. Use these objects when
you want to inspect or transform controls before fitting.

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
columns:

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
Statistics Canada WDS endpoints and supported 2016 Census Profile bulk files
with small Python functions that return plain dataclasses, dictionaries, and
paths.

```python
from pathlib import Path

from synthpopcan.statcan import (
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
```

Live source functions depend on Statistics Canada service availability and may
raise network or source-format errors. In reproducible research scripts, store
the downloaded source files and provenance manifests rather than relying on live
downloads during every run.

## Tree Models

The tree library exposes two model families: `FrequencyTreeModel`, which stores
conditional aggregate outcomes, and `CartTreeModel`, which stores a serialized
scikit-learn CART classifier. The command-line [Tree Models](tree.md) chapter
discusses the methodological risks; the library API gives you the objects needed
to train, audit, serialize, and generate from those models.

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
from synthpopcan.tree import generate_linked_population, validate_linked_population

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

Tree-output validation compares generated distributions with a training view:

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
after you understand the workflow-level concepts above.
