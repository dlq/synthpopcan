# Ecosystem Enrichment Implementation Plan

Status: planned\
Created: 2026-07-15\
Last updated: 2026-07-19\
Target: `0.7.0`–`0.7.3`\
Next action: complete safe source-level profiles for every private and public
candidate source before designing adapters or inspecting private records\
Roadmap: [PLANS.md](../PLANS.md) | [Plan index](README.md)

## Purpose

Extend a validated, geographically placed synthetic household/person
population with modular cohort, environmental, built-environment,
public-service, accessibility, activity, and network layers. Enrichment must
remain distinguishable from census calibration: it adds modeled attributes or
linked context without silently changing the already validated base population.

This work starts only after `0.6.x` provides durable runs, a stable versioned
linked-population schema, reproducible artifacts, and shared CLI/HTTP workflow
services.

## Source Inventory

### Private or access-controlled sources

The local ignored `data/private` cache currently contains these third-party
source families, all of which must be represented in the source inventory even
if later review concludes that a source cannot or should not be integrated:

Their presence is not evidence that SynthPopCan owns them, may use them for a
new purpose, may redistribute them, or will make them available to users. The
project makes no availability commitment for any third-party private source.
Any future support should normally operate on data independently supplied by an
authorized user in their own environment. Dataset-specific code, documentation,
fixtures, models, or derived outputs require separate written authority where
applicable.

| Source family | Initial role to investigate | Required gate before use |
| --- | --- | --- |
| CANUE | Postal-code-linked environmental and urban exposure measures | Data-use agreement, redistribution limits, temporal/geographic coverage, and linkage-risk review. |
| CPTP | Cohort/access-request family; usable analysis tables may require separate approval | Confirm available data, approved purpose, access status, variable dictionary, cohort universe, and publication constraints. |
| MAVAN | Maternal/child cohort attributes and outcomes | Ethics/access authority, representativeness, harmonization, weighting/matching, uncertainty, and disclosure review. |
| MoNNET | Neighbourhood/cohort measures, questionnaires, and location-bearing extracts | Data dictionary, coordinate sensitivity, permitted geography, cohort universe, temporal alignment, and disclosure review. |
| TOPO | Montréal youth and neighbourhood indicators plus health-service geographies | Methodology, aggregation level, boundary concordance, licence/access status, temporal alignment, and suppression rules. |

Generated benchmarks, model release assets, and small-area outputs also live
under `data/private`, but they are project artifacts rather than third-party
source families. Keep that distinction explicit in inventory reports.

Private-source rules:

- Never commit source files, record-level samples, exact private paths, secrets,
  access correspondence, or derived disclosure-sensitive values.
- Keep safe local-only manifests beside private sources; commit only generic
  adapter specifications, synthetic fixtures, and non-sensitive source labels.
- Record the authority, approved purpose, steward, access expiry, permitted
  transformations, publication rules, and destruction/retention obligations.
- Do not infer permission from a file being present locally.
- Do not advertise, package, upload, mirror, sublicense, or provide access to a
  third-party private source through SynthPopCan.
- Do not promise that an adapter, model, example, or derived public artifact
  will be delivered for any named private source.
- Require an explicit review before using coordinates, small cells, genetics,
  health outcomes, or other high-risk attributes.

### Public and authoritative sources

Maintain a discovery lane for any relevant public dataset available through
authoritative catalogues, including:

- [Open Government Canada](https://search.open.canada.ca/opendata/) as a primary
  federal catalogue that also indexes some provincial and territorial records;
- [Données Québec](https://www.donneesquebec.ca/) and its CKAN catalogue/API as
  a primary Québec and municipal discovery source;
- Statistics Canada and other authoritative federal sources;
- other Canadian provincial, territorial, Indigenous-government, municipal,
  public-health, education, and public-agency open-data portals;
- authoritative school, healthcare, public-service, food-environment,
  land-use/built-environment, road, transit, environmental, boundary, and
  accessibility resources.

Do not maintain a supposedly exhaustive hard-coded list of portals: it will
become stale and may exclude useful local or specialist authorities. Catalogue
providers belong in a versioned, extensible registry. “Public” and “open” mean
eligible for evaluation, not automatically suitable or automatically included.
Every candidate receives a source profile covering:

- authoritative publisher and canonical dataset/resource identifier;
- title, description, variables, unit of observation, and data dictionary,
  retaining authoritative English and French forms when available;
- source language availability plus translation status and provenance for each
  descriptive field, distinguishing official text from reviewed
  project-supplied translations;
- licence and attribution requirements, including modification and
  redistribution permissions;
- formats, API/resource URLs, update frequency, version, and temporal coverage;
- spatial coverage, geometry/geography, coordinate reference system, and
  concordance requirements;
- missingness, suppression, quality indicators, and known limitations;
- intended enrichment role and whether linkage is aggregate, spatial,
  probabilistic, or record-level;
- retrieval timestamp, response metadata, file size, and SHA-256 checksum.

A candidate advances to supported-source work only when its research relevance,
licence and attribution obligations, quality, geographic and temporal
alignment, version/update behaviour, and reproducible access have been reviewed.

Use catalogue APIs for reproducible discovery and metadata refresh. Download
or query selected resources on demand into ignored local caches such as
`data/raw`; do not mirror the whole catalogue. Package only tiny synthetic or
clearly redistributable test fixtures.

The initial public-source backlog must include the public/reconstructable
families previously kept out of `data/private`: Montréal school layers, food
environment layers, derived/rebuildable geography layers, and relevant health,
transport, road, land-use, and environmental datasets discoverable through
Données Québec or their authoritative publishers.

Treat Statistics Canada's
[Canadian Food Environment Dataset (Can-FED)](https://www150.statcan.gc.ca/n1/pub/13-20-0001/132000012022001-eng.htm)
as a first-class `0.7.1` public source rather than an unnamed example. Its
public dissemination-area measures are based on 2018 food-outlet data and are
intended for research on local food environments, dietary intake, and health
outcomes. The source profile must preserve that vintage, distinguish public
DA-level measures from more detailed restricted material, record outlet and
access-measure definitions, and prevent users from interpreting the layer as a
current inventory of individual establishments.

## Enrichment Contract

Each enrichment runs against an immutable identified base-population artifact
and writes a separate versioned layer or a new derived population with explicit
lineage. It must not overwrite the source population.

Every layer records:

- enrichment schema version and source-profile version;
- base-population run ID and checksums;
- person, household, geography, location, or network key roles;
- variable definitions, types, units, code lists, and missing-value rules;
- linkage method, parameters, random seeds, eligibility rules, and tie-breaking;
- matched, unmatched, multiply matched, and out-of-scope counts;
- weighting, calibration, uncertainty, and representativeness diagnostics;
- source licence/access classification and permitted output classification;
- validation results and an exact reproduction request.

Use stable language-neutral keys for machines and paired English/French display
metadata for people. A single-language upstream source may use an explicit
fallback, but missing French or English metadata must remain visible rather than
being silently treated as bilingual.

Prefer normalized linked tables over continually widening household/person
CSVs. Candidate table families include `locations`, `environment`, `services`,
`activities`, `cohort_attributes`, and `contacts`, keyed through stable public
synthetic identifiers and versioned geography/location identifiers.

## Release Slices

### 0.7.0: Source and enrichment foundation

- Complete safe profiles for every private source family and the first public
  catalogue candidates.
- Implement versioned source-profile and enrichment-manifest schemas.
- Define bilingual descriptive-metadata fields, language availability,
  authoritative-versus-project translation provenance, and deterministic
  fallback rules without localizing stable schema identifiers.
- Add CKAN catalogue discovery and metadata capture, beginning with Données
  Québec, plus Open Government Canada catalogue discovery; keep
  provider-specific code behind a generic catalogue interface and registry.
- Implement bounded, atomic, checksum-verified public-resource retrieval using
  the existing download safety posture.
- Define aggregate, spatial, probabilistic, and record-level linkage classes.
- Add reviewed fine-area placement primitives and boundary concordance reports.
- Prove through tests that enrichment cannot mutate the base population.
- Apply CARE principles and, where First Nations data or knowledge are in
  scope, OCAP-informed review alongside FAIR practice; record authority,
  collective benefit, control, responsibility, ethics, community expectations,
  and limits on reuse rather than treating open licensing as sufficient.

### 0.7.1: Spatial and environmental layers

- Profile and integrate the public Can-FED dissemination-area food-environment
  measures, including its 2018 source vintage, category/access definitions,
  geography linkage, missingness, and documented usage limits.
- Record safe source-level profiles for TOPO, MoNNET, and CANUE; implement
  dataset-specific support only if separately authorized and useful, without
  distributing their data.
- Add selected authoritative public geography, schools, healthcare/services,
  food, transport/roads, built-environment, and environmental sources.
- Produce normalized location/environment/service tables plus exposure and
  accessibility measures with uncertainty and unmatched-area reporting.
- Validate geography, temporal alignment, units, topology, and aggregation
  independently of the production join code.

### 0.7.2: Cohort attachment

- Record safe source-level profiles for MAVAN, CPTP, MoNNET, and other cohorts;
  implement dataset-specific support only under separate data-use, ethics,
  methods, and privacy authority, without distributing their data.
- Define variable harmonization, cohort eligibility, weighting, statistical
  matching/modeling, and extrapolation procedures.
- Preserve observed-versus-modeled status and never present attached values as
  census-observed facts.
- Publish aggregate utility, representativeness, uncertainty, privacy, and
  disclosure evidence without publishing restricted records.
- Require human methods/privacy approval before any cohort-derived public
  artifact or model is released.

### 0.7.3: Networks and scenarios

- Add modular schools, workplaces, healthcare, food-access, road/transport,
  activity, and contact-network layers.
- Represent interventions and scenarios as derived runs that preserve the
  original population and enrichment layers.
- Support reproducible comparisons, provenance, validation, and exports for
  downstream research/simulation tools.

## Acceptance Criteria

- Every third-party family currently under `data/private` has a safe source
  profile and an explicit locally support, defer, or reject decision with
  rationale; no decision implies redistribution or public availability.
- Public-source discovery is reproducible from catalogue metadata and does not
  depend on undocumented manual downloads.
- Every selected public resource has verified licensing, attribution,
  provenance, version, retrieval evidence, and geography/temporal coverage.
- Supported source profiles, data dictionaries, and user-facing enrichment
  metadata expose reviewed English and French text where available, declare
  single-language gaps explicitly, and pass metadata-parity tests.
- No private record or restricted derived value enters git, CI logs, public
  fixtures, documentation, releases, or telemetry.
- Enrichment layers retain stable linkage to the validated base population and
  cannot silently change its row counts, controls, identifiers, or provenance.
- Linkage, weighting, uncertainty, representativeness, and unmatched cases are
  independently validated and visible to users.
- Each release includes synthetic public fixtures and end-to-end reproduction
  tests for every supported enrichment class.
