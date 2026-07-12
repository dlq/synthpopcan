import os

import pytest

from synthpopcan.benchmarks import (
    PROVINCE_SCALE_SMALL_AREA_BUDGET,
    assess_ipf_benchmark_case,
    build_ipf_benchmark_cases,
    build_small_area_benchmark_fixture,
    run_ipf_benchmark,
    run_ipf_benchmarks,
    run_small_area_benchmark,
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


def test_builds_and_runs_small_area_benchmark_fixture() -> None:
    households, controls = build_small_area_benchmark_fixture(
        candidate_households=120,
        target_geographies=3,
        target_households_per_geography=40,
    )

    result = run_small_area_benchmark(
        households,
        controls,
        geography_dimension="geo",
        n_workers=1,
    )

    assert len(households) == 120
    assert result["candidate_households"] == 120
    assert result["target_geographies"] == 3
    assert result["target_households"] == 120
    assert result["weight_cells"] == 360
    assert result["estimated_retained_weight_bytes"] == 360 * 32
    assert result["converged_geographies"] == 3
    assert result["fit_seconds"] >= 0


@pytest.mark.parametrize(
    ("candidate_households", "target_geographies", "target_households", "message"),
    [
        (9, 1, 2, "candidate_households must be at least 10"),
        (10, 0, 2, "target_geographies must be at least 1"),
        (10, 1, 1, "target_households_per_geography must be at least 2"),
    ],
)
def test_small_area_benchmark_fixture_rejects_invalid_scale(
    candidate_households: int,
    target_geographies: int,
    target_households: int,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        build_small_area_benchmark_fixture(
            candidate_households=candidate_households,
            target_geographies=target_geographies,
            target_households_per_geography=target_households,
        )


def test_province_scale_small_area_budget_is_explicit() -> None:
    budget = PROVINCE_SCALE_SMALL_AREA_BUDGET.to_dict()

    assert budget["name"] == "province_scale"
    assert budget["candidate_households"] == 10_000
    assert budget["target_geographies"] == 1_200
    assert budget["weight_cells"] == 12_000_000
    assert budget["max_retained_weight_bytes"] == 512 * 1024 * 1024
