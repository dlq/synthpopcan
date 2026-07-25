# Ecosystem Enrichment Implementation Plan

Status: planned\
Created: 2026-07-15\
Last updated: 2026-07-25\
Target: `0.7.0`–`0.7.2`\
Next action: define the source-resource and enrichment manifest contracts, then
prove them with public synthetic fixtures\
Roadmap: [PLANS.md](../PLANS.md) | [Plan index](README.md) | Geography
prerequisite: [small-area geography](2026-07-22-small-area-geography.md)

## Purpose And Boundary

Add governed contextual layers to a validated household/person population
without silently changing the population itself. The first releases cover
source provenance, reproducible resource acquisition, geography-keyed
enrichment, Can-FED, and one bounded public-service pilot.

Enrichment is distinct from Census calibration. A layer may describe the
environment or services associated with a synthetic geography, household, or
person, but it must not alter base rows, identifiers, controls, or validation
evidence. Cohort attachment, activities, schedules, contact networks,
interventions, and simulation behaviour are not committed `0.7.x` outcomes.

The [small-area geography plan](2026-07-22-small-area-geography.md) owns
structured geography requests, relationship indexing, DA synthesis, and
cross-vintage concordance. This plan consumes those contracts; it does not
reimplement them.

## Source And Resource Contract

### Source profiles

A versioned source profile describes a dataset independently of any local copy.
It records:

- stable project and authoritative publisher identifiers;
- canonical resource and documentation URLs;
- authoritative English and French titles and descriptions where available,
  with language availability, fallback, and translation provenance;
- licence, attribution, access, redistribution, and retention conditions;
- source version, publication date, observation period, and update policy;
- unit of observation, variables, units, code lists, missingness, suppression,
  and known limitations;
- geographic level, identifier namespace, vintage, coverage, and CRS where
  applicable; and
- the intended linkage role and the review decision that permits support.

Open-data catalogues such as
[Open Government Canada](https://search.open.canada.ca/opendata/) and
[Données Québec](https://www.donneesquebec.ca/) are discovery sources, not
runtime dependencies. Add a catalogue-specific client only when a selected
supported resource requires it for reproducible acquisition. SynthPopCan is
not intended to mirror or become a general browser for open-data catalogues.

### Resource records

Each acquired public resource receives an immutable resource record containing:

- its source-profile ID and source version;
- resolved URL, retrieval time, response metadata, media type, and byte size;
- observed SHA-256, plus comparison with a publisher checksum when one exists;
- local cache identity and current, superseded, withdrawn, or rejected status;
  and
- extraction or conversion lineage for every retained derivative.

Retrieval must be bounded and atomic. Reacquiring identical bytes reuses the
recorded object; different bytes create an explicit new resource revision
rather than overwriting the prior one. Default tests use public synthetic
fixtures, while live retrieval checks remain opt-in.

Existing Statistics Canada inventories and download manifests are migration
inputs for this contract. Preserve their product IDs, URLs, and local files,
and add missing retrieval or integrity metadata without presenting a local
inventory as a complete public catalogue.

### Access-controlled research candidates

CANUE, CPTP, MAVAN, MoNNET, and TOPO remain possible research sources, not
promised project inputs. Their presence in an authorized research environment
does not establish ownership, permission for a new purpose, or permission to
redistribute source data, derived values, fixtures, models, or examples.

No numbered release depends on access to these sources. Dataset-specific work
requires current written authority for the purpose, an identified steward and
methods/privacy reviewer, applicable ethics approval, and documented
publication, retention, and destruction conditions. Public code may contain
only generic contracts and synthetic fixtures unless separate authority permits
more.

Never expose private records, samples, exact local paths, access
correspondence, secrets, coordinates, small cells, or disclosure-sensitive
derived values through git, CI, documentation, logs, releases, or telemetry.
CARE practice and rights-holder engagement apply when Indigenous data or
knowledge are in scope; an open licence alone is not sufficient authority.

## Enrichment Contract

An enrichment manifest composes, rather than replaces:

- the existing linked-population v1 descriptor;
- the durable run record and published-artifact hashes when a run produced the
  population; and
- one or more source profiles and immutable resource records.

It records the base table hashes, layer schema version, key roles, source
lineage, variables, units, code lists, observed-versus-modeled status, linkage
method, parameters, seeds where relevant, access classification, validation,
and exact reproduction request.

Initial enrichment is geography-keyed. Every geography key includes its Census
vintage, level, and authoritative identifier namespace; a matching text value
alone is insufficient. Joins reject unknown, duplicate, ambiguous, or
cross-vintage keys unless a separately reviewed concordance is supplied.

Each layer is a normalized table rather than an automatic widening of
`households.csv` or `persons.csv`. The manifest reports matched, unmatched,
multiply matched, and out-of-scope records. Weighting, uncertainty,
representativeness, and privacy diagnostics are required only when the linkage
method makes them relevant.

## Release Slices

### `0.7.0`: Source and enrichment foundation

Implement:

- source-profile, resource-record, and enrichment-manifest validators;
- bilingual descriptive-metadata fields with explicit authoritative and
  project-supplied translation provenance;
- bounded, atomic acquisition with recorded checksums and explicit resource
  revisions;
- migration/inspection of the currently supported Statistics Canada source
  metadata;
- composition with linked-population v1 and durable-run artifacts without
  modifying either schema; and
- a geography-keyed synthetic enrichment fixture that proves the base
  population remains byte-for-byte unchanged.

The library owns the contracts and validation. CLI and local-workbench
surfaces, if provided, call the shared Python workflow rather than implementing
separate source or linkage logic.

`0.7.0` does not include a general catalogue client, private cohort adapter,
cross-vintage concordance, arbitrary-polygon selection, or national DA
orchestration.

### `0.7.1`: Can-FED vertical slice

Integrate Statistics Canada's public general-use
[Canadian Food Environment Dataset (Can-FED)](https://www150.statcan.gc.ca/n1/pub/13-20-0001/132000012022001-eng.htm)
as the first real enrichment:

- acquire and profile the public 1 km and 3 km categorical files;
- preserve the July 2018 food-outlet observation period and 2016 DA geography;
- key the normalized environment layer by the explicit 2016 DA namespace;
- validate buffer variants, fields, duplicate keys, source coverage, and all
  unmatched source and base DAs;
- reject an unreviewed join to a 2021 DA population; and
- keep detailed Research Data Centre measures outside the public integration.

The result is historical, area-level food-environment context. It is not a
current inventory of establishments, a person-level exposure measurement, or
evidence that the food environment caused an outcome.

### `0.7.2`: One public service/location pilot

Select exactly one public school, healthcare, food-access, or other
public-service resource after documenting:

- the research question and intended users;
- canonical publisher, licence, version, and reproducible acquisition;
- service definition, observation period, geography, and quality limitations;
- the one supported area-level presence, capacity, or proximity measure; and
- why its benefit justifies its maintenance and dependency cost.

Publish one normalized service/location layer with source and geography
lineage, unmatched reporting, synthetic fixtures, and an end-to-end
reproduction. Do not claim route or travel-time accessibility without an
independently validated transport network, routing method, and temporal model.

## Deferred Decisions

No `0.7.3` outcome is committed. After `0.7.1` and `0.7.2`, use actual research
demand and data authority to decide whether another public layer is warranted.

Private cohort attachment remains a conditional research project. It would
require a concrete study, current source authority, harmonization and
eligibility rules, a reviewed weighting or statistical-matching method,
representativeness and uncertainty evidence, and human methods/privacy
approval. Activities, schedules, memberships, contact networks, and
intervention scenarios likewise require their own evidence and behavioral
assumptions; they are not implied by the enrichment contract.

## Acceptance Criteria

### `0.7.0`

- Unknown contract versions, invalid access classifications, unsafe paths, and
  incomplete geography namespaces are rejected.
- A repeated retrieval of identical bytes is reused; changed bytes create a
  visible resource revision without replacing prior provenance.
- Public fixtures reproduce without network access, and live-source tests are
  explicitly opt-in.
- Enrichment preserves the exact base file hashes, row counts, identifiers,
  controls, and linked-population descriptor.
- User-facing metadata exposes reviewed English/French text where available
  and clearly marks single-language or project-translated fields.

### `0.7.1`

- Both public Can-FED buffer products are reproducibly acquired and profiled.
- Duplicate or malformed DA keys and any 2021-to-2016 join attempt fail
  clearly.
- Source coverage, base coverage, and unmatched records reconcile exactly.
- A synthetic end-to-end example reproduces the normalized layer and
  validation report without redistributing restricted Can-FED material.

### `0.7.2`

- One named source, research question, jurisdiction, vintage, geography, and
  metric define the supported scope.
- The source profile, acquisition, normalization, linkage, validation,
  limitations, and exact reproduction are independently testable.
- Documentation distinguishes source observations, project-derived measures,
  missing services, and unmatched areas without implying unsupported
  accessibility or causal conclusions.
