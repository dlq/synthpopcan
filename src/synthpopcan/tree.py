"""Tree-based synthetic population generator contracts."""

from __future__ import annotations

import csv
import json
import random
from collections import defaultdict
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


@dataclass(frozen=True)
class FrequencyOutcome:
    values: dict[str, str]
    weight: float

    def to_dict(self) -> dict[str, object]:
        return {"values": self.values, "weight": self.weight}


@dataclass(frozen=True)
class FrequencyGroup:
    conditions: dict[str, str]
    support: float
    outcomes: tuple[FrequencyOutcome, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "conditions": self.conditions,
            "support": self.support,
            "outcomes": [outcome.to_dict() for outcome in self.outcomes],
        }


@dataclass(frozen=True)
class FrequencyTreeModel:
    spec: TreeModelSpec
    groups: tuple[FrequencyGroup, ...]
    global_outcomes: tuple[FrequencyOutcome, ...]
    source_format: str
    records_trained: int
    release_class: str = "private_working"
    min_support_threshold: int = 5
    model_type: str = "conditional-frequency"

    def to_dict(self) -> dict[str, object]:
        minimum_support = min((group.support for group in self.groups), default=0.0)
        groups_below_threshold = sum(
            1 for group in self.groups if group.support < self.min_support_threshold
        )
        return {
            "schema_version": "synthpopcan-tree-model-v1",
            "model_type": self.model_type,
            "release_class": self.release_class,
            "spec": self.spec.as_summary(),
            "source_format": self.source_format,
            "records_trained": self.records_trained,
            "groups": [group.to_dict() for group in self.groups],
            "global_outcomes": [outcome.to_dict() for outcome in self.global_outcomes],
            "privacy": {
                "contains_raw_rows": False,
                "contains_source_identifiers": False,
                "minimum_support": minimum_support,
                "min_support_threshold": self.min_support_threshold,
                "groups_below_threshold": groups_below_threshold,
                "publishable": False,
            },
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> FrequencyTreeModel:
        if payload.get("schema_version") != "synthpopcan-tree-model-v1":
            raise ValueError("unsupported tree model schema")
        if payload.get("model_type") != "conditional-frequency":
            raise ValueError("unsupported tree model type")
        spec_payload = payload["spec"]
        if not isinstance(spec_payload, dict):
            raise ValueError("tree model spec must be an object")
        spec = TreeModelSpec(
            level=spec_payload["level"],  # type: ignore[arg-type]
            target_columns=tuple(spec_payload["target_columns"]),  # type: ignore[arg-type]
            conditioning_columns=tuple(spec_payload["conditioning_columns"]),  # type: ignore[arg-type]
            geography_column=spec_payload.get("geography_column"),  # type: ignore[arg-type]
            weight_column=spec_payload.get("weight_column"),  # type: ignore[arg-type]
            random_seed=int(spec_payload.get("random_seed", 0)),
            model_family=str(spec_payload.get("model_family", "tree-based")),
        )
        return cls(
            spec=spec,
            groups=tuple(
                FrequencyGroup(
                    conditions=dict(group["conditions"]),  # type: ignore[index]
                    support=float(group["support"]),  # type: ignore[index]
                    outcomes=tuple(
                        FrequencyOutcome(
                            values=dict(outcome["values"]),  # type: ignore[index]
                            weight=float(outcome["weight"]),  # type: ignore[index]
                        )
                        for outcome in group["outcomes"]  # type: ignore[index]
                    ),
                )
                for group in payload["groups"]  # type: ignore[index]
            ),
            global_outcomes=tuple(
                FrequencyOutcome(
                    values=dict(outcome["values"]),  # type: ignore[index]
                    weight=float(outcome["weight"]),  # type: ignore[index]
                )
                for outcome in payload["global_outcomes"]  # type: ignore[index]
            ),
            source_format=str(payload["source_format"]),
            records_trained=int(payload["records_trained"]),
            release_class=str(payload.get("release_class", "private_working")),
            min_support_threshold=int(
                payload.get("privacy", {}).get("min_support_threshold", 5)  # type: ignore[union-attr]
            ),
        )


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


def train_frequency_model(
    sample: TreeTrainingSample,
    *,
    random_seed: int = 0,
    min_support: int = 5,
) -> FrequencyTreeModel:
    grouped: dict[tuple[str, ...], dict[tuple[str, ...], float]] = defaultdict(
        lambda: defaultdict(float)
    )
    global_counts: dict[tuple[str, ...], float] = defaultdict(float)

    for row_number, record in enumerate(sample.records, start=2):
        weight = read_record_weight(record, sample.weight_column, row_number)
        condition_key = tuple(record[column] for column in sample.conditioning_columns)
        target_key = tuple(record[column] for column in sample.target_columns)
        grouped[condition_key][target_key] += weight
        global_counts[target_key] += weight

    groups = tuple(
        FrequencyGroup(
            conditions=dict(
                zip(sample.conditioning_columns, condition_key, strict=True)
            ),
            support=sum(outcome_counts.values()),
            outcomes=frequency_outcomes(sample.target_columns, outcome_counts),
        )
        for condition_key, outcome_counts in sorted(grouped.items())
    )
    return FrequencyTreeModel(
        spec=TreeModelSpec(
            level=sample.level,
            target_columns=sample.target_columns,
            conditioning_columns=sample.conditioning_columns,
            geography_column=sample.geography_column,
            weight_column=sample.weight_column,
            random_seed=random_seed,
        ),
        groups=groups,
        global_outcomes=frequency_outcomes(sample.target_columns, global_counts),
        source_format=sample.source_format,
        records_trained=len(sample.records),
        min_support_threshold=min_support,
    )


def generate_frequency_rows(
    model: FrequencyTreeModel,
    *,
    rows: int,
    conditions: dict[str, str] | None = None,
    random_seed: int | None = None,
) -> list[dict[str, str]]:
    if rows <= 0:
        raise ValueError("rows must be greater than zero")
    rng = random.Random(model.spec.random_seed if random_seed is None else random_seed)
    requested_conditions = conditions or {}
    generated_rows: list[dict[str, str]] = []
    for index in range(1, rows + 1):
        group = choose_group(model, requested_conditions, rng)
        outcome = choose_outcome(group.outcomes, rng)
        generated_rows.append(
            {
                "synthetic_id": str(index),
                **group.conditions,
                **outcome.values,
            }
        )
    return generated_rows


def write_frequency_model(path: Path, model: FrequencyTreeModel) -> None:
    path.write_text(json.dumps(model.to_dict(), indent=2, sort_keys=True) + "\n")


def read_frequency_model(path: Path) -> FrequencyTreeModel:
    try:
        payload = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path} is not valid JSON") from exc
    return FrequencyTreeModel.from_dict(payload)


def write_generated_rows(path: Path, rows: list[dict[str, str]]) -> None:
    if not rows:
        raise ValueError("cannot write empty generated output")
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=tuple(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def parse_conditions(values: tuple[str, ...]) -> dict[str, str]:
    conditions: dict[str, str] = {}
    for value in values:
        if "=" not in value:
            raise ValueError(f"condition {value!r} must use COLUMN=VALUE")
        column, condition_value = value.split("=", 1)
        if not column:
            raise ValueError(f"condition {value!r} must include a column name")
        conditions[column] = condition_value
    return conditions


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


def read_record_weight(
    record: dict[str, str], weight_column: str | None, row_number: int
) -> float:
    if weight_column is None:
        return 1.0
    try:
        return float(record[weight_column])
    except ValueError as exc:
        raise ValueError(f"row {row_number} has invalid weight") from exc


def frequency_outcomes(
    target_columns: tuple[str, ...],
    outcome_counts: dict[tuple[str, ...], float],
) -> tuple[FrequencyOutcome, ...]:
    return tuple(
        FrequencyOutcome(
            values=dict(zip(target_columns, target_key, strict=True)),
            weight=weight,
        )
        for target_key, weight in sorted(outcome_counts.items())
    )


def choose_group(
    model: FrequencyTreeModel,
    conditions: dict[str, str],
    rng: random.Random,
) -> FrequencyGroup:
    if conditions:
        missing = [
            column
            for column in conditions
            if column not in model.spec.conditioning_columns
        ]
        if missing:
            raise ValueError(f"unknown conditioning columns: {', '.join(missing)}")
        matches = [
            group
            for group in model.groups
            if all(
                group.conditions.get(column) == value
                for column, value in conditions.items()
            )
        ]
        if not matches:
            return FrequencyGroup(
                conditions={
                    column: conditions.get(column, "")
                    for column in model.spec.conditioning_columns
                },
                support=sum(outcome.weight for outcome in model.global_outcomes),
                outcomes=model.global_outcomes,
            )
        return weighted_choice(matches, [group.support for group in matches], rng)
    return weighted_choice(model.groups, [group.support for group in model.groups], rng)


def choose_outcome(
    outcomes: tuple[FrequencyOutcome, ...], rng: random.Random
) -> FrequencyOutcome:
    return weighted_choice(outcomes, [outcome.weight for outcome in outcomes], rng)


def weighted_choice(items, weights: list[float], rng: random.Random):
    total = sum(weights)
    if total <= 0:
        raise ValueError("cannot sample from non-positive weights")
    threshold = rng.uniform(0, total)
    cumulative = 0.0
    for item, weight in zip(items, weights, strict=True):
        cumulative += weight
        if threshold <= cumulative:
            return item
    return items[-1]
