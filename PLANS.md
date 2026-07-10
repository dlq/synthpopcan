# SynthPopCan Plan

Status: release-phased roadmap\
Last updated: 2026-07-10

## Goal

Build SynthPopCan as a Python library, CLI, and local web app for Canadian
synthetic population generation.

This file says what belongs in each release phase. Completed release notes
belong in `CHANGELOG.md`; research background and source synthesis belong in
`NOTES.md`; full implementation task plans belong in `docs/superpowers/plans/`.

The core product scope remains:

1. Build synthetic populations through iterative proportional fitting from
   StatCan margin/control tables.
1. Build household- and person-level synthetic populations with a tree-based
   synthetic population generator using pluggable census microdata sources. The
   local 2016 Census material is the first available microdata source, not the
   tool boundary.
1. Keep environmental, school, healthcare, food, and broader enrichment data as
   later extensions unless they are needed for validation or demos.

## Principles

- Keep source data out of git. Track only code, documentation, tiny fixtures,
  and reproducible metadata.
- Prefer public fetches for public geography and service layers rather than
  storing copies in the project.
- Make the library usable without the web app. The CLI, beginner Python API,
  and local web app should share the same Python workflow and domain layers.
- Treat `synthpopcan serve` as a local guided workbench, not as a separately
  deployable frontend or a second implementation of the synthesis algorithms.
  Keep standalone outputs such as `geo map` HTML exports independent from that
  application-runtime decision.
- Keep beginner workflows readable for humanities and digital-humanities readers:
  approachable defaults, helpful errors, visible next steps, and optional
  machine-readable output for automation.
- Treat geography, variables, margins, seed samples, weights, generated rows,
  model packages, and validation reports as explicit concepts.
- Preserve provenance for every generated output: source tables, geography,
  variables, filters, model version, random seed, and validation metrics.

## Release Phases

### 0.1.x - Public Baseline And Stabilization

Status: active maintenance. Versions `0.1.0` and `0.1.1` establish the first
public baseline.

Purpose: make the current package trustworthy to install, inspect, document,
and demonstrate before adding the next modelling layer.

Shipped baseline:

- Python package, `synthpopcan` CLI, local `synthpopcan serve` web app, Sphinx
  documentation, Read the Docs configuration, PyPI publishing workflow, CI, and
  GitHub release workflow.
- Public-facing README, changelog, citation metadata, security policy,
  contribution notes, issue templates, release checklist, and project metadata.
- Beginner-friendly Python API through `synthpopcan.api` and top-level imports:
  `read_seed`, `read_controls`, `fit_ipf`, `write_weights`,
  `expand_population`, `read_model_package`, `generate_from_model`, and
  `write_population`.
- Beginner-lane CLI guidance through `synthpopcan guide`,
  `synthpopcan guide ipf`, and `synthpopcan guide model`, matching the web
  app's two main workflows: "IPF from margin tables" and "Generate from
  existing model".
- Core IPF workflow: normalized controls, seed checks, fitted weights,
  streamed expansion, fit reports, validation against controls, and browser
  preview/download support.
- StatCan WDS search, metadata inspection, ZIP fetch/normalization, WDS
  explain helpers, starter mapping support, and local-helper web app flow for
  generating IPF seed/control CSVs.
- Microdata inspection and 2016 hierarchical adapter for deriving household and
  person training views from mixed household/person source files.
- Tree/model workflow: train linked household/person models, audit models,
  prepare publishable-candidate release copies, package linked models, inspect
  packages, fetch release assets, generate linked household/person CSVs, and
  validate linked output.
- Prepared model catalogue available to both the CLI and web app, with release
  assets hosted on GitHub releases rather than bundled into the wheel.
- Web app first pass: frontend-first ES modules, narrow local helper for WDS
  and model catalogue support, Biome formatting/linting, generated previews,
  guarded expanded output, prepared model workflow, and basic validation
  summaries.
- Documentation site first pass: install guide, web app guide, IPF/control
  workflows, StatCan discovery, tree/model packaging workflows, validation,
  data/source notes, status page, API reference, and acknowledgments.

Remaining 0.1.x work:

- Treat `0.1.x` as a bugfix and polish line: fix broken docs, help text,
  packaging metadata, release workflow issues, PyPI/Read the Docs drift, and
  model-fetch regressions without expanding scope.
- Keep public release assets reproducible: checksums, release notes, model
  provenance, and clear download/fetch instructions.
- Run first-run smoke tests from a clean installed wheel for both beginner
  paths: `synthpopcan guide`, `synthpopcan serve`, IPF demo files, and prepared
  model generation.
- Add documentation-example checks for the most visible beginner workflows.
- Continue the coverage ratchet toward the stated 100% coverage goal without
  making private/raw-data tests part of the default suite.
- Review generated artifacts as user documents: default filenames, CSV column
  names, JSON manifest fields, provenance text, and validation/report wording.

0.1.x exit criteria:

- A new user can install from PyPI, launch the web app, run the IPF demo,
  generate from a prepared model, fetch published model assets, and find the
  same workflows in the docs.
- CI, packaging, docs, linting, web checks, and default tests are green from a
  clean checkout.
- The public repo does not require private data, large local caches, or hidden
  services.

### 0.2.x - Small-Area Linked Synthesis MVP

Status: complete as of 0.2.0.

Purpose: turn the existing IPF, Census Profile, tree package, linked
generation, and validation pieces into the first workflow that assigns linked
household/person populations to small geographies.

Problem statement:

- Broad-geography microdata-derived model packages can generate plausible
  linked households and persons.
- Census Profile small-area tables provide aggregate controls, not household
  rows.
- The missing bridge is a workflow that generates candidate linked
  household/person rows, calibrates candidate households to small-area controls,
  assigns those households to target geographies, copies linked persons into
  the assigned households, and validates both control margins and
  household/person structure.

Primary deliverables:

- Explicit small-area workflow that consumes a prepared linked model package and
  Census Profile controls.
- StatCan Census Profile fetch and preparation helpers for 2016 small
  geographies, starting with Montreal census tracts for the prototype and
  aggregate dissemination areas for broader province/country runs.
- Reviewed `controls from-census-profile` mappings for initial household
  controls such as household size, tenure, dwelling type, and any selected
  person controls used for validation.
- Household-level calibration first: fit or integerize generated household
  candidates per target geography, then let linked person rows inherit the
  assigned geography.
- Validation reports that check household controls, person margins used only
  for validation, and linked-output consistency.
- CLI and Python API entry points that are explicit about the workflow without
  forcing researchers to understand every intermediate command.
- Documentation workflow with a small reproducible fixture and a real-data
  optional path.

Geography strategy:

- Use Montreal census tracts for the first prototype because the files and
  analytical target are familiar.
- Use 2016 Census Profile aggregate dissemination area controls before
  dissemination area controls for broad province/country runs because ADAs are
  less sparse and cover the country.
- Add `da-all` support after calibration and validation are stable.
- Treat dissemination blocks as a later placement geography, not the first
  calibration geography.

Completed in the first implementation pass:

- `small-area calibrate-linked` consumes linked household/person candidate CSVs,
  fits household candidates to controls split by a target geography, and writes
  assigned household/person CSVs while preserving links.
- The beginner API exposes the same workflow as
  `synthpopcan.calibrate_small_area_linked(...)`.
- A Montreal CT tenure-control run generated 1,830,000 households and 4,170,389
  persons across 951 census tracts and passed linked-output validation.
- A Quebec ADA tenure-control run generated 3,750,000 households and 8,330,828
  persons across 1,115 aggregate dissemination areas and passed linked-output
  validation.

0.2.x exit criteria:

- A user can generate candidate linked households/persons from a prepared model
  package and calibrate households to at least one small-area control fixture.
  **Met for CLI and beginner API.**
- A Montreal census-tract prototype can run from documented commands or API
  calls with ignored local data. **Met for tenure controls; broaden controls
  after recoding household-size categories.**
- Validation clearly reports fitted household margins, inherited person
  geography, household/person link consistency, and limitations. **Met;
  calibration report includes geography-level residual summaries and a
  top-level convergence summary block.**
- The beginner-facing story remains one workflow, not a pile of intermediate
  files. **Met; `geo synthesize-from-package` generates candidates from a
  package and calibrates in one command.**

### 0.3.x - Small-Area Quality, Validation, And Performance

Status: complete as of `0.3.2`. `0.3.0` shipped the first quality/diagnostics
pass, `0.3.1` followed with bug fixes and output consistency, and `0.3.2`
completed the remaining work below.

Purpose: make small-area synthesis robust enough for larger geographies and
serious review.

Candidate work:

- Add staged or joint person-level calibration after household-level calibration
  is stable. **Met; an optional person-control file now triggers a household-first
  joint refinement over household indicators and linked-person category counts.
  Household/person links remain intact, and reports distinguish fractional from
  integerized residuals.**

- Add household-size recoding helpers for Census Profile categories such as
  `1`, `2`, `3`, `4`, and `5 or more` before fitting generated exact household
  sizes to small-area controls. **Met in 0.3.0; Census Profile household-size
  recoding preserves exact `household_size` values and fits grouped controls
  through `household_size_group`.**

- Improve margin-selection helpers so researchers can see which StatCan tables are
  usable controls, which are validation-only, and which require enrichment.
  **Met; `ipf suggest-controls` now presents all three decisions explicitly for
  the selected household or person row unit.**

- Add richer non-convergence diagnostics for inconsistent small-area controls,
  sparse geographies, structural zeros, and category mismatches. **Met; 0.3.0
  added calibration preflight checks for missing candidate columns and
  categories, followed by inconsistent-total errors, unsupported
  cross-category structural-zero errors, sparse-geography and sparse-support
  warnings, and linked-person ID checks.**

- Improve validation reports with geography-level summaries, largest residuals,
  linked household/person checks, and suggested next steps. **Met across 0.3.0
  and 0.3.1; calibration reports now carry geography-level residual summaries,
  largest-residual rows, and suggested next steps, and per-cell residual
  messages were clarified.**

- Prototype optional SciPy CSR or other sparse backends for high-cardinality or
  repeated IPF updates while keeping the current pure-Python indexed fitter as
  the default until dependency and browser implications are clear. **Met as a
  developer benchmark: `scripts/benchmarks.py ipf-backends` compares the current
  fitter, NumPy `bincount`, optional SciPy CSR, and optional Polars paths. Only
  the proven NumPy repeated-geography index is used by small-area runtime code.**

- Reduce memory pressure in microdata adapters through narrower column loading
  or streaming where it meaningfully affects real workflows. **Met for the
  common check and export paths: the StatCan adapter retains only identifiers,
  weights, and requested modelling columns; schema-inspection commands continue
  to load the complete column set intentionally.**

- Add performance budgets and benchmark fixtures for province-scale generation
  and calibration. **Met; `geo estimate-run` gives researchers a preflight scale
  estimate and web app vs CLI/API recommendation before calibration, backed by
  an executable synthetic small-area benchmark and a tracked
  province-scale profile covering candidate rows, geographies, output scale,
  fit time, and retained-weight memory.**

- Rationalize user scenarios into an explicit end-to-end integration-test
  source of truth. The repo already has scenario material in
  `docs/which-workflow.md`, `docs/library-getting-started.md`,
  `docs/web-app.md`, and `tests/test_workflows.py`, but the stories are
  currently implicit and scattered across docs and test names. Add a durable
  scenario inventory with stable IDs that can be referenced from tests, docs,
  and release checks without duplicating the full command transcript everywhere.

  Initial scenario inventory:

  - `SCN-IPF-001`: a beginner or notebook user has seed rows plus public control
    totals, exports or reads the seed, fits IPF weights, keeps the fit report,
    and validates the weighted or expanded artifact against controls.
  - `SCN-WDS-001`: a command-line user starts from a Statistics Canada WDS table,
    creates a category mapping template, normalizes controls, checks IPF inputs,
    fits weights, and validates the result.
  - `SCN-TREE-001`: a researcher with hierarchical microdata derives a training
    table, trains a tree model, generates rows under explicit conditions, and
    validates generated output against the training distribution.
  - `SCN-MODEL-001`: a user starts from a reviewed linked household/person model
    package, generates candidate households and people, validates links, then
    uses IPF to calibrate generated household candidates to controls.
  - `SCN-SMALLAREA-001`: a user starts from linked household/person candidates
    and small-area controls, calibrates households to target geographies,
    writes assigned household/person CSVs, and keeps validation reports with
    the outputs.
  - `SCN-WEB-001`: a first-time user uses the local web app's IPF path with demo
    or helper-generated files, previews inputs and outputs, and downloads the
    generated artifacts.
  - `SCN-WEB-002`: a first-time user uses the local web app's prepared-model
    path, generates linked household/person rows from a safe package, reviews
    validation summaries, and downloads both CSV files.

  Testing approach:

  - Keep `tests/test_workflows.py` as the CLI-level integration home, but rename
    or annotate tests so each one cites a scenario ID.
  - Add missing scenario coverage incrementally rather than creating one
    monolithic E2E test. Each scenario should assert the user-visible artifacts:
    CSV headers and row counts, JSON report fields, validation pass/fail status,
    provenance fields, and beginner-facing error or next-step text where
    relevant.
  - Keep fixtures tiny and public. Scenarios that depend on private Census
    material should use synthetic fixture rows or be documented as optional
    local/manual checks.
  - Add documentation-example checks for any scenario that appears as a copied
    command transcript in the docs, so docs, fixtures, and integration tests do
    not drift.
  - Treat web-app E2E tests separately from CLI workflow tests: browser tests
    should cover the two beginner paths and download artifacts, while CLI tests
    should remain fast and deterministic.

  **Met; `docs/scenarios.md` is the stable seven-scenario inventory. CLI
  workflows carry pytest scenario markers, documentation tests enforce complete
  ID references, and Playwright covers the browser IPF and prepared-model paths.**

0.3.x exit criteria:

- Small-area runs have predictable diagnostics for both success and failure.
  **Met.**
- Performance guidance is concrete enough to tell researchers when to use the web
  app, CLI, or Python API. **Met.**
- Optional faster backends remain invisible unless they clearly help a real
  user workflow. **Met; optional probes remain developer-only.**
- The main beginner and reviewer scenarios have stable IDs, documented fixtures,
  and at least one integration or browser test that exercises the workflow from
  user-visible input to user-visible artifact. **Met.**

### 0.4.x - Model Catalogue And Privacy Hardening

Status: planned.

Purpose: make prepared model distribution repeatable, reviewable, and safer for
public use.

Candidate work:

- Broaden the publishable-candidate workflow from demo/Montreal/Quebec models
  toward a repeatable Canada, province, territory, and large-CMA model
  catalogue.
- Add model-design advisor support for choosing full, reduced, or minimal
  target profiles by geography size, column sparsity, and privacy risk.
- Strengthen disclosure-risk checks before treating models trained from
  restricted microdata as public distribution candidates:
  - no raw rows, source identifiers, household identifiers, bootstrap indices,
    cached training data, debug example records, or exact source row storage;
  - minimum support thresholds for leaves or conditional-frequency groups;
  - rare-combination checks for linked household/person records;
  - high-purity checks and category-coarsening recommendations;
  - geography thresholding and model simplification constraints;
  - provenance metadata covering source description, columns, geography,
    parameters, random seed, package date, privacy audit, and warnings.
- Improve model-size and local-generation guidance for prepared packages.
- Keep public claims precise: a publishable model has passed SynthPopCan
  disclosure-risk checks and still requires appropriate human review.

0.4.x exit criteria:

- Published model assets have a consistent review, packaging, release, fetch,
  inspection, and documentation story.
- The CLI and web app can show geography, census vintage, source, privacy
  review status, release version, model size, generation limits, and known
  limitations for each prepared model.

### 0.5.x - Local Web Application Runtime

Status: planned.

Purpose: turn `synthpopcan serve` into a task-oriented local research workbench
backed by the same Python workflows as the CLI and beginner API.

Architecture decision:

- Static hosting and frontend-only portability are no longer design
  constraints. The browser guides setup, starts and monitors jobs, previews
  diagnostics, and exposes artifacts; Python performs synthesis, validation,
  and file writing.
- The web app must call shared application services directly through structured
  HTTP requests. It must not shell out to Click commands or parse terminal
  output.
- Browser-side IPF and model generation are migration code, not permanent
  parallel implementations. Remove them after backend parity and end-to-end
  coverage are established.
- The standalone `geo map` HTML export remains an artifact-oriented path using
  MapLibre GL JS and OpenFreeMap. It does not need to become part of the local
  application runtime.

Implementation plan:

- `docs/superpowers/plans/2026-07-10-local-web-application-runtime.md`

Candidate work:

- Introduce a small application-workflow layer for file-backed IPF, prepared
  model generation, small-area synthesis, validation, and artifact metadata.
  Keep Click, Rich, HTTP, and browser concerns outside this layer and extend the
  architecture tests to enforce the boundary.
- Replace the standard-library static helper with a supported loopback HTTP
  application runtime that provides structured request validation, streaming
  uploads, job status, cancellation, server-sent progress events, and artifact
  downloads.
- Add a controlled local workspace with durable run directories. Each run keeps
  a versioned manifest, parameters, input provenance, random seed, status,
  diagnostics, exact reproducible CLI command, and named output artifacts.
- Execute synthesis jobs outside the web-server process, initially with one
  local worker at a time. Interrupted or cancelled jobs must leave an explicit
  terminal state and must not expose partial files as completed artifacts.
- Migrate the current IPF and prepared-model browser workflows to backend jobs,
  preserving demos, file previews, model provenance, validation summaries, and
  downloadable outputs before deleting duplicated JavaScript computation.
- Add a guided small-area workflow that connects prepared-model generation,
  controls, preflight scale estimation, calibration, linked-output validation,
  and map generation without requiring users to assemble every intermediate
  command manually.
- Support larger local runs by writing rows and reports incrementally to disk.
  Browser memory must not scale with generated population size, and the UI must
  show preflight estimates for output rows, disk use, retained weights, and
  expected runtime before launching expensive work.
- Organize the UI around durable runs rather than a single long form: start a
  workflow, inspect inputs, configure approachable defaults, review preflight
  checks, monitor progress, and inspect results. Keep advanced model training,
  privacy auditing, and release packaging CLI-first during this phase.
- Keep the frontend as packaged HTML, CSS, and ES modules unless measured UI
  complexity provides a concrete reason for a framework. The removal of
  browser-side synthesis does not itself justify a frontend rewrite.
- Keep the default server loopback-only, reject unrestricted filesystem paths
  from HTTP requests, restrict file access to the configured workspace, and
  require an explicit future security design before supporting network serving.
- Revise the stable web scenarios to cover job creation, progress, completion,
  cancellation, restart/interruption handling, validation, artifact download,
  and reproducible-command output.

0.5.x exit criteria:

- The CLI and HTTP adapters use the same application services for IPF and
  prepared-model generation, with small-area synthesis available through the
  same run model.
- The web app can launch, monitor, cancel, revisit, and reproduce durable local
  runs without loading complete generated populations into browser memory.
- Completed run directories contain sufficient provenance, diagnostics, and
  artifacts to understand and reproduce the work outside the browser.
- Browser-side IPF and tree-generation implementations have been removed after
  parity tests pass; browser code is responsible only for interaction,
  inspection, and presentation.
- Loopback, workspace, upload, artifact, and path-traversal protections have
  automated coverage.
- Deterministic end-to-end scenarios cover a successful IPF run, prepared-model
  run, small-area run, failed preflight, cancellation, and artifact download.

### 0.6.x And Later - Enrichment And Scenario Layers

Status: deferred.

Purpose: extend generated populations with public contextual layers and
scenario workflows after the core synthesis workflows are stable.

Candidate work:

- Environmental exposure integration.
- School, healthcare, food-access, and other public-service enrichment.
- Spatial placement into dissemination blocks or other fine placement units
  using reviewed dwelling, land-use, building, or local public-data evidence.
- Scenario simulation and counterfactual workflows.
- Richer data-source documentation for StatCan, open.canada.ca,
  donneesquebec.ca, and related portals.
- Mapping of the original Google Drive source bundle to reproducible public
  sources where possible.

## Ongoing Tracks

### Data And Source Policy

Tracked:

- Source code.
- Documentation.
- Public-safe manifests.
- Tiny synthetic fixtures.
- Generated examples only when they are small, reproducible, and safe.

Ignored:

- Raw Census files.
- Private research datasets.
- Large public data caches.
- Generated populations from real source data.
- Model artifacts trained from private or large raw sources unless they have
  passed the explicit publishable-candidate release workflow and are published
  as release assets.

Documentation should keep distinguishing:

- public fetches;
- ignored local public caches;
- restricted/private local files;
- release-hosted prepared model assets;
- generated outputs that should not be committed.

### Testing And Coverage

- Keep the default suite fixture-based and free of private/raw-data
  requirements.
- Keep documentation examples runnable where they are presented as workflows.
- Continue working toward 100% coverage, using module/workflow ratchets rather
  than one brittle global gate while public surfaces are still moving.
- Keep live StatCan and full-data smoke tests opt-in and documented separately
  from the default test suite.
- Preserve web checks: Biome formatting/linting, static asset tests, local API
  contract tests, job-lifecycle tests, and browser scenarios for the local app.

### Documentation And Notes

- `README.md`: short project orientation, install command, quickest workflows,
  links to hosted docs, citation/license/status pointers.
- `docs/`: user guides, API reference, status, examples, release workflows, data
  access notes, and longer walkthroughs.
- `NOTES.md`: research synthesis, external-source notes, background literature,
  and decisions that are not immediate roadmap tasks.
- `PLANS.md`: release-phase roadmap only; avoid turning this file back into an
  implementation log.

### Public Release Operations

- Keep GitHub releases as the no-service distribution point for prepared model
  assets.
- Keep PyPI publishing and Read the Docs builds aligned with tags.
- Include release notes, checksums, and asset provenance for public model
  packages.
- Smoke test the published wheel, console script, docs link, and model fetch
  path after each release.

## Open Decisions

- Exact dependency stack for larger arrays/tables/models: the general IPF path
  remains pure Python, repeated-geography calibration uses the proven NumPy
  index, pandas is used for linked realization, and SciPy CSR/Polars remain
  developer benchmark probes rather than runtime choices.
- A technical internals document covering the Python implementation choices,
  IPF backend experiments (pure Python vs NumPy bincount vs SciPy CSR vs
  Polars), and design rationale would be worth writing eventually — either as
  a dedicated docs page or a NOTES.md section.
- First broadly supported Census Profile access path and default geography
  levels for small-area synthesis.
- First stable small-area generated-output schema for linked
  household/person/geography rows.
- Integerization alternatives beyond the current deterministic expansion path.

## Done Means

The first useful public line is done when a user can:

1. Install SynthPopCan from PyPI.
1. Launch the local web app.
1. Search or inspect a StatCan table and prepare IPF inputs.
1. Generate and validate an IPF synthetic population.
1. Fetch or choose a prepared model package.
1. Generate linked household/person rows from that package.
1. Understand the provenance, limitations, and validation output.
1. Reproduce the run from tracked code and ignored local data caches.
