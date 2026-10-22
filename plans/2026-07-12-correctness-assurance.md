# Correctness Assurance Maintenance Plan

Status: active maintenance\
Created: 2026-07-12\
Last updated: 2026-10-22\
Target: ongoing correctness and release evidence\
Next action: preserve the frozen `1.x` interface and exact-commit assurance
gates; implement the shared local/CI test selections for `1.2.0`, and reassess
Python 3.15 support after its final release and ecosystem-wheel availability
in November 2026\
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

These tooling slices are scheduled for `1.2.0`; they do not change the `1.1.2`
release harness.

| ID | Status | Depends on | Deliverable | Acceptance |
| --- | --- | --- | --- | --- |
| `ASSURE12-01` | `ready` | Current pytest organization and release gates | One lightweight runner with named test selections and conservative selection from changed files | Local and CI invocations resolve the same named selection; dry-run output explains selected tests; shared or unmapped changes fall back to the full suite; selection regressions verify omissions and fallback without adding a heavyweight dependency |
| `ASSURE12-02` | `blocked` | `ASSURE12-01` | GitHub CI integration and contributor guidance | Pull requests can use affected selections through the shared runner; main and release workflows retain full supported-Python, coverage, correctness, web, and distribution gates; required checks cannot report success merely because selection is empty or an upstream job failed; equivalent local commands and measured runtime are documented |

Keep ordinary development focused on affected behaviour. Coverage thresholds
apply to full-suite runs, not partial selections. Extended numerical and
installed-distribution checks remain available as explicit selections and
mandatory release gates. Prefer a small explicit mapping with safe fallback
over a new test framework or an opaque dependency-discovery service.

## Scheduled Runtime Review

Keep Python 3.11 through 3.14 as the supported, blocking CI matrix for now. In
November 2026, after Python 3.15 final has had time to reach downstream binary
packages, test the complete locked dependency graph and full project gate on
3.15. Add it to the supported matrix only when runtime and `model-build`
dependencies install without ad hoc system build requirements and the full
suite passes.

An initial local check on Python 3.15.0rc1 found no core SynthPopCan failure:
the locked runtime installed from source, package imports and version metadata
worked, and a bounded API/IPF/schema slice passed 100 tests. The optional
`model-build` environment was not ready on macOS ARM64 because SciPy lacked a
matching wheel and its source build required a separately installed OpenBLAS.
This is useful prerelease evidence, not a support claim or a reason to expand
the current CI matrix.

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
