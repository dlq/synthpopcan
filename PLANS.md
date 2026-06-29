# SynthPopCan Plan

Status: release-phased roadmap\
Last updated: 2026-06-26

## Goal

Build SynthPopCan as a Python library, CLI, and local web app for Canadian
synthetic population generation.

This file says what belongs in each release phase. Detailed completed
implementation status, benchmark notes, and verification evidence belong in the
Sphinx documentation, especially `docs/status.md`. Research background and
source synthesis belong in `NOTES.md`. Full implementation task plans belong in
`docs/superpowers/plans/`.

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
- Make the library usable without the web app. The CLI should expose the same
  core workflows as the Python API.
- Keep beginner workflows readable for humanities and digital-humanities users:
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
  forcing users to understand every intermediate command.
- Documentation workflow with a small reproducible fixture and a real-data
  optional path.

Implementation anchor:

- Detailed implementation plan:
  `docs/superpowers/plans/2026-06-25-small-area-linked-synthesis.md`.

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

Status: planned after the 0.2.x MVP proves the workflow.

Purpose: make small-area synthesis robust enough for larger geographies and
serious review.

Candidate work:

- Add staged or joint person-level calibration after household-level calibration
  is stable.
- Add household-size recoding helpers for Census Profile categories such as
  `1`, `2`, `3`, `4`, and `5 or more` before fitting generated exact household
  sizes to small-area controls.
- Improve margin-selection helpers so users can see which StatCan tables are
  usable controls, which are validation-only, and which require enrichment.
- Add richer non-convergence diagnostics for inconsistent small-area controls,
  sparse geographies, structural zeros, and category mismatches.
- Improve validation reports with geography-level summaries, largest residuals,
  linked household/person checks, and suggested next steps.
- Prototype optional SciPy CSR or other sparse backends for high-cardinality or
  repeated IPF updates while keeping the current pure-Python indexed fitter as
  the default until dependency and browser implications are clear.
- Reduce memory pressure in microdata adapters through narrower column loading
  or streaming where it meaningfully affects real workflows.
- Add performance budgets and benchmark fixtures for province-scale generation
  and calibration. **Partly met; `geo estimate-run` gives users a preflight
  scale estimate and web app vs CLI/API recommendation before calibration.**

0.3.x exit criteria:

- Small-area runs have predictable diagnostics for both success and failure.
- Performance guidance is concrete enough to tell users when to use the web
  app, CLI, or Python API.
- Optional faster backends remain invisible unless they clearly help a real
  user workflow.

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
- Improve model-size and browser-readiness guidance for prepared packages.
- Keep public claims precise: a publishable model has passed SynthPopCan
  disclosure-risk checks and still requires appropriate human review.

0.4.x exit criteria:

- Published model assets have a consistent review, packaging, release, fetch,
  inspection, and documentation story.
- The CLI and web app can show geography, census vintage, source, privacy
  review status, release version, model size, generation limits, and known
  limitations for each prepared model.

### 0.5.x - Browser Scale And Reusable Web Runtime

Status: planned.

Purpose: decide how far the web app can go as a frontend-first local tool.

Candidate work:

- Investigate browser streaming exports for larger web-app runs using
  `ReadableStream`, `TextEncoderStream`, Web Workers, and the File System
  Access API where supported.
- Keep hard memory guardrails and show exact CLI commands when browser export
  is too large.
- Evaluate Pyodide/WebAssembly for selected Python-backed workflows if it
  reduces the need for a local backend without making the app brittle.
- Keep the local Python helper narrow: serving assets, StatCan download support,
  model catalogue access, and possibly streaming file output when browser
  writing is not reliable.
- Decide whether browser-side IPF/model-generation modules are stable enough
  for an npm package. Do not create an npm surface until the terminology and
  workflows rhyme with the Python API, CLI, and web app.

0.5.x exit criteria:

- The web app has clear limits for file size, output size, memory, and expected
  runtime.
- Any reusable JavaScript package has a reason to exist beyond the packaged
  Python web assets.

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
- Preserve web checks: Biome formatting/linting and static asset tests for the
  local app.

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

- Exact dependency stack for arrays/tables/models: current default is pure
  Python for indexed IPF, scikit-learn where CART models are used, and later
  optional NumPy/SciPy CSR/Polars/PyArrow experiments for larger sparse or
  table-ingestion-heavy workflows.
- A technical internals document covering the Python implementation choices,
  IPF backend experiments (pure Python vs NumPy bincount vs SciPy CSR vs
  Polars), and design rationale would be worth writing eventually — either as
  a dedicated docs page or a NOTES.md section.
- Whether schemas should remain dataclasses or move to Pydantic once the API
  surface stabilizes.
- First broadly supported Census Profile access path and default geography
  levels for small-area synthesis.
- First stable small-area generated-output schema for linked
  household/person/geography rows.
- Integerization alternatives beyond the current deterministic expansion path.
- How far the web app can remain static/frontend-first before a backend or
  Pyodide-style runtime is justified.

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
