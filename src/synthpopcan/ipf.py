"""Iterative proportional fitting for seed records and margin tables."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

Record = Mapping[str, object]
CategoryKey = tuple[str, ...]


@dataclass(frozen=True)
class IPFMargin:
    dimensions: tuple[str, ...]
    targets: Mapping[CategoryKey, float]

    def __post_init__(self) -> None:
        if not self.dimensions:
            raise ValueError("margin dimensions must not be empty")
        for key, value in self.targets.items():
            if len(key) != len(self.dimensions):
                raise ValueError(
                    f"target key {key!r} does not match dimensions {self.dimensions!r}"
                )
            if value < 0:
                raise ValueError(f"target {key!r} must be non-negative")


@dataclass(frozen=True)
class IPFResult:
    records: Sequence[Record]
    weights: list[float]
    converged: bool
    iterations: int
    max_abs_error: float

    def margin_totals(self, dimensions: tuple[str, ...]) -> dict[CategoryKey, float]:
        totals: dict[CategoryKey, float] = {}
        for record, weight in zip(self.records, self.weights, strict=True):
            key = category_key(record, dimensions)
            totals[key] = totals.get(key, 0.0) + weight
        return totals


def fit_ipf(
    records: Sequence[Record],
    margins: Sequence[IPFMargin],
    *,
    weight_field: str | None = None,
    max_iterations: int = 100,
    tolerance: float = 1e-6,
) -> IPFResult:
    if not records:
        raise ValueError("IPF requires at least one seed record")
    if not margins:
        raise ValueError("IPF requires at least one margin")
    if max_iterations < 1:
        raise ValueError("max_iterations must be at least 1")
    if tolerance < 0:
        raise ValueError("tolerance must be non-negative")

    weights = initial_weights(records, weight_field)
    validate_margin_coverage(records, margins)

    max_abs_error = float("inf")
    for iteration in range(1, max_iterations + 1):
        for margin in margins:
            totals = weighted_totals(records, weights, margin.dimensions)
            for key, target in margin.targets.items():
                current = totals.get(key, 0.0)
                if current == 0.0:
                    if target == 0.0:
                        continue
                    raise ValueError(
                        f"margin {margin.dimensions!r} target {key!r} "
                        "has no seed records"
                    )
                ratio = target / current
                for index, record in enumerate(records):
                    if category_key(record, margin.dimensions) == key:
                        weights[index] *= ratio

        max_abs_error = calculate_max_abs_error(records, weights, margins)
        if max_abs_error <= tolerance:
            return IPFResult(records, weights, True, iteration, max_abs_error)

    return IPFResult(records, weights, False, max_iterations, max_abs_error)


def initial_weights(records: Sequence[Record], weight_field: str | None) -> list[float]:
    if weight_field is None:
        return [1.0 for _ in records]

    weights: list[float] = []
    for record in records:
        try:
            weight = float(record[weight_field])
        except KeyError as exc:
            raise ValueError(f"weight field {weight_field!r} is missing") from exc
        if weight < 0:
            raise ValueError("seed weights must be non-negative")
        weights.append(weight)
    return weights


def validate_margin_coverage(
    records: Sequence[Record], margins: Sequence[IPFMargin]
) -> None:
    for margin in margins:
        observed = {category_key(record, margin.dimensions) for record in records}
        for key, target in margin.targets.items():
            if target > 0 and key not in observed:
                raise ValueError(
                    f"margin {margin.dimensions!r} target {key!r} has no seed records"
                )


def weighted_totals(
    records: Sequence[Record],
    weights: Sequence[float],
    dimensions: tuple[str, ...],
) -> dict[CategoryKey, float]:
    totals: dict[CategoryKey, float] = {}
    for record, weight in zip(records, weights, strict=True):
        key = category_key(record, dimensions)
        totals[key] = totals.get(key, 0.0) + weight
    return totals


def calculate_max_abs_error(
    records: Sequence[Record],
    weights: Sequence[float],
    margins: Sequence[IPFMargin],
) -> float:
    max_abs_error = 0.0
    for margin in margins:
        totals = weighted_totals(records, weights, margin.dimensions)
        for key, target in margin.targets.items():
            max_abs_error = max(max_abs_error, abs(totals.get(key, 0.0) - target))
    return max_abs_error


def category_key(record: Record, dimensions: Iterable[str]) -> CategoryKey:
    key: list[str] = []
    for dimension in dimensions:
        try:
            value = record[dimension]
        except KeyError as exc:
            raise ValueError(f"record is missing dimension {dimension!r}") from exc
        key.append(str(value))
    return tuple(key)
