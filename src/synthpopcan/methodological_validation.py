"""Independent diagnostics and bounded external-comparison evidence.

The functions in this module recompute diagnostics from candidate rows and
emitted fractional/integer weights.  They intentionally do not consume the
production fit report, so that a report builder cannot validate itself.
"""

from __future__ import annotations

__all__ = [
    "EXTERNAL_COMPARISON_SCHEMA_VERSION",
    "VALIDATION_PROFILE_SCHEMA_VERSION",
    "FieldValidationSpec",
    "ValidationCellSpec",
    "build_calibration_validation_profile",
    "build_linked_calibration_validation_profile",
    "read_external_comparison_descriptor",
    "resolve_external_comparison_archive",
    "validate_external_comparison_fixture",
]

import csv
import hashlib
import json
import math
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from synthpopcan.controls import ControlTable
from synthpopcan.geography import GeographyIdentity

VALIDATION_PROFILE_SCHEMA_VERSION = "synthpopcan-validation-profile-v1"
EXTERNAL_COMPARISON_SCHEMA_VERSION = "synthpopcan-external-comparison-v1"

_FIELD_STATUSES = frozenset(
    {"controlled", "approximate", "validation-only", "derived", "uncontrolled"}
)
_HEX_DIGITS = frozenset("0123456789abcdef")


@dataclass(frozen=True)
class FieldValidationSpec:
    """Declare the intended validation role of one generated field.

    ``controlled`` is reserved for a field fitted to a reviewed local margin.
    ``approximate`` names a fitted but coarsened or derived margin.  The other
    statuses describe fields that were not fitted directly.  This declaration
    does not itself prove that a fit ran, converged, or met its residual bound.
    """

    field: str
    unit: str
    status: str
    universe: str
    margin: str | None = None
    limitation: str | None = None

    def __post_init__(self) -> None:
        _require_text(self.field, "field")
        _require_text(self.unit, "field unit")
        _require_text(self.universe, "field universe")
        if self.status not in _FIELD_STATUSES:
            raise ValueError(f"unsupported field validation status: {self.status!r}")
        if self.status in {"controlled", "approximate"} and not self.margin:
            raise ValueError(f"{self.status} fields require a control margin")
        if self.margin is not None:
            _require_text(self.margin, "control margin")
        if self.limitation is not None:
            _require_text(self.limitation, "field limitation")


@dataclass(frozen=True)
class ValidationCellSpec:
    """One explicitly sourced category cell used for tail or zero checks."""

    name: str
    unit: str
    dimensions: tuple[str, ...]
    categories: Mapping[str, str]
    reference_count: float
    reference_source: str

    def __post_init__(self) -> None:
        _require_text(self.name, "cell name")
        _require_text(self.unit, "cell unit")
        _require_text(self.reference_source, "cell reference source")
        if not self.dimensions or len(set(self.dimensions)) != len(self.dimensions):
            raise ValueError("cell dimensions must be non-empty and distinct")
        if set(self.dimensions) != set(self.categories):
            raise ValueError("cell categories must match its dimensions exactly")
        for dimension in self.dimensions:
            _require_text(dimension, "cell dimension")
            _require_text(self.categories[dimension], "cell category")
        if not math.isfinite(self.reference_count) or self.reference_count < 0:
            raise ValueError("cell reference_count must be finite and non-negative")


@dataclass(frozen=True)
class _TargetSpec:
    unit: str
    margin: str
    dimensions: tuple[str, ...]
    categories: tuple[str, ...]


@dataclass(frozen=True)
class _TargetCell:
    spec: _TargetSpec
    count: float


def build_calibration_validation_profile(
    records: Sequence[Mapping[str, str]],
    fractional_weights: Sequence[float],
    integer_weights: Sequence[int],
    *,
    field_specs: Sequence[FieldValidationSpec],
    category_cells: Sequence[ValidationCellSpec] = (),
    structural_zero_cells: Sequence[ValidationCellSpec] = (),
    geography: GeographyIdentity | None = None,
    population_unit: str = "household",
    rare_threshold: float = 5.0,
    tolerance: float = 1e-9,
) -> dict[str, Any]:
    """Recompute a versioned validation profile from calibration artifacts.

    The result keeps fractional calibration and integer realization separate.
    Rare cells are selected from ``category_cells`` by their explicitly supplied
    reference counts.  Structural-zero cells must have reference count zero.
    """

    _require_text(population_unit, "population unit")
    if not records:
        raise ValueError("at least one candidate record is required")
    if not math.isfinite(rare_threshold) or rare_threshold <= 0:
        raise ValueError("rare_threshold must be finite and positive")
    if not math.isfinite(tolerance) or tolerance < 0:
        raise ValueError("tolerance must be finite and non-negative")
    fractional = _validated_fractional_weights(fractional_weights, len(records))
    integer = _validated_integer_weights(integer_weights, len(records))
    if sum(fractional) <= 0:
        raise ValueError("fractional weights must have a positive total")
    fields = _field_report(records, field_specs)
    rare = _rare_category_report(
        records,
        fractional,
        integer,
        category_cells,
        rare_threshold=rare_threshold,
        tolerance=tolerance,
    )
    structural_zeros = _structural_zero_report(
        records,
        fractional,
        integer,
        structural_zero_cells,
        tolerance=tolerance,
    )
    issues = [*fields["issues"], *rare["issues"], *structural_zeros["issues"]]
    issues.sort(
        key=lambda issue: (
            issue["severity"] != "error",
            str(issue["kind"]),
            str(issue.get("name", issue.get("field", ""))),
        )
    )
    return {
        "schema_version": VALIDATION_PROFILE_SCHEMA_VERSION,
        "passed": not any(issue["severity"] == "error" for issue in issues),
        "geography": geography.as_dict() if geography is not None else None,
        "population_unit": population_unit,
        "candidate_records": len(records),
        "metric_definitions": _metric_definitions(population_unit),
        "weight_concentration": _weight_concentration(fractional),
        "candidate_reuse": _candidate_reuse(integer),
        "fields": {key: value for key, value in fields.items() if key != "issues"},
        "rare_categories": {
            key: value for key, value in rare.items() if key != "issues"
        },
        "structural_zeros": {
            key: value for key, value in structural_zeros.items() if key != "issues"
        },
        "issues": issues,
    }


def build_linked_calibration_validation_profile(
    households: Sequence[Mapping[str, str]],
    persons: Sequence[Mapping[str, str]],
    household_controls: ControlTable,
    person_controls: ControlTable | None,
    weights_by_geography: Mapping[str, Sequence[float]],
    integer_weights_by_geography: Mapping[str, Sequence[int]],
    *,
    geography_dimension: str,
    geography_column: str,
    household_id_column: str = "synthetic_household_id",
    rare_threshold: float = 5.0,
    fractional_tolerance: float = 1e-6,
    zero_tolerance: float = 1e-9,
) -> dict[str, Any]:
    """Independently validate household-weighted linked calibration artifacts.

    Target contributions are cached once for each unique unit/dimension/category
    combination, then all geography counts are recomputed with NumPy matrix
    multiplication.  Person controls count linked people per candidate household;
    they never apply person labels directly to household rows.

    Field classifications are deliberately ``targeted`` or ``uncontrolled``.
    A targeted field does not authorize a local-representativeness claim: source
    quality, universe alignment, convergence history, and disclosure treatment
    remain outside this artifact.
    """

    _require_text(geography_dimension, "geography dimension")
    _require_text(geography_column, "geography column")
    _require_text(household_id_column, "household ID column")
    if not households:
        raise ValueError("at least one candidate household row is required")
    if not math.isfinite(rare_threshold) or rare_threshold <= 0:
        raise ValueError("rare_threshold must be finite and positive")
    if not math.isfinite(fractional_tolerance) or fractional_tolerance < 0:
        raise ValueError("fractional_tolerance must be finite and non-negative")
    if not math.isfinite(zero_tolerance) or zero_tolerance < 0:
        raise ValueError("zero_tolerance must be finite and non-negative")

    household_targets = _targets_by_geography(
        household_controls,
        geography_dimension=geography_dimension,
        unit="household",
    )
    person_targets = (
        _targets_by_geography(
            person_controls,
            geography_dimension=geography_dimension,
            unit="person",
        )
        if person_controls is not None
        else {}
    )
    geographies = set(household_targets)
    if person_controls is not None and set(person_targets) != geographies:
        raise ValueError(
            "household and person controls must name the same target geographies"
        )
    if set(weights_by_geography) != geographies:
        raise ValueError("fractional weights must match control geographies exactly")
    if set(integer_weights_by_geography) != geographies:
        raise ValueError("integer weights must match control geographies exactly")

    geography_order = sorted(geographies)
    fractional_matrix = np.asarray(
        [
            _validated_fractional_weights(
                weights_by_geography[geography], len(households)
            )
            for geography in geography_order
        ],
        dtype=np.float64,
    )
    integer_rows = [
        _validated_integer_weights(
            integer_weights_by_geography[geography], len(households)
        )
        for geography in geography_order
    ]
    integer_matrix = np.asarray(integer_rows, dtype=np.int64)
    if np.any(np.sum(fractional_matrix, axis=1) <= 0):
        raise ValueError("every geography's fractional weights require positive mass")

    all_targets = {
        target.spec
        for targets in (*household_targets.values(), *person_targets.values())
        for target in targets
    }
    contribution_vectors, linkage = _build_contribution_vectors(
        households,
        persons,
        all_targets,
        household_id_column=household_id_column,
    )
    contribution_keys = sorted(
        contribution_vectors,
        key=lambda key: (key[0], key[1], key[2]),
    )
    contribution_matrix = np.vstack(
        [contribution_vectors[key] for key in contribution_keys]
    )
    contribution_index = {key: index for index, key in enumerate(contribution_keys)}
    fractional_counts = contribution_matrix @ fractional_matrix.T
    integer_counts = contribution_matrix @ integer_matrix.T

    geography_reports: dict[str, Any] = {}
    all_issues: list[dict[str, Any]] = []
    for geography_index, geography in enumerate(geography_order):
        targets = [
            *household_targets[geography],
            *person_targets.get(geography, ()),
        ]
        cells: list[dict[str, Any]] = []
        rare_cells: list[dict[str, Any]] = []
        zero_cells: list[dict[str, Any]] = []
        issues: list[dict[str, Any]] = []
        fractional_max_abs_error = 0.0
        realized_max_abs_error = 0.0
        for target_index, target in enumerate(targets, start=1):
            contribution_key = _contribution_key(target.spec)
            vector_index = contribution_index[contribution_key]
            vector = contribution_matrix[vector_index]
            fractional_count = float(fractional_counts[vector_index, geography_index])
            realized_float = float(integer_counts[vector_index, geography_index])
            realized_count = int(round(realized_float))
            fractional_abs_error = abs(fractional_count - target.count)
            realized_abs_error = abs(realized_count - target.count)
            fractional_max_abs_error = max(
                fractional_max_abs_error, fractional_abs_error
            )
            realized_max_abs_error = max(realized_max_abs_error, realized_abs_error)
            row = {
                "name": f"{target.spec.margin}:{target_index}",
                "unit": target.spec.unit,
                "margin": target.spec.margin,
                "dimensions": list(target.spec.dimensions),
                "categories": dict(
                    zip(
                        target.spec.dimensions,
                        target.spec.categories,
                        strict=True,
                    )
                ),
                "target_count": target.count,
                "candidate_rows": int(round(float(np.sum(vector)))),
                "supporting_households": int(np.count_nonzero(vector)),
                "fractional_count": fractional_count,
                "realized_count": realized_count,
                "fractional_abs_error": fractional_abs_error,
                "realized_abs_error": realized_abs_error,
            }
            cells.append(row)
            if target.count > 0 and not np.any(vector):
                issues.append(
                    _profile_issue(
                        "error",
                        "unsupported_positive_target",
                        geography,
                        row,
                    )
                )
            if fractional_abs_error > fractional_tolerance:
                issues.append(
                    _profile_issue(
                        "error",
                        "fractional_residual_exceeds_tolerance",
                        geography,
                        row,
                    )
                )
            if target.count == 0:
                zero_row = {
                    **row,
                    "constraint_kind": "declared-zero-target",
                    "structural_impossibility_claimed": False,
                    "fractional_violation": fractional_count > zero_tolerance,
                    "realized_violation": realized_count > 0,
                }
                zero_cells.append(zero_row)
                if zero_row["fractional_violation"] or zero_row["realized_violation"]:
                    issues.append(
                        _profile_issue(
                            "error",
                            "zero_target_constraint_violation",
                            geography,
                            zero_row,
                        )
                    )
            elif target.count <= rare_threshold:
                rare_row = {
                    **row,
                    "retained_fractionally": fractional_count > zero_tolerance,
                    "retained_in_realization": realized_count > 0,
                }
                rare_cells.append(rare_row)
                if realized_count == 0:
                    issues.append(
                        _profile_issue(
                            "warning",
                            "rare_category_lost_in_realization",
                            geography,
                            rare_row,
                        )
                    )
        issues.sort(key=_issue_sort_key)
        all_issues.extend(issues)
        geography_reports[geography] = {
            "passed": not any(issue["severity"] == "error" for issue in issues),
            "fit_evidence_status": (
                "verified-fractional-residual"
                if fractional_max_abs_error <= fractional_tolerance
                else "failed-fractional-residual"
            ),
            "fractional_tolerance": fractional_tolerance,
            "fractional_max_abs_error": fractional_max_abs_error,
            "realized_max_abs_error": realized_max_abs_error,
            "targets_assessed": len(targets),
            "weight_concentration": _weight_concentration(
                fractional_matrix[geography_index].tolist()
            ),
            "candidate_reuse": _candidate_reuse(integer_rows[geography_index]),
            "rare_threshold": rare_threshold,
            "rare_categories": rare_cells,
            "zero_target_constraints": zero_cells,
            "cells": cells,
            "issues": issues,
        }

    all_issues.sort(key=_issue_sort_key)
    return {
        "schema_version": VALIDATION_PROFILE_SCHEMA_VERSION,
        "profile_kind": "linked-geography-calibration",
        "passed": not any(issue["severity"] == "error" for issue in all_issues),
        "geography_dimension": geography_dimension,
        "geography_column": geography_column,
        "candidate_households": len(households),
        "candidate_persons": len(persons),
        "linkage": linkage,
        "claim_status": "not-assessed",
        "claim_note": (
            "Target and residual evidence does not by itself establish source, "
            "universe, or local-representativeness validity."
        ),
        "field_status": _linked_field_status(
            households,
            persons,
            household_controls,
            person_controls,
            geography_dimension=geography_dimension,
            geography_column=geography_column,
            household_id_column=household_id_column,
        ),
        "metric_definitions": _linked_metric_definitions(),
        "performance_contract": {
            "candidate_scan_scope": "once per unit and unique dimension tuple",
            "unique_dimension_sets": len(
                {(spec.unit, spec.dimensions) for spec in all_targets}
            ),
            "unique_contribution_vectors": len(contribution_vectors),
            "geographies_assessed": len(geography_order),
            "count_recomputation": (
                "vectorized matrix multiplication over cached household "
                "contribution vectors"
            ),
        },
        "geographies": geography_reports,
        "issues": all_issues,
    }


def _targets_by_geography(
    controls: ControlTable,
    *,
    geography_dimension: str,
    unit: str,
) -> dict[str, tuple[_TargetCell, ...]]:
    grouped: dict[str, list[_TargetCell]] = {}
    seen: set[tuple[str, _TargetSpec]] = set()
    for margin in controls.margins:
        if geography_dimension not in margin.dimensions:
            raise ValueError(
                f"control margin {margin.name!r} does not include geography "
                f"dimension {geography_dimension!r}"
            )
        dimensions = tuple(
            dimension
            for dimension in margin.dimensions
            if dimension != geography_dimension
        )
        if not dimensions:
            raise ValueError(
                f"control margin {margin.name!r} requires a non-geography dimension"
            )
        for cell in margin.cells:
            geography = cell.categories.get(geography_dimension, "")
            if not geography:
                raise ValueError(
                    f"control margin {margin.name!r} has a cell without "
                    f"{geography_dimension!r}"
                )
            try:
                categories = tuple(
                    cell.categories[dimension] for dimension in dimensions
                )
            except KeyError as exc:
                raise ValueError(
                    f"control margin {margin.name!r} cell is missing {exc.args[0]!r}"
                ) from exc
            spec = _TargetSpec(unit, margin.name, dimensions, categories)
            identity = (geography, spec)
            if identity in seen:
                raise ValueError(
                    f"duplicate {unit} control cell for geography {geography!r}"
                )
            seen.add(identity)
            grouped.setdefault(geography, []).append(
                _TargetCell(spec=spec, count=float(cell.count))
            )
    if not grouped:
        raise ValueError(f"{unit} controls contain no target geographies")
    return {geography: tuple(targets) for geography, targets in grouped.items()}


def _contribution_key(
    spec: _TargetSpec,
) -> tuple[str, tuple[str, ...], tuple[str, ...]]:
    return spec.unit, spec.dimensions, spec.categories


def _build_contribution_vectors(
    households: Sequence[Mapping[str, str]],
    persons: Sequence[Mapping[str, str]],
    targets: set[_TargetSpec],
    *,
    household_id_column: str,
) -> tuple[
    dict[tuple[str, tuple[str, ...], tuple[str, ...]], np.ndarray],
    dict[str, int],
]:
    if not targets:
        raise ValueError("at least one household or person target cell is required")
    household_indexes: dict[str, int] = {}
    for index, household in enumerate(households):
        identifier = household.get(household_id_column, "")
        if not identifier:
            raise ValueError(
                f"candidate household row {index + 1} requires {household_id_column!r}"
            )
        if identifier in household_indexes:
            raise ValueError(f"duplicate candidate household ID {identifier!r}")
        household_indexes[identifier] = index

    linked_person_rows = 0
    unlinked_person_rows = 0
    person_household_indexes: list[int | None] = []
    for person in persons:
        household_index = household_indexes.get(person.get(household_id_column, ""))
        person_household_indexes.append(household_index)
        if household_index is None:
            unlinked_person_rows += 1
        else:
            linked_person_rows += 1

    categories_by_group: dict[tuple[str, tuple[str, ...]], set[tuple[str, ...]]] = {}
    for target in targets:
        categories_by_group.setdefault((target.unit, target.dimensions), set()).add(
            target.categories
        )

    vectors: dict[tuple[str, tuple[str, ...], tuple[str, ...]], np.ndarray] = {}
    for (unit, dimensions), categories_set in categories_by_group.items():
        group_vectors = {
            categories: np.zeros(len(households), dtype=np.float64)
            for categories in categories_set
        }
        if unit == "household":
            for household_index, record in enumerate(households):
                categories = tuple(
                    record.get(dimension, "") for dimension in dimensions
                )
                vector = group_vectors.get(categories)
                if vector is not None:
                    vector[household_index] += 1.0
        elif unit == "person":
            for record, household_index in zip(
                persons, person_household_indexes, strict=True
            ):
                if household_index is None:
                    continue
                categories = tuple(
                    record.get(dimension, "") for dimension in dimensions
                )
                vector = group_vectors.get(categories)
                if vector is not None:
                    vector[household_index] += 1.0
        else:
            raise ValueError(f"unsupported calibration target unit: {unit!r}")
        for categories, vector in group_vectors.items():
            vectors[(unit, dimensions, categories)] = vector
    return vectors, {
        "candidate_households": len(households),
        "candidate_person_rows": len(persons),
        "linked_person_rows": linked_person_rows,
        "unlinked_person_rows": unlinked_person_rows,
    }


def _linked_field_status(
    households: Sequence[Mapping[str, str]],
    persons: Sequence[Mapping[str, str]],
    household_controls: ControlTable,
    person_controls: ControlTable | None,
    *,
    geography_dimension: str,
    geography_column: str,
    household_id_column: str,
) -> dict[str, Any]:
    def targeted_margins(controls: ControlTable | None) -> dict[str, list[str]]:
        margins: dict[str, list[str]] = {}
        if controls is None:
            return margins
        for margin in controls.margins:
            for dimension in margin.dimensions:
                if dimension == geography_dimension:
                    continue
                margins.setdefault(dimension, []).append(margin.name)
        return {field: sorted(set(names)) for field, names in margins.items()}

    def rows_for(
        records: Sequence[Mapping[str, str]],
        targets: Mapping[str, Sequence[str]],
    ) -> list[dict[str, Any]]:
        fields = sorted(
            {field for record in records for field in record} | set(targets)
        )
        return [
            {
                "field": field,
                "status": "targeted" if field in targets else "uncontrolled",
                "target_margins": list(targets.get(field, ())),
                "present_in_all_candidates": bool(records)
                and all(field in record for record in records),
                "role": (
                    "identifier"
                    if field == household_id_column
                    else "output-geography"
                    if field == geography_column
                    else "attribute"
                ),
            }
            for field in fields
        ]

    household_targets = targeted_margins(household_controls)
    person_targets = targeted_margins(person_controls)
    return {
        "status_definition": {
            "targeted": (
                "named by a supplied calibration margin; fit quality is reported "
                "separately for each geography"
            ),
            "uncontrolled": "not named by a supplied calibration margin",
        },
        "claim_status": "not-assessed",
        "household": rows_for(households, household_targets),
        "person": rows_for(persons, person_targets),
    }


def _linked_metric_definitions() -> dict[str, Any]:
    return {
        "fractional_residual": {
            "unit": "target-cell count",
            "definition": "absolute target minus independently recomputed count",
        },
        "realized_residual": {
            "unit": "target-cell count",
            "definition": (
                "absolute target minus count after deterministic integerization"
            ),
        },
        "linked_person_contribution": {
            "unit": "person rows per candidate household",
            "definition": (
                "person-category contributions are summed within household, then "
                "multiplied by that household's fractional or integer weight"
            ),
        },
        "zero_target_constraint": {
            "unit": "explicit supplied target cell",
            "definition": (
                "a zero target is checked as a declared constraint; it is not "
                "called a structural impossibility without separate provenance"
            ),
        },
        "field_status": {
            "unit": "candidate field",
            "definition": (
                "targeted versus uncontrolled is descriptive and does not "
                "authorize a local-representativeness claim"
            ),
        },
    }


def _profile_issue(
    severity: str,
    kind: str,
    geography: str,
    cell: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "severity": severity,
        "kind": kind,
        "geography": geography,
        "name": cell["name"],
        "unit": cell["unit"],
        "message": f"{kind.replace('_', ' ')} for {cell['name']!r}",
    }


def _issue_sort_key(issue: Mapping[str, Any]) -> tuple[bool, str, str, str]:
    return (
        issue.get("severity") != "error",
        str(issue.get("geography", "")),
        str(issue.get("kind", "")),
        str(issue.get("name", "")),
    )


def _validated_fractional_weights(
    weights: Sequence[float], expected: int
) -> list[float]:
    if len(weights) != expected:
        raise ValueError("fractional weights must match candidate records")
    values = [float(weight) for weight in weights]
    if any(not math.isfinite(weight) or weight < 0 for weight in values):
        raise ValueError("fractional weights must be finite and non-negative")
    return values


def _validated_integer_weights(weights: Sequence[int], expected: int) -> list[int]:
    if len(weights) != expected:
        raise ValueError("integer weights must match candidate records")
    values: list[int] = []
    for weight in weights:
        if isinstance(weight, bool) or not isinstance(weight, int) or weight < 0:
            raise ValueError("integer weights must be non-negative integers")
        values.append(weight)
    return values


def _weight_concentration(weights: Sequence[float]) -> dict[str, Any]:
    total = sum(weights)
    sum_squares = sum(weight * weight for weight in weights)
    positive = [weight for weight in weights if weight > 0]
    effective_sample_size = total * total / sum_squares
    top_count = max(1, math.ceil(len(weights) * 0.1))
    top_share = sum(sorted(weights, reverse=True)[:top_count]) / total
    return {
        "candidate_count": len(weights),
        "positive_weight_candidates": len(positive),
        "zero_weight_candidates": len(weights) - len(positive),
        "total_weight": total,
        "minimum_positive_weight": min(positive),
        "maximum_weight": max(weights),
        "mean_weight": total / len(weights),
        "kish_effective_sample_size": effective_sample_size,
        "effective_sample_share": effective_sample_size / len(weights),
        "herfindahl_concentration": sum_squares / (total * total),
        "largest_candidate_weight_share": max(weights) / total,
        "top_10_percent_candidate_count": top_count,
        "top_10_percent_weight_share": top_share,
    }


def _candidate_reuse(weights: Sequence[int]) -> dict[str, Any]:
    total = sum(weights)
    selected = [weight for weight in weights if weight > 0]
    repeated = [weight for weight in weights if weight > 1]
    histogram = Counter(weights)
    return {
        "candidate_count": len(weights),
        "realized_records": total,
        "selected_candidates": len(selected),
        "unselected_candidates": len(weights) - len(selected),
        "reused_candidates": len(repeated),
        "additional_copies_from_reuse": sum(weight - 1 for weight in repeated),
        "maximum_copies_of_one_candidate": max(weights),
        "candidate_selection_share": len(selected) / len(weights),
        "unique_copy_share": (
            sum(weight == 1 for weight in weights) / total if total else 0.0
        ),
        "realized_share_from_reused_candidates": (
            sum(repeated) / total if total else 0.0
        ),
        "copy_count_histogram": {
            str(copy_count): count for copy_count, count in sorted(histogram.items())
        },
    }


def _field_report(
    records: Sequence[Mapping[str, str]], specs: Sequence[FieldValidationSpec]
) -> dict[str, Any]:
    names = [spec.field for spec in specs]
    if len(set(names)) != len(names):
        raise ValueError("field validation specifications must be unique")
    counts = Counter(spec.status for spec in specs)
    rows: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    for spec in sorted(specs, key=lambda item: item.field):
        present = all(spec.field in record for record in records)
        rows.append(
            {
                "field": spec.field,
                "unit": spec.unit,
                "status": spec.status,
                "universe": spec.universe,
                "margin": spec.margin,
                "limitation": spec.limitation,
                "present_in_candidates": present,
                "fit_evidence_status": "not_assessed",
                "claim_note": (
                    "The declared field tier does not authorize a local-"
                    "representativeness claim without independently verified "
                    "source, universe, fit, and residual evidence."
                ),
            }
        )
        if not present and spec.status in {"controlled", "approximate"}:
            issues.append(
                {
                    "severity": "error",
                    "kind": "missing_fitted_field",
                    "field": spec.field,
                    "message": (
                        f"{spec.status} field {spec.field!r} is missing from at "
                        "least one candidate record."
                    ),
                }
            )
    return {
        "status_counts": {status: counts[status] for status in sorted(_FIELD_STATUSES)},
        "controlled_fields": sorted(
            spec.field for spec in specs if spec.status == "controlled"
        ),
        "uncontrolled_fields": sorted(
            spec.field for spec in specs if spec.status == "uncontrolled"
        ),
        "items": rows,
        "issues": issues,
    }


def _rare_category_report(
    records: Sequence[Mapping[str, str]],
    fractional_weights: Sequence[float],
    integer_weights: Sequence[int],
    cells: Sequence[ValidationCellSpec],
    *,
    rare_threshold: float,
    tolerance: float,
) -> dict[str, Any]:
    selected = [cell for cell in cells if 0 < cell.reference_count <= rare_threshold]
    rows: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    for cell in sorted(selected, key=lambda item: item.name):
        candidate_support, fractional_count, realized_count = _cell_counts(
            records, fractional_weights, integer_weights, cell
        )
        row = {
            **_cell_identity(cell),
            "candidate_support": candidate_support,
            "fractional_count": fractional_count,
            "realized_count": realized_count,
            "fractional_abs_error": abs(fractional_count - cell.reference_count),
            "realized_abs_error": abs(realized_count - cell.reference_count),
            "retained_fractionally": fractional_count > tolerance,
            "retained_in_realization": realized_count > 0,
        }
        rows.append(row)
        if candidate_support == 0:
            issues.append(
                {
                    "severity": "error",
                    "kind": "unsupported_rare_category",
                    "name": cell.name,
                    "message": (
                        "A positive rare reference cell has no candidate support."
                    ),
                }
            )
        elif realized_count == 0:
            issues.append(
                {
                    "severity": "warning",
                    "kind": "rare_category_lost_in_realization",
                    "name": cell.name,
                    "message": (
                        "A supported rare category was lost during integer realization."
                    ),
                }
            )
    return {
        "definition": {
            "reference_count_min_exclusive": 0.0,
            "reference_count_max_inclusive": rare_threshold,
            "reference_count_source": "supplied explicitly for each cell",
        },
        "screened_cells": len(cells),
        "rare_cells": len(selected),
        "items": rows,
        "issues": issues,
    }


def _structural_zero_report(
    records: Sequence[Mapping[str, str]],
    fractional_weights: Sequence[float],
    integer_weights: Sequence[int],
    cells: Sequence[ValidationCellSpec],
    *,
    tolerance: float,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    for cell in sorted(cells, key=lambda item: item.name):
        if cell.reference_count != 0:
            raise ValueError("structural-zero cells require reference_count=0")
        candidate_support, fractional_count, realized_count = _cell_counts(
            records, fractional_weights, integer_weights, cell
        )
        fractional_violation = fractional_count > tolerance
        realized_violation = realized_count > 0
        rows.append(
            {
                **_cell_identity(cell),
                "candidate_support": candidate_support,
                "fractional_count": fractional_count,
                "realized_count": realized_count,
                "fractional_violation": fractional_violation,
                "realized_violation": realized_violation,
            }
        )
        if fractional_violation or realized_violation:
            issues.append(
                {
                    "severity": "error",
                    "kind": "structural_zero_violation",
                    "name": cell.name,
                    "message": (
                        "A declared structural-zero cell has positive fitted or "
                        "realized mass."
                    ),
                }
            )
    return {
        "tolerance": tolerance,
        "cells": len(cells),
        "violations": len(issues),
        "items": rows,
        "issues": issues,
    }


def _cell_counts(
    records: Sequence[Mapping[str, str]],
    fractional_weights: Sequence[float],
    integer_weights: Sequence[int],
    cell: ValidationCellSpec,
) -> tuple[int, float, int]:
    matches = [
        all(
            record.get(dimension) == cell.categories[dimension]
            for dimension in cell.dimensions
        )
        for record in records
    ]
    return (
        sum(matches),
        sum(
            weight
            for weight, matches_cell in zip(fractional_weights, matches, strict=True)
            if matches_cell
        ),
        sum(
            weight
            for weight, matches_cell in zip(integer_weights, matches, strict=True)
            if matches_cell
        ),
    )


def _cell_identity(cell: ValidationCellSpec) -> dict[str, Any]:
    return {
        "name": cell.name,
        "unit": cell.unit,
        "dimensions": list(cell.dimensions),
        "categories": {
            dimension: cell.categories[dimension] for dimension in cell.dimensions
        },
        "reference_count": cell.reference_count,
        "reference_source": cell.reference_source,
    }


def _metric_definitions(population_unit: str) -> dict[str, Any]:
    return {
        "weight_concentration": {
            "input_unit": f"candidate {population_unit}",
            "denominator": "sum of non-negative fractional candidate weights",
            "direction": (
                "higher effective-sample share and lower concentration are preferable"
            ),
            "important_failure_mode": (
                "good residuals can coexist with a few dominant candidates"
            ),
        },
        "candidate_reuse": {
            "input_unit": f"candidate {population_unit}",
            "denominator": "integer realized records or candidate records, as named",
            "direction": "lower reuse usually means greater realized diversity",
            "important_failure_mode": (
                "reuse is not a residual and may be necessary for sparse pools"
            ),
        },
        "rare_categories": {
            "input_unit": "explicit category cell",
            "denominator": "cell-specific supplied reference count",
            "direction": "retain supported reference cells while reporting tail error",
            "important_failure_mode": (
                "a sampling zero is not automatically a structural zero"
            ),
        },
        "structural_zeros": {
            "input_unit": "explicit category cell",
            "denominator": "declared zero reference cell",
            "direction": "zero fitted and realized mass is required",
            "important_failure_mode": (
                "a zero must be sourced, not inferred from absent candidates"
            ),
        },
        "fields": {
            "input_unit": "generated field",
            "denominator": "all explicitly classified fields",
            "direction": (
                "pair declared field tiers with independently verified source, "
                "universe, fit, and residual evidence"
            ),
            "important_failure_mode": (
                "field presence does not make it locally representative"
            ),
        },
    }


def read_external_comparison_descriptor(path: Path) -> dict[str, Any]:
    """Read and strictly validate a pinned external-comparison descriptor."""

    try:
        payload = json.loads(path.read_text())
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(
            f"could not read external comparison descriptor: {exc}"
        ) from exc
    if not isinstance(payload, dict):
        raise ValueError("external comparison descriptor must be a JSON object")
    if payload.get("schema_version") != EXTERNAL_COMPARISON_SCHEMA_VERSION:
        raise ValueError("unsupported external comparison descriptor schema")
    for key in (
        "comparison_id",
        "title",
        "source",
        "resource",
        "download_policy",
        "fixture",
    ):
        if key not in payload:
            raise ValueError(f"external comparison descriptor requires {key!r}")
    source = _required_mapping(payload, "source")
    resource = _required_mapping(payload, "resource")
    policy = _required_mapping(payload, "download_policy")
    fixture = _required_mapping(payload, "fixture")
    for key in ("doi", "version", "license", "record_url"):
        _require_text(source.get(key), f"source {key}")
    filename = _safe_filename(resource.get("filename"))
    _require_https(resource.get("url"), "resource URL")
    size = _positive_integer(resource.get("byte_size"), "resource byte_size")
    algorithm, digest = _parse_checksum(resource.get("checksum"))
    if policy.get("default") != "disabled":
        raise ValueError("external comparison downloads must be disabled by default")
    if policy.get("explicit_opt_in_required") is not True:
        raise ValueError("external comparison download must require explicit opt-in")
    if policy.get("cache_outside_git") is not True:
        raise ValueError("external comparison resources must remain outside git")
    maximum = _positive_integer(policy.get("maximum_bytes"), "maximum_bytes")
    if maximum < size:
        raise ValueError("download maximum_bytes is smaller than the pinned resource")
    if fixture.get("contains_external_records") is not False:
        raise ValueError("the committed fixture must not contain external records")
    fixture_path = _safe_relative_path(fixture.get("path"), "fixture path")
    fixture_algorithm, fixture_digest = _parse_checksum(fixture.get("checksum"))
    if fixture_algorithm != "sha256":
        raise ValueError("the committed fixture requires a SHA-256 checksum")
    empirical_payload = payload.get("empirical_aggregate_evidence")
    empirical: dict[str, Any] | None = None
    if empirical_payload is not None:
        if not isinstance(empirical_payload, dict):
            raise ValueError("empirical_aggregate_evidence must be an object")
        empirical_path = _safe_relative_path(
            empirical_payload.get("path"), "empirical aggregate evidence path"
        )
        empirical_algorithm, empirical_digest = _parse_checksum(
            empirical_payload.get("checksum")
        )
        if empirical_algorithm != "sha256":
            raise ValueError("empirical aggregate evidence requires SHA-256")
        if empirical_payload.get("contains_external_records") is not False:
            raise ValueError("empirical evidence must not contain external rows")
        if empirical_payload.get("aggregate_only") is not True:
            raise ValueError("empirical evidence must be aggregate-only")
        empirical = {
            **empirical_payload,
            "path": str(empirical_path),
            "checksum": f"{empirical_algorithm}:{empirical_digest}",
        }
    return {
        **payload,
        "resource": {
            **resource,
            "filename": filename,
            "byte_size": size,
            "checksum": f"{algorithm}:{digest}",
        },
        "download_policy": {**policy, "maximum_bytes": maximum},
        "fixture": {
            **fixture,
            "path": str(fixture_path),
            "checksum": f"{fixture_algorithm}:{fixture_digest}",
        },
        **(
            {"empirical_aggregate_evidence": empirical} if empirical is not None else {}
        ),
    }


def validate_external_comparison_fixture(descriptor_path: Path) -> dict[str, Any]:
    """Verify the committed schema-only fixture without network access."""

    descriptor = read_external_comparison_descriptor(descriptor_path)
    fixture = descriptor["fixture"]
    fixture_path = (descriptor_path.parent / fixture["path"]).resolve()
    root = descriptor_path.parent.resolve()
    if not fixture_path.is_relative_to(root):
        raise ValueError("external comparison fixture escapes its descriptor directory")
    if not fixture_path.is_file():
        raise ValueError("external comparison fixture is missing")
    actual_checksum = f"sha256:{_file_digest(fixture_path, 'sha256')}"
    if actual_checksum != fixture["checksum"]:
        raise ValueError("external comparison fixture checksum does not match")
    with fixture_path.open(newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        columns = reader.fieldnames or []
    expected_columns = descriptor.get("schema_crosswalk", {}).get("external_fields")
    if not isinstance(expected_columns, list) or not all(
        isinstance(column, str) and column for column in expected_columns
    ):
        raise ValueError("schema_crosswalk.external_fields must be a string list")
    missing = sorted(set(expected_columns) - set(columns))
    if missing:
        raise ValueError(
            "external comparison fixture is missing fields: " + ", ".join(missing)
        )
    empirical_result: dict[str, Any] | None = None
    empirical = descriptor.get("empirical_aggregate_evidence")
    if isinstance(empirical, dict):
        empirical_path = (descriptor_path.parent / empirical["path"]).resolve()
        if not empirical_path.is_relative_to(root):
            raise ValueError("empirical aggregate evidence escapes its directory")
        if not empirical_path.is_file():
            raise ValueError("empirical aggregate evidence is missing")
        actual_empirical_checksum = f"sha256:{_file_digest(empirical_path, 'sha256')}"
        if actual_empirical_checksum != empirical["checksum"]:
            raise ValueError("empirical aggregate evidence checksum does not match")
        try:
            empirical_payload = json.loads(empirical_path.read_text())
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError(
                f"could not read empirical aggregate evidence: {exc}"
            ) from exc
        if (
            not isinstance(empirical_payload, dict)
            or empirical_payload.get("schema_version")
            != "synthpopcan-external-aggregate-comparison-v1"
        ):
            raise ValueError("unsupported empirical aggregate evidence schema")
        safety = empirical_payload.get("public_safety")
        if not isinstance(safety, dict) or safety.get("aggregate_only") is not True:
            raise ValueError("empirical evidence lacks aggregate-only safety metadata")
        if safety.get("contains_source_rows") is not False:
            raise ValueError("empirical evidence may not contain source rows")
        empirical_result = {
            "path": str(empirical_path),
            "checksum": actual_empirical_checksum,
            "schema_version": empirical_payload["schema_version"],
            "aggregate_only": True,
        }
    return {
        "schema_version": EXTERNAL_COMPARISON_SCHEMA_VERSION,
        "passed": True,
        "comparison_id": descriptor["comparison_id"],
        "network_accessed": False,
        "contains_external_records": False,
        "fixture_path": str(fixture_path),
        "fixture_checksum": actual_checksum,
        "rows": len(rows),
        "columns": columns,
        "empirical_aggregate_evidence": empirical_result,
    }


def resolve_external_comparison_archive(
    descriptor_path: Path,
    cache_dir: Path,
    *,
    allow_download: bool = False,
    downloader: Callable[[str, Path, int], None] | None = None,
) -> Path:
    """Return a verified cached archive, downloading only after explicit opt-in.

    The caller must provide ``downloader`` when enabling a transfer.  This
    deliberate boundary prevents the 9.6 GB reference archive from being
    fetched accidentally by tests or an ordinary library import.
    """

    descriptor = read_external_comparison_descriptor(descriptor_path)
    resource = descriptor["resource"]
    destination = cache_dir / resource["filename"]
    if destination.is_file():
        _verify_pinned_resource(destination, resource)
        return destination
    if not allow_download:
        raise FileNotFoundError(
            "external comparison archive is not cached; downloading is opt-in"
        )
    if downloader is None:
        raise ValueError(
            "an explicit downloader is required for external comparison data"
        )
    cache_dir.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.download")
    if temporary.exists():
        raise ValueError("external comparison temporary download already exists")
    try:
        downloader(
            str(resource["url"]),
            temporary,
            int(descriptor["download_policy"]["maximum_bytes"]),
        )
        _verify_pinned_resource(temporary, resource)
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)
    return destination


def _verify_pinned_resource(path: Path, resource: Mapping[str, Any]) -> None:
    expected_size = int(resource["byte_size"])
    if path.stat().st_size != expected_size:
        raise ValueError("external comparison archive byte size does not match")
    algorithm, expected = _parse_checksum(resource["checksum"])
    if _file_digest(path, algorithm) != expected:
        raise ValueError("external comparison archive checksum does not match")


def _file_digest(path: Path, algorithm: str) -> str:
    digest = (
        hashlib.md5(usedforsecurity=False) if algorithm == "md5" else hashlib.sha256()
    )
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _parse_checksum(value: object) -> tuple[str, str]:
    if not isinstance(value, str) or ":" not in value:
        raise ValueError("checksum must include its algorithm")
    algorithm, digest = value.split(":", 1)
    expected_length = {"md5": 32, "sha256": 64}.get(algorithm)
    if (
        expected_length is None
        or len(digest) != expected_length
        or not set(digest) <= _HEX_DIGITS
    ):
        raise ValueError("checksum must be a lowercase MD5 or SHA-256 digest")
    return algorithm, digest


def _safe_filename(value: object) -> str:
    _require_text(value, "resource filename")
    assert isinstance(value, str)
    if Path(value).name != value or value in {".", ".."}:
        raise ValueError("resource filename must be a plain filename")
    return value


def _safe_relative_path(value: object, label: str) -> Path:
    _require_text(value, label)
    assert isinstance(value, str)
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"{label} must remain below the descriptor directory")
    return path


def _require_https(value: object, label: str) -> None:
    _require_text(value, label)
    assert isinstance(value, str)
    if not value.startswith("https://"):
        raise ValueError(f"{label} must use HTTPS")


def _positive_integer(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{label} must be a positive integer")
    return value


def _required_mapping(payload: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = payload.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"external comparison descriptor requires object {key!r}")
    return value


def _require_text(value: object, label: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be non-empty text")
