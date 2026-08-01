# Reusable External-Data Enrichment Framework Plan

Status: active; `0.7.0` foundation released\
Created: 2026-07-15\
Last updated: 2026-08-01\
Target: `0.7.0`–`0.7.2`\
Next action: implement the bounded public `0.7.1` Can-FED reference adapter\
Roadmap: [PLANS.md](../PLANS.md) | [Plan index](README.md) | Released geography
foundation: [small-area geography](archive/2026-07-22-small-area-geography.md)

## Purpose And Boundary

Build a reusable external-data enrichment framework that can connect any
amenable public, locally supplied, licensed, or restricted dataset to a
validated household/person population without silently changing the
population itself. Named datasets and the families currently represented in
`data/private/sources` are examples and possible consumers of the framework,
not its scope, an exhaustive source list, or a separate integration track.

The first releases establish source provenance, reproducible resource
acquisition, source-independent normalization and linkage, and governed
sidecar layers. Can-FED v2 and the Open Database of Educational Facilities
(ODEF) v3 are contrasting area-attribute and facility reference adapters that
prove the framework against real data; they are not special cases embedded in
the core contracts.

Enrichment is distinct from Census calibration. A layer may describe the
environment or services associated with a synthetic geography, household, or
person, but it must not alter base rows, identifiers, controls, or validation
evidence. Cohort attachment, activities, schedules, contact networks,
interventions, and simulation behaviour are not committed `0.7.x` outcomes.

The archived [small-area geography plan](archive/2026-07-22-small-area-geography.md)
records the released structured geography requests, relationship indexing, and
DA/ADA synthesis foundation. This plan consumes those contracts; it does not
reimplement them. Follow-on control-coverage work belongs to the active
[correctness plan](2026-07-12-correctness-assurance.md).

## Source-Agnostic Pipeline

Every supported adapter uses the same staged workflow:

1. **Describe:** identify the authoritative publisher, resource, version,
   observation period, units, geography, licence, access mode, and intended
   research use.
1. **Acquire or reference:** retrieve public resources reproducibly, or
   register locally supplied, licensed, or restricted resources without
   exposing their contents or locations.
1. **Verify:** record immutable resource identity, checksums, byte size,
   format, and any publisher integrity evidence.
1. **Normalize:** transform source-specific fields into a versioned,
   documented layer schema while preserving raw-to-normalized lineage.
1. **Align and link:** match geography, time, facilities, households, or
   persons through an explicit reviewed method; never infer compatibility from
   similarly named identifiers.
1. **Validate:** reconcile duplicates, missingness, coverage, unmatched and
   multiply matched records, units, code lists, and method-specific quality or
   privacy diagnostics.
1. **Publish or retain:** emit a sidecar layer, manifest, validation evidence,
   and reproduction request only to destinations permitted by the source's
   authority and redistribution conditions.

The core library defines these stages and contracts. Dataset adapters supply
source-specific discovery, parsing, normalization, and linkage declarations
without bypassing the common validation or authority gates.

The framework supports two entry paths:

- a maintained source adapter may automate the complete pipeline for a
  selected dataset; or
- a researcher may supply an externally prepared normalized layer together
  with valid source, resource, schema, and lineage metadata.

The second path is essential to generality: a dataset does not need a
SynthPopCan-specific adapter before it can use the common linkage, validation,
sidecar, and provenance contracts. SynthPopCan validates the declared
normalized artifact; it does not imply that an undocumented external
transformation was correct.

## Source And Resource Contract

### Source profiles

A versioned source profile describes a dataset independently of any local copy.
It records:

- stable project and authoritative publisher identifiers;
- canonical resource and documentation URLs;
- acquisition mode (`public-download`, `public-api`, `local-provided`,
  `licensed`, or `restricted`) and the authority under which it may be used;
- authoritative English and French titles and descriptions where available,
  with language availability, fallback, and translation provenance;
- licence, attribution, access, redistribution, and retention conditions;
- source version, publication date, observation period, and update policy;
- unit of observation, variables, units, code lists, missingness, suppression,
  and known limitations;
- geographic level, identifier namespace, vintage, coverage, and CRS where
  applicable; and
- the intended linkage role and the review decision that permits support.

Public portals and open-data catalogues such as
[Open Government Canada](https://search.open.canada.ca/opendata/) and
[Données Québec](https://www.donneesquebec.ca/) are examples of discovery
sources. They are neither an exhaustive source universe nor runtime
dependencies. Add a catalogue- or provider-specific client only when a
selected supported resource requires it for reproducible acquisition.
SynthPopCan is not intended to mirror or become a general browser for open-data
catalogues.

### Resource records

Each acquired or registered resource receives an immutable resource record
containing:

- its source-profile ID and source version;
- permitted locator or opaque local identity, retrieval or registration time,
  response metadata when applicable, media type, and byte size;
- observed SHA-256, plus comparison with a publisher checksum when one exists;
- local cache identity and current, superseded, withdrawn, or rejected status;
  and
- extraction or conversion lineage for every retained derivative.

Public retrieval must be bounded and atomic. Registering local, licensed, or
restricted material must not copy it into a public project location or expose
its filesystem path. Reacquiring or reregistering identical bytes reuses the
recorded object; different bytes create an explicit new resource revision
rather than overwriting the prior one. Default tests use public synthetic
fixtures, while live retrieval and controlled-data checks remain opt-in.

Existing Statistics Canada inventories and download manifests are migration
inputs for this contract. Preserve their product IDs, URLs, and local files,
and add missing retrieval or integrity metadata without presenting a local
inventory as a complete public catalogue.

### Example sources and authority gates

Can-FED, public portal datasets, and future facility, environmental, service,
or administrative resources are examples of public consumers. CANUE, CPTP,
MAVAN, MoNNET, TOPO, and any other families represented under
`data/private/sources` are examples of locally available or access-controlled
consumers. Neither list is exhaustive, and a source's presence in a local
directory does not make it a promised project input.

The same framework may support all of these acquisition modes, but authority
is evaluated adapter by adapter. Access to a dataset does not establish
ownership, permission for a new purpose, or permission to redistribute source
data, derived values, fixtures, models, or examples. No numbered release
depends on access-controlled material. Dataset-specific work requires current
written authority for the purpose, an identified steward and methods/privacy
reviewer, applicable ethics approval, and documented publication, retention,
and destruction conditions. Public code may contain only generic contracts
and synthetic fixtures unless separate authority permits more.

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

### Layer and source classes

The framework distinguishes source classes because they require different
keys, claims, and validation:

- **Area attributes:** environmental, socioeconomic, land-use, or policy
  observations keyed by an explicit geography namespace and vintage. Publish
  these as geography sidecars, not automatically as person-level exposures.
- **Facilities and points:** schools, healthcare sites, food outlets, and
  other service locations with coordinates or service areas. Preserve source
  observations separately from derived presence, capacity, distance, or
  accessibility measures.
- **Household, person, or cohort attachments:** survey, administrative, or
  cohort variables linked or statistically assigned under an approved method.
  These are conditional research adapters requiring authority, privacy,
  representativeness, uncertainty, and disclosure review.
- **Networks, activities, schedules, and relationships:** relational or
  temporal data represented as separate edge, event, or membership layers.
  These remain conditional until a concrete research question and validated
  generative method justify them.

Supporting the first two classes in reference adapters does not imply that the
latter two are safe or scientifically valid by default. New source classes may
be added when their semantics and validation requirements can be expressed
without weakening the common contracts.

## Release Slices

### `0.7.0`: Reusable framework foundation

Implement:

- source-profile, resource-record, and enrichment-manifest validators;
- a source-adapter interface covering describe, acquire-or-reference,
  normalize, link, validate, and publish-or-retain stages;
- a generic import and validation path for researcher-supplied normalized
  layers that have no built-in source adapter;
- public, local-provided, licensed, and restricted acquisition modes with
  explicit authority and redistribution gates;
- bilingual descriptive-metadata fields with explicit authoritative and
  project-supplied translation provenance;
- bounded, atomic acquisition with recorded checksums and explicit resource
  revisions;
- migration/inspection of the currently supported Statistics Canada source
  metadata;
- composition with linked-population v1 and durable-run artifacts without
  modifying either schema; and
- source-independent public synthetic fixtures, including a geography-keyed
  area layer and a bounded facility/point layer, that prove the base
  population remains byte-for-byte unchanged.

The library owns the contracts and validation. CLI and local-workbench
surfaces, if provided, call the shared Python workflow rather than implementing
separate source or linkage logic.

`0.7.0` establishes reusable capability; it does not claim compatibility with
every external dataset. It does not include a general catalogue client,
private cohort adapter, cross-vintage concordance, arbitrary-polygon
selection, or national DA orchestration.

### `0.7.1`: Can-FED v2 reference adapter

Integrate Statistics Canada's public general-use
[Canadian Food Environment Dataset (Can-FED) v2](https://www150.statcan.gc.ca/n1/pub/13-20-0001/132000012025002-eng.htm)
as the first real area-attribute adapter:

- acquire and profile the public general-use 1 km and 3 km categorical files
  in their published CSV or Parquet form;
- preserve the August 2024 food-environment observation period, 2024 Business
  Register basis, and 2021 DA geography;
- key the normalized environment layer by the explicit 2021 DA namespace;
- validate buffer variants, fields, duplicate keys, source coverage, and all
  unmatched source and base DAs;
- reject an unreviewed join to a 2016 DA population; and
- keep detailed Research Data Centre measures outside the public integration.

The result is historical, area-level food-environment context. It is not a
current inventory of establishments, a person-level exposure measurement, or
evidence that the food environment caused an outcome.

### `0.7.2`: ODEF v3 facility reference adapter

Integrate Statistics Canada's
[Open Database of Educational Facilities (ODEF) v3](https://www150.statcan.gc.ca/n1/pub/37-26-0001/372600012022001-eng.htm)
as the contrasting national facility/point adapter. The approximately 19,000
records collected in 2024 provide coordinates and fields including facility
type, governing authority, ISCED level, official-language-minority status,
address, and CSD/CMA identifiers.

Preserve source identifiers and observations, assess duplicate facilities and
geocoding/coverage limitations, and publish a normalized facility layer with
source and geography lineage, unmatched reporting, synthetic fixtures, and an
end-to-end reproduction through the same framework used by Can-FED. ODEF
supports facility inventory and spatial linkage; it does not establish school
capacity, catchments, quality, enrolment eligibility, or accessibility. Do not
derive or claim route or travel-time accessibility without an independently
validated transport network, routing method, and temporal model.

## Ranked Candidate Adapter Queue

No version is reserved for the following integrations. Reconsider the order
when a concrete research question, user, source update, or maintenance concern
changes the evidence:

1. **Proximity Measures Database 2021:** add the nationwide dissemination-block
   [PMD 2021](https://www150.statcan.gc.ca/n1/pub/17-26-0002/172600022023001-eng.htm)
   as a high-value area-attribute adapter spanning health care, pharmacies,
   primary and secondary education, child care, transit, parks, libraries,
   employment, and grocery stores. Preserve its normalized relative
   proximity semantics; it is not a capacity, quality, wait-time, or realized
   access measure.
1. **Québec health-service geography:** evaluate the official
   [health and social-service facilities and territories](https://www.quebec.ca/sante/systeme-et-services-de-sante/organisation-des-services/donnees-systeme-sante-quebecois-services/information-geographique-sante-services-sociaux)
   as a richer provincial facility/service-area adapter covering
   installations and CLSC, RLS, RTS, RSS, and RUISSS territories.
1. **Can-ALE 2.0:** evaluate the
   [Canadian Active Living Environments Database](https://www150.statcan.gc.ca/n1/pub/82-003-x/2026006/article/00001-eng.htm)
   as a reproducible DA-level built-environment adapter for 2011, 2016, and
   2021\. Keep active-living context distinct from individual behaviour or
   health outcome.
1. **CANUE:** evaluate
   [Canadian Urban Environmental Health Research Consortium data](https://canue.ca/data-tools/canue-data/)
   for postal-code-standardized air pollution, climate, greenness, noise, and
   built/socioeconomic environment exposures. Treat application-controlled
   access and researcher eligibility as authority gates, not as public
   acquisition.
1. **Open Database of Healthcare Facilities:** evaluate
   [ODHF v1.1](https://www.statcan.gc.ca/en/lode/databases/odhf) as a national
   point layer or comparison source only after reviewing its acknowledged
   incompleteness and 2019–2020 collection vintage.
1. **Québec school-system depth:** compare ODEF with Québec's
   [school locations and education-system territories](https://www.quebec.ca/education/cartes-donnees-geographiques)
   when a provincial question needs current school-network detail, service
   territories, or school deprivation indices.
1. **CanSET 2021:** evaluate the
   [Canadian Social Environment Typology](https://www150.statcan.gc.ca/n1/pub/17-20-0002/172000022026001-eng.htm)
   only when an urban social-context typology is substantively useful. Record
   that it clusters Census-derived variables, excludes areas outside CMAs/CAs,
   and that its 2016 and 2021 versions are not directly comparable.

These candidates intentionally cover three different source classes: area
measures such as PMD and Can-ALE, facility/service layers such as ODEF and
Québec health geography, and environmental exposures such as CANUE. An area
measure is not an individual exposure; a facility location is not capacity or
access; proximity is not service use; and Census-derived context can be
circular when used to explain a population synthesized from the same Census.

## Speculative Independent LODE Refresh Products

Periodically audit the complete
[Statistics Canada Linkable Open Data Environment (LODE) catalogue](https://www.statcan.gc.ca/en/lode/databases)
instead of assuming that a currently listed database contains current
observations. Record release, collection, and provider-update dates
separately. The 2025 greenhouse, building, pedestrian, transit, and cycling
releases show active recent work, while the healthcare, cultural/art,
recreation/sport, and address inventories remain snapshots largely assembled
in 2019–2021.

A reproducible refresh of one or more aging LODE facility inventories may be a
valuable independent open-data product, starting with healthcare because of
its public-health value and need for current information. This is speculation,
not a SynthPopCan release commitment. Before starting:

- inventory the current provincial and territorial sources, licences,
  definitions, update mechanisms, identifiers, and coverage;
- define a narrow defensible scope and common schema without erasing
  jurisdiction-specific classifications;
- preserve provider identifiers and row-level source, observation-date,
  transformation, and manual-correction lineage;
- publish jurisdiction-level freshness, completeness, geocoding, duplicate,
  and classification evidence rather than claiming a complete national
  register;
- use a distinct name and governance so the result cannot be mistaken for an
  official Statistics Canada continuation;
- seek collaboration or technical guidance from the responsible Statistics
  Canada team before duplicating active work; and
- give any separate product its own repository, release cycle, licence,
  citation, DOI, stewardship, and contributor community. SynthPopCan would
  consume a pinned public release through the normal enrichment adapter.

The public [CSBP-CPSE GitHub organization](https://github.com/CSBP-CPSE)
contains useful prior art:

- [`LODE-ECDO`](https://github.com/CSBP-CPSE/LODE-ECDO) provides a
  `MasterList_OpenDataPortals.csv`, historical theme-specific source
  inventories, MIT-licensed source descriptors, and older transformation
  scripts. Treat these as discovery and provenance seeds whose URLs, licences,
  and coverage must be reverified—not as a current registry.
- [`OpenTabulate`](https://github.com/CSBP-CPSE/OpenTabulate) demonstrates a
  descriptor-driven CSV/XML normalization pipeline with explicit source,
  provider, licence, encoding, format, schema mapping, filtering, and output
  fields. Reuse the concepts and compare schemas, but do not add the aging
  Linux-oriented Python 3.5–3.8 package as a SynthPopCan dependency without a
  fresh code, security, compatibility, and maintenance review.
- the address and building workflow repositories document download,
  normalization, spatial CSD assignment, deduplication, source precedence,
  sampling, and validation techniques that may inform adapters without being
  copied uncritically;
- the recent
  [`CanWalkOntology`](https://github.com/CSBP-CPSE/CanWalkOntology) and
  [`CanBICSOntology`](https://github.com/CSBP-CPSE/CanBICSOntology) may inform
  stable bilingual pedestrian and cycling vocabulary; and
- the LODE and proximity viewers are implementation references, not required
  runtime dependencies for the Python enrichment framework.

Before importing any code, inspect the file-level licence and history, retain
the required Crown copyright and MIT notices, identify third-party material,
and prefer a small attributed port with tests over depending on an inactive
repository.

### OpenStreetMap and Overture as corroborating sources

Evaluate [OpenStreetMap](https://www.openstreetmap.org/) and
[Overture Maps](https://overturemaps.org/) as complementary evidence and
spatial infrastructure for a refreshed facility product. Neither automatically
supersedes an authoritative provincial or territorial record.

OpenStreetMap can contribute:

- independently mapped hospitals, clinics, pharmacies, social facilities,
  schools, child care, community services, entrances, addresses, operators,
  websites, opening hours, emergency status, accessibility attributes, and
  occasional capacity-related tags;
- building footprints and pedestrian, cycling, road, transit, and path
  connectivity around a facility; and
- candidate facilities, missing-attribute signals, and conflicts to send
  through review or community mapping rather than silently accepting.

Use bounded Overpass queries only for development and small study areas. For
reproducible province- or country-scale work, acquire a dated Canada or
provincial PBF extract, record its checksum and replication timestamp, and
process it locally. Never build bulk acquisition or geocoding on the public
Nominatim service. Preserve element type, OSM ID, version, timestamp, tags, and
the required OpenStreetMap attribution; do not assume an OSM object ID is a
permanent real-world facility identifier.

Overture can contribute cloud-queryable GeoParquet themes for:

- **places:** categorized health care, education, food, recreation, cultural,
  government, and business points with names, addresses, operating status,
  confidence, and property-level source lineage;
- **buildings:** conflated footprints and building attributes;
- **transportation:** routable road, rail, and water segments/connectors; and
- **addresses, divisions, and base:** candidate geocodes, contextual
  boundaries, land use, and environmental features where Canadian coverage
  and source quality are sufficient.

Overture's Global Entity Reference System identifiers and bridge files may
help track matched features across monthly releases. They are project
identifiers, not proof of authoritative identity. Pin the exact data and
schema release, checksums, source arrays, confidence, licences, attribution
files, and any bridge-file operations. Public Overture data releases are
retained for only a limited period, so a reproducible build must preserve an
authorized local input or independently archived artifact rather than relying
on an old cloud path.

Treat licensing at theme and source level. OpenStreetMap, Overture buildings,
and Overture transportation are ODbL; Overture places is multi-licensed,
including CDLA Permissive, Apache 2.0, and CC0 sources. Keep raw and normalized
layers separable, preserve source-specific notices, and obtain a licence
review before distributing a combined database whose derivation might trigger
ODbL share-alike obligations.

The proposed evidence model is:

1. **Authoritative record:** a current jurisdictional source establishes the
   facility and its official attributes.
1. **Corroborated record:** OSM or Overture independently supports identity,
   location, classification, or selected attributes.
1. **Candidate-only record:** an open-map feature has no authoritative match
   and remains visibly unconfirmed.
1. **Conflict:** sources disagree about identity, coordinates, type, status, or
   attributes and require review.
1. **Historical-only record:** an older LODE or other source is retained for
   lineage but not presented as current.

Start with a bounded Québec metropolitan-and-rural comparison of current
official health facilities against OSM and Overture. Measure authoritative
match rate, candidate precision after review, apparent omissions, duplicate
clusters, coordinate displacement, type agreement, attribute completeness,
urban/rural imbalance, and network connectivity. Repeat with one contrasting
province before proposing a national build. Do not infer capacity, service
availability, catchment, wait time, travel time, or operational status from a
mapped point or building alone.

## Deferred Decisions

No `0.7.3` outcome is committed. After the reference adapters, additional
public, local-provided, licensed, or restricted adapters may be added
incrementally whenever a concrete research question, maintainable source, and
data authority justify them. They need not wait for a special private-data
phase, and the framework does not guarantee that every candidate source will
be suitable.

Household/person/cohort attachment remains a conditional research project
regardless of whether the source is public or private. It requires a concrete
study, current source authority, harmonization and eligibility rules, a
reviewed weighting or statistical-matching method, representativeness and
uncertainty evidence, and human methods/privacy approval. Activities,
schedules, memberships, contact networks, and intervention scenarios likewise
require their own evidence and behavioural assumptions; they are not implied
by the enrichment contract.

## Acceptance Criteria

### `0.7.0`

- Unknown contract versions, invalid access classifications, unsafe paths, and
  incomplete geography namespaces are rejected.
- Every adapter executes through the common describe, acquire-or-reference,
  verify, normalize, align/link, validate, and publish-or-retain stages.
- A synthetic external dataset with no built-in adapter can enter through the
  normalized-layer contract and receive the same linkage, validation,
  provenance, and sidecar treatment.
- Authority and redistribution gates prevent a local, licensed, or restricted
  resource from being copied or emitted as though it were public.
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
- The August 2024 observation period, 2024 Business Register basis, and 2021
  DA namespace are preserved in the layer and manifest.
- Duplicate or malformed DA keys and any 2016-to-2021 join attempt fail
  clearly.
- Source coverage, base coverage, and unmatched records reconcile exactly.
- A synthetic end-to-end example reproduces the normalized layer and
  validation report without bundling RDC-controlled detailed Can-FED
  measures.

### `0.7.2`

- ODEF v3 acquisition, source version, 2024 collection period, national
  coverage, coordinate fields, and source identifiers are preserved.
- The source profile, acquisition, normalization, linkage, validation,
  limitations, and exact reproduction are independently testable.
- Duplicate and ungeocoded facilities, missing fields, and unmatched
  geographies reconcile explicitly.
- Documentation distinguishes facility observations from project-derived
  measures and does not imply unsupported capacity, catchment, quality,
  eligibility, accessibility, or causal conclusions.
