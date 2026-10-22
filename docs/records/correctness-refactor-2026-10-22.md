# Correctness And Refactoring — 2026-10-22

This development amendment records defects reproduced after the naming audit.
The package remains version `1.1.1`; these changes are unreleased. Earlier
release evidence and dated measurements remain historical records.

## Reproduced Failures And Corrections

| Failure | Correction and regression evidence |
| --- | --- |
| Web preflight added five independent person-margin totals of 21 and compared 105 with a population of 21. | Web and domain planning now use the same structure, reconciliation, evidence-binding, and universe policies. Both-vintage broad-pack preflight fixtures reconcile each person margin independently. |
| A request containing a registered model, package upload, and linked candidate pair was accepted and extra sources were discarded. | Source selection admits exactly one model, one package, or one complete linked pair. All 13 invalid combinations of the four source fields are covered. |
| Missing map fields produced zero percentages and zero household income. | Unknown observations remain null and unobserved variables are omitted. Percentages require complete observations; incomplete household incomes remain unknown. Actual zero income remains zero. |
| The map immigrant percentage included non-permanent residents. | The numerator follows the registry's immigrant category, keeping non-permanent residents separate. The three-category fixture expects 33.3%, rather than 66.7%. |
| Excess expansion weights were silently ignored; too few weights caused an index error. | Length mismatch raises a specific validation error before integerization or expansion. |
| A NaN tolerance made model validation pass a 0.5 proportion shift, including CLI exit status zero. | Non-finite and negative tolerances fail validation. The CLI regression requires a failure exit and actionable error. |
| Finite extreme starting weights and targets overflowed the adjustment ratio, eventually reporting scalar convergence with a NaN weight. | Adjustment uses a normalized fallback when the ratio overflows or underflows; finite feasible targets remain finite on both backends. Non-finite accumulated totals and residuals fail closed. |

The ordinary-scale numerical audit also checked 50 independently solved 2×2
IPF problems on both backends and 200 integerization cases. Twelve deterministic
2×2 oracle cases are retained in the correctness suite: a high-precision
odds-ratio equation determines the expected fitted cells independently of
either IPF implementation.

## Responsibility Changes

- `workflows.preflight` owns small-area source resolution, controls, support,
  geography, capacity, and normalization behind typed stage/result objects and
  a narrow upload-resolver protocol. The HTTP adapter retains parsing and the
  existing response representation.
- `workflows.national` owns candidate-pool reuse/preparation, plan checks,
  execution, and summary assembly. The geography CLI retains option parsing,
  error presentation, and optional map presentation.
- Worker sessions share cancellation, progress events, artifact publication,
  success messages, and failure translation. Preparation failures also produce
  one terminal failure message.
- `_map_statistics` owns observed statistics independently of map geometry and
  HTML rendering.

The frozen interface baseline, supported CLI spellings, public signatures,
saved schemas, and publication authority remain unchanged. New numerical
guards and extracted functions pass the complexity ratchet without increasing
existing limits. These preparation changes do not admit a new conditional
control family or complete the localization feature work for `1.2.0`.

## Verification

The final local `scripts/check.sh` run passes with 2,048 Python tests and seven
opt-in live/performance skips, 95.47% combined statement/branch coverage, 35 web
unit tests, and 13 browser scenarios. Lint, formatting, standard typing,
complexity, citation metadata, documentation style, and the warning-free Sphinx
build pass. The frozen public-interface contract is current without regeneration.

The extended numerical correctness selection passes all 358 tests. Fresh wheel
and source-distribution installs pass outside the checkout, as do the optional
`model-build` extra and fictional case-study interface smokes. The released
Quebec model bytes and live Statistics Canada service were not tested.

`RB12-02` and `RB12-03` are complete. `TYPE12-02` is ready for its separate strict
typing slice; this extraction does not claim that the new workflow is strict-clean.
The 95.47% coverage result exceeds the 95.25% candidate headroom requirement,
which must be rechecked for the eventual release candidate.
