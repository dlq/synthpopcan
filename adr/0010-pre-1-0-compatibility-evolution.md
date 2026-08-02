# ADR-0010: Permit Deliberate Pre-1.0 Compatibility Breaks

- **Status:** Accepted
- **Date:** 2026-08-01
- **Amended:** 2026-08-02
- **Decision owners:** Maintainers

## Context

SynthPopCan is still defining durable contracts for linked populations, model
packages, control packs, and richer household and family structures. Preserving
every alpha-era interface could force misleading representations or unnecessary
complexity into the eventual stable design. At the same time, silent changes to
artifact meaning would make research workflows difficult to audit and could
invalidate published results.

The project therefore needs an explicit boundary between compatibility that is
useful during development and compatibility that would prevent a material
correctness or architectural improvement.

## Decision

Before `1.0.0`, SynthPopCan may make a deliberate breaking change when it
materially simplifies the architecture, improves correctness, or makes the
research model more honest. Backward compatibility is desirable, but is not a
release gate during this period.

Every deliberate compatibility break must:

- version any changed public schema, model package, control package, or other
  persisted contract;
- document what changed, why it changed, and the supported replacement path;
- reject unsupported old artifacts with a clear error rather than guessing,
  silently coercing, or reinterpreting their meaning;
- identify the last compatible software release when support is removed; and
- provide a migration tool or one-time converter when practical and when it can
  preserve meaning without inventing unavailable information.

Published artifacts, releases, checksums, DOIs, and archival records remain
immutable. A new contract or corrected artifact is published as a new version;
an existing published object is never rewritten in place.

At `1.0.0`, the project freezes the documented CLI command paths and options,
documented Python API symbols, and versioned persisted contracts explicitly
declared supported for the `1.x` line. Later minor releases may add interfaces
and new versioned schemas. Removing a frozen interface or changing its meaning
requires a documented deprecation where practical and a new major version.
Internal modules, undocumented helpers, web presentation details, external
source catalogues, and research findings are not part of that freeze.

Before the freeze, the project must publish and test an explicit supported
surface inventory. `1.0.0` is a stability claim about the bounded supported
core, not a claim that every planned field, geography, population universe,
method, enrichment, or downstream adapter has been implemented.

This decision does not itself authorize a particular schema or architecture.
Consequential replacement contracts still require their own design review and,
where appropriate, a new ADR that supersedes the earlier decision.

## Alternatives Considered

- **Require complete backward compatibility immediately:** rejected because it
  could preserve weak alpha-era abstractions and make correctness improvements
  disproportionately expensive before the public contracts are mature.
- **Allow unversioned breaking changes:** rejected because consumers could not
  distinguish an intentional new contract from corruption or accidental
  reinterpretation.
- **Defer all improvements until `1.0.0`:** rejected because reaching a stable
  release requires exercising and correcting the contracts that will become
  stable.
- **Rewrite published artifacts when contracts improve:** rejected because it
  would break provenance, checksums, citations, and reproducibility.

## Consequences

- Near-term interfaces may change, and alpha users must consult release and
  migration notes when upgrading.
- Maintainers must treat versioning, explicit failure, and migration guidance
  as part of implementing a breaking change rather than as follow-up work.
- Compatibility layers are retained only when their value exceeds their
  complexity and risk.
- Published research artifacts remain reproducible even when current software
  no longer reads them directly.
- The chained-model, family-hierarchy, and multi-margin control designs remain
  open until their plans produce decisions with enough evidence to accept.

## Evidence And Related Records

- [Project plans and compatibility policy](../PLANS.md)
- [Expanded hierarchical tree-model plan](../plans/2026-08-01-expanded-hierarchical-tree-models.md)
- [Expanded small-area controls plan](../plans/2026-08-01-expanded-small-area-controls.md)
- [ADR-0003: Use a versioned linked-population schema](0003-versioned-linked-population-schema.md)
- [ADR-0006: Define canonical release and archive authorities](0006-canonical-release-and-archive-authorities.md)
- [Release process](../RELEASING.md)
