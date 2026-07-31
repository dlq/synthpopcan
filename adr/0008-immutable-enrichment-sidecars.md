# ADR-0008: Add External Context Through Immutable Sidecars

- **Status:** Accepted (retrospective)
- **Date:** 2026-07-30
- **Decision owners:** Maintainers

## Context

Research questions often need environmental, facility, policy, survey, or
administrative context that is not part of the synthetic population model.
Writing those values directly into the household or person tables would blur
the distinction between generated population attributes and externally
observed or modelled context. It could also change a validated research object
without leaving evidence of what changed.

Sources differ in authority, licensing, geography, time, units, and linkage
quality. Local possession of a dataset does not establish permission to use,
publish, or redistribute it.

## Decision

External context is attached as a versioned **sidecar layer**. An enrichment
operation composes:

- a source profile describing authority, semantics, geography, time, and
  limitations;
- an immutable resource record with permitted locator information and
  checksums;
- a normalized layer with explicit keys and variables;
- validation evidence for coverage, duplicates, unmatched records, and
  method-specific limitations; and
- an enrichment manifest that links the layer to a versioned base population.

The operation records the base household and person hashes before and after
enrichment and fails if the base population changes. Geography-keyed layers use
the explicit identity from ADR-0007. Restricted or licensed resources may be
registered with opaque local identity; their paths and contents are not copied
into public artifacts.

## Alternatives Considered

- **Add columns directly to the base population:** rejected because it mutates
  a validated object and obscures which source produced each value.
- **Build a separate ad hoc importer for every source:** rejected because
  provenance, authority, validation, and publication gates must remain
  consistent across sources.
- **Record only the source URL or local path:** rejected because locations can
  change and local paths may disclose sensitive information; immutable resource
  identity requires checksums and revision metadata.
- **Treat access as permission:** rejected because access does not establish
  research authority or redistribution rights.

## Consequences

- Researchers join or interpret a sidecar explicitly rather than receiving a
  silently widened population table.
- Base-population validation and citation remain stable as new context layers
  are added.
- Enrichment requires more metadata before import, especially for local,
  licensed, or restricted sources.
- Cohort attachment, simulation behaviour, and source-specific adapters remain
  separately reviewed work; the generic framework does not make them valid by
  default.

## Evidence And Related Records

- [Ecosystem enrichment plan](../plans/2026-07-15-ecosystem-enrichment.md)
- [External-Data Enrichment](../docs/enrichment.md)
- [Getting Started With the Beginner API](../docs/library-getting-started.md)
- [`synthpopcan.enrichment`](../src/synthpopcan/enrichment.py)
- [`synthpopcan.api.enrich_population`](../src/synthpopcan/api.py)
