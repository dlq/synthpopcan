# Installation

SynthPopCan is not yet published on PyPI and does not yet have a public
repository URL in these docs. This page is therefore a source-checkout
installation guide for early users and contributors. The download and package
installation section should be expanded once the distribution mechanism is set.

## Requirements

- Python 3.11 or newer.
- Git, once a public repository URL is available.
- A Python environment tool. The current development workflow uses `uv`, but
  end-user documentation should eventually prefer a normal installed
  `synthpopcan` command.
- Local source data staged outside git when working with real census or private files.

You do not need a database, a cloud account, or a web server for the
command-line workflows.

## Download the Source

This section is a placeholder until SynthPopCan has a public source URL.

```bash
git clone REPOSITORY_URL synthpopcan
cd synthpopcan
```

## Install the Development Environment

The repository currently uses `uv` for repeatable local development. If you do
not have `uv`, install it from the official documentation for your platform.

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

Eventually, installed users should be able to run:

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

## Quick Getting Started

This tiny fixture workflow fits two seed rows to age and sex controls. It does
not download public data and does not use private microdata.

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

If you are running from a source checkout without activating the environment,
add `uv run` before each `synthpopcan` command.

## Build the Documentation

```bash
uv run sphinx-build -W -b html docs docs/_build/html
```

The `-W` flag treats warnings as errors. This is intentional: it catches broken
links and malformed documentation before Read the Docs publishes the site.

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

Use `--data-root PATH` or `SYNTHPOPCAN_DATA_ROOT` when your data lives somewhere
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
build installs the package with the documentation dependency group and builds
from `docs/conf.py`.
