# Python 3.15 Clean-Linux Acceptance — 2026-11-22

A clean GitHub-hosted Linux x86-64 runner tested CPython 3.15.2 with the
committed numerical lock refresh, both `performance` and `model-build` extras,
and the development and documentation groups. This is experimental evidence,
not a change to the supported Python versions.

The [final acceptance run](https://github.com/dlq/synthpopcan/actions/runs/45061339518)
used snapshot `7c822010710ccae4d01824acda24b8f4ae498b1a`. The full Python
suite passed 2,841 tests with seven skips and 95.35% branch coverage; the
extended correctness selection passed 362 tests. Documentation and 28 browser
scenarios passed. Clean installation and smoke checks passed for the wheel,
sdist, `performance` extra, `model-build` extra and fictional case study.

The installed numerical versions included NumPy 2.5.5, SciPy 1.18.1, pandas
3.1.1, Polars 2.1.0, Numba 0.68.1 and scikit-learn 1.9.1. The runner was
Ubuntu Linux x86-64; this does not establish support on every operating system,
architecture or free-threaded build.

The seven skipped tests were one timing-sensitive benchmark, one check that
requires locally acquired Statistics Canada source files, two live
CAN-FED/ODEF reference checks, and three live WDS checks. The extended
correctness run did not skip tests. The full suite emitted one upstream
pytest/AnyIO deprecation warning. Live sources were intentionally outside
this offline acceptance gate.

The earlier [initial run](https://github.com/dlq/synthpopcan/actions/runs/45060095845)
found a workflow test that assumed exactly two locked installations; the test
was corrected to check the scheduled jobs separately from the new experimental
job. A subsequent run caught a browser assertion made ambiguous by the new
model heading; it was narrowed to the model form heading before the passing
run above. These were test-harness failures, not Python 3.15 runtime failures.

Promoting 3.15 to the supported blocking matrix remains a separate platform
policy decision (`ASSURE315-03`), including any changes to classifiers and
public support documentation.
