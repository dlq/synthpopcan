# Correctness Assurance Maintenance Plan

Status: active maintenance\
Created: 2026-07-12\
Last updated: 2026-11-21\
Target: ongoing correctness and release evidence\
Next action: preserve the frozen `1.x` interface and exact-commit assurance
gates; apply a separately reviewed Python 3.15 lock refresh and run Linux CI before changing the
supported matrix\
Roadmap: [PLANS.md](../PLANS.md) | [Plan index](README.md)

## Current Contract

SynthPopCan must retain an auditable assurance case for numerical results,
generated distributions, linked records, and persisted artifacts. The current
public claims and limitations live in [CORRECTNESS.md](../CORRECTNESS.md).

Every maintained or newly released workflow must, in proportion to its risk:

- test mathematical and structural invariants independently of report
  serialization;
- reconcile emitted evidence by reading the artifact back;
- distinguish deterministic software correctness from statistical fitness,
  source validity, disclosure safety, and substantive interpretation;
- preserve exact inputs, configuration, seeds, versions, hashes, and relevant
  environment identity;
- fail closed on malformed, incompatible, incomplete, or unsupported evidence;
  and
- keep compatibility, coverage, correctness, installed-distribution, and
  exact-release-commit gates blocking.

Passing the project gate establishes behavior only under the tested conditions.
It does not certify source accuracy, representativeness, disclosure safety,
causal validity, or fitness for a particular study.

## Maintenance Triggers

Review this plan whenever a change:

- alters a numerical method, tolerance, integerization rule, stopping rule, or
  random process;
- adds a control family, geography level, source universe, model profile, or
  persisted evidence schema;
- changes linkage, reconciliation, suppression, missingness, or structural-zero
  handling;
- changes a released interface or installed-distribution behavior; or
- expands a correctness, utility, privacy, or performance claim.

The change must name the independent oracle, invariant, comparison, fixture,
or bounded empirical evidence that supports it. A new claim without a matching
gate is incomplete work.

## Ongoing Release Gate

Later `1.x` releases must preserve:

1. exact source-version, lockfile, and public-interface checks;
1. the normal test suite with the documented branch-coverage threshold;
1. extended correctness and methodological evidence tests;
1. warning-clean documentation and web/browser checks;
1. fresh wheel and sdist construction plus isolated installed-package smokes;
1. immutable, checksummed, attested release evidence bound to the exact green
   CI commit; and
1. read-back verification of every public artifact before a claim is recorded.

The operator sequence is in [RELEASING.md](../RELEASING.md). Release history
belongs in [CHANGELOG.md](../CHANGELOG.md), not in this plan.

## PR-Sized Work

The `1.2.0` tooling slices are complete. The Python 3.15 slices are
maintenance work, independent of a committed feature release.

| ID | Status | Depends on | Deliverable | Acceptance |
| --- | --- | --- | --- | --- |
| `ASSURE12-01` | `done` | Current pytest organization and release gates | One lightweight runner with named test selections and conservative selection from changed files ([#54](https://github.com/dlq/synthpopcan/issues/54)) | Local and CI invocations share named selections; dry runs explain choices, and regression tests cover mappings, missing files and full-suite fallback |
| `ASSURE12-02` | `done` | `ASSURE12-01` | GitHub CI integration and contributor guidance | [PR #57](https://github.com/dlq/synthpopcan/pull/57) verified the safe full-suite fallback in the affected compatibility jobs, while the full coverage job, matrix summary, web and distribution checks passed; contributor commands and timings are documented |
| `ASSURE315-01` | `done` | [Python 3.15 review](../docs/records/python-3.15-review-2026-11-20.md) | Review a targeted lockfile refresh and development-tool build requirements | Check NumPy/SciPy and other 3.15 wheel availability, resolve the locked base and both optional extras without ad hoc system builds, and run the existing Python 3.11–3.14 matrix; record any remaining tooling constraints. |
| `ASSURE315-01B` | `in progress` | `ASSURE315-01` and [lock review](../docs/records/python-3.15-lock-review-2026-11-21.md) | Apply and review the targeted numerical lock refresh | NumPy and SciPy have been refreshed as reviewed; run the existing locked Python 3.11–3.14 CI matrix and affected package checks without changing the support claim. Record or separately review any additional dependency updates. |
| `ASSURE315-02` | `blocked` | `ASSURE315-01B` | Run the full Python 3.15 acceptance gate on clean Linux CI | Test the refreshed locked environment with the full Python suite and coverage, extended correctness, documentation and web/browser checks, and clean wheel and sdist installation including `performance` and `model-build` extras; record versions, platform, results and skips. A non-blocking experimental job may gather evidence before support is promoted. |
| `ASSURE315-03` | `blocked` | `ASSURE315-02` and reviewed platform policy | Decide whether to promote Python 3.15 to supported blocking CI | Only after the full gate passes, review supported-platform limits and update the blocking matrix, Python classifier and public support documentation together; otherwise record the blockers and retain the current matrix. |

Keep ordinary development focused on affected behaviour. Coverage thresholds
apply to full-suite runs, not partial selections. Extended numerical and
installed-distribution checks remain available as explicit selections and
mandatory release gates. Prefer a small explicit mapping with safe fallback
over a new test framework or an opaque dependency-discovery service.

## Python 3.15 Runtime Review

Keep Python 3.11–3.14 as the supported blocking CI matrix. Python 3.15.2
passed the local full suite and published-distribution smokes with a temporary
NumPy and SciPy refresh, but the committed lock lacks 3.15 wheels and clean
Linux CI has not yet verified it. Add 3.15 only after the locked runtime and
model-build dependencies install without ad hoc system build requirements and
the complete gate passes. The [review record](../docs/records/python-3.15-review-2026-11-20.md)
contains the measured results, prerelease baseline and remaining work. The
[lock review](../docs/records/python-3.15-lock-review-2026-11-21.md) adds a
local supported-Python matrix and isolates development-tool build requirements.
The targeted numerical refresh is applied for `ASSURE315-01B`; the existing
supported-Python CI matrix and affected package checks remain its acceptance
gate. The refresh does not itself add Python 3.15 support.

## Conditional Extensions

Broader controls and uncertainty work remain owned by their dedicated plans:

- [Expanded Small-Area Controls](2026-08-01-expanded-small-area-controls.md)
- [Methodological Validation and Uncertainty](2026-08-02-methodological-validation-and-uncertainty.md)
- [Expanded Hierarchical Tree Models](2026-08-01-expanded-hierarchical-tree-models.md)

They become release work only after the trigger and bounded evidence tranche in
the owning plan are satisfied.

## Preserved Baseline

The detailed implementation and acceptance record through `1.0.0` is preserved
as the [Correctness Assurance Baseline](archive/2026-07-12-correctness-assurance-baseline.md).
It is historical evidence, not the current task list.
