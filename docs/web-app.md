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

Prepared-model generation is another **New run** path. **Small-area workflow**
opens the linked generation/calibration setup; its resulting job appears in the
same durable Runs history.

The current workbench does not expose the unreleased national DA/ADA
orchestration, prepared-geodata retrieval, or external-data enrichment
interfaces. Use the command line or Python library for those development
workflows.

### Workspace and run lifecycle

The default workspace is `synthpopcan-runs/` under the directory where the
server starts. Use `--workspace PATH` to place it elsewhere. Each run receives a
separate directory containing claimed input copies, an append-only progress
event stream, a versioned manifest, temporary work files, and published
artifacts. The app displays the active workspace path before a run begins.

Queued and running jobs can be cancelled. A page refresh reconnects to the
stored event stream and manifest; after a server restart, unfinished runs are
recorded as interrupted rather than silently restarted. Succeeded, failed,
cancelled, and interrupted records remain inspectable until the user removes
the workspace. Published artifacts are written atomically and previews are
bounded; complete CSVs are downloaded directly rather than embedded in JSON.

The app records package provenance and privacy-review metadata where available,
but a successful run is not a privacy certification or a fitness-for-purpose
finding. Every terminal run records a versioned assurance object with its
normalized request, settings, model identity where applicable, input and
artifact hashes and row counts, diagnostics, lifecycle state, warnings, and
limitations. `RunStore.verify_assurance(run_id)` independently re-hashes and
recounts files and reruns linked household/person integrity checks.

Every completed synthesis also records a structured, shell-safe CLI
reproduction recipe. A recipe retains the legacy primary `command` and `shell`
fields and adds ordered `commands` and `shell_commands` arrays when multiple
steps are required. Managed paths such as `inputs/controls.csv` are relative to
the run directory; run the recorded commands from that directory and they write
new `reproduced...` output without replacing published artifacts. IPF,
prepared-model, generated small-area, uploaded-candidate, and mapped small-area
recipes are executed in tests.

The web app, CLI, and Python API use the same Python domain algorithms. IPF
also shares file-backed workflow orchestration; prepared-model and small-area
adapters still translate some options separately. Choose among the surfaces
for guidance, automation, or notebook integration, and use the recorded
version, inputs, seeds, and validation evidence when comparing results.

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
   dimensions, compact output rows, fitted population total, estimated output
   size, and workspace capacity.
1. Choose **Start run**. The isolated Python worker records progress even if the
   page is reloaded.
1. In **Results**, confirm convergence, inspect the bounded weighted preview,
   download `weights.csv` and `fit-report.json`, and keep the displayed CLI
   command with the research record.

This run tests the durable browser-to-Python workflow and teaches the
input/output shape. It does not represent a Canadian population. Continue to
[IPF](ipf.md) before replacing the teaching files with research inputs.

### Generate Linked Households and People

1. Choose **New run**, then **Generate from a prepared model**.
1. Select **Safe demo household/person package**.
1. Keep `10` households and random seed `13`, and
   enter `geo=Demo North` under **Conditions**.
1. Choose **Check model and scale**, review the package provenance, privacy
   status, requested household count, conservative storage allowance, and
   available disk space, then choose **Start run**.
1. Confirm that the linkage check passes, compare the household and person
   counts, inspect both previews, and download both CSVs.

Before using a public research package, read its provenance, privacy-review
status, generation limits, and known limitations in the model summary. The
[Generate From a Model Package](tree-generate.md) chapter explains how to do the
same work reproducibly at larger scale.

### Prepare a Small-Area Run

1. Open **Small-area workflow**, then choose **Prepare a small-area synthesis**.
1. Select a premade 2016 or 2021 linked model, upload a reviewed local package,
   or upload both existing linked candidate CSVs.
1. Upload normalized household controls and, when available, compatible person
   controls. Enter the geography dimension used by the controls, such as `ct`
   or `ada`.
1. Set the candidate household count and, for an exploratory run, a calibration
   pool size. Keep both random seeds recorded with the project.
1. Choose **Estimate and prepare**, review target counts and workspace capacity,
   then start the durable small-area run.
1. Review convergence and residual diagnostics, inspect bounded household and
   person previews, download the linked CSVs and report, and retain the
   recorded `geo synthesize` or `geo calibrate` reproduction recipe.
   Optionally upload prepared boundary GeoJSON to receive a standalone map
   artifact and a following `geo map` reproduction step.

Generation and calibration execute in Python; complete populations are not
serialized into the browser. Building appropriate controls and interpreting
residuals are covered in [Small-Area Linked Synthesis](small-area.md).

## Workflow Details

### IPF from margin tables

Choose this when we want to fit **seed rows** to **public margin/control totals**.
The current workbench accepts a seed CSV and a normalized controls CSV, or fills
both with the bundled teaching example. Statistics Canada WDS discovery and
normalization remain available in the CLI while their durable web migration is
completed; see {doc}`statcan` and {doc}`controls`.

Uploads are streamed and hashed by the loopback service. **Preflight** uses the
same Python input diagnostics as the CLI, including missing dimensions,
unsupported categories, compact output rows, fitted population total,
output-size estimate, and free workspace capacity. **Start run** atomically claims the uploads, creates a run
manifest, and executes IPF in one isolated worker process. The event stream and
manifest are persisted, so refresh and reconnect do not restart the fit.

Uploads, preflights, model catalogue changes, estimates, run creation, and
result previews are sequenced against the draft or durable run that started
them. Editing a form invalidates an older pending response instead of allowing
it to overwrite the newer state. Once a run is created, previews and the CLI
reproduction command come from its persisted manifest rather than mutable form
fields.

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

Choose this when we have a **prepared linked household/person package JSON**.
The web app can also use reviewed packages served by the local helper. The
bundled safe demo package is synthetic toy data, not Census microdata. Package
inspection, generation, and validation run in Python; uploaded JSON and output
CSVs remain in the controlled workspace rather than being materialized in
browser memory. Generation stays disabled until preflight has checked package
structure, publishability, provenance, privacy metadata, requested conditions,
estimated scale, and available disk space.

The local web workbench accepts at most 250,000 requested households and its
isolated worker stops before writing more than 2,000,000 people. A worker that
runs for six hours is terminated and retained as a failed durable run rather
than remaining indefinitely active. These are local-app safety limits, not
claims about the library's computational ceiling. Use the CLI for a deliberately
reviewed larger run with appropriate storage, monitoring, and validation.

For a linked household/person package, the durable worker writes household rows
first and then person rows inside each household. The result panel shows:

- generated household and person counts;
- whether each person row links to a known household;
- whether each household's `household_size` matches its generated persons;
- download links for `households.csv` and `persons.csv`;
- short previews of both CSV files;
- a copyable `models generate` reproduction command.

Model-generated previews preserve the package's raw source codes. For
PUMF-derived packages, values such as `99999999`, `9999`, `99`, and `9` are
usually Statistics Canada special codes such as not applicable, not available,
or valid skip, depending on the column. They should be decoded with field
metadata before being treated as numeric analysis values.

The first web app deliberately does **not train models**. Training, audit, and
release workflows remain advanced command-line/library work; see {doc}`tree`.

### Prepare a small-area synthesis

Choose this when we have a linked household/person model or an existing linked
candidate population plus normalized controls for census tracts, aggregate
dissemination areas, or another target geography. Select a premade model ID,
upload a local package JSON, or upload both `households.csv` and `persons.csv`,
then upload the household controls and optional person controls.

The form asks for the geography dimension and output column, candidate household
count, optional calibration pool size, average persons per household, and random
seed. Question-mark help labels can be hovered, tapped, or reached with the
keyboard for a short field explanation. **Estimate and prepare** sends only the controls text and numeric settings
to the local Python helper. It uses the same `estimate_small_area_run` logic as
the CLI and reports:

- target geographies and households;
- estimated person and total output rows;
- candidate and calibration pool sizes;
- whether the run belongs in the web app or the CLI/Python API;
- concrete planning guidance.

The local app runs generation and calibration in an isolated Python worker and
publishes bounded previews plus downloadable artifacts. The result retains
`geo synthesize` reproduction metadata for model-based runs or `geo calibrate`
metadata for existing candidates. This keeps province-scale output out of
browser memory while preserving model conditions, seeds, candidate settings,
person controls, fitted-weight output, geography fields, and optional map
creation. When the controls use the Census Profile `household_size_group`
dimension, the generated command automatically adds `--max-household-size 5`
and the matching grouped-column option. See {doc}`small-area` for
control-building, validation, and mapping steps.

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
- `--workspace`: durable run directory. The default is `synthpopcan-runs/` in
  the current directory.

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
