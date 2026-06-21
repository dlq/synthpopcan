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


def validate_columns(columns: tuple[str, ...], *, required: tuple[str, ...]) -> None:
    missing = [column for column in required if column not in columns]
    if missing:
        raise ValueError(f"missing required columns: {', '.join(missing)}")
