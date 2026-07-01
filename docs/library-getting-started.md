# Getting Started With the Beginner API

{download}`Download as Jupyter notebook <_static/library-getting-started.ipynb>`

The beginner API is the **supported first path** for notebooks, teaching examples,
and short scripts. It is designed for readers who want to ask research
questions with synthetic population data without first learning every internal
module in SynthPopCan.

It gives us a few functions for **common work**:

- fit seed rows to control totals with IPF;
- save weighted or expanded IPF output;
- generate linked household/person rows from a prepared model package.
- calibrate generated linked household/person candidates to small-area
  household controls.

It does **not** expose training, auditing, packaging, source inspection, or release
workflows at the top level. Those remain available in the command line and in
the lower-level library modules described in [Advanced Library Use](library.md).

## The Same Two Beginner Workflows

The beginner API mirrors the **two main web app paths**:

1. **IPF from margin tables:** read seed rows, read normalized controls, fit
   IPF weights, then write a weighted or expanded population artifact.
1. **Generate from existing model:** read a reviewed model package, generate
   linked household/person rows, then write the generated CSV files.

It also exposes one follow-on workflow:

3. **Small-area linked synthesis:** take generated linked household/person
   candidate CSVs, calibrate household rows to small-area controls, and write
   household/person CSVs with an assigned geography such as census tract or ADA.

Use the **web app** when we want guided local controls, previews, and downloads.
Use the **beginner API** when we want the same work inside a notebook, script, or
teaching example.

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

A notebook is a good place to inspect files, try a small fit, and record the
choices that shaped the output.

The source checkout includes a **tiny already-exported seed file** and a **matching
control file**. We will use those first so the notebook example has concrete
paths:

```python
fixture_root = Path("tests/fixtures/workflows/microdata_ipf")
seed_path = fixture_root / "expected-seed.csv"
controls_path = fixture_root / "controls.csv"
```

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
preparation work. Once a package has been prepared and reviewed, generation is
short:

```python
package = spc.read_model_package("linked-model-package.json")

population = spc.generate_from_model(
    package,
    households=100,
    conditions={"geo": "Demo North"},
    random_seed=42,
)

len(population.households), len(population.persons)
```

Write linked output to a directory:

```python
spc.write_population(population, "synthetic-linked-population")
```

That directory will contain `households.csv` and `persons.csv`. Keep the model
package, generated files, notebook, and validation notes together so another
reader can understand both the result and the choices that produced it.

## Assign Generated Rows To Small Areas

Small-area synthesis starts after a candidate linked population exists. The
controls must include one geography dimension, such as `ct` for census tract or
`ada` for aggregate dissemination area, plus household dimensions already
present in the candidate household CSV.

```python
summary = spc.calibrate_small_area_linked(
    households="candidate-households.csv",
    persons="candidate-persons.csv",
    controls="ct-tenure-controls.csv",
    geography_dimension="ct",
    geography_column="ct",
    households_out="synthetic-households.csv",
    persons_out="synthetic-persons.csv",
    report_out="small-area-report.json",
)

summary["assigned_households"], summary["assigned_persons"]
```

The current small-area workflow calibrates household-level controls. Person rows
inherit the assigned household geography, so validate linked output and document
which person-level totals were not fitted directly.

## Reproducible Generation

Use a fixed random seed when generating from a model package so notebook runs
are reproducible:

```python
population = spc.generate_from_model(
    "linked-model-package.json",
    households=250,
    random_seed=2026,
)
```

Leave `require_publishable=True` unless we are deliberately inspecting a trusted
local development package:

```python
population = spc.generate_from_model(
    "linked-model-package.json",
    households=25,
    require_publishable=False,
)
```

That option is useful for development and teaching, but publishable or shared
work should use reviewed packages.

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

The beginner API exposes a small set of names:

- {py:func}`~synthpopcan.api.read_seed`
- {py:func}`~synthpopcan.api.read_controls`
- {py:func}`~synthpopcan.api.fit_ipf`
- {py:func}`~synthpopcan.api.expand_population`
- {py:func}`~synthpopcan.api.write_weights`
- {py:func}`~synthpopcan.api.read_model_package`
- {py:func}`~synthpopcan.api.generate_from_model`
- {py:func}`~synthpopcan.api.write_population`
- {py:class}`~synthpopcan.api.LinkedPopulation`
