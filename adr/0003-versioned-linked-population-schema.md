# ADR-0003: Use A Versioned Linked-Population Schema

- **Status:** Accepted (retrospective)
- **Date:** 2026-07-25
- **Decision owners:** Maintainers

## Context

Prepared-model generation, small-area calibration, validation, the beginner
API, and future simulator exchange all need to identify households and people
consistently. Model-specific demographic columns must remain extensible, but
keys and relationships cannot be inferred safely from filenames or similar
column names.

## Decision

The public linked-population contract is versioned independently of unrelated
workflow manifests:

- `households.csv` uses `synthetic_household_id` as its primary key;
- `persons.csv` uses `synthetic_person_id` as its primary key and
  `synthetic_household_id` as a required foreign key;
- optional geography is assigned to households and inherited by their people;
- model-specific demographic columns remain extensible; and
- a descriptor records paths, ordered columns, row counts, keys,
  relationships, and geography semantics.

Unknown schema versions are rejected. Existing paired files can be described as
version 1 only when they already satisfy its identifiers and relationships;
SynthPopCan does not guess identifiers or silently rewrite their meaning.

## Alternatives Considered

- **Freeze every output column:** rejected because models legitimately expose
  different attributes.
- **Infer keys and relationships:** rejected because a plausible guess can
  silently corrupt household/person linkage.
- **Assign geography independently to people:** rejected because it could
  separate household members and violate household-first calibration.
- **Reuse a workflow-manifest version:** rejected because artifact and run
  lifecycle contracts evolve for different reasons.

## Consequences

- Consumers can validate structural compatibility without knowing every
  demographic field.
- Schema changes require explicit versioning and compatibility review.
- Household geography is authoritative for linked people.
- Legacy adoption remains deliberately strict.

## Evidence And Related Records

- [Linked population schema plan](../plans/archive/2026-07-18-linked-population-schema.md)
- [Linked Population Outputs documentation](../docs/linked-population.md)
- [`src/synthpopcan/linked_schema.py`](../src/synthpopcan/linked_schema.py)
