"""Tree-based synthetic population generator contracts."""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

TreeLevel = Literal["household", "person"]


@dataclass(frozen=True)
class TreeTrainingSample:
    level: TreeLevel
    source_format: str
    records: tuple[dict[str, str], ...]
    columns: tuple[str, ...]
    target_columns: tuple[str, ...]
    conditioning_columns: tuple[str, ...]
    geography_column: str | None = None
    weight_column: str | None = None
    metadata: dict[str, object] = field(default_factory=dict)

    def as_summary(self) -> dict[str, object]:
        summary = {
            "level": self.level,
            "source_format": self.source_format,
            "records": len(self.records),
            "columns": list(self.columns),
            "target_columns": list(self.target_columns),
            "conditioning_columns": list(self.conditioning_columns),
            "geography_column": self.geography_column,
            "weight_column": self.weight_column,
        }
        summary.update(self.metadata)
        return summary


@dataclass(frozen=True)
class TreeModelSpec:
    level: TreeLevel
    target_columns: tuple[str, ...]
    conditioning_columns: tuple[str, ...]
    geography_column: str | None = None
    weight_column: str | None = None
    random_seed: int = 0
    model_family: str = "tree-based"

    def __post_init__(self) -> None:
        validate_tree_roles(
            target_columns=self.target_columns,
            conditioning_columns=self.conditioning_columns,
        )

    def as_summary(self) -> dict[str, object]:
        return {
            "level": self.level,
            "model_family": self.model_family,
            "target_columns": list(self.target_columns),
            "conditioning_columns": list(self.conditioning_columns),
            "geography_column": self.geography_column,
            "weight_column": self.weight_column,
            "random_seed": self.random_seed,
        }


@dataclass(frozen=True)
class TreeGenerationRequest:
    model_spec: TreeModelSpec
    rows: int
    geography_values: tuple[str, ...] = ()
    random_seed: int | None = None

    def __post_init__(self) -> None:
        if self.rows <= 0:
            raise ValueError("rows must be greater than zero")


def read_tree_training_sample(
    path: Path,
    *,
    level: TreeLevel,
    target_columns: tuple[str, ...],
    conditioning_columns: tuple[str, ...],
    geography_column: str | None = None,
    weight_column: str | None = None,
) -> TreeTrainingSample:
    with path.open(newline="") as handle:
        reader = csv.DictReader(handle)
        records = tuple(dict(row) for row in reader)
        columns = tuple(reader.fieldnames or ())

    validate_tree_roles(
        target_columns=target_columns,
        conditioning_columns=conditioning_columns,
    )
    validate_columns(
        columns,
        required=tuple(
            column
            for column in (
                *target_columns,
                *conditioning_columns,
                geography_column,
                weight_column,
            )
            if column
        ),
    )
    return TreeTrainingSample(
        level=level,
        source_format="csv-v1",
        records=records,
        columns=columns,
        target_columns=target_columns,
        conditioning_columns=conditioning_columns,
        geography_column=geography_column,
        weight_column=weight_column,
    )


def validate_tree_roles(
    *,
    target_columns: tuple[str, ...],
    conditioning_columns: tuple[str, ...],
) -> None:
    if not target_columns:
        raise ValueError("at least one target column is required")
    if not conditioning_columns:
        raise ValueError("at least one conditioning column is required")

    overlap = sorted(set(target_columns) & set(conditioning_columns))
    if overlap:
        raise ValueError(
            f"target and conditioning columns must not overlap: {', '.join(overlap)}"
        )


def validate_columns(columns: tuple[str, ...], *, required: tuple[str, ...]) -> None:
    missing = [column for column in required if column not in columns]
    if missing:
        raise ValueError(f"missing required columns: {', '.join(missing)}")
