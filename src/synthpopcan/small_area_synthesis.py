"""Small-area linked household/person synthesis helpers."""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from synthpopcan.controls import (
    ControlCell,
    ControlMargin,
    ControlTable,
    read_control_table,
)
from synthpopcan.diagnostics import build_ipf_fit_report
from synthpopcan.ipf import fit_ipf, integerize_weights

HouseholdRow = dict[str, str]
PersonRow = dict[str, str]


@dataclass(frozen=True)
class GeographyHouseholdFit:
    """Fitted candidate-household weights for each target geography."""

    weights_by_geography: dict[str, list[float]]
    reports: dict[str, dict[str, Any]]


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


def fit_households_by_geography(
    households: Sequence[HouseholdRow],
    controls: ControlTable,
    *,
    geography_dimension: str,
    household_id_column: str = "synthetic_household_id",
    weight_field: str | None = None,
    max_iterations: int = 100,
    tolerance: float = 1e-6,
) -> GeographyHouseholdFit:
    """Fit the same candidate household pool to each target geography."""

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

    weights_by_geography: dict[str, list[float]] = {}
    reports: dict[str, dict[str, Any]] = {}
    for geography, geography_controls in controls_for_geographies.items():
        result = fit_ipf(
            households,
            geography_controls.to_ipf_margins(),
            weight_field=weight_field,
            max_iterations=max_iterations,
            tolerance=tolerance,
        )
        weights_by_geography[geography] = result.weights
        reports[geography] = build_ipf_fit_report(geography_controls, result)

    return GeographyHouseholdFit(
        weights_by_geography=weights_by_geography,
        reports=reports,
    )


def realize_linked_geography_population(
    households: Sequence[HouseholdRow],
    persons: Sequence[PersonRow],
    *,
    weights_by_geography: dict[str, list[float]],
    geography_column: str,
    household_id_column: str = "synthetic_household_id",
    person_id_column: str = "synthetic_person_id",
) -> tuple[list[HouseholdRow], list[PersonRow]]:
    """Integerize geography weights and copy linked persons into households."""

    if not weights_by_geography:
        raise ValueError("at least one target geography is required")
    persons_by_household: dict[str, list[PersonRow]] = defaultdict(list)
    for person in persons:
        household_id = person.get(household_id_column, "")
        if household_id:
            persons_by_household[household_id].append(person)

    assigned_households: list[HouseholdRow] = []
    assigned_persons: list[PersonRow] = []
    next_household_number = 1
    next_person_number = 1
    for geography in sorted(weights_by_geography):
        weights = weights_by_geography[geography]
        if len(weights) != len(households):
            raise ValueError(
                f"weights for geography {geography!r} do not match household rows"
            )
        integer_weights = integerize_weights(weights)
        for candidate_index, repeats in enumerate(integer_weights):
            source_household = households[candidate_index]
            source_household_id = source_household[household_id_column]
            for _copy_index in range(repeats):
                assigned_household_id = f"{geography}-{next_household_number}"
                next_household_number += 1
                assigned_household = {
                    **source_household,
                    household_id_column: assigned_household_id,
                    geography_column: geography,
                    "source_candidate_household_id": source_household_id,
                }
                assigned_households.append(assigned_household)
                for source_person in persons_by_household.get(source_household_id, []):
                    assigned_person = {
                        **source_person,
                        person_id_column: f"{geography}-{next_person_number}",
                        household_id_column: assigned_household_id,
                        geography_column: geography,
                        "source_candidate_person_id": source_person.get(
                            person_id_column,
                            "",
                        ),
                    }
                    next_person_number += 1
                    assigned_persons.append(assigned_person)

    return assigned_households, assigned_persons


def calibrate_linked_household_csvs(
    *,
    households_path: Path,
    persons_path: Path,
    controls_path: Path,
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
) -> dict[str, Any]:
    """Calibrate linked household/person CSVs to geography controls."""

    households = _read_csv_rows(households_path)
    persons = _read_csv_rows(persons_path)
    controls = read_control_table(controls_path)
    fit = fit_households_by_geography(
        households,
        controls,
        geography_dimension=geography_dimension,
        household_id_column=household_id_column,
        weight_field=weight_field,
        max_iterations=max_iterations,
        tolerance=tolerance,
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
    )
    if report_out:
        report_out.parent.mkdir(parents=True, exist_ok=True)
        report_out.write_text(json.dumps(summary, indent=2, sort_keys=True))
    return summary


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
    if not households:
        raise ValueError("at least one candidate household row is required")
    persons_by_household: dict[str, list[PersonRow]] = defaultdict(list)
    for person in persons:
        household_id = person.get(household_id_column, "")
        if household_id:
            persons_by_household[household_id].append(person)

    household_fieldnames = _ordered_fieldnames(
        (
            *households,
            {
                household_id_column: "",
                geography_column: "",
                "source_candidate_household_id": "",
            },
        )
    )
    person_fieldnames = _ordered_fieldnames(
        (
            *persons,
            {
                person_id_column: "",
                household_id_column: "",
                geography_column: "",
                "source_candidate_person_id": "",
            },
        )
    )
    households_path.parent.mkdir(parents=True, exist_ok=True)
    persons_path.parent.mkdir(parents=True, exist_ok=True)

    assigned_households = 0
    assigned_persons = 0
    assigned_by_geography: dict[str, int] = defaultdict(int)
    next_household_number = 1
    next_person_number = 1
    with (
        households_path.open("w", newline="") as household_handle,
        persons_path.open("w", newline="") as person_handle,
    ):
        household_writer = csv.DictWriter(
            household_handle,
            fieldnames=household_fieldnames,
        )
        person_writer = csv.DictWriter(person_handle, fieldnames=person_fieldnames)
        household_writer.writeheader()
        person_writer.writeheader()
        for geography in sorted(weights_by_geography):
            weights = weights_by_geography[geography]
            if len(weights) != len(households):
                raise ValueError(
                    f"weights for geography {geography!r} do not match household rows"
                )
            integer_weights = integerize_weights(weights)
            for candidate_index, repeats in enumerate(integer_weights):
                if repeats == 0:
                    continue
                source_household = households[candidate_index]
                source_household_id = source_household[household_id_column]
                source_persons = persons_by_household.get(source_household_id, [])
                for _copy_index in range(repeats):
                    assigned_household_id = f"{geography}-{next_household_number}"
                    next_household_number += 1
                    household_writer.writerow(
                        {
                            **source_household,
                            household_id_column: assigned_household_id,
                            geography_column: geography,
                            "source_candidate_household_id": source_household_id,
                        }
                    )
                    assigned_households += 1
                    assigned_by_geography[geography] += 1
                    for source_person in source_persons:
                        person_writer.writerow(
                            {
                                **source_person,
                                person_id_column: f"{geography}-{next_person_number}",
                                household_id_column: assigned_household_id,
                                geography_column: geography,
                                "source_candidate_person_id": source_person.get(
                                    person_id_column,
                                    "",
                                ),
                            }
                        )
                        next_person_number += 1
                        assigned_persons += 1

    return {
        "assigned_households": assigned_households,
        "assigned_persons": assigned_persons,
        "geographies": dict(assigned_by_geography),
    }


def _write_weights_csv(
    path: Path,
    households: Sequence[HouseholdRow],
    weights_by_geography: dict[str, list[float]],
    *,
    household_id_column: str,
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
                        "weight": _format_float(weight),
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
) -> dict[str, Any]:
    return {
        "schema_version": "synthpopcan-small-area-linked-calibration-v1",
        "geography_dimension": geography_dimension,
        "geography_column": geography_column,
        "candidate_households": len(households),
        "candidate_persons": len(persons),
        "assigned_households": assigned_household_count,
        "assigned_persons": assigned_person_count,
        "geographies": {
            geography: {
                "converged": report["converged"],
                "iterations": report["iterations"],
                "max_abs_error": report["max_abs_error"],
                "assigned_households": assigned_households_by_geography.get(
                    geography,
                    0,
                ),
            }
            for geography, report in sorted(fit.reports.items())
        },
    }


def _ordered_fieldnames(rows: Sequence[dict[str, str]]) -> list[str]:
    fieldnames: list[str] = []
    for row in rows:
        for fieldname in row:
            if fieldname not in fieldnames:
                fieldnames.append(fieldname)
    return fieldnames


def _format_float(value: float) -> str:
    return str(int(value)) if value.is_integer() else f"{value:.12g}"
