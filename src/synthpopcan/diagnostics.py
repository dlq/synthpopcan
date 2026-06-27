"""Diagnostics for fitted synthetic population workflows."""

from __future__ import annotations

__all__ = [
    "build_control_total_checks",
    "build_ipf_fit_report",
    "build_ipf_input_report",
    "format_categories",
    "format_number",
    "relative_error",
    "suggest_ipf_fit_next_steps",
]

from typing import Any

from synthpopcan.controls import ControlTable
from synthpopcan.ipf import IPFResult, Record, _category_key, weighted_totals


def build_ipf_fit_report(
    control_table: ControlTable,
    result: IPFResult,
    *,
    precomputed_totals: dict[tuple[str, ...], dict[tuple[str, ...], float]]
    | None = None,
) -> dict[str, Any]:
    """Build a fit-quality report for a completed IPF result.

    Parameters
    ----------
    precomputed_totals:
        Optional mapping ``{dimensions: {category_key: total}}`` computed by
        :meth:`~synthpopcan.ipf.NumpyIPFIndex.compute_totals`.  When present,
        the Python ``weighted_totals`` loop is skipped for those margins,
        replacing it with the pre-computed numpy totals.
    """
    margins: list[dict[str, Any]] = []
    margin_summaries: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    control_total_checks = build_control_total_checks(control_table)
    if control_total_checks["status"] == "inconsistent":
        min_total = format_number(control_total_checks["min_total"])
        max_total = format_number(control_total_checks["max_total"])
        issues.append(
            {
                "severity": "error",
                "kind": "inconsistent_control_totals",
                "margin": "multiple",
                "message": (
                    "Control margins do not agree on total population: "
                    f"smallest total is {min_total} and largest total is {max_total}."
                ),
                "tip": (
                    "Review the source tables, filters, geography, and category "
                    "mappings before fitting."
                ),
                "abs_error": control_total_checks["difference"],
            }
        )
    for control_margin in control_table.margins:
        if (
            precomputed_totals is not None
            and control_margin.dimensions in precomputed_totals
        ):
            totals = precomputed_totals[control_margin.dimensions]
        else:
            totals = weighted_totals(
                result.records,
                result.weights,
                control_margin.dimensions,
            )
        cells: list[dict[str, Any]] = []
        target_total = 0.0
        fitted_total = 0.0
        max_abs_error = 0.0
        max_relative_error = 0.0
        for cell in control_margin.cells:
            key = tuple(
                cell.categories[dimension] for dimension in control_margin.dimensions
            )
            fitted = totals.get(key, 0.0)
            residual = fitted - cell.count
            abs_error = abs(residual)
            target_total += cell.count
            fitted_total += fitted
            max_abs_error = max(max_abs_error, abs_error)
            max_relative_error = max(
                max_relative_error, relative_error(abs_error, cell.count)
            )
            cells.append(
                {
                    "categories": dict(cell.categories),
                    "target": cell.count,
                    "fitted": fitted,
                    "residual": residual,
                }
            )
            if not result.converged and abs_error > 0:
                category_label = format_categories(cell.categories)
                issues.append(
                    {
                        "severity": "warning",
                        "kind": "cell_residual",
                        "margin": control_margin.name,
                        "categories": dict(cell.categories),
                        "message": (
                            f"Largest residual is {format_number(abs_error)} "
                            f"for {category_label}."
                        ),
                        "tip": (
                            "Check whether this control conflicts with another "
                            "margin or whether the seed data needs records for "
                            "this category combination."
                        ),
                        "abs_error": abs_error,
                    }
                )
        margins.append(
            {
                "name": control_margin.name,
                "dimensions": list(control_margin.dimensions),
                "cells": cells,
            }
        )
        margin_summaries.append(
            {
                "name": control_margin.name,
                "dimensions": list(control_margin.dimensions),
                "cells": len(control_margin.cells),
                "target_total": target_total,
                "fitted_total": fitted_total,
                "max_abs_error": max_abs_error,
                "max_relative_error": max_relative_error,
            }
        )

    return {
        "converged": result.converged,
        "iterations": result.iterations,
        "max_abs_error": result.max_abs_error,
        "seed_records": len(result.records),
        "control_total_checks": control_total_checks,
        "issues": sorted(
            issues,
            key=lambda issue: issue["abs_error"],
            reverse=True,
        ),
        "suggested_next_steps": suggest_ipf_fit_next_steps(
            control_total_checks,
            issues,
        ),
        "margin_summaries": margin_summaries,
        "margins": margins,
    }


def build_control_total_checks(control_table: ControlTable) -> dict[str, Any]:
    totals = [
        {
            "margin": margin.name,
            "dimensions": list(margin.dimensions),
            "target_total": sum(cell.count for cell in margin.cells),
        }
        for margin in control_table.margins
    ]
    if not totals:
        return {
            "status": "ok",
            "totals": [],
            "min_total": 0.0,
            "max_total": 0.0,
            "difference": 0.0,
        }
    total_values = [float(total["target_total"]) for total in totals]
    min_total = min(total_values)
    max_total = max(total_values)
    difference = max_total - min_total
    return {
        "status": "inconsistent" if difference > 1e-9 else "ok",
        "totals": totals,
        "min_total": min_total,
        "max_total": max_total,
        "difference": difference,
    }


def suggest_ipf_fit_next_steps(
    control_total_checks: dict[str, Any],
    issues: list[dict[str, Any]],
) -> list[str]:
    steps: list[str] = []
    if control_total_checks["status"] == "inconsistent":
        steps.append(
            "Review the source tables or mappings: control margins have different "
            "total populations, so IPF cannot satisfy all controls exactly."
        )
    if any(issue.get("kind") == "cell_residual" for issue in issues):
        steps.append(
            "Inspect the largest residual cells; they often point to incompatible "
            "margins, missing seed coverage, or labels that should be remapped."
        )
    return steps


def build_ipf_input_report(
    seed_rows: list[Record],
    control_table: ControlTable,
) -> dict[str, Any]:
    dimensions = [
        _build_dimension_input_check(seed_rows, control_table, dimension)
        for dimension in control_table.dimensions
    ]
    unsupported_cells = _find_unsupported_control_cells(seed_rows, control_table)
    return {
        "passed": all(check["status"] == "ok" for check in dimensions)
        and not unsupported_cells,
        "seed_records": len(seed_rows),
        "control_margins": len(control_table.margins),
        "dimensions": dimensions,
        "unsupported_cells": unsupported_cells,
        "suggested_next_steps": _suggest_ipf_input_next_steps(dimensions),
    }


def _build_dimension_input_check(
    seed_rows: list[Record],
    control_table: ControlTable,
    dimension: str,
) -> dict[str, Any]:
    control_categories = sorted(
        _control_categories_for_dimension(control_table, dimension)
    )
    if any(dimension not in row for row in seed_rows):
        return {
            "dimension": dimension,
            "status": "problem",
            "seed_column": "missing",
            "control_categories": control_categories,
            "seed_categories": [],
            "missing_categories": control_categories,
            "unused_seed_categories": [],
            "detail": "seed column is missing; add this attribute before IPF",
        }

    seed_categories = sorted(str(row.get(dimension, "")) for row in seed_rows)
    seed_category_set = set(seed_categories)
    control_category_set = set(control_categories)
    missing = sorted(control_category_set - seed_category_set)
    unused = sorted(seed_category_set - control_category_set)
    details: list[str] = []
    if missing:
        details.append(f"missing control categories: {', '.join(missing)}")
    if unused:
        details.append(f"unused seed categories: {', '.join(unused)}")
    return {
        "dimension": dimension,
        "status": "problem" if details else "ok",
        "seed_column": "found",
        "control_categories": control_categories,
        "seed_categories": sorted(seed_category_set),
        "missing_categories": missing,
        "unused_seed_categories": unused,
        "detail": "; ".join(details) if details else "seed and controls match",
    }


def _suggest_ipf_input_next_steps(dimension_checks: list[dict[str, Any]]) -> list[str]:
    steps: list[str] = []
    for check in dimension_checks:
        if check["status"] == "ok":
            continue
        dimension = str(check["dimension"])
        if check["seed_column"] == "missing":
            steps.append(
                f"Missing seed column for dimension '{dimension}': IPF cannot "
                "create this variable. Add it first with an enrichment/modeling "
                f"step, export a seed column named '{dimension}', or choose "
                "controls whose dimensions already exist in the seed. Run "
                "`synthpopcan ipf suggest-controls --seed seed.csv` to inspect "
                "usable calibration columns."
            )
            continue
        missing = check.get("missing_categories", [])
        if missing:
            first_missing = str(missing[0])
            steps.append(
                f"Column/category mismatch for dimension '{dimension}': controls "
                f"include '{first_missing}', but the seed does not. If this came "
                "from WDS labels, run `synthpopcan controls wds mapping-template "
                f'... --dimensions "{dimension}" --out categories.json`, fill '
                "in the target seed labels, then rerun `controls from-wds "
                "--mapping categories.json`."
            )
    return steps


def _control_categories_for_dimension(
    control_table: ControlTable, dimension: str
) -> set[str]:
    categories: set[str] = set()
    for margin in control_table.margins:
        if dimension not in margin.dimensions:
            continue
        for cell in margin.cells:
            categories.add(cell.categories[dimension])
    return categories


def _find_unsupported_control_cells(
    seed_rows: list[Record],
    control_table: ControlTable,
) -> list[dict[str, Any]]:
    unsupported: list[dict[str, Any]] = []
    for margin in control_table.margins:
        seed_keys = set()
        if all(
            all(dimension in row for dimension in margin.dimensions)
            for row in seed_rows
        ):
            seed_keys = {_category_key(row, margin.dimensions) for row in seed_rows}
        for cell in margin.cells:
            key = tuple(cell.categories[dimension] for dimension in margin.dimensions)
            if cell.count > 0 and key not in seed_keys:
                unsupported.append(
                    {
                        "margin": margin.name,
                        "dimensions": list(margin.dimensions),
                        "categories": dict(cell.categories),
                        "target": cell.count,
                    }
                )
    return unsupported


def relative_error(abs_error: float, target: float) -> float:
    if target == 0.0:
        return 0.0 if abs_error == 0.0 else float("inf")
    return abs_error / abs(target)


def format_categories(categories: dict[str, str]) -> str:
    return ", ".join(f"{key}={value}" for key, value in categories.items())


def format_number(value: float) -> str:
    rounded = round(value)
    if abs(value - rounded) < 1e-9:
        return f"{rounded:,}"
    return f"{value:.6g}"
