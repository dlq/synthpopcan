# Changelog

All notable public changes to SynthPopCan are tracked here.

## Unreleased

- Record the minted `1.0.0` Zenodo version DOI and the completed Software
  Heritage snapshot, release object, and source revision in citation metadata
  and a dated preservation record.

## 1.0.0 - 2026-08-16

Stable public interfaces and open, durable research-software stewardship.

- Add a packaged, machine-readable 1.x contract for the complete
  documented command tree, curated beginner and advanced Python APIs, and
  supported persisted schemas. Publish the corresponding 1.x compatibility,
  deprecation, output-stream, and correctness-exception policy; validate the
  same contract from an isolated installed wheel.
- Add a complete machine-readable eligibility inventory for all 116 fields in
  the 2016 hierarchical PUMF and all 122 fields in 2021. Reconcile the 35
  existing source targets per vintage; classify identifiers, weights,
  geography context, deferred fields, cross-vintage concepts, applicability,
  support, controls, interpretation concerns, and family-entity requirements
  without introducing a new public model profile.
- Add a bilingual English/French Quebec 2021 case study with a pinned released
  model, DOI, compressed and uncompressed checksums, fixed seed, validation
  sequence, and scoped interpretation. Exercise the documented fetch, inspect,
  generate, and validate commands from an isolated installed wheel using an
  honest offline fictional-package substitution in release CI.
- Add full Citation File Format schema validation as a development-only local
  and CI gate, record the independently preserved Software Heritage snapshot
  and release objects, and publish dated FAIR4RS, software-management,
  preservation, supported-environment, maintenance, succession, and end-of-life
  records.
- Accept Darcy Quesnel's 2026-08-15 open-by-default prepared-model policy in
  ADR-0014: MIT for software, continuing Statistics Canada Open Licence
  conditions for source Information, and CC BY 4.0 only for original rights the
  package author owns or controls. Keep those layers cumulative and scoped,
  preserve privacy and provenance safeguards, and make external review optional
  rather than a `1.0.0` gate. Complete and durably record the reviewed,
  non-overwriting correction of all 32 existing model concepts.
- Add a strict, versioned prepared-model licensing object that distinguishes
  Census-derived, synthetic-only, and unclassified legacy packages without
  inferring an author licence from arbitrary provenance. Preserve validated
  licensing metadata through package inspection, linked generation,
  calibration, exchange, CLI, API, and workflow manifests. Census-derived
  completion remains bound to the accepted maintainer policy authority and
  date rather than an invented external approval.
- Make current Zenodo correction manifests explicitly review-only and gate all
  production model deposition on accepted ADR and separate correction-
  implementation and correction-execution markers.
  Add a streaming, byte-preserving corrected-asset builder plus a fail-closed
  executor for identifier-preserving metadata edits, non-overwriting versions,
  supersession, historical/new-asset verification, exact registry candidates,
  durable draft ownership, and operation/version/hash-aware resume. Historical
  assets remain ineligible for sandbox upload. Independent adversarial review
  closed all three prior executor blockers, with 137 focused tests plus Ruff,
  Pyright, and diff checks passing. On 2026-08-16, remotely verify all 32
  metadata corrections and 32 corrected package versions, preserve every
  historical asset, confirm zero mutable drafts, integrate the 32 exact
  registry updates, and add tracked sanitized clean-clone evidence.
- Add a reproducible package-wide strict-Pyright audit configuration and move
  the exchange CLI adapter into the strict-clean regression list by separating
  its typed artifact-path mapping from the heterogeneous result payload.
  Preserve 100% Pyright public type completeness for the frozen Python surface.
- Pin the isolated Hatchling build backend in the lock graph, make every README
  link and image render correctly from PyPI, and strengthen the local and
  publishing gates. Release evidence now requires the exact successful push CI
  run, both distributions, and completed wheel, sdist, optional model-build,
  and bilingual case-study installation smokes.
- Advance the package maturity classifier from alpha to beta while retaining
  explicit limits on statistical fitness, representativeness, disclosure
  safety, causal claims, and support commitments.

## 0.9.0 - 2026-08-10

Bounded methodological and small-area confidence.

- Add a reproducible independent bounded relative-entropy calibration oracle,
  generated feasible and infeasible linked cases, and a reviewed
  integerization comparison. Retain the production linked multiplicative
  updater and deterministic systematic-midpoint integerizer; keep the oracle
  and largest-remainder method as evidence comparators rather than new runtime
  switches.
- Add strict versioned control-pack, compatibility-registry, and source/
  universe-evidence contracts. Ship eight definition-only core packs spanning
  the 2016 and 2021 Census vintages and CSD, CT, ADA, and DA levels, with
  reviewed private-household household-size, tenure, and broad age-by-sex or
  age-by-gender mappings. Census counts remain explicit normalized inputs and
  are never bundled into pack definitions.
- Add fail-closed pack planning across the Python API, CLI, and durable local
  web workflow. Plans bind the exact control tables, source revisions, Census
  vintage, geography namespace, eligible geography set, and private-household
  universe evidence; validate complete vectors, candidate fields and support,
  linkage, duplicate cells, and reconciliation; apply reviewed candidate
  derivations; and report controlled, coarsened, derived, and uncontrolled
  fields without treating carried-through PUMF attributes as local controls.
- Add an independently recomputed linked-calibration validation profile to
  small-area reports. It separates fractional residuals from integer
  realization, counts person contributions through household weights, and
  reports weight concentration, effective sample size, candidate reuse,
  supported rare-cell loss, declared zero-target violations, field targeting,
  and explicit claim limitations using cached vectorized contribution data.
- Add bounded multi-scale calibration evidence and a pinned, aggregate-only
  comparison with the Prédhumeau-Manley Canadian synthetic population. The
  comparison records exact external resource and slice provenance and remains
  descriptive: differing geography vintages, methods, and modeled outputs do
  not create a record-level truth or representativeness claim.
- Record the calibration and integerization backend decision in ADR-0012 and
  the separation of reusable control definitions, normalized counts, and
  checksummed evidence in ADR-0013. Document the applicability boundaries and
  defer broader control families, collective populations, national claims,
  uncertainty ensembles, and richer hierarchical entities until after the
  pre-1.0 interface freeze unless separately justified.

## 0.8.0 - 2026-08-07

Portable, simulator-neutral population handoff.

- Add `synthpopcan-exchange-v1`, a self-describing CSV/JSON population-
  contribution bundle that copies linked household and person CSV bytes
  unchanged and carries their stable keys, foreign-key relationship, row
  counts, and optional household geography.
- Add a complete machine-readable data dictionary, standalone or durable-run
  provenance, exact CLI/library reproduction metadata, creation-time
  validation, and a manifest with SHA-256 digests, byte sizes, media types,
  access classifications, redistribution status, temporal context, limitations,
  and explicitly absent simulation inputs.
- Add shared `create_exchange_bundle` and `validate_exchange_bundle` library
  workflows plus `synthpopcan bundle create` and `bundle validate` commands.
  Strict validation rejects missing, changed, extra, misclassified, or
  structurally inconsistent bundle files and incompatible Census geography
  context.
- Document and test a deterministic fictional handoff from the bundled model,
  successful durable-run composition, tamper detection, CLI/API parity, and an
  isolated installed-wheel exchange workflow without adding a simulator or
  optional format dependency.
- Keep exchange v1 deliberately bounded: it is not a runnable simulation,
  target-specific adapter, observed-residence claim, privacy certification, or
  finding of statistical fitness. Parquet, GIS containers, RO-Crate, archives,
  and target adapters remain demand-backed future mappings.

## 0.7.2 - 2026-08-02

Maintained public Can-FED and educational-facility enrichment adapters. This
release combines the outcomes originally sequenced as 0.7.1 and 0.7.2; no
separate 0.7.1 package is planned.

- Add shared maintained-adapter orchestration for bounded public acquisition,
  offline reuse of pinned content-addressed bytes, reviewed byte-revision
  checks, deterministic normalization, source-specific and generic validation,
  immutable source/resource evidence, sidecar publication, and proof that
  linked base tables remain unchanged. Reject an output directory that aliases
  the base population before any file is written.
- Add the Can-FED v2 general-use adapter and `enrich can-fed`/
  `enrich_can_fed` interfaces. It combines or selects the public 1 km and 3 km
  categorical products, preserves 2021 DA and August 2024/Business Register
  context, rejects malformed keys and cross-vintage linkage, reconciles exact
  source/base coverage, and excludes RDC-controlled detailed measures.
- Record the live Can-FED discrepancy explicitly: the reviewed archive contains
  57,936 unique DAs per buffer even though the accompanying guide says 28 DAs
  were excluded. Validation follows acquired bytes without inventing a quality
  flag.
- Add the corrected ODEF v3.0.1 adapter and `enrich odef`/`enrich_odef`
  interfaces. It streams normalized rows through an atomic output, preserves
  stable and source facility IDs, provider/authority, address, grade and ISCED,
  language, provider-specific facility type, source dates, CSD context, WKT,
  and parsed coordinates while retaining missing and potentially colocated
  facilities.
- Pin the mutable ODEF v3.0 URL to its reviewed v3.0.1 correction and report
  differences between the live CSV, bundled record layout, and older product
  prose. The current source has no CMA columns or separate source longitude and
  latitude fields, so the adapter does not invent them.
- Add public-safe synthetic fixtures, source-drift and malformed-data tests,
  end-to-end CLI/API reproduction, exact unmatched-geography evidence, opt-in
  live Statistics Canada checks, and documentation that keeps area context and
  facility inventory distinct from exposure, capacity, catchment,
  accessibility, eligibility, or causal claims.
- Make adapter JSON output report every written artifact path alongside the
  complete validation object; document exact normalized columns, missing-value
  encodings, ordinal Can-FED semantics, and ODEF's undeclared coordinate CRS.
- Restore 100% Pyright public type completeness after adding the maintained
  adapters, while retaining the package-wide standard gate and the existing
  16-module strict ratchet.

## 0.7.0 - 2026-08-01

Explicit Census geography and reusable external-data enrichment framework.

- Publish the independently versioned `geodata-v1` display-boundary catalogue
  and checksummed 2016 national and 2021 national/regional assets; add verified,
  atomic runtime retrieval and caching; and prefer topology-preserving prepared
  geometry for national maps without replacing canonical analytical boundaries.
- Make scikit-learn an optional `model-build` dependency for CART training.
  Portable frequency/CART model reading and population generation remain in the
  base runtime, as does conditional-frequency training.
- Fix permanent evidence attachment by giving the checkout-free release job an
  explicit GitHub repository target.
- Add explicit versioned Census geography universe, identity, and relationship
  contracts; reject cross-vintage and namespace mismatches; and carry the
  geography universe through small-area library, CLI, durable-run, and local
  API requests.
- Add a reusable external-data enrichment foundation with bilingual source
  profiles, immutable resource revisions, bounded content-addressed public
  retrieval, governed local/restricted registration, sidecar layers,
  researcher-supplied normalized-layer import, validation, and manifests that
  prove the linked base population remains byte-for-byte unchanged.
- Register the official 2021 national DA cartographic boundary and Québec DA
  Census Profile products, tolerate their differing official archive names,
  and add a bounded metropolitan/rural Québec DA evidence preparer with
  authoritative DGRF relationships, exact controls, streaming boundary
  subsetting, hashes, resource measurements, and a compact 2016 DA regression.
- Register all six official regional 2021 DA Census Profile products and
  generalize restartable national orchestration across DA and ADA for all 13
  provinces and territories. Level-specific profile and DGRF adapters share
  plan and batch schemas, one-pass boundary partitioning, explicit exclusions,
  storage estimates, resumable state, model conditioning, linked validation,
  artifact hashes, and optional maps; the PUMF's combined northern `PR=70`
  candidate pool remains explicit with separate territorial controls.
- Accelerate national DA/ADA execution by generating one evidence-checked
  linked candidate pool per PUMF condition, verifying caches without reopening
  the model, atomically checkpointing batches, supporting bounded process and
  fit parallelism, recording phase timings and in-write artifact hashes, and
  deferring opt-in batch maps in favour of a compact completed-plan national
  summary. The existing `geo map` CLI and `render_small_area_map` API now accept
  a completed national plan or its directory, stream and cache the standard
  household/person map statistics across every batch, and render the familiar
  12-variable polygon choropleth. It prefers separately published,
  topology-preserving display geometry when available and retains the
  fixed-grid canonical-boundary fallback. The compact point overview remains
  separate and canonical StatCan geometry is unchanged.
- Exclude hierarchical-PUMF `TENUR=8` (“Not available”) households and their
  linked persons from national tenure-calibration pools, record the exclusions,
  invalidate incompatible caches, and reject any uncontrolled candidate
  category during general small-area preflight.
- Align 2016 and 2021 Census Profile tenure controls with the hierarchical PUMF
  by combining the published band/local-government dwelling count with renter
  rather than omitting it and proportionally rescaling the remaining classes.
- Version StatCan resource manifests with explicit source revisions, SHA-256
  digests, byte sizes, and geography identity for single-universe boundary
  products.
- Validate untrusted local-web requests, durable manifests, uploads, events,
  and worker messages with strict Pydantic runtime schemas; move the complete
  package to Pyright standard mode and ratchet 16 clean modules to strict.
- Make calibrated CLI, beginner-API, and durable small-area workflows publish
  a linked-population manifest so their outputs compose directly with
  enrichment; align standard StatCan boundary-field inference and extend the
  isolated-wheel smoke test through an offline enrichment workflow.

## 0.6.3 - 2026-07-27

Reproduction and durable correctness evidence.

- Add exact, structured small-area reproduction sequences covering model
  conditions, uploaded candidates, calibration settings, optional fitted
  weights, and optional map creation; execute generated and uploaded-candidate
  recipes in parity tests.
- Embed versioned `synthpopcan-assurance-v1` evidence in every terminal durable
  run, including lifecycle-safe success status, normalized requests, model and
  file checksums, row counts, diagnostics, warnings, limitations, and
  independently recomputed tamper and linkage checks.
- Preserve permanent release evidence: full coverage and correctness reports,
  installed-wheel smoke output, build inputs, SHA-256 manifests tied to the
  exact tag and commit, GitHub build-provenance attestations, and attachment to
  the matching GitHub Release.
- Refresh the research notes and public documentation for the released durable
  Python runtime, explicit 2016/2021 Census support, current 33-entry model
  catalogue, and national 2021 CSD boundaries.
- Reset the forward roadmap against the `0.6.2` codebase: reserve `0.6.3` for
  exact reproduction and durable release evidence; define `0.7.x` as a
  reusable external-data enrichment framework demonstrated by Can-FED v2 and
  ODEF v3; rank later health, education, built, social, and environmental
  candidates; and defer simulator-specific work until after a neutral `0.8.0`
  exchange bundle.
- Prune completed, duplicated, speculative, and obsolete implementation-plan
  work; make national DA synthesis, individual source adapters,
  catalogue-wide source browsing, optional spatial formats, and multiple
  simulator adapters explicitly gated rather than promised.
- Correct stale browser-numerics evidence links and narrow small-area
  reproduction claims to the options the current command actually records.
- Add a bounded bilingual case-study, preservation, FAIR4RS, governance,
  community-introduction, and JOSS-maturation track to the research-software
  stewardship roadmap.
- Record a speculative independent refresh path for aging Statistics Canada
  LODE facility inventories; assess the public CSBP-CPSE source registries,
  OpenTabulate descriptors, workflows, and ontologies as prior art; and frame
  OpenStreetMap and Overture as separately licensed corroboration, candidate,
  building, address, and network sources rather than automatic authority.

## 0.6.2 - 2026-07-20

Citation, licensing, and archival release.

- Carry the Statistics Canada Open Licence attribution notice with every
  Census-derived model package. Public use microdata files are "Information"
  under that licence, which permits distributing derived "Value-added Products"
  provided its prescribed notice travels with them. Each package's `provenance`
  now states the exact product, catalogue number, and Census reference year, and adds
  the required no-endorsement statement.
- Add a `source_licence` field to the model catalogue, shown as a new
  "Source licence" row by `synthpopcan models show`.
- Include `provenance` and `source_licence` in a package payload's
  `catalogue_metadata`, so generated populations and manifests inherit the
  attribution rather than leaving it behind in the catalogue listing.
- Reword prepared-model descriptions from "the local 2016 hierarchical PUMF" to
  "the 2016 Census hierarchical PUMF"; "local" described the training machine
  and meant nothing to a reader.
- Add `.zenodo.json` so archived releases carry explicit metadata. Note that
  Zenodo ignores `CITATION.cff` whenever this file is present; `CITATION.cff`
  still drives GitHub's citation widget.
- Sync `CITATION.cff` to the released version and guard it, along with
  `.zenodo.json`, against drift from the package version and changelog date.
- Add `scripts/build_zenodo_depositions.py` and
  `scripts/deposit_zenodo_records.py` to generate and deposit archival records
  for the prepared model catalogue, with full provenance, both checksums, and
  links to the software record and upstream microdata file.
- Correct the IPF diagram in the documentation. The fitted weights shown did
  not match what `fit_ipf` produces for the illustrated seed, and the caption
  claimed integerization preserves margin totals exactly, which holds for that
  example but is not guaranteed.
- Document source licensing and attribution obligations in the data guide, and
  require a licence and attribution check before publishing a model package.

## 0.6.1 - 2026-07-18

- Add the versioned `synthpopcan-linked-population-v1` household/person artifact
  contract, shared descriptors across library, CLI, prepared-model, and
  small-area outputs, explicit geography inheritance, compatibility rules, and
  a golden schema fixture. Exercise representative 2016 and 2021 hierarchical
  Census inputs end to end against the shared contract.
- Reject malformed, cyclic, multiply rooted, or inconsistent serialized CART
  models; bound local-web generation to 250,000 households and 2,000,000
  people; and terminate isolated workers that exceed the six-hour run limit.
- Sequence browser uploads, preflights, catalogue changes, estimates, durable
  submissions, and result previews so stale asynchronous completions cannot
  overwrite newer drafts or selected runs.
- Expand failure and lifecycle coverage for linked schemas, durable workers,
  prepared-model packages, and public API adapters; make the local check script
  enforce the same 95% Python branch-coverage threshold as CI.
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
  atomic artifacts, and recorded CLI reproduction metadata. Exact executable
  parity for every small-area option remains follow-up correctness work.
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
