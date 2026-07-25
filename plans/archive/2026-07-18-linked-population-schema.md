# Linked Population Schema Implementation Plan

Status: archived; completed and released in `0.6.1`\
Created: 2026-07-18\
Completed: 2026-07-18\
Last updated: 2026-07-25\
Target: `0.6.1`\
Maintenance: governed by ADR-0003, the linked-schema documentation, and
regression tests; this archived plan owns no new work\
Roadmap: [PLANS.md](../../PLANS.md) | [Plan index](../README.md)

## Objective

Stabilize the public linked household/person/geography artifact contract without
freezing every demographic column emitted by a model. The contract must support
the beginner API, CLI model generation, durable prepared-model runs, small-area
calibration, future enrichment, and later simulator interchange.

## v1 decisions

- `households.csv` uses `synthetic_household_id` as its primary key.
- `persons.csv` uses `synthetic_person_id` as its primary key and
  `synthetic_household_id` as a required foreign key.
- Model-specific household and person attributes remain extensible.
- Optional geography is assigned on households and inherited by people.
- A descriptor records table paths, ordered columns, row counts, keys,
  relationships, and geography semantics.
- Existing workflow manifests embed the descriptor rather than changing their
  unrelated lifecycle/report schema versions.
- Unknown linked schema versions are rejected. Legacy paired CSVs may be
  validated and described as v1 only when they already satisfy v1 identifiers
  and relationships; identifier guessing is prohibited.

## Work stages

- [x] Inventory current library, CLI, prepared-model, durable-run, and
  small-area linked artifacts.
- [x] Define the v1 table, key, relationship, geography, and extension rules.
- [x] Implement shared descriptor construction, validation, reading, and
  writing.
- [x] Embed the descriptor in the principal linked-generation and calibration
  surfaces.
- [x] Add an explicit legacy-directory adoption helper that validates v1 keys
  and relationships without guessing or rewriting demographic columns.
- [x] Add bounded structural validation for uploaded model graphs, local-web
  household/person output limits, cancellation, forced termination, execution
  timeout, and stale-run recovery from the remaining `0.6.1` P2 backlog.
- [x] Exercise representative 2016 and 2021 hierarchical Census inputs through
  training, package loading, linked generation, v1 artifact writing, and
  relationship validation.
- [x] Audit and finish stale asynchronous browser-operation sequencing.
- [x] Run the complete correctness, documentation, browser, packaging, and
  installed-wheel gates before release.

## Completion evidence

- [`linked_schema.py`](../../src/synthpopcan/linked_schema.py) defines the v1
  version, keys, relationship, optional household geography, legacy adoption,
  and structural validation.
- [`test_linked_schema.py`](../../tests/test_linked_schema.py) covers descriptor
  construction and round trips, extension columns, invalid schemas and
  relationships, legacy adoption, and representative 2016/2021 generation.
- The
  [golden v1 descriptor](../../tests/fixtures/schemas/linked-population-v1.json)
  makes intentional contract changes reviewable.
- The [linked-population documentation](../../docs/linked-population.md)
  describes compatibility, migration, geography inheritance, and the
  distinction between schema conformance and statistical validity.
- The [`0.6.1` changelog entry](../../CHANGELOG.md#061---2026-07-18) records
  the released outcome.

Future compatible additions remain ordinary maintenance. Renaming stable keys,
changing relationship semantics, or requiring another table needs a new schema
version, migration path, and explicit review outside this archived plan.
