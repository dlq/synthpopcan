# Installation

SynthPopCan is a **command-line tool** and **Python library**. Using it requires
opening a **terminal** — a text window where we type commands rather than click
buttons. For readers who have not used a terminal before, these introductions
are written for humanities researchers and require no prior programming
experience:

- **Mac:** [Introduction to the Bash Command Line](https://programminghistorian.org/en/lessons/intro-to-bash)
  — Programming Historian
- **Windows:** [Introduction to the Windows Command Line with PowerShell](https://programminghistorian.org/en/lessons/intro-to-powershell)
  — Programming Historian

Read one of those first, then return here.

SynthPopCan can be installed from [PyPI](https://pypi.org/), run as a one-off
command with `uvx`, or installed from a source checkout for development. If we
only want to **use the command line or beginner Python API**, start with the
PyPI installation. If we want to **edit the code, documentation, or tests**, use
the source checkout.

## Requirements

- Python 3.11 or newer. Download from [python.org/downloads](https://www.python.org/downloads/).
  For readers who have not used Python before, the Programming Historian's
  [Introduction to Python](https://programminghistorian.org/en/lessons/introduction-and-installation)
  is a good starting point.
- Git, only when cloning from the repository.
- `pip`, which is included with most Python installations.
- Optional: [`uv`](https://docs.astral.sh/uv/), when using `uvx` for one-off commands or when working on the
  source checkout.
- Local source data staged outside git when working with real census or private files.

We do not need a database, a cloud account, or a web server for the
command-line workflows.

## Install From PyPI

For most readers, the best first path is the **published package from PyPI**:

```bash
python -m pip install synthpopcan
```

Then check that the command is available:

```bash
synthpopcan --help
```

This is the best path when we want to run **command-line examples**, use the
**beginner API in a notebook**, or build small teaching workflows without
editing SynthPopCan itself.

For notebook work, install SynthPopCan into the same Python environment that
[Jupyter](https://jupyter.org/) uses. A minimal notebook smoke test is:

```python
import synthpopcan as spc

spc.__version__
```

## Run One-Off Commands With `uvx`

If we have `uv` installed but do not want to install SynthPopCan into the
current environment, `uvx` can download the package and run the `synthpopcan`
command in an isolated temporary environment:

```bash
uvx synthpopcan --help
uvx synthpopcan guide ipf
```

This is useful for trying the CLI or running a short command. For repeated work
in a project folder or notebook, a normal `pip` installation is usually easier
to reason about.

## Install From a Source Checkout

A source checkout is a local copy of the SynthPopCan repository cloned from
GitHub. Use one when we want to **edit SynthPopCan**, **run the tests**, **build
the documentation locally**, or work against unreleased changes.

Clone the repository, then enter the checkout:

```bash
git clone https://github.com/dlq/synthpopcan.git
cd synthpopcan
```

The repository currently uses `uv` for repeatable local development. If we do
not have `uv`, install it from the [official installation guide](https://docs.astral.sh/uv/getting-started/installation/).

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

If SynthPopCan was installed with `pip`, run:

```bash
synthpopcan --help
```

When working directly from a source checkout with `uv`, prefix commands with
`uv run` so they use the checkout's isolated Python environment — a separate
installation that keeps SynthPopCan's dependencies from interfering with other
Python projects on the same machine:

```bash
uv run synthpopcan --help
```

The rest of the documentation usually shows `synthpopcan ...` to focus on the
tool itself. If we are using `uvx`, replace `synthpopcan ...` with
`uvx synthpopcan ...`. If we are working from a checkout, use
`uv run synthpopcan ...`.

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
links and malformed documentation before [Read the Docs](https://readthedocs.org/) publishes the site.

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

## Find SynthPopCan Online

- **Documentation:** <https://synthpopcan.readthedocs.io/>
- **Source code and issues:** <https://github.com/dlq/synthpopcan>
- **Package:** <https://pypi.org/project/synthpopcan/>
