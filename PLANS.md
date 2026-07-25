# SynthPopCan Plan

Status: release-phased roadmap\
Last updated: 2026-07-25\
Current release: `0.6.2`

## Current Focus

Start here, then open a linked implementation plan only for the area being
worked on. Completed release detail belongs in [CHANGELOG.md](CHANGELOG.md);
completed implementation plans belong in [`plans/archive/`](plans/archive/).

| Order | Focus | Owner |
| --- | --- | --- |
| 1 | `0.6.3`: correct small-area reproduction parity and make release evidence durable. | [Correctness assurance](plans/2026-07-12-correctness-assurance.md) |
| 2 | `0.7.0`: establish explicit geography identity, prove a bounded 2016 DA workflow, and add the minimum governed source/enrichment contracts needed for safe layers. | [Small-area geography](plans/2026-07-22-small-area-geography.md) and [ecosystem enrichment](plans/2026-07-15-ecosystem-enrichment.md) |
| 3 | `0.7.1`: integrate public general-use Can-FED as the first real enrichment, preserving its 2018 measures and 2016 DA geography. | [Ecosystem enrichment](plans/2026-07-15-ecosystem-enrichment.md) |
| 4 | `0.7.2`: add one public service or location layer selected from a concrete research question—not an omnibus data catalogue. | [Ecosystem enrichment](plans/2026-07-15-ecosystem-enrichment.md) |
| 5 | `0.8.0`–`0.8.1`: publish a simulator-neutral exchange bundle, then validate one demand-backed target adapter. | [Simulation interoperability](plans/2026-07-15-simulation-interoperability.md) |
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

`0.6.2` is a published alpha release with a stable v1 linked-population
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
  recovery, provenance, artifact hashes, and CLI reproduction metadata.

The released web, CLI, and library surfaces share Python domain algorithms.
IPF also shares structured workflow orchestration. Model and small-area CLI
orchestration still differs from the durable web workflow, and small-area
conditions and optional map creation are not yet captured by an exact
executable reproduction recipe. That is `0.6.3` work; public claims should not
say “exact CLI handoff” until its parity tests pass.

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

## Sequenced Releases

### `0.6.3`: Reproduction and durable assurance

This is a maintenance release, not another feature expansion.

- Represent every result-affecting small-area web option in an executable
  reproduction recipe, including model conditions and optional map creation.
- Execute generated IPF, prepared-model, and small-area recipes in tests and
  compare their fixed-seed artifact semantics.
- Extend and validate the existing run/report evidence rather than inventing a
  parallel provenance system.
- Attach correctness reports, checksums, and build/dependency provenance to the
  GitHub Release or another permanent release record instead of relying only on
  expiring Actions artifacts.
- Keep the linked-population v1 contract unchanged.

### `0.7.0`: Geography, source, and enrichment foundation

Two prerequisites ship together because neither is useful for safe
geography-keyed enrichment alone:

- make `(census_vintage, geography_level, identifier_namespace, identifier)`
  explicit in requests, manifests, joins, and errors;
- prove one bounded Québec 2016 DA workflow with metropolitan and rural areas,
  matching controls, boundaries, authoritative relationships, resource
  estimates, validation, and map-size evidence;
- add versioned source-resource and enrichment manifests that compose the
  existing source provenance, linked-population v1, and durable-run records;
- implement immutable, bounded, checksum-recorded resource retrieval and
  explicit source revisions;
- support English/French labels and translation provenance in the metadata
  contract; and
- prove with synthetic fixtures that enrichment leaves the base population and
  its identifiers byte-for-byte unchanged.

This release does not include national DA orchestration, 2021-to-2016 DA
concordance, arbitrary-polygon selection, a general CKAN browser, or a private
cohort adapter.

### `0.7.1`: Can-FED vertical slice

- Integrate the public general-use 1 km and 3 km Can-FED categorical measures
  as a normalized geography/environment layer.
- Preserve July 2018 outlet-measure vintage and the 2016 DA identifier
  namespace.
- Reject an unreviewed join to a 2021 DA population.
- Report duplicate keys, unknown fields, missing source/base DAs, the
  publisher-documented incomplete DA coverage, and all unmatched records.
- Keep detailed Research Data Centre measures out of the public integration.
- Describe the output as area-level historical food-environment context, not a
  current outlet inventory or person-level exposure.

### `0.7.2`: One public service/location pilot

Choose one school, healthcare, food-access, or other public-service source only
after recording the research question, canonical publisher, licence, vintage,
geography, and intended metric. Start with transparent area-level presence,
capacity, or proximity. Do not claim travel-time accessibility without an
independently validated transport network and routing method.

No `0.7.3` outcome is committed yet. After `0.7.1` and `0.7.2`, decide from
real use and authority whether the next work is another public layer, a
restricted cohort research pilot, or no additional enrichment release.

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

The stewardship plan owns the model-licensing decision, full CFF validation,
Software Heritage capture, a dated FAIR4RS baseline, lightweight governance and
maintenance documentation, a tested bilingual 2021 case study, targeted
community introduction, and JOSS maturation.

JOSS submission is not currently ready. The repository became public in June
2026; current JOSS screening requires more than six months of public,
iterative development plus demonstrated research use and other readiness
evidence. January 2027 is only the earliest plausible review point, not a
deadline or promise.

## Explicitly Deferred Or Conditional

- Hosted, authenticated, multi-user, or distributed web operation.
- Redistribution or implied availability of third-party private data.
- Blanket adapters for every dataset in `data/private`.
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
- Consider private cohort attachment only with current written data-use,
  ethics, purpose, methods, and privacy authority.

## Open Decisions

- Exact schema relationship between the current model-specific
  `synthpopcan-source-provenance-v1` record and the general `0.7.0` source
  profile.
- Which public service/location source and research question should define
  `0.7.2`.
- Supported operating-system claim and the minimum Windows/macOS evidence
  needed to make it.
- Whether optional columnar or spatial export merits new dependencies after the
  CSV/JSON interchange contract is proven.
- Boundary between automated model/privacy findings and required human review.
