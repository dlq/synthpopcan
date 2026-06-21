"""Diagnostics for fitted synthetic population workflows."""

from __future__ import annotations

from typing import Any

from synthpopcan.controls import ControlTable
from synthpopcan.ipf import IPFResult, weighted_totals


def build_ipf_fit_report(
    control_table: ControlTable, result: IPFResult
) -> dict[str, Any]:
    margins: list[dict[str, Any]] = []
    for control_margin in control_table.margins:
        totals = weighted_totals(
            result.records,
            result.weights,
            control_margin.dimensions,
        )
        margins.append(
            {
                "name": control_margin.name,
                "dimensions": list(control_margin.dimensions),
                "cells": [
                    {
                        "categories": dict(cell.categories),
                        "target": cell.count,
                        "fitted": totals.get(
                            tuple(
                                cell.categories[dimension]
                                for dimension in control_margin.dimensions
                            ),
                            0.0,
                        ),
                        "residual": totals.get(
                            tuple(
                                cell.categories[dimension]
                                for dimension in control_margin.dimensions
                            ),
                            0.0,
                        )
                        - cell.count,
                    }
                    for cell in control_margin.cells
                ],
            }
        )

    return {
        "converged": result.converged,
        "iterations": result.iterations,
        "max_abs_error": result.max_abs_error,
        "seed_records": len(result.records),
        "margins": margins,
    }
