# SynthPopCan Plan

Status: release-phased roadmap\
Last updated: 2026-07-22\
Current release: `0.6.2`

## Current Focus

Start here, then open a linked implementation plan only when working in that
area. Completed release detail belongs in [CHANGELOG.md](CHANGELOG.md) and
completed implementation plans belong in [`plans/archive/`](plans/archive/).

| Horizon | Focus | Detail |
| --- | --- | --- |
| Released | `0.6.2` adds citation, licensing, and Zenodo archival metadata on top of the `0.6.1` linked schema and 2021 Census work. | [GitHub Release](https://github.com/dlq/synthpopcan/releases/tag/v0.6.2) |
| Correctness | Preserve the released assurance gate and extend public benchmarks, model audits, and durable evidence. | [Correctness plan](plans/2026-07-12-correctness-assurance.md) |
| Small-area geography | Prove a bounded province-scale DA workflow, structured geography selection, and authoritative relationship indexing. | [Small-area geography plan](plans/2026-07-22-small-area-geography.md) |
| Research-software stewardship | Keep releases citable, archived, reproducible, governed, and legible to scientific-software and digital-humanities communities. | [Stewardship and publication plan](plans/2026-07-19-research-software-stewardship.md) |
| `0.7.x` | Establish governed source metadata and enrichment, then add reviewed spatial, environmental, cohort, service, activity, and network layers. | [Ecosystem enrichment plan](plans/2026-07-15-ecosystem-enrichment.md) |
| `0.8.x` | Hand validated populations and enrichment layers to external simulation platforms through a simulator-neutral interchange contract. | [Simulation interoperability plan](plans/2026-07-15-simulation-interoperability.md) |

## Goal And Principles

Build a Python library, CLI, and local web application for Canadian synthetic
population generation through:

1. iterative proportional fitting from Statistics Canada controls; and
1. tree-based linked household/person generation followed, where needed, by
   small-area calibration.

Principles:

- Keep raw, restricted, large, and generated data out of git.
- Share Python workflow and domain layers across the API, CLI, and web app.
- Treat `synthpopcan serve` as a local guided workbench, not a hosted service.
- Use approachable language and defaults for humanities researchers while
  preserving machine-readable output and expert controls.
- Make public interfaces, documentation, and descriptive metadata bilingual in
  English and French as practicable, with stable language-neutral identifiers
  and explicit translation provenance.
- Preserve source, geography, variables, filters, model version, seeds, and
  validation metrics with generated output.
- Choose geography for the research question rather than treating one level as
  universal.
- Distinguish software correctness, statistical fitness, disclosure-risk
  checks, and human review.
- Treat the software, its methods, and generated research objects as citable
  scholarly outputs with persistent identifiers and reproducible provenance.

Research background belongs in [NOTES.md](NOTES.md). Every unfinished roadmap
item must appear here or be owned by a linked plan with a current status and
next action. The [plan index](plans/README.md) records active and archived plans.

## Current Product State

`0.6.2` provides a stable public package, CLI, Python API, and local web
workbench. It supports:

- seed/control IPF with diagnostics, compact weights, integerized records,
  reports, and validation;
- Statistics Canada WDS discovery, Census Profile preparation, 2016 and 2021
  microdata adapters, matching boundaries, and geographic relationship inputs;
- linked frequency/CART training, audit, packaging, fetching, generation, and
  validation;
- a 33-entry prepared-model registry covering a demo plus parallel 2016 and
  2021 packages for Canada, supported provinces, and five PUMF-coded CMAs;
- linked small-area calibration, joint person controls, scale estimation,
  residual reports, realization, and standalone maps; and
- durable local runs with bounded uploads and previews, progress, cancellation,
  recovery, provenance, downloadable artifacts, and exact CLI handoff.

The versioned linked household/person/geography schema and local runtime are
released. Preserve their regression gates and review any schema change
explicitly. Completed architecture and acceptance detail remains in the
[archived runtime plan](plans/archive/2026-07-10-local-web-application-runtime.md)
and [archived linked-schema plan](plans/archive/2026-07-18-linked-population-schema.md).

Territory and broader CMA model coverage, a verified DA workflow, stronger
public correctness evidence, bilingual metadata, enrichment, and external
simulation interchange remain active or future work.

## Release History

| Line | Outcome |
| --- | --- |
| `0.1.x` | Public package, CLI/API/web surfaces, IPF, Statistics Canada and microdata adapters, tree generation, documentation, and release automation. |
| `0.2.x` | Linked small-area MVP, Census Profile controls, NumPy/threaded calibration, maps, and catalogue expansion. |
| `0.3.x` | Joint person calibration, diagnostics, grouped household size, performance work, validation, and stable scenarios. |
| `0.4.0` | Model metadata and downloads, privacy presentation, safer WDS refinement, browser small-area preparation, and CLI handoff. |
| `0.5.0` | Consolidated CLI and Python API, linked-population directory contracts, stronger typing and provenance, and documentation cleanup. |
| `0.5.1` | Correctness-assurance suite and claims matrix, audited integrity fixes, hardened release gates, permanent evidence, and tag-constrained publishing. |
| `0.6.0` | Durable FastAPI/Uvicorn local runtime, shared workflows, controlled workspaces, isolated jobs, progress, cancellation, recovery, and bounded artifacts. |
| `0.6.1` | Stable linked-population schema, explicit 2021 Census support and model catalogue, bounded execution, and browser sequencing. |
| `0.6.2` | Statistics Canada attribution, citation and archival metadata, prepared-model DOIs, Zenodo tooling, and corrected IPF documentation. |

## Active Plans

### Correctness and model quality

The [correctness-assurance plan](plans/2026-07-12-correctness-assurance.md) owns
the post-`0.5.1` evidence backlog. Current priorities include:

- per-run assurance manifests and permanent release evidence;
- additional public reference workflows, including a bounded external Canadian
  synthetic-population comparison;
- explicit structural-zero and sampling-zero policy;
- multi-scale and rare-category validation;
- QISI and systematic-integerization comparison;
- linked-model support, privacy, and rare-combination audits; and
- external methods review and broader platform evidence.

Correctness claims remain scoped: passing tests does not establish statistical
fitness, disclosure safety, or substantive validity for a particular study.

### Small-area geography

The [small-area geography plan](plans/2026-07-22-small-area-geography.md) owns
the next geography work. Retain CT for tracted metropolitan analysis, ADA for
moderately local wall-to-wall coverage, and CSD for municipal or
municipal-equivalent questions. Add DA only where finer placement materially
supports the research question and the controls, runtime, suppression, map
size, and disclosure risks are acceptable.

The first DA proof is province-scale. National execution must be restartable by
province or territory and produce aggregate diagnostics rather than one
monolithic fit. Structured geography requests and an authoritative relationship
index should replace undocumented prefix knowledge in beginner workflows.

### Research-software stewardship

The [research-software stewardship plan](plans/2026-07-19-research-software-stewardship.md)
owns FAIR4RS review, software citation, archival identifiers, governance,
community engagement, research-object preservation, and eventual JOSS
readiness. Publication should follow independent scholarly use and durable
evidence rather than a calendar deadline.

## Future Releases

### `0.7.x`: Ecosystem enrichment

The [ecosystem enrichment plan](plans/2026-07-15-ecosystem-enrichment.md) owns
source contracts and optional layers added to a validated base population.

| Release | Outcome |
| --- | --- |
| `0.7.0` | Versioned source/enrichment contracts, bilingual metadata foundations, source inventory and discovery, Census metadata and recall-aware cache foundations, and reviewed fine-area placement. |
| `0.7.1` | Reviewed spatial and environmental layers, beginning with Can-FED and suitable public geography, service, transport, built-environment, and environmental sources. |
| `0.7.2` | Privacy-governed cohort attachment for approved sources using documented harmonization, weighting or matching, uncertainty, and representativeness checks. |
| `0.7.3` | Modular school, workplace, healthcare, food-access, transport, activity, contact-network, and reproducible scenario layers. |

Use [CanCensus](https://mountainmath.github.io/cancensus/) as a design reference
for metadata-first Census discovery, variable hierarchies, geography selection,
and cache management, not as a runtime dependency. Prefer authoritative
Statistics Canada products, checksums, official relationships, and no required
third-party account.

### `0.8.x`: Simulation interoperability

The [simulation interoperability plan](plans/2026-07-15-simulation-interoperability.md)
owns external handoff. SynthPopCan should produce validated, documented data;
downstream platforms should own simulation behaviour and outcomes.

| Release | Outcome |
| --- | --- |
| `0.8.0` | Simulator-neutral exchange contract, manifest, validation, provenance, uncertainty, and example bundle. |
| `0.8.1` | Initial table/Python adapters for selected ActivitySim, Starsim, Mesa, and GAMA workflows after fixture validation. |
| `0.8.2` | Transport adapters for MATSim and SUMO only after the necessary activities, locations, schedules, memberships, and networks exist. |

## Far Future

Optional compositional public-health simulation remains a research direction,
not a committed release. Activate it only for a concrete question where time,
behaviour, interaction, constraints, or feedback make static population and
accessibility analysis insufficient. It requires suitable evidence, an
implementation owner or partner, baseline and intervention scenarios,
calibration, external validation, sensitivity analysis, and explicit limits on
causal claims. Simulation validity remains outside core population-generation
correctness claims.

## Ongoing Tracks

| Track | Policy / next work |
| --- | --- |
| Data | Track code, documentation, public-safe metadata, and tiny fixtures; ignore raw or restricted data, large caches, real generated populations, and unpublished private-data models. |
| Testing | Prefer correctness evidence over defensive-branch coverage; keep default tests public and deterministic, with live Statistics Canada and full-data checks opt-in. |
| Documentation | Keep examples synchronized with tested CLI help and the public API; add contributor internals only when useful. |
| Bilingualism | Progressively provide English/French interfaces, documentation, data dictionaries, and metadata while preserving authoritative language and translation provenance. |
| Projection experiments | After province-scale DA validation, test future cross-sectional populations driven by official province/territory age-sex scenarios. Begin with a 2016-to-2021 backcast; distinguish projected values from attributes carried forward, treat ADA/DA allocation as modelled, and do not claim longitudinal people or household trajectories. |
| Releases | Align tags, PyPI, Read the Docs, release notes, checksums, model provenance, installed-wheel tests, Zenodo archiving, and durable evidence. |

## Open Decisions

- Dependency posture beyond the current pure Python, NumPy, and pandas runtime;
  SciPy CSR and Polars remain benchmark probes.
- User-facing defaults for CT, ADA, CSD, and DA after representative CSD and DA
  performance and correctness evidence exists.
- Integerization alternatives beyond deterministic systematic expansion after
  the planned QISI comparison.
- Boundary between automated model/privacy advice and required expert review.
