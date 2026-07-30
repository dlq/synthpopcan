# Small-Area Geography Implementation Plan

Status: implementation complete; awaiting the `0.7.0` release\
Created: 2026-07-22\
Last updated: 2026-07-29\
Target: `0.7.0`, with later expansion gated by evidence\
Next action: preserve the reviewed proof evidence through the `0.7.0` release\
Roadmap: [PLANS.md](../PLANS.md) | [Plan index](README.md)

## Purpose

Make Census geography an explicit data and research contract rather than a
filename, identifier prefix, or incidental column. Preserve the current CT,
ADA, and CSD workflows while adding only the DA support needed for a reviewed
small-area proof and the reusable geography-keyed external-data framework.

This plan owns geography identity, authoritative relationships, selection, and
small-area execution. The
[external-data enrichment framework](2026-07-15-ecosystem-enrichment.md)
consumes that contract; it does not redefine it.

## Current Baseline

The codebase already provides:

- linked small-area calibration, realization, validation, and mapping;
- explicit 2016 and 2021 Census Profile adapters;
- 2016 CT, ADA, DA, CSD, CD, and province/territory boundary registrations;
- 2021 CT, ADA, DA, and CSD boundary registrations;
- national 2021 CT, ADA, DA, and CSD boundary data and a 2021 Dissemination
  Geographies Relationship File; and
- a 2016 national DA Census Profile resource.

The explicit geography contracts, Québec DA profile registration, national DA
boundary registration, deterministic DGRF selection, streaming boundary
subset, exact controls, and compact 2016 regression are implemented. The
bounded proof now covers four Montréal DAs and four rural Québec DAs, with
converged fractional fits, linked-population validation, explicit realized
integer residuals, parent summaries, hashes, resource measurements, and a
bounded map. Coverage still differs by Census vintage, and matching-looking
codes are never treated as interchangeable across vintages.

The reviewed run generated 800 households and 1,896 linked people across all
eight selected DAs. All eight fractional fits converged with maximum absolute
error below `1e-6`; integer realization produced a maximum household residual
of 10, reported rather than hidden. It found no unknown household links, size
mismatches, missing selected geographies, or unknown observed geographies.

The reviewed national DA preparation on 2026-07-29 reconciled 57,936
final-DGRF DA records with 57,932 cartographic boundary features. It found
56,072 DAs with usable household-size and tenure controls, excluded 1,864
explicitly, and planned 14,971,780 households in 159 restartable batches. The
four DGRF records absent from the boundary product have zero area and
unavailable profile values; none has usable controls. A bounded Nunavut
execution then generated 9,950 households and 34,979 linked people across 41
DAs from the PUMF's `PR=70` northern candidate pool. All 41 fractional fits
converged below `1e-6`; realized integer controls had a reported maximum
residual of 17, and linked-population validation found no unknown links or
household-size mismatches.

The matching national ADA preparation reconciled 5,433 final-DGRF ADAs with
the national boundary product. It found 4,961 ADAs with usable controls,
excluded 472 explicitly, found no usable ADA without a boundary, and planned
14,977,735 households in 161 restartable batches. A bounded Nunavut execution
generated 9,925 households and 35,048 linked people across 25 ADAs. All 25
fractional fits converged below `1e-6`; realized integer controls had a
reported maximum residual of 21, and linked-population validation found zero
unknown links or household-size mismatches. These runs prove both national
planning paths and one territorial execution per level, not all national
population outputs or universal model fitness.

National execution no longer reloads and regenerates candidates from the
1.6 GB model package for every batch. It builds one linked candidate pool per
PUMF condition, records the source-model evidence, seed, category support,
integrity, and timings, and verifies that cache on resume. Batches stage output
atomically, checkpoint after every result, can run in bounded parallel
processes, and defer optional detailed maps. Completed plans receive aggregate
CSV/JSON evidence, a polygon choropleth using display-only fixed-grid-quantized
geometry, and a separate compact point overview derived from canonical feature
extents. Neither display product alters the analytical boundaries.

The first real Newfoundland and Labrador ADA timing exercise used a 10,000
household `PR=10` pool. Model loading took 41.5 seconds and the one-time pool
build took 68.3 seconds. A 99,665-household batch covering 29 ADAs then took
3.5 seconds for calibration, realization, linked validation, and artifact
handling; a cache-verified resumed CLI invocation completed in 5.7 seconds
wall time without loading the model. This is performance evidence for that
machine and batch, not a universal runtime guarantee.

A reproducible sensitivity script then generated one 50,000-household `PR=10`
reference pool in 343.0 seconds and fitted the same 29-ADA, 99,665-household
batch with deterministic 10,000, 25,000, and 50,000 candidate selections. All
29 fractional fits converged below `1e-6` at every size. Calibration,
realization, and report construction took 2.2, 3.1, and 3.6 seconds
respectively on a cache-reuse run. Compared with the 50,000-pool result, the
largest total-variation distance among non-identifier uncontrolled household
fields was 2.12% at 10,000 and 1.38% at 25,000; among person fields it was 2.64%
and 1.61%. Linked person totals differed by at most 178 people (0.08%).
Integer realized maximum residuals were 46, 77, and 66, so they did not improve
monotonically with pool size. The default 10,000 pool is therefore a pragmatic
execution default, not a declaration of scientific equivalence: substantive
work should repeat the recorded benchmark with its geography, variables, and
candidate conditions, and use a larger pool or multiple seeds when sensitivity
matters. The benchmark utility is
`scripts/benchmark_national_candidate_pools.py`.

The completed Canada ADA execution generated 14,977,735 households and
36,175,520 linked persons across all 4,961 usable ADAs in 161 restartable
batches. All 161 linked-population validations passed, every ADA matched the
national summary and maps, and all 4,961 fractional fits converged below
`1e-6`; the maximum reported integer-realization cell residual was 89. The
national polygon map reduced the display copy of the 1.64 GB canonical
boundary product to 52.5 MB at three-decimal coordinate precision, matched all
4,961 ADAs, and retained the point overview as an explicitly secondary output.
The existing `geo map` CLI and `render_small_area_map` API accept this completed
plan directly. Their cached 4,961-row statistics layer is derived from all 161
full-variable household/person batches and exposes the same 12 curated
variables as the established single-population map.

The first complete pass exposed a category-contract defect rather than a
numerical failure: 457 ADAs in PEI, Manitoba, and Saskatchewan did not reach the
strict tolerance because their pools included 30 generated households with
PUMF `TENUR=8`. Official PUMF metadata defines 8 as “Not available,” while the
Census control correctly combines renter and band/local-government dwellings
under the PUMF `TENUR=2` definition. Leaving 8 outside the two control cells
made its weights unconstrained. Pool preparation now excludes those households
and their 177 linked persons, records that decision, invalidates older caches,
and general preflight rejects any uncontrolled candidate category. A bounded
correction regenerated the three affected pools and twelve batches; the final
zero-nonconvergence result above is from that corrected pass.

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
- Build only the relationship records required by the Québec 2021 DA proof
  from authoritative Statistics Canada files.
- Emit explicit unmatched, ambiguous, and vintage-mismatch reports.
- Add migrations or compatibility handling for current manifests where
  necessary; do not silently reinterpret an old identifier.

### 2. Prove a bounded Québec 2021 DA workflow

Use public, release-pinned inputs and include at least one metropolitan and one
rural study area. Add the missing registered 2021 DA profile/boundary path
needed to attach Can-FED v2, while keeping the current 2016 DA resources
recognized and covered by a compact compatibility regression. Exercise:

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

- automatic 2016/2021 DA concordance;
- arbitrary-polygon selection;
- a complete cross-product relationship graph among all Census geographies;
  or
- a monolithic national fit.

National DA/ADA orchestration now uses one restartable province/territory
planner with level-specific source adapters, per-batch manifests, checkpoints,
resource bounds, reusable candidate pools, bounded parallel execution, and
aggregate coverage evidence. It deliberately does not
assert that one model is scientifically representative for every Canadian
small-area question; national execution uses the broad Canada 2021 package by
default and still requires research-specific fitness review. In particular,
the 2021 hierarchical PUMF combines Yukon, Northwest Territories, and Nunavut
as `PR=70`; all three use that shared northern candidate pool and separate
territorial controls. Cross-vintage harmonization and user-supplied polygon
intersection each require separately reviewed methods.

### Validated full-field ADA/DA control expansion

The completed national plans currently control household size and tenure. The
linked-person records retain all model fields, but a field retained from a
province/territory-conditioned PUMF candidate pool is not thereby an estimate
of that field's ADA- or DA-level distribution. For example, an uncontrolled
immigration-status map can primarily reflect the provincial candidate pool,
with only incidental within-province variation. Map labels, metadata, and
research claims must make that distinction explicit until the relevant local
control is fitted.

Before presenting any synthetic household or person variable as small-area
controlled, implement a versioned 2021 Census Profile control-coverage audit
for **every field in the linked synthetic household and person schemas**, at
both ADA and DA level. The audit must record, per field and PUMF category:

- the Profile characteristic/member, universe, geography level, Census
  vintage, source revision, and suppression or availability conditions;
- an exact category crosswalk where one is defensible;
- where exact equivalence is impossible, the approved coarser margin or
  aggregation and the information it does not constrain; and
- an explicit `unavailable` or `uncontrolled` classification where no valid
  public small-area control exists.

Use the audit to build level-specific, evidence-checked household and linked
person control resources. Start with high-value, suitably supported person
margins such as age/sex, immigration status, citizenship, generation status,
visible-minority status, language, education, labour-force status, and income
bands; add compatible housing and household attributes where the Profile and
PUMF categories permit it. Avoid treating continuous values, source/provenance
identifiers, PUMF-only recodes, unavailable categories, or suppressed values as
direct controls. High-dimensional joint margins must be introduced only when
their support and feasibility are demonstrated; separate compatible margins are
preferred initially.

Extend national plan manifests and batch execution to carry both household and
person control resources into linked calibration. Preserve whole-household
assignment: person controls may alter household weights but must never detach
people from their linked household. For each ADA and DA run, emit field-level
coverage, residual, support/structural-zero, suppression, and reconciliation
reports. Regenerate—not merely remap—any population whose added controls change
the fit, and test that current household-only runs remain reproducible.

This expansion is a correctness and substantive-fitness milestone after the
current household-control national proof, not a promise that every model field
will acquire an exact small-area Census control. It requires review of each
source/category crosswalk and should be released only with fixtures,
documentation, and claims-to-evidence updates.

The planner keeps the canonical cartographic boundaries exact. If geometry
size becomes a material delivery or rendering constraint, a later
topology-preserving simplification may create an explicitly derived display
artifact with a recorded method, tolerance, source hash, identifier coverage,
geometry-validity checks, and quantified area/extent change. It must never
silently replace the canonical analytical boundary or affect control
assignment.

### National ADA orchestration parity

Completed for `0.7.0`. DA and ADA share fitting, linked realization,
validation, geography identity, boundary partitioning, batching, resume state,
resource estimation, PUMF conditioning, reusable candidate pools, atomic
outputs, phase timing, artifact hashing, aggregate summaries, and map behavior.
The source adapters intentionally differ: DA reads six regional products and
the DGRF DA relationship; ADA reads one national product and the DGRF ADA
relationship. CLI plan identity checks prevent either runner from accepting
the other level's plan.

## Completion Criteria

- The canonical identity is present and validated wherever geography affects a
  `0.7.0` result.
- Unsupported and cross-vintage joins fail with actionable diagnostics.
- The public Québec 2021 DA proof passes control, linkage, geography, resource,
  mapping, and reproducibility checks for metropolitan and rural cases.
- All six official regional 2021 DA profile products can be reconciled with
  national boundaries and DGRF relationships into restartable batches for all
  13 provinces and territories, with exclusions and resource estimates
  reported explicitly.
- The official national 2021 ADA profile can be reconciled through the same
  planner and executor, with parity tests covering source adaptation, plan
  identity, batching, resume state, synthesis, validation, and mapping.
- Existing 2016 DA resources remain recognized, and cross-vintage joins fail
  rather than being interpreted as concordant.
- The enrichment layer can consume the identity contract without duplicating
  geography logic.
- Documentation distinguishes national execution readiness from scientific
  representativeness of any particular model.
