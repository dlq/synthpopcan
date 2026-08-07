# ADR-0011: Use A Simulator-Neutral Population Exchange

- **Status:** Accepted
- **Date:** 2026-08-07
- **Decision owners:** Maintainers

## Context

SynthPopCan produces linked household/person populations, but downstream
research models differ widely in their required land use, activities,
schedules, networks, states, coefficients, and executable configuration.
Selecting one simulator before a real consumer and pinned target contract exist
would add speculative semantics and maintenance cost. Publishing only two CSVs,
however, would omit the relationships, provenance, geography, validation, and
governance needed for a defensible handoff.

The project already has a stable linked-population v1 contract and durable-run
v1 evidence. The handoff should compose those records rather than rename their
identifiers or create a competing provenance system.

## Decision

SynthPopCan uses `synthpopcan-exchange-v1` as its initial downstream handoff.
It is a directory of unchanged UTF-8 household/person CSVs and JSON metadata:

- an exchange manifest with hashes, sizes, row counts, media types, access and
  redistribution classifications, geography and temporal context, limitations,
  and missing simulation inputs;
- a linked-population v1 descriptor;
- a complete column dictionary;
- standalone or successful durable-run provenance and an exact reproduction
  request; and
- creation-time validation evidence.

The bundle is always described as a **population contribution**, never as a
runnable simulation. Validation rejects undeclared, missing, changed,
misclassified, or structurally inconsistent files. Census geography requires
an explicit compatible vintage, level, namespace, and household identifier
column.

CSV and JSON remain the authoritative exchange v1 forms. Parquet, GeoParquet,
GeoPackage, RO-Crate, deterministic archives, and target-specific formats may
be added only as validated mappings with a demonstrated consumer. No
simulator-specific adapter is added before the `1.0.0` interface freeze.

## Alternatives Considered

- **Support one popular simulator immediately:** rejected because popularity
  does not supply a research question, stable contract, authorized fixture, or
  all non-population inputs.
- **Publish only household and person CSVs:** rejected because the recipient
  could not verify identifiers, relationships, meaning, provenance, governance,
  or byte integrity.
- **Adopt Parquet or a GIS container as the canonical form:** deferred because
  it adds dependencies and semantic conversions without a demonstrated benefit
  for the first consumer.
- **Use a broad research-object standard as the native contract:** deferred;
  RO-Crate can later map the tested native records, but should not replace
  domain validation or become a prerequisite for a plain file handoff.
- **Embed target defaults to make the bundle runnable:** rejected because this
  would silently invent behaviour and model semantics outside SynthPopCan's
  scope.

## Consequences

- Any downstream tool can read the authoritative files with standard CSV/JSON
  support and independently recompute integrity and linkage checks.
- The bundle is more verbose than a pair of CSVs, but the extra records travel
  with the artifact instead of depending on undocumented project knowledge.
- Users must classify access and redistribution honestly; hashes do not grant
  permission or certify disclosure safety.
- A target adapter must state every conversion, loss, default, and external
  prerequisite and must preserve the exchange provenance.
- Exchange v1 becomes a candidate persisted contract for the `1.x` stability
  inventory after experience during `0.8.x` and `0.9.x`.

## Evidence And Related Records

- [Portable Population Exchange](../docs/exchange.md)
- [Simulation interoperability plan](../plans/2026-07-15-simulation-interoperability.md)
- [Correctness assurance](../CORRECTNESS.md)
- [ADR-0001: Shared Python workflow core](0001-shared-python-workflow-core.md)
- [ADR-0003: Versioned linked-population schema](0003-versioned-linked-population-schema.md)
- [ADR-0007: Explicit Census geography identity](0007-explicit-census-geography-identity.md)
- [ADR-0010: Pre-1.0 compatibility evolution](0010-pre-1-0-compatibility-evolution.md)
