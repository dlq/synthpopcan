# Installation

SynthPopCan is currently a source-installable Python project. It is intended for
research and digital-humanities workflows where users may work from a local
checkout while the API and command set are still settling.

## Requirements

- Python 3.11 or newer.
- `uv` for the documented development and documentation commands.
- Local source data staged outside git when working with real census or private
  files.

You do not need to install a database, run a server, or configure a cloud
account for the command-line workflows in this documentation.

## Install from a Checkout

From the repository root, install the package and normal runtime dependencies:

```bash
uv sync
```

Then run the CLI through `uv`:

```bash
uv run synthpopcan --help
```

That command should print the main command groups. The most common early ones
are `microdata`, `controls`, `ipf`, and `validate`.

For documentation work, include the documentation dependency group:

```bash
uv sync --group docs
```

Build the documentation locally with:

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

## If You Are New to Command-Line Tools

Run commands from the repository root unless a page says otherwise. In examples,
lines ending with `\` continue onto the next line. You can paste the whole block
into a terminal, or put it on one line by removing the backslashes.

Most examples write small files such as `seed.csv`, `weights.csv`, and
`fit-report.json` in the current directory. For a real project, create a
separate working folder so outputs from different runs do not get mixed
together.

## Read the Docs

The project includes a `.readthedocs.yaml` file for Read the Docs. The published
build installs the package with the documentation dependency group and builds
from `docs/conf.py`.
