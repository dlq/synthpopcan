# SynthPopCan Plan

Status: release-phased roadmap\
Last updated: 2026-08-10\
Current published release: `0.9.0`

## Current Focus

Start here, then open a linked implementation plan only for the area being
worked on. Completed release detail belongs in [CHANGELOG.md](CHANGELOG.md);
completed implementation plans belong in [`plans/archive/`](plans/archive/).

| Order | User outcome | Done when | Owned by |
| --- | --- | --- | --- |
| Next: `1.0.0` | Researchers and downstream tools can rely on a documented stable CLI, Python API, and declared persisted contracts. | The supported surface inventory is reviewed, pre-1.0 aliases and inconsistencies are resolved, compatibility tests freeze the declared contracts, the installed-package documentation and bilingual case study pass, and release/stewardship gates are complete. | This roadmap, [stewardship](plans/2026-07-19-research-software-stewardship.md), [strict typing](plans/2026-08-01-strict-typing.md), and [ADR-0010](adr/0010-pre-1-0-compatibility-evolution.md) |
| Post-`1.0` expansion | Add richer fields, family and collective-population structure, deeper uncertainty/privacy methods, building placement, and demand-backed adapters without destabilizing the frozen core. | Each addition uses the stable extension points or a separately versioned new contract and has its own evidence-backed release scope. | Active research plans and the research queue below |

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
- Before `1.0.0`, allow deliberate breaking changes when they materially
  simplify the architecture, improve correctness, or make the research model
  more honest. Version changed schemas and packages, document the break and
  replacement path, fail clearly on unsupported old artifacts, and provide a
  converter when practical; backward compatibility is desirable but is not a
  release gate. Never rewrite an already published artifact or archival record
  in place. [ADR-0010](adr/0010-pre-1-0-compatibility-evolution.md) records this
  compatibility boundary.

Research background belongs in [NOTES.md](NOTES.md). Every unfinished roadmap
item must appear here or be owned by one linked active plan with a current next
action. The [plan index](plans/README.md) records active and archived plans.

## Current Product State

`0.9.0` is a published alpha release with bounded methodological evidence,
strict control-pack and source/universe-evidence contracts, explicit Census
geography identity, a reusable external-data enrichment framework, maintained
Can-FED and ODEF adapters, and a stable v1 linked-population artifact contract.
It provides:

- seed/control IPF with diagnostics, compact weights, integerized records,
  reports, and validation;
- Statistics Canada WDS discovery, Census Profile preparation, explicit 2016
  and 2021 microdata adapters, selected matching boundaries, and geographic
  relationship inputs;
- linked frequency/CART training, audit, packaging, fetching, generation, and
  validation;
- a 33-entry prepared-model registry containing a demo plus parallel 2016 and
  2021 packages for Canada, supported provinces, and five PUMF-coded CMAs;
- linked small-area calibration, joint person controls, fail-closed control-pack
  planning, independently recomputed field/weight/reuse/tail diagnostics, scale
  estimation, residual reports, realization, and standalone maps;
- durable local runs with bounded uploads and previews, progress, cancellation,
  recovery, exact structured reproduction recipes, and versioned assurance
  evidence with independently verifiable hashes, row counts, diagnostics, and
  linkage findings; and
- a simulator-neutral CSV/JSON population-contribution bundle with unchanged
  linked tables, a data dictionary, provenance, access classifications,
  reproduction evidence, strict validation, and per-file hashes.

The released web, CLI, and library surfaces share Python domain algorithms.
IPF also shares structured workflow orchestration. Model and small-area CLI
orchestration still differs in places from the durable web workflow, so parity
tests execute the recorded fixed-seed recipes, including model conditions,
uploaded candidates, fitted weights, and optional map creation.

The release also publishes a separately versioned `geodata-v1` catalogue of
checksummed display-only boundaries and implements verified runtime retrieval.
Canonical Statistics Canada geometry remains the analytical input. It moves
scikit-learn behind the optional
`model-build` extra: CART training needs it, while portable model reading,
generation, and conditional-frequency training do not.

Completed implementation records are archived:

- [local web runtime](plans/archive/2026-07-10-local-web-application-runtime.md);
- [linked-population schema](plans/archive/2026-07-18-linked-population-schema.md);
- [small-area geography](plans/archive/2026-07-22-small-area-geography.md); and
- [external-data enrichment](plans/archive/2026-07-15-ecosystem-enrichment.md).

## Path To `1.0.0` And Stability Boundary

The project should reach `1.0.0` by stabilizing the useful core, not by
finishing every research direction. Only three bounded product tranches are on
the pre-`1.0` path.

### `0.8.0`: portable handoff — completed

Released on 2026-08-07. The simulator-neutral CSV/JSON bundle composes the
linked-population and durable-run contracts without adding a simulator-specific
adapter. A real consumer can read and independently validate the contract with
no optional format or simulator dependency.

### `0.9.0`: bounded methodological and small-area confidence — completed

Released on 2026-08-10. The bounded private-household workflow now has:

- generated feasible linked-calibration cases and one independent
  solver-backed oracle;
- a reviewed integerization comparison and backend decision;
- versioned generic control-pack and field/control compatibility contracts;
- reviewed 2016 and 2021 core household controls plus private-household
  age-by-sex/gender person controls for explicitly named supported geographies;
- bounded multi-scale validation and a pinned external Canadian comparison;
- weight concentration, candidate reuse, rare-category, declared-zero-target,
  and targeted-versus-uncontrolled reporting; and
- one representative end-to-end fixture proving that the generic model-profile
  and control-pack interfaces can accept later additive profiles without a CLI
  redesign.

This tranche did not require implementing every candidate control, every
hierarchical PUMF field, a family hierarchy, collective populations, a national
fit, full uncertainty ensembles, or a new generative-model family.

### `1.0.0`: interface review and freeze

Before tagging `1.0.0`:

1. inventory every documented `synthpopcan` command path, option, exit behavior,
   and machine-readable output mode;
1. inventory every documented Python import and symbol intended as public;
1. list the persisted schemas and model/control/exchange contracts supported by
   the `1.x` line;
1. remove, rename, or consolidate misleading pre-`1.0` interfaces while a
   deliberate break is still allowed, with migration guidance where useful;
1. add installed-package CLI/API compatibility fixtures and semantic snapshots
   that ignore harmless formatting, paths, and timestamps;
1. verify documentation, public type completeness, supported-platform claims,
   packaging, security, citation, preservation, licensing, and the bilingual
   2021 case study; and
1. publish the compatibility policy and exact declared surface with the
   release.

The freeze covers documented CLI command paths and options, documented Python
API symbols, and versioned persisted contracts explicitly declared supported
for `1.x`. Additive commands, options, symbols, and new versioned schemas may be
introduced in later minor releases. Removing or changing the meaning of frozen
surface requires deprecation where practical and a new major version. Internal
modules, undocumented helpers, web presentation details, external source
catalogues, and research findings are not frozen.

`1.0.0` does not require Pyright strict mode, a monolithic national population,
all possible controls, building-level placement, population projection,
simulation, or a JOSS paper. It means the supported core is coherent,
documented, tested, and stable enough to build upon.

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
| `0.7.0` | Explicit Census geography identity, bounded national DA/ADA workflows, reusable external-data enrichment contracts, separately versioned display geodata, and an optional CART model-building dependency. |
| `0.7.2` | Maintained Can-FED area-context and corrected ODEF facility-inventory adapters with pinned acquisition, normalization, validation, and complete provenance evidence; no separate `0.7.1` package was released. |
| `0.8.0` | Simulator-neutral linked-population exchange bundle with data dictionary, provenance, reproduction, file governance, hashes, and strict independent validation. |
| `0.9.0` | Independent bounded calibration and integerization evidence, strict 2016/2021 core private-household control packs across CSD/CT/ADA/DA, bound source/universe evidence, and linked methodological diagnostics. |

## Sequenced Releases

### `0.7.0`: Geography and reusable external-data enrichment framework

Released on 2026-08-01. It established explicit Census geography identity,
bounded national DA/ADA planning and execution, and reusable source, resource,
layer, validation, and enrichment-manifest contracts. Researchers can import a
conforming normalized sidecar without waiting for a built-in dataset adapter,
and synthetic fixtures prove that enrichment does not mutate the base linked
population. See [CHANGELOG.md](CHANGELOG.md) and the archived
[small-area geography plan](plans/archive/2026-07-22-small-area-geography.md)
for completed implementation and evidence.

This release does not include a monolithic national fit, an automatic claim
that the broad Canada PUMF model is fit for every provincial, territorial, or
small-area research question, 2021-to-2016 DA concordance,
arbitrary-polygon selection, a general CKAN browser, or an automatic
compatibility promise for every candidate source.

The full-field ADA/DA control-coverage audit and linked person-control expansion
are a parallel post-`0.7.0` correctness track. They did not block the combined
area- and facility-sidecar implementation released in `0.7.2`, but they do
block any new claim that a carried-through PUMF field represents an ADA- or
DA-local distribution.

With the framework released, another dataset may be integrated whenever a
research question, access and redistribution authority, geographic and
temporal fit, validation strategy, and maintenance case justify it. A source
need not appear in the current repository examples or wait for every planned
reference implementation.

### `0.7.1` outcome: Can-FED v2 reference implementation

Implemented and released in `0.7.2` rather than published separately.

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

Released in the combined `0.7.2` tranche using the corrected v3.0.1 bytes
served by the official v3.0 URL. The adapter preserves the fields actually present:
source identifiers, provider and authority, source dates, facility type,
grades/ISCED, language indicators, 2021 CSD context, WKT, and parsed
coordinates. It validates duplicates, missingness, geocoding, coverage, and
unmatched CSDs. The live source contains no CMA fields, so CMA lineage is not
invented. The result is a facility inventory, not evidence of capacity,
catchment, quality, eligibility, or accessibility.

Can-FED and ODEF demonstrate that the framework is reusable; they do not
define or limit its scope. The enrichment plan ranks PMD 2021, Québec
health-service geography, Can-ALE 2.0, CANUE, ODHF, Québec education layers,
and CanSET as later candidates. No `0.7.3` outcome is committed. Further
integrations may land in an appropriate maintenance or feature release when
they pass the same demand, authority, semantics, validation, and stewardship
gates.

### `0.8.0`: Simulator-neutral exchange

Released on 2026-08-07. It composes the existing linked-population and
durable-run contracts into a self-describing bundle; requires CSV
household/person tables plus JSON manifest, data dictionary, validation,
reproduction, access classification, and per-file hashes; preserves
`synthetic_household_id` and `synthetic_person_id`; and remains readable and
validatable without simulator dependencies. Parquet, GeoParquet, GeoPackage,
RO-Crate, deterministic archives, and target adapters remain conditional later
mappings.

### `0.9.0`: Bounded methodological and small-area confidence

Released on 2026-08-10. It retains the production linked multiplicative
updater and systematic-midpoint integerizer after independent bounded
comparisons; adds strict, definition-only 2016/2021 CSD, CT, ADA, and DA core
control packs; binds exact normalized counts to explicit source and
private-household-universe evidence; and carries independently recomputed
residual, concentration, reuse, rare-cell, zero-target, and field-status
diagnostics through the API, CLI, and local web workflow. The multi-scale and
external Canadian evidence is bounded and descriptive, not a national
representativeness or record-level truth claim.

### Post-`1.0`: One target adapter pilot

Select one external target after `1.0.0` only when there is a real user or
reference model, a pinned supported version, an official input contract, and a
maintainable import smoke test. The adapter must distinguish a population
contribution from a runnable simulation and list every external network,
land-use, schedule, behaviour, coefficient, or model input still required.

ActivitySim, Starsim, Mesa, GAMA, MATSim, SUMO, Vivarium, FRED, and AnyLogic
remain researched candidates, not simultaneous commitments. Transport-plan
adapters remain unversioned future work until activities, locations, schedules,
modes, and network/link mappings are justified by a concrete project.

## Ongoing Assurance And Stewardship

The correctness plan owns exact reproduction, the versioned assurance payload,
routine evidence gates, zero-cell policy, cross-platform evidence, and external
review. The dedicated
[methodological validation and uncertainty plan](plans/2026-08-02-methodological-validation-and-uncertainty.md)
owns calibration oracles, backend and integerization comparisons, uncertainty
ensembles, shared multi-axis validation, external Canadian benchmarks, and
attack-oriented disclosure evidence. Territory and broader-CMA models are
feasibility candidates, not promised coverage: each must pass support,
rare-category, privacy, provenance, and reproducible-build gates.

Prepared-geodata releases need a deterministic catalogue audit before each
publication: verify the expected year/geography/PRUID identity coverage,
unique asset names, immutable release-tag URLs, and both checksum fields. A
separate bounded remote retrieval check may exercise a representative asset,
but routine CI must not redownload the complete boundary release.

The stewardship plan owns the pre-`1.0` model-licensing decision, full CFF
validation, Software Heritage capture, dated FAIR4RS and management records,
and tested bilingual 2021 case study. Targeted community introduction and JOSS
maturation remain post-`1.0` or non-blocking activities.

JOSS submission is not currently ready. The repository became public in June
2026; current JOSS screening requires more than six months of public,
iterative development plus demonstrated research use and other readiness
evidence. January 2027 is only the earliest plausible review point, not a
deadline or promise.

### Strict typing migration

Pyright `standard` remains a package-wide blocking gate. Strict mode advances
as a non-release-blocking ratchet through the active
[strict typing plan](plans/2026-08-01-strict-typing.md); a numbered release is
blocked only if it explicitly adopts a stricter typing gate.

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
- Any simulator-specific adapter before the `1.0.0` interface freeze.
- Exhaustive implementation of every candidate small-area control or extended
  PUMF field before `1.0.0`.
- Chained production models, economic- or census-family entities, and
  collective/non-private-household generation before `1.0.0`.
- Full uncertainty ensembles and a general empirical privacy-attack framework
  beyond the bounded evidence required for current public models before
  `1.0.0`.
- Building- or dwelling-level household placement before the stable population,
  geography, and exchange contracts exist.
- Population simulation inside SynthPopCan.
- Claims that test passage proves substantive validity, disclosure safety, or
  causal validity.

## Research Queue, Not Release Commitments

- Design building-level residential placement after `1.0.0`. Start with a
  bounded urban/rural Canadian case and treat it as constrained allocation of
  whole households to compatible dwelling/building candidates—not random point
  placement. Required evidence includes authoritative or licensed building and
  dwelling sources, vintage and address/geography reconciliation, residential
  capacity, vacancy, multi-unit and mixed-use handling, housing/household
  compatibility, collective-dwelling separation, unmatched cases, spatial
  uncertainty, privacy, and aggregation back to Census geography. Keep precise
  coordinates optional and access-classified, and do not claim that a building
  match is an observed residence.
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
