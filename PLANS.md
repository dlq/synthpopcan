# SynthPopCan Plan

Status: release-phased roadmap\
Last updated: 2026-07-17\
Current release: `0.6.0`

## Current Focus

Start here. Open a linked implementation plan only when working on that area.

| Horizon | Focus | Detail |
| --- | --- | --- |
| Released | `0.6.0` completes the durable local-runtime redesign while retaining the `0.5.1` correctness-assurance gate. | [GitHub Release](https://github.com/dlq/synthpopcan/releases/tag/v0.6.0) |
| Correctness | Preserve and extend the correctness-assurance gate in priority order. | [Correctness plan](plans/2026-07-12-correctness-assurance.md) |
| Next patch | Stabilize the public linked household/person/geography schema in `0.6.1` after all workflows use the durable runtime. | [Local runtime plan](plans/2026-07-10-local-web-application-runtime.md) |
| Later `0.7.x`–`0.8.x` | Add governed enrichment layers, then hand validated generated data to external simulation platforms without implementing population simulation in SynthPopCan. | [Plan index](plans/README.md) |
| Far future, after `0.8.x` | Research optional, compositional public-health simulation only after the population, enrichment, and interchange contracts are stable; do not commit to one simulation platform. | [Far-future direction](#far-future-compositional-public-health-simulation) |

## Goal And Principles

Build a Python library, CLI, and local web application for Canadian synthetic
population generation through:

1. iterative proportional fitting from StatCan controls; and
1. tree-based linked household/person generation followed, where needed, by
   small-area calibration.

Principles:

- Keep raw, restricted, large, and generated data out of git.
- Share Python workflow and domain layers across the API, CLI, and web app.
- Treat `synthpopcan serve` as a local guided workbench, not a hosted frontend.
- Keep standalone artifacts such as `geo map` independent from the app runtime.
- Use approachable defaults and language for humanities users while preserving
  machine-readable output.
- Preserve source, geography, variables, filters, model version, seeds, and
  validation metrics with generated output.
- Distinguish software correctness, statistical fitness, disclosure-risk checks,
  and human review.

Completed release notes belong in [CHANGELOG.md](CHANGELOG.md), research
background in [NOTES.md](NOTES.md), and detailed tasks in [`plans/`](plans/).
Every unfinished roadmap item must either appear directly in this file or be
owned by a linked implementation plan with a current status and next action.

## Current Product State

`0.5.1` adds the current architecture's correctness-assurance gate: independent
and differential numerical checks, generated invariants, statistical model
oracles, linked-record integrity checks, small-area artifact reconciliation,
known-truth reference workflows, permanent release evidence, and a
tag-constrained trusted-publishing path. It retains the consolidated CLI,
smaller typed beginner API, linked-population artifact contract, independent
candidate-subsample seeds, and stronger provenance introduced in `0.5.0`.

Implemented capabilities include:

- seed/control IPF with diagnostics, compact weights, expanded records, reports,
  and validation;
- StatCan WDS discovery and reproducible input preparation plus 2016 Census
  hierarchical microdata adapters;
- linked frequency/CART training, audit, packaging, fetching, generation, and
  validation;
- a 17-entry prepared-model registry covering Canada, all provinces, five major
  CMAs, and a demo; territories and broader CMA coverage remain open;
- `geo calibrate`, `geo synthesize`, joint person controls,
  scale estimation, residual reports, linked realization, and maps;
- a packaged local web app for guided IPF, prepared models, WDS preparation,
  small-area preflight, downloads, and exact CLI handoff.

The released `0.6.0` app uses FastAPI/Uvicorn, a controlled workspace,
durable manifests and events, isolated Python jobs, progress, cancellation,
restart recovery, bounded previews, incremental artifact publication, and
backend IPF, prepared-model, and guided small-area workflows. Existing linked
candidates can enter the same small-area path, and model catalogue installation
and removal stay bounded in the browser. Browser IPF and tree generation are
removed. The implementation, cleanup, documentation, clean-wheel smoke, full
correctness/coverage gate, browser scenarios, and bounded scale smokes are
complete.

## Release History

| Line | Outcome |
| --- | --- |
| `0.1.x` | Public package, CLI/API/web surfaces, IPF, StatCan and microdata adapters, tree generation, docs, and release automation. |
| `0.2.x` | Linked small-area MVP, Census Profile controls, NumPy/threaded calibration, maps, and catalogue expansion. |
| `0.3.x` | Joint person calibration, diagnostics, grouped household size, performance/memory work, validation, and stable scenarios. |
| `0.4.0` | Model metadata/downloads, privacy presentation, safer WDS refinement, browser small-area preparation, and CLI handoff. |
| `0.5.0` | Consolidated CLI and Python API, linked-population directory contracts, stronger typing and provenance, and documentation cleanup. |
| `0.5.1` | Correctness-assurance suite and public claims matrix, audited integrity fixes, hardened release gates, permanent release evidence, and tag-constrained trusted publishing. |

The original public baseline is achieved: users can install SynthPopCan, prepare
StatCan inputs, generate and validate IPF or linked-model output, inspect
provenance, and reproduce work through the CLI.

## 0.5.x: Interface Stabilization And Correctness Hardening

Status: complete; preserve its regression and release gates while `0.6.x`
changes the runtime architecture.

### 0.5.0 release

- independent `--random-seed` and `--subsample-seed` controls;
- report provenance for input and selected household/person counts;
- composable beginner API results and separate flat and linked output writers;
- an explicit stable top-level API contract and inline typing marker;
- clearer small-area CLI, API, notebook, and web-app documentation;
- a coherent CLI command tree with one linked-population directory contract;
- correctness roadmap and planning rationalization.

For follow-up patches, run the release gate, installed-wheel and model-fetch
smoke tests, public docs build, and the correctness checks available at that
point.

### 0.5.1 release (completed 2026-07-15)

The correctness implementation, selected release-safety P2 tranche, and public
release are complete:

- [x] Commit and push the complete correctness-assurance change set.
- [x] Set the package version to `0.5.1`, refresh locked metadata, and finalize
  the changelog and release notes for the versioned commit.
- [x] Run the normal, extended-correctness, documentation, browser, model-fetch,
  build, and isolated-wheel gates from the versioned commit; retain the commit
  SHA and machine-readable reports.
- [x] Create and push the annotated `v0.5.1` tag, then create the
  GitHub Release with scoped correctness claims, known limitations, checksums,
  and links to the tested commit and evidence.
- [x] Run the tag-constrained trusted-publishing workflow and verify `0.5.1` on
  PyPI, the GitHub Release, installation from PyPI, and rendered documentation.

Release evidence: commit `71b326b9ef97fd674546b68b3f1d80dac96cff2f`,
annotated tag `v0.5.1`, [GitHub Release](https://github.com/dlq/synthpopcan/releases/tag/v0.5.1),
[trusted-publishing run](https://github.com/dlq/synthpopcan/actions/runs/29438201657),
and [PyPI 0.5.1](https://pypi.org/project/synthpopcan/0.5.1/). The GitHub
distribution assets are byte-for-byte identical to the files published on
PyPI; the Release also permanently carries their checksums and the retained
correctness JUnit report.

### 0.5.1 code-audit backlog

The 2026-07-14 audit found no P0 issue. Its P1 items and selected release-safety
P2 items are complete with focused regression tests. The three remaining P2
items below are explicitly owned by the `0.6.x` runtime migration.

`0.5.1` is also the correctness-assurance release for every algorithm and
artifact path present in the current architecture. Complete all six workstreams
in the [correctness plan](plans/2026-07-12-correctness-assurance.md), run their
deterministic checks on every pull request, and run the larger reference and
distribution tiers before release. Do not defer a current-code correctness
check merely because the affected workflow will later move behind the `0.6.x`
runtime. Tests for genuinely new `0.6.x` behavior remain acceptance gates for
the release that introduces that behavior.

#### Correctness, data integrity, and privacy

- [x] **P1 — Prevent in-place candidate data loss.** Reject
  `--candidates-out` paths that alias `--candidates`, or recode atomically
  through a distinct temporary file before replacement.
- [x] **P1 — Give scalar and NumPy IPF identical sparse-control semantics.** Do
  not turn represented but omitted target cells into explicit zero targets;
  add sparse-margin differential tests.
- [x] **P1 — Validate every reused NumPy IPF index against ordered margin
  dimensions and categories.** Do not reuse the first geography's encoding for
  an incompatible later geography, and independently reconcile reported
  residuals.
- [x] **P1 — Replace browser largest-remainder expansion with the Python
  systematic integerizer.** Cover highly fractional weights, row-order bias,
  aggregate preservation, and Python/browser parity.
- [x] **P1 — Enforce finite, non-negative numeric invariants at every boundary.**
  Reject Python control counts and weights containing `NaN` or infinity,
  browser negative control targets, and negative/non-finite frequency-model
  weights; ensure fit and validation can never swallow a non-finite residual as
  zero error.
- [x] **P1 — Detect category collisions after WDS mapping.** When distinct
  source labels map to one canonical category, aggregate them deliberately or
  reject the mapping instead of silently keeping the last count.
- [x] **P1 — Enforce linked-person integrity whenever person rows are present.**
  Reject orphan people and duplicate household/person identifiers before merge
  realization so joins cannot silently drop or multiply people.
- [x] **P1 — Reserve generated identifier columns.** Prevent seed or model
  fields from overwriting `synthetic_id`, `synthetic_household_id`, or
  `synthetic_person_id`, and make linked validation check identifier uniqueness.
- [x] **P1 — Base disclosure support on contributing source-row counts.** Do
  not let survey-weight totals satisfy frequency-model or geography minimum
  support thresholds; keep weighted totals as separate statistical metadata.
- [x] **P1 — Preserve complete seed profiles in browser compact-weight output.**
  Retain all seed dimensions and add a collision-safe fitted-weight column so
  the artifact is self-contained for analysis, validation, and expansion.
- [x] **P2 — Preserve the exact requested total when scaling controls.** Use a
  globally reconciled integer allocation rather than independent rounding by
  geography/category.
- [x] **P2 — Require every declared normalized-control dimension to exist in
  the CSV header.** Do not silently create an empty-string category or an empty
  `ControlTable.dimensions` result.
- [x] **P2 — Apply the same model-package schema validation to mappings and
  files.** Reject unsupported schema versions before generation regardless of
  how the package entered the API.
- [x] **P2 — Make browser and CLI prepared-model reproduction claims exact.**
  Share backend generation or a bit-identical RNG and seed schedule; until then,
  do not claim that the same seed reproduces the same population.
- [x] **P2 — Align browser WDS snapshot selection with Python.** Exclude
  `REF_DATE` from suggested dimensions and consistently select the latest
  reference period.

#### Web security and resource bounds

- [x] **P1 — Keep supported large models out of whole-payload browser paths.**
  Registered packages above the 32 MiB uncompressed browser threshold are
  disabled in the web catalogue and rejected by the local API with an exact
  CLI handoff. Backend generation remains the `0.6.1` replacement path.
- [x] **P1 — Bound WDS and ZIP processing before allocation.** Cap request
  bodies, archive entries, compressed and aggregate uncompressed sizes, remote
  response bytes, CSV rows, and concurrent work; inflate only the selected
  member rather than retaining every archive entry.
- [ ] **P2 / `0.6.1` — Validate uploaded model structure and bound execution.**
  Reject cyclic or invalid CART graphs, cap household/person output, and add
  worker cancellation, timeout, and stale-job handling in the backend model-run
  path before removing browser generation.
- [ ] **P2 / `0.6.0` — Harden or replace the current local server.** Reject
  non-loopback hosts, validate `Host` and `Origin`, protect state-changing
  requests, require appropriate content types, cap `Content-Length`, and carry
  these requirements into the FastAPI replacement. Any network mode still
  requires a separate security design.
- [x] **P2 — Escape standalone map content for its HTML and JavaScript
  contexts.** HTML-escape titles, safely encode inline JSON including
  `</script>`, and build tooltip content with text nodes rather than
  `innerHTML`.
- [x] **P2 — Resolve paths before applying private-data safeguards.** Cover
  symlinks and `..` traversal so a path into `data/private` cannot bypass the
  sampling/release guard.
- [x] **P2 — Return structured 4xx errors for all invalid JSON shapes.** A
  valid non-object JSON request must not escape as `AttributeError` and close
  the connection.

#### Filesystem, network, maps, and releases

- [x] **P2 — Serialize or lock model-cache fetches.** Use request-unique
  temporary files plus atomic replacement so concurrent threads/processes do
  not truncate, unlink, or replace one another's downloads.
- [x] **P2 — Make StatCan downloads bounded and atomic.** Add network timeouts,
  stream to a temporary file, verify completion, and preserve a valid cached
  file when a refresh fails partway through.
- [ ] **P2 / `0.6.0`–`0.6.1` — Sequence asynchronous browser operations.**
  Snapshot inputs when a job starts, abort or ignore stale model/WDS/estimate
  completions, and build CLI handoff commands from the completed durable run
  rather than the current mutable form.
- [x] **P2 — Fail map generation when no population geography matches the
  boundaries.** Do not emit HTML with empty variables or invalid infinite
  bounds.
- [x] **P2 — Preserve shapefile polygon topology.** Classify exterior and
  interior rings correctly so holes are not rendered as filled polygons.
- [x] **P2 — Constrain PyPI publishing to tested release tags.** A manual
  workflow dispatch must verify tag/version agreement and pass the release gate
  before trusted publishing.

### Remaining work

- Complete reviewed catalogue coverage for territories and selected large CMAs,
  using a repeatable release workflow rather than ad hoc registry entries.
- Add model-design advice for full, reduced, or minimal profiles by geography,
  sparsity, size, and privacy risk.
- Derive raw-row and identifier findings from model contents instead of trusting
  serializer booleans.
- Audit linked models jointly for rare cross-level combinations and reconcile
  training/audit support thresholds with category-coarsening guidance.
- Keep automated disclosure checks explicitly subordinate to human review.
- Add a machine-readable assurance manifest to every generated run, containing
  version, input checksums, seeds, algorithm settings, convergence, requested
  and realized residuals, structural-zero findings, and linkage findings.
- Add Hypothesis-based shrinking for generated numerical cases, frozen
  cross-version output fixtures, and mutation testing for the numerical and
  reconciliation kernels.
- Expand independent public reference workflows beyond the initial Yukon WDS
  fixture, including multi-dimensional controls and a linked household/person
  example reviewed separately from the implementation.
- Add macOS and Windows compatibility evidence for supported workflows, while
  retaining Linux/Python 3.11 and 3.12 as required pull-request checks.
- Permanently attach correctness reports, checksums, dependency provenance, and
  build attestations to GitHub Releases instead of relying only on expiring
  Actions artifacts.
- Seek an external methods/code review of the algorithms, fixtures, tolerances,
  assurance claims, and stated limitations; record review scope and responses
  in a durable public artifact.

## 0.6.x: Local Web Application Runtime

Status: in progress; Stages 0–5 complete. See the
[staged implementation plan](plans/2026-07-10-local-web-application-runtime.md).

Architecture decisions:

- Python performs synthesis, validation, and file writing; the browser guides
  setup, jobs, diagnostics, and artifacts.
- CLI and HTTP adapters call shared application services; HTTP never shells out
  to Click or parses terminal text.
- Remove browser synthesis only after backend parity and replacement scenarios.
- Keep packaged HTML/CSS/ES modules unless measured complexity justifies a
  framework.
- Remain loopback-only with controlled workspace access; network serving needs a
  separate security design.
- Keep the `0.6.0` run manifest extensible for linked artifacts, but defer the
  stable public household/person/geography output contract to `0.6.1`, after
  backend prepared-model and small-area workflows own those artifacts.

| Release | Outcome |
| --- | --- |
| `0.6.0` | Complete the local-runtime redesign: controlled workspace, durable backend IPF/prepared-model/small-area runs, bounded artifacts, selected utilities, removal of browser synthesis, cleanup, and release proof. |
| `0.6.1` | Stabilize and version the public linked household/person/geography schema, with explicit compatibility and migration rules. |

Completion criteria:

- CLI and HTTP share services for IPF, prepared-model, and small-area workflows.
- Runs can be launched, monitored, cancelled, revisited, and reproduced without
  loading complete populations into browser memory.
- Run directories preserve parameters, provenance, diagnostics, artifacts, and
  executable reproduction commands.
- The standard-library server and browser synthesis implementations are removed
  after acceptance tests pass.
- Local security, lifecycle, interruption, failure, and download scenarios have
  deterministic automated coverage.

## 0.7.x: Ecosystem Enrichment

Status: planned after the stable local runtime and linked-population schema. See
the [ecosystem enrichment plan](plans/2026-07-15-ecosystem-enrichment.md).

| Release | Outcome |
| --- | --- |
| `0.7.0` | Versioned enrichment/source contract, complete private-source inventory, public-catalogue discovery, provenance/licensing controls, and reviewed fine-area placement foundation. |
| `0.7.1` | Spatial and environmental layers, beginning with Can-FED as a first-class public food-environment source, profiled TOPO, MoNNET, and CANUE, plus suitable authoritative public geography, service, transport, built-environment, and environmental sources. |
| `0.7.2` | Privacy-governed cohort attachment for MAVAN, CPTP, and other approved sources using documented harmonization, weighting or statistical matching, uncertainty, and representativeness checks. |
| `0.7.3` | Modular school, workplace, healthcare, food-access, road/transport, contact-network, and reproducible scenario layers. |

Public-source discovery begins with the
[Open Government Canada open-data catalogue](https://search.open.canada.ca/opendata/)
and the [Données Québec CKAN catalogue](https://www.donneesquebec.ca/), while
remaining open to relevant datasets from authoritative Canadian federal,
provincial, territorial, Indigenous-government, municipal, public-health,
education, and other public-agency catalogues. Every public dataset is a
candidate for evaluation rather than automatic inclusion: verify relevance,
licensing and attribution, quality, geographic and temporal alignment,
versioning, and reproducible access first. Selected public data are fetched or
queried from authoritative sources with recorded metadata, licence, retrieval
time, version, and checksum; they are not indiscriminately mirrored or bundled
with the package.

Restricted or access-controlled source data remain under `data/private` and
never enter git, logs, fixtures, documentation, or release artifacts. Their
local presence creates no commitment to use, redistribute, provide, or publish
adapters or derived artifacts for them; dataset-specific work requires separate
authority and should ordinarily run only against data supplied independently by
an authorized user.

## 0.8.x: Simulation Interoperability And Data Handoff

Status: planned after the stable linked-population schema; individual adapters
also depend on the location, activity, and network layers they require. See the
[simulation interoperability plan](plans/2026-07-15-simulation-interoperability.md).

SynthPopCan will construct, validate, document, and export synthetic population
data for external models. It will not become a population-simulation engine in
this track. A versioned simulator-neutral interchange bundle is the boundary;
target-specific adapters translate that bundle and reject exports whose required
activities, locations, schedules, networks, or model configuration are absent.

| Release | Outcome |
| --- | --- |
| `0.8.0` | Versioned interchange bundle with stable identifiers, Parquet/CSV/GIS tables, manifest, data dictionary, provenance, checksums, and validation evidence. |
| `0.8.1` | Initial table/Python-oriented adapters and examples for ActivitySim, Starsim, Mesa, and GAMA, selected only after contract research and fixture validation. |
| `0.8.2` | Transport-demand adapters for MATSim and SUMO after `0.7.3` can supply the required activities, locations, times, memberships, and networks. |

FRED, Vivarium, AnyLogic, and other platforms remain researched candidate
targets rather than commitments. Promote them only when their supported custom
population contract is verified and real user demand justifies maintenance.

## Far Future: Compositional Public-Health Simulation

Status: deliberately deferred until after the `0.8.x` data-handoff work; no
release number or implementation platform is committed.

The broader SynthEco public-health direction may eventually evaluate changes
to food, healthcare, education, housing, transport, environmental exposure,
and other public infrastructure. This is a different and much larger problem
than generating a synthetic population or exporting it to an external model.
A runnable simulation also needs documented behavioural, institutional,
capacity, transition, outcome, and feedback rules, with calibration and
validation evidence appropriate to the jurisdiction and period.

Do not select a universal engine prematurely. Starsim and JUNE are important
specialist candidates for disease, health-state, contact, and epidemiological
work, but their disease orientation should not define the overall simulated
world. OpenM++ remains a technical reference for Canadian-style longitudinal
microsimulation rather than a platform commitment. GAMA or Mesa may support
spatial, institutional, or exploratory models, while transport, accessibility,
queueing, and health-transition components may remain separate tools connected
through versioned data contracts.

Before implementing dynamic simulation, prefer the least complicated method
that answers the research question. Many useful public-health analyses require
only a validated synthetic population plus facility, capacity, network, or
environmental layers and static counterfactual comparison. Introduce dynamic
simulation only when time, behaviour, interaction, constraints, or feedback
materially affect the answer.

If this track becomes justified, begin with research and small reference cases:

- define a platform-neutral, readable intervention manifest covering timing,
  targets, resource changes, eligibility, coverage, assumptions, outcomes, and
  provenance without pretending that YAML supplies causal behaviour;
- catalogue candidate Canadian and Quebec transition rules with jurisdiction,
  population, observation period, source, estimation method, uncertainty,
  access/licence restrictions, and validation status;
- separate population, environment, accessibility, service/capacity,
  transport, health-transition, disease/contact, and outcome components;
- compare specialist adapters or coupled tools against concrete public-health
  questions rather than ranking platforms in the abstract;
- require baseline and intervention scenarios, repeated stochastic runs,
  calibration targets, external validation, sensitivity analysis, and explicit
  limits on causal claims; and
- keep simulation behaviour and outcome validity outside SynthPopCan's core
  population-generation correctness claims.

Activation requires a concrete research question, suitable evidence for the
necessary rules, a maintainable implementation owner or partner, and proof
that static accessibility or counterfactual analysis is insufficient.

## Ongoing Tracks

| Track | Policy / next work |
| --- | --- |
| Data | Track code, docs, public-safe metadata, and tiny fixtures; ignore raw/restricted data, large caches, real generated populations, and unpublished private-data models. |
| Testing | Prefer correctness evidence over defensive-branch coverage; keep default tests public and deterministic, with live StatCan/full-data checks opt-in. |
| Documentation | Keep workflow examples synchronized with tested CLI help; add contributor internals only when useful. |
| Releases | Align tags, PyPI, Read the Docs, release notes, checksums, model provenance, installed-wheel smoke tests, and model-fetch checks; later add automatic Zenodo publication for versioned archival releases and DOI metadata. |

## Open Decisions

- Dependency posture beyond the current pure Python, NumPy, and pandas runtime;
  SciPy CSR and Polars remain benchmark probes.
- Default small-area geography levels beyond current 2016 CT/ADA workflows.
- Integerization alternatives beyond deterministic systematic expansion.
- Boundary between automated model/privacy advice and required expert review.
