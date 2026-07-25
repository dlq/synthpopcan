# Small-Area Geography Implementation Plan

Status: active\
Created: 2026-07-22\
Last updated: 2026-07-25\
Target: `0.7.0`, with later expansion gated by evidence\
Next action: define the geography identity contract and prove one bounded
Québec 2016 DA workflow\
Roadmap: [PLANS.md](../PLANS.md) | [Plan index](README.md)

## Purpose

Make Census geography an explicit data and research contract rather than a
filename, identifier prefix, or incidental column. Preserve the current CT,
ADA, and CSD workflows while adding only the DA support needed for a reviewed
small-area proof and the first geography-keyed enrichment.

This plan owns geography identity, authoritative relationships, selection, and
small-area execution. The
[enrichment plan](2026-07-15-ecosystem-enrichment.md) consumes that contract;
it does not redefine it.

## Current Baseline

The codebase already provides:

- linked small-area calibration, realization, validation, and mapping;
- explicit 2016 and 2021 Census Profile adapters;
- 2016 CT, ADA, DA, CSD, CD, and province/territory boundary registrations;
- 2021 CT, ADA, and CSD boundary registrations;
- national 2021 CT, ADA, and CSD boundary data and a 2021 Dissemination
  Geographies Relationship File; and
- a 2016 national DA Census Profile resource.

Those assets do not yet form one proven DA workflow. In particular, coverage
differs by Census vintage, geography identity is not a uniform request
contract, and matching-looking codes must not be treated as interchangeable
across vintages.

## Geography Contract

Every geography-bearing request, manifest, layer, and join must identify:

- `census_vintage`;
- `geography_level`;
- `identifier_namespace`;
- the short identifier and DGUID when the source supplies both;
- parent or selection geography, where applicable;
- authoritative product, release date, and resource checksum; and
- selection or relationship method.

The canonical identity is the tuple of vintage, level, namespace, and
identifier. A bare `DAUID`, `CTUID`, or other short code is insufficient
outside a resource whose other fields establish that context.

Reject rather than guess when:

- Census vintages differ;
- levels or namespaces differ;
- a relationship is missing, ambiguous, or unsupported; or
- a boundary and control table do not describe the same geography universe.

Direct identifiers and prefix filters may remain expert and reproduction
interfaces, but beginner interfaces should use structured selections.

## `0.7.0` Work

### 1. Version the identity and relationship records

- Define and validate the geography identity payload.
- Add it to small-area requests, run manifests, outputs, validation reports,
  maps, and the source/enrichment contracts.
- Preserve DGUIDs and source short identifiers without synthesizing either.
- Build only the relationship records required by the Québec 2016 DA proof
  from authoritative Statistics Canada files.
- Emit explicit unmatched, ambiguous, and vintage-mismatch reports.
- Add migrations or compatibility handling for current manifests where
  necessary; do not silently reinterpret an old identifier.

### 2. Prove a bounded Québec 2016 DA workflow

Use public, release-pinned inputs and include at least one metropolitan and one
rural study area. Exercise:

1. profile, boundary, and relationship retrieval with hashes;
1. universe and category reconciliation;
1. candidate preparation;
1. household and, where supported, joint-person calibration;
1. integer realization and linked-population validation;
1. target- and parent-level residual reporting; and
1. bounded map generation.

Record runtime, peak memory where practical, artifact sizes, unmatched
geographies, suppression/missing-data handling, convergence, rare categories,
structural-zero findings, and disclosure cautions. A numerically successful
fit is not accepted if geography or household linkage checks fail.

### 3. Add regression evidence

- Use small deterministic public fixtures in the default test suite.
- Keep any live publisher retrieval or larger province-scale exercise
  explicitly opt-in and cacheable.
- Test cross-vintage rejection, duplicate and unknown geography identifiers,
  missing boundaries, and unsupported relationships.
- Test equivalent structured and direct-identifier selections.
- Pin a reviewed golden manifest and report schema, not a large generated
  population.

### 4. Document level choice

Explain that:

- CT supports tracted CMAs/CAs rather than national coverage;
- ADA is a population-balanced wall-to-wall geography;
- CSD represents municipalities or municipal equivalents and often fits
  service or policy questions;
- DA is finer and wall-to-wall but costlier and more exposed to sparse or
  suppressed controls; and
- DB is primarily a placement/relationship geography unless a source provides
  suitable controls.

Record the selected level and research rationale in run provenance. Do not
present CT, ADA, CSD, DA, and DB as a universally simple nesting hierarchy.

## Deferred And Gated Expansion

The following are not `0.7.0` commitments:

- country-wide DA synthesis;
- 2021 DA profile/boundary parity merely for symmetry;
- automatic 2016/2021 DA concordance;
- arbitrary-polygon selection;
- a complete cross-product relationship graph among all Census geographies;
  or
- a monolithic national fit.

If real research use justifies national DA execution, design restartable
province/territory batches with per-batch manifests, checkpoints, resource
bounds, and aggregate validation. Cross-vintage harmonization and
user-supplied polygon intersection each require separately reviewed methods.

## Completion Criteria

- The canonical identity is present and validated wherever geography affects a
  `0.7.0` result.
- Unsupported and cross-vintage joins fail with actionable diagnostics.
- The public Québec 2016 DA proof passes control, linkage, geography, resource,
  mapping, and reproducibility checks for metropolitan and rural cases.
- The enrichment layer can consume the identity contract without duplicating
  geography logic.
- Documentation states supported coverage and limitations without implying
  national DA readiness.
