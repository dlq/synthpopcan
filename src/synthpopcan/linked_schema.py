"""Versioned contract for linked household/person population artifacts."""

from __future__ import annotations

__all__ = [
    "HOUSEHOLD_ID_COLUMN",
    "LINKED_POPULATION_SCHEMA_VERSION",
    "PERSON_ID_COLUMN",
    "adopt_linked_population_directory",
    "build_linked_population_contract",
    "read_linked_population_contract",
    "validate_linked_population_contract",
    "write_linked_population_contract",
]

import csv
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

LINKED_POPULATION_SCHEMA_VERSION = "synthpopcan-linked-population-v1"
HOUSEHOLD_ID_COLUMN = "synthetic_household_id"
PERSON_ID_COLUMN = "synthetic_person_id"


def adopt_linked_population_directory(
    directory: Path,
    *,
    geography_column: str | None = None,
    manifest_name: str = "manifest.json",
) -> dict[str, Any]:
    """Validate legacy paired CSVs and add a v1 descriptor without rewriting."""

    from synthpopcan.tree import validate_linked_population_files

    households_path = directory / "households.csv"
    persons_path = directory / "persons.csv"
    validation = validate_linked_population_files(
        households_path,
        persons_path,
        household_size_column=None,
    )
    if not validation["passed"]:
        issues = validation.get("issues", [])
        message = (
            str(issues[0].get("message"))
            if isinstance(issues, list) and issues and isinstance(issues[0], dict)
            else "linked household/person identifiers failed validation"
        )
        raise ValueError(f"cannot adopt legacy linked population: {message}")
    return write_linked_population_contract(
        directory / manifest_name,
        households_path,
        persons_path,
        geography_column=geography_column,
    )


def build_linked_population_contract(
    households_path: Path,
    persons_path: Path,
    *,
    geography_column: str | None = None,
) -> dict[str, Any]:
    """Describe two linked CSVs using the stable v1 artifact contract.

    Demographic and model-specific columns remain extensible. The contract
    freezes the two primary keys, the person-to-household foreign key, and the
    rule that an optional geography assignment lives on households and is
    inherited by their people.
    """

    household_columns, household_rows = _csv_shape(households_path)
    person_columns, person_rows = _csv_shape(persons_path)
    _require_columns(
        household_columns,
        (HOUSEHOLD_ID_COLUMN,),
        table="households",
    )
    _require_columns(
        person_columns,
        (PERSON_ID_COLUMN, HOUSEHOLD_ID_COLUMN),
        table="persons",
    )
    if geography_column is not None:
        _require_columns(
            household_columns,
            (geography_column,),
            table="households",
        )

    contract: dict[str, Any] = {
        "schema_version": LINKED_POPULATION_SCHEMA_VERSION,
        "format": "csv",
        "tables": {
            "households": {
                "path": households_path.name,
                "rows": household_rows,
                "columns": household_columns,
                "primary_key": HOUSEHOLD_ID_COLUMN,
            },
            "persons": {
                "path": persons_path.name,
                "rows": person_rows,
                "columns": person_columns,
                "primary_key": PERSON_ID_COLUMN,
            },
        },
        "relationships": [
            {
                "from_table": "persons",
                "from_column": HOUSEHOLD_ID_COLUMN,
                "to_table": "households",
                "to_column": HOUSEHOLD_ID_COLUMN,
                "cardinality": "many-to-one",
            }
        ],
        "geography": (
            {
                "household_column": geography_column,
                "person_assignment": "inherited-via-household",
            }
            if geography_column is not None
            else None
        ),
    }
    validate_linked_population_contract(contract)
    return contract


def validate_linked_population_contract(payload: Mapping[str, object]) -> None:
    """Reject an unsupported or structurally invalid linked contract."""

    if payload.get("schema_version") != LINKED_POPULATION_SCHEMA_VERSION:
        raise ValueError("unsupported linked population schema")
    if payload.get("format") != "csv":
        raise ValueError("linked population v1 requires CSV tables")

    tables = _mapping(payload.get("tables"), "tables")
    households = _mapping(tables.get("households"), "households table")
    persons = _mapping(tables.get("persons"), "persons table")
    _validate_table(
        households,
        table="households",
        primary_key=HOUSEHOLD_ID_COLUMN,
        required_columns=(HOUSEHOLD_ID_COLUMN,),
    )
    _validate_table(
        persons,
        table="persons",
        primary_key=PERSON_ID_COLUMN,
        required_columns=(PERSON_ID_COLUMN, HOUSEHOLD_ID_COLUMN),
    )

    relationships = payload.get("relationships")
    expected_relationship = {
        "from_table": "persons",
        "from_column": HOUSEHOLD_ID_COLUMN,
        "to_table": "households",
        "to_column": HOUSEHOLD_ID_COLUMN,
        "cardinality": "many-to-one",
    }
    if (
        not isinstance(relationships, list)
        or expected_relationship not in relationships
    ):
        raise ValueError("linked population contract is missing the household link")

    geography = payload.get("geography")
    if geography is not None:
        geography_mapping = _mapping(geography, "geography")
        household_column = geography_mapping.get("household_column")
        if not isinstance(household_column, str) or not household_column:
            raise ValueError("geography household_column must be a non-empty string")
        if household_column not in _columns(households, "households"):
            raise ValueError("geography column is missing from the household table")
        if geography_mapping.get("person_assignment") != "inherited-via-household":
            raise ValueError("unsupported linked population geography assignment")


def write_linked_population_contract(
    path: Path,
    households_path: Path,
    persons_path: Path,
    *,
    geography_column: str | None = None,
) -> dict[str, Any]:
    """Build and write a linked-population v1 manifest."""

    contract = build_linked_population_contract(
        households_path,
        persons_path,
        geography_column=geography_column,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(contract, indent=2, sort_keys=True) + "\n")
    return contract


def read_linked_population_contract(path: Path) -> dict[str, Any]:
    """Read and validate a linked-population v1 manifest."""

    try:
        payload = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path} is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("linked population manifest must be a JSON object")
    validate_linked_population_contract(payload)
    return payload


def _csv_shape(path: Path) -> tuple[list[str], int]:
    with path.open(newline="") as handle:
        reader = csv.reader(handle)
        try:
            columns = next(reader)
        except StopIteration as exc:
            raise ValueError(f"linked population CSV is empty: {path}") from exc
        if not columns or any(not column for column in columns):
            raise ValueError(f"linked population CSV has an invalid header: {path}")
        if len(columns) != len(set(columns)):
            raise ValueError(f"linked population CSV has duplicate columns: {path}")
        rows = sum(1 for _ in reader)
    return columns, rows


def _require_columns(
    columns: list[str], required: tuple[str, ...], *, table: str
) -> None:
    missing = [column for column in required if column not in columns]
    if missing:
        raise ValueError(
            f"linked population {table} table is missing required columns: "
            + ", ".join(missing)
        )


def _mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError(f"linked population {label} must be an object")
    return value


def _columns(table: Mapping[str, object], label: str) -> list[str]:
    columns = table.get("columns")
    if not isinstance(columns, list) or not all(
        isinstance(column, str) and column for column in columns
    ):
        raise ValueError(f"linked population {label} columns must be strings")
    if len(columns) != len(set(columns)):
        raise ValueError(f"linked population {label} columns must be unique")
    return columns


def _validate_table(
    table_payload: Mapping[str, object],
    *,
    table: str,
    primary_key: str,
    required_columns: tuple[str, ...],
) -> None:
    path = table_payload.get("path")
    if not isinstance(path, str) or not path or Path(path).name != path:
        raise ValueError(f"linked population {table} path must be a filename")
    rows = table_payload.get("rows")
    if not isinstance(rows, int) or isinstance(rows, bool) or rows < 0:
        raise ValueError(f"linked population {table} rows must be non-negative")
    if table_payload.get("primary_key") != primary_key:
        raise ValueError(f"linked population {table} primary key is invalid")
    _require_columns(_columns(table_payload, table), required_columns, table=table)
