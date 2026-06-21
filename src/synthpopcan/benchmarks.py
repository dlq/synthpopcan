"""Developer-facing IPF benchmark fixtures."""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter

from synthpopcan.ipf import IPFMargin, Record, fit_ipf, integerize_weights


@dataclass(frozen=True)
class IPFBenchmarkCase:
    name: str
    records: list[Record]
    margins: list[IPFMargin]
    max_iterations: int = 100
    tolerance: float = 1e-6
    expected_converged: bool = True

    @property
    def margin_cell_count(self) -> int:
        return sum(len(margin.targets) for margin in self.margins)


def build_ipf_benchmark_cases(seed_records: int = 50_000) -> list[IPFBenchmarkCase]:
    if seed_records < 12:
        raise ValueError("seed_records must be at least 12")
    return [
        build_easy_balanced_case(seed_records),
        build_moderate_three_margin_case(seed_records),
        build_high_cardinality_inconsistent_case(seed_records),
    ]


def build_easy_balanced_case(seed_records: int) -> IPFBenchmarkCase:
    records = [
        {
            "id": str(index + 1),
            "age": "young" if index % 2 == 0 else "old",
            "sex": "female" if (index // 2) % 2 == 0 else "male",
        }
        for index in range(seed_records)
    ]
    return IPFBenchmarkCase(
        name="easy_balanced",
        records=records,
        margins=[
            IPFMargin(("age",), {("young",): 600.0, ("old",): 600.0}),
            IPFMargin(("sex",), {("female",): 600.0, ("male",): 600.0}),
        ],
    )


def build_moderate_three_margin_case(seed_records: int) -> IPFBenchmarkCase:
    age_groups = [f"age_{index:02d}" for index in range(10)]
    regions = [f"region_{index:02d}" for index in range(6)]
    sexes = ["female", "male"]
    records = [
        {
            "id": str(index + 1),
            "age": age_groups[index % len(age_groups)],
            "sex": sexes[(index // len(age_groups)) % len(sexes)],
            "region": regions[(index // (len(age_groups) * len(sexes))) % len(regions)],
        }
        for index in range(seed_records)
    ]
    target_total = float(seed_records * 5)
    return IPFBenchmarkCase(
        name="moderate_three_margin",
        records=records,
        margins=[
            IPFMargin(
                ("age",),
                {(age,): target_total / len(age_groups) for age in age_groups},
            ),
            IPFMargin(
                ("sex",),
                {(sex,): target_total / len(sexes) for sex in sexes},
            ),
            IPFMargin(
                ("region",),
                {(region,): target_total / len(regions) for region in regions},
            ),
        ],
    )


def build_high_cardinality_inconsistent_case(seed_records: int) -> IPFBenchmarkCase:
    age_groups = [f"age_{index:02d}" for index in range(36)]
    sexes = ["female", "male"]
    records = [
        {
            "id": str(index + 1),
            "age": age_groups[index % len(age_groups)],
            "sex": sexes[index % len(sexes)],
        }
        for index in range(seed_records)
    ]
    target_total = float(seed_records * 5)
    age_targets = {(age,): target_total / len(age_groups) for age in age_groups}
    return IPFBenchmarkCase(
        name="high_cardinality_inconsistent",
        records=records,
        margins=[
            IPFMargin(("age",), age_targets),
            IPFMargin(
                ("sex",),
                {
                    ("female",): target_total * 0.8,
                    ("male",): target_total * 0.2,
                },
            ),
        ],
        expected_converged=False,
    )


def run_ipf_benchmark(case: IPFBenchmarkCase) -> dict[str, int | float | str | bool]:
    start = perf_counter()
    result = fit_ipf(
        case.records,
        case.margins,
        max_iterations=case.max_iterations,
        tolerance=case.tolerance,
    )
    fit_seconds = perf_counter() - start
    return {
        "case": case.name,
        "seed_records": len(case.records),
        "margin_cells": case.margin_cell_count,
        "iterations": result.iterations,
        "converged": result.converged,
        "expected_converged": case.expected_converged,
        "max_abs_error": result.max_abs_error,
        "fit_seconds": fit_seconds,
        "expanded_rows": sum(integerize_weights(result.weights)),
    }


def run_ipf_benchmarks(
    seed_records: int = 50_000,
) -> list[dict[str, int | float | str | bool]]:
    return [
        run_ipf_benchmark(case)
        for case in build_ipf_benchmark_cases(seed_records=seed_records)
    ]
