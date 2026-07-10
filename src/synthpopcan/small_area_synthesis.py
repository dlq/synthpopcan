"""Small-area linked household/person synthesis helpers."""

from __future__ import annotations

__all__ = [
    "GeographyHouseholdFit",
    "calibrate_linked_household_csvs",
    "check_linked_person_calibration_inputs",
    "check_small_area_calibration_inputs",
    "controls_by_geography",
    "estimate_small_area_run",
    "fit_households_by_geography",
    "fit_linked_by_geography",
    "realize_linked_geography_population",
]

import csv
import json
import os
from collections import defaultdict
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from synthpopcan.controls import (
    ControlCell,
    ControlMargin,
    ControlTable,
    read_control_table,
)
from synthpopcan.diagnostics import build_ipf_fit_report, relative_error
from synthpopcan.ipf import (
    IPFResult,
    NumpyIPFIndex,
    _initial_weights,
    integerize_weights,
)
from synthpopcan.tabular import format_csv_number

HouseholdRow = dict[str, str]
PersonRow = dict[str, str]


@dataclass(frozen=True)
class GeographyHouseholdFit:
    """Fitted candidate-household weights and reports for each target geography."""

    weights_by_geography: dict[str, list[float]]
    reports: dict[str, dict[str, Any]]


@dataclass(frozen=True)
class _ConstraintSpec:
    unit: str
    margin: str
    dimensions: tuple[str, ...]
    categories: tuple[str, ...]


@dataclass(frozen=True)
class _LinkedCalibrationIndex:
    specs: tuple[_ConstraintSpec, ...]
    contributions: np.ndarray

    @classmethod
    def build(
        cls,
        households: Sequence[HouseholdRow],
        persons: Sequence[PersonRow],
        household_controls: ControlTable,
        person_controls: ControlTable,
        *,
        household_id_column: str,
    ) -> _LinkedCalibrationIndex:
        specs = tuple(
            _constraint_specs(household_controls, unit="household")
            + _constraint_specs(person_controls, unit="person")
        )
        household_indexes = {
            household[household_id_column]: index
            for index, household in enumerate(households)
        }
        rows: list[np.ndarray] = []
        for spec in specs:
            if spec.unit == "household":
                rows.append(
                    np.fromiter(
                        (
                            all(
                                household.get(dimension, "") == category
                                for dimension, category in zip(
                                    spec.dimensions,
                                    spec.categories,
                                    strict=True,
                                )
                            )
                            for household in households
                        ),
                        dtype=np.float64,
                        count=len(households),
                    )
                )
                continue
            contribution = np.zeros(len(households), dtype=np.float64)
            for person in persons:
                if not all(
                    person.get(dimension, "") == category
                    for dimension, category in zip(
                        spec.dimensions,
                        spec.categories,
                        strict=True,
                    )
                ):
                    continue
                household_index = household_indexes.get(
                    person.get(household_id_column, "")
                )
                if household_index is not None:
                    contribution[household_index] += 1.0
            rows.append(contribution)
        return cls(
            specs=specs,
            contributions=np.vstack(rows),
        )

    def targets(
        self,
        household_controls: ControlTable,
        person_controls: ControlTable,
    ) -> np.ndarray:
        targets_by_spec = {
            _constraint_spec_key(spec): target
            for controls, unit in (
                (household_controls, "household"),
                (person_controls, "person"),
            )
            for spec, target in _control_spec_targets(controls, unit=unit)
        }
        expected = {_constraint_spec_key(spec) for spec in self.specs}
        if set(targets_by_spec) != expected:
            raise ValueError(
                "household and person control cells must have the same category "
                "structure in every target geography"
            )
        return np.asarray(
            [targets_by_spec[_constraint_spec_key(spec)] for spec in self.specs],
            dtype=np.float64,
        )


def controls_by_geography(
    controls: ControlTable,
    *,
    geography_dimension: str,
) -> dict[str, ControlTable]:
    """Split normalized controls into one control table per target geography.

    The returned control tables remove ``geography_dimension`` from each margin
    so a candidate household pool can be fitted independently to every target
    geography.
    """

    grouped: dict[str, list[ControlMargin]] = defaultdict(list)
    for margin in controls.margins:
        if geography_dimension not in margin.dimensions:
            raise ValueError(
                f"control margin {margin.name!r} does not include geography "
                f"dimension {geography_dimension!r}"
            )
        reduced_dimensions = tuple(
            dimension
            for dimension in margin.dimensions
            if dimension != geography_dimension
        )
        if not reduced_dimensions:
            raise ValueError(
                f"control margin {margin.name!r} must include at least one "
                f"dimension besides {geography_dimension!r}"
            )

        cells_by_geography: dict[str, list[ControlCell]] = defaultdict(list)
        for cell in margin.cells:
            geography = cell.categories.get(geography_dimension, "")
            if not geography:
                raise ValueError(
                    f"control margin {margin.name!r} has a cell without "
                    f"{geography_dimension!r}"
                )
            cells_by_geography[geography].append(
                ControlCell(
                    categories={
                        dimension: cell.categories[dimension]
                        for dimension in reduced_dimensions
                    },
                    count=cell.count,
                )
            )
        for geography, cells in cells_by_geography.items():
            grouped[geography].append(
                ControlMargin(
                    name=margin.name,
                    dimensions=reduced_dimensions,
                    cells=tuple(cells),
                )
            )

    return {
        geography: ControlTable(
            margins=tuple(margins),
            dimensions=_control_dimensions(margins),
        )
        for geography, margins in grouped.items()
    }


def check_small_area_calibration_inputs(
    households: Sequence[HouseholdRow],
    controls: ControlTable,
    *,
    geography_dimension: str,
) -> dict[str, Any]:
    """Check that household candidates contain the columns and categories needed.

    This preflight catches the common small-area setup errors before IPF starts,
    so users see a workflow-level message rather than a lower-level seed-record
    exception.
    """
    return _check_calibration_inputs(
        households,
        controls,
        geography_dimension=geography_dimension,
        candidate_unit="household",
    )


def check_linked_person_calibration_inputs(
    households: Sequence[HouseholdRow],
    persons: Sequence[PersonRow],
    controls: ControlTable,
    *,
    geography_dimension: str,
    household_id_column: str = "synthetic_household_id",
) -> dict[str, Any]:
    """Check person controls and household linkage before linked calibration."""
    report = _check_calibration_inputs(
        persons,
        controls,
        geography_dimension=geography_dimension,
        candidate_unit="person",
    )
    household_ids = {
        household[household_id_column]
        for household in households
        if household.get(household_id_column)
    }
    missing_link_count = sum(not person.get(household_id_column) for person in persons)
    orphan_count = sum(
        bool(person.get(household_id_column))
        and person.get(household_id_column) not in household_ids
        for person in persons
    )
    link_issues: list[dict[str, Any]] = []
    if missing_link_count:
        link_issues.append(
            {
                "severity": "error",
                "kind": "missing_person_household_id",
                "missing_persons": missing_link_count,
                "message": (
                    f"{missing_link_count} candidate person rows do not have "
                    f"'{household_id_column}'."
                ),
                "tip": "Regenerate or repair linked candidates before calibration.",
            }
        )
    if orphan_count:
        link_issues.append(
            {
                "severity": "error",
                "kind": "orphan_person_household",
                "orphan_persons": orphan_count,
                "message": (
                    f"{orphan_count} candidate person rows refer to households "
                    "outside the candidate household pool."
                ),
                "tip": (
                    "Use household and person CSVs from the same generation run, "
                    "or subsample them together."
                ),
            }
        )
    issues = [*link_issues, *report["issues"]]
    report.update(
        {
            "passed": not any(issue["severity"] == "error" for issue in issues),
            "candidate_persons": len(persons),
            "linked_households": len(household_ids),
            "error_count": sum(issue["severity"] == "error" for issue in issues),
            "warning_count": sum(issue["severity"] == "warning" for issue in issues),
            "issues": issues,
        }
    )
    return report


def _check_calibration_inputs(
    candidates: Sequence[dict[str, str]],
    controls: ControlTable,
    *,
    geography_dimension: str,
    candidate_unit: str,
) -> dict[str, Any]:
    candidate_label = (
        "candidate households"
        if candidate_unit == "household"
        else "candidate person rows"
    )
    candidate_columns = set().union(*(candidate.keys() for candidate in candidates))
    issues: list[dict[str, Any]] = []
    missing_dimensions: set[str] = set()
    missing_categories: set[tuple[str, str]] = set()
    for dimension in controls.dimensions:
        if dimension == geography_dimension:
            continue
        if dimension not in candidate_columns:
            issues.append(
                _missing_candidate_column_issue(
                    dimension,
                    candidate_unit=candidate_unit,
                )
            )
            missing_dimensions.add(dimension)
            continue
        candidate_categories = {
            str(candidate.get(dimension, "")) for candidate in candidates
        }
        for category in sorted(controls.categories_for(dimension)):
            if category not in candidate_categories:
                missing_categories.add((dimension, category))
                issues.append(
                    {
                        "severity": "error",
                        "kind": "missing_candidate_category",
                        "dimension": dimension,
                        "category": category,
                        "message": (
                            f"For dimension '{dimension}', controls include "
                            f"'{category}', but {candidate_label} do not."
                        ),
                        "tip": _missing_category_tip(candidate_unit),
                    }
                )

    issues.extend(
        _inconsistent_margin_total_issues(
            controls,
            geography_dimension=geography_dimension,
        )
    )
    issues.extend(
        _structural_zero_issues(
            candidates,
            controls,
            geography_dimension=geography_dimension,
            missing_dimensions=missing_dimensions,
            missing_categories=missing_categories,
            candidate_unit=candidate_unit,
        )
    )
    if not any(issue["severity"] == "error" for issue in issues):
        issues.extend(
            _sparse_support_warnings(
                candidates,
                controls,
                geography_dimension=geography_dimension,
                candidate_unit=candidate_unit,
            )
        )
    candidate_key = f"candidate_{candidate_unit}s"
    return {
        "passed": not any(issue["severity"] == "error" for issue in issues),
        candidate_key: len(candidates),
        "control_margins": len(controls.margins),
        "geography_dimension": geography_dimension,
        "error_count": sum(issue["severity"] == "error" for issue in issues),
        "warning_count": sum(issue["severity"] == "warning" for issue in issues),
        "issues": issues,
    }


def _missing_category_tip(candidate_unit: str) -> str:
    if candidate_unit == "person":
        return (
            "Review person-control category labels and mappings, or treat this "
            "margin as validation-only until linked candidates cover it."
        )
    return (
        "Review category labels and mappings. If this is a Census Profile "
        "household-size control, use household_size_group or run with "
        "--max-household-size 5."
    )


def _inconsistent_margin_total_issues(
    controls: ControlTable,
    *,
    geography_dimension: str,
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for geography, geography_controls in controls_by_geography(
        controls,
        geography_dimension=geography_dimension,
    ).items():
        margin_totals = {
            margin.name: sum(cell.count for cell in margin.cells)
            for margin in geography_controls.margins
        }
        if len(margin_totals) < 2:
            continue
        totals = list(margin_totals.values())
        if max(totals) - min(totals) <= 1e-6:
            continue
        issues.append(
            {
                "severity": "error",
                "kind": "inconsistent_margin_totals",
                "geography": geography,
                "margin_totals": margin_totals,
                "message": (
                    f"Control margins for geography '{geography}' do not have "
                    "the same total."
                ),
                "tip": (
                    "Use margins for the same population universe and reference "
                    "period, then reconcile suppression or rounding differences."
                ),
            }
        )
    return issues


def _structural_zero_issues(
    candidates: Sequence[dict[str, str]],
    controls: ControlTable,
    *,
    geography_dimension: str,
    missing_dimensions: set[str],
    missing_categories: set[tuple[str, str]],
    candidate_unit: str,
) -> list[dict[str, Any]]:
    unsupported: dict[
        tuple[str, tuple[str, ...], tuple[tuple[str, str], ...]], list[str]
    ] = defaultdict(list)
    for margin in controls.margins:
        dimensions = tuple(
            dimension
            for dimension in margin.dimensions
            if dimension != geography_dimension
        )
        if any(dimension in missing_dimensions for dimension in dimensions):
            continue
        for cell in margin.cells:
            if cell.count <= 0:
                continue
            categories = tuple(
                (dimension, cell.categories[dimension]) for dimension in dimensions
            )
            if any(item in missing_categories for item in categories):
                continue
            if any(
                all(
                    candidate.get(dimension, "") == category
                    for dimension, category in categories
                )
                for candidate in candidates
            ):
                continue
            key = (margin.name, dimensions, categories)
            geography = cell.categories.get(geography_dimension, "")
            if geography and geography not in unsupported[key]:
                unsupported[key].append(geography)

    return [
        {
            "severity": "error",
            "kind": "structural_zero",
            "margin": margin,
            "dimensions": list(dimensions),
            "categories": dict(categories),
            "geographies": sorted(geographies),
            "message": (
                f"Control cell {dict(categories)!r} in margin '{margin}' has a "
                f"positive target but no matching candidate {candidate_unit} row."
            ),
            "tip": (
                f"Add candidate {candidate_unit} rows for this category "
                "combination, coarsen the "
                "control, or treat the margin as validation-only."
            ),
        }
        for (margin, dimensions, categories), geographies in unsupported.items()
    ]


def _sparse_support_warnings(
    candidates: Sequence[dict[str, str]],
    controls: ControlTable,
    *,
    geography_dimension: str,
    candidate_unit: str,
) -> list[dict[str, Any]]:
    warnings: list[dict[str, Any]] = []
    sparse_geographies: list[str] = []
    controls_for_geographies = controls_by_geography(
        controls,
        geography_dimension=geography_dimension,
    )
    for geography, geography_controls in controls_for_geographies.items():
        if _first_margin_total(geography_controls) < 50:
            sparse_geographies.append(geography)
    if sparse_geographies:
        target_unit = "households" if candidate_unit == "household" else "people"
        warnings.append(
            {
                "severity": "warning",
                "kind": "sparse_geography",
                "geography_count": len(sparse_geographies),
                "geographies": sorted(sparse_geographies)[:10],
                "message": (
                    f"{len(sparse_geographies)} target geographies contain fewer "
                    f"than 50 {target_unit}."
                ),
                "tip": (
                    "Review residuals and disclosure risk carefully, or use this "
                    "margin only for validation at a broader geography."
                ),
            }
        )

    seen_cells: set[tuple[str, tuple[tuple[str, str], ...]]] = set()
    sparse_cells: list[dict[str, Any]] = []
    for margin in controls.margins:
        dimensions = tuple(
            dimension
            for dimension in margin.dimensions
            if dimension != geography_dimension
        )
        for cell in margin.cells:
            if cell.count <= 0:
                continue
            categories = tuple(
                (dimension, cell.categories[dimension]) for dimension in dimensions
            )
            cell_key = (margin.name, categories)
            if cell_key in seen_cells:
                continue
            seen_cells.add(cell_key)
            support = sum(
                all(
                    candidate.get(dimension, "") == category
                    for dimension, category in categories
                )
                for candidate in candidates
            )
            if support < 2:
                sparse_cells.append(
                    {
                        "margin": margin.name,
                        "categories": dict(categories),
                        f"candidate_{candidate_unit}s": support,
                    }
                )
    if sparse_cells:
        warnings.append(
            {
                "severity": "warning",
                "kind": "sparse_candidate_support",
                "cell_count": len(sparse_cells),
                "cells": sparse_cells[:10],
                "message": (
                    f"{len(sparse_cells)} positive control cells are represented "
                    f"by fewer than two candidate {candidate_unit} rows."
                ),
                "tip": (
                    "Increase or broaden the candidate pool before relying on "
                    "uncalibrated attributes in those cells."
                ),
            }
        )
    return warnings


def estimate_small_area_run(
    controls: ControlTable,
    *,
    geography_dimension: str,
    candidate_households: int,
    pool_size: int | None = None,
    average_persons_per_household: float = 2.22,
) -> dict[str, Any]:
    """Estimate small-area run scale before generating or calibrating rows.

    The estimate is intentionally simple and file-free: callers provide the
    controls already planned for calibration plus the expected candidate pool
    size. The result is suitable for CLI summaries, notebook checks, and JSON
    automation before launching a large linked synthesis job.
    """
    if candidate_households <= 0:
        raise ValueError("candidate_households must be greater than zero")
    if pool_size is not None and pool_size <= 0:
        raise ValueError("pool_size must be greater than zero")
    if average_persons_per_household < 0:
        raise ValueError("average_persons_per_household cannot be negative")

    controls_for_geographies = controls_by_geography(
        controls,
        geography_dimension=geography_dimension,
    )
    target_households = sum(
        _first_margin_total(geo_controls)
        for geo_controls in controls_for_geographies.values()
    )
    target_households_i = int(round(target_households))
    estimated_persons = int(round(target_households * average_persons_per_household))
    calibration_pool_size = min(pool_size or candidate_households, candidate_households)
    recommended_surface = (
        "web_app_ok"
        if candidate_households <= 10_000
        and target_households_i <= 50_000
        and estimated_persons <= 125_000
        else "cli_or_python_api"
    )
    return {
        "schema_version": "synthpopcan-small-area-performance-estimate-v1",
        "target_geographies": len(controls_for_geographies),
        "target_households": target_households_i,
        "estimated_persons": estimated_persons,
        "estimated_total_output_rows": target_households_i + estimated_persons,
        "candidate_households": candidate_households,
        "calibration_pool_size": calibration_pool_size,
        "candidate_pool_fraction": calibration_pool_size / candidate_households,
        "fits_to_run": len(controls_for_geographies),
        "recommended_surface": recommended_surface,
        "guidance": _small_area_performance_guidance(
            candidate_households=candidate_households,
            calibration_pool_size=calibration_pool_size,
            recommended_surface=recommended_surface,
        ),
    }


def _first_margin_total(controls: ControlTable) -> float:
    if not controls.margins:
        return 0.0
    return sum(cell.count for cell in controls.margins[0].cells)


def _small_area_performance_guidance(
    *,
    candidate_households: int,
    calibration_pool_size: int,
    recommended_surface: str,
) -> list[str]:
    guidance = [
        f"Calibration will fit {calibration_pool_size:,} candidate households "
        "for each target geography."
    ]
    if calibration_pool_size == candidate_households and candidate_households > 10_000:
        guidance.append(
            "Start with --pool-size 10000 for exploratory runs; increase it only "
            "if validation shows poor fit or too little household variety."
        )
    if recommended_surface == "cli_or_python_api":
        guidance.append(
            "Keep the web app for small demos; use the CLI or Python API for "
            "large linked CSV outputs."
        )
    else:
        guidance.append("This is small enough for the web app, CLI, or Python API.")
    return guidance


def _missing_candidate_column_issue(
    dimension: str,
    *,
    candidate_unit: str = "household",
) -> dict[str, Any]:
    if candidate_unit == "household" and dimension == "household_size_group":
        tip = (
            "For Census Profile household-size controls, run "
            "`synthpopcan geo synthesize-from-package ... --max-household-size 5`, "
            "or run `geo build-controls` with candidate recoding so "
            "household_size_group is added."
        )
    else:
        tip = (
            "Choose controls whose non-geography dimensions exist in the candidate "
            f"{candidate_unit} CSV, or add/map this column before calibration."
        )
    message = (
        f"Controls require candidate column '{dimension}', but household "
        "candidates do not have it."
        if candidate_unit == "household"
        else (
            f"Controls require candidate column '{dimension}', but candidate "
            "person rows do not have it."
        )
    )
    return {
        "severity": "error",
        "kind": "missing_candidate_column",
        "dimension": dimension,
        "message": message,
        "tip": tip,
    }


def fit_households_by_geography(
    households: Sequence[HouseholdRow],
    controls: ControlTable,
    *,
    geography_dimension: str,
    household_id_column: str = "synthetic_household_id",
    weight_field: str | None = None,
    max_iterations: int = 100,
    tolerance: float = 1e-6,
    n_workers: int | None = None,
) -> GeographyHouseholdFit:
    """Fit the same candidate household pool to each target geography.

    Parameters
    ----------
    weight_field:
        Optional household column with non-negative starting weights.  Every
        geography fit starts from these weights instead of uniform ``1.0``,
        so candidates that IPF cannot distinguish keep their relative
        starting proportions.
    n_workers:
        Number of threads for parallel geography fitting.  Each geography's
        IPF is independent and numpy releases the GIL during ``bincount``
        and array arithmetic, so threading gives real concurrency.  Defaults
        to ``min(os.cpu_count(), 8)`` when ``None``.
    """

    if not households:
        raise ValueError("at least one candidate household row is required")
    missing_id_rows = [
        index
        for index, household in enumerate(households, start=2)
        if not household.get(household_id_column)
    ]
    if missing_id_rows:
        raise ValueError(
            f"household row {missing_id_rows[0]} requires {household_id_column!r}"
        )

    controls_for_geographies = controls_by_geography(
        controls,
        geography_dimension=geography_dimension,
    )
    if not controls_for_geographies:
        raise ValueError("controls contain no target geographies")

    # Pre-build the numpy index once for the whole candidate pool.
    # All geographies share the same dimension structure; only targets differ.
    first_margins = next(iter(controls_for_geographies.values())).to_ipf_margins()
    numpy_index = NumpyIPFIndex.build(households, first_margins)

    starting_weights: np.ndarray | None = None
    if weight_field is not None:
        starting_weights = np.asarray(
            _initial_weights(households, weight_field), dtype=np.float64
        )

    _n_workers = min(n_workers or (os.cpu_count() or 1), 8)

    def _fit_geo(
        geo_ctrl_pair: tuple[str, ControlTable],
    ) -> tuple[str, list[float], dict[str, Any]]:
        geography, geo_controls = geo_ctrl_pair
        ipf_margins = geo_controls.to_ipf_margins()
        # fit() returns a raw ndarray; keep it until compute_totals is done
        # to avoid a tolist() → asarray() round-trip in the report step.
        weights_np, converged, iterations, max_abs_error = numpy_index.fit(
            ipf_margins,
            max_iterations=max_iterations,
            tolerance=tolerance,
            initial_weights=starting_weights,
        )
        # compute_totals uses numpy bincount, replacing the Python weighted_totals loop
        precomputed = numpy_index.compute_totals(weights_np)
        weights_list = weights_np.tolist()
        result = IPFResult(
            households, weights_list, converged, iterations, max_abs_error
        )
        report = build_ipf_fit_report(
            geo_controls, result, precomputed_totals=precomputed
        )
        return geography, weights_list, report

    weights_by_geography: dict[str, list[float]] = {}
    reports: dict[str, dict[str, Any]] = {}

    # ThreadPoolExecutor gives real concurrency here: numpy releases the GIL
    # during bincount and array arithmetic, letting multiple geography fits
    # overlap on separate CPU cores without any data races (each fit allocates
    # its own weights array; enc.cat_ids is shared read-only).
    with ThreadPoolExecutor(max_workers=_n_workers) as executor:
        for geography, weights_list, report in executor.map(
            _fit_geo, controls_for_geographies.items()
        ):
            weights_by_geography[geography] = weights_list
            reports[geography] = report

    return GeographyHouseholdFit(
        weights_by_geography=weights_by_geography,
        reports=reports,
    )


def fit_linked_by_geography(
    households: Sequence[HouseholdRow],
    persons: Sequence[PersonRow],
    household_controls: ControlTable,
    person_controls: ControlTable,
    *,
    geography_dimension: str,
    household_id_column: str = "synthetic_household_id",
    weight_field: str | None = None,
    max_iterations: int = 100,
    tolerance: float = 1e-6,
    n_workers: int | None = None,
) -> GeographyHouseholdFit:
    """Fit household and linked-person controls with household weights.

    Household-only IPF supplies the initial weights. A joint iterative
    proportional updating pass then adjusts those same household weights using
    household indicators and linked-person category counts. Selecting a
    household therefore always selects all people linked to it.
    """
    household_fit = fit_households_by_geography(
        households,
        household_controls,
        geography_dimension=geography_dimension,
        household_id_column=household_id_column,
        weight_field=weight_field,
        max_iterations=max_iterations,
        tolerance=tolerance,
        n_workers=n_workers,
    )
    household_by_geography = controls_by_geography(
        household_controls,
        geography_dimension=geography_dimension,
    )
    person_by_geography = controls_by_geography(
        person_controls,
        geography_dimension=geography_dimension,
    )
    if set(household_by_geography) != set(person_by_geography):
        missing_person = sorted(set(household_by_geography) - set(person_by_geography))
        missing_household = sorted(
            set(person_by_geography) - set(household_by_geography)
        )
        raise ValueError(
            "household and person controls must cover the same geographies; "
            f"missing person controls for {missing_person[:5]!r}, missing household "
            f"controls for {missing_household[:5]!r}"
        )

    first_geography = sorted(household_by_geography)[0]
    index = _LinkedCalibrationIndex.build(
        households,
        persons,
        household_by_geography[first_geography],
        person_by_geography[first_geography],
        household_id_column=household_id_column,
    )
    worker_count = min(n_workers or (os.cpu_count() or 1), 8)

    def _fit_geography(
        geography: str,
    ) -> tuple[str, list[float], dict[str, Any]]:
        targets = index.targets(
            household_by_geography[geography],
            person_by_geography[geography],
        )
        initial_weights = np.asarray(
            household_fit.weights_by_geography[geography],
            dtype=np.float64,
        )
        weights, converged, iterations, max_abs_error = _fit_joint_constraints(
            index.contributions,
            targets,
            initial_weights=initial_weights,
            max_iterations=max_iterations,
            tolerance=tolerance,
        )
        fitted = index.contributions @ weights
        integer_weights = np.asarray(
            integerize_weights(weights.tolist()),
            dtype=np.float64,
        )
        realized = index.contributions @ integer_weights
        report = _linked_constraint_report(
            index.specs,
            targets,
            fitted,
            converged=converged,
            iterations=iterations,
            max_abs_error=max_abs_error,
            seed_records=len(households),
        )
        report["household_stage"] = household_fit.reports[geography]
        report["realized"] = _linked_constraint_report(
            index.specs,
            targets,
            realized,
            converged=bool(np.max(np.abs(realized - targets)) <= tolerance),
            iterations=0,
            max_abs_error=float(np.max(np.abs(realized - targets))),
            seed_records=len(households),
            include_issues=False,
        )
        return geography, weights.tolist(), report

    weights_by_geography: dict[str, list[float]] = {}
    reports: dict[str, dict[str, Any]] = {}
    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        for geography, weights, report in executor.map(
            _fit_geography,
            sorted(household_by_geography),
        ):
            weights_by_geography[geography] = weights
            reports[geography] = report
    return GeographyHouseholdFit(weights_by_geography, reports)


def _constraint_specs(
    controls: ControlTable,
    *,
    unit: str,
) -> list[_ConstraintSpec]:
    return [spec for spec, _target in _control_spec_targets(controls, unit=unit)]


def _control_spec_targets(
    controls: ControlTable,
    *,
    unit: str,
) -> list[tuple[_ConstraintSpec, float]]:
    return [
        (
            _ConstraintSpec(
                unit=unit,
                margin=margin.name,
                dimensions=margin.dimensions,
                categories=tuple(
                    cell.categories[dimension] for dimension in margin.dimensions
                ),
            ),
            cell.count,
        )
        for margin in controls.margins
        for cell in margin.cells
    ]


def _constraint_spec_key(
    spec: _ConstraintSpec,
) -> tuple[str, str, tuple[str, ...], tuple[str, ...]]:
    return spec.unit, spec.margin, spec.dimensions, spec.categories


def _fit_joint_constraints(
    contributions: np.ndarray,
    targets: np.ndarray,
    *,
    initial_weights: np.ndarray,
    max_iterations: int,
    tolerance: float,
) -> tuple[np.ndarray, bool, int, float]:
    """Run iterative proportional updating over household contribution rows."""
    if max_iterations < 1:
        raise ValueError("max_iterations must be at least 1")
    if tolerance < 0:
        raise ValueError("tolerance must be non-negative")
    if contributions.shape[1] != len(initial_weights):
        raise ValueError("joint calibration contributions do not match households")
    weights = np.asarray(initial_weights, dtype=np.float64).copy()
    if np.any(weights < 0):
        raise ValueError("initial household weights must be non-negative")

    for row, target in zip(contributions, targets, strict=True):
        if target == 0:
            weights[row > 0] = 0.0
    for row, target in zip(contributions, targets, strict=True):
        if target > 0 and float(row @ weights) <= 0:
            raise ValueError(
                "a positive linked calibration target has no household support "
                "after applying structural-zero controls"
            )

    max_abs_error = float("inf")
    for iteration in range(1, max_iterations + 1):
        for row, target in zip(contributions, targets, strict=True):
            if target == 0:
                continue
            current = float(row @ weights)
            if current <= 0:
                continue
            log_ratio = np.clip(np.log(target / current), -50.0, 50.0)
            exponent = row / max(float(np.max(row)), 1.0)
            weights *= np.exp(log_ratio * exponent)
        max_abs_error = float(np.max(np.abs(contributions @ weights - targets)))
        if max_abs_error <= tolerance:
            return weights, True, iteration, max_abs_error
    return weights, False, max_iterations, max_abs_error


def _linked_constraint_report(
    specs: Sequence[_ConstraintSpec],
    targets: np.ndarray,
    fitted: np.ndarray,
    *,
    converged: bool,
    iterations: int,
    max_abs_error: float,
    seed_records: int,
    include_issues: bool = True,
) -> dict[str, Any]:
    grouped: dict[
        tuple[str, str, tuple[str, ...]], list[tuple[_ConstraintSpec, float, float]]
    ] = defaultdict(list)
    for spec, target, actual in zip(specs, targets, fitted, strict=True):
        grouped[(spec.unit, spec.margin, spec.dimensions)].append(
            (spec, float(target), float(actual))
        )

    margins: list[dict[str, Any]] = []
    margin_summaries: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    for (unit, margin_name, dimensions), cells in grouped.items():
        cell_rows: list[dict[str, Any]] = []
        margin_max_abs_error = 0.0
        margin_max_relative_error = 0.0
        for spec, target, actual in cells:
            residual = actual - target
            abs_error = abs(residual)
            categories = dict(zip(dimensions, spec.categories, strict=True))
            margin_max_abs_error = max(margin_max_abs_error, abs_error)
            margin_max_relative_error = max(
                margin_max_relative_error,
                relative_error(abs_error, target),
            )
            cell_rows.append(
                {
                    "categories": categories,
                    "target": target,
                    "fitted": actual,
                    "residual": residual,
                }
            )
            if include_issues and not converged and abs_error > 0:
                issues.append(
                    {
                        "severity": "warning",
                        "kind": "cell_residual",
                        "unit": unit,
                        "margin": margin_name,
                        "categories": categories,
                        "message": f"Residual is {abs_error:.12g} for {categories}.",
                        "tip": (
                            "Review conflicting controls, sparse linked household "
                            "support, and category mappings."
                        ),
                        "abs_error": abs_error,
                    }
                )
        margins.append(
            {
                "unit": unit,
                "name": margin_name,
                "dimensions": list(dimensions),
                "cells": cell_rows,
            }
        )
        margin_summaries.append(
            {
                "unit": unit,
                "name": margin_name,
                "dimensions": list(dimensions),
                "cells": len(cell_rows),
                "target_total": sum(cell[1] for cell in cells),
                "fitted_total": sum(cell[2] for cell in cells),
                "max_abs_error": margin_max_abs_error,
                "max_relative_error": margin_max_relative_error,
            }
        )
    return {
        "calibration_mode": "household_and_person",
        "converged": converged,
        "iterations": iterations,
        "max_abs_error": max_abs_error,
        "seed_records": seed_records,
        "issues": sorted(issues, key=lambda issue: issue["abs_error"], reverse=True),
        "suggested_next_steps": (
            [
                "Inspect the largest household and person residuals; linked "
                "controls may conflict or have too little household support."
            ]
            if issues
            else []
        ),
        "margin_summaries": margin_summaries,
        "margins": margins,
    }


def realize_linked_geography_population(
    households: Sequence[HouseholdRow],
    persons: Sequence[PersonRow],
    *,
    weights_by_geography: dict[str, list[float]],
    geography_column: str,
    household_id_column: str = "synthetic_household_id",
    person_id_column: str = "synthetic_person_id",
) -> tuple[list[HouseholdRow], list[PersonRow]]:
    """Integerize geography weights and copy linked persons into households.

    This is the in-memory form of the realization step. It shares its expansion
    logic with :func:`_write_realized_population_to_csv`; use that function when
    streaming to disk for large runs.
    """

    realized = _expand_realized_population(
        households,
        persons,
        weights_by_geography=weights_by_geography,
        geography_column=geography_column,
        household_id_column=household_id_column,
        person_id_column=person_id_column,
    )
    household_rows = _frame_to_string_rows(realized.household_frame)
    person_rows = (
        _frame_to_string_rows(realized.person_frame)
        if realized.person_frame is not None
        else []
    )
    return household_rows, person_rows


def calibrate_linked_household_csvs(
    *,
    households_path: Path,
    persons_path: Path,
    controls_path: Path,
    person_controls_path: Path | None = None,
    geography_dimension: str,
    geography_column: str,
    households_out: Path,
    persons_out: Path,
    weights_out: Path | None = None,
    report_out: Path | None = None,
    household_id_column: str = "synthetic_household_id",
    person_id_column: str = "synthetic_person_id",
    weight_field: str | None = None,
    max_iterations: int = 100,
    tolerance: float = 1e-6,
    pool_size: int | None = None,
    n_workers: int | None = None,
) -> dict[str, Any]:
    """Calibrate linked household/person CSVs to geography controls.

    Parameters
    ----------
    pool_size:
        Maximum number of candidate households to use.  When ``None`` the full
        pool is used.  Values of 5 000–10 000 reproduce aggregate statistics
        (ownership rates, household-size distributions) with near-identical
        accuracy to the full pool while cutting synthesis time by 10× or more.
        Use the full pool only when individual-household uniqueness matters.
    n_workers:
        Number of threads for parallel geography fitting.  Defaults to
        ``min(os.cpu_count(), 8)`` when ``None``.
    """

    # Read independent inputs concurrently; CSV parsing and control loading are
    # I/O-bound at this stage.
    with ThreadPoolExecutor(max_workers=4) as _io_ex:
        _hh_f = _io_ex.submit(_read_csv_rows, households_path)
        _p_f = _io_ex.submit(_read_csv_rows, persons_path)
        _ctrl_f = _io_ex.submit(read_control_table, controls_path)
        _person_ctrl_f = (
            _io_ex.submit(read_control_table, person_controls_path)
            if person_controls_path is not None
            else None
        )
        households = _hh_f.result()
        persons = _p_f.result()
        controls = _ctrl_f.result()
        person_controls = (
            _person_ctrl_f.result() if _person_ctrl_f is not None else None
        )

    if not households:
        raise ValueError(f"candidate household CSV has no data rows: {households_path}")

    if pool_size is not None and pool_size < len(households):
        households, persons = _subsample_candidates(
            households,
            persons,
            pool_size,
            household_id_column=household_id_column,
        )

    household_input_report = check_small_area_calibration_inputs(
        households,
        controls,
        geography_dimension=geography_dimension,
    )
    if not household_input_report["passed"]:
        raise ValueError(_format_preflight_error(household_input_report))
    person_input_report: dict[str, Any] | None = None
    if person_controls is not None:
        person_input_report = check_linked_person_calibration_inputs(
            households,
            persons,
            person_controls,
            geography_dimension=geography_dimension,
            household_id_column=household_id_column,
        )
        if not person_input_report["passed"]:
            raise ValueError(_format_preflight_error(person_input_report))
        fit = fit_linked_by_geography(
            households,
            persons,
            controls,
            person_controls,
            geography_dimension=geography_dimension,
            household_id_column=household_id_column,
            weight_field=weight_field,
            max_iterations=max_iterations,
            tolerance=tolerance,
            n_workers=n_workers,
        )
    else:
        fit = fit_households_by_geography(
            households,
            controls,
            geography_dimension=geography_dimension,
            household_id_column=household_id_column,
            weight_field=weight_field,
            max_iterations=max_iterations,
            tolerance=tolerance,
            n_workers=n_workers,
        )
    realization = _write_realized_population_to_csv(
        households_out,
        persons_out,
        households,
        persons,
        weights_by_geography=fit.weights_by_geography,
        geography_column=geography_column,
        household_id_column=household_id_column,
        person_id_column=person_id_column,
    )

    if weights_out:
        _write_weights_csv(
            weights_out,
            households,
            fit.weights_by_geography,
            household_id_column=household_id_column,
            integer_weights_by_geography=realization["integer_weights"],
        )

    summary = _small_area_report(
        households=households,
        persons=persons,
        assigned_household_count=realization["assigned_households"],
        assigned_person_count=realization["assigned_persons"],
        assigned_households_by_geography=realization["geographies"],
        fit=fit,
        geography_dimension=geography_dimension,
        geography_column=geography_column,
        household_input_report=household_input_report,
        person_input_report=person_input_report,
    )
    if report_out:
        report_out.parent.mkdir(parents=True, exist_ok=True)
        report_out.write_text(json.dumps(summary, indent=2, sort_keys=True))
    return summary


def _format_preflight_error(report: dict[str, Any]) -> str:
    issues = report.get("issues", [])
    if not isinstance(issues, list) or not issues:
        return "small-area calibration inputs did not pass preflight checks"
    first = issues[0]
    if not isinstance(first, dict):
        return "small-area calibration inputs did not pass preflight checks"
    message = str(first.get("message", "small-area calibration input mismatch"))
    tip = str(first.get("tip", "")).strip()
    if tip:
        return f"{message} {tip}"
    return message


def _control_dimensions(margins: Sequence[ControlMargin]) -> tuple[str, ...]:
    seen: list[str] = []
    for margin in margins:
        for dimension in margin.dimensions:
            if dimension not in seen:
                seen.append(dimension)
    return tuple(seen)


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _write_csv_rows(path: Path, rows: Sequence[dict[str, str]]) -> None:
    if not rows:
        raise ValueError(f"no rows to write to {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = _ordered_fieldnames(rows)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _subsample_candidates(
    households: list[HouseholdRow],
    persons: list[PersonRow],
    pool_size: int,
    *,
    household_id_column: str,
    seed: int = 42,
) -> tuple[list[HouseholdRow], list[PersonRow]]:
    """Return a random subsample of the candidate pool with consistent persons."""
    rng = np.random.default_rng(seed)
    indices = rng.choice(len(households), size=pool_size, replace=False)
    selected_hh = [households[int(i)] for i in indices]
    selected_ids = {hh[household_id_column] for hh in selected_hh}
    selected_persons = [
        p for p in persons if p.get(household_id_column, "") in selected_ids
    ]
    return selected_hh, selected_persons


@dataclass(frozen=True)
class _RealizedPopulation:
    """Expanded household/person frames plus realization metadata."""

    household_frame: pd.DataFrame
    person_frame: pd.DataFrame | None
    integer_weights: dict[str, list[int]]
    assigned_by_geography: dict[str, int]
    assigned_households: int
    assigned_persons: int


def _expand_realized_population(
    households: Sequence[HouseholdRow],
    persons: Sequence[PersonRow],
    *,
    weights_by_geography: dict[str, list[float]],
    geography_column: str,
    household_id_column: str,
    person_id_column: str,
) -> _RealizedPopulation:
    """Integerize geography weights and expand candidates into assigned frames.

    This is the single realization implementation shared by the in-memory
    :func:`realize_linked_geography_population` and the streaming
    :func:`_write_realized_population_to_csv`. It assigns each integerized
    household copy a ``{geography}-{n}`` identifier and fans linked persons out
    into every household copy, inheriting the assigned geography.
    """

    if not households:
        raise ValueError("at least one candidate household row is required")
    if not weights_by_geography:
        raise ValueError("at least one target geography is required")

    # --- Build expand index across all geographies ---
    # Integerize once per geography; the caller reuses the result for the
    # weights CSV without re-calling integerize_weights.
    integer_weights: dict[str, list[int]] = {}
    idx_parts: list[np.ndarray] = []
    geo_parts: list[np.ndarray] = []
    for geography in sorted(weights_by_geography):
        weights = weights_by_geography[geography]
        if len(weights) != len(households):
            raise ValueError(
                f"weights for geography {geography!r} do not match household rows"
            )
        int_w = integerize_weights(weights)
        integer_weights[geography] = int_w
        counts = np.array(int_w, dtype=np.int32)
        nonzero = np.where(counts > 0)[0]
        repeated = np.repeat(nonzero, counts[nonzero])
        idx_parts.append(repeated)
        geo_parts.append(np.full(len(repeated), geography, dtype=object))

    all_idxs = np.concatenate(idx_parts)  # (total_households,)
    all_geos = np.concatenate(geo_parts)  # (total_households,)
    n_hh = len(all_idxs)

    # --- Expand households ---
    df_hh = pd.DataFrame(households)
    df_hh_exp = df_hh.iloc[all_idxs].reset_index(drop=True)
    df_hh_exp["source_candidate_household_id"] = df_hh_exp[household_id_column].values
    df_hh_exp[geography_column] = all_geos

    # Build sequential IDs with numpy string ops — 2× faster than a Python
    # f-string loop over millions of rows.
    seq = np.arange(1, n_hh + 1, dtype=np.int64)
    sep = np.full(n_hh, "-", dtype="U1")
    new_hh_ids = np.char.add(np.char.add(all_geos.astype("U"), sep), seq.astype("U"))
    df_hh_exp[household_id_column] = new_hh_ids
    df_hh_exp["_new_hh_id"] = new_hh_ids
    df_hh_exp["_cand_idx"] = all_idxs

    hh_extra = [
        c
        for c in [geography_column, "source_candidate_household_id"]
        if c not in df_hh.columns
    ]
    hh_cols = list(df_hh.columns) + hh_extra
    household_frame = df_hh_exp[hh_cols]

    # --- Expand persons ---
    person_frame: pd.DataFrame | None = None
    n_p = 0
    if persons:
        df_p = pd.DataFrame(persons)
        df_hh_idx = df_hh[[household_id_column]].copy()
        df_hh_idx["_cand_idx"] = np.arange(len(df_hh), dtype=np.int32)
        df_p_idx = df_p.merge(df_hh_idx, on=household_id_column, how="left")

        df_p_exp = df_p_idx.merge(
            df_hh_exp[["_cand_idx", "_new_hh_id", geography_column]],
            on="_cand_idx",
            how="inner",
        )
        df_p_exp["source_candidate_person_id"] = df_p_exp[person_id_column]
        df_p_exp[household_id_column] = df_p_exp["_new_hh_id"]
        geo_col = (
            f"{geography_column}_y"
            if f"{geography_column}_x" in df_p_exp.columns
            else geography_column
        )
        df_p_exp[geography_column] = df_p_exp[geo_col]
        n_p = len(df_p_exp)
        seq_p = np.arange(1, n_p + 1, dtype=np.int64)
        sep_p = np.full(n_p, "-", dtype="U1")
        df_p_exp[person_id_column] = np.char.add(
            np.char.add(df_p_exp[geography_column].values.astype("U"), sep_p),
            seq_p.astype("U"),
        )

        p_extra = [
            c
            for c in [geography_column, "source_candidate_person_id"]
            if c not in df_p.columns
        ]
        p_cols = [c for c in list(df_p.columns) + p_extra if c in df_p_exp.columns]
        person_frame = pd.DataFrame(df_p_exp[p_cols])

    assigned_by_geography = df_hh_exp[geography_column].value_counts().to_dict()

    return _RealizedPopulation(
        household_frame=household_frame,
        person_frame=person_frame,
        integer_weights=integer_weights,
        assigned_by_geography=assigned_by_geography,
        assigned_households=n_hh,
        assigned_persons=n_p,
    )


def _frame_to_string_rows(frame: pd.DataFrame) -> list[dict[str, str]]:
    """Convert a realized frame to list-of-dict rows with string values."""

    return [
        {str(column): str(value) for column, value in record.items()}
        for record in frame.fillna("").to_dict("records")
    ]


def _write_realized_population_to_csv(
    households_path: Path,
    persons_path: Path,
    households: Sequence[HouseholdRow],
    persons: Sequence[PersonRow],
    *,
    weights_by_geography: dict[str, list[float]],
    geography_column: str,
    household_id_column: str,
    person_id_column: str,
) -> dict[str, Any]:
    realized = _expand_realized_population(
        households,
        persons,
        weights_by_geography=weights_by_geography,
        geography_column=geography_column,
        household_id_column=household_id_column,
        person_id_column=person_id_column,
    )

    households_path.parent.mkdir(parents=True, exist_ok=True)
    realized.household_frame.to_csv(households_path, index=False)

    persons_path.parent.mkdir(parents=True, exist_ok=True)
    if realized.person_frame is not None:
        realized.person_frame.to_csv(persons_path, index=False)
    else:
        persons_path.write_text("")

    return {
        "assigned_households": realized.assigned_households,
        "assigned_persons": realized.assigned_persons,
        "geographies": realized.assigned_by_geography,
        "integer_weights": realized.integer_weights,
    }


def _write_weights_csv(
    path: Path,
    households: Sequence[HouseholdRow],
    weights_by_geography: dict[str, list[float]],
    *,
    household_id_column: str,
    integer_weights_by_geography: dict[str, list[int]] | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=(
                "target_geography",
                "source_candidate_household_id",
                "weight",
                "integer_weight",
            ),
        )
        writer.writeheader()
        for geography in sorted(weights_by_geography):
            weights = weights_by_geography[geography]
            if integer_weights_by_geography is not None:
                integer_weights = integer_weights_by_geography[geography]
            else:
                integer_weights = integerize_weights(weights)
            for household, weight, integer_weight in zip(
                households,
                weights,
                integer_weights,
                strict=True,
            ):
                writer.writerow(
                    {
                        "target_geography": geography,
                        "source_candidate_household_id": household[household_id_column],
                        "weight": format_csv_number(weight),
                        "integer_weight": integer_weight,
                    }
                )


def _small_area_report(
    *,
    households: Sequence[HouseholdRow],
    persons: Sequence[PersonRow],
    assigned_household_count: int,
    assigned_person_count: int,
    assigned_households_by_geography: dict[str, int],
    fit: GeographyHouseholdFit,
    geography_dimension: str,
    geography_column: str,
    household_input_report: dict[str, Any],
    person_input_report: dict[str, Any] | None,
) -> dict[str, Any]:
    non_converged = sorted(
        geography
        for geography, report in fit.reports.items()
        if not report["converged"]
    )
    all_errors = [report["max_abs_error"] for report in fit.reports.values()]
    realized_errors = [
        float(realized.get("max_abs_error", 0.0))
        for report in fit.reports.values()
        if isinstance((realized := report.get("realized")), dict)
    ]
    largest_residuals = _largest_small_area_residuals(fit.reports)
    realized_max_abs_error = max(realized_errors) if realized_errors else None
    calibration_mode = (
        "household_and_person" if person_input_report is not None else "household_only"
    )
    return {
        "schema_version": (
            "synthpopcan-small-area-linked-calibration-v2"
            if person_input_report is not None
            else "synthpopcan-small-area-linked-calibration-v1"
        ),
        "calibration_mode": calibration_mode,
        "geography_dimension": geography_dimension,
        "geography_column": geography_column,
        "candidate_households": len(households),
        "candidate_persons": len(persons),
        "assigned_households": assigned_household_count,
        "assigned_persons": assigned_person_count,
        "summary": {
            "total_geographies": len(fit.reports),
            "converged_count": len(fit.reports) - len(non_converged),
            "non_converged_count": len(non_converged),
            "max_abs_error": max(all_errors) if all_errors else 0.0,
            "non_converged_geographies": non_converged,
            "largest_residuals": largest_residuals,
            "realized_max_abs_error": realized_max_abs_error,
        },
        "suggested_next_steps": _suggest_small_area_next_steps(
            non_converged=non_converged,
            largest_residuals=largest_residuals,
            realized_max_abs_error=realized_max_abs_error,
        ),
        "input_checks": {
            "household": household_input_report,
            "person": person_input_report,
        },
        "geographies": {
            geography: {
                "converged": report["converged"],
                "iterations": report["iterations"],
                "max_abs_error": report["max_abs_error"],
                "assigned_households": assigned_households_by_geography.get(
                    geography,
                    0,
                ),
                "margin_summaries": report["margin_summaries"],
                "realized_margin_summaries": (
                    report.get("realized", {}).get("margin_summaries", [])
                    if isinstance(report.get("realized"), dict)
                    else []
                ),
            }
            for geography, report in sorted(fit.reports.items())
        },
    }


def _largest_small_area_residuals(
    reports: dict[str, dict[str, Any]],
    *,
    limit: int = 10,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for geography, report in reports.items():
        for margin in report.get("margins", []):
            margin_name = str(margin.get("name", ""))
            dimensions = list(margin.get("dimensions", []))
            for cell in margin.get("cells", []):
                residual = float(cell.get("residual", 0.0))
                abs_error = abs(residual)
                if abs_error <= 1e-9:
                    continue
                target = float(cell.get("target", 0.0))
                row = {
                    "geography": geography,
                    "margin": margin_name,
                    "dimensions": dimensions,
                    "categories": dict(cell.get("categories", {})),
                    "target": target,
                    "fitted": float(cell.get("fitted", 0.0)),
                    "residual": residual,
                    "abs_error": abs_error,
                    "relative_error": relative_error(abs_error, target),
                }
                if margin.get("unit"):
                    row["unit"] = str(margin["unit"])
                rows.append(row)
    return sorted(
        rows,
        key=lambda row: (
            -float(row["abs_error"]),
            str(row["geography"]),
            str(row["margin"]),
            tuple(row["categories"].items()),
        ),
    )[:limit]


def _suggest_small_area_next_steps(
    *,
    non_converged: Sequence[str],
    largest_residuals: Sequence[dict[str, Any]],
    realized_max_abs_error: float | None = None,
) -> list[str]:
    steps: list[str] = []
    if largest_residuals:
        steps.append(
            "Review the largest residual rows first; they identify the geography, "
            "margin, and category that the calibration could not satisfy."
        )
    if non_converged:
        steps.append(
            "For non-converged geographies, check whether controls conflict, "
            "categories were mapped consistently, or the candidate pool lacks "
            "enough matching households."
        )
    if realized_max_abs_error is not None and realized_max_abs_error > 1e-9:
        steps.append(
            "Review the realized margin summaries: integer household selection "
            "introduced residuals after the fractional household/person fit."
        )
    return steps


def _ordered_fieldnames(rows: Sequence[dict[str, str]]) -> list[str]:
    fieldnames: list[str] = []
    for row in rows:
        for fieldname in row:
            if fieldname not in fieldnames:
                fieldnames.append(fieldname)
    return fieldnames
