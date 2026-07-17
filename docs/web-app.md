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

## Runs Workbench

The first screen is a durable **Runs** workbench. **New run** starts an IPF job;
the left-hand history lists active and completed jobs stored in the local
workspace. Inputs, progress events, fit diagnostics, and artifacts survive a
page refresh and can be reopened by run ID.

Prepared-model generation and small-area planning remain available under
**Legacy browser tools** while they are migrated into the same durable runtime.

## Three Short Walkthroughs

These walkthroughs name the controls as they appear in the app. They are meant
to get us through one complete interaction before we study the detailed options
later on this page.

### Try IPF With the Teaching Files

1. Choose **New run**, then **Use demo age/sex files**.
1. Choose **Upload and continue**. The two tiny fictional CSVs stream to the
   local workspace instead of being parsed for synthesis in the browser.
1. Keep the default compact weighted output. Iteration, tolerance, starting
   weight, and non-convergence options are under **Advanced IPF settings**.
1. Choose **Check inputs** and review the seed count, control margins,
   dimensions, estimated output size, and workspace capacity.
1. Choose **Start run**. The isolated Python worker records progress even if the
   page is reloaded.
1. In **Results**, confirm convergence, inspect the bounded weighted preview,
   download `weights.csv` and `fit-report.json`, and keep the displayed CLI
   command with the research record.

This run tests the durable browser-to-Python workflow and teaches the
input/output shape. It does not represent a Canadian population. Continue to
[IPF](ipf.md) before replacing the teaching files with research inputs.

### Generate Linked Households and People

1. Open **Legacy browser tools**, then choose **Generate from existing model**.
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

1. Open **Legacy browser tools**, then choose **Prepare a small-area synthesis**.
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
The current workbench accepts a seed CSV and a normalized controls CSV, or fills
both with the bundled teaching example. Statistics Canada WDS discovery and
normalization remain available in the CLI while their durable web migration is
completed; see {doc}`statcan` and {doc}`controls`.

Uploads are streamed and hashed by the loopback service. **Preflight** uses the
same Python input diagnostics as the CLI, including missing dimensions,
unsupported categories, expected weighted rows, output-size estimate, and free
workspace capacity. **Start run** atomically claims the uploads, creates a run
manifest, and executes IPF in one isolated worker process. The event stream and
manifest are persisted, so refresh and reconnect do not restart the fit.

Compact fitted weights are the default and only Stage 3 run artifact. They
preserve fractional weights without creating a potentially enormous expanded
population in browser memory. The results page requests at most 10 preview rows
from a server endpoint capped at 25; full artifacts are available only through
download responses. Use `synthpopcan ipf expand` when an explicitly expanded
CSV is required.

Each completed run stores `weights.csv`, `fit-report.json`, checksums, fit
diagnostics, and a shell-safe reproduction command. The same workflow is
documented for command-line use in {doc}`ipf`.

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
