# Test Structure And Conventions

Organize tests around the behaviour they protect. The suite has several levels:

| Level | Purpose | Examples |
| --- | --- | --- |
| Domain and contract | Exercise valid inputs, invariants and specific rejection reasons without application services | `test_conditional_universe.py`, `test_control_pack_contracts.py` |
| Independent numerical/reference evidence | Compare against pinned expected results, separate implementations and reproducible generated cases | `test_reference_correctness.py`, `test_ipf_correctness.py` |
| Adapter and workflow integration | Exercise real CLI parsing, API normalization, files, durable runs and error presentation | `test_cli_errors.py`, `test_webapi_small_area.py`, `test_workflows.py` |
| Tooling integration | Exercise the actual quality gate or inventory boundary | `test_coverage_gate.py`, `test_complexity_guard.py`, `test_localization_inventory.py` |
| Browser acceptance | Verify complete user journeys, delayed responses and persisted results | `web/scenarios.spec.mjs`, [scenario inventory](SCENARIOS.md) |
| Installed distributions | Verify package contents and supported interfaces from outside the checkout | `../scripts/check-wheel.sh` |

Keep related tests together, but split a file when it accumulates distinct
responsibilities. Control-pack tests separate definitions/loaders, contracts,
derivations, planning, calibration and CLI behaviour. Map tests separate
geometry, statistics, boundary preparation, rendering, national summaries and
CLI commands. API tests separate application/security, models, preflight,
durable runs and small-area work.

## Fixtures And Isolation

- Put a fixture beside the tests that use it. Use function scope for mutable
  requests and filesystem/service state. A module-scoped inventory may be
  shared when tests only read it.
- Shared synthetic data builders and bounded API helpers live in `support/`.
  Import them explicitly; never import helpers from another collected test
  module. Do not turn unrelated fixtures into a global autouse environment.
- Use `tmp_path`, restore patches with `monkeypatch`, seed generated numerical
  cases, and always shut down services in a `finally` block or fixture teardown.
- Mock external I/O at the boundary. Keep the workflow or adapter under test
  real when its coordination and side effects are the subject of the test.

## Assertions And Failure Diagnostics

- Give each test one coherent behaviour. An end-to-end scenario can assert
  several related results; unrelated success and rejection cases should be
  separate tests or named parameter cases.
- Give parameter cases descriptive IDs. Assert the expected exception type and
  reason, so an unrelated rejection cannot satisfy a negative test.
- Check results and relevant side effects: exit status, output streams, saved
  evidence, unchanged inputs, unclaimed uploads and absence of partial runs.
- Use independently specified expected values for numerical correctness. Do
  not obtain the expected result by calling the implementation being tested.
- Check inventory completeness against an independent surface: the maintained
  interface contract, registered application routes, or Git-owned files.
  Spot checks are useful for policy examples but do not prove completeness.
- Keep structural wiring tests distinct from real invocations. Construct valid
  Click contexts; cover parsing and group dispatch through `CliRunner` too.
- Test quality gates through their real entry point. The precision regression
  invokes `pytest-cov` with the repository coverage configuration, clears
  inherited coverage state, and checks values below and at both thresholds.
- Assert exact bytes or wording where they are a deliberate contract. For
  other prose, assert the reason and actionable information rather than every
  punctuation choice. Passing coverage is supporting evidence, not proof of
  test quality or research validity.

## Running Checks

Use a focused file, node ID or name filter while iterating. Plain pytest does
not collect coverage unless requested. `--lf` reruns previous failures and
`--ff` runs them first. Changed-module selection is currently manual; related
workflow and adapter tests matter as well as the matching unit-test file.
There is no additional test-selection service, database or plugin to maintain.

```sh
uv run --locked pytest -q tests/test_conditional_universe.py
uv run --locked pytest -q tests/test_webapi_small_area.py -k preflight
uv run --locked pytest -q --lf
```

The full-suite pre-commit hook is manual, so a documentation commit does not
launch all Python tests. Invoke it explicitly when useful:

```sh
uv run --locked pre-commit run pytest --hook-stage manual --all-files
```

CI runs the coverage-tool integration cases once in its Python 3.12 coverage
job. Application behaviour tests still run on Python 3.11–3.14. The
`coverage_gate` marker is only for testing the coverage tool itself; it does
not exclude application tests or reduce the enforced coverage requirement.

Run the full gate at a review/release boundary or after broad shared changes,
rather than after every edit:

```sh
uv run --locked pytest tests/test_conditional_universe.py
./scripts/check.sh
UV_LOCKED=1 sh scripts/check-correctness.sh
```

Build fresh distributions and run `scripts/check-wheel.sh` for changes that
need installed-package verification. These checks include the optional
model-build and fictional case-study smokes. Follow [the contributor
guide](../CONTRIBUTING.md) and [release procedure](../RELEASING.md).

Live Statistics Canada and other external-source checks remain opt-in and
separate from deterministic regression tests. Performance checks are also
opt-in. Poll actual conditions with a bounded deadline for asynchronous work;
use deliberate delayed-response fixtures to test races rather than arbitrary
waits for ordinary browser assertions.
