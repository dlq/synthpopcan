"""Build deterministic CSD/CT/ADA/DA linked-calibration evidence."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from synthpopcan.controls import ControlCell, ControlMargin, ControlTable
from synthpopcan.ipf import integerize_weights
from synthpopcan.methodological_validation import (
    build_linked_calibration_validation_profile,
)
from synthpopcan.small_area_synthesis import fit_linked_by_geography

_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_FIXTURE = (
    _ROOT
    / "tests"
    / "fixtures"
    / "correctness"
    / "small_area_0_9_multiscale"
    / "cases.json"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, default=_DEFAULT_FIXTURE)
    parser.add_argument("--out", type=Path, help="Write JSON instead of printing it.")
    return parser.parse_args()


def build_evidence(fixture_path: Path = _DEFAULT_FIXTURE) -> dict[str, Any]:
    """Run the real linked fitter and independently recompute bounded evidence."""

    fixture = json.loads(fixture_path.read_text())
    households = fixture["candidate_households"]
    persons = fixture["candidate_persons"]
    cases = fixture["geographies"]
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for case in cases:
        grouped[case["identifier_column"]].append(case)

    case_outputs: dict[str, dict[str, Any]] = {}
    fitted_weights: dict[str, list[float]] = {}
    integer_weights: dict[str, list[int]] = {}
    for geography_column, grouped_cases in sorted(grouped.items()):
        household_controls = _control_table(
            grouped_cases,
            fixture["household_margins"],
            geography_column=geography_column,
            target_key="household_targets",
        )
        person_controls = _control_table(
            grouped_cases,
            fixture["person_margins"],
            geography_column=geography_column,
            target_key="person_targets",
        )
        fit = fit_linked_by_geography(
            households,
            persons,
            household_controls,
            person_controls,
            geography_dimension=geography_column,
            max_iterations=1_000,
            tolerance=1e-10,
            n_workers=1,
        )
        realized = {
            geography: integerize_weights(weights)
            for geography, weights in fit.weights_by_geography.items()
        }
        profile = build_linked_calibration_validation_profile(
            households,
            persons,
            household_controls,
            person_controls,
            fit.weights_by_geography,
            realized,
            geography_dimension=geography_column,
            geography_column=geography_column,
            fractional_tolerance=fixture["acceptance_bounds"][
                "fractional_max_abs_error"
            ],
        )
        for case in grouped_cases:
            identifier = case["identity"]["identifier"]
            case_id = case["case_id"]
            weights = fit.weights_by_geography[identifier]
            integers = realized[identifier]
            fitted_weights[case_id] = weights
            integer_weights[case_id] = integers
            expected = case["expected_candidate_weights"]
            report = fit.reports[identifier]
            case_outputs[case_id] = {
                "identity": case["identity"],
                "identifier_column": geography_column,
                "fitter": {
                    "function": "fit_linked_by_geography",
                    "converged": bool(report["converged"]),
                    "iterations": int(report["iterations"]),
                    "reported_max_abs_error": float(report["max_abs_error"]),
                },
                "fractional_weights": weights,
                "integer_weights": integers,
                "expected_weight_max_abs_error": max(
                    abs(weight - target)
                    for weight, target in zip(weights, expected, strict=True)
                ),
                "independent_validation": profile["geographies"][identifier],
            }

    reconciliation = _parent_child_reconciliation(
        fixture,
        case_outputs,
        fitted_weights,
        integer_weights,
    )
    bounds = fixture["acceptance_bounds"]
    checks = {
        "all_fitters_converged": all(
            output["fitter"]["converged"] for output in case_outputs.values()
        ),
        "all_independent_profiles_pass": all(
            output["independent_validation"]["passed"]
            for output in case_outputs.values()
        ),
        "fractional_error_within_bound": all(
            output["independent_validation"]["fractional_max_abs_error"]
            <= bounds["fractional_max_abs_error"]
            for output in case_outputs.values()
        ),
        "realized_error_within_bound": all(
            output["independent_validation"]["realized_max_abs_error"]
            <= bounds["realized_cell_max_abs_error"]
            for output in case_outputs.values()
        ),
        "parent_child_targets_reconcile": (
            reconciliation["target_max_abs_error"]
            <= bounds["parent_child_target_max_abs_error"]
        ),
        "parent_child_fractional_counts_reconcile": (
            reconciliation["fractional_max_abs_error"]
            <= bounds["parent_child_fractional_max_abs_error"]
        ),
        "parent_child_realized_counts_reconcile": (
            reconciliation["realized_max_abs_error"]
            <= bounds["parent_child_realized_max_abs_error"]
        ),
    }
    return _round_floats(
        {
            "schema_version": "synthpopcan-multiscale-calibration-evidence-v1",
            "fixture_schema_version": fixture["schema_version"],
            "generated_by": "scripts/build_multiscale_validation_evidence.py",
            "passed": all(checks.values()),
            "checks": checks,
            "acceptance_bounds": bounds,
            "cases": {
                case_id: case_outputs[case_id] for case_id in sorted(case_outputs)
            },
            "parent_child_reconciliation": reconciliation,
            "limitations": fixture["limitations"],
        }
    )


def _control_table(
    cases: Sequence[Mapping[str, Any]],
    margin_specs: Sequence[Mapping[str, Any]],
    *,
    geography_column: str,
    target_key: str,
) -> ControlTable:
    margins: list[ControlMargin] = []
    dimensions = [geography_column]
    for margin_spec in margin_specs:
        dimension = str(margin_spec["dimension"])
        dimensions.append(dimension)
        cells: list[ControlCell] = []
        for case in cases:
            identifier = str(case["identity"]["identifier"])
            categories = margin_spec["categories"]
            targets = case[target_key][margin_spec["name"]]
            if len(categories) != len(targets):
                raise ValueError(
                    "fixture categories and targets must have equal length"
                )
            cells.extend(
                ControlCell(
                    {
                        geography_column: identifier,
                        dimension: str(category),
                    },
                    float(target),
                )
                for category, target in zip(categories, targets, strict=True)
            )
        margins.append(
            ControlMargin(
                name=str(margin_spec["name"]),
                dimensions=(geography_column, dimension),
                cells=tuple(cells),
            )
        )
    return ControlTable(
        margins=tuple(margins), dimensions=tuple(dict.fromkeys(dimensions))
    )


def _cell_key(cell: Mapping[str, Any]) -> tuple[str, str, tuple[tuple[str, str], ...]]:
    return (
        str(cell["unit"]),
        str(cell["margin"]),
        tuple(
            sorted((str(key), str(value)) for key, value in cell["categories"].items())
        ),
    )


def _parent_child_reconciliation(
    fixture: Mapping[str, Any],
    outputs: Mapping[str, Mapping[str, Any]],
    fractional_weights: Mapping[str, Sequence[float]],
    integer_weights: Mapping[str, Sequence[int]],
) -> dict[str, Any]:
    spec = fixture["parent_child_reconciliation"]
    parent_id = spec["parent_case_id"]
    child_ids = spec["child_case_ids"]
    parent_cells = {
        _cell_key(cell): cell
        for cell in outputs[parent_id]["independent_validation"]["cells"]
    }
    child_cells = [
        {
            _cell_key(cell): cell
            for cell in outputs[child_id]["independent_validation"]["cells"]
        }
        for child_id in child_ids
    ]
    if any(set(cells) != set(parent_cells) for cells in child_cells):
        raise ValueError("parent and child evidence must contain identical cell keys")
    rows: list[dict[str, Any]] = []
    for key in sorted(parent_cells):
        parent = parent_cells[key]
        target_children = sum(cells[key]["target_count"] for cells in child_cells)
        fractional_children = sum(
            cells[key]["fractional_count"] for cells in child_cells
        )
        realized_children = sum(cells[key]["realized_count"] for cells in child_cells)
        rows.append(
            {
                "unit": key[0],
                "margin": key[1],
                "categories": dict(key[2]),
                "parent_target": parent["target_count"],
                "children_target_sum": target_children,
                "target_abs_error": abs(parent["target_count"] - target_children),
                "parent_fractional_count": parent["fractional_count"],
                "children_fractional_sum": fractional_children,
                "fractional_abs_error": abs(
                    parent["fractional_count"] - fractional_children
                ),
                "parent_realized_count": parent["realized_count"],
                "children_realized_sum": realized_children,
                "realized_abs_error": abs(parent["realized_count"] - realized_children),
            }
        )
    candidate_fractional_errors = [
        abs(
            fractional_weights[parent_id][index]
            - sum(fractional_weights[child_id][index] for child_id in child_ids)
        )
        for index in range(len(fractional_weights[parent_id]))
    ]
    candidate_integer_errors = [
        abs(
            integer_weights[parent_id][index]
            - sum(integer_weights[child_id][index] for child_id in child_ids)
        )
        for index in range(len(integer_weights[parent_id]))
    ]
    return {
        **spec,
        "target_max_abs_error": max(row["target_abs_error"] for row in rows),
        "fractional_max_abs_error": max(row["fractional_abs_error"] for row in rows),
        "realized_max_abs_error": max(row["realized_abs_error"] for row in rows),
        "candidate_weight_fractional_max_abs_error": max(candidate_fractional_errors),
        "candidate_weight_integer_max_abs_error": max(candidate_integer_errors),
        "cells": rows,
    }


def _round_floats(value: Any) -> Any:
    if isinstance(value, float):
        return round(value, 12)
    if isinstance(value, dict):
        return {key: _round_floats(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_round_floats(item) for item in value]
    return value


def render_evidence(fixture_path: Path = _DEFAULT_FIXTURE) -> str:
    return json.dumps(build_evidence(fixture_path), indent=2, sort_keys=True) + "\n"


def main() -> None:
    args = parse_args()
    rendered = render_evidence(args.fixture)
    if args.out is None:
        print(rendered, end="")
        return
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(rendered)


if __name__ == "__main__":
    main()
