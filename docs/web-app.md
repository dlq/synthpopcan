# Local Web App

The `serve` command starts the **local SynthPopCan web app**. It is meant for
local inspection and guided workflows: configuring runs, reviewing controls,
checking outputs, and downloading generated artifacts. It is **not a public
deployment command**.

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

The first screen has **three guided paths**. All use only the local browser and
the loopback Python helper.

### IPF from margin tables

Choose this when we want to fit **seed rows** to **public margin/control totals**.
This path can start in two ways:

- use the demo files or blank templates when we are learning the format; or
- search for a Statistics Canada [WDS](https://www.statcan.gc.ca/en/developers/wds) product ID, inspect the table, refine it to a non-overlapping population
  slice, and let the local helper fill the seed CSV and normalized margin/control
  CSV.

The web app offers table `17100005`, **Population estimates on July 1, by age
and gender**, as a recommended starting point. Plain-word search results are
ranked for population-count usefulness and identify tables whose measure or
unit needs closer review. Downloaded ZIP and column overrides remain available
under the advanced options disclosure.

The WDS refinement step chooses a geography and offers detailed gender and
single-year or five-year age schemes when those dimensions are present. Its
live estimate reports the selected control cells, approximate expanded record
count, and source unit. Avoid modes marked as potentially overlapping. The web
app downloads the resulting `synthpopcan-wds-selection.json` so the same subset
can be passed to `controls from-wds --selection`.

After the two IPF input files are loaded, **Expanded synthetic records** is the
default for selections at or below the 100,000-row browser limit. Larger WDS
selections switch to **Compact fitted weights** automatically. Weighted output
is smaller and preserves fractional fitted weights; expanded output creates one
integerized row per synthetic record.

Completed WDS, IPF, and prepared-model runs end with a collapsed **Continue in
the CLI** section. The commands use the selected product or model, input
filenames, conditions, random seed, and output settings shown in the web app.

The same workflow is documented for command-line use in {doc}`statcan`,
{doc}`controls`, and {doc}`ipf`.

### Generate from existing model

Choose this when we have a **prepared model JSON** or a **linked household/person
package JSON**. The web app can also load premade packages served by the local
helper. The bundled safe demo package is synthetic toy data, not Census
microdata. When a published model such as `montreal-cma-2016-all-fields` is not
yet in the local cache, **Use premade model** downloads and verifies it before
loading it. The web app shows an indeterminate download indicator and the known
compressed package size while that first-use download is running.
Generation stays disabled until the selected package has loaded successfully or
an uploaded JSON file has been inspected. The ready state names the active model
and adapts the row label and available condition columns to that package.

For a linked household/person package, the browser generates household rows
first and then person rows inside each household. The result panel shows:

- generated household and person counts;
- whether each person row links to a known household;
- whether each household's `household_size` matches its generated persons;
- download links for `households.csv` and `persons.csv`;
- short previews of both CSV files.
- copyable `tree generate` or `tree generate-from-package` follow-up commands.

Model-generated previews preserve the package's raw source codes. For
PUMF-derived packages, values such as `99999999`, `9999`, `99`, and `9` are
usually Statistics Canada special codes such as not applicable, not available,
or valid skip, depending on the column. They should be decoded with field
metadata before being treated as numeric analysis values.

The first web app deliberately does **not train models**. Training, audit, and
release workflows remain advanced command-line/library work; see {doc}`tree`.

### Prepare a small-area synthesis

Choose this when we have a linked household/person model plus normalized
controls for census tracts, aggregate dissemination areas, or another target
geography. Select a premade model ID or a local package JSON, then upload the
household controls and optional person controls.

The form asks for the geography dimension and output column, candidate household
count, optional calibration pool size, average persons per household, and random
seed. **Estimate and prepare** sends only the controls text and numeric settings
to the local Python helper. It uses the same `estimate_small_area_run` logic as
the CLI and reports:

- target geographies and households;
- estimated person and total output rows;
- candidate and calibration pool sizes;
- whether the run belongs in the web app or the CLI/Python API;
- concrete planning guidance.

`0.4.0` does not run the full calibration in the browser. The result ends with
commented commands to fetch a selected published model, repeat `geo
estimate-run`, and execute `geo synthesize-from-package`. This keeps
province-scale output out of browser memory while preserving the exact choices
made in the form. When the controls use the Census Profile
`household_size_group` dimension, the generated command automatically adds
`--max-household-size 5` and the matching grouped-column option. See
{doc}`small-area` for control-building, validation, and mapping steps.

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

**We need command-line reproducibility:** use the command-line pages for the
workflow we are building. The web app is useful for guided inspection, while
the CLI is easier to record in scripts, notebooks, and methods sections.
