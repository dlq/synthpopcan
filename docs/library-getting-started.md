# Getting Started With the Beginner API

{download}`Download as Jupyter notebook <_static/library-getting-started.ipynb>`

The beginner API is the **supported first path** for notebooks, teaching examples,
and short scripts. It is designed for readers who want to ask research
questions with synthetic population data without first learning every internal
module in SynthPopCan.

It gives us a few functions for **common work**:

- fit seed rows to control totals with IPF;
- save weighted or expanded IPF output;
- generate linked household/person rows from a prepared model package;
- calibrate generated linked household/person candidates to small-area
  household controls;
- render a browser map from calibrated small-area output; and
- attach a validated external-data sidecar without changing the linked
  household/person files; and
- package linked household/person files for a portable, validated handoff.

It does **not** expose training, auditing, packaging, source inspection, or release
workflows at the top level. Those remain available in the command line and in
the lower-level library modules described in [Advanced Library Use](library.md).

## The Beginner Paths

Three beginner API paths correspond to the **three web app paths**:

1. **IPF from margin tables:** read seed rows, read normalized controls, fit
   IPF weights, then write a weighted or expanded population artifact.
1. **Generate from existing model:** fetch or read a reviewed model package, generate
   linked household/person rows, then write the generated CSV files.
1. **Small-area linked synthesis:** take generated linked household/person
   candidate CSVs, calibrate household rows to small-area controls, and write
   household/person CSVs with an assigned geography such as census tract or ADA.

The API also provides two command-line/library-only paths:

4. **External-data enrichment:** attach a validated normalized sidecar layer to
   an existing linked population while preserving the base files.
1. **Portable exchange:** package linked household/person CSVs with a data
   dictionary, provenance, governance classifications, and integrity evidence.

The web app runs IPF, prepared-model generation, and small-area synthesis as
durable Python-backed workflows. Use the **web app** when we want guided local
controls, previews, and downloads. Use the **beginner API** when we want the
same computational work inside a notebook, script, or teaching example, or
when we need enrichment or a portable exchange bundle.

## Why Use a Notebook?

A notebook lets us keep **prose, code, output, and interpretation together**. That
is useful for humanities and digital humanities work because the important part
of a synthetic population workflow is not only the final CSV. It is also the
record of choices:

- which source files were used;
- which rows and geographies were selected;
- which controls were fitted;
- whether the fit converged;
- what caveats should travel with the output.

Jupyter notebooks are a common way to do this kind of mixed narrative and
computational work. For readers who have not used notebooks before, this
introduction is written for humanities researchers and requires no prior
programming experience:

- [Introduction to Jupyter Notebooks](https://programminghistorian.org/en/lessons/jupyter-notebooks)
  — Programming Historian

For reference documentation once the notebook environment is running:

- [Project Jupyter documentation](https://docs.jupyter.org/en/latest/)
- [JupyterLab notebooks user guide](https://jupyterlab.readthedocs.io/en/latest/user/notebook.html)
- [Try Jupyter in a browser](https://jupyter.org/try)

This page assumes SynthPopCan is already available in the Python environment
used by the notebook. When we are working from a source checkout, we should
start with [Installation](installation.md).

## First Notebook Cell

Start with the path helper and the SynthPopCan import:

```python
from pathlib import Path

import synthpopcan as spc
```

The same functions are also available from `synthpopcan.api`, but importing the
package as `spc` keeps notebooks compact and readable.

If that import fails, the notebook is probably using a different Python
environment from the one where SynthPopCan is installed. In JupyterLab, we
should check the selected kernel for the notebook. A kernel is the Python
process that actually runs the code cells.

## Fit Seed Rows With IPF

**Runnable teaching example.** Run the cells in this section from top to bottom.
They create their own fictional files in the notebook's working directory.

A notebook is a good place to inspect files, try a small fit, and record the
choices that shaped the output. We will create a **tiny seed file** and a
**matching control file** so this example works with a normal PyPI installation
as well as a source checkout. These are fictional teaching values, not census
data.

```python
example_dir = Path("synthpopcan-notebook-example")
example_dir.mkdir(exist_ok=True)

seed_path = example_dir / "seed.csv"
seed_path.write_text(
    "PP_ID,AGEGRP,SEX,WEIGHT\n11101,adult,F,1\n11102,child,M,1\n",
    encoding="utf-8",
)

controls_path = example_dir / "controls.csv"
controls_path.write_text(
    "margin,dimensions,AGEGRP,SEX,count\n"
    "age,AGEGRP,adult,,100\n"
    "age,AGEGRP,child,,100\n"
    "sex,SEX,,F,100\n"
    "sex,SEX,,M,100\n",
    encoding="utf-8",
)
```

Writing the values here makes the example inspectable and reproducible. For a
research project, replace these files with a documented seed and controls that
describe the same population universe.

Read a seed file and look at its shape before fitting. The first line asks how
many rows were read. The second shows one row so we can inspect the column
names and values:

```python
seed = spc.read_seed(seed_path)

len(seed), seed[0]
```

The beginner API represents CSV rows as ordinary dictionaries. That keeps the
data straightforward to inspect without learning a dataframe library first. This cell
lists the column names from the first row:

```python
sorted(seed[0])
```

Read controls and inspect the margins:

```python
controls = spc.read_controls(controls_path)

[(margin.name, margin.dimensions, len(margin.cells)) for margin in controls.margins]
```

Before fitting, we should pause and ask whether the controls correspond to
columns in the seed rows. If a control uses an `age` category but the seed rows
have no `age` column, IPF cannot solve that mismatch for us.

Fit the seed rows to the controls:

```python
fit = spc.fit_ipf(
    seed,
    controls,
    weight_field="WEIGHT",
    max_iterations=250,
    tolerance=0.01,
)

{
    "converged": fit.converged,
    "iterations": fit.iterations,
    "max_abs_error": fit.max_abs_error,
}
```

If `converged` is false, do not treat the output as finished. Go back to the
[IPF](ipf.md) discussion of impossible controls, sparse controls, and
non-convergence before deciding whether to change the seed, controls, or
tolerance.

Write the fitted weights once the fit is acceptable:

```python
spc.write_weights(fit, "synthetic-weights.csv")
```

For many research workflows, weighted output is the best first artifact: it is
small, auditable, and keeps the relationship to the seed records visible. We can
still expand it when a downstream tool needs one row per generated record:

```python
expanded = spc.expand_population(fit)

len(expanded), expanded[0]
```

Then write the expanded rows:

```python
spc.write_population(expanded, "expanded-population.csv")
```

In a notebook, it is usually better to keep the weighted file and only expand
small examples. Expanded population files can be much larger than the seed file.

## Work Directly From Paths

When we do not need to inspect or filter rows between steps, pass paths
directly:

```python
fit = spc.fit_ipf(seed_path, controls_path, weight_field="WEIGHT")
spc.write_weights(fit, "weights.csv")
```

Use in-memory objects when we want to inspect or modify data between steps:

```python
seed = spc.read_seed(seed_path)
controls = spc.read_controls(controls_path)

adult_seed = [row for row in seed if row["AGEGRP"] == "adult"]
```

That pattern is useful in notebooks because each step can show its assumptions.
Add a Markdown cell above filters like this explaining why the selection was
made and what it excludes. Do not fit the original controls to a filtered seed
unless the controls have also been filtered or rebuilt for the same population
universe.

## Generate From a Prepared Model Package

The beginner API treats model training and release packaging as advanced
preparation work. SynthPopCan includes a small, fictional package so we can run
the complete generation path without downloading anything:

```python
package = spc.fetch_model("demo-linked-household-person")

population = spc.generate_from_model(
    package,
    households=100,
    conditions={"geo": "Demo North"},
    random_seed=42,
)

len(population.households), len(population.persons)
```

For a real project, list reviewed public packages with `synthpopcan models list`, then pass the chosen ID to `spc.fetch_model`. Downloadable packages need
an internet connection the first time; later calls reuse the verified local
cache. Use `spc.read_model_package(path)` when a collaborator gives us a local
package file instead.

Write linked output to a directory:

```python
population_files = spc.write_linked_population(
    population,
    "synthetic-linked-population",
)
```

That directory will contain `households.csv`, `persons.csv`, and a
linked-population `manifest.json`. Keep the model package, generated files,
notebook, and validation notes together so another reader can understand both
the result and the choices that produced it. The returned
`LinkedPopulationFiles` keeps the paths together for later steps. If rows are
already assigned, pass `geography_column` so the manifest records the
assignment.

## Assign Generated Rows To Small Areas

**Template: replace these paths.** This section continues from the generated
population above, but it also needs research-specific geography controls. Use
the runnable {doc}`small-area` walkthrough to prepare compatible controls and
boundaries first.

Small-area synthesis starts after a candidate linked population exists. The
controls must include one geography dimension, such as `ct` for census tract or
`ada` for aggregate dissemination area, plus household dimensions already
present in the candidate household CSV.

```python
result = spc.calibrate_small_area(
    population,
    "ct-tenure-controls.csv",
    person_controls="ct-age-sex-controls.csv",  # optional
    geography_dimension="ct",
    output_dir="synthetic-ct-population",
)

result.assigned_households, result.assigned_persons, result.converged
```

Household controls are fitted first. If compatible person controls are supplied,
SynthPopCan refines the household weights against linked-person category counts
without splitting households. Keep both fractional and integerized residual
summaries with the output. `result.population` contains the paired output paths,
and `result.details` retains the complete machine-readable report.

## Render the Small-Area Result as a Map

Once calibration has produced assigned household and person files, the beginner
API can render the same self-contained browser map as `synthpopcan geo map`.
Mapping also needs a boundary file for the same geography level. The
{doc}`small-area` walkthrough explains how to prepare and inspect that file.

The following cell continues the research-specific calibration template above:

```python
map_path = spc.render_small_area_map(
    households=result,
    boundaries="data/derived/statcan/census/2016/boundaries/2016-boundary-ct.geojson",
    geography_column="ct",
    out="synthetic-ct-map.html",
    title="Synthetic Census-Tract Population",
)

map_path
```

The standard `CTUID` boundary field is inferred from `geography_column="ct"`.
Pass `geography_id_field` explicitly for a non-standard boundary schema. The
boundary identifiers must match the assigned geography values in the household
output. The generated HTML contains the mapped data, but it needs an internet
connection when opened because the browser fetches base-map tiles.
Keep the calibration report with the map so readers can distinguish controlled
geographic patterns from variables that were only carried through from the
candidate population.

For a completed national DA or ADA run, pass its plan or output directory
directly. The same function infers the registered boundaries and geography,
streams all restartable household/person batches, and caches the standard map
statistics:

```python
map_path = spc.render_small_area_map(
    households="data/work/canada-ada-2021/plan.json",
)
```

For a completed jurisdiction within a partial national plan, pass its PRUID
explicitly. The resulting map is scoped to that jurisdiction rather than being
presented as national coverage:

```python
map_path = spc.render_small_area_map(
    households="data/work/canada-da-2021/plan.json",
    jurisdiction_pruids=["24"],  # Québec
    out="data/work/canada-da-2021/quebec-da-map.html",
)
```

## Attach an External Context Layer

For the two maintained public sources, use the reviewed adapters. They acquire
or reuse the pinned archive, normalize it, validate its source-specific
semantics, and publish all provenance records with the sidecar:

```python
from synthpopcan.geography import statcan_geography_universe

canfed = spc.enrich_can_fed(
    "synthetic-da-population/",
    output_dir="canfed-enrichment/",
    base_geography=statcan_geography_universe(2021, "da", "DAUID"),
)
odef = spc.enrich_odef(
    "synthetic-population/",
    output_dir="odef-enrichment/",
)
assert canfed.validation["passed"] and odef.validation["passed"]
```

Can-FED requires the population's explicit 2021 DA universe. ODEF is an
unlinked national facility inventory unless we deliberately supply compatible
2021 CSD geography for a coverage comparison. That comparison also requires
the population manifest to declare the same household CSDUID column supplied
to the adapter. See {doc}`enrichment` before interpreting either layer.

**Research template: prepare the source and geography records first.**
The complete {doc}`enrichment` walkthrough explains how to create
`source-profile.json`, register an immutable resource revision, normalize a
sidecar CSV, and interpret unmatched geographies.

Once those records exist, the beginner API keeps the call compact:

```python
enrichment = spc.enrich_population(
    "synthetic-da-population/",
    "normalized-area-context.csv",
    source_profile="source-profile.json",
    resource_record="resource-record.json",
    layer_id="example.area-context.2025",
    layer_class="area-attributes",
    key_columns=["DAUID"],
    variables=["context_category"],
    base_geography={
        "schema_version": "synthpopcan-geography-universe-v1",
        "census_vintage": 2021,
        "geography_level": "da",
        "identifier_namespace": "statcan:census:2021:da",
        "identifier_column": "DAUID",
        "dguid_column": None,
    },
    output_dir="area-context-enrichment/",
    limitations=["Area context is not person-level exposure."],
)

enrichment.validation["passed"]
```

The result points to the copied sidecar and its manifest. It does not return a
widened household or person table. Keep the source profile, resource record,
normalization code, manifest, and coverage report with the notebook.

## Package a Portable Handoff

Use an exchange bundle when another researcher or tool needs the linked
population plus enough metadata to inspect and validate it independently:

```python
exchange = spc.create_exchange_bundle(
    "synthetic-linked-population/",
    "synthetic-exchange/",
    reproduction={
        "interface": "python",
        "script": "population-notebook.ipynb",
    },
    access_classification="local",
    redistribution_status="not-assessed",
    limitations=["Fictional teaching population; not representative."],
)

assert exchange.report["passed"]
assert spc.validate_exchange_bundle(exchange.directory)["passed"]
```

The bundle preserves the two CSV files byte-for-byte and adds a linked-table
descriptor, data dictionary, provenance, validation record, and checksummed
manifest. It does not certify disclosure safety or grant permission to share
the data. See {doc}`exchange` before changing the conservative governance
defaults or declaring Census geography context.

## Reproducible Generation

Use a fixed random seed when generating from a model package so notebook runs
are reproducible:

```python
population = spc.generate_from_model(
    package,
    households=250,
    conditions={"geo": "Demo North"},
    random_seed=2026,
)
```

Leave `require_publishable=True`, its default, for ordinary work. Advanced
developers can disable that check while inspecting a trusted local development
package, but publishable or shared work should use a reviewed package.

## A Good Notebook Record

For humanities-facing research, a useful notebook should read like a short
method note. Include Markdown cells that answer:

- What source files or model packages did we use?
- What geography, period, or population is included?
- What controls were fitted, and which were left out?
- Did the IPF fit converge?
- Did we keep weighted output or expand it?
- What should another reader not infer from this output?

The code cells should then support that narrative. If a result changes after we
rerun the notebook, the prose should make it clear which random seed, filters,
controls, or package version shaped the result.

## Beginner API Objects

The beginner API groups a small set of names around common tasks.

**Read and fit IPF inputs:**

- {py:func}`~synthpopcan.api.read_seed`
- {py:func}`~synthpopcan.api.read_controls`
- {py:func}`~synthpopcan.api.fit_ipf`
- {py:func}`~synthpopcan.api.expand_population`
- {py:func}`~synthpopcan.api.write_weights`
- {py:func}`~synthpopcan.api.write_population`

**Generate linked households and people:**

- {py:func}`~synthpopcan.api.fetch_model`
- {py:func}`~synthpopcan.api.read_model_package`
- {py:func}`~synthpopcan.api.generate_from_model`
- {py:func}`~synthpopcan.api.write_linked_population`

**Assign and map small-area results:**

- {py:func}`~synthpopcan.api.calibrate_small_area`
- {py:func}`~synthpopcan.api.render_small_area_map`

**Attach validated external context:**

- {py:func}`~synthpopcan.api.enrich_can_fed`
- {py:func}`~synthpopcan.api.enrich_odef`
- {py:func}`~synthpopcan.api.enrich_population`

**Inspect returned results:**

- {py:class}`~synthpopcan.controls.ControlTable`
- {py:class}`~synthpopcan.ipf.IPFResult`
- {py:class}`~synthpopcan.api.LinkedPopulation`
- {py:class}`~synthpopcan.api.LinkedPopulationFiles`
- {py:class}`~synthpopcan.api.SmallAreaResult`
- {py:class}`~synthpopcan.api.EnrichmentResult`

## Where To Go Next

Continue to {doc}`library` when we need to inspect intermediate objects, prepare
source-specific controls, call lower-level calibration functions, or train and
audit models. That page assumes we already understand the corresponding method
and concentrates on composing the library modules.

Use the {doc}`api` when we already know the object or function name and need its
exact signature, parameters, return type, exceptions, or member-level notes. We
do not need to read the generated reference from beginning to end.
