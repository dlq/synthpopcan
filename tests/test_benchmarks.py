import os

import pytest

from synthpopcan.benchmarks import (
    assess_ipf_benchmark_case,
    build_ipf_benchmark_cases,
    run_ipf_benchmark,
    run_ipf_benchmarks,
)

PERFORMANCE_ENV = "SYNTHPOPCAN_PERF_TESTS"
BROWSER_BUDGET_SECONDS = 1.0
SMALL_BENCHMARK_ROWS = 120
PERFORMANCE_BENCHMARK_ROWS = 5_000


def test_builds_named_ipf_benchmark_cases() -> None:
    cases = build_ipf_benchmark_cases(seed_records=SMALL_BENCHMARK_ROWS)

    assert [case.name for case in cases] == [
        "easy_balanced",
        "moderate_three_margin",
        "high_cardinality_inconsistent",
    ]
    assert len(cases[0].records) == SMALL_BENCHMARK_ROWS
    assert cases[0].margin_cell_count == 4
    assert cases[1].margin_cell_count > cases[0].margin_cell_count
    assert cases[2].expected_converged is False


def test_rejects_too_small_ipf_benchmark_cases() -> None:
    with pytest.raises(ValueError, match="at least 12"):
        build_ipf_benchmark_cases(seed_records=11)


def test_runs_all_small_ipf_benchmarks() -> None:
    results = run_ipf_benchmarks(seed_records=SMALL_BENCHMARK_ROWS)

    assert [result["case"] for result in results] == [
        "easy_balanced",
        "moderate_three_margin",
        "high_cardinality_inconsistent",
    ]
    assert results[-1]["expected_converged"] is False


def test_runs_small_ipf_benchmark_case() -> None:
    case = build_ipf_benchmark_cases(seed_records=SMALL_BENCHMARK_ROWS)[0]

    result = run_ipf_benchmark(case)

    assert result["case"] == "easy_balanced"
    assert result["seed_records"] == SMALL_BENCHMARK_ROWS
    assert result["margin_cells"] == 4
    assert result["converged"] is True
    assert result["iterations"] > 0
    assert result["fit_seconds"] >= 0
    assert result["expanded_rows"] == SMALL_BENCHMARK_ROWS * 10
    assert result["average_records_per_margin_cell"] == SMALL_BENCHMARK_ROWS / 2
    assert result["dependency_hint"] == "pure_python_ok"


def test_assesses_ipf_benchmark_case_shape_for_dependency_decisions() -> None:
    cases = build_ipf_benchmark_cases(seed_records=SMALL_BENCHMARK_ROWS)

    assessments = {case.name: assess_ipf_benchmark_case(case) for case in cases}

    assert assessments["easy_balanced"] == {
        "case": "easy_balanced",
        "seed_records": SMALL_BENCHMARK_ROWS,
        "margin_count": 2,
        "margin_cells": 4,
        "record_memberships": SMALL_BENCHMARK_ROWS * 2,
        "average_records_per_margin_cell": SMALL_BENCHMARK_ROWS / 2,
        "dependency_hint": "pure_python_ok",
    }
    assert assessments["high_cardinality_inconsistent"]["dependency_hint"] == (
        "consider_sparse_or_vectorized"
    )


@pytest.mark.performance
@pytest.mark.skipif(
    os.environ.get(PERFORMANCE_ENV) != "1",
    reason=f"set {PERFORMANCE_ENV}=1 to run timing-sensitive tests",
)
def test_moderate_ipf_benchmark_stays_under_browser_budget() -> None:
    case = build_ipf_benchmark_cases(seed_records=PERFORMANCE_BENCHMARK_ROWS)[1]

    result = run_ipf_benchmark(case)

    assert result["converged"] is True
    assert result["fit_seconds"] < BROWSER_BUDGET_SECONDS
