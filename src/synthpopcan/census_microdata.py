"""Census microdata seed sample contracts and adapters."""

from __future__ import annotations

import csv
from dataclasses import dataclass
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

    def as_summary(self) -> dict[str, object]:
        return {
            "level": self.level,
            "source_format": self.source_format,
            "records": len(self.records),
            "columns": list(self.columns),
            "weight_column": self.weight_column,
            "geography_columns": list(self.geography_columns),
            "id_columns": list(self.id_columns),
        }


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


def validate_columns(columns: tuple[str, ...], *, required: tuple[str, ...]) -> None:
    missing = [column for column in required if column not in columns]
    if missing:
        raise ValueError(f"missing required columns: {', '.join(missing)}")
