# ADR-0009: Separate Display Geometry From Analytical Boundaries

- **Status:** Accepted (retrospective)
- **Date:** 2026-07-31
- **Decision owners:** Maintainers

## Context

Canonical Statistics Canada boundary products can be large enough to make a
self-contained interactive national map slow to build, transfer, and open.
Reducing coordinate detail makes presentation practical, but simplified
geometry may no longer preserve measurements, coastline detail, or every
property needed for analytical selection and reconciliation.

Bundling every prepared boundary in the Python wheel would make ordinary
installation unnecessarily large. Fetching an unversioned convenience file
would instead make a map difficult to reproduce or audit.

## Decision

Canonical analytical boundaries and prepared display boundaries are different
research artifacts with different uses:

- canonical publisher-derived geometry remains the authority for geographic
  selection, relationships, reconciliation, and spatial measurement; and
- simplified display geometry is used only to render maps.

Prepared display assets are published outside the Python wheel in a separately
versioned geodata release. A versioned catalogue gives each asset an exact
Census year, geography level, optional PRUID scope, immutable release URL,
representation, compressed checksum, and unpacked checksum.

The runtime selects only an exact catalogue match, verifies both byte
representations, installs atomically into a user cache, and reuses only a
checksum-valid file. Maps may fall back to canonical geometry when a prepared
asset is unavailable, but display geometry must never silently replace the
canonical analytical input in planning or calibration.

## Alternatives Considered

- **Bundle display boundaries in the wheel:** rejected because large national
  assets would burden every installation, including users who never make maps.
- **Use canonical geometry for every map:** retained as a fallback, but rejected
  as the only route because repeated simplification and large embedded output
  make national presentation unnecessarily expensive.
- **Publish files without a catalogue:** rejected because filenames alone do
  not establish geography identity, scope, representation, or integrity.
- **Replace canonical files after simplification:** rejected because a display
  optimization must not alter the analytical research object.

## Consequences

- Mapping has a smaller, reusable, integrity-checked geometry path without
  adding large wheel assets.
- Research provenance must name both the canonical analytical boundary and any
  prepared display asset used for presentation.
- A valid checksum proves byte identity, not compatibility with a population's
  geography universe or suitability for a substantive spatial operation.
- Every geodata release requires a deterministic catalogue and coverage audit
  independent of the software release process.

## Evidence And Related Records

- [Prepared Display Boundaries](../docs/geodata.md)
- [Small-Area Linked Synthesis](../docs/small-area.md)
- [Correctness Assurance](../CORRECTNESS.md)
- [`synthpopcan.geodata`](../src/synthpopcan/geodata.py)
- [`synthpopcan.map_render`](../src/synthpopcan/map_render.py)
- [Current roadmap](../PLANS.md)
