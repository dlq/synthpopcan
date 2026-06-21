"""Census microdata seed sample contracts and adapters."""

from __future__ import annotations

import csv
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

SeedLevel = Literal["household", "person"]


@dataclass(frozen=True)
class SeedSample:
    level: SeedLevel
    source_format: str
    records: tuple[dict[str, str], ...]
    columns: tuple[str, ...]
    weight_column: str | None
    geography_columns: tuple[str, ...]
    id_columns: tuple[str, ...]
    metadata: dict[str, object] = field(default_factory=dict)

    def as_summary(self) -> dict[str, object]:
        summary = {
            "level": self.level,
            "source_format": self.source_format,
            "records": len(self.records),
            "columns": list(self.columns),
            "weight_column": self.weight_column,
            "geography_columns": list(self.geography_columns),
            "id_columns": list(self.id_columns),
        }
        summary.update(self.metadata)
        return summary


def read_fixture_seed_sample(
    path: Path,
    *,
    level: SeedLevel,
    weight_column: str | None,
    geography_columns: tuple[str, ...],
    id_columns: tuple[str, ...],
) -> SeedSample:
    with path.open(newline="") as handle:
        reader = csv.DictReader(handle)
        records = tuple(dict(row) for row in reader)
        columns = tuple(reader.fieldnames or ())

    validate_columns(
        columns,
        required=tuple(
            column
            for column in (*geography_columns, *id_columns, weight_column)
            if column
        ),
    )
    return SeedSample(
        level=level,
        source_format="fixture-v1",
        records=records,
        columns=columns,
        weight_column=weight_column,
        geography_columns=geography_columns,
        id_columns=id_columns,
    )


def read_statcan_2016_hierarchical_seed_sample(path: Path) -> SeedSample:
    with path.open(newline="") as handle:
        reader = csv.DictReader(handle)
        records = tuple(dict(row) for row in reader)
        columns = tuple(reader.fieldnames or ())

    validate_columns(columns, required=("HH_ID", "EF_ID", "CF_ID", "PP_ID", "WEIGHT"))
    household_ids = [record["HH_ID"] for record in records if record.get("HH_ID")]
    person_ids = [record["PP_ID"] for record in records if record.get("PP_ID")]
    household_count = len(set(household_ids))
    person_count = len(records)
    duplicate_person_ids = sum(
        count - 1 for count in Counter(person_ids).values() if count > 1
    )
    average_household_size = (
        round(person_count / household_count, 4) if household_count else 0
    )

    return SeedSample(
        level="person",
        source_format="statcan-2016-hierarchical",
        records=records,
        columns=columns,
        weight_column="WEIGHT",
        geography_columns=(),
        id_columns=("PP_ID",),
        metadata={
            "household_id_column": "HH_ID",
            "economic_family_id_column": "EF_ID",
            "census_family_id_column": "CF_ID",
            "person_id_column": "PP_ID",
            "households": household_count,
            "people": person_count,
            "average_household_size": average_household_size,
            "duplicate_person_ids": duplicate_person_ids,
        },
    )


def export_seed_rows(
    sample: SeedSample,
    *,
    columns: tuple[str, ...],
) -> tuple[list[dict[str, str]], dict[str, object]]:
    if not columns:
        raise ValueError("at least one seed column is required")
    validate_columns(sample.columns, required=columns)

    derived_columns = ("household_size",) if "household_size" in sample.columns else ()
    output_columns = unique_columns(
        (
            *sample.id_columns,
            *sample.geography_columns,
            *columns,
            *derived_columns,
            sample.weight_column,
        )
    )
    rows = [
        {column: record.get(column, "") for column in output_columns}
        for record in sample.records
    ]
    return rows, {
        "source_format": sample.source_format,
        "level": sample.level,
        "rows_read": len(sample.records),
        "rows_written": len(rows),
        "columns": list(output_columns),
        "selected_columns": list(columns),
        "id_columns": list(sample.id_columns),
        "geography_columns": list(sample.geography_columns),
        "weight_column": sample.weight_column,
    }


def export_training_rows(
    sample: SeedSample,
    *,
    level: SeedLevel,
    target_columns: tuple[str, ...],
    conditioning_columns: tuple[str, ...],
) -> tuple[list[dict[str, str]], dict[str, object]]:
    if sample.source_format != "statcan-2016-hierarchical":
        raise ValueError("training export requires statcan-2016-hierarchical")
    if not target_columns:
        raise ValueError("at least one target column is required")
    if not conditioning_columns:
        raise ValueError("at least one conditioning column is required")
    if level == "person":
        return export_statcan_2016_person_training_rows(
            sample,
            target_columns=target_columns,
            conditioning_columns=conditioning_columns,
        )
    return export_statcan_2016_household_training_rows(
        sample,
        target_columns=target_columns,
        conditioning_columns=conditioning_columns,
    )


def export_statcan_2016_person_training_rows(
    sample: SeedSample,
    *,
    target_columns: tuple[str, ...],
    conditioning_columns: tuple[str, ...],
) -> tuple[list[dict[str, str]], dict[str, object]]:
    validate_columns(sample.columns, required=("PP_ID", "HH_ID", "WEIGHT"))
    source_columns = tuple(
        column
        for column in (*conditioning_columns, *target_columns)
        if column != "household_size"
    )
    validate_columns(sample.columns, required=source_columns)

    household_sizes = household_size_lookup(sample.records)
    output_columns = unique_columns(
        ("PP_ID", "HH_ID", *conditioning_columns, *target_columns, "WEIGHT")
    )
    rows = [
        {
            column: training_value(
                record,
                column,
                household_sizes=household_sizes,
            )
            for column in output_columns
        }
        for record in sample.records
    ]
    return rows, training_export_summary(
        sample,
        level="person",
        rows_written=len(rows),
        output_columns=output_columns,
        target_columns=target_columns,
        conditioning_columns=conditioning_columns,
        id_columns=("PP_ID", "HH_ID"),
    )


def export_statcan_2016_household_training_rows(
    sample: SeedSample,
    *,
    target_columns: tuple[str, ...],
    conditioning_columns: tuple[str, ...],
) -> tuple[list[dict[str, str]], dict[str, object]]:
    selected_columns = unique_columns((*conditioning_columns, *target_columns))
    household_sample = derive_statcan_2016_household_seed_sample(
        sample,
        columns=tuple(
            column for column in selected_columns if column != "household_size"
        ),
    )
    output_columns = unique_columns(
        ("HH_ID", *conditioning_columns, *target_columns, "WEIGHT")
    )
    rows = [
        {column: record[column] for column in output_columns}
        for record in household_sample.records
    ]
    return rows, training_export_summary(
        sample,
        level="household",
        rows_written=len(rows),
        output_columns=output_columns,
        target_columns=target_columns,
        conditioning_columns=conditioning_columns,
        id_columns=("HH_ID",),
    )


def training_export_summary(
    sample: SeedSample,
    *,
    level: SeedLevel,
    rows_written: int,
    output_columns: tuple[str, ...],
    target_columns: tuple[str, ...],
    conditioning_columns: tuple[str, ...],
    id_columns: tuple[str, ...],
) -> dict[str, object]:
    return {
        "source_format": sample.source_format,
        "level": level,
        "rows_read": len(sample.records),
        "rows_written": rows_written,
        "columns": list(output_columns),
        "target_columns": list(target_columns),
        "conditioning_columns": list(conditioning_columns),
        "id_columns": list(id_columns),
        "weight_column": "WEIGHT",
    }


def derive_statcan_2016_household_seed_sample(
    sample: SeedSample,
    *,
    columns: tuple[str, ...],
) -> SeedSample:
    if sample.source_format != "statcan-2016-hierarchical":
        raise ValueError("household derivation requires statcan-2016-hierarchical")
    if not columns:
        raise ValueError("at least one household column is required")
    validate_columns(sample.columns, required=("HH_ID", "WEIGHT", *columns))

    records_by_household = group_records_by_household(sample.records)

    household_records: list[dict[str, str]] = []
    for household_id, records in records_by_household.items():
        household_record = {"HH_ID": household_id}
        for column in columns:
            household_record[column] = unique_household_value(
                records,
                column,
                household_id,
                "household column",
            )
        household_record["household_size"] = str(len(records))
        household_record["WEIGHT"] = unique_household_value(
            records,
            "WEIGHT",
            household_id,
            "household weight",
        )
        household_records.append(household_record)

    return SeedSample(
        level="household",
        source_format=sample.source_format,
        records=tuple(household_records),
        columns=("HH_ID", *columns, "household_size", "WEIGHT"),
        weight_column="WEIGHT",
        geography_columns=(),
        id_columns=("HH_ID",),
        metadata={
            "households": len(household_records),
            "people": len(sample.records),
            "derivation": "one row per HH_ID with constant selected household columns",
        },
    )


def check_statcan_2016_household_seed_columns(
    sample: SeedSample,
    *,
    columns: tuple[str, ...],
) -> dict[str, object]:
    if sample.source_format != "statcan-2016-hierarchical":
        raise ValueError("household seed checks require statcan-2016-hierarchical")
    if not columns:
        raise ValueError("at least one household column is required")
    validate_columns(sample.columns, required=("HH_ID", "WEIGHT", *columns))

    records_by_household = group_records_by_household(sample.records)
    checks = [
        household_column_check(records_by_household, column) for column in columns
    ]
    checks.append(household_column_check(records_by_household, "WEIGHT", role="weight"))
    checks.append(
        {
            "column": "household_size",
            "role": "derived",
            "status": "ok",
            "detail": "derived from row count per HH_ID",
            "problem_households": 0,
        }
    )

    return {
        "source_format": sample.source_format,
        "level": "household",
        "households": len(records_by_household),
        "people": len(sample.records),
        "passed": all(check["status"] == "ok" for check in checks),
        "checks": checks,
    }


def group_records_by_household(
    records: tuple[dict[str, str], ...],
) -> dict[str, list[dict[str, str]]]:
    records_by_household: dict[str, list[dict[str, str]]] = {}
    for record in records:
        household_id = record.get("HH_ID", "")
        if not household_id:
            raise ValueError("household derivation requires non-empty HH_ID values")
        records_by_household.setdefault(household_id, []).append(record)
    return records_by_household


def household_size_lookup(records: tuple[dict[str, str], ...]) -> dict[str, str]:
    return {
        household_id: str(len(household_records))
        for household_id, household_records in group_records_by_household(
            records
        ).items()
    }


def training_value(
    record: dict[str, str],
    column: str,
    *,
    household_sizes: dict[str, str],
) -> str:
    if column == "household_size":
        return household_sizes[record["HH_ID"]]
    return record[column]


def household_column_check(
    records_by_household: dict[str, list[dict[str, str]]],
    column: str,
    *,
    role: str = "selected household column",
) -> dict[str, object]:
    problem_households = sum(
        1
        for records in records_by_household.values()
        if len({record.get(column, "") for record in records}) != 1
    )
    status = "problem" if problem_households else "ok"
    if problem_households:
        detail = f"varies within {problem_households:,} "
        detail += "household" if problem_households == 1 else "households"
    else:
        detail = "constant within each HH_ID"
    return {
        "column": column,
        "role": role,
        "status": status,
        "detail": detail,
        "problem_households": problem_households,
    }


def unique_household_value(
    records: list[dict[str, str]],
    column: str,
    household_id: str,
    label: str,
) -> str:
    values = {record.get(column, "") for record in records}
    if len(values) != 1:
        raise ValueError(f"conflicting {label} {column!r} for HH_ID {household_id!r}")
    return next(iter(values))


def validate_columns(columns: tuple[str, ...], *, required: tuple[str, ...]) -> None:
    missing = [column for column in required if column not in columns]
    if missing:
        raise ValueError(f"missing required columns: {', '.join(missing)}")


def unique_columns(columns: tuple[str | None, ...]) -> tuple[str, ...]:
    output: list[str] = []
    for column in columns:
        if column and column not in output:
            output.append(column)
    return tuple(output)
