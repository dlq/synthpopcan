"""Diagnostics for fitted synthetic population workflows."""

from __future__ import annotations

from typing import Any

from synthpopcan.controls import ControlTable
from synthpopcan.ipf import IPFResult, weighted_totals


def build_ipf_fit_report(
    control_table: ControlTable, result: IPFResult
) -> dict[str, Any]:
    margins: list[dict[str, Any]] = []
    margin_summaries: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    for control_margin in control_table.margins:
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
        "issues": sorted(
            issues,
            key=lambda issue: issue["abs_error"],
            reverse=True,
        ),
        "margin_summaries": margin_summaries,
        "margins": margins,
    }


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
