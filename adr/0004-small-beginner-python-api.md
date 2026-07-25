# ADR-0004: Maintain A Small Beginner-Facing Python API

- **Status:** Accepted (retrospective)
- **Date:** 2026-07-25
- **Decision owners:** Maintainers

## Context

The project serves humanities and digital-humanities researchers who may begin
in a notebook, as well as advanced users who need control over method-specific
objects. Exposing every implementation module at the package root would make
discovery harder and imply a stability commitment for internal and specialist
interfaces.

## Decision

The `synthpopcan` package root re-exports a deliberately small,
beginner-friendly API from `synthpopcan.api`. It covers common file reading,
IPF, prepared-model generation, linked outputs, small-area calibration, and
output writing.

Advanced research code imports from the module that owns the concept, such as
`synthpopcan.ipf`, `synthpopcan.controls`, or `synthpopcan.tree`. CLI, web,
console, and underscored implementation objects are adapters or internals, not
alternate public library entry points.

## Alternatives Considered

- **Export most library objects at package level:** rejected because it would
  overwhelm beginner discovery and make ownership unclear.
- **Require all users to import implementation modules:** rejected because
  introductory notebooks benefit from one coherent workflow vocabulary.
- **Expose only the CLI:** rejected because notebooks and reproducible Python
  pipelines are important research environments.

## Consequences

- The top-level `__all__` is a meaningful compatibility boundary and should
  remain documented and tested.
- Adding a top-level name requires evidence that it belongs in common beginner
  workflows.
- Advanced module APIs can be more explicit and specialized, but documented
  changes still require normal compatibility care.
- Examples should use the beginner API until they genuinely need lower-level
  control.

## Evidence And Related Records

- [Getting Started With the Beginner API](../docs/library-getting-started.md)
- [Advanced Library Use](../docs/library.md)
- [`src/synthpopcan/__init__.py`](../src/synthpopcan/__init__.py)
- [`src/synthpopcan/api.py`](../src/synthpopcan/api.py)
