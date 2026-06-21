"""Normalized control table parsing."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from synthpopcan.ipf import IPFMargin


@dataclass
class _MarginGroup:
    dimensions: tuple[str, ...]
    targets: dict[tuple[str, ...], float]


def read_control_margins(path: Path) -> list[IPFMargin]:
    grouped: dict[str, _MarginGroup] = {}
    with path.open(newline="") as handle:
        for row_number, row in enumerate(csv.DictReader(handle), start=2):
            dimensions = parse_dimensions(row.get("dimensions", ""))
            if not dimensions:
                raise ValueError(f"controls row {row_number} has no dimensions")
            try:
                count = float(row["count"])
            except KeyError as exc:
                raise ValueError("controls CSV requires a count column") from exc
            except ValueError as exc:
                raise ValueError(
                    f"controls row {row_number} has invalid count"
                ) from exc

            margin_label = row.get("margin", "").strip()
            margin_key = margin_label or "|".join(dimensions)
            group = grouped.setdefault(margin_key, _MarginGroup(dimensions, {}))
            if group.dimensions != dimensions:
                raise ValueError(
                    f"controls row {row_number} margin {margin_label!r} mixes "
                    f"dimensions {group.dimensions!r} and {dimensions!r}"
                )

            key = tuple(row.get(dimension, "") for dimension in dimensions)
            if key in group.targets:
                raise ValueError(
                    f"controls row {row_number} duplicates target {key!r} "
                    f"for dimensions {dimensions!r}"
                )
            group.targets[key] = count

    return [IPFMargin(group.dimensions, group.targets) for group in grouped.values()]


def parse_dimensions(value: str) -> tuple[str, ...]:
    separator = "|" if "|" in value else ","
    return tuple(part.strip() for part in value.split(separator) if part.strip())
