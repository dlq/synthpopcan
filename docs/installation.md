# Installation

SynthPopCan is in early public release preparation. This page focuses on a
source-checkout installation for contributors and early users. Once the PyPI
project is enabled, users will also be able to install the published package
with `pip install synthpopcan`.

## Requirements

- Python 3.11 or newer.
- Git, when cloning from a repository.
- A Python environment tool. The current development workflow uses `uv`, but
  the rest of the documentation usually shows the installed `synthpopcan`
  command.
- Local source data staged outside git when working with real census or private files.

You do not need a database, a cloud account, or a web server for the
command-line workflows.

## Download the Source

Clone the repository, then enter the checkout:

```bash
git clone https://github.com/dlq/synthpopcan.git
cd synthpopcan
```

## Install the Development Environment

The repository currently uses `uv` for repeatable local development. If we do
not have `uv`, we should install it from the official documentation for our
platform.

From the repository root:

```bash
uv sync
```

This creates a local environment and installs SynthPopCan with its runtime
dependencies.

For documentation work:

```bash
uv sync --group docs
```

## Run the Command

If your environment exposes the console script, run:

```bash
synthpopcan --help
```

When working directly from the source checkout with `uv`, prefix commands with
`uv run`:

```bash
uv run synthpopcan --help
```

The rest of the documentation usually shows `synthpopcan ...` to focus on the
tool itself. If you have not activated an environment or installed the command,
use `uv run synthpopcan ...` instead.

Beginner command-line guidance is available with:

```bash
synthpopcan guide ipf
synthpopcan guide model
```

## Quick Getting Started

This tiny fixture workflow fits two seed rows to age and sex controls. It does
not download public data and does not use private microdata.

This is a smoke test for the command-line setup. For a fuller explanation of
each IPF step, see [IPF](ipf.md). For the equivalent notebook-oriented Python
workflow, see [Getting Started With the Beginner API](library-getting-started.md).

```bash
synthpopcan microdata export-seed \
  tests/fixtures/workflows/microdata_ipf/hierarchical.csv \
  --input-format statcan-2016-hierarchical \
  --columns AGEGRP,SEX \
  --out seed.csv

synthpopcan ipf check-inputs \
  --seed seed.csv \
  --controls tests/fixtures/workflows/microdata_ipf/controls.csv

synthpopcan ipf fit \
  --seed seed.csv \
  --controls tests/fixtures/workflows/microdata_ipf/controls.csv \
  --weight-field WEIGHT \
  --out weights.csv \
  --report fit-report.json

synthpopcan ipf report fit-report.json

synthpopcan validate controls \
  --population weights.csv \
  --controls tests/fixtures/workflows/microdata_ipf/controls.csv \
  --kind weights
```

If we are running from a source checkout without activating the environment, we
can add `uv run` before each `synthpopcan` command.

## Build the Documentation

```bash
uv run sphinx-build -W -b html docs docs/_build/html
```

The `-W` flag treats warnings as errors. This is intentional: it catches broken
links and malformed documentation before Read the Docs publishes the site.

Check the reStructuredText source files with:

```bash
uv run --group docs doc8 docs
```

Check Markdown formatting with:

```bash
uv run --group docs mdformat --check docs README.md
```

Apply Markdown formatting with:

```bash
uv run --group docs mdformat docs README.md
```

When changing examples, also run the examples that are presented as runnable.
Good examples are part of the interface: check command names, fixture paths,
column names, output files, and whether the example still makes sense in the
surrounding explanation.

## Local Data

SynthPopCan looks for local data under `data/` by default. Raw and private data
should stay out of git.

```text
data/
  raw/
  private/
```

Check the expected local layout with:

```bash
uv run synthpopcan data doctor
```

Use `--data-root PATH` or `SYNTHPOPCAN_DATA_ROOT` when the data lives somewhere
else.

## Working Folder Advice

Run commands from the repository root unless a page says otherwise. In examples,
lines ending with `\` continue onto the next line.

Most examples write small files such as `seed.csv`, `weights.csv`, and
`fit-report.json` in the current directory. For a real project, create a
separate working folder so outputs from different runs do not get mixed
together.

## Read the Docs

The project includes a `.readthedocs.yaml` file for Read the Docs. The published
build installs the package and Sphinx requirements, then builds from
`docs/conf.py`.

## Release Publishing

The repository includes a manual GitHub Actions workflow for PyPI publishing.
Before running it, the PyPI project owner should configure a trusted publisher
for:

- repository: `dlq/synthpopcan`
- workflow: `.github/workflows/publish.yml`
- environment: `pypi`
- package: `synthpopcan`
