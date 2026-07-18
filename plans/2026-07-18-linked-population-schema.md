# Linked Population Schema Implementation Plan

Status: release candidate validated\
Created: 2026-07-18\
Last updated: 2026-07-18\
Target: `0.6.1`\
Next action: commit and tag the validated release candidate\
Roadmap: [PLANS.md](../PLANS.md) | [Plan index](README.md)

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

## Acceptance criteria

- All supported linked-output paths declare the same schema version and key
  relationship.
- Additional demographic columns remain valid and round-trip unchanged.
- Missing keys, invalid geography declarations, unknown schema versions, and
  broken household relationships fail clearly.
- Golden fixtures make intentional schema changes reviewable.
- Both supported hierarchical Census vintages enter the same stable key and
  relationship contract while retaining their vintage-specific extension
  columns.
- Public documentation distinguishes schema conformance from statistical
  validity, provenance quality, and disclosure safety.
