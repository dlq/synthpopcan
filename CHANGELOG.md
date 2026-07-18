# Changelog

All notable public changes to SynthPopCan are tracked here.

## Unreleased

- Add the versioned `synthpopcan-linked-population-v1` household/person artifact
  contract, shared descriptors across library, CLI, prepared-model, and
  small-area outputs, explicit geography inheritance, compatibility rules, and
  a golden schema fixture. Exercise representative 2016 and 2021 hierarchical
  Census inputs end to end against the shared contract.
- Reject malformed, cyclic, multiply rooted, or inconsistent serialized CART
  models; bound local-web generation to 250,000 households and 2,000,000
  people; and terminate isolated workers that exceed the six-hour run limit.
- Add year-aware Census Profile downloads for verified 2021 CT, ADA, and
  national CSD products, national CSD cartographic boundaries for both
  vintages, balance the local 2016/2021 small-area source coverage, and parse
  both vintages' distinct characteristic and geography schemas.
- Add explicit Statistics Canada 2021 hierarchical and individuals PUMF
  adapters, a year-specific linked-tree column profile, streaming inspection
  for full-size public microdata, and linked 2021 model-training support.
- Add 16 checksum-verified 2021 linked household/person model packages covering
  Canada, nine provinces, five PUMF-coded CMAs, and a minimal-profile Prince
  Edward Island model to the shared CLI and web-app catalogue.
- Add reproducible extraction of public-safe variable labels and fixed-width
  metadata from the official SPSS command files.
- Add national 2021 CT and ADA cartographic-boundary preparation with retained
  DGUID, land-area, and province/territory attributes, streaming atomic GeoJSON
  output, and the final 2021 dissemination-geographies relationship-file
  download.
- Rationalize the local 2016 layout to mirror 2021, preserve every source CT
  and ADA boundary attribute, and separate authoritative raw inputs from
  regional subsets and intermediate derived files.
- Rationalize the complete ignored data cache into authoritative `raw`,
  reusable `derived`, disposable `work`, and restricted `private/sources`
  roots; relocate prepared boundaries, release candidates, model-build
  workspaces, and experimental small-area outputs according to lifecycle and
  provenance rather than sensitivity.

## 0.6.0 - 2026-07-17

- Replaced browser-owned IPF, prepared-model, and small-area synthesis with
  durable FastAPI/Uvicorn runs backed by the same file-oriented Python
  workflows as the CLI and beginner API.
- Added a controlled run workspace with streamed uploads, versioned manifests,
  persisted progress, cancellation and restart recovery, bounded previews,
  atomic artifacts, and exact CLI reproduction commands.
- Added Python-backed small-area generation and calibration from either a
  reviewed model/package or existing linked candidate CSVs, with scale,
  linkage, dimension, category, disk, convergence, residual, and map checks.
- Added bounded model catalogue installation and removal for large published
  packages without loading their JSON payloads into browser memory.
- Removed obsolete browser synthesis and ZIP/WDS-normalization modules; the
  local web app, CLI, and Python API now share Python implementations rather
  than separate computational tiers.

## 0.5.1 - 2026-07-15

- Added a public correctness-assurance statement, independent numerical and
  artifact oracles, generated invariant and parity tests, a versioned public
  Statistics Canada fixture, scheduled/live-drift checks, and installed-wheel
  verification before publishing.
- Corrected sparse IPF semantics, browser integerization, exact geographic
  allocation, linked identifier checks, finite numeric boundaries, WDS mapping
  collisions, and output-column collisions uncovered by the assurance pass.
- Based model disclosure thresholds on contributing source-row counts while
  retaining weighted support separately, preventing survey weights from making
  a one-row group appear adequately supported.
- Bounded local WDS preparation by request/download size, ZIP entry and
  decompression totals, selected CSV size, row count, and concurrency; browser
  ZIP handling now inspects metadata before inflating only the selected data
  member.
- Disabled registered models above a 32 MiB uncompressed threshold in the web
  app and local model API, with a CLI handoff until backend generation replaces
  browser whole-payload processing.
- Hardened standalone maps by escaping HTML and inline-script data, constructing
  tooltips with text nodes, rejecting unmatched geographies, and preserving
  polygon holes and islands from shapefiles.
- Resolved private-data paths before disclosure guards, serialized concurrent
  model-cache updates through unique temporary files, and made StatCan downloads
  bounded, completion-checked, and atomic so failed refreshes preserve cached data.
- Clarified that browser and CLI random-number generators do not promise
  identical rows, aligned their WDS latest-period selection, and constrained
  trusted PyPI publishing to tested tags matching the package version.

## 0.5.0 - 2026-07-14

Simplified and consolidated the public CLI, Python API, and linked-population
artifact contract. This release intentionally removes superseded pre-1.0
interfaces rather than retaining compatibility aliases.

- Consolidated model work under `models` (`models generate` for reviewed linked
  packages and `models build ...` for training, audit, and packaging), shortened
  small-area commands to `geo controls|estimate|calibrate|synthesize|boundaries`,
  and removed redundant single-choice flags. Linked workflows now exchange one
  directory containing `households.csv`, `persons.csv`, and a manifest or report.
- Renamed validation commands to `validate ipf`, `validate linked`, and
  `validate model`; standardized CLI starting-weight options on
  `--weight-column`; made human summaries the default where raw JSON was
  previously printed without an explicit format choice; and made fetched asset
  paths available on stdout for composition.
- Added `--subsample-seed` to `geo calibrate` and
  `geo synthesize`, exposing the previously hard-coded
  candidate-subsample seed independently from candidate generation. Runs stay
  reproducible by default (seed `42`), and the calibration report's `subsample`
  block now records the effective seed plus input and selected row counts so
  `--pool-size` runs are traceable and their sensitivity can be checked by
  varying the seed.
- Simplified the stable beginner Python API around composable workflow results:
  `calibrate_small_area` now accepts generated linked rows, paired CSV paths, or
  a linked-population directory and returns a typed `SmallAreaResult` with artifact
  paths and headline diagnostics.
- Split population writing into `write_population` for one flat CSV and
  `write_linked_population` for paired household/person files. Writers now
  create parent directories and return the paths they wrote.
- Added typed `LinkedPopulationFiles`, `SmallAreaResult`, `PopulationRows`,
  `ControlTable`, and `IPFResult` exports, an explicit stable-API contract test,
  and a `py.typed` marker for downstream type checkers.
- Narrowed beginner `fit_ipf` controls to normalized control CSV paths or
  `ControlTable` values. Advanced callers that already construct raw
  `IPFMargin` sequences can continue to use `synthpopcan.ipf.fit_ipf`.
- Updated the API reference, library tutorial, downloadable notebook, and
  small-area guide for the simplified workflow and typed results.

## 0.4.0 - 2026-07-10

Model catalogue metadata, safer guided browser workflows, and small-area
preparation with reproducible CLI handoff.

- Added a third local web-app workflow for preparing linked small-area
  synthesis. It uses the shared Python estimator to report geography, household,
  person, output-row, and calibration-pool scale before producing exact
  `geo estimate-run` and `geo synthesize-from-package` commands.
- Made `geo synthesize-from-package` accept registered premade model IDs as well
  as local linked-package JSON paths.
- Added Census vintage, asset release, privacy-review status, compressed size,
  generation guidance, and known limitations to prepared-model catalogue data,
  CLI listings, and web inspection.
- Let the local web app automatically download and verify published model
  packages, with a visible download indicator and generation controls disabled
  until a model is ready.
- Added guided WDS category refinement, safer search ranking and warning labels,
  a recommended population table, reproducible selection manifests, and
  category-filtering CLI follow-ups.
- Made expanded synthetic records the approachable IPF default, highlighted
  prepared inputs, improved result explanations, and added commented CLI
  continuations to completed browser workflows.
- Added `SCN-WEB-003` and Python HTTP-adapter tests for successful and invalid
  small-area preflight requests.
- Made small-area CLI handoffs detect Census `household_size_group` controls and
  add the required candidate-grouping options automatically.
- Kept `models list` compact and added `models show MODEL_ID` for detailed
  provenance, privacy, release, size, generation, and limitation metadata.
- Split the browser entry point into scoped IPF/WDS, prepared-model, and
  small-area controllers with independently tested command builders and shared
  form and HTTP utilities.
- Aligned local, CI, and release verification around Python type checks,
  JavaScript unit tests, and Playwright scenarios.

## 0.3.2 - 2026-07-10

Linked-person calibration, diagnostics, performance guidance, and end-to-end
workflow coverage.

- Added optional linked person-level small-area controls. Household controls
  are fitted first, then household weights are jointly refined against
  linked-person category counts without separating people from households.
- Expanded small-area preflight diagnostics for inconsistent margin totals,
  unsupported cross-category cells, sparse geographies, sparse candidate
  support, and broken household/person links.
- Classified suggested controls as usable now, validation-only for the current
  row unit, or requiring enrichment/model changes.
- Reduced retained memory for common microdata checks and exports by loading
  only identifiers, weights, and requested modelling columns.
- Added an executable small-area benchmark fixture and explicit province-scale
  timing and retained-weight budgets while keeping experimental SciPy CSR and
  Polars probes out of the runtime path.
- Added a stable seven-scenario end-to-end inventory, linked pytest scenario
  markers, a linked small-area integration workflow, and Playwright coverage
  for the browser IPF and prepared-model paths.
- Fixed narrow-screen web-app tooltip and brand-layout overflow.
- Reframed the planned web-app runtime around shared Python workflows, durable
  local runs, and streamed artifacts while keeping the standalone MapLibre map
  export independent.

## 0.3.1 - 2026-07-08

Bug fixes, output consistency, and internal cleanup.

- Fixed `--weight-field` being silently ignored in small-area calibration:
  `geo calibrate-linked` and `calibrate_small_area_linked` now start each
  geography fit from the candidate starting weights instead of uniform ones.
- Corrupt cached model packages are now removed and re-downloaded by
  `models fetch` instead of failing on every retry; checksum verification
  streams instead of loading whole packages into memory.
- Clarified validation and fit-report residual messages: each issue now reads
  "Residual is ..." instead of every issue claiming to be the largest.
- Reported a clearer error for empty candidate CSVs and for training rows
  missing their weight column.
- Unified the in-memory and streaming small-area realization paths onto one
  shared implementation so their output can no longer drift apart.
- Made numeric CSV output consistent across the library and CLI: the beginner
  API's `write_weights` now formats near-integer weights the same way as
  `ipf fit`, absorbing floating-point noise instead of writing values such as
  `2.9999999998`.
- Renamed `TreeModelSpec.as_summary()` to `TreeModelSpec.to_dict()` so the name
  matches the other complete model serializers; `as_summary()` now denotes only
  lossy summaries (as on `TreeTrainingSample`). The returned dictionary is
  unchanged.

## 0.3.0 - 2026-06-29

Small-area quality, validation, and performance guidance.

- Added the Canada 2016 all-fields linked model package to the downloadable
  model registry as `canada-2016-all-fields`.
- Switched downloadable model release assets to gzip-compressed JSON while
  keeping the local model cache as normal JSON files.
- Added Census Profile household-size recoding that preserves exact
  `household_size` values and fits grouped controls through
  `household_size_group`.
- Added largest-residual and suggested-next-step diagnostics to small-area
  calibration reports and CLI summaries.
- Added small-area calibration preflight checks for missing candidate columns
  and categories before IPF fitting starts.
- Added `geo estimate-run` to preview small-area run scale and recommend
  whether the web app, CLI, or Python API is the right surface before launching
  a large calibration.

## 0.2.1 - 2026-06-28

Polish and CI hardening.

- Added a clean-install smoke-test CI job that builds the wheel, installs it in
  an isolated environment, and exercises key CLI entry points including bundled
  demo generation.
- Added an end-to-end doc-example test that runs the five-command IPF workflow
  from `docs/installation.md` against the repo's fixture files.
- Fixed "Miss" column heading to "Missing" in the IPF input check table.
- Replaced `(s)` plural shorthand with proper plurals in the calibrate-linked
  summary message.
- Replaced vague "process" action verb with "read or write" in the
  calibrate-linked file-access error message.

## 0.2.0 - 2026-06-28

Small-area linked synthesis MVP.

- Added `small-area calibrate-linked` command and `calibrate_small_area_linked`
  API entry point to assign linked household/person candidates to target
  geographies using Census Profile controls.
- Added `geo` command group: `build-controls`, `map`, `prepare-boundaries`, and
  `synthesize-from-package` subcommands covering the end-to-end small-area
  workflow in a single command.
- Added StatCan Census Profile 2016 fetch and preparation helpers for census
  tracts and aggregate dissemination areas.
- Added geography-level residual summaries to calibration reports.
- Expanded the prepared model catalogue to include all provinces, territories,
  and major CMAs.
- Vectorized IPF and population expansion using NumPy (~2.3× speedup); added
  threaded IPF loop and pool-size subsampling for large candidate sets.
- Renamed `--geography-*` CLI flags to `--geo-*` for consistency.
- Declared pandas as an explicit dependency.
- Enforced public/private distinction across library modules with `__all__`.
- Added pre-commit hooks for ruff, pyright, and pytest.
- Raised test coverage from 95% to 99.5% (552 tests).

## 0.1.1 - 2026-06-26

Public repository polish release.

- Added README badges for CI, documentation, PyPI, and license status.
- Added `CITATION.cff` for research software citation metadata.
- Added GitHub issue templates for bugs, feature requests, and model release
  reviews.
- Added release checklist guidance for package and model asset releases.
- Added a CI Python formatting check with `ruff format --check`.
- Normalized documentation links to `synthpopcan.readthedocs.io`.
- Added repository topics for discovery on GitHub.

## 0.1.0 - 2026-06-25

Initial public release.

- Added the `synthpopcan` Python package and CLI.
- Added IPF workflows for seed rows and normalized margin/control tables.
- Added Statistics Canada WDS search, inspection, fetch, and IPF-preparation
  helpers.
- Added census microdata adapters, validation helpers, and data layout checks.
- Added tree-based household/person synthetic population generation workflows.
- Added local web app support for beginner IPF and generated-from-model paths.
- Added downloadable model package registry with GitHub Release assets.
- Added Sphinx documentation, CI, PyPI publishing workflow, and Read the Docs
  configuration.
