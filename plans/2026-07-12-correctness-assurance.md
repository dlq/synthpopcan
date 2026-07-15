# Correctness Assurance Implementation Plan

Status: active\
Created: 2026-07-12\
Last updated: 2026-07-15\
Target: `0.5.1` current-architecture correctness gate\
Next action: verify the completed P1 and release-safety P2 tranche through the
`0.5.1` release gate, record its evidence, and prepare release metadata\
Roadmap: [PLANS.md](../PLANS.md) | [Plan index](README.md)

## Purpose

Build evidence that SynthPopCan's numerical results, generated distributions,
linked records, and small-area artifacts are correct. Coverage, branch tests,
schema checks, reproducibility, and successful command execution remain useful,
but they do not by themselves demonstrate mathematical, statistical, or
structural correctness.

The correctness suite should combine:

- independently calculated reference fixtures;
- mathematical and structural invariants;
- differential checks between equivalent implementations;
- metamorphic checks under transformations that should preserve results;
- statistical acceptance tests for generated distributions;
- end-to-end reconciliation of artifacts read back from disk.

Production report builders must not be the sole validators of production
output. Tests should independently aggregate emitted artifacts wherever
practical so that a defect in calculation and reporting cannot validate itself.

## Scope

This plan covers:

- pure-Python and NumPy IPF;
- deterministic integerization and expanded rows;
- frequency and CART model training and generation;
- linked household/person generation;
- household-only and joint small-area calibration;
- realized household/person CSVs and reports;
- versioned public reference workflows.

It does not replace:

- unit tests for parsing, validation, and error handling;
- architecture and module-boundary tests;
- performance benchmarks;
- browser interaction tests;
- opt-in live tests for external API drift;
- privacy and disclosure-risk review.

## Release Allocation

`0.5.1` owns all six workstreams in this plan for code and artifact paths that
exist today. Its release gate includes:

- independent or differential evidence for the current numerical kernels;
- generated invariant and metamorphic tests for IPF and integerization;
- probability oracles and fixed-seed semantic round trips for current frequency
  and CART models;
- linked-record integrity across current in-memory and CSV paths;
- independent reconciliation of current small-area CSV and report artifacts;
- tiny known-truth workflows, one public versioned StatCan-derived fixture, and
  installed-wheel correctness smoke tests;
- deterministic pull-request checks plus the larger scheduled and pre-release
  tiers defined below.

Later releases must add regression evidence for behavior introduced by their
own architecture. The `0.6.x` runtime therefore retains acceptance checks for
durable job cancellation and recovery, new CLI/HTTP service parity, incremental
artifact writing, and chunk-size independence. Those checks cannot run against
`0.5.1` because those execution paths do not exist yet; they do not justify
deferring checks of the current algorithms or artifacts.

### `0.5.1` correctness dashboard

| Workstream | State | Remaining release work |
| --- | --- | --- |
| 1. IPF numerical correctness | Core complete | Consolidate known-truth fixtures under Workstream 6. |
| 2. Integerization correctness | Core complete | Generated Python properties, finite-weight checks, realized residuals, and Python/browser parity are implemented. Retain regression coverage as output paths evolve. |
| 3. Prepared-model correctness | Core complete | Analytical frequency probabilities, multi-seed thresholds, CART leaf/probability comparison, invalid weights, and semantic round trips are implemented. |
| 4. Linked-population invariants | Core complete | Both model families now have deterministic identifier, relationship, inherited-condition, privacy-column, validation, and in-memory/CSV equivalence checks. |
| 5. Small-area reconciliation | Core complete | Household-only, joint, multi-geography, subsampled, non-converged, serial/parallel, geography-isolation, and realized-residual oracles are implemented; structural-zero preflight remains covered as a blocking input case. |
| 6. Reference workflows | Core complete | Tracked microdata/WDS tutorial fixtures, tiny known-truth workflows, a pinned and independently documented public StatCan WDS fixture, isolated installed-wheel proof, and retained JUnit reports are implemented. |

## Public Assurance And Evidence Publication

Status: first public assurance layer implemented for `0.5.1`.

Completed:

- [x] Publish a bounded claims-to-evidence matrix in `CORRECTNESS.md`, with
  direct links to tests and fixtures and a limitation beside every claim.
- [x] Link correctness evidence from the README and rendered documentation and
  expose the scheduled workflow status through a public badge.
- [x] Test the normal Python gate on Python 3.11 and 3.12 and retain
  commit-specific JUnit reports for both versions.
- [x] Run larger generated-case/model ensembles weekly and before package
  publishing, with a separate scheduled live StatCan interface-drift check.
- [x] Require an isolated installed-wheel correctness smoke test before trusted
  publishing and document scoped release-note language.

Planned evidence improvements:

- [ ] Emit a machine-readable per-run assurance manifest with the SynthPopCan
  version, input checksums, seeds, settings, convergence, requested/fitted/
  realized residuals, unsupported cells, and linked-integrity findings.
- [ ] Add Hypothesis-generated cases with failure shrinking and mutation
  testing to measure whether the suite detects deliberately introduced kernel
  and report defects.
- [ ] Add frozen cross-version semantic fixtures and more independently
  reviewed public reference workflows, including multi-dimensional and linked
  household/person cases.
- [ ] Add macOS and Windows compatibility jobs for supported workflows.
- [ ] Attach permanent correctness reports, checksums, dependency provenance,
  and build attestations to each GitHub Release rather than relying on expiring
  Actions artifacts.
- [ ] Commission or invite an external methods/code review and publish its
  scope, findings, limitations, and project responses.

## Workstream 1: IPF Numerical Correctness

Status: core differential and metamorphic suite implemented for `0.5.1`;
known-truth consolidation remains under Workstream 6.

Add differential tests that generate many small feasible tables, run both
`fit_ipf` and `fit_ipf_numpy`, and compare:

- fitted weights;
- fitted totals for every control cell;
- maximum absolute residual;
- convergence state;
- iteration count where both contracts require the same behavior.

Test the intentional unsupported-cell behavior difference separately: the
general fitter raises when a positive cell has no remaining support, while the
repeated-geography NumPy fitter currently reports non-convergence so one bad
geography does not abort all fits.

For every converged result, assert these invariants:

- all weights are finite and non-negative;
- every fitted control cell is within the requested tolerance;
- each margin total reconciles with its target total;
- multiplying every control by a positive constant multiplies fitted weights by
  the same constant;
- reordering seed records does not change aggregate fitted results;
- renaming categories consistently does not change numerical results;
- equivalent duplicated records preserve aggregate fitted totals.

Include independently solved fixtures for:

- balanced 2x2 one-way margins;
- a sparse but feasible table;
- zero-valued target cells;
- incompatible totals;
- a positive target with no seed support;
- non-convergence under a deliberately small iteration limit;
- non-uniform starting weights.

## Workstream 2: Integerization Correctness

Status: core complete for current `0.5.1` paths; deterministic generated Python
properties, finite-weight rejection, realized residual checks, and browser
parity fixtures are implemented.

Use generated non-negative weight vectors to assert:

- every returned count is a non-negative integer;
- `sum(counts) == round(sum(weights))`;
- zero-weight records are never selected;
- results are deterministic;
- cumulative systematic-sampling discrepancy remains within its mathematical
  bound;
- expanded records reproduce the integer counts exactly;
- source and synthetic identifiers remain unique and traceable;
- empty, all-zero, highly fractional, and very large weights behave correctly.

Reaggregate integerized output separately from fractional fitted weights. Verify
that reports present both sets of residuals correctly and do not describe a
fractionally converged fit as an exact realized match.

## Workstream 3: Prepared-Model Correctness

Status: core complete for current `0.5.1` frequency and CART paths.

### Frequency models

Train from weighted fixtures with analytically known conditional probabilities.
Assert that the serialized groups, support values, global fallback, and outcome
probabilities match the independent calculations exactly.

Generate sufficiently large fixed-seed samples and require category proportions
to remain within predefined statistical bounds. Use several fixed seeds or a
seed ensemble rather than accepting one favorable draw.

Exercise:

- exact, partial, unknown, and empty conditions;
- group fallback and global fallback;
- weighted training rows;
- multiple target columns;
- zero and sparse outcome support.

### CART models

For a matrix of conditioning values, compare the serialized model's traversal,
selected leaf, and class probabilities with the original scikit-learn estimator.
This independently checks the custom serializer and runtime traversal.

### Round trips

For both model families, require write/read round trips to preserve model
semantics and generated rows for a fixed seed. Semantic checks should be primary;
avoid brittle byte snapshots for harmless formatting or dependency metadata.

## Workstream 4: Linked-Population Invariants

Status: core complete for current `0.5.1` in-memory and CSV generation across
both model families. Add incremental and chunk-size equivalence when those
paths are introduced in `0.6.x`.

Exercise mixed household sizes, multiple conditions, fallback groups, both model
families, and streamed generation. Assert:

- household and person identifiers are unique;
- every person references exactly one emitted household;
- every household receives exactly the number of people named by its household
  size;
- person rows inherit the relevant household conditions consistently;
- no source identifiers or raw training rows appear in generated artifacts;
- in-memory and streamed CSV generation produce equivalent rows and summaries;
- generation remains deterministic for a fixed seed.

Test invalid sizes, orphaned people, duplicate identifiers, unknown households,
missing conditioning values, and incompatible household/person model packages.

## Workstream 5: Small-Area Reconciliation

Status: core complete for current `0.5.1` paths; independent household-only,
joint, multi-geography, subsampled, non-converged, serial/parallel,
geography-isolation, and realized-residual checks are implemented, with
structural zeros blocked during preflight. Add durable-job and
incremental-writing failure semantics when those paths are introduced in
`0.6.x`.

Independently read emitted household and person CSVs and aggregate them without
calling SynthPopCan report helpers. Compare the resulting totals with:

- household controls;
- optional person controls;
- assigned counts by geography;
- fractional fit residuals;
- integerized realization residuals;
- the values written to the JSON report.

Verify geography isolation:

- no household or person leaks between target geographies;
- each person references a household in the same geography;
- household member counts remain correct after replication;
- inherited household attributes remain consistent on person rows;
- generated identifiers remain unique across all geographies.

Exercise:

- household-only and joint household/person calibration;
- full-pool and subsampled calibration;
- independent generation and subsample seeds;
- one and many target geographies;
- structural zeros and sparse support;
- incompatible control totals and missing categories;
- explicit non-convergence;
- non-uniform candidate starting weights;
- household-size grouping;
- candidate pools with and without person rows.

Require single-worker and parallel calibration to produce equivalent artifacts.
Require in-memory, streaming, and CSV realization paths to produce equivalent
rows and summaries. Failed or non-converged runs must not expose partial files as
successful output.

## Workstream 6: Reference Workflows

Status: core complete for the `0.5.1` pre-release gate.

Track tiny public "known truth" fixtures with independently calculated expected
results for:

- balanced and sparse IPF;
- incompatible IPF controls;
- household-only small-area calibration;
- joint household/person calibration;
- two-geography linked realization;
- frequency-model conditional generation;
- CART serialization and generation.

Add one public, versioned StatCan-derived fixture whose transformations, selected
categories, reconciled totals, and expected outputs were calculated
independently. Use live StatCan tests to detect endpoint or schema drift, not as
the numerical oracle.

Keep semantic golden outputs for stable reference workflows. Record the fixture
source, independent calculation method, expected invariants, and acceptable
tolerances next to each fixture.

## Proposed Test Organization

```text
tests/correctness/test_ipf_properties.py
tests/correctness/test_integerization_properties.py
tests/correctness/test_tree_distributions.py
tests/correctness/test_linked_invariants.py
tests/correctness/test_small_area_reconciliation.py
tests/correctness/test_reference_workflows.py
tests/fixtures/correctness/
```

Use Hypothesis or an equivalent property-testing tool for generated feasible
tables, record permutations, category renaming, target scaling, and weight
vectors. Strategies should construct valid inputs directly rather than discard
large numbers of invalid examples.

## Execution Tiers

Every pull request:

- deterministic mathematical and structural invariants;
- Python/NumPy differential IPF checks;
- tiny known-truth fixtures;
- artifact reconciliation on small workflows;
- fixed-seed model round trips.

Nightly or scheduled:

- larger property-test example counts;
- multi-seed distributional acceptance tests;
- public-data reference benchmarks;
- opt-in live StatCan drift checks;
- medium-scale single-worker/parallel equivalence.

Before a release:

- the complete reference workflow set;
- larger fixed-seed distribution ensembles;
- installed-wheel correctness smoke tests;
- a machine-readable correctness report retained with normal test and coverage
  results.

## Implementation Order

1. Differential Python/NumPy IPF tests and converged-fit invariants.
1. Independent small-area output reconciliation.
1. Integerization properties and realized-output residual checks.
1. Frequency and CART probability oracles plus distributional acceptance tests.
1. Linked-generation invariants and execution-path equivalence.
1. Versioned known-truth and public StatCan-derived reference workflows.

## Completion Criteria

- Every numerical kernel has at least one independent oracle or equivalent
  differential implementation.
- Core algorithms have generated invariant and metamorphic tests, not only
  example-based branch coverage.
- Emitted small-area artifacts are reconciled independently against controls and
  report values.
- Model generation has explicit, reviewed statistical acceptance thresholds.
- Linked outputs are checked for structural integrity across both model families
  and all execution paths.
- Pull-request, scheduled, and release correctness tiers run in CI with clear
  ownership and failure output.
