"""Developer-facing IPF benchmark fixtures."""

from __future__ import annotations

__all__ = [
    "PROVINCE_SCALE_SMALL_AREA_BUDGET",
    "SmallAreaBenchmarkBudget",
    "assess_ipf_benchmark_case",
    "build_ipf_benchmark_cases",
    "build_small_area_benchmark_fixture",
    "run_ipf_benchmark",
    "run_ipf_benchmarks",
    "run_small_area_benchmark",
]

from dataclasses import dataclass
from time import perf_counter
from typing import Any

from synthpopcan.controls import ControlCell, ControlMargin, ControlTable
from synthpopcan.ipf import IPFMargin, fit_ipf, integerize_weights
from synthpopcan.small_area_synthesis import fit_households_by_geography


@dataclass(frozen=True)
class SmallAreaBenchmarkBudget:
    """Reviewable scale and resource limits for a small-area benchmark."""

    name: str
    candidate_households: int
    target_geographies: int
    target_households: int
    max_fit_seconds: float
    max_retained_weight_bytes: int

    @property
    def weight_cells(self) -> int:
        return self.candidate_households * self.target_geographies

    def to_dict(self) -> dict[str, int | float | str]:
        """Return the budget as JSON-serializable benchmark metadata."""
        return {
            "name": self.name,
            "candidate_households": self.candidate_households,
            "target_geographies": self.target_geographies,
            "target_households": self.target_households,
            "weight_cells": self.weight_cells,
            "max_fit_seconds": self.max_fit_seconds,
            "max_retained_weight_bytes": self.max_retained_weight_bytes,
        }


PROVINCE_SCALE_SMALL_AREA_BUDGET = SmallAreaBenchmarkBudget(
    name="province_scale",
    candidate_households=10_000,
    target_geographies=1_200,
    target_households=4_500_000,
    max_fit_seconds=180.0,
    max_retained_weight_bytes=512 * 1024 * 1024,
)


@dataclass(frozen=True)
class _IPFBenchmarkCase:
    name: str
    records: list[dict[str, str]]
    margins: list[IPFMargin]
    max_iterations: int = 100
    tolerance: float = 1e-6
    expected_converged: bool = True

    @property
    def margin_cell_count(self) -> int:
        return sum(len(margin.targets) for margin in self.margins)


def build_ipf_benchmark_cases(seed_records: int = 50_000) -> list[_IPFBenchmarkCase]:
    if seed_records < 12:
        raise ValueError("seed_records must be at least 12")
    return [
        _build_easy_balanced_case(seed_records),
        _build_moderate_three_margin_case(seed_records),
        _build_high_cardinality_inconsistent_case(seed_records),
    ]


def assess_ipf_benchmark_case(
    case: _IPFBenchmarkCase,
) -> dict[str, int | float | str]:
    record_memberships = len(case.records) * len(case.margins)
    average_records_per_margin_cell = record_memberships / case.margin_cell_count
    return {
        "case": case.name,
        "seed_records": len(case.records),
        "margin_count": len(case.margins),
        "margin_cells": case.margin_cell_count,
        "record_memberships": record_memberships,
        "average_records_per_margin_cell": average_records_per_margin_cell,
        "dependency_hint": _classify_ipf_dependency_need(
            case.margin_cell_count,
            average_records_per_margin_cell,
        ),
    }


def _classify_ipf_dependency_need(
    margin_cells: int,
    average_records_per_margin_cell: float,
) -> str:
    if margin_cells >= 32 or average_records_per_margin_cell < 10:
        return "consider_sparse_or_vectorized"
    return "pure_python_ok"


def _build_easy_balanced_case(seed_records: int) -> _IPFBenchmarkCase:
    records = [
        {
            "id": str(index + 1),
            "age": "young" if index % 2 == 0 else "old",
            "sex": "female" if (index // 2) % 2 == 0 else "male",
        }
        for index in range(seed_records)
    ]
    return _IPFBenchmarkCase(
        name="easy_balanced",
        records=records,
        margins=[
            IPFMargin(("age",), {("young",): 600.0, ("old",): 600.0}),
            IPFMargin(("sex",), {("female",): 600.0, ("male",): 600.0}),
        ],
    )


def _build_moderate_three_margin_case(seed_records: int) -> _IPFBenchmarkCase:
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
    return _IPFBenchmarkCase(
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


def _build_high_cardinality_inconsistent_case(seed_records: int) -> _IPFBenchmarkCase:
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
    return _IPFBenchmarkCase(
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


def run_ipf_benchmark(case: _IPFBenchmarkCase) -> dict[str, int | float | str | bool]:
    assessment = assess_ipf_benchmark_case(case)
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
        "average_records_per_margin_cell": assessment[
            "average_records_per_margin_cell"
        ],
        "dependency_hint": assessment["dependency_hint"],
    }


def run_ipf_benchmarks(
    seed_records: int = 50_000,
) -> list[dict[str, int | float | str | bool]]:
    return [
        run_ipf_benchmark(case)
        for case in build_ipf_benchmark_cases(seed_records=seed_records)
    ]


def build_small_area_benchmark_fixture(
    *,
    candidate_households: int,
    target_geographies: int,
    target_households_per_geography: int,
) -> tuple[list[dict[str, str]], ControlTable]:
    """Build public synthetic candidates and controls for calibration timing."""
    if candidate_households < 10:
        raise ValueError("candidate_households must be at least 10")
    if target_geographies < 1:
        raise ValueError("target_geographies must be at least 1")
    if target_households_per_geography < 2:
        raise ValueError("target_households_per_geography must be at least 2")

    households = [
        {
            "synthetic_household_id": f"h{index + 1}",
            "household_size_group": str(index % 5 + 1),
            "tenure": "owner" if index % 10 < 6 else "renter",
        }
        for index in range(candidate_households)
    ]
    size_cells: list[ControlCell] = []
    tenure_cells: list[ControlCell] = []
    for geography_index in range(target_geographies):
        geography = f"G{geography_index + 1:05d}"
        for category, count in zip(
            ("1", "2", "3", "4", "5"),
            _split_integer_total(target_households_per_geography, 5),
            strict=True,
        ):
            size_cells.append(
                ControlCell(
                    {"geo": geography, "household_size_group": category},
                    count,
                )
            )
        owner_count = round(target_households_per_geography * 0.6)
        tenure_cells.extend(
            (
                ControlCell(
                    {"geo": geography, "tenure": "owner"},
                    owner_count,
                ),
                ControlCell(
                    {"geo": geography, "tenure": "renter"},
                    target_households_per_geography - owner_count,
                ),
            )
        )
    controls = ControlTable(
        margins=(
            ControlMargin(
                name="household size",
                dimensions=("geo", "household_size_group"),
                cells=tuple(size_cells),
            ),
            ControlMargin(
                name="tenure",
                dimensions=("geo", "tenure"),
                cells=tuple(tenure_cells),
            ),
        ),
        dimensions=("geo", "household_size_group", "tenure"),
    )
    return households, controls


def run_small_area_benchmark(
    households: list[dict[str, str]],
    controls: ControlTable,
    *,
    geography_dimension: str,
    n_workers: int | None = None,
) -> dict[str, Any]:
    """Time repeated-geography calibration and report its retained weight scale."""
    target_geographies = len(controls.categories_for(geography_dimension))
    target_households = sum(cell.count for cell in controls.margins[0].cells)
    start = perf_counter()
    fit = fit_households_by_geography(
        households,
        controls,
        geography_dimension=geography_dimension,
        n_workers=n_workers,
    )
    fit_seconds = perf_counter() - start
    weight_cells = len(households) * target_geographies
    return {
        "schema_version": "synthpopcan-small-area-benchmark-v1",
        "candidate_households": len(households),
        "target_geographies": target_geographies,
        "target_households": int(round(target_households)),
        "weight_cells": weight_cells,
        # Each retained Python float uses roughly 24 bytes plus an 8-byte list
        # pointer on 64-bit CPython. This excludes reports and input rows.
        "estimated_retained_weight_bytes": weight_cells * 32,
        "fit_seconds": fit_seconds,
        "converged_geographies": sum(
            bool(report["converged"]) for report in fit.reports.values()
        ),
        "max_abs_error": max(
            float(report["max_abs_error"]) for report in fit.reports.values()
        ),
    }


def _split_integer_total(total: int, groups: int) -> list[int]:
    quotient, remainder = divmod(total, groups)
    return [quotient + (index < remainder) for index in range(groups)]
