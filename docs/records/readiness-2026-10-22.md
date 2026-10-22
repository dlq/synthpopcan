# 1.2.0 Preparation Record — 2026-10-22

This records preparation for the November–December 2026 release window. It is
not a release candidate or an acceptance claim for new statistical controls.
The software version remains 1.1.1; the CLI error improvements are on main.

## Conditional-Person Universe Contract (`SA12-01`)

The internal `synthpopcan-conditional-person-universe-v1` contract is implemented
in `synthpopcan._conditional_universe`. It records one fully identified Census
geography, the all-private-household population, age-15+ population, an explicit
under-15 population, and a non-empty source-evidence reference.

The proof requires:

- reviewed 2016 or 2021 geography identity, including namespace and identifier;
- finite, non-negative observed counts; missing, suppressed, textual, boolean,
  negative and non-finite values are rejected;
- reconciled age-15+ plus under-15 targets equal to the all-private-household
  total (absolute numerical comparison tolerance `1e-9`);
- an exhaustive, mutually exclusive eligible category vector summing to the
  age-15+ denominator; and
- a separately evidenced under-15 not-applicable target.

This numerical tolerance is not permission to absorb Census rounding. Raw
rounded counts must be reconciled upstream under the reviewed source policy,
with raw counts, row identities, suppression decisions, reconciliation method
and adjusted targets retained in the referenced evidence. No count is inferred
by substituting zero for suppression or silently subtracting incompatible
published totals. The contract does not perform reconciliation itself.

The internal validator rejects mismatches before a caller can proceed to
fitting. It does not change existing packs, fit weights, assign categories,
classify candidate ages, or admit a new control family. `SA12-10` must connect
the accepted universe proof to preparers and preflight, preserve evidence, and
reject candidate age bands that cannot distinguish the cutoff. An explicit
conditional fitting path may exclude children from its eligible indicators
only while retaining their counts and identities in the universe evidence.

Each of marital status, education, labour-force status and work activity still
requires its independent vintage-specific source review. A family with a
narrower or otherwise different universe cannot reuse this contract by merely
renaming its denominator. Existing broad packs remain unchanged.

## Localization Inventory (`I18N12-01`, in progress)

[The generated inventory](readiness-2026-10-22/localization.json) covers the
complete Click command tree, including groups, aliases and option help, static
web API routes, package files, user documentation and historical exclusions.
Python literal locations are recorded against file content hashes. Dictionary
keys are separated from human/source candidates and docstrings needing CLI-help
or maintainer classification. The file policy distinguishes presentation,
domain/workflow messages, machine contracts, user documentation and historical
records. It preserves source labels pending provenance review.

This is an extraction inventory, not a translation catalogue. Remaining work:
review ambiguous literal roles; inventory individual HTML/JavaScript prose,
accessibility labels, automation logs and verbatim third-party notices; and
review the complete classification before closing `I18N12-01`. Canonical
locales remain `en-CA` and `fr-CA`, with English fallback. No French product
coverage is claimed and no locale-dependent machine output is introduced.

## Typing Baseline (`TYPE12-01`)

[The strict audit](readiness-2026-10-22/typing.json) records the Pyright version,
files analyzed, findings by rule and file, diagnostic-bearing file counts by
scope, and the blocking strict-path list. Reproduce from the locked development
environment using the script below.

The older 1,095-finding audit covered the package before later refactors. The
current configuration also discovers maintainer scripts. Compare package and
script findings separately; a combined total is not a package regression
measure. Standard-mode package/script checks remain blocking. The new internal universe
module and audit script are strict-clean and join the blocking strict list.

## Complexity Baseline (`RB12-04`)

[The baseline](readiness-2026-10-22/complexity.json) records Ruff C901 complexity
for qualified functions in package code and maintainer scripts, including
functions with `noqa`, plus physical package line concentration. Line counts
include prose/comments and are descriptive, not a quality limit.

The local and CI quality gates reject a function whose complexity exceeds its
recorded value. A new function must stay at or below 10. Qualified names make
line-number changes irrelevant. Baseline increases require explicit review;
do not regenerate the baseline merely to suppress a failing gate. Removed or
renamed functions remain subject to the new-function threshold.

## Coverage Precision (`RB12-05`)

Coverage now reports and enforces two decimal places. Regression checks use real
coverage data to prove that 94.50% and 94.99% fail the 95.00% gate and 95.00%
passes. The candidate target remains 95.25%; this preparation does not lower it
or claim full release acceptance. The final local Python gate passes 1,922
tests with 7 documented skips and 95.26% combined statement/branch coverage
under an explicit `--cov-fail-under=95.25` check. The actual release candidate
must retain this threshold on its exact commit.

## Verification

The complete local source/type/lint/citation/documentation/web gate passes,
including 13 browser scenarios. The final coverage run above includes the
additional overflow rejection fixture. The extended numerical suite passes
339 tests. Fresh wheel and sdist installations pass the installed interface,
resource and 24-pack smoke tests; the new universe validator also passes an
installed-wheel check. These are local preparation results, not a published
1.2.0 release or a new GitHub CI result.

## Reproduction

Run from the checkout with locked development dependencies:

```sh
uv run --locked python scripts/audit_release_readiness.py typing
uv run --locked python scripts/audit_release_readiness.py localization
uv run --locked python scripts/audit_release_readiness.py complexity \
  --baseline docs/records/readiness-2026-10-22/complexity.json
```

The inventories require no source-service access and make no external writes.
Use `--output PATH` to save a new dated audit; preserve this record as evidence.
The complexity baseline is an intentional review gate, not an automatically
refreshed file. Localization and strict counts are dated snapshots rather
than continuously asserted completion claims.

## Same-Day Amendment — Test Structure And Development Cost

A subsequent test-quality review strengthened the preparation tests and split
mixed API, control-pack and map suites by responsibility. Before decomposing
individual scenarios, collection comparisons verified that all 184 existing
cases in those three suites were retained. Shared data builders now live in
`tests/support`; collected test modules do not import one another.

The coverage precision tests invoke pytest-cov directly with the repository
configuration. Exact ratios minimize fixture size. Inventory tests compare
complete CLI paths with the interface contract, routes with the registered
application, and source-file coverage with Git-owned files. Known literal
fixtures verify roles and source hashes. CLI wiring tests construct valid
contexts, and real Click invocations cover every top-level family. Universe
rejections have descriptive cases and assertions about their specific cause.

The full local gate passes 1,988 Python tests with 7 documented skips and
95.26% combined coverage, 35 web unit tests, 13 browser scenarios, and the
source/type/lint/citation/documentation checks. The extended suite passes
339 tests. Wheel, sdist, optional model-build and fictional case-study installed
smokes all pass. The seven skips retain their existing opt-in conditions;
these results do not assert that the live Statistics Canada service recovered.

Development uses explicit pytest file/node/name selection without coverage by
default. The full-suite pre-commit hook is manual. CI runs the coverage-tool
regressions once in the Python 3.12 coverage job while retaining application
behaviour checks across Python 3.11–3.14. No changed-module selection service,
new dependency, or persistent test-selection database is introduced.

On this workstation, the final Python coverage run took about 99 seconds. A
separate run of the CI compatibility selection, without coverage-tool cases or
coverage collection, passed 1,983 tests in about 26 seconds. These are local
observations, not timing guarantees or additional performance gates. See the
[test guide](https://github.com/dlq/synthpopcan/blob/main/tests/README.md) for the
intended development sequence.

## Naming amendment (2026-10-22)

The naming cleanup moves control advice into `control_suggestions`, standardizes
Click callback suffixes, and adds preferred acronym and serialization names.
Previous library imports, CLI spellings, serialization override hooks, and the
frozen 1.x interface baseline remain supported. The naming policy is maintained
in the repository's `CONTRIBUTING.md`.

The complexity inventory carries its original numeric limits forward under
renamed function identities. Its `identity_renames_2026_10_22` map records those
exact moves; the inventory was not regenerated from the refactored code.
Historical module-line measurements, typing findings, and localization source
hashes still describe the original preparation snapshot.
