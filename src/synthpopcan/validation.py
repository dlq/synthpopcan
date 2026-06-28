"""Validation reports for generated population artifacts."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from synthpopcan.controls import ControlTable
from synthpopcan.diagnostics import format_categories, format_number, relative_error
from synthpopcan.ipf import Record, weighted_totals

__all__ = [
    "build_control_validation_report",
    "build_distribution_comparison",
    "build_tree_output_validation_report",
    "comparison_dimensions",
]


def build_control_validation_report(
    control_table: ControlTable,
    records: Sequence[Record],
    weights: list[float],
    *,
    tolerance: float = 1e-6,
    artifact_kind: str = "weights",
) -> dict[str, Any]:
    """Compare weighted records against every cell in a control table.

    Returns a JSON-serializable report with margin summaries, cell residuals,
    and reader-facing issue messages for residuals above ``tolerance``. The
    report is appropriate for CLI output, notebooks, tests, or provenance files.
    """

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


def build_tree_output_validation_report(
    *,
    training_rows: Sequence[Record],
    generated_rows: Sequence[Record],
    target_columns: tuple[str, ...],
    conditioning_columns: tuple[str, ...],
    weight_field: str | None = None,
    tolerance: float = 0.05,
) -> dict[str, Any]:
    """Compare generated tree output with its training distribution.

    The report checks target columns, joint target distributions, and selected
    conditioning columns for large proportion shifts or unseen generated
    category combinations. Unknown generated categories are reported as errors;
    distribution shifts beyond ``tolerance`` are reported as warnings.
    """

    if not training_rows:
        raise ValueError("training rows are required")
    if not generated_rows:
        raise ValueError("generated rows are required")
    if not target_columns:
        raise ValueError("at least one target column is required")

    dimensions = comparison_dimensions(target_columns, conditioning_columns)
    training_weights = [
        read_validation_weight(row, weight_field, row_number)
        for row_number, row in enumerate(training_rows, start=2)
    ]
    generated_weights = [1.0 for _row in generated_rows]

    comparisons: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    max_abs_delta = 0.0
    for dimension_group in dimensions:
        comparison = build_distribution_comparison(
            training_rows,
            training_weights,
            generated_rows,
            generated_weights,
            dimension_group,
        )
        comparisons.append(comparison)
        for cell in comparison["cells"]:
            abs_delta = abs(cell["proportion_delta"])
            max_abs_delta = max(max_abs_delta, abs_delta)
            if cell["training_count"] == 0 and cell["generated_count"] > 0:
                issues.append(
                    {
                        "severity": "error",
                        "kind": "unknown_generated_category",
                        "dimensions": list(dimension_group),
                        "categories": dict(cell["categories"]),
                        "message": (
                            "Generated output contains a category combination "
                            "not present in the training view."
                        ),
                        "abs_proportion_delta": abs_delta,
                    }
                )
            elif abs_delta > tolerance:
                issues.append(
                    {
                        "severity": "warning",
                        "kind": "distribution_shift",
                        "dimensions": list(dimension_group),
                        "categories": dict(cell["categories"]),
                        "message": (
                            "Generated output distribution differs from the "
                            "training view beyond tolerance."
                        ),
                        "abs_proportion_delta": abs_delta,
                    }
                )

    sorted_issues = sorted(
        issues,
        key=lambda issue: (
            issue["kind"] != "unknown_generated_category",
            -issue["abs_proportion_delta"],
        ),
    )
    return {
        "passed": not sorted_issues,
        "artifact_kind": "tree-output",
        "training_records": len(training_rows),
        "generated_records": len(generated_rows),
        "target_columns": list(target_columns),
        "conditioning_columns": list(conditioning_columns),
        "weight_field": weight_field,
        "tolerance": tolerance,
        "max_abs_proportion_delta": max_abs_delta,
        "issues": sorted_issues,
        "comparisons": comparisons,
    }


def comparison_dimensions(
    target_columns: tuple[str, ...],
    conditioning_columns: tuple[str, ...],
) -> list[tuple[str, ...]]:
    """Return one-way and joint dimension groups used for tree validation.

    The returned groups are the default dimensions compared by
    :func:`build_tree_output_validation_report`.
    """

    dimensions: list[tuple[str, ...]] = [(column,) for column in target_columns]
    if len(target_columns) > 1:
        dimensions.append(target_columns)
    dimensions.extend((column,) for column in conditioning_columns)
    return dimensions


def build_distribution_comparison(
    training_rows: Sequence[Record],
    training_weights: list[float],
    generated_rows: Sequence[Record],
    generated_weights: list[float],
    dimensions: tuple[str, ...],
) -> dict[str, Any]:
    """Build one weighted distribution comparison for a dimension group.

    The result includes category-level training and generated proportions,
    absolute proportion deltas, and the maximum absolute delta for the group.
    """

    training_counts = weighted_totals(training_rows, training_weights, dimensions)
    generated_counts = weighted_totals(generated_rows, generated_weights, dimensions)
    training_total = sum(training_counts.values())
    generated_total = sum(generated_counts.values())
    cells: list[dict[str, Any]] = []
    max_abs_delta = 0.0
    for key in sorted(set(training_counts) | set(generated_counts)):
        training_count = training_counts.get(key, 0.0)
        generated_count = generated_counts.get(key, 0.0)
        training_proportion = safe_proportion(training_count, training_total)
        generated_proportion = safe_proportion(generated_count, generated_total)
        delta = generated_proportion - training_proportion
        max_abs_delta = max(max_abs_delta, abs(delta))
        cells.append(
            {
                "categories": dict(zip(dimensions, key, strict=True)),
                "training_count": training_count,
                "generated_count": generated_count,
                "training_proportion": training_proportion,
                "generated_proportion": generated_proportion,
                "proportion_delta": delta,
            }
        )
    return {
        "name": " x ".join(dimensions),
        "dimensions": list(dimensions),
        "cells": cells,
        "training_total": training_total,
        "generated_total": generated_total,
        "max_abs_proportion_delta": max_abs_delta,
    }


def read_validation_weight(
    row: Record,
    weight_field: str | None,
    row_number: int,
) -> float:
    if weight_field is None:
        return 1.0
    try:
        return float(row[weight_field])
    except KeyError as exc:
        raise ValueError(f"training rows require a {weight_field!r} column") from exc
    except ValueError as exc:
        raise ValueError(f"training row {row_number} has invalid weight") from exc


def safe_proportion(count: float, total: float) -> float:
    if total == 0:
        return 0.0
    return count / total
