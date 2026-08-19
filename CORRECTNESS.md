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
| Built-in core control packs reject incompatible model fields, Census identity, control vectors, universe evidence, and unsupported cells before fitting. | Both-vintage CSD/CT/ADA/DA manifest, evidence-binding, derivation, duplicate/missing-cell, reconciliation, linkage, and feasibility cases in [`test_control_packs.py`](https://github.com/dlq/synthpopcan/blob/main/tests/test_control_packs.py). | Pack definitions contain no Census counts. A passing plan is limited to the exact normalized tables, source revisions, eligible geographies, and private-household universe recorded by its evidence document. |
| Small-area reports independently recompute linked residual, concentration, candidate-reuse, rare-cell, zero-target, and field-targeting diagnostics. | Linked household/person contribution, integer realization, fitter-generated multi-scale, and external aggregate comparison cases in [`test_methodological_validation.py`](https://github.com/dlq/synthpopcan/blob/main/tests/test_methodological_validation.py). | Targeting and low residuals do not establish local representativeness; carried-through and coarsened attributes remain explicitly limited, and the external comparison is not record-level truth. |
| A versioned public Statistics Canada example reproduces independently recorded totals. | The frozen source selection, mapping, expected controls, provenance, and independent total in [`tests/fixtures/correctness`](https://github.com/dlq/synthpopcan/tree/main/tests/fixtures/correctness), exercised by [`test_reference_correctness.py`](https://github.com/dlq/synthpopcan/blob/main/tests/test_reference_correctness.py). | One reference table cannot represent every Statistics Canada product, vintage, or transformation. |
| The distributed wheel contains a working library, CLI, and required web assets. | An isolated installation outside the checkout runs IPF, resource, import-origin, and CLI checks through [`check-wheel.sh`](https://github.com/dlq/synthpopcan/blob/main/scripts/check-wheel.sh). | This is a representative packaging smoke test, not an exhaustive installed-package test. |
| Browser-facing WDS, upload, and registered-model paths reject inputs outside documented resource bounds. | Download, request, archive, decompression, row-count, concurrency, selected-member, upload, catalogue, and API regression tests in [`test_webapp.py`](https://github.com/dlq/synthpopcan/blob/main/tests/test_webapp.py), [`test_webapi.py`](https://github.com/dlq/synthpopcan/blob/main/tests/test_webapi.py), [`test_models.py`](https://github.com/dlq/synthpopcan/blob/main/tests/test_models.py), and [`test_statcan.py`](https://github.com/dlq/synthpopcan/blob/main/tests/test_statcan.py). | Resource limits reduce accidental exhaustion; they do not make the current loopback server suitable for network deployment. |
| Standalone maps preserve tested polygon topology and cannot embed supplied labels as executable HTML. | Hole/island classification, unmatched-geography, inline JSON, title escaping, and text-node tooltip tests in [`test_map_render.py`](https://github.com/dlq/synthpopcan/blob/main/tests/test_map_render.py). | Projection and topology checks cover current StatCan polygon inputs, not every malformed or non-polygon geospatial source. |
| Published external artifacts replace valid local files only after a bounded, verified transfer. | Concurrent model-cache and interrupted, oversized, or truncated StatCan transfer tests in [`test_models.py`](https://github.com/dlq/synthpopcan/blob/main/tests/test_models.py) and [`test_statcan.py`](https://github.com/dlq/synthpopcan/blob/main/tests/test_statcan.py). | A successful transfer does not independently establish the accuracy or continued availability of the upstream source. |
| Prepared display boundaries are identified unambiguously and are used only after integrity verification. | Catalogue validation, exact year/level/PRUID matching, compressed and unpacked SHA-256 checks, cache reuse, and invalid-metadata tests in [`test_geodata.py`](https://github.com/dlq/synthpopcan/blob/main/tests/test_geodata.py). | These checks verify the selected published bytes, not the substantive appropriateness of a geography or control universe. |
| Geography-bearing workflows preserve Census vintage, level, namespace, and authoritative relationship context. | Identity, universe, relationship, cross-vintage rejection, bounded Québec DA proof, and national DA/ADA planning tests in [`test_geography.py`](https://github.com/dlq/synthpopcan/blob/main/tests/test_geography.py), [`test_da_proof.py`](https://github.com/dlq/synthpopcan/blob/main/tests/test_da_proof.py), and [`test_national_small_area.py`](https://github.com/dlq/synthpopcan/blob/main/tests/test_national_small_area.py). | Matching-looking identifiers do not establish concordance across vintages, and successful national execution does not establish that one prepared model is scientifically representative for every small area. |
| Enrichment publishes validated sidecars without rewriting the linked base population. | Source/resource authority, immutable revision, normalized-layer, coverage, cross-vintage, byte-preservation, corruption, CLI, and beginner-API tests in [`test_enrichment.py`](https://github.com/dlq/synthpopcan/blob/main/tests/test_enrichment.py). | Structural and integrity checks do not validate an undocumented upstream transformation or establish causal, exposure, accessibility, or substantive research claims. |
| Exchange v1 preserves linked population bytes and detects incomplete, changed, or semantically inconsistent handoffs. | Source-byte, manifest, hash, row-count, linkage, dictionary, geography, provenance, tamper, CLI/API, fictional-demo, and installed-wheel tests in [`test_exchange.py`](https://github.com/dlq/synthpopcan/blob/main/tests/test_exchange.py), [`test_api.py`](https://github.com/dlq/synthpopcan/blob/main/tests/test_api.py), and [`check-wheel.sh`](https://github.com/dlq/synthpopcan/blob/main/scripts/check-wheel.sh). | A valid population contribution is not a runnable simulation and does not establish representativeness, privacy, substantive fitness, or compatibility with an unnamed target. |
| Durable-run evidence identifies terminal state and detects changed inputs or artifacts. | Complete, failed, cancelled, interrupted, row-recount, digest-tamper, and linked-integrity checks in [`test_runs.py`](https://github.com/dlq/synthpopcan/blob/main/tests/test_runs.py). | The evidence verifies recorded bytes and implemented checks; it is not a privacy certification or substantive-validity finding. |
| Recorded workflow recipes reproduce the represented fixed-seed artifacts. | Executed IPF, prepared-model, generated small-area, uploaded-candidate, and mapped small-area recipe tests in the workflow test modules. | Reproduction still requires access to the recorded inputs or documented replacements; restricted source data are not embedded. |

## How the evidence runs

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

Verify a locally built wheel independently of the checkout with:

```bash
uv build --wheel
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
