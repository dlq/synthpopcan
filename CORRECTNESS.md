# Correctness Assurance

SynthPopCan is research software. No finite test suite can prove that it is
correct for every dataset or research question. The project instead maintains
an auditable assurance case: each public correctness claim is limited, linked
to independent evidence, rerun automatically, and paired with known
limitations.

This file is the current public assurance summary. The
[correctness-assurance plan](https://github.com/dlq/synthpopcan/blob/main/plans/2026-07-12-correctness-assurance.md)
owns future maintenance work;
[CHANGELOG.md](https://github.com/dlq/synthpopcan/blob/main/CHANGELOG.md)
records released changes; and workflow reports and release assets preserve
commit-specific results.

Passing these checks means that the tested version behaved as specified under
the documented conditions. It does not establish that source data or chosen
controls are accurate, that a synthetic population is statistically suitable
for every inference, or that disclosure risk has been eliminated.

## Current assurance claims

| Claim | Automated evidence | Important boundary |
| --- | --- | --- |
| Feasible IPF problems reproduce their controls within tolerance. | Generated feasible cases, independently aggregated residuals, and known-truth fixtures in [`test_ipf_correctness.py`](https://github.com/dlq/synthpopcan/blob/main/tests/test_ipf_correctness.py). | Convergence is not guaranteed for inconsistent controls, unsupported cells, or every possible input. |
| Scalar and NumPy IPF have equivalent documented semantics. | Differential, sparse-control, scaling, row-order, category-renaming, and record-duplication tests in [`test_ipf_correctness.py`](https://github.com/dlq/synthpopcan/blob/main/tests/test_ipf_correctness.py). | Differential agreement is strongest when combined with the independent invariants; two implementations could otherwise share a conceptual defect. |
| Integerization preserves the requested aggregate and is deterministic. | Generated vector properties, cumulative-discrepancy checks, expansion, and identifier-traceability checks in [`test_ipf_correctness.py`](https://github.com/dlq/synthpopcan/blob/main/tests/test_ipf_correctness.py). | Integerized cells can differ from fractional targets; users must inspect realized residuals. |
| Frequency and CART model runtimes reproduce their defined probabilities and structure. | Analytical probability fixtures, scikit-learn leaf/probability comparisons, multi-seed acceptance tests, and semantic round trips in [`test_model_correctness.py`](https://github.com/dlq/synthpopcan/blob/main/tests/test_model_correctness.py). | Computational agreement does not establish that a fitted model is representative or appropriate for a research question. |
| Linked output preserves household/person relationships and generated identifier integrity. | Independent relationship, household-size, uniqueness, inheritance, privacy-column, determinism, and CSV/in-memory equivalence checks in [`test_model_correctness.py`](https://github.com/dlq/synthpopcan/blob/main/tests/test_model_correctness.py). | These checks cannot correct omissions, bias, or errors already present in training data. |
| Current small-area artifacts reconcile with supplied household and person controls. | Independent read-back aggregation, geography-isolation, serial/parallel, subsampling, non-convergence, and household/person oracle tests in [`test_small_area_correctness.py`](https://github.com/dlq/synthpopcan/blob/main/tests/test_small_area_correctness.py). | Structural zeros and incompatible controls can make an exact solution impossible and must be reported, not hidden. |
| The retained linked calibration and integerization backends behave as specified on the bounded 0.9 evidence domain. | Exact regeneration of the analytical, generated, sparse, linked-person, non-uniform, redundant, infeasible, and integerization-comparator artifact in [`test_methodology.py`](https://github.com/dlq/synthpopcan/blob/main/tests/test_methodology.py). | The independent relative-entropy oracle is evidence-only and bounded; agreement does not prove arbitrary feasibility, global production convergence, or substantive fitness. |
| Built-in control packs reject incompatible model fields, Census identity, control vectors, universe evidence, and unsupported cells before fitting. | Both-vintage CSD/CT/ADA/DA manifest, evidence-binding, derivation, duplicate/missing-cell, reconciliation, linkage, and feasibility cases in [control-pack contract](https://github.com/dlq/synthpopcan/blob/main/tests/test_control_pack_contracts.py), [planning](https://github.com/dlq/synthpopcan/blob/main/tests/test_control_pack_planning.py), and [calibration tests](https://github.com/dlq/synthpopcan/blob/main/tests/test_control_pack_calibration.py). | Pack definitions contain no Census counts. A passing plan is limited to the exact normalized tables, source revisions, eligible geographies, and private-household universe recorded by its evidence document. |
| Small-area reports independently recompute linked residual, concentration, candidate-reuse, rare-cell, zero-target, and field-targeting diagnostics. | Linked household/person contribution, integer realization, fitter-generated multi-scale, and external aggregate comparison cases in [`test_methodological_validation.py`](https://github.com/dlq/synthpopcan/blob/main/tests/test_methodological_validation.py). | Targeting and low residuals do not establish local representativeness; carried-through and coarsened attributes remain explicitly limited, and the external comparison is not record-level truth. |
| A versioned public Statistics Canada example reproduces independently recorded totals. | The frozen source selection, mapping, expected controls, provenance, and independent total in [`tests/fixtures/correctness`](https://github.com/dlq/synthpopcan/tree/main/tests/fixtures/correctness), exercised by [`test_reference_correctness.py`](https://github.com/dlq/synthpopcan/blob/main/tests/test_reference_correctness.py). | One reference table cannot represent every Statistics Canada product, vintage, or transformation. |
| The distributed wheel contains a working library, CLI, and required web assets. | An isolated installation outside the checkout runs IPF, resource, import-origin, and CLI checks through [`check-wheel.sh`](https://github.com/dlq/synthpopcan/blob/main/scripts/check-wheel.sh). | This is a representative packaging smoke test, not an exhaustive installed-package test. |
| Browser-facing WDS, upload, and registered-model paths reject inputs outside documented resource bounds. | Download, request, archive, decompression, row-count, concurrency, selected-member, upload, catalogue, and API regression tests in [`test_webapp.py`](https://github.com/dlq/synthpopcan/blob/main/tests/test_webapp.py), [API security](https://github.com/dlq/synthpopcan/blob/main/tests/test_webapi.py) and [model API tests](https://github.com/dlq/synthpopcan/blob/main/tests/test_webapi_models.py), [`test_models.py`](https://github.com/dlq/synthpopcan/blob/main/tests/test_models.py), and [`test_statcan.py`](https://github.com/dlq/synthpopcan/blob/main/tests/test_statcan.py). | Resource limits reduce accidental exhaustion; they do not make the current loopback server suitable for network deployment. |
| Standalone maps preserve tested polygon topology and cannot embed supplied labels as executable HTML. | Hole/island classification in [geometry tests](https://github.com/dlq/synthpopcan/blob/main/tests/test_map_geometry.py); unmatched-geography, inline JSON, title escaping, and text-node tooltip tests in [`test_map_render.py`](https://github.com/dlq/synthpopcan/blob/main/tests/test_map_render.py). | Projection and topology checks cover current StatCan polygon inputs, not every malformed or non-polygon geospatial source. |
| Published external artifacts replace valid local files only after a bounded, verified transfer. | Concurrent model-cache and interrupted, oversized, or truncated StatCan transfer tests in [`test_models.py`](https://github.com/dlq/synthpopcan/blob/main/tests/test_models.py) and [`test_statcan.py`](https://github.com/dlq/synthpopcan/blob/main/tests/test_statcan.py). | A successful transfer does not independently establish the accuracy or continued availability of the upstream source. |
| Prepared display-boundary catalogue publication commits only complete, single-writer batches, and selected boundaries are identified unambiguously and used only after integrity verification. | Resume-fingerprint, source/output-tamper, stale/corrupt-gzip, batch-catalogue-commit, and concurrent-writer tests in [`geodata-build.test.mjs`](https://github.com/dlq/synthpopcan/blob/main/tests/web/geodata-build.test.mjs), plus catalogue validation, exact year/level/PRUID matching, compressed and unpacked SHA-256 checks, cache reuse, and invalid-metadata tests in [`test_geodata.py`](https://github.com/dlq/synthpopcan/blob/main/tests/test_geodata.py). | A failed build can leave unreferenced immutable assets, but it does not replace the catalogue. These checks verify selected bytes, not the substantive appropriateness of a geography or control universe. |
| Geography-bearing workflows preserve Census vintage, level, namespace, and authoritative relationship context. | Identity, universe, relationship, cross-vintage rejection, bounded Québec DA proof, and national DA/ADA planning tests in [`test_geography.py`](https://github.com/dlq/synthpopcan/blob/main/tests/test_geography.py), [`test_da_proof.py`](https://github.com/dlq/synthpopcan/blob/main/tests/test_da_proof.py), and [`test_national_small_area.py`](https://github.com/dlq/synthpopcan/blob/main/tests/test_national_small_area.py). | Matching-looking identifiers do not establish concordance across vintages, and successful national execution does not establish that one prepared model is scientifically representative for every small area. |
| Enrichment publishes validated sidecars without rewriting the linked base population. | Source/resource authority, immutable revision, normalized-layer, coverage, cross-vintage, byte-preservation, corruption, CLI, and beginner-API tests in [`test_enrichment.py`](https://github.com/dlq/synthpopcan/blob/main/tests/test_enrichment.py). | Structural and integrity checks do not validate an undocumented upstream transformation or establish causal, exposure, accessibility, or substantive research claims. |
| Exchange v1 preserves linked population bytes and detects incomplete, changed, or semantically inconsistent handoffs. | Source-byte, manifest, hash, row-count, linkage, dictionary, geography, provenance, tamper, CLI/API, fictional-demo, and installed-wheel tests in [`test_exchange.py`](https://github.com/dlq/synthpopcan/blob/main/tests/test_exchange.py), [`test_api.py`](https://github.com/dlq/synthpopcan/blob/main/tests/test_api.py), and [`check-wheel.sh`](https://github.com/dlq/synthpopcan/blob/main/scripts/check-wheel.sh). | A valid population contribution is not a runnable simulation and does not establish representativeness, privacy, substantive fitness, or compatibility with an unnamed target. |
| Durable-run evidence identifies terminal state and detects changed inputs or artifacts. | Complete, failed, cancelled, interrupted, row-recount, digest-tamper, and linked-integrity checks in [`test_runs.py`](https://github.com/dlq/synthpopcan/blob/main/tests/test_runs.py). | The evidence verifies recorded bytes and implemented checks; it is not a privacy certification or substantive-validity finding. |
| Recorded workflow recipes reproduce the represented fixed-seed artifacts. | Executed IPF, prepared-model, generated small-area, uploaded-candidate, and mapped small-area recipe tests in the workflow test modules. | Reproduction still requires access to the recorded inputs or documented replacements; restricted source data are not embedded. |

## How the evidence runs

The [2026-10-22 correctness/refactoring record](https://github.com/dlq/synthpopcan/blob/main/docs/records/correctness-refactor-2026-10-22.md)
documents boundary failures found beyond the previous green suite and their
regressions. The additional checks cover an independent 2×2 odds-ratio IPF
oracle, finite arithmetic, aligned expansion weights, finite validation
tolerances, every invalid source-selection combination, multi-margin web/domain
parity, and missing map observations. Passing a fitter alone does not validate
downstream summaries or presentation semantics.

- The [normal CI workflow](https://github.com/dlq/synthpopcan/actions/workflows/ci.yml)
  runs deterministic correctness tests on every pull request and push to
  `main`, across the supported Python 3.11 through 3.14 versions. It retains a
  machine-readable JUnit report for each version and commit.
- The [extended correctness workflow](https://github.com/dlq/synthpopcan/actions/workflows/correctness.yml)
  runs larger generated-case and multi-seed suites each week and on demand. It
  also checks the live Statistics Canada WDS interface for external drift.
- The [package publishing workflow](https://github.com/dlq/synthpopcan/actions/workflows/publish.yml)
  checks out an existing release tag, verifies that it exactly matches the
  package version, runs the full coverage gate and extended correctness suite,
  tests the built wheel, attests the distributions, and attaches checksummed
  reports and build evidence to the matching GitHub Release before PyPI
  publishing can proceed.
- Browser unit tests and real Chromium workflow scenarios check presentation,
  sequencing, and integration with the shared Python backend. The browser does
  not contain an independent numerical implementation.

GitHub Actions artifacts remain useful commit evidence but expire. The release
workflow therefore also uploads distributions, XML reports, wheel-smoke output,
the dependency lock and build metadata, a tag-and-commit-bound evidence
manifest, and SHA-256 sums to the permanent GitHub Release.

Every terminal durable run embeds `synthpopcan-assurance-v1` in `run.json`.
It records the normalized request, settings and seeds, model identity where
applicable, independently observed input and artifact metadata, diagnostics,
linked integrity, warnings, limitations, and terminal state. Failed, cancelled,
and interrupted work is mechanically marked unsuccessful. Readers must ignore
unknown additive fields; an incompatible future format requires a new schema
identifier and migration reader rather than rewriting old evidence.

Reproduction metadata retains a primary command for compatibility and an
ordered command sequence for multi-step output. Small-area recipes preserve
model conditions and optional map creation and are executed against both
generated and uploaded candidate fixtures.

## Reproduce the checks

From a source checkout with `uv`, Node.js, and the Playwright browser installed:

```bash
UV_CACHE_DIR=/tmp/uv-cache ./scripts/check.sh
```

Run the larger numerical and artifact suite directly with:

```bash
sh scripts/check-correctness.sh
```

Build both distributions and verify their installation independently of the
checkout with:

```bash
uv build
sh scripts/check-wheel.sh
```

The exact commands, dependency versions, commit, operating system, and Python
version should be recorded when these results are cited in research outputs.

## Interpreting a generated population

Project-level tests answer whether known classes of implementation defects are
detected. Users must still validate each generated population. At minimum,
retain and inspect:

- convergence status and tolerances;
- requested, fractionally fitted, and integerized realized totals;
- residuals by geography, dimension, and category;
- unsupported or structurally impossible cells;
- household/person linkage and identifier findings;
- input provenance, category mappings, random seeds, and SynthPopCan version;
- warnings about statistical fitness, source limitations, and disclosure risk.

See the [validation documentation](https://synthpopcan.readthedocs.io/en/latest/validate.html)
for current commands and reports.

## Reporting a suspected correctness problem

Open a [GitHub issue](https://github.com/dlq/synthpopcan/issues) with the
smallest shareable reproducer, SynthPopCan version, command or API call, random
seed, expected result, and actual result. Do not attach restricted microdata or
other private inputs. Security or disclosure-sensitive findings should instead
use [private vulnerability reporting](https://github.com/dlq/synthpopcan/security/advisories/new).

### Source-specific map and age-control coding

The hierarchical 2016/2021 PUMF uses 13 substantive `AGEGRP` bands; codes
12 and 13 represent ages 65+, and 88 is unavailable. The released v1
age-control derivation assumes 18 bands and must not be applied directly to
these hierarchical fields. The 2021 hierarchical `GENDER` codes are also
1 = Women+ and 2 = Men+, while the released age/gender control source axes
reverse those labels. Until a versioned replacement is available, prepare
`age_group_3` and gender targets using the source codebook and use generic
calibration with
compatible private-household age controls.

Map callers can supply binary `age_under_20`, `age_65_plus`, and
`visible_minority` indicators derived from their source codebook. A supplied
blank or invalid indicator remains unobserved. Without these columns the
legacy raw-code interpretation remains in effect; it is not suitable for every
PUMF schema.

The composable CLI preparation commands provide this source-specific path
without custom scripts: `geo prepare-controls` reads observed 2021 CMA/CT
Profile counts, and `geo prepare-candidates` derives the hierarchical age and
gender fields before generic `geo calibrate`. Normalization and incomplete
geography exclusions are explicit choices and recorded. The CLI leaves frozen
v1 pack definitions unchanged and retains realized residuals for independent
`geo audit` checks. See the complete CLI workflow in the small-area reference.

## Accelerated linked fitting

Identical contribution columns may be grouped by summing their initial weights.
Multiplicative fitting preserves each group's relative weights, which are used
to expand the fitted totals back to every original household. Original control
matrices independently verify convergence after expansion.

The optional hybrid solver minimizes generalized relative entropy through its
convex dual: weights have the form `w0 * exp(A.T @ lambda)`. It accepts only
solutions meeting the original absolute residual tolerance and retains exact
structural zeros and initially zero support. Failed, infeasible or ill-conditioned
attempts are discarded; IPU then starts from the unchanged original weights.
Integer realization is independently audited and can still introduce residuals.

Support LPs retain their full variables and constraints when presolve is disabled.
Numerical failures retry with presolve enabled. An alternative equivalent LP
basis can change added candidate supports; seeded generation itself preserves
its draw sequence when caching CART leaf distributions and cumulative weights.

## CSV and fallback optimization safeguards

Maintained writers and completed validators can supply measured headers and
record counts to the internal contract builder. Counts from an unvalidated
manifest are never used to bypass actual-file validation. Combination still
reads back the output to validate unique IDs, linkage, household sizes and counts,
and the control audit independently aggregates the emitted CSV records. Projected
CSV readers retain quoted-newline, blank-record, duplicate-header and short-record
semantics.

IPU lookup tables are read-only and shared across geographies. Permanently zero
weights may be omitted from repeated updates, but exponent normalization comes
from the original full rows and every convergence decision uses the full matrix.
Geography-specific support masks never mutate shared lookup tables.

Map acceleration counts raw values in bounded chunks, then applies the existing
integer-code and eligibility rules. Exact weighted income medians replace lists
of repeated values. Missing and inapplicable observations retain their original
denominators; a faster map is not permitted to zero-fill unknown values.

The optional `performance` extra compiles sequential IPU updates without fast
math and retains the original BLAS reductions, exponent normalization,
structural-zero rules and full-system residual checks. Prepared encodings belong
to the calibration system; each concurrent fit owns its mutable weights. Missing
or incompatible native compiler/BLAS support falls back to NumPy. Tiny fits do
not compile. Differential and concurrency tests live in
`tests/test_numba_ipu.py`.

Bounded Polars audit/map paths reread actual population CSVs in 4 MiB buffers.
Quoting, ambiguous null/empty values, unusual record syntax and unsafe numeric
ranges restart the reference operation, discarding partial native aggregation.
Duplicate headers, source-order diagnostics, exact income medians and rounding
retain their reference behavior. Focused differential fixtures live in
`tests/test_columnar_audit.py` and `tests/test_polars_map_statistics.py`;
`scripts/performance_smoke.py` verifies actual native execution from an installed
wheel. Reference fallbacks are tested even when the extra is installed. Backend
rounding may depend on the platform's BLAS implementation; per-platform parity
checks accompany the independent mathematical tests.

Provincial ADA preparation uses each area's published occupied-private-dwelling
count, with an independently observed provincial root. Missing or suppressed
area counts are never treated as zero or redistributed. Plans expose excluded
areas, known household shortfalls and unknown household counts, while keeping
rounded area private-person totals separate from provincial totals. The
age/gender universe policy is identical to the CMA path. Province-source and
coverage fixtures are in `tests/test_province_profile_preparation.py`; a real
CLI preparation/calibration/dual-map fixture is in `tests/test_geo_preparation.py`.

An explicit observed policy first attempts the structural fit. Unsupported
zero constraints, exhausted strict budgets, or stationary strict weights can
instead use a fixed-household-total
entropy/least-squares fit against every original count, including zero targets.
The original prior is recovered before household-stage zero exclusions; genuine
prior zeros remain zero. Approximation never edits targets or equates optimizer
success with control convergence. The loss, regularization, stopping reason,
zero-cell error and requested/effective policy are recorded. The approximate
optimizer has a separate 100-step budget, independent of strict sweep limits.
Centering uses the exact household total; orthogonal projection removes constant
loss directions, with discarded-direction error bounded in original count units.
A trust-region Newton step avoids softmax saturation from ill-conditioned
curvature. Original count residuals still determine control convergence. Independent
analytic fixtures are in `tests/test_observed_calibration.py`; linked and CLI
fixtures are in `tests/test_observed_linked_calibration.py` and
`tests/test_cli_observed_calibration.py`. Whole-household witness retention and
its lack of a feasibility guarantee are checked in
`tests/test_candidate_witness_support.py`.

CSV combination uses bounded row batches, retaining independent output read-back
validation. Validation projects identifiers and sizes as tuples while preserving
short-row and duplicate-header semantics. CSV integrity uses buffered UTF-8
bytes for both writing and SHA-256, avoiding a second encoding pass; Unicode
and multiline-record byte equivalence is covered in
`tests/test_population_performance.py`. The writer's reviewed complexity
baseline rises from one to two for its buffer threshold and empty-flush guard.

The optional compiled categorical household IPF loop preserves targeted and
untargeted categories, zero priors, sequential updates and overflow/underflow
handling. It uses float64 without fastmath; unavailable compilation falls back
without modifying the NumPy starting state. Differential cases are in
`tests/test_numba_ipu.py`. Its reviewed complexity of 18 reflects numerical
guards and margin/category/record loops; backend dispatch adds one branch to
`NumpyIPFIndex.fit`. The linked observed path checks strict weights at 150 and
300 sweeps when budget permits, retains the remaining budget when weights move,
and reports approximation separately from convergence. Stage iteration counts
are retained independently. Structural defaults keep their strict fit policy.

Large plain CSV combination uses bounded native string frames, preserves union
column order and geography inheritance, and independently validates the emitted
files. Quoting or ambiguous native parsing restarts the current table after
truncating its partial output and restoring household assignment state. File
linkage validation similarly restarts both files with a fresh disposable database
when native projection needs reference parsing. Missing foreign keys remain
unknown references; their explicit counter permits a single-index count table.
The SQLite page cache is bounded at 256 MiB and grows on demand.

Weight diagnostics use float64 reductions and partitioning with the same metric
definitions; harmless last-bit differences are assessed with floating tolerances.
Reuse counts retain Python integer semantics when fixed-width sums might overflow.
The reviewed complexity increases in fractional validation (3 to 4) and reuse
(1 to 2) are the coercion/shape guard and unbounded-integer fallback. CSV fallback,
error ordering, integer overflow and analytic metric fixtures are covered in
`test_population_performance.py`, `test_linked_csv_validation.py` and
`test_methodological_validation.py`.

Plain-record safety scans now compare native newline offsets while retaining
quote, NUL, BOM, carriage-return and field-limit fallback. Audits skip a geography
filter only when that margin covers the entire validated geography universe.
Map integer parsing checks unusual syntax only among failed native conversions;
both map views share boundary geometry but copy feature properties per view.
CART restoration uses the same `float()` coercion through a native iterator.

Large typed-string realization tables can use bounded 65,536-row native CSV
serialization. Numeric/object tables, unsupported values, missing-value conversion
and unusual carriage returns fall back to pandas, reopening the output so partial
native bytes never survive. Unicode, quoting, empty strings, late fallback and
exact SHA-256/byte counts are covered by the CSV performance fixtures. The
reviewed writer complexity changes from one to two for optional backend dispatch.
Experiments with native text buffering, multi-value SQL insertion, categorical-only
audit grouping and larger validation batches were rejected after measurement.
The retained native audit accumulator instead merges at most sixteen reduced
chunks per dimension group, preserving minimum source ordinals and margin
ordering. Per-operation categorical keys avoid retaining source string buffers.

Native linkage projection now extracts tuple lists directly from frame slices,
maintaining exact 4,096-record boundaries across parser buffers. This avoids
per-record Python yielding/appending while retaining first-seen insertion,
ordered duplicate replay and whole-validation reference restart.

Native population combination compiles ID and geography enum expressions once
per source, then matches whole buffers by integer codes. Household duplicates
still use their last geography assignment before independent final-file checks.
The original Python lookup is released after native index construction; unusual
person CSV restores it before restarting the reference copier. Completed source
lookups are released before final-file validation on either backend. Tests cover
leading zeros, whitespace/Unicode labels, unknown links, duplicate assignments,
late person-record fallback and exact batch boundaries.

Native CSV reads use 8 MiB buffers. Carriage-return checks compare adjacent
bytes with NumPy, accepting a trailing CR only until the next buffer arrives;
the final-file guard still rejects a bare trailing CR. Exhaustive short-input
tests cover repeated CRs and split CRLF sequences. SQLite scratch indexes use
16 KiB pages with the same 256 MiB cache bound, savepoints and duplicate replay.

The six-part responsibility refactor retains public façades and model class
locations. National serial and process executors share lazy batch selection,
attempt initialization, interruption recovery and plan persistence. Their
scheduling and exception behavior remain explicit. Map geometry and boundary
I/O live in `_map_boundaries`, with checksum-bound national preparation in
`_national_map_statistics`; `map_render` retains its existing import paths.
CSV/SQLite linkage implementation lives in `_linked_validation`, and catalogue
payload builders live in `_control_pack_catalogue`. All 24 built-in pack
payloads/hashes and the compatibility-registry payload match the prior bytes.

Archive execution separates validated immutable inputs, checkpoint recovery,
owned draft preparation, publication recovery, asset upload, metadata binding
and explicit publication. Four identical verify/checkpoint sequences share one
helper; intermediate publication checkpoints retain their original positions.
The existing mocked transport, ownership, fault and resume fixtures verify the
same operations and refusals. No archive state, gate or real publication is
added. Web upload, preflight, manifest, event, cancellation and artifact route
groups retain registration order and the existing security/lifecycle context.

Complexity ceilings follow relocated functions without increases. The reviewed
archive phase split replaces the entry point's score of 70 with 3; its largest
phase scores 27. Existing orchestrator ceilings are tightened after extraction.
This phase decomposition does not implement the separately planned pure
archive transition selector or remove any of its review gates.
