# ADR-0007: Make Census Geography Identity Explicit

- **Status:** Accepted (retrospective)
- **Date:** 2026-07-30
- **Decision owners:** Maintainers

## Context

A short Census geography code is meaningful only within a particular Census
vintage, geography level, and identifier system. The same-looking value may
refer to a different universe in another product or year. Prefix matching can
also misrepresent relationships that Statistics Canada publishes explicitly.

Small-area calibration, national batch planning, mapping, and external-data
enrichment all need to establish that their boundaries, controls, and output
rows describe the same places. A filename or a column named `GEOUID` is not
enough evidence.

## Decision

Every geography-bearing request, selection, manifest, layer, and join identifies
its Census geography with:

- a Census vintage;
- a geography level;
- an identifier namespace; and
- the identifier in that namespace.

Together, these fields form the canonical geography identity. We retain short
identifiers and DGUIDs when the source provides both, but we do not invent one
from the other.

Geography collections also declare their universe: the geographic coverage,
selection method, authoritative product, and relevant parent geography.
Cross-level and parent-child selection uses an authoritative relationship
product when one exists. The software rejects unknown, ambiguous,
cross-vintage, or cross-namespace joins instead of guessing.

## Alternatives Considered

- **Use the short identifier alone:** rejected because its meaning depends on
  unstated product and vintage context.
- **Use DGUID alone:** rejected because not every input provides one, and a
  DGUID does not by itself document the selected universe or source product.
- **Infer relationships from identifier prefixes:** retained only as an
  explicit expert or reproduction interface where documented; it is not the
  general geography contract.
- **Infer relationships spatially from boundaries:** rejected as the default
  because authoritative relationship files are more reproducible and avoid
  hidden geometric judgments.

## Consequences

- Requests and artifacts carry more metadata, but another researcher can
  identify the geography they describe.
- Apparently compatible tables may be rejected until their vintage, namespace,
  and universe are made explicit.
- National DA and ADA workflows can reconcile profile, relationship, and
  boundary universes before fitting any population.
- Cross-vintage concordance is a separate reviewed method, not an implicit
  string join.

## Evidence And Related Records

- [Small-area geography plan](../plans/2026-07-22-small-area-geography.md)
- [Small-Area Linked Synthesis](../docs/small-area.md)
- [External-Data Enrichment](../docs/enrichment.md)
- [`synthpopcan.geography`](../src/synthpopcan/geography.py)
- [`synthpopcan.national_small_area`](../src/synthpopcan/national_small_area.py)
