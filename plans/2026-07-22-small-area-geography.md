# Small-Area Geography Implementation Plan

Status: planned and partially implemented\
Created: 2026-07-22\
Last updated: 2026-07-22\
Target: staged work after `0.6.2`, before DA-dependent enrichment\
Next action: prove a bounded province-scale DA workflow with matching controls,
boundaries, relationship metadata, validation, and resource estimates\
Roadmap: [PLANS.md](../PLANS.md) | [Plan index](README.md)

## Purpose

Make geography an explicit research and data contract rather than a filename,
identifier prefix, or universal choice of small-area level. Preserve the
existing CT, ADA, and CSD workflows while adding a verified DA path and the
metadata needed to select, relate, validate, and reproduce Census geographies.

## Current Baseline

SynthPopCan currently supports linked small-area calibration and mapping, 2016
and 2021 Census Profile adapters, national 2021 CT, ADA, and CSD boundary
preparation, and the 2021 Dissemination Geographies Relationship File. CTs are
useful inside tracted metropolitan areas, ADAs provide moderately local
wall-to-wall coverage, and CSDs represent municipalities or municipal
equivalents. A verified national DA profile-and-boundary workflow remains open.

Keep control, boundary, relationship, candidate, and output vintages aligned.
Never assume CT, ADA, CSD, and DA form one simple nested hierarchy.

## Geography Strategy

- **CT:** retain for detailed work inside tracted CMAs and CAs; do not present
  it as national coverage.
- **ADA:** retain for population-balanced, wall-to-wall provincial and national
  calibration when DA detail is unnecessary or too costly.
- **CSD:** use for municipal policy, service delivery, healthcare, education,
  food access, facility capacity, and related administrative questions.
- **DA:** add for fine placement and accessibility questions where aggregation
  would hide meaningful local variation, including rural areas without CTs.
- **DB:** use as a placement or geographic relationship layer only where its
  limited published attributes support the task; do not imply full Census
  controls exist at DB level.

The selected level and its research rationale belong in run provenance.

## Workstreams

### Structured geography selection

Replace prefix knowledge as the primary interface with a request that records:

- Census vintage;
- parent region level and identifier;
- requested output geography level;
- short identifiers and DGUIDs where available; and
- the authoritative product and relationship-file versions used.

Direct identifier and prefix filters may remain available for advanced and
reproduction workflows, but beginner interfaces should not require users to
infer the geography hierarchy from code strings.

### Official relationship index

Convert supported Statistics Canada geographic attribute and relationship
files into a versioned, validated local index. Support auditable traversal among
available province/territory, CMA/CA, CD, CSD, CT, ADA, DA, and DB identifiers
without inventing containment where the official relationships do not provide
it. Report unmatched, ambiguous, vintage-mismatched, and unsupported joins.

After coded relationships and vintage checks are reliable, investigate a local
operation that selects Census geographies intersecting user-supplied GeoJSON.
Treat cross-vintage boundary harmonization as a separate reviewed method.

### Province-scale DA proof

For one representative province, implement and verify bounded:

1. authoritative profile and boundary retrieval;
1. control extraction and universe/category reconciliation;
1. linked-candidate preparation;
1. household and optional joint-person calibration;
1. integer realization, mapping, and multi-scale validation; and
1. runtime, memory, map-size, suppression, and disclosure-risk reporting.

Include at least one rural area and one metropolitan area. A successful fit is
not sufficient if geography joins, rare categories, or household links fail.

### National orchestration

Build country-wide DA execution as restartable province/territory batches with
per-batch manifests, checkpoints, diagnostics, and bounded artifacts. Produce
an aggregate national validation report after all accepted batches complete.
Do not implement national synthesis as one monolithic fit.

### Validation and guidance

Report results at the target geography and at appropriate CSD/CMA,
province/territory, and national aggregates. Include error distributions,
rare-category results, convergence, structural-zero findings, linkage checks,
unmatched geographies, resource use, and disclosure cautions.

After CSD and DA workflows have representative performance and correctness
evidence, provide user-facing guidance for choosing among CT, ADA, CSD, and DA.

## Completion Criteria

- A structured geography request can reproduce an equivalent direct-identifier
  workflow and records the selected vintage, region, level, and rationale.
- The relationship index is built from authoritative files, preserves DGUIDs,
  and rejects unsupported or cross-vintage joins clearly.
- A province-scale DA workflow passes control, linkage, geography, resource,
  mapping, and disclosure checks on reviewable public inputs.
- National execution can resume by province or territory and aggregates
  accepted diagnostics without loading the complete population in memory.
- Documentation explains the geographic choice and limitations without
  presenting one level as universally correct.
