# SynthPopCan Roadmap

Status: `1.x` maintenance roadmap\
Last updated: 2026-08-19\
Current software version: `1.1.0`

## How To Use This Roadmap

This file answers three questions:

1. What work does the project currently maintain?
1. Which research directions are candidates rather than commitments?
1. Which decisions still need to be made?

It is a routing document, not a second changelog or implementation log. Open
the [implementation-plan index](plans/README.md) only when a task matches one
of its scopes.

| Question | Source of truth |
| --- | --- |
| What is maintained or being considered now? | This roadmap and the linked active plans |
| What changed in a release? | [CHANGELOG.md](CHANGELOG.md) |
| How does the current product work? | [README.md](README.md) and the [user documentation](docs/index.rst) |
| Why was a durable technical choice made? | [Architecture decision records](adr/README.md) |
| What correctness evidence supports current claims? | [CORRECTNESS.md](CORRECTNESS.md) |
| How is a release or public artifact published? | [RELEASING.md](RELEASING.md) |
| What research informed the project? | The dated historical snapshot in [NOTES.md](NOTES.md) |
| What completed an implementation tranche? | [Archived plans](plans/archive/) and the changelog |

Dated records under `docs/records/`, accepted ADRs, archived plans, and fixture
READMEs preserve evidence in its original context. Do not rewrite them merely
to make them sound current; add a new record or a clearly marked amendment
when later evidence changes the interpretation.

## Current Priorities

The bounded `1.1.0` small-area control expansion is released and preserved.
`1.2.0` is now the scoped conditional-person tranche, while `1.3.0` remains a
forecast rather than a commitment. The project plans only this three-release
horizon: one released baseline, one scoped successor, and one
evidence-dependent forecast. Work beyond it remains trigger-based research.

| Priority | Current commitment | Detailed owner |
| --- | --- | --- |
| `1.x` compatibility | Preserve the frozen documented CLI, curated Python API, and supported persisted schemas. Use additive interfaces or separately versioned contracts for new work. | [Compatibility policy](docs/compatibility.md), [ADR-0010](adr/0010-pre-1-0-compatibility-evolution.md) |
| Correctness and release evidence | Keep exact-commit CI, coverage, correctness, installed-distribution, release-evidence, and reproduction gates blocking later releases. | [Correctness assurance plan](plans/2026-07-12-correctness-assurance.md) |
| Stewardship and publication | Preserve the verified `1.1.0` DOI and Software Heritage identifiers together with earlier records; retain scoped licensing, non-overwriting archives, support boundaries, and exact release provenance. | [Stewardship plan](plans/2026-07-19-research-software-stewardship.md), [ADR-0014](adr/0014-separate-prepared-model-and-source-licensing.md) |
| Type-safety maintenance | Keep package-wide Pyright `standard` blocking and expand the strict-clean module set without weakening dynamic-data validation. | [Strict typing plan](plans/2026-08-01-strict-typing.md) |
| Release train | Preserve the additive `1.1.0` control expansion and admit later families only through their stated universe and evidence gates. | [Post-1.0 release train](plans/2026-08-19-post-1-0-release-train.md) |

## Release Horizon

| Release | Confidence | Target window | Planned outcome |
| --- | --- | --- | --- |
| `1.1.0` | Released | August 2026 | 24 reviewed control packs and 14 compatible control families, including broad packs that jointly apply nine household and five person margins with explicit fail-closed runtime invariants. |
| `1.2.0` | Scoped following release | November–December 2026 | Conditional age-15+ marital-status, education, labour-force, and work-activity controls that pass explicit universe and residual gates. |
| `1.3.0` | Forecast, not committed | First half of 2027 | Evidence-qualified language, immigrant place-of-birth, and income-band controls; approximate mortgage/subsidy only as an opt-in tier. |

Patch releases remain demand-driven. Family entities, collective populations,
richer model profiles, and breaking changes have prerequisites rather than
dates. The detailed scope and movement rules live in the
[post-1.0 release train](plans/2026-08-19-post-1-0-release-train.md).

## Conditional Research Tracks

These plans own research beyond the committed `1.1.0` scope. A family assigned
to provisional `1.2.0` or forecast `1.3.0` still returns here if its source,
universe, privacy, or validation gate fails.

| Track | Trigger for implementation | Plan |
| --- | --- | --- |
| Richer hierarchical models | A concrete research use justifies one coherent additive field family and a separately versioned profile. | [Expanded hierarchical tree models](plans/2026-08-01-expanded-hierarchical-tree-models.md) |
| Post-`1.1.0` small-area controls | A conditional person, economic, language, or approximate family passes the release train's explicit universe, suppression, compatibility, and bounded validation gate. | [Expanded small-area controls](plans/2026-08-01-expanded-small-area-controls.md) |
| Uncertainty and disclosure evidence | A study requires quantified candidate-pool, control, seed, model, or privacy uncertainty beyond the released bounded evidence. | [Methodological validation and uncertainty](plans/2026-08-02-methodological-validation-and-uncertainty.md) |
| One target adapter | A real downstream consumer supplies a pinned target contract, authorized fixture, and maintainable import smoke test. | [Simulation interoperability](plans/2026-07-15-simulation-interoperability.md) |

The tracks may inform one another, but they have distinct ownership:

- the tree-model plan owns fields, entity relationships, and profile design;
- the controls plan owns public controls, universes, compatibility, and
  calibration inputs;
- the methodological plan owns independent comparisons, uncertainty,
  statistical utility, and disclosure-risk evidence; and
- the interoperability plan owns population handoff and target-specific
  mappings, not simulation inside SynthPopCan.

## Roadmap Boundaries

SynthPopCan builds, validates, documents, enriches, and exports synthetic
populations through two maintained approaches:

1. iterative proportional fitting from Statistics Canada controls; and
1. linked household/person generation from reviewed model packages, followed
   where appropriate by small-area calibration.

Roadmap decisions must preserve these boundaries:

- Keep raw, restricted, large, and generated data out of git.
- Treat `synthpopcan serve` as a local guided workbench, not a hosted service.
- Preserve source, Census vintage, geography, variables, filters, model
  version, seeds, validation evidence, access classification, and hashes.
- Never infer cross-vintage geography equivalence from matching-looking codes.
- Distinguish software correctness, statistical fitness, disclosure-risk
  review, and substantive research validity.
- Keep external context in governed sidecar contracts rather than silently
  rewriting a linked population.
- Add dependencies, standards, catalogues, or platform adapters only for a
  concrete use that justifies their maintenance cost.
- Never replace published file bytes, version identities, or checksums in
  place. Descriptive metadata corrections must be audited and disclosed;
  changed bytes require a new version.
- Add English/French descriptive metadata progressively while retaining stable
  language-neutral identifiers and translation provenance.

The project does not currently simulate population change, infer causal
effects, certify disclosure safety, or redistribute third-party private data.

## Deferred Or Out Of Scope

The following are not current commitments:

- hosted, authenticated, multi-user, or distributed web operation;
- a monolithic national small-area fit or a universal representativeness claim;
- automatic 2016/2021 geography concordance;
- generic activities, schedules, contact networks, interventions, or
  population projection inside SynthPopCan;
- multiple simulator adapters before one demand-backed pilot succeeds;
- collective-population, economic-family, or census-family generation without
  a separately reviewed entity and artifact contract;
- building- or dwelling-level household placement without authoritative
  capacity evidence, uncertainty treatment, and privacy review;
- blanket integrations for open-data catalogues or restricted sources without
  a research use, authority, provenance, and maintenance case; and
- claims that passing tests proves substantive validity, disclosure safety, or
  causal validity.

## Research Queue

These are ideas to investigate, not scheduled work:

- Start building-level residential placement with one bounded Canadian
  urban/rural case. Allocate whole households to compatible capacity-bearing
  candidates, keep precise coordinates optional and access-classified, and do
  not describe a match as an observed residence.
- Test official province/territory projection scenarios first through a
  2016-to-2021 backcast that clearly separates projected values from
  carried-forward attributes.
- Evaluate arbitrary-polygon selection only after authoritative coded
  geography relationships and vintage checks remain reliable.
- Treat cross-vintage boundary harmonization as a separately reviewed method.
- Consider household-, person-, or cohort-level attachment only with current
  written data-use, ethics, purpose, methods, privacy, and redistribution
  authority.
- Select any next enrichment source—such as PMD, Québec health or education
  geography, Can-ALE, CANUE, ODHF, or CanSET—only after a concrete research
  question establishes temporal/geographic fit, reuse authority, validation,
  and maintenance ownership.
- Reassess aging facility inventories only as a separately governed data
  product with revalidated official sources, licensing, lineage, and bounded
  geographic comparisons.

## Open Decisions

- How should the model-specific `synthpopcan-source-provenance-v1` record relate
  to the general enrichment source profile?
- Which candidate after ODEF has the strongest demonstrated research demand
  and maintenance case?
- What additional Windows and macOS evidence would justify expanding the
  supported-platform claim?
- Does a concrete consumer justify optional columnar or spatial export and its
  dependencies?
- Where should automated model/privacy findings stop and required human review
  begin?

## Completed Work And Historical Detail

Version `1.0.0` established the stable interface boundary; it did not complete
every research direction. Use these records instead of extending this roadmap
with release narrative:

- [CHANGELOG.md](CHANGELOG.md) for observable release history from `0.1.0`
  through `1.0.0`;
- [compatibility policy](docs/compatibility.md) for the exact `1.x` stability
  promise;
- [CORRECTNESS.md](CORRECTNESS.md) for current claims and limitations;
- [stewardship and preservation](docs/stewardship.md) for citation, support,
  licensing, and archive identifiers;
- [prepared-model archive correction record](docs/records/prepared-model-archive-correction-2026-08-16.md)
  for the completed 32-model correction evidence; and
- [archived implementation plans](plans/archive/) for completed design and
  acceptance detail.

Every unfinished roadmap item must appear here or be owned by one linked plan
with a current next action. When a plan is complete, record its user-visible
outcome in the changelog and move the plan to `plans/archive/`.
