# Correctness Assurance

SynthPopCan is research software. No finite test suite can prove that it is
correct for every dataset or research question. The project instead maintains
an auditable assurance case: each public correctness claim is limited, linked
to independent evidence, rerun automatically, and paired with known
limitations.

Passing these checks means that the tested version behaved as specified under
the documented conditions. It does not establish that source data or chosen
controls are accurate, that a synthetic population is statistically suitable
for every inference, or that disclosure risk has been eliminated.

## Current assurance claims

| Claim | Automated evidence | Important boundary |
| --- | --- | --- |
| Feasible IPF problems reproduce their controls within tolerance. | Generated feasible cases, independently aggregated residuals, and known-truth fixtures in [`test_ipf_correctness.py`](https://github.com/dlq/synthpopcan/blob/main/tests/test_ipf_correctness.py). | Convergence is not guaranteed for inconsistent controls, unsupported cells, or every possible input. |
| Scalar and NumPy IPF have equivalent documented semantics. | Differential, sparse-control, scaling, row-order, category-renaming, and record-duplication tests in [`test_ipf_correctness.py`](https://github.com/dlq/synthpopcan/blob/main/tests/test_ipf_correctness.py). | Differential agreement is strongest when combined with the independent invariants; two implementations could otherwise share a conceptual defect. |
| Integerization preserves the requested aggregate and is deterministic. | Generated vector properties, cumulative-discrepancy checks, traceability checks, and Python/browser parity fixtures in [`test_ipf_correctness.py`](https://github.com/dlq/synthpopcan/blob/main/tests/test_ipf_correctness.py) and [`ipf.test.mjs`](https://github.com/dlq/synthpopcan/blob/main/tests/web/ipf.test.mjs). | Integerized cells can differ from fractional targets; users must inspect realized residuals. |
| Frequency and CART model runtimes reproduce their defined probabilities and structure. | Analytical probability fixtures, scikit-learn leaf/probability comparisons, multi-seed acceptance tests, and semantic round trips in [`test_model_correctness.py`](https://github.com/dlq/synthpopcan/blob/main/tests/test_model_correctness.py). | Computational agreement does not establish that a fitted model is representative or appropriate for a research question. |
| Linked output preserves household/person relationships and generated identifier integrity. | Independent relationship, household-size, uniqueness, inheritance, privacy-column, determinism, and CSV/in-memory equivalence checks in [`test_model_correctness.py`](https://github.com/dlq/synthpopcan/blob/main/tests/test_model_correctness.py). | These checks cannot correct omissions, bias, or errors already present in training data. |
| Current small-area artifacts reconcile with supplied household and person controls. | Independent read-back aggregation, geography-isolation, serial/parallel, subsampling, non-convergence, and household/person oracle tests in [`test_small_area_correctness.py`](https://github.com/dlq/synthpopcan/blob/main/tests/test_small_area_correctness.py). | Structural zeros and incompatible controls can make an exact solution impossible and must be reported, not hidden. |
| A versioned public Statistics Canada example reproduces independently recorded totals. | The frozen source selection, mapping, expected controls, provenance, and independent total in [`tests/fixtures/correctness`](https://github.com/dlq/synthpopcan/tree/main/tests/fixtures/correctness), exercised by [`test_reference_correctness.py`](https://github.com/dlq/synthpopcan/blob/main/tests/test_reference_correctness.py). | One reference table cannot represent every Statistics Canada product, vintage, or transformation. |
| The distributed wheel contains a working library, CLI, and required web assets. | An isolated installation outside the checkout runs IPF, resource, import-origin, and CLI checks through [`check-wheel.sh`](https://github.com/dlq/synthpopcan/blob/main/scripts/check-wheel.sh). | This is a representative packaging smoke test, not an exhaustive installed-package test. |
| Browser-facing WDS and registered-model paths reject inputs outside documented resource bounds. | Download, request, archive, decompression, row-count, concurrency, selected-member, catalogue, and API regression tests in [`test_webapp.py`](https://github.com/dlq/synthpopcan/blob/main/tests/test_webapp.py) and [`wds-normalize.test.mjs`](https://github.com/dlq/synthpopcan/blob/main/tests/web/wds-normalize.test.mjs). | Resource limits reduce accidental exhaustion; they do not make the current loopback server suitable for network deployment. |
| Standalone maps preserve tested polygon topology and cannot embed supplied labels as executable HTML. | Hole/island classification, unmatched-geography, inline JSON, title escaping, and text-node tooltip tests in [`test_map_render.py`](https://github.com/dlq/synthpopcan/blob/main/tests/test_map_render.py). | Projection and topology checks cover current StatCan polygon inputs, not every malformed or non-polygon geospatial source. |
| Published external artifacts replace valid local files only after a bounded, verified transfer. | Concurrent model-cache and interrupted, oversized, or truncated StatCan transfer tests in [`test_models.py`](https://github.com/dlq/synthpopcan/blob/main/tests/test_models.py) and [`test_statcan.py`](https://github.com/dlq/synthpopcan/blob/main/tests/test_statcan.py). | A successful transfer does not independently establish the accuracy or continued availability of the upstream source. |

## How the evidence runs

- The [normal CI workflow](https://github.com/dlq/synthpopcan/actions/workflows/ci.yml)
  runs deterministic correctness tests on every pull request and push to
  `main`, across the supported Python 3.11 and 3.12 versions. It retains a
  machine-readable JUnit report for each version and commit.
- The [extended correctness workflow](https://github.com/dlq/synthpopcan/actions/workflows/correctness.yml)
  runs larger generated-case and multi-seed suites each week and on demand. It
  also checks the live Statistics Canada WDS interface for external drift.
- The [package publishing workflow](https://github.com/dlq/synthpopcan/actions/workflows/publish.yml)
  checks out an existing release tag, verifies that it exactly matches the
  package version, reruns the extended correctness suite, and tests the built
  wheel before PyPI publishing can proceed.
- Browser unit tests and real Chromium workflow scenarios check the independent
  browser implementation and its user-visible integration.

GitHub Actions artifacts are evidence for a particular commit, not a permanent
archive. Release notes should identify the tested commit and summarize the
checks that passed. Permanently attaching reports or attestations to releases
remains planned.

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
for current commands and reports. The roadmap tracks richer machine-readable
per-run assurance manifests and the remaining evidence work.

## Reporting a suspected correctness problem

Open a [GitHub issue](https://github.com/dlq/synthpopcan/issues) with the
smallest shareable reproducer, SynthPopCan version, command or API call, random
seed, expected result, and actual result. Do not attach restricted microdata or
other private inputs. Security or disclosure-sensitive findings should instead
use [private vulnerability reporting](https://github.com/dlq/synthpopcan/security/advisories/new).
