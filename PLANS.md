# SynthPopCan Plan

Status: release-phased roadmap\
Last updated: 2026-07-14\
Current release: `0.5.0`

## Current Focus

Start here. Open a linked implementation plan only when working on that area.

| Horizon | Focus | Detail |
| --- | --- | --- |
| Next patch | Stabilize the new CLI, API, and linked-artifact contracts in `0.5.1`. | [CHANGELOG.md](CHANGELOG.md) |
| Correctness | Add Python/NumPy IPF differential tests, independent small-area reconciliation, then integerization properties. | [Correctness plan](plans/2026-07-12-correctness-assurance.md) |
| Next minor | Build the durable backend IPF workbench for `0.6.0`. | [Local runtime plan](plans/2026-07-10-local-web-application-runtime.md) |
| Later `0.6.x` | Move prepared-model generation and small-area synthesis into the same durable run model. | [Plan index](plans/README.md) |

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

## Current Product State

`0.5.0` consolidates the CLI around `models`, `geo`, and `validate`, establishes
linked-population artifact directories as the workflow contract, and provides a
smaller typed beginner Python API. It also adds independent candidate-subsample
seeds, stronger provenance, expanded small-area documentation, and planning
cleanup.

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

The current app still uses the standard-library loopback server and browser-side
IPF/tree generation. Durable runs, progress, cancellation, restart recovery, and
incremental artifact streaming are not implemented.

## Release History

| Line | Outcome |
| --- | --- |
| `0.1.x` | Public package, CLI/API/web surfaces, IPF, StatCan and microdata adapters, tree generation, docs, and release automation. |
| `0.2.x` | Linked small-area MVP, Census Profile controls, NumPy/threaded calibration, maps, and catalogue expansion. |
| `0.3.x` | Joint person calibration, diagnostics, grouped household size, performance/memory work, validation, and stable scenarios. |
| `0.4.0` | Model metadata/downloads, privacy presentation, safer WDS refinement, browser small-area preparation, and CLI handoff. |
| `0.5.0` | Consolidated CLI and Python API, linked-population directory contracts, stronger typing and provenance, and documentation cleanup. |

The original public baseline is achieved: users can install SynthPopCan, prepare
StatCan inputs, generate and validate IPF or linked-model output, inspect
provenance, and reproduce work through the CLI.

## 0.5.x: Interface Stabilization And Correctness Hardening

Status: active follow-up line.

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
- Implement the independent-oracle, invariant, differential, metamorphic,
  statistical, linked-integrity, and reconciliation work in the
  [correctness plan](plans/2026-07-12-correctness-assurance.md).

## 0.6.x: Local Web Application Runtime

Status: planned. See the
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

| Release | Outcome |
| --- | --- |
| `0.6.0` | FastAPI/Uvicorn runtime, controlled workspace, durable runs, backend IPF, Runs workbench, and removal of browser IPF. |
| `0.6.1` | Backend prepared-model generation, incremental artifacts, scale/disk preflight, and removal of browser tree generation. |
| `0.6.2` | Guided small-area jobs, validation/maps, prominent non-convergence, calibration-mode guidance, chunked realization, and cleanup. |

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

## 0.7.x And Later

Deferred until synthesis and the local runtime are stable: environmental and
public-service enrichment, reviewed fine-area placement, scenario simulation,
and richer reproducible public-source mappings.

## Ongoing Tracks

| Track | Policy / next work |
| --- | --- |
| Data | Track code, docs, public-safe metadata, and tiny fixtures; ignore raw/restricted data, large caches, real generated populations, and unpublished private-data models. |
| Testing | Prefer correctness evidence over defensive-branch coverage; keep default tests public and deterministic, with live StatCan/full-data checks opt-in. |
| Documentation | Document `models remove`; keep workflow examples synchronized with tested CLI help; add contributor internals only when useful. |
| Releases | Align tags, PyPI, Read the Docs, release notes, checksums, model provenance, installed-wheel smoke tests, and model-fetch checks. |

## Open Decisions

- Dependency posture beyond the current pure Python, NumPy, and pandas runtime;
  SciPy CSR and Polars remain benchmark probes.
- Default small-area geography levels beyond current 2016 CT/ADA workflows.
- First stable public linked household/person/geography output schema.
- Integerization alternatives beyond deterministic systematic expansion.
- Boundary between automated model/privacy advice and required expert review.
