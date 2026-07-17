# Local Web App

The `serve` command starts the **local SynthPopCan web app**. It is meant for
local inspection and guided workflows: configuring runs, reviewing controls,
checking outputs, and downloading generated artifacts.

```{admonition} The web app is local, not a deployment server
:class: warning

The `serve` command is **not a public deployment command**. Keep the app bound
to the local loopback address unless we have separately provided appropriate
authentication, access controls, and production hosting.
```

## Getting Started

**Runnable after installation.** The local app includes fictional IPF files and
a bundled model package, so its first two teaching workflows work without a
network connection or source checkout.

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

## Three Short Walkthroughs

These walkthroughs name the controls as they appear in the app. They are meant
to get us through one complete interaction before we study the detailed options
later on this page.

### Try IPF With the Teaching Files

1. Keep **IPF from margin tables** selected.
1. Under **Use a demo or make templates**, choose **Use demo age/sex files**.
   The app fills both IPF file inputs with tiny fictional data.
1. Keep **Expanded synthetic records** selected and leave the iteration and
   tolerance defaults unchanged.
1. Choose **Run IPF**.
1. In the result, confirm that the fit converged, inspect the preview, and
   download the CSV. Open **Continue in the CLI** when we want a copyable record
   of the equivalent command-line steps.

This run checks the browser workflow and teaches the input/output shape. It does
not represent a Canadian population. Continue to [IPF](ipf.md) before replacing
the teaching files with research inputs.

### Generate Linked Households and People

1. Choose **Generate from existing model**.
1. Select **Safe demo household/person package**, then choose **Use premade
   model**.
1. Wait for the ready message. Keep `10` households and random seed `13`, and
   enter `geo=Demo North` under **Conditions**.
1. Choose **Generate rows**.
1. Confirm that the linkage check passes, compare the household and person
   counts, inspect both previews, and download both CSVs.

Before using a public research package, read its provenance, privacy-review
status, generation limits, and known limitations in the model summary. The
[Generate From a Model Package](tree-generate.md) chapter explains how to do the
same work reproducibly at larger scale.

### Prepare a Small-Area Run

1. Choose **Prepare a small-area synthesis**.
1. Select a premade linked model or upload a reviewed local package.
1. Upload normalized household controls and, when available, compatible person
   controls. Enter the geography dimension used by the controls, such as `ct`
   or `ada`.
1. Set the candidate household count and, for an exploratory run, a calibration
   pool size. Keep both random seeds recorded with the project.
1. Choose **Estimate and prepare**.
1. Read the target counts and surface recommendation, then copy the generated
   `models fetch`, `geo estimate`, and `geo synthesize` commands into a script or
   method note.

This path is a **preflight**, not a browser calibration. Building appropriate
controls and interpreting residuals are covered in
[Small-Area Linked Synthesis](small-area.md).

## Workflow Details

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

The local helper and browser enforce limits on request and download bytes, ZIP
entries, compressed and uncompressed sizes, selected CSV size and row count,
and concurrent WDS preparation. Only the selected data CSV is inflated in the
browser. If a table exceeds these workbench limits, download and process it
with the CLI instead of increasing browser memory pressure.

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
microdata. Registered packages up to the 32 MiB uncompressed browser threshold
can be downloaded and verified on first use. Larger packages are labelled
**CLI only** and the local API refuses to serialize them into browser memory;
use `synthpopcan models generate MODEL_ID ...` for those models.
Generation stays disabled until the selected package has loaded successfully or
an uploaded JSON file has been inspected. The ready state names the active model
and adapts the row label and available condition columns to that package.

For a linked household/person package, the browser generates household rows
first and then person rows inside each household. The result panel shows:

- generated household and person counts;
- whether each person row links to a known household;
- whether each household's `household_size` matches its generated persons;
- download links for `households.csv` and `persons.csv`;
- short previews of both CSV files;
- copyable `models build generate` or `models generate` follow-up commands.

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

The local app prepares the small-area workflow but does not run the full
calibration in the browser. The result ends with commented commands to fetch a
selected published model, repeat
`geo estimate`, and execute `geo synthesize`. This keeps
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
