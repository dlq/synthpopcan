"""Validation reports for generated population artifacts."""

from __future__ import annotations

from typing import Any

from synthpopcan.controls import ControlTable
from synthpopcan.diagnostics import format_categories, format_number, relative_error
from synthpopcan.ipf import Record, weighted_totals


def build_control_validation_report(
    control_table: ControlTable,
    records: list[Record],
    weights: list[float],
    *,
    tolerance: float = 1e-6,
    artifact_kind: str = "weights",
) -> dict[str, Any]:
    margins: list[dict[str, Any]] = []
    margin_summaries: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    max_abs_error = 0.0
    max_relative_error = 0.0

    for control_margin in control_table.margins:
        totals = weighted_totals(records, weights, control_margin.dimensions)
        cells: list[dict[str, Any]] = []
        target_total = 0.0
        actual_total = 0.0
        margin_max_abs_error = 0.0
        margin_max_relative_error = 0.0
        for cell in control_margin.cells:
            key = tuple(
                cell.categories[dimension] for dimension in control_margin.dimensions
            )
            actual = totals.get(key, 0.0)
            residual = actual - cell.count
            abs_error = abs(residual)
            rel_error = relative_error(abs_error, cell.count)
            target_total += cell.count
            actual_total += actual
            max_abs_error = max(max_abs_error, abs_error)
            max_relative_error = max(max_relative_error, rel_error)
            margin_max_abs_error = max(margin_max_abs_error, abs_error)
            margin_max_relative_error = max(margin_max_relative_error, rel_error)
            cells.append(
                {
                    "categories": dict(cell.categories),
                    "target": cell.count,
                    "actual": actual,
                    "residual": residual,
                }
            )
            if abs_error > tolerance:
                category_label = format_categories(cell.categories)
                issues.append(
                    {
                        "severity": "error",
                        "kind": "validation_residual",
                        "margin": control_margin.name,
                        "categories": dict(cell.categories),
                        "message": (
                            "Largest validation error is "
                            f"{format_number(abs_error)} for {category_label}."
                        ),
                        "tip": (
                            "Check that the population artifact was generated from "
                            "these controls and has not been filtered or edited."
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
                "actual_total": actual_total,
                "max_abs_error": margin_max_abs_error,
                "max_relative_error": margin_max_relative_error,
            }
        )

    sorted_issues = sorted(
        issues,
        key=lambda issue: issue["abs_error"],
        reverse=True,
    )
    return {
        "passed": max_abs_error <= tolerance,
        "artifact_kind": artifact_kind,
        "population_records": len(records),
        "tolerance": tolerance,
        "max_abs_error": max_abs_error,
        "max_relative_error": max_relative_error,
        "issues": sorted_issues,
        "margin_summaries": margin_summaries,
        "margins": margins,
    }
