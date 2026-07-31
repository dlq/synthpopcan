# SynthPopCan Plan

Status: release-phased roadmap\
Last updated: 2026-07-31\
Current published release: `0.6.3`\
Release candidate: `0.7.0`

## Current Focus

Start here, then open a linked implementation plan only for the area being
worked on. Completed release detail belongs in [CHANGELOG.md](CHANGELOG.md);
completed implementation plans belong in [`plans/archive/`](plans/archive/).

| Order | Focus | Owner |
| --- | --- | --- |
| 1 | `0.7.0`: establish explicit geography identity and a reusable external-data enrichment framework, then prove both with a bounded 2021 DA workflow and synthetic fixtures while retaining 2016 compatibility evidence. | [Small-area geography](plans/2026-07-22-small-area-geography.md) and [external-data enrichment](plans/2026-07-15-ecosystem-enrichment.md) |
| 2 | `0.7.1`: use public general-use Can-FED v2 as the first reference implementation, preserving its August 2024 measures and 2021 DA geography. | [External-data enrichment](plans/2026-07-15-ecosystem-enrichment.md) |
| 3 | `0.7.2`: use ODEF v3 as the contrasting national facility/location reference implementation. | [External-data enrichment](plans/2026-07-15-ecosystem-enrichment.md) |
| 4 | `0.8.0`–`0.8.1`: publish a simulator-neutral exchange bundle, then validate one demand-backed target adapter. | [Simulation interoperability](plans/2026-07-15-simulation-interoperability.md) |
| Ongoing | Licensing, citation, preservation, FAIR4RS, community introduction, and JOSS maturation. | [Research-software stewardship](plans/2026-07-19-research-software-stewardship.md) |

## Goal And Boundaries

Build an early-stage Python library, CLI, and local web workbench for Canadian
synthetic population generation through:

1. iterative proportional fitting from Statistics Canada controls; and
1. tree-based linked household/person generation followed, where appropriate,
   by small-area calibration.

The project generates, validates, documents, enriches, and exports synthetic
populations. It does not currently implement population simulation, infer
causal effects, certify disclosure safety, or redistribute third-party private
data.

Principles:

- Keep raw, restricted, large, and generated data out of git.
- Share Python algorithms across the API, CLI, and local web app; consolidate
  orchestration where surface drift would prevent exact reproduction.
- Treat `synthpopcan serve` as a local guided workbench, not a hosted service.
- Use approachable language and defaults while preserving machine-readable
  output and expert controls.
- Add English/French descriptive metadata progressively, with stable
  language-neutral identifiers and explicit translation provenance.
- Preserve source, geography, variables, filters, model version, seeds,
  validation evidence, and artifact checksums.
- Build enrichment around reusable source, resource, layer, and validation
  contracts rather than around a fixed catalogue. Treat datasets currently
  represented under `data/private/sources`, public portal resources, and
  future sources as possible consumers of those contracts—not as separate or
  exhaustive categories.
- Treat Census vintage and geography level as part of an identifier's meaning;
  never join matching-looking codes across vintages implicitly.
- Distinguish software correctness, statistical fitness, disclosure-risk
  review, and substantive research validity.
- Add a dependency, standard, catalogue integration, or platform adapter only
  when a concrete use case justifies its maintenance cost.

Research background belongs in [NOTES.md](NOTES.md). Every unfinished roadmap
item must appear here or be owned by one linked active plan with a current next
action. The [plan index](plans/README.md) records active and archived plans.

## Current Product State

`0.6.3` is a published alpha release with a stable v1 linked-population
artifact contract. It provides:

- seed/control IPF with diagnostics, compact weights, integerized records,
  reports, and validation;
- Statistics Canada WDS discovery, Census Profile preparation, explicit 2016
  and 2021 microdata adapters, selected matching boundaries, and geographic
  relationship inputs;
- linked frequency/CART training, audit, packaging, fetching, generation, and
  validation;
- a 33-entry prepared-model registry containing a demo plus parallel 2016 and
  2021 packages for Canada, supported provinces, and five PUMF-coded CMAs;
- linked small-area calibration, joint person controls, scale estimation,
  residual reports, realization, and standalone maps; and
- durable local runs with bounded uploads and previews, progress, cancellation,
  recovery, exact structured reproduction recipes, and versioned assurance
  evidence with independently verifiable hashes, row counts, diagnostics, and
  linkage findings.

The released web, CLI, and library surfaces share Python domain algorithms.
IPF also shares structured workflow orchestration. Model and small-area CLI
orchestration still differs in places from the durable web workflow, so parity
tests execute the recorded fixed-seed recipes, including model conditions,
uploaded candidates, fitted weights, and optional map creation.

The development branch additionally publishes a separately versioned
`geodata-v1` catalogue of checksummed display-only boundaries and implements
verified runtime retrieval. Canonical Statistics Canada geometry remains the
analytical input. The branch also moves scikit-learn behind the optional
`model-build` extra: CART training needs it, while portable model reading,
generation, and conditional-frequency training do not.

The completed runtime and linked-schema implementation records are archived:

- [local web runtime](plans/archive/2026-07-10-local-web-application-runtime.md);
- [linked-population schema](plans/archive/2026-07-18-linked-population-schema.md).

## Release History

| Line | Outcome |
| --- | --- |
| `0.1.x` | Public package, CLI/API/web surfaces, IPF, Statistics Canada and microdata adapters, tree generation, documentation, and release automation. |
| `0.2.x` | Linked small-area MVP, Census Profile controls, NumPy/threaded calibration, maps, and catalogue expansion. |
| `0.3.x` | Joint person calibration, diagnostics, grouped household size, performance work, validation, and stable scenarios. |
| `0.4.0` | Model metadata and downloads, privacy presentation, safer WDS refinement, browser small-area preparation, and CLI handoff. |
| `0.5.0` | Consolidated CLI and Python API, linked-population directory contracts, stronger typing and provenance, and documentation cleanup. |
| `0.5.1` | Correctness suite and public claims-to-evidence matrix, integrity fixes, retained CI reports, and hardened trusted publishing. |
| `0.6.0` | Durable FastAPI/Uvicorn local runtime, controlled workspaces, isolated jobs, progress, cancellation, recovery, and bounded artifacts. |
| `0.6.1` | Stable linked-population schema, explicit 2021 Census support and model catalogue, bounded execution, and browser sequencing. |
| `0.6.2` | Statistics Canada attribution, citation and archival metadata, prepared-model DOIs, Zenodo tooling, and corrected IPF documentation. |
| `0.6.3` | Exact portable reproduction recipes, versioned per-run assurance, permanent checksummed release evidence, and distribution provenance attestations. |

## Sequenced Releases

### `0.7.0`: Geography and reusable external-data enrichment framework

Two prerequisites ship together because neither is useful for safe
geography-keyed enrichment alone:

- make `(census_vintage, geography_level, identifier_namespace, identifier)`
  explicit in requests, manifests, joins, and errors;
- prove one bounded Québec 2021 DA workflow with metropolitan and rural areas,
  matching controls, boundaries, authoritative relationships, resource
  estimates, validation, and map-size evidence, while retaining a compact 2016
  DA compatibility regression;
- add restartable national 2021 DA/ADA orchestration using level-specific
  official profile adapters, shared province/territory manifests, bounded
  batches, one-pass boundary partitioning, reusable evidence-checked
  condition-specific candidate pools, atomic/checkpointed resumable execution,
  bounded parallel workers, national aggregate evidence, and disk safeguards;
- add versioned source-resource and enrichment manifests that compose the
  existing source provenance, linked-population v1, and durable-run records;
- implement immutable, bounded, checksum-recorded resource retrieval and
  explicit source revisions;
- support reusable, source-independent enrichment layers and validators for
  geography-keyed attributes, point/service locations, and governed
  household/person relationships without mutating the base population;
- let a researcher import a conforming normalized layer without waiting for a
  project-maintained adapter for that source;
- record each integration's authority, licence and access class, temporal and
  geographic semantics, variables, linkage method, limitations, and
  redistribution status;
- support English/French labels and translation provenance in the metadata
  contract; and
- prove with synthetic fixtures that enrichment leaves the base population and
  its identifiers byte-for-byte unchanged.

This release does not include a monolithic national fit, an automatic claim
that the broad Canada PUMF model is fit for every provincial, territorial, or
small-area research question, 2021-to-2016 DA concordance,
arbitrary-polygon selection, a general CKAN browser, or an automatic
compatibility promise for every candidate source.

The separately validated full-field ADA/DA control-coverage audit and linked
person-control expansion remain a post-`0.7.0` correctness milestone. Until
that work is complete, every carried-through PUMF field that is not named in a
fitted local margin remains explicitly uncontrolled and must not be presented
as an ADA- or DA-local estimate.

Once the framework ships, another dataset may be integrated whenever a
research question, access and redistribution authority, geographic and
temporal fit, validation strategy, and maintenance case justify it. A source
need not appear in the current repository examples or wait for every planned
reference implementation.

### `0.7.1`: Can-FED v2 reference implementation

- Integrate the public general-use 1 km and 3 km Can-FED categorical measures
  as a normalized geography/environment layer.
- Preserve the August 2024 observation period, 2024 Business Register basis,
  and 2021 DA identifier namespace.
- Reject an unreviewed join to a 2016 DA population.
- Report duplicate keys, unknown fields, missing source/base DAs, the
  publisher-documented incomplete DA coverage, and all unmatched records.
- Keep detailed Research Data Centre measures out of the public integration.
- Describe the output as area-level historical food-environment context, not a
  current outlet inventory or person-level exposure.

### `0.7.2`: ODEF v3 facility reference implementation

Integrate Statistics Canada's national Open Database of Educational Facilities
v3 as the contrasting facility/point adapter. Preserve its 2024 collection
period, source identifiers, coordinates, facility type, authority, ISCED
level, official-language-minority status, and CSD/CMA lineage. Validate
duplicates, missingness, geocoding, coverage, and unmatched geographies.
Treat the result as a facility inventory, not evidence of capacity, catchment,
quality, eligibility, or accessibility.

Can-FED and ODEF demonstrate that the framework is reusable; they do not
define or limit its scope. The enrichment plan ranks PMD 2021, Québec
health-service geography, Can-ALE 2.0, CANUE, ODHF, Québec education layers,
and CanSET as later candidates. No `0.7.3` outcome is committed. Further
integrations may land in an appropriate maintenance or feature release when
they pass the same demand, authority, semantics, validation, and stewardship
gates.

### `0.8.0`: Simulator-neutral exchange

- Compose the existing linked-population and durable-run contracts into a
  self-describing bundle.
- Require CSV household/person tables plus JSON manifest, data dictionary,
  validation, reproduction, access classification, and per-file hashes.
- Preserve `synthetic_household_id` and `synthetic_person_id`; do not introduce
  competing generic identifiers.
- Include only optional geography or enrichment tables that actually exist.
- Keep the bundle readable and validatable without simulator dependencies.
- Treat Parquet, GeoParquet, GeoPackage, and RO-Crate as later optional mappings
  until semantic types, dependency costs, and round trips are demonstrated.

### `0.8.1`: One target adapter pilot

Select one external target only when there is a real user or reference model,
a pinned supported version, an official input contract, and a maintainable
import smoke test. The adapter must distinguish a population contribution from
a runnable simulation and list every external network, land-use, schedule,
behaviour, coefficient, or model input still required.

ActivitySim, Starsim, Mesa, GAMA, MATSim, SUMO, Vivarium, FRED, and AnyLogic
remain researched candidates, not simultaneous commitments. Transport-plan
adapters remain unversioned future work until activities, locations, schedules,
modes, and network/link mappings are justified by a concrete project.

## Ongoing Assurance And Stewardship

The correctness plan owns exact reproduction, a versioned assurance payload,
zero-cell policy, multi-scale and rare-category validation, model content
audits, public external comparisons, QISI evaluation, cross-platform evidence,
and external review. Territory and broader-CMA models are feasibility
candidates, not promised coverage: each must pass support, rare-category,
privacy, provenance, and reproducible-build gates.

Prepared-geodata releases need a deterministic catalogue audit before each
publication: verify the expected year/geography/PRUID identity coverage,
unique asset names, immutable release-tag URLs, and both checksum fields. A
separate bounded remote retrieval check may exercise a representative asset,
but routine CI must not redownload the complete boundary release.

The stewardship plan owns the model-licensing decision, full CFF validation,
Software Heritage capture, a dated FAIR4RS baseline, lightweight governance and
maintenance documentation, a tested bilingual 2021 case study, targeted
community introduction, and JOSS maturation.

JOSS submission is not currently ready. The repository became public in June
2026; current JOSS screening requires more than six months of public,
iterative development plus demonstrated research use and other readiness
evidence. January 2027 is only the earliest plausible review point, not a
deadline or promise.

### Strict typing migration

The package is clean under Pyright's `standard` mode and has complete public
type information. An initial 2026-07-31 strict-mode audit reported 986
diagnostics; 923 (93.6%) were cascading unknown member, variable, or argument
types, while 16 source files were already strict-clean. The first ratchet made
those 16 files strict, fixed every argument-type, general-type, and deprecated
annotation diagnostic, and reduced the remaining strict total to 908. Treat
the rest as an incremental quality ratchet rather than a release-blocking
all-at-once conversion.

Next actions, in order:

- keep `standard` mode blocking for the complete package and retain the 16
  clean files in Pyright's per-path `strict` list so they cannot regress;
- type dynamic-data boundaries shared by the assurance/preflight reports, CLI
  output, national execution manifests, run artifacts, and GeoJSON/map paths;
- use Pydantic for untrusted HTTP, persisted JSON, and worker-message
  boundaries, but prefer `TypedDict`, dataclasses, and protocols for trusted
  internal structures, and retain validated models instead of immediately
  converting them back to `dict[str, Any]`;
- concentrate root fixes in `webapi.py`, `map_render.py`, `cli_output.py`,
  `national_execution.py`, and `assurance.py`, rather than suppressing their
  downstream findings with blanket `Any` or `cast()` calls;
- isolate pandas, pyshp, and scikit-learn behind typed adapters or reviewed
  stubs, and document narrow exceptions such as decorator-registered FastAPI
  handlers that strict mode otherwise reports as unused; and
- expand the strict path list whenever a module reaches zero diagnostics, with
  CI continuing to reject regressions in both the standard package check and
  the strict-clean subset.

The migration is complete when the source package passes strict mode with only
explicitly documented third-party or framework exceptions and without using
blanket `Any`, unchecked casts, or Pydantic models solely to silence the type
checker.

## Explicitly Deferred Or Conditional

- Hosted, authenticated, multi-user, or distributed web operation.
- Redistribution or implied availability of third-party private data.
- Blanket adapters for repository examples, open-data portals, or any other
  catalogue without a justified research use and maintainable contract.
- Automatic 2016/2021 geography concordance.
- A monolithic national DA fit.
- Generic activity, schedule, contact-network, or intervention generation
  without an evidence-backed research model.
- Multiple simulator adapters before one target pilot demonstrates demand.
- Population simulation inside SynthPopCan.
- Claims that test passage proves substantive validity, disclosure safety, or
  causal validity.

## Research Queue, Not Release Commitments

- Test official province/territory projection scenarios only after the DA
  foundation is validated. Begin with a 2016-to-2021 backcast; distinguish
  projected values from carried-forward attributes and never claim
  longitudinal people or household trajectories.
- Evaluate arbitrary-polygon geography selection only after authoritative
  coded relationships and vintage checks are reliable.
- Investigate cross-vintage boundary harmonization as a separately reviewed
  method.
- Consider household-, person-, or cohort-level attachment—including
  restricted sources—only with current written data-use, ethics, purpose,
  methods, privacy, and redistribution authority.
- Periodically audit the full Statistics Canada LODE catalogue and investigate
  whether a separately governed, reproducible refresh of aging national
  facility inventories—starting with healthcare—would merit an independent
  open-data product. Use the CSBP-CPSE source registries, OpenTabulate
  descriptors, and processing repositories as revalidated prior art, not as
  current source truth or automatic dependencies.
- For any facility refresh, test authoritative jurisdictional records against
  OpenStreetMap and Overture Maps as separately licensed corroboration,
  candidate-discovery, building, address, and transport-network layers. Begin
  with a bounded Québec metropolitan/rural comparison, preserve conflicts and
  source-level lineage, and never treat an open-map feature as proof of
  capacity, service availability, or official status.

## Open Decisions

- Exact schema relationship between the current model-specific
  `synthpopcan-source-provenance-v1` record and the general `0.7.0` source
  profile.
- Which candidate after ODEF has the strongest concrete research demand and
  maintenance case.
- Supported operating-system claim and the minimum Windows/macOS evidence
  needed to make it.
- Whether optional columnar or spatial export merits new dependencies after the
  CSV/JSON interchange contract is proven.
- Boundary between automated model/privacy findings and required human review.
