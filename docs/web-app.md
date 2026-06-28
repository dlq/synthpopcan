# Local Web App

The `serve` command starts the local SynthPopCan web app. It is meant for local
inspection and guided workflows: configuring runs, reviewing controls, checking
outputs, and downloading generated artifacts. It is not a public deployment
command.

## Getting Started

From an installed environment:

```bash
synthpopcan serve
```

From a source checkout without an activated environment:

```bash
uv run synthpopcan serve
```

By default, the app listens on `127.0.0.1:8000` and opens in the default
browser.

## Choose a Workflow

The first screen has two beginner paths. Both run locally on your machine.

### IPF from margin tables

Choose this when you want to fit seed rows to public margin/control totals.
This path can start in two ways:

- use the demo files or blank templates when you are learning the format; or
- search for a Statistics Canada [WDS](https://www.statcan.gc.ca/en/developers/wds) product ID, inspect the table, and let the
  local helper fill the seed CSV and normalized margin/control CSV.

After the two IPF input files are loaded, keep **Weights CSV** as the first
output choice. Weighted output is smaller and easier to inspect. Use expanded
rows only for small browser runs or when a downstream tool really needs one row
per generated record.

The same workflow is documented for command-line use in {doc}`statcan`,
{doc}`controls`, and {doc}`ipf`.

### Generate from existing model

Choose this when you have a prepared model JSON or a linked household/person
package JSON. The web app can also load premade packages served by the local
helper. The bundled safe demo package is synthetic toy data, not Census
microdata; published models such as `montreal-cma-2016-all-fields` appear in
the same chooser after they are fetched into the local model cache.

For a linked household/person package, the browser generates household rows
first and then person rows inside each household. The result panel shows:

- generated household and person counts;
- whether each person row links to a known household;
- whether each household's `household_size` matches its generated persons;
- download links for `households.csv` and `persons.csv`;
- short previews of both CSV files.

Model-generated previews preserve the package's raw source codes. For
PUMF-derived packages, values such as `99999999`, `9999`, `99`, and `9` are
usually Statistics Canada special codes such as not applicable, not available,
or valid skip, depending on the column. They should be decoded with field
metadata before being treated as numeric analysis values.

The first web app deliberately does not train models. Training, audit, and
release workflows remain advanced command-line/library work; see {doc}`tree`.

## Options

```bash
synthpopcan serve \
  --host 127.0.0.1 \
  --port 8000 \
  --open
```

Important options:

- `--host`: host interface for the local web app. The default is `127.0.0.1`,
  which keeps the server on the local machine.
- `--port`: local port. Use another port if `8000` is already in use.
- `--open / --no-open`: open the browser automatically, or start the server
  without opening a browser.

## Troubleshooting

**The port is already in use:** choose another port:

```bash
synthpopcan serve --port 8001
```

**The browser does not open:** start with `--no-open` and visit the printed
local URL manually.

**The app cannot see expected local data:** run {doc}`data` first to check the
local data layout, then use `data inspect` and `data schema` to inspect specific files.

**You need command-line reproducibility:** use the command-line pages for the
workflow you are building. The web app is useful for guided inspection, while
the CLI is easier to record in scripts, notebooks, and methods sections.
