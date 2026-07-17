# Local Web Application Runtime Implementation Plan

Status: planned\
Created: 2026-07-10\
Last updated: 2026-07-15\
Target: `0.6.0`–`0.6.2`\
Next action: execute Stage 0, HTTP runtime and module-boundary skeleton\
Roadmap: [PLANS.md](../PLANS.md) | [Plan index](README.md)

> **For agentic workers:** Execute this plan one stage at a time. Keep each
> patch reviewable, preserve existing CLI behavior while a workflow is being
> migrated, and do not remove browser-side computation until parity tests and
> replacement browser scenarios pass.

**Goal:** Turn `synthpopcan serve` into a local research workbench that uses the
same Python workflows as the CLI and beginner API, supports durable and
potentially large synthesis runs, and keeps enough provenance and validation
evidence to reproduce each run outside the browser.

**Architecture:** Keep synthesis algorithms in the existing domain modules.
Add a UI-independent application-workflow layer for file-backed orchestration,
reports, provenance, and artifacts. Both Click commands and a loopback HTTP API
call that layer. The HTTP adapter owns request validation and local job control;
the packaged HTML/CSS/ES-module frontend owns interaction, progress display,
previews, and artifact navigation. Long-running work executes in a separate
local process and writes directly into a durable run directory.

**Tech stack:** Python dataclasses for domain and workflow types; FastAPI and
Uvicorn at the HTTP adapter boundary; one spawned Python worker process at a
time; versioned JSON manifests and newline-delimited JSON progress events;
packaged vanilla HTML, CSS, and ES modules; pytest and Playwright.

______________________________________________________________________

## Product And Architecture Decisions

These decisions are settled for the 0.6.x implementation:

1. The web app is local software started by `synthpopcan serve`. It is not a
   static-site deployment target and is not intended to be hosted publicly.
1. Python owns synthesis, validation, provenance, and artifact writing. The
   browser does not maintain parallel IPF or tree-generation algorithms.
1. The web API does not shell out to Click commands and does not parse terminal
   output. CLI and HTTP adapters call shared Python workflow functions.
1. The frontend remains packaged HTML, CSS, and ES modules. Moving computation
   to Python is not, by itself, a reason to add React or another UI framework.
1. A run is a durable research object, not an ephemeral browser promise. Its
   manifest, inputs or input references, parameters, random seed, status,
   diagnostics, artifacts, and reproducible command survive browser refreshes.
1. `0.6.0` keeps the run manifest extensible for linked artifacts without
   declaring their complete column contract stable. `0.6.1`, alongside backend
   prepared-model generation, defines and ships the versioned stable public
   linked household/person/geography schema.
1. The first job manager runs one synthesis process at a time. This keeps local
   CPU and memory use predictable and avoids introducing a database, Redis,
   Celery, or a general distributed queue.
1. Browser memory must not scale with output population size. Large artifacts
   are written in chunks and downloaded or inspected by reference.
1. `geo map` remains a standalone exported HTML artifact using MapLibre GL JS
   and OpenFreeMap. The local app may create or open that artifact, but the map
   exporter is not absorbed into the application frontend.
1. Pyodide, a reusable browser synthesis package, and npm distribution are out
   of scope unless a future static-hosting requirement returns.

## Non-Goals

- Public or multi-user hosting.
- Authentication, accounts, shared projects, or remote job workers.
- Concurrent province-scale runs.
- Reimplementing advanced model training, privacy auditing, or release
  packaging in the first web-app release.
- Replacing the beginner Python API with HTTP calls.
- Replacing domain dataclasses with Pydantic models. Pydantic is limited to the
  HTTP request and response boundary.
- Turning every CLI command into a web form. Add workflows according to user
  value and composability, not command count.

## Product Flow

The first screen is the actual workbench, not a landing page. It has one primary
action, **New run**, followed by a compact list of recent runs and their state.
Primary navigation is limited to **Runs**, **Models**, and **Data**.

Starting a run presents a plain-language workflow list:

- Fit seed rows to controls.
- Generate households and people from a prepared model.
- Assign linked households and people to small areas.
- Inspect or validate existing artifacts.

Every synthesis workflow uses the same sequence:

1. **Inputs:** choose files or a prepared model, inspect columns and metadata,
   and resolve blocking input problems.
1. **Configure:** show approachable defaults first and place specialist options
   in an advanced disclosure section.
1. **Preflight:** summarize expected rows, disk use, retained weights, runtime
   class, validation steps, random seed, and output directory.
1. **Run:** show the current stage, elapsed time, concise messages, and a cancel
   action without streaming terminal output into the page.
1. **Results:** show validation first, then sampled previews and named artifacts.
   Include the exact CLI reproduction command and actions to run again or open
   the run directory.

The UI must not display every capability on every screen. Training, privacy
review, and release tooling remain discoverable through documentation and the
CLI rather than occupying the beginner workbench.

## Runtime Contract

### Workspace

Add `synthpopcan serve --workspace PATH`. The default is
`./synthpopcan-runs`, resolved from the directory where the command is started.
The server prints the resolved workspace and the UI shows it in the Runs view.

The server creates only these managed paths:

```text
synthpopcan-runs/
  uploads/
  runs/
    20260710T142355Z-6f2a81c4/
      run.json
      events.ndjson
      inputs/
      artifacts/
      work/
```

- `uploads/` holds streamed browser uploads until they are claimed by a run.
- `inputs/` holds claimed uploads or small generated inputs such as demo files.
- `artifacts/` contains only completed, user-visible outputs.
- `work/` contains partial files and intermediate state. It is never exposed by
  the artifact endpoint and can be removed after terminal completion.
- Manifest and event writes use temporary files plus atomic replacement where
  applicable. Completed artifact files are renamed from `work/` only after the
  writer closes successfully.

Do not accept arbitrary filesystem paths from HTTP JSON. An HTTP request may
refer only to an opaque upload ID, a model-catalogue ID, or an artifact ID
already present in a run manifest. Future server-side file selection must be
restricted to an explicitly configured root.

### Run Manifest

Use schema version `synthpopcan-run-v1`. `run.json` contains at least:

```text
schema_version
run_id
workflow
status
created_at
started_at
finished_at
synthpopcan_version
request
random_seed
inputs
artifacts
summary
error
reproduction
```

Input and artifact entries include a stable logical name, relative managed
path, media type, byte size, and SHA-256 digest. Record row counts when they can
be collected while reading or writing without another complete pass.

The v1 run manifest must be able to reference a future linked-population schema
and its data dictionary, but `0.6.0` does not freeze the complete linked CSV
column set. The `0.6.1` contract will define required household/person
identifiers and linkage, model-specific extension fields, geography metadata,
types, missing-value conventions, code lists, and compatibility rules.

`reproduction` contains both the canonical structured workflow request and a
shell-safe CLI command rendered with `shlex.join`. Tests must execute the
rendered command against fixtures so command drift is detected.

### Run States

Use these states:

```text
queued -> running -> succeeded
                  -> failed
                  -> cancelling -> cancelled
                  -> interrupted
```

- `succeeded`, `failed`, `cancelled`, and `interrupted` are terminal.
- On server startup, manifests left in `queued`, `running`, or `cancelling`
  become `interrupted`; they are never reported as successful and are not
  silently resumed. The user may create a new run from the preserved request.
- Cancelling first sets a shared cancellation flag. If the worker does not stop
  after a short grace period, terminate the worker process and mark the run
  `cancelled` after its process exits.

### Progress Events

Workers append compact events to `events.ndjson`:

```text
event_id
timestamp
level
stage
message
completed
total
```

Stages are workflow concepts such as `checking-inputs`, `fitting`,
`generating-households`, `generating-persons`, `calibrating`, `validating`, and
`writing-artifacts`. They are not copied terminal lines. `completed` and
`total` are optional because some algorithms cannot provide meaningful
fine-grained progress.

### HTTP Surface

Keep the API private to the packaged frontend, but make its contract explicit:

```text
GET  /api/app
GET  /api/models
GET  /api/models/{model_id}
POST /api/uploads
POST /api/preflight
GET  /api/runs
POST /api/runs
GET  /api/runs/{run_id}
GET  /api/runs/{run_id}/events
POST /api/runs/{run_id}/cancel
GET  /api/runs/{run_id}/artifacts/{artifact_id}
```

- `POST /api/uploads` streams the request body to disk and returns an opaque
  upload ID. It must not read the complete file into memory.
- `POST /api/preflight` accepts the same discriminated workflow request as run
  creation and returns normalized options, blocking input diagnostics, scale
  estimates, expected artifacts, and disk headroom. It does not create a run.
- `POST /api/runs` accepts a discriminated request model with `workflow`, input
  references, and typed options. It repeats the blocking preflight checks so a
  stale browser result cannot bypass validation.
- `GET /events` uses server-sent events and supports reconnecting from the last
  received event ID.
- Artifact responses use manifest-owned paths and `Content-Disposition`; a URL
  path can never be translated directly into a filesystem path.
- Existing model and WDS helpers remain available during migration, but move
  behind the FastAPI application before the standard-library handler is
  removed.

### Local Security

- Bind to loopback only. Non-loopback hosts are rejected in 0.6.x rather than
  described as a supported deployment mode.
- Generate a new session secret when the server starts. Set it in a
  `SameSite=Strict`, `HttpOnly` cookie from the app bootstrap response and
  require it for API access.
- Reject unexpected `Origin` values and do not enable permissive CORS.
- Sanitize uploaded filenames for display, but choose all stored filenames on
  the server.
- Check available disk space before accepting a declared upload or launching a
  run. Fail preflight rather than allowing a predictable partial artifact.
- Add explicit path-traversal, symlink-escape, stale-upload, and cross-origin
  tests.

## Module Boundaries

Use this dependency direction:

```text
domain modules
    -> application workflows
        -> run store and job runner
            -> CLI and HTTP adapters
                -> browser UI
```

The arrows mean "is used by". Dependencies must never point back toward an
adapter.

Create the application layer as a small package:

- `src/synthpopcan/workflows/types.py`
  - Workflow request dataclasses, progress protocol, artifact metadata, and
    workflow result types.
- `src/synthpopcan/workflows/ipf.py`
  - File-backed input checking, fitting, streamed expansion, fit report, and
    control validation orchestration.
- `src/synthpopcan/workflows/models.py`
  - Prepared-model inspection, linked generation, artifact metadata, and linked
    validation orchestration.
- `src/synthpopcan/workflows/small_area.py`
  - Scale estimate, linked calibration, validation, and optional map artifact
    orchestration.
- `src/synthpopcan/runs.py`
  - Workspace layout, run IDs, versioned manifests, atomic state transitions,
    upload claiming, and safe artifact resolution.
- `src/synthpopcan/jobs.py`
  - One-process queue, cancellation, interruption recovery, and progress event
    persistence.
- `src/synthpopcan/webapi.py`
  - FastAPI request/response models, routes, session checks, and static asset
    mounting.
- `src/synthpopcan/webapp.py`
  - Uvicorn startup, browser opening, URL construction, and graceful shutdown.

Rules enforced in `tests/test_architecture.py`:

- Existing domain modules cannot import `workflows`, `runs`, `jobs`, CLI, HTTP,
  or browser modules.
- `workflows` cannot import Click, Rich, FastAPI, `webapp`, `webapi`, or CLI
  modules.
- `runs` and `jobs` cannot import Click, Rich, `webapp`, or CLI modules.
- `api.py` cannot import CLI or web adapters.
- CLI and HTTP adapters may import application and domain modules.
- The browser is never a source of truth for workflow defaults or algorithm
  behavior that already exists in Python.

## Staged Implementation

### Stage 0: HTTP Runtime And Boundary Skeleton

**Files:**

- Modify: `pyproject.toml`, `uv.lock`, `.gitignore`

- Create: `src/synthpopcan/webapi.py`

- Modify: `src/synthpopcan/webapp.py`

- Modify: `src/synthpopcan/cli.py`

- Modify: `tests/test_architecture.py`, `tests/test_webapp.py`

- [x] Add FastAPI and Uvicorn runtime dependencies and an HTTP client test
  dependency in the development group.

- [x] Add `create_web_app(...)` with `/api/app`, existing model endpoints, the
  WDS seed/control helper, and packaged static assets.

- [x] Preserve `synthpopcan serve --port` and `--open / --no-open`; add
  `--workspace`; reject non-loopback `--host` values with a helpful message.

- [x] Ignore the default `synthpopcan-runs/` workspace so starting the app from
  a source checkout cannot accidentally stage generated inputs or populations.

- [x] Add session-cookie, origin, cache-control, and graceful-shutdown tests.

- [x] Extend architecture checks before adding application modules.

- [x] Run the existing browser scenarios against the new server without changing
  their computation path yet.

**Acceptance:** The server implementation changes, but current IPF and prepared
model browser scenarios remain behaviorally unchanged. Existing model and WDS
API tests pass through FastAPI.

### Stage 1: Shared IPF Workflow

**Files:**

- Create: `src/synthpopcan/workflows/__init__.py`

- Create: `src/synthpopcan/workflows/types.py`

- Create: `src/synthpopcan/workflows/ipf.py`

- Modify: `src/synthpopcan/cli_ipf.py`, `src/synthpopcan/api.py`

- Create: `tests/test_workflow_ipf.py`

- Modify: `tests/test_ipf.py`, `tests/test_workflows.py`

- [x] Extract file-backed input checking, fitting, report writing, compact weight
  output, streamed expansion, and validation from Click command bodies.

- [x] Keep Click responsible only for parsing options, translating exceptions,
  and presenting success or error output.

- [x] Add a progress callback protocol with no dependency on the job runner.

- [x] Build the canonical structured reproduction request and CLI renderer.

- [x] Prove that the migrated CLI fixture outputs and reports are byte-for-byte
  equivalent where timestamps are not present.

- [x] Keep the beginner in-memory API behavior unchanged while reusing shared
  lower-level functions where that removes duplication.

**Acceptance:** `SCN-IPF-001` and `SCN-WDS-001` still pass, and the IPF workflow
can be invoked without importing Click, Rich, FastAPI, or browser modules.

### Stage 2: Durable Runs And IPF Job Vertical Slice

**Files:**

- Create: `src/synthpopcan/runs.py`

- Create: `src/synthpopcan/jobs.py`

- Modify: `src/synthpopcan/webapi.py`

- Create: `tests/test_runs.py`, `tests/test_jobs.py`, `tests/test_webapi.py`

- [x] Implement workspace creation, opaque run/upload IDs, versioned manifests,
  safe relative paths, hashes collected while copying or writing, and atomic
  state updates.

- [x] Implement streamed uploads and upload claiming without loading complete
  files into Python memory.

- [x] Implement authenticated preflight for IPF and repeat its blocking checks
  when the run is created.

- [x] Implement one queued spawned worker, event persistence, SSE replay,
  cancellation, partial-artifact isolation, and startup interruption recovery.

- [x] Add the generic run lifecycle routes and support `workflow: "ipf"` first.

- [x] Add a deterministic API integration test that uploads fixtures, starts an
  IPF run, observes progress, downloads the result and report, and executes the
  reproduction command.

- [x] Test failure before fitting, failure during work, cancellation, restart,
  path traversal, unknown IDs, and insufficient disk preflight.

**Acceptance:** A complete IPF run can be created and recovered by run ID with
no browser involvement. The API never returns the complete output CSV as JSON.

### Stage 3: Runs Workbench And IPF UI Migration

**Files:**

- Modify: `src/synthpopcan/web/index.html`, `styles.css`, `app.mjs`

- Create: focused ES modules for API access, run state, run list, workflow steps,
  and progress events

- Modify: `tests/web/scenarios.spec.mjs`, `tests/SCENARIOS.md`, `docs/web-app.md`

- [ ] Replace the workflow-card first screen with the Runs workbench and a
  single New run action while preserving existing visual tokens and branding.

- [ ] Implement Inputs, Configure, Preflight, Run, and Results views for IPF.

- [ ] Stream selected files to `/api/uploads`; do not call `File.text()` for
  synthesis inputs.

- [ ] Show input diagnostics before enabling Run, keep expert IPF settings under
  Advanced, and display weighted output as the default.

- [ ] Reconnect to active runs after refresh and list completed runs from the
  workspace.

- [ ] Show fit diagnostics, a bounded preview, artifacts, and the reproducible
  CLI command on the Results view.

- [ ] Update `SCN-WEB-001` from browser-local computation to the durable backend
  run lifecycle.

- [ ] Delete browser IPF computation only after the replacement scenario and
  Python/JavaScript parity fixtures pass.

**Acceptance:** A first-time user can complete the demo IPF run without knowing
a command name, refresh during or after the run, and retrieve the same result
from the Runs list.

### Stage 4: Prepared-Model Workflow Migration

**Files:**

- Create: `src/synthpopcan/workflows/models.py`

- Modify: `src/synthpopcan/cli_tree.py`, `src/synthpopcan/api.py`

- Modify: `src/synthpopcan/webapi.py` and web workflow modules

- Create: `tests/test_workflow_models.py`

- Modify: `tests/test_tree.py`, `tests/test_workflows.py`, browser scenarios

- [ ] Extract prepared-package inspection, publishability checks, linked
  generation, output writing, manifest data, and linked validation from the CLI
  adapter.

- [ ] Add typed prepared-model run requests using a catalogue model ID or claimed
  package upload plus household count, conditions, and random seed.

- [ ] Make package provenance and privacy metadata part of preflight, not a
  separate optional inspection action.

- [ ] Write household and person CSVs directly to the run artifact workspace and
  return only summaries and bounded previews through HTTP.

- [ ] Update `SCN-WEB-002` to exercise the backend job and durable run result.

- [ ] Remove browser tree/model generation after fixed-seed parity tests and the
  replacement scenario pass.

**Acceptance:** CLI, beginner API, and web runs use the same Python model
generation behavior. No production browser module contains tree traversal,
frequency sampling, or linked-population generation logic.

### Stage 5: Chunked Generation And Scale Guardrails

**Files:**

- Modify: `src/synthpopcan/tree.py`, `src/synthpopcan/api.py`

- Modify: `src/synthpopcan/workflows/models.py`, `jobs.py`

- Modify: `src/synthpopcan/benchmarks.py`, `scripts/benchmarks.py`

- Modify: model, workflow, benchmark, and browser tests

- [ ] Add an iterator or chunk callback for linked generation while retaining the
  current collecting API for compatibility.

- [ ] Preserve deterministic fixed-seed output regardless of configured write
  chunk size.

- [ ] Keep household/person identifiers and link validation correct across chunk
  boundaries.

- [ ] Write CSV rows, hashes, byte counts, and row counts incrementally.

- [ ] Add cancellation checks between chunks and before artifact finalization.

- [ ] Add preflight estimates and explicit disk headroom for prepared-model runs.

- [ ] Add a deterministic medium-scale CI profile and an opt-in province-scale
  local profile. The large profile must use the same job and artifact path as
  the web app, not a separate benchmark-only implementation.

**Acceptance:** The browser receives bounded status and preview payloads while a
large file-backed generation run proceeds. Increasing output rows does not
increase browser-side CSV memory, and backend peak memory is governed by the
model plus configured chunk size rather than complete generated output.

### Stage 6: Guided Small-Area Workflow

**Files:**

- Create: `src/synthpopcan/workflows/small_area.py`

- Modify: `src/synthpopcan/cli_geo.py`, `src/synthpopcan/api.py`

- Modify: web API and workflow UI modules

- Create: `tests/test_workflow_small_area.py`

- Modify: small-area, workflow, scenario, and browser tests

- [ ] Extract scale estimation, linked calibration, report writing, linked
  validation, and optional map creation into one file-backed workflow.

- [ ] Allow the run to start from existing linked candidate uploads or chain
  prepared-model generation inside the same run request.

- [ ] Present household controls, optional person controls, geography settings,
  candidate pool, and output scale as one guided flow.

- [ ] Block launch on incompatible geography dimensions, missing linked IDs,
  unrepresentable controls, or insufficient disk.

- [ ] Show household and person residual summaries before artifact links.

- [ ] Produce the standalone map through `map_render.py` and expose it as a named
  artifact without changing the exported MapLibre/OpenFreeMap architecture.

- [ ] Update `SCN-SMALLAREA-001` with an HTTP/browser-owned acceptance path while
  retaining the CLI integration scenario.

**Acceptance:** A user can generate or provide linked candidates, calibrate
them to small areas, validate the linked outputs, and open the map from one
durable run without manually carrying intermediate filenames between commands.

### Stage 7: Small And Medium Utility Workflows

Add web surfaces only where a guided interface clearly reduces setup or
interpretation work:

- data inspect, schema, and bounded sample;
- controls validation and input compatibility checks;
- model catalogue, fetch, inspect, and removal;
- linked-output, control, and tree-output validation;
- existing run and artifact inspection.

Each utility should call an existing domain or application function and return
structured data. Do not expose commands by executing the CLI, and do not add a
generic terminal panel.

**Acceptance:** Utilities compose into synthesis preflight and results views
instead of becoming a second menu that mirrors every CLI command.

### Stage 8: Cleanup, Documentation, And Release Proof

**Files:**

- Remove obsolete browser computation modules and tests

- Modify: `README.md`, `PLANS.md`, `CHANGELOG.md`, `docs/web-app.md`,
  `docs/getting-started.md`, `tests/SCENARIOS.md`, `docs/glossary.md`

- Modify: packaging, CI, architecture, API, workflow, and browser tests

- [ ] Remove the standard-library request handler and all fallback messages for
  static-only or browser-only operation.

- [ ] Remove browser IPF, tree generation, ZIP processing, and worker modules
  that no longer own UI behavior. Keep focused preview/parsing helpers only when
  they still remove real duplication.

- [ ] Document workspace location, run lifecycle, privacy, cancellation,
  recovery, scale expectations, and CLI reproduction.

- [ ] Update performance guidance so the web app and CLI are alternate adapters
  over the same runtime rather than different computational tiers.

- [ ] Build a wheel and sdist, install the wheel in a clean environment, launch
  `synthpopcan serve`, complete demo IPF and prepared-model runs, and verify
  packaged static assets and runtime dependencies.

- [ ] Run the full Python suite, architecture checks, Biome, Playwright desktop
  and mobile scenarios, Sphinx with warnings as errors, and opt-in scale smoke
  tests.

**Acceptance:** Documentation and tests describe one Python implementation with
three user surfaces: CLI, beginner API, and local web app. No public claim
depends on static hosting or browser-side synthesis.

## Test Matrix

| Concern | Unit | Integration | Browser | Opt-in scale |
| --- | --- | --- | --- | --- |
| Module boundaries | AST import tests | - | - | - |
| Run manifests and paths | State/path tests | Restart and artifact tests | Recent-runs view | - |
| Uploads | Chunked writer tests | Large streamed fixture | File selection | Large local file |
| IPF | Existing algorithm tests | CLI/API artifact parity | `SCN-WEB-001` | Expanded output |
| Prepared models | Existing model tests | Fixed-seed CLI/API parity | `SCN-WEB-002` | Chunked generation |
| Small area | Existing calibration tests | Shared workflow artifacts | Small-area scenario | Province profile |
| Progress/cancel | Job state tests | Worker termination/recovery | Progress and cancel UI | Long-running job |
| Security | Origin/session/path tests | Symlink and traversal tests | Session expiry | - |
| Packaging | - | Clean installed wheel | Packaged app smoke | - |

## Suggested Release Slices

- **0.6.0:** FastAPI/Uvicorn runtime, durable runs, backend IPF, Runs workbench,
  and removal of browser IPF.
- **0.6.1:** Backend prepared-model generation, the stable versioned
  linked-population schema, chunked artifacts, scale preflight, and removal of
  browser tree generation.
- **0.6.2:** Guided small-area synthesis, validation/map results, selected
  utility workflows, cleanup, and final documentation parity.

Do not make the release split a reason to leave two synthesis implementations
indefinitely. Every migrated workflow has a named cleanup gate in the same
minor release slice.

## Definition Of Done

The local-runtime redesign is complete when:

1. A new user can start `synthpopcan serve`, choose a research task, pass
   preflight, run it, understand validation, and retrieve artifacts without
   learning command syntax first.
1. The same structured workflow functions are exercised by CLI and HTTP
   adapters, with parity tests for supported options and fixed seeds.
1. Runs survive browser refresh and server restart as succeeded, failed,
   cancelled, or interrupted research records.
1. Large outputs are written to disk incrementally and never serialized into a
   browser message or JSON response.
1. Each completed run records sufficient provenance and an executable CLI
   reproduction command.
1. Browser-side synthesis algorithms and the old standard-library API handler
   have been removed.
1. Loopback, workspace, session, path, upload, cancellation, and partial-output
   behavior have automated tests.
1. The standalone map export still opens independently and remains covered by
   its existing map tests.
